"""Candidate controller "capmodel": learned monthly peak-cap policy (twin only, ST-portable).

Idea (peak is ~88 % of the v5 gap to the LP bound; v5's cap comes from ONE pessimistic trajectory,
expected + k*sigma at EVERY step and PV*pvf, which overstates daily risk because it assumes all
per-step errors happen together; the DP then imports "for free" up to that cap and the cap becomes
the month's peak):
  * Day library (own history only): ring buffers of the last NW workdays / NWE Saturdays / NWE
    Sundays of the REALISED net load, base = FEC - PV_available, and the EV power we drew.
  * Daily statistic: at each day end R_d = the lowest cap that would have held that day starting
    with a full battery at 00:00 (bisection). Kept per day type; used for the optional monthly floor.
  * Scenario cap: for each library day s a horizon trajectory is built from the library days of the
    matching day types (today -> s-th latest day of today's type, tomorrow -> s-th latest of
    tomorrow's type), plus an intraday additive correction (today's actual base minus the scenario's
    over the last W steps, fading with tau), plus EV = max(known connected sessions, library EV).
    For each scenario the lowest cap T_s feasible from the current stored energy (incl. recharge
    under the cap, same feasibility rule as v5) is computed. Cap = the (r+1)-th largest T_s
    (r = number of library days we accept to miss), r larger early in the month ("avoid ratcheting
    the cap early": many days remain, the cap can still be raised later at the same price).
  * The paid peak is sunk: T = max(paid peak, cap * margin, optional floor).
  * Pre-charge target: from the critical scenario (the one defining the cap) a reverse recursion gives
    need_i = stored energy needed at step i to hold T for the rest of the horizon; the DP adds
    pre_w * max(need_i - E, 0) per state/step (an explicit SoC floor; at night it becomes the
    "SoC by the morning" target).  DP energy costs use the v5 expected forecast.
  * Cold start / few library days: falls back to the v5 cap (EMA + k*sigma, PV*pvf).
Rules: past data only (own measurements and the price tables), no embedded profiles.
API: make(**kw) -> ctrl(obs) for twin.simulate; config(mode); v5_config(mode); make_mode(mode, **over).
"""
import os, sys, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(HERE))
from twin import P, TS, CUM                               # noqa: E402
from strategies import Forecaster, guard, bc_max, bd_max, ev_max, LIM_IMP, LIM_EXP, EUSE, TT_NT, TT_VT  # noqa: E402

GRID_VT, GRID_NT, EXPF = P["GRID_VT"], P["GRID_NT"], P["EXPF"]
ETC, ETD, BCH, BDC = P["ETA_C"], P["ETA_D"], P["BCH"], P["BDC"]


def _wd(day):
    return ((2 + day) % 7) + 1


def _dt(wd):
    return 0 if wd <= 5 else (1 if wd == 6 else 2)


def _feas(E0, arr, Ts):
    """Vectorised v5 feasibility. arr: (S, h) net load; Ts: (S, C) caps -> (S, C) bool."""
    E = np.full(Ts.shape, float(E0))
    ok = np.ones(Ts.shape, dtype=bool)
    for i in range(arr.shape[1]):
        g = arr[:, i:i + 1]
        over = g - Ts
        ok &= over <= BDC
        dis = np.maximum(over, 0.0) * (TS / ETD)
        chg = np.minimum(np.minimum(np.maximum(-over, 0.0), BCH), (EUSE - E) / (TS * ETC)) * (TS * ETC)
        E = E - dis + np.where(over > 0, 0.0, chg)
        ok &= E >= 0.0
    return ok


def _min_caps(E0, arr, lo):
    """Lowest feasible cap per scenario in [lo, LIM_IMP], ~1 kW resolution (ST: bisection, 10 iter)."""
    S = arr.shape[0]
    g1 = np.linspace(lo, LIM_IMP, 33)
    ok = _feas(E0, arr, np.tile(g1, (S, 1)))
    res = np.full(S, LIM_IMP)
    lo2 = np.full(S, lo)
    for s in range(S):
        idx = np.flatnonzero(ok[s])
        if len(idx) == 0:
            res[s] = LIM_IMP; lo2[s] = np.nan
        elif idx[0] == 0:
            res[s] = lo; lo2[s] = np.nan
        else:
            lo2[s] = g1[idx[0] - 1]; res[s] = g1[idx[0]]
    need = ~np.isnan(lo2)
    if need.any():
        sub = arr[need]
        a = lo2[need]; b = res[need]
        g2 = a[:, None] + (b - a)[:, None] * np.linspace(0, 1, 33)[None, :]
        ok2 = _feas(E0, sub, g2)
        first = np.argmax(ok2, axis=1)
        res[need] = g2[np.arange(len(a)), first]
    return res


def _feas1(E0, arr, T):
    E = E0
    for g in arr:
        if g > T:
            nd = g - T
            if nd > BDC: return False
            E -= nd * TS / ETD
            if E < 0: return False
        else:
            E += min(T - g, BCH, (EUSE - E) / (TS * ETC)) * TS * ETC
    return True


def _cap_v5(E0, arr, T0, margin):
    """Exactly strategies.dp_strategy cap() (12-step bisection)."""
    if _feas1(E0, arr, T0):
        return T0
    lo, hi = T0, LIM_IMP
    for _ in range(12):
        mid = 0.5 * (lo + hi)
        if _feas1(E0, arr, mid): hi = mid
        else: lo = mid
    return max(T0, min(LIM_IMP, hi * margin))


def _req_full(day):
    """R_d: lowest cap holding one realised day from a full battery (bisection)."""
    a, b = 0.0, LIM_IMP
    arr = np.asarray(day)[None, :]
    for _ in range(14):
        m = 0.5 * (a + b)
        if _feas(EUSE, arr, np.array([[m]]))[0, 0]:
            b = m
        else:
            a = m
    return b


def make(H=96, dE=40.0, pen=20.0, tvf=0.9, pvf=0.6, cap_margin=1.02, a_fec=0.5, a_pv=0.3, a_sig=0.3,
         nacts=41, neg_curt=True, ksig=0.0, hi_in_dp=True, cw=4, ctau=16.0, hmax=96, coldmax=True,
         realistic=True,
         # ---- capmodel ----
         scen=True, NW=10, NWE=4, smin=4, r_early=1, r_late=0, dl_thr=10, W=4, otau=16.0, ocorr=True,
         ev_hist=True, combine="scen", dpprof="crit", pre_w=0.0, floor_f=0.0, floor_q=0.5, floor_n=20,
         pvf_scen=1.0, dbg=None):
    fc = Forecaster(a_fec, a_pv, a_sig, cw, ctau, True, True)
    Forecaster.D7 = False
    fc.coldmax = coldmax
    NS = int(round(EUSE / dE))
    amax_c = int(BCH * TS * ETC / dE)
    amax_d = int(BDC * TS / ETD / dE)
    acts = np.arange(-amax_d, amax_c + 1)
    bus = np.where(acts > 0, -(acts * dE) / (TS * ETC), (-acts * dE) * ETD / TS)
    sidx = np.arange(NS + 1)[:, None] + acts[None, :]
    valid = (sidx >= 0) & (sidx <= NS)
    sidx_c = np.clip(sidx, 0, NS)
    Egrid = np.arange(NS + 1) * dE
    # day library: per day type, list (newest first) of (base[96], ev[96])
    lib = {0: [], 1: [], 2: []}
    cap_n = {0: NW, 1: NWE, 2: NWE}
    Rd = []                                       # recent daily R_d (all day types), newest last
    cur = dict(day=-1, base=np.zeros(96), ev=np.zeros(96))
    st = dict(month=0, T=0.0, evlast=0.0)

    def stepcost(n, ci, ce, T, b, nh):
        g = n - b
        imp = np.maximum(g, 0.0); ex = np.minimum(np.maximum(-g, 0.0), LIM_EXP)
        return imp * TS * ci - ex * TS * ce + pen * np.maximum(nh - b - T, 0.0)

    def c(o):
        t = o["t"]; k = o["k"]; q = t["qh"]; day = t["day"]
        # ---- library bookkeeping (previous step's EV draw is known now) ----
        if k > 0:
            cur["ev"][(k - 1) % 96] = st["evlast"]
        if day != cur["day"]:
            if cur["day"] >= 0:
                dt0 = _dt(_wd(cur["day"]))
                L = lib[dt0]
                L.insert(0, (cur["base"].copy(), cur["ev"].copy()))
                del L[cap_n[dt0]:]
                Rd.append(_req_full(cur["base"] + cur["ev"]))
                del Rd[:-floor_n]
            cur["day"] = day; cur["base"][:] = 0.0; cur["ev"][:] = 0.0
        cur["base"][q] = o["fec"] - o["fne"]
        fc.update(t, o["fec"], o["fne"], o["vt"])
        evm = [ev_max(e) for e in o["ev"]]
        if realistic and o["mode"] == 1:
            h = min(hmax, (96 - q) + (96 if q >= 52 else 0))
        else:
            h = H
        h = max(1, min(h, 35040 - k))
        n = np.zeros(h); ci = np.zeros(h); ce = np.zeros(h); pvh = np.zeros(h); evk = np.zeros(h)
        evrem = [e["rem"] if e["conn"] else 0.0 for e in o["ev"]]
        evsteps = [e["stepsLeft"] for e in o["ev"]]
        for i in range(h):
            kk = k + i; qq_ = kk % 96
            if i == 0:
                fec, pv, vt = o["fec"], o["fne"], o["vt"]
            else:
                fec, pv, vt = fc.fec_at(kk) * fc.corr(fc.rf, i), fc.pv_at(qq_) * fc.corr(fc.rp, i), fc.vt[qq_]
            ev = 0.0
            for j in range(4):
                if evrem[j] > 1e-6 and i < evsteps[j]:
                    pe = min(P["EV_MAX"], evrem[j] / (TS * P["EV_ETA"]))
                    evrem[j] -= pe * TS * P["EV_ETA"]; ev += pe
            evk[i] = ev
            n[i] = fec + ev - pv; pvh[i] = pv
            if o["mode"] == 1 or i == 0:
                p = o["price"][kk]
            else:
                p = (TT_VT if vt else TT_NT)[(t["month"] - 1) // 3]
            ci[i] = p + (GRID_VT if vt else GRID_NT)
            ce[i] = max(0.0, EXPF * p)
        if t["month"] != st["month"]:
            st["month"] = t["month"]; st["T"] = 0.0
        st["T"] = max(st["T"], o["mpeak"])
        E0 = (o["soc"] - P["SOC_MIN"]) / 100 * P["CAP"]
        # ---- v5 cap (pessimistic single trajectory) ----
        npk = n.copy(); npk[1:] += (1 - pvf) * pvh[1:]
        for i in range(1, h):
            npk[i] += ksig * fc.sig_at(k + i)
        T5 = _cap_v5(E0, npk, st["T"], cap_margin)
        nh = npk if hi_in_dp else n
        T = T5
        need = None
        # ---- capmodel scenario cap ----
        dtoday = _dt(t["weekday"])
        nsc = min(len(lib[0]), cap_n[0]) if dtoday == 0 else len(lib[dtoday])
        if scen and nsc >= smin and len(lib[0]) >= smin:
            S = nsc
            arrb = np.zeros((S, h)); arre = np.zeros((S, h))
            for s in range(S):
                i = 0
                while i < h:
                    kk = k + i; dd = kk // 96; qq0 = kk % 96
                    Ld = lib[_dt(_wd(dd))]
                    seg = min(h - i, 96 - qq0)
                    if Ld:
                        b_, e_ = Ld[s % len(Ld)]
                        arrb[s, i:i + seg] = b_[qq0:qq0 + seg]
                        arre[s, i:i + seg] = e_[qq0:qq0 + seg]
                    else:
                        arrb[s, i:i + seg] = n[i:i + seg] - evk[i:i + seg]
                    i += seg
            if ocorr and q >= 1:
                # additive intraday correction: today's actual base vs the scenario's same quarter-hours
                lo_ = max(0, q - W)
                act = cur["base"][lo_:q].mean()
                Lt = lib[dtoday]
                dec = np.exp(-np.arange(1, h) / otau)
                for s in range(S):
                    off = act - Lt[s % len(Lt)][0][lo_:q].mean()
                    arrb[s, 1:] += off * dec
            if pvf_scen != 1.0:
                arrb[:, 1:] += (1 - pvf_scen) * pvh[1:][None, :]
            # EV: known connected sessions, plus (ev_hist) the library day's EV draw where it is larger
            arr = arrb + (np.maximum(arre, evk[None, :]) if ev_hist else evk[None, :])
            arr[:, 0] = n[0]
            Ts = _min_caps(E0, arr, st["T"])
            days_left = CUM[t["month"]] - day
            r = r_early if days_left > dl_thr else r_late
            r = min(r, S - 1)
            order = np.argsort(-Ts)
            scrit = int(order[r])
            Tq = float(Ts[scrit])
            Tq = st["T"] if Tq <= st["T"] + 1e-9 else max(st["T"], min(LIM_IMP, Tq * cap_margin))
            if combine == "scen":
                T = Tq
            elif combine == "min":
                T = min(T5, Tq)
            elif combine == "max":
                T = max(T5, Tq)
            elif combine == "avg":
                T = 0.5 * (T5 + Tq)
            if dpprof == "crit":
                nh = arr[scrit].copy()
                nh[0] = n[0]
            elif dpprof == "exp":
                nh = n
            # else "v5": keep v5 pessimistic nh
            if pre_w > 0:
                # explicit SoC floor: energy needed at each step to hold T for the rest of the horizon
                g = arr[scrit]
                need = np.zeros(h + 1)
                for i in range(h - 1, -1, -1):
                    x = g[i] - T
                    if x > 0:
                        need[i] = min(EUSE, need[i + 1] + x * TS / ETD)
                    else:
                        need[i] = max(0.0, need[i + 1] - min(-x, BCH) * TS * ETC)
        if floor_f > 0 and len(Rd) >= 5:
            T = max(T, min(LIM_IMP, floor_f * float(np.quantile(Rd, floor_q))))
        tv = float(np.mean(ci)) * tvf
        V = -Egrid * tv
        for i in range(h - 1, 0, -1):
            if need is not None:
                V = V + pre_w * np.maximum(need[i + 1] - Egrid, 0.0)
            ca = stepcost(n[i], ci[i], ce[i], T, bus, nh[i])
            M = np.where(valid, ca[None, :] + V[sidx_c], 1e18)
            V = M.min(axis=1)
        if need is not None:
            V = V + pre_w * np.maximum(need[1] - Egrid, 0.0)
        bc, bd = bc_max(o["soc"]), bd_max(o["soc"])
        bs = np.linspace(-bc, bd, nacts)
        if n[0] > -bc and n[0] < bd:
            bs = np.append(bs, n[0])
        if n[0] - T > -bc and n[0] - T < bd:
            bs = np.append(bs, n[0] - T)
        E1 = E0 + np.where(bs < 0, -bs * TS * ETC, -bs * TS / ETD)
        x = np.clip(E1 / dE, 0, NS)
        v1 = np.interp(x, np.arange(NS + 1), V) if h > 1 else -E1 * tv
        tot = stepcost(n[0], ci[0], ce[0], T, bs, n[0]) + v1
        pb = float(bs[int(np.argmin(tot))])
        if n[0] - pb > T:
            pb = min(bd, n[0] - T)
        curt = None
        if neg_curt and o["price"][k] < 0 and o["fec"] + sum(evm) - pb - o["fne"] < 0:
            curt = max(0.0, o["fec"] + sum(evm) - pb)
        if dbg is not None:
            dbg.append((k, T5, T, pb, o["soc"]))
        out = guard(o, pb, evm, curt)
        st["evlast"] = sum(out["ev"])
        return out
    return c


def v5_config(mode):
    """Exact v5 (ME_v5_k075) parameters = strategies.st_config(mode)."""
    kw = dict(realistic=True, cw=4, dE=40.0, hmax=96, coldmax=True, nacts=41)
    if mode == 0:
        kw.update(ksig=0.75, hi_in_dp=True, pvf=0.6)
    else:
        kw.update(ksig=0.0, hi_in_dp=False, pvf=0.2)
    return kw


def config(mode):
    kw = v5_config(mode)
    kw.update(scen=True)
    return kw


def make_mode(mode, **over):
    kw = config(mode); kw.update(over)
    return make(**kw)
