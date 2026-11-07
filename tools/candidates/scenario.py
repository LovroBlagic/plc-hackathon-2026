"""Candidate controller "scenario": scenario-robust monthly cap + peak deferral (twin only).

Idea (peak is ~88 % of the gap to the LP bound):
  * Scenarios: instead of one pessimistic trajectory (expected + k*sigma at EVERY step, PV*pvf), build K
    load trajectories = expected forecast + the realised forecast residual of the same quarter-hour
    s days ago (s = 1..K), i.e. a residual bootstrap from our own recent errors (FEC and PV residuals,
    each kept in a 96*D ring buffer). They keep the time correlation of real errors, so they are less
    pessimistic than "+k sigma everywhere" but still contain real cloudy/high-load days.
  * Cap: for each scenario the lowest feasible monthly cap T_s (bisection, same feasibility check as v5);
    T_rob = the (qsel+1)-th largest T_s (qsel=0: max) * cap_margin, optionally max'ed with the v5 cap.
  * DP: unchanged v5 rolling-horizon DP with T_rob as the cap (penalty above it).
  * Deferral ("adaptive reserve"): if the chosen first action would raise the month's paid peak S, import
    only the lowest level x in [S, g0] for which every covered scenario is still feasible with cap T_rob
    from the resulting stored energy. The reserve is therefore sized by the scenarios at the current
    time of day and SoC, and the paid peak is raised only when the scenarios really require it.
Rules: past data only (own measurements, price tables), no embedded profiles.
API: make(**kw) -> ctrl(obs) for twin.simulate; config(mode) -> tuned kwargs; v5_config(mode).
     make_mode(mode) = make(**config(mode)).   python tools/candidates/scenario.py [mode] [dataset]

ST port notes (only needed if the candidate is adopted):
  * new data: rResF, rResP : ARRAY[0..671] OF REAL (ring buffers, 7 days x 96, index k MOD 672) + xHave BOOL
    array; scenario s, horizon step i uses index (k + i - 96*s) MOD 672 (always in the past since h <= 96).
  * per step: write residual (actual - profile forecast BEFORE the EMA update) -> 2 subtractions.
  * cap: unchanged v5 bisection on the pessimistic trajectory (capsrc 'v5', as in config()).
  * deferral (only when the DP's first-step import exceeds the paid peak and SoC > floor):
    bisection over the import level x (6 iterations) x K(=5, +1 for the v5 trajectory in S2) scenarios x 95 steps,
    each step = the existing F_Feasible inner loop body (compare, 1 mul, 1 MIN, add).
  * ops/step: DP 27k + v5 cap 1.2k (unchanged) + scenario build 0.5k + deferral <= 6*6*95 = 3.4k
    => ~32k inner iterations worst case (~1.2x v5); the per-scenario caps (capsrc 'scen') would add
    K*12*96 = 5.8k more (~1.4x v5).
"""
import os, sys, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from twin import P, TS                                    # noqa: E402
import strategies as S                                     # noqa: E402
from strategies import Forecaster, guard, bc_max, bd_max, ev_max, LIM_IMP, LIM_EXP, EUSE  # noqa: E402

GRID_VT, GRID_NT, EXPF = P["GRID_VT"], P["GRID_NT"], P["EXPF"]


def _feas_grid(E0, arrs, Ts):
    """Vectorised v5 feasibility: arrs (K, h) import-before-battery trajectories (step 0 excluded by caller
    if wanted), Ts (M,) caps or (M, K) caps, E0 scalar or (M, 1). Returns bool (M, K)."""
    K, h = arrs.shape
    Tm = np.broadcast_to(Ts if np.ndim(Ts) == 2 else np.asarray(Ts)[:, None], (len(Ts), K)).astype(float)
    E = np.broadcast_to(np.asarray(E0, dtype=float), Tm.shape).copy()
    ok = np.ones(Tm.shape, dtype=bool)        # like v5: only an EMPTY battery after a discharge is infeasible
    for i in range(h):
        g = arrs[:, i][None, :]
        d = g - Tm
        over = d > 0
        ok &= ~(over & (d > P["BDC"]))
        dis = np.where(over, d * TS / P["ETA_D"], 0.0)
        chg = np.where(over, 0.0, np.minimum(np.minimum(-d, P["BCH"]), (EUSE - E) / (TS * P["ETA_C"])) * TS * P["ETA_C"])
        E = E - dis + chg
        ok &= ~(over & (E < 0))
    return ok


def _min_caps(E0, arrs, lo):
    """Lowest feasible cap per scenario in [lo, LIM_IMP] (two-pass grid search, ~1 kW resolution).
    Returns (K,) array; LIM_IMP if not even LIM_IMP is feasible."""
    K = arrs.shape[0]
    g1 = np.linspace(lo, LIM_IMP, 33)
    ok = _feas_grid(E0, arrs, g1)                      # (33, K)
    res = np.empty(K)
    lo2 = np.empty(K); hi2 = np.empty(K)
    for s in range(K):
        idx = np.flatnonzero(ok[:, s])
        if len(idx) == 0:
            res[s] = LIM_IMP; lo2[s] = hi2[s] = LIM_IMP
        elif idx[0] == 0:
            res[s] = lo; lo2[s] = hi2[s] = lo
        else:
            j = idx[0]; lo2[s] = g1[j - 1]; hi2[s] = g1[j]; res[s] = np.nan
    need = np.isnan(res)
    if need.any():
        fr = np.linspace(0.0, 1.0, 17)[1:]                 # 16 fine points per bracket
        Tm = lo2[None, :] + (hi2 - lo2)[None, :] * fr[:, None]   # (16, K)
        ok2 = _feas_grid(E0, arrs, Tm)
        for s in np.flatnonzero(need):
            idx = np.flatnonzero(ok2[:, s])
            res[s] = Tm[idx[0], s] if len(idx) else hi2[s]
    return res


def make(K=5, D=7, rs=1.0, rs_pv=1.0, qsel=0, cap_margin=1.02, with_v5=False, capsrc="scen",
         defer=True, defer_set="covered", defer_min=0.0, defer_k0=672, scen_k0=672, defer_mode="full", defer_soc=0.0, defer_chk="cov", wpk=None, hi_dp="v5", ksig=0.75, pvf=0.6, a_fec=0.5, a_pv=0.3,
         a_sig=0.3, cw=4, ctau=16.0, coldmax=True, dE=40.0, hmax=96, nacts=41, pen=20.0, tvf=0.9,
         neg_curt=True, pvneg=True, dbg=None):
    """K scenarios from the last K days' residuals (ring buffer D>=K days). rs/rs_pv scale FEC/PV residuals.
    with_v5: also add the v5 pessimistic trajectory (n + ksig*sig + (1-pvf)*pv) as a scenario.
    capsrc: 'scen' (scenario cap), 'v5' (v5 cap, scenarios only used for deferral), 'max' (max of both).   hi_dp: trajectory penalised in the DP: 'v5' (npk), 'exp' (n),
    'env' (pointwise max over the covered scenarios).  defer: peak deferral at step 0 (see module doc).
    defer_set: 'covered' (scenarios with T_s <= T_rob) or 'all'."""
    assert K <= D
    fc = Forecaster(a_fec, a_pv, a_sig, cw, ctau, True, True)
    fc.coldmax = coldmax
    Forecaster.D7 = False
    NS = int(round(EUSE / dE))
    amax_c = int(P["BCH"] * TS * P["ETA_C"] / dE)
    amax_d = int(P["BDC"] * TS / P["ETA_D"] / dE)
    acts = np.arange(-amax_d, amax_c + 1)
    bus = np.where(acts > 0, -(acts * dE) / (TS * P["ETA_C"]), (-acts * dE) * P["ETA_D"] / TS)
    sidx = np.arange(NS + 1)[:, None] + acts[None, :]
    valid = (sidx >= 0) & (sidx <= NS)
    sidx_c = np.clip(sidx, 0, NS)
    RB = 96 * D
    resf = np.zeros(RB); resp = np.zeros(RB); have = np.zeros(RB, dtype=bool)
    st = dict(month=0, T=0.0)

    def stepcost(n, ci, ce, T, b, nh):
        g = n - b
        imp = np.maximum(g, 0.0); ex = np.minimum(np.maximum(-g, 0.0), LIM_EXP)
        return imp * TS * ci - ex * TS * ce + pen * np.maximum(nh - b - T, 0.0)

    def c(o):
        t = o["t"]; k = o["k"]; mode = o["mode"]
        # residual of this step vs the forecast made before seeing it (profile, no intraday correction)
        if k > 0 or fc.fec[0][0] is not None:
            f0 = fc.fec_at(k); p0 = fc.pv[t["qh"]]
            if f0 is not None and p0 is not None:
                resf[k % RB] = o["fec"] - f0; resp[k % RB] = o["fne"] - p0; have[k % RB] = True
            else:
                have[k % RB] = False
        fc.update(t, o["fec"], o["fne"], o["vt"])
        evm = [ev_max(e) for e in o["ev"]]
        if mode == 1:
            h = min(hmax, (96 - t["qh"]) + (96 if t["qh"] >= 52 else 0))
        else:
            h = hmax
        h = max(1, min(h, 35040 - k))
        n = np.zeros(h); ci = np.zeros(h); ce = np.zeros(h); pvh = np.zeros(h); fech = np.zeros(h)
        evrem = [e["rem"] if e["conn"] else 0.0 for e in o["ev"]]
        evsteps = [e["stepsLeft"] for e in o["ev"]]
        qq = (t["month"] - 1) // 3
        for i in range(h):
            kk = k + i; q = kk % 96
            if i == 0:
                fec, pv, vt = o["fec"], o["fne"], o["vt"]
            else:
                fec, pv, vt = fc.fec_at(kk) * fc.corr(fc.rf, i), fc.pv_at(q) * fc.corr(fc.rp, i), fc.vt[q]
            ev = 0.0
            for j in range(4):
                if evrem[j] > 1e-6 and i < evsteps[j]:
                    pe = min(P["EV_MAX"], evrem[j] / (TS * P["EV_ETA"]))
                    evrem[j] -= pe * TS * P["EV_ETA"]; ev += pe
            n[i] = fec + ev - pv; pvh[i] = pv; fech[i] = fec
            if mode == 1 or i == 0:
                p = o["price"][kk]
            else:
                p = (S.TT_VT if vt else S.TT_NT)[qq]
            ci[i] = p + (GRID_VT if vt else GRID_NT)
            ce[i] = max(0.0, EXPF * p)
        if t["month"] != st["month"]:
            st["month"] = t["month"]; st["T"] = 0.0
        st["T"] = max(st["T"], o["mpeak"])
        Sp = st["T"]
        E0 = (o["soc"] - P["SOC_MIN"]) / 100 * P["CAP"]
        # v5 pessimistic trajectory
        npk = n.copy(); npk[1:] += (1 - pvf) * pvh[1:]
        for i in range(1, h):
            npk[i] += ksig * fc.sig_at(k + i)
        # scenario trajectories (step 0 = actual)
        idx = (k + np.arange(h)[None, :] - 96 * np.arange(1, K + 1)[:, None]) % RB      # (K, h)
        hv = have[idx]
        rf = np.where(hv, resf[idx], 0.0); rp = np.where(hv, resp[idx], 0.0)
        pvs = np.maximum(0.0, pvh[None, :] + rs_pv * rp)
        if pvneg:
            pvs = np.minimum(pvs, P["FNE_MAX"])
        fs = np.maximum(0.0, fech[None, :] + rs * rf)
        scen = n[None, :] + (pvh[None, :] - pvs) + (fs - fech[None, :])
        scen[:, 0] = n[0]
        if with_v5:
            scen = np.vstack([scen, npk[None, :]])
        Ts = _min_caps(E0, scen, Sp)
        srt = np.sort(Ts)[::-1]
        Trob = srt[min(qsel, len(srt) - 1)]
        Trob = max(Sp, min(LIM_IMP, Trob * cap_margin)) if Trob > Sp else Sp
        if capsrc != "scen" or k < scen_k0:
            T5 = _min_caps(E0, npk[None, :], Sp)[0]
            T5 = max(Sp, min(LIM_IMP, T5 * cap_margin)) if T5 > Sp else Sp
            Trob = T5 if (capsrc == "v5" or k < scen_k0) else max(Trob, T5)
        T = Trob
        cov = Ts <= Trob + 1e-6 if defer_set == "covered" else np.ones(len(Ts), dtype=bool)
        if (capsrc != "scen" or k < scen_k0) and not with_v5:
            # the v5 pessimistic trajectory is covered by the cap: include it in the deferral check
            scen = np.vstack([scen, npk[None, :]]); cov = np.append(cov, True)
        if hi_dp == "v5":
            nh = npk
        elif hi_dp == "exp":
            nh = n
        else:
            nh = scen[cov].max(axis=0) if cov.any() else n
        tv = float(np.mean(ci)) * tvf
        V = -(np.arange(NS + 1) * dE) * tv
        for i in range(h - 1, 0, -1):
            ca = stepcost(n[i], ci[i], ce[i], T, bus, nh[i])
            M = np.where(valid, ca[None, :] + V[sidx_c], 1e18)
            V = M.min(axis=1)
        bc, bd = bc_max(o["soc"]), bd_max(o["soc"])
        bs = np.linspace(-bc, bd, nacts)
        if n[0] > -bc and n[0] < bd:
            bs = np.append(bs, n[0])
        if n[0] - T > -bc and n[0] - T < bd:
            bs = np.append(bs, n[0] - T)
        E1 = E0 + np.where(bs < 0, -bs * TS * P["ETA_C"], -bs * TS / P["ETA_D"])
        x = np.clip(E1 / dE, 0, NS)
        v1 = np.interp(x, np.arange(NS + 1), V) if h > 1 else -E1 * tv
        tot = stepcost(n[0], ci[0], ce[0], T, bs, n[0]) + v1
        pb = float(bs[int(np.argmin(tot))])
        if n[0] - pb > T:
            pb = min(bd, n[0] - T)
        g0 = n[0] - pb
        if defer and k >= defer_k0 and o["soc"] > defer_soc and g0 > Sp + 1e-6 and h > 1 and cov.any():
            # lowest import level x in [Sp, g0] that keeps every covered scenario feasible with cap T
            xlo = Sp if defer_mode == "full" else max(Sp, min(g0, n[0]))   # 'charge': only cut charging
            xs = np.linspace(xlo, g0, 17)
            # SoC floor: deferral may only spend the energy above defer_soc (never less than the DP's pb)
            pbfl = max(pb, (o["soc"] - defer_soc) / 100 * P["CAP"] * P["ETA_D"] / TS)
            pbs = np.minimum(np.minimum(n[0] - xs, bd), pbfl)
            E1x = E0 + np.where(pbs < 0, -pbs * TS * P["ETA_C"], -pbs * TS / P["ETA_D"])
            if defer_chk == "none":
                ok = np.ones(len(xs), dtype=bool)
            else:
                sel = scen[cov] if defer_chk == "cov" else scen[:K]
                ok = _feas_grid(E1x[:, None], sel[:, 1:], np.full(len(xs), T)).all(axis=1)
            if ok.any():
                if wpk is None:
                    jx = int(np.flatnonzero(ok)[0])            # lowest feasible import level
                else:
                    # economic deferral: DP objective of the first step (energy now + cost-to-go) plus
                    # wpk * PEAK per kW the paid peak is raised now
                    x1 = np.clip(E1x / dE, 0, NS)
                    v1x = np.interp(x1, np.arange(NS + 1), V)
                    sc = stepcost(n[0], ci[0], ce[0], T, pbs, n[0]) + v1x + wpk * P["PEAK"] * np.maximum(n[0] - pbs - Sp, 0.0)
                    sc = np.where(ok, sc, 1e18)
                    jx = int(np.argmin(sc))
                if g0 - xs[jx] > defer_min:
                    pb = float(pbs[jx])
        curt = None
        if neg_curt and o["price"][k] < 0 and o["fec"] + sum(evm) - pb - o["fne"] < 0:
            curt = max(0.0, o["fec"] + sum(evm) - pb)
        if dbg is not None:
            dbg.append((k, Sp, T, g0, n[0] - pb, o["soc"], list(np.round(Ts))))
        return guard(o, pb, evm, curt)
    return c


def v5_config(mode):
    return S.st_config(mode)


# tuned configs (filled after tuning; see report)
CFG = {0: dict(capsrc="v5", ksig=0.75, pvf=0.6, hi_dp="v5", K=5, defer=True, defer_mode="full", defer_chk="scen",
              defer_soc=80.0),
       1: dict(capsrc="v5", ksig=0.0, pvf=0.2, hi_dp="exp", K=5, qsel=1, defer=True, defer_mode="full",
              defer_chk="cov", defer_soc=50.0)}


def config(mode):
    return dict(CFG[mode])


def make_mode(mode, **over):
    kw = config(mode); kw.update(over)
    return make(**kw)


if __name__ == "__main__":
    import twin
    mode = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    data = None
    if len(sys.argv) > 2:
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "datasets"))
        from loader import load_dataset
        data = load_dataset(sys.argv[2])
    r = twin.simulate(make_mode(mode), mode, data=data)
    print("scenario m%d %s" % (mode, twin.fmt(r)))
