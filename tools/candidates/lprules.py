"""LP-guided rules on top of the v5 DP controller (candidate "lprules").

Factory:  make(mode, **kw)  -> ctrl(obs) compatible with twin.simulate (same contract as strategies.dp_strategy).
          make_s1(**kw) / make_s2(**kw) use the tuned per-mode defaults (S1_KW / S2_KW below).
With all rule parameters at their neutral values, make(mode) reproduces strategies.dp_strategy(**st_config(mode))
(v5 = ME_v5_k075) step for step.

What the full-year LP (tools/lp_bound.py) does with the monthly peak, and the rules distilled from it
(no LP trajectories and no practice-data values are embedded; only scalar parameters):
  * The LP holds ONE flat import level P_m for the whole month; on workdays import sits at P_m from the night
    charging window through the end of the load window, and the battery is drained only by the load above P_m.
    Its P_m equals the max over days of the daily minimal shaving cap (battery full in the morning).
  * Our v5 discharges "discretionarily" (import below the paid peak) early in the VT window because, inside
    one tariff block, the DP is indifferent about WHEN it discharges.  When the afternoon then turns out
    heavier than forecast the battery is empty and the peak jumps (e.g. 748 vs 565 kW).
  Rule G  "glide-path reserve" (peak-window discharge spreading): on workdays the stored energy should not drop
          below a reserve line R(q) that is gl_E kWh at quarter-hour gl_q0 and falls linearly to 0 at gl_q1;
          each kWh below the line costs gl_rho EUR per step in the DP (soft; far below the cap penalty, so it
          never raises the peak, it only re-orders discretionary discharge).  Weekend days use gl_we * gl_E.
  Rule A  "late discharge preference": inside the DP the import price of horizon step i is scaled by
          (1 + late_eps * i / 96) -> among equal-price choices discharge as late as possible (LP: flat import).
  Rule C  "charge only to the expected cap": grid charging may not lift import above
          max(paid peak, cap from the EXPECTED forecast) (the pessimistic cap is a safety level for load,
          not a licence to set a new peak by charging).
  Rule B  "history cap ceiling": the controller records the hindsight minimal shaving cap of every finished
          day from its OWN measured net load (one bisection per day).  The pessimistic cap is not allowed to
          exceed max(paid peak, cap from expected forecast, hb_f * rolling-max of the last hb_n workday caps).
Only past data, own history, the price tables and constants are used.
"""
import math, os, sys

import numpy as np

_T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _T not in sys.path:
    sys.path.insert(0, _T)
from twin import P, TS  # noqa: E402
import strategies as S  # noqa: E402
from strategies import (Forecaster, guard, bc_max, bd_max, ev_max, LIM_IMP, LIM_EXP, EUSE,  # noqa: E402
                        GRID_VT, GRID_NT, EXPF, TT_NT, TT_VT)

V5 = {0: dict(realistic=True, cw=4, dE=40.0, hmax=96, coldmax=True, nacts=41, ksig=0.75, hi_in_dp=True, pvf=0.6),
      1: dict(realistic=True, cw=4, dE=40.0, hmax=96, coldmax=True, nacts=41, ksig=0.0, hi_in_dp=False, pvf=0.2)}

NEUTRAL = dict(late_eps=0.0, late_tv=False, gl_E=0.0, gl_q0=28, gl_q1=68, gl_rho=0.0, gl_we=0.0, chg_exp=False,
               hb_n=0, hb_f=1.0)

# tuned per-mode defaults (filled in after tuning; see report)
S1_KW = dict()
S2_KW = dict()


def make_s1(**kw):
    d = dict(S1_KW); d.update(kw)
    return make(0, **d)


def make_s2(**kw):
    d = dict(S2_KW); d.update(kw)
    return make(1, **d)


def make(mode=0, H=96, dE=40.0, pen=20.0, tvf=0.9, pvf=None, cap_margin=1.02, a_fec=0.5, a_pv=0.3, a_sig=0.3,
         nacts=41, ksig=None, hi_in_dp=None, cw=4, ctau=16.0, hmax=96, coldmax=True,
         late_eps=0.0, late_tv=False, gl_E=0.0, gl_q0=28, gl_q1=68, gl_rho=0.0, gl_we=0.0, chg_exp=False, hb_n=0,
         hb_f=1.0, **_ignored):
    v5 = V5[mode]
    pvf = v5["pvf"] if pvf is None else pvf
    ksig = v5["ksig"] if ksig is None else ksig
    hi_in_dp = v5["hi_in_dp"] if hi_in_dp is None else hi_in_dp
    fc = Forecaster(a_fec, a_pv, a_sig, cw, ctau, True, True)
    Forecaster.D7 = False
    fc.coldmax = coldmax
    NS = int(round(EUSE / dE))
    amax_c = int(P["BCH"] * TS * P["ETA_C"] / dE)
    amax_d = int(P["BDC"] * TS / P["ETA_D"] / dE)
    acts = np.arange(-amax_d, amax_c + 1)
    bus = np.where(acts > 0, -(acts * dE) / (TS * P["ETA_C"]), (-acts * dE) * P["ETA_D"] / TS)  # + = discharge
    sidx = np.arange(NS + 1)[:, None] + acts[None, :]
    valid = (sidx >= 0) & (sidx <= NS)
    sidx_c = np.clip(sidx, 0, NS)
    Elev = np.arange(NS + 1) * dE
    use_gl = gl_rho > 0.0 and gl_E > 0.0
    st = dict(month=0, T=0.0, dnet=[], hcaps=[], day=-1)

    def stepcost(n, ci, ce, T, b, nh):
        g = n - b
        imp = np.maximum(g, 0.0); ex = np.minimum(np.maximum(-g, 0.0), LIM_EXP)
        return imp * TS * ci - ex * TS * ce + pen * np.maximum(nh - b - T, 0.0)

    def feasible(T, arr, E0, h):
        E = E0
        for i in range(h):
            g = arr[i]
            if g > T:
                need = g - T
                if need > P["BDC"]: return False
                E -= need * TS / P["ETA_D"]
                if E < 0: return False
            else:
                E += min(T - g, P["BCH"], (EUSE - E) / (TS * P["ETA_C"])) * TS * P["ETA_C"]
        return True

    def cap(arr, E0, h, T0):
        if feasible(T0, arr, E0, h):
            return T0
        lo, hi = T0, LIM_IMP
        for _ in range(12):
            mid = 0.5 * (lo + hi)
            if feasible(mid, arr, E0, h): hi = mid
            else: lo = mid
        return max(T0, min(LIM_IMP, hi * cap_margin))

    def glide(kk):
        """reserve line R (kWh) at the start of step kk"""
        q = kk % 96
        if q < gl_q0 or q >= gl_q1:
            return 0.0
        wd = ((2 + kk // 96) % 7) + 1
        e = gl_E if wd <= 5 else gl_E * gl_we
        return e * (gl_q1 - q) / float(gl_q1 - gl_q0)

    def c(o):
        t = o["t"]; k = o["k"]
        fc.update(t, o["fec"], o["fne"], o["vt"])
        evm = [ev_max(e) for e in o["ev"]]
        # --- rule B bookkeeping: hindsight daily cap from own measured net load (previous day) ---
        if hb_n > 0:
            if t["day"] != st["day"]:
                if len(st["dnet"]) == 96 and st.get("dE0") is not None and st.get("dwd", 7) <= 5:
                    arr = st["dnet"]
                    lo, hi = 0.0, LIM_IMP
                    for _ in range(12):
                        mid = 0.5 * (lo + hi)
                        if feasible(mid, arr, EUSE, 96): hi = mid
                        else: lo = mid
                    st["hcaps"].append(hi); st["hcaps"] = st["hcaps"][-hb_n:]
                st["dnet"] = []; st["day"] = t["day"]; st["dE0"] = 1; st["dwd"] = t["weekday"]
            st["dnet"].append(o["fec"] + sum(evm) - o["fne"])
        if o["mode"] == 1:
            h = min(hmax, (96 - t["qh"]) + (96 if t["qh"] >= 52 else 0))
        else:
            h = H
        h = max(1, min(h, 35040 - k))
        n = np.zeros(h); ci = np.zeros(h); ce = np.zeros(h); pvh = np.zeros(h)
        evrem = [e["rem"] if e["conn"] else 0.0 for e in o["ev"]]
        evsteps = [e["stepsLeft"] for e in o["ev"]]
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
            n[i] = fec + ev - pv; pvh[i] = pv
            if o["mode"] == 1 or i == 0:
                p = o["price"][kk]
            else:
                qq = (t["month"] - 1) // 3
                p = (TT_VT if vt else TT_NT)[qq]
            ci[i] = p + (GRID_VT if vt else GRID_NT)
            ce[i] = max(0.0, EXPF * p)
        if t["month"] != st["month"]:
            st["month"] = t["month"]; st["T"] = 0.0
        st["T"] = max(st["T"], o["mpeak"])
        E0 = (o["soc"] - P["SOC_MIN"]) / 100 * P["CAP"]
        npk = n.copy(); npk[1:] += (1 - pvf) * pvh[1:]
        for i in range(1, h):
            npk[i] += ksig * fc.sig_at(k + i)
        nh = npk if hi_in_dp else n
        T = cap(npk, E0, h, st["T"])
        Tx = None
        if chg_exp or hb_n > 0:
            Tx = cap(n, E0, h, st["T"])          # cap under the expected forecast
        if hb_n > 0 and len(st["hcaps"]) >= min(3, hb_n):
            ceil_ = max(st["T"], Tx, hb_f * max(st["hcaps"]))
            T = min(T, ceil_)
        tv = float(np.mean(ci)) * tvf
        cid = ci if late_eps == 0.0 else ci * (1.0 + late_eps * np.arange(h) / 96.0)
        if late_tv and late_eps != 0.0:      # pure time preference: terminal value scaled consistently
            tv *= 1.0 + late_eps * h / 96.0

        V = -Elev * tv
        for i in range(h - 1, 0, -1):
            ca = stepcost(n[i], cid[i], ce[i], T, bus, nh[i])
            M = np.where(valid, ca[None, :] + V[sidx_c], 1e18)
            V = M.min(axis=1)
            if use_gl:
                R = glide(k + i)
                if R > 0.0:
                    V = V + gl_rho * np.maximum(R - Elev, 0.0)
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
        if chg_exp and n[0] - pb > max(st["T"], Tx):
            lim = max(st["T"], Tx)
            if pb < 0.0:                       # rule C: grid charging only up to the expected cap
                pb = max(pb, min(0.0, n[0] - lim))
            if chg_exp == 2 and n[0] - pb > lim:   # C2: also serve load from the battery down to it
                pb = min(bd, n[0] - lim)
        curt = None
        if o["price"][k] < 0 and o["fec"] + sum(evm) - pb - o["fne"] < 0:
            curt = max(0.0, o["fec"] + sum(evm) - pb)
        return guard(o, pb, evm, curt)
    return c


if __name__ == "__main__":
    # equivalence check vs v5 on the practice data
    import twin
    m = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    r = twin.simulate(make(m), m)
    print("lprules neutral mode", m, twin.fmt(r))
