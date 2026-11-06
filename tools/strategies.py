"""Strategies for the twin. Each factory returns ctrl(obs) -> dict(curt, pb, ev). Mirrors the ST FBs."""
from twin import P, TS

LIM_IMP = P["IMP"] - 1.0
LIM_EXP = P["EXP"] - 1.0


def bc_max(soc):
    return max(0.0, min(P["BCH"], (P["SOC_MAX"] - soc) / 100 * P["CAP"] / (TS * P["ETA_C"])))


def bd_max(soc):
    return max(0.0, min(P["BDC"], (soc - P["SOC_MIN"]) / 100 * P["CAP"] * P["ETA_D"] / TS))


def ev_max(e):
    return min(P["EV_MAX"], e["rem"] / (TS * P["EV_ETA"])) if e["conn"] else 0.0


def guard(o, pb_req, ev_req, curt_req=None):
    """FB_GridGuard replica."""
    bc, bd = bc_max(o["soc"]), bd_max(o["soc"])
    evm = [ev_max(e) for e in o["ev"]]
    slack = [(e["stepsLeft"] - e["rem"] / (P["EV_MAX"] * TS * P["EV_ETA"])) if e["conn"] else 0.0 for e in o["ev"]]
    pb = min(max(pb_req, -bc), bd)
    ev = [min(max(ev_req[j], 0.0), evm[j]) for j in range(4)]
    fa = o["fne"]
    f = fa if curt_req is None else min(fa, max(0.0, curt_req))
    pg = o["fec"] - f + sum(ev) - pb
    flags = []
    if pg > LIM_IMP:
        d = min(pg - LIM_IMP, fa - f)
        if d > 0: f += d; pg -= d
        d = min(pg - LIM_IMP, bd - pb)
        if d > 0: pb += d; pg -= d
        for _ in range(4):
            if pg <= LIM_IMP: break
            cand = [j for j in range(4) if ev[j] > 0]
            if not cand: break
            j = max(cand, key=lambda x: slack[x])
            d = min(pg - LIM_IMP, ev[j]); ev[j] -= d; pg -= d; flags.append("shed")
        if pg > LIM_IMP: flags.append("fail")
    if pg < -LIM_EXP:
        d = min(-LIM_EXP - pg, pb + bc)
        if d > 0: pb -= d; pg += d
        if pg < -LIM_EXP:
            f = max(0.0, f - (-LIM_EXP - pg)); flags.append("curt")
    curt = f if f < fa - 1e-4 else None
    return dict(curt=curt, pb=pb, ev=ev, flags=flags)


def baseline():
    def c(o):
        ev = [ev_max(e) for e in o["ev"]]
        return guard(o, o["fec"] + sum(ev) - o["fne"], ev)
    return c


# ------------------------------------------------------------------------------------------
# Rolling-horizon DP strategy (prototype for the ST FB_Planner)
# ------------------------------------------------------------------------------------------
import numpy as np
import math

GRID_VT, GRID_NT, EXPF, PEAK = P["GRID_VT"], P["GRID_NT"], P["EXPF"], P["PEAK"]
TT_NT = [0.09, 0.1051, 0.0934, 0.0949]
TT_VT = [0.1531, 0.1786, 0.1588, 0.1613]
EUSE = (P["SOC_MAX"] - P["SOC_MIN"]) / 100 * P["CAP"]       # 1200 kWh usable stored energy


class Forecaster:
    """EMA profiles per day type (0 Mon-Fri, 1 Sat, 2 Sun) x qh for FEC; per qh for PV and VT."""
    def __init__(s, a_fec=0.5, a_pv=0.3, a_sig=0.3, cw=0, ctau=16.0, cpv=True, cfec=True):
        s.a_fec, s.a_pv, s.a_sig = a_fec, a_pv, a_sig
        s.cw, s.ctau, s.cpv, s.cfec = cw, ctau, cpv, cfec
        s.hf = []; s.hp = []
        s.rf = 1.0; s.rp = 1.0
        s.fec = [[None] * 96 for _ in range(3)]
        s.sig = [[0.0] * 96 for _ in range(3)]
        s.pv = [None] * 96
        s.vt = [False] * 96

    @staticmethod
    def dtype(wd):
        return 0 if wd <= 5 else (1 if wd == 6 else 2)

    def update(s, t, fec, pv, vt):
        s.cur = fec
        dt = s.dtype(t["weekday"]); q = t["qh"]
        f = s.fec[dt][q]
        p0 = s.pv[q]
        if s.cw > 0:
            s.hf.append((fec, f if f is not None else fec)); s.hf = s.hf[-s.cw:]
            s.hp.append((pv, p0 if p0 is not None else pv)); s.hp = s.hp[-s.cw:]
            af = sum(x for x, _ in s.hf); bf = sum(y for _, y in s.hf)
            ap = sum(x for x, _ in s.hp); bp = sum(y for _, y in s.hp)
            s.rf = min(1.5, max(0.5, af / bf)) if (s.cfec and bf > 10.0) else 1.0
            s.rp = min(1.5, max(0.2, ap / bp)) if (s.cpv and bp > 20.0) else 1.0
        if f is not None:
            s.sig[dt][q] += s.a_sig * (abs(fec - f) - s.sig[dt][q])
        s.fec[dt][q] = fec if f is None else f + s.a_fec * (fec - f)
        p = s.pv[q]
        s.pv[q] = pv if p is None else p + s.a_pv * (pv - p)
        s.vt[q] = vt

    def corr(s, r, i):
        return 1.0 + (r - 1.0) * math.exp(-i / s.ctau) if s.cw > 0 else 1.0

    def fec_at(s, k):
        day = k // 96; q = k % 96
        wd = ((2 + day) % 7) + 1
        v = s.fec[s.dtype(wd)][q]
        if v is None:
            v = s.fec[0][q] if s.fec[0][q] is not None else s.cur
        return v

    def sig_at(s, k):
        day = k // 96; q = k % 96
        wd = ((2 + day) % 7) + 1
        return s.sig[s.dtype(wd)][q]

    def pv_at(s, q):
        v = s.pv[q]
        return 0.0 if v is None else v


def dp_strategy(H=96, dE=20.0, pen=20.0, tvf=0.9, pvf=0.6, cap_margin=1.02, realistic=False,
                a_fec=0.5, a_pv=0.3, oracle=False, nacts=21, neg_curt=True, peak_mode=True, dbg=None,
                ksig=0.0, a_sig=0.3, hi_in_dp=True, qf=0.0, cw=0, ctau=16.0, cpv=True, cfec=True):
    fc = Forecaster(a_fec, a_pv, a_sig, cw, ctau, cpv, cfec)
    from twin import load
    D = globals().get("_DATA") or load()
    NS = int(round(EUSE / dE))
    amax_c = int(P["BCH"] * TS * P["ETA_C"] / dE)
    amax_d = int(P["BDC"] * TS / P["ETA_D"] / dE)
    acts = np.arange(-amax_d, amax_c + 1)
    bus = np.where(acts > 0, -(acts * dE) / (TS * P["ETA_C"]), (-acts * dE) * P["ETA_D"] / TS)  # + = discharge
    NA = len(acts)
    # index matrix for V[s+a]
    sidx = np.arange(NS + 1)[:, None] + acts[None, :]
    valid = (sidx >= 0) & (sidx <= NS)
    sidx_c = np.clip(sidx, 0, NS)
    st = dict(month=0, T=0.0)

    def stepcost(n, ci, ce, T, b, nh):
        g = n - b
        imp = np.maximum(g, 0.0); ex = np.minimum(np.maximum(-g, 0.0), LIM_EXP)
        c = imp * TS * ci - ex * TS * ce + qf * imp * imp * TS / 1000.0
        if peak_mode:
            c = c + pen * np.maximum(nh - b - T, 0.0)
        return c

    def c(o):
        t = o["t"]; k = o["k"]
        fc.update(t, o["fec"], o["fne"], o["vt"])
        evm = [ev_max(e) for e in o["ev"]]
        if realistic and o["mode"] == 1:
            h = (96 - t["qh"]) + (96 if t["qh"] >= 52 else 0)
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
            elif oracle:
                fec, pv, vt = D["fec"][kk], D["fne"][kk], D["vt"][kk]
            else:
                fec, pv, vt = fc.fec_at(kk) * fc.corr(fc.rf, i), fc.pv_at(q) * fc.corr(fc.rp, i), fc.vt[q]
            ev = 0.0
            for j in range(4):
                if evrem[j] > 1e-6 and i < evsteps[j]:
                    pe = min(P["EV_MAX"], evrem[j] / (TS * P["EV_ETA"]))
                    evrem[j] -= pe * TS * P["EV_ETA"]; ev += pe
            n[i] = fec + ev - pv; pvh[i] = pv
            if o["mode"] == 1 or i == 0 or oracle:
                p = o["price"][kk]
            else:   # same as ST F_EnergyPrice: quarter of the current month, forecast VT
                qq = (t["month"] - 1) // 3
                p = (TT_VT if vt else TT_NT)[qq]
            ci[i] = p + (GRID_VT if vt else GRID_NT)
            ce[i] = max(0.0, EXPF * p)
        if t["month"] != st["month"]:
            st["month"] = t["month"]; st["T"] = 0.0
        st["T"] = max(st["T"], o["mpeak"])
        E0 = (o["soc"] - P["SOC_MIN"]) / 100 * P["CAP"]
        npk = n.copy(); npk[1:] += (1 - pvf) * pvh[1:]
        if not oracle:
            for i in range(1, h):
                npk[i] += ksig * fc.sig_at(k + i)
        nh = npk if hi_in_dp else n

        def feasible(T):
            E = E0
            for i in range(h):
                g = npk[i]
                if g > T:
                    need = g - T
                    if need > P["BDC"]: return False
                    E -= need * TS / P["ETA_D"]
                    if E < 0: return False
                else:
                    E += min(T - g, P["BCH"], (EUSE - E) / (TS * P["ETA_C"])) * TS * P["ETA_C"]
            return True
        if feasible(st["T"]):
            Tp = st["T"]
        else:
            lo, hi = st["T"], LIM_IMP
            for _ in range(12):
                mid = 0.5 * (lo + hi)
                if feasible(mid): hi = mid
                else: lo = mid
            Tp = min(LIM_IMP, hi * cap_margin)
        T = max(st["T"], Tp)
        tv = float(np.mean(ci)) * tvf
        V = -(np.arange(NS + 1) * dE) * tv
        for i in range(h - 1, 0, -1):
            ca = stepcost(n[i], ci[i], ce[i], T, bus, nh[i])
            M = np.where(valid, ca[None, :] + V[sidx_c], 1e18)
            V = M.min(axis=1)
        bc, bd = bc_max(o["soc"]), bd_max(o["soc"])
        bs = np.linspace(-bc, bd, nacts)
        if n[0] > -bc and n[0] < bd:
            bs = np.append(bs, n[0])          # exact self-consumption candidate
        if peak_mode and n[0] - T > -bc and n[0] - T < bd:
            bs = np.append(bs, n[0] - T)
        E1 = E0 + np.where(bs < 0, -bs * TS * P["ETA_C"], -bs * TS / P["ETA_D"])
        x = np.clip(E1 / dE, 0, NS)
        if h > 1:
            v1 = np.interp(x, np.arange(NS + 1), V)
        else:
            v1 = -E1 * tv
        tot = stepcost(n[0], ci[0], ce[0], T, bs, n[0]) + v1
        pb = float(bs[int(np.argmin(tot))])
        if n[0] - pb > T:
            pb = min(bd, n[0] - T)
        curt = None
        p0 = o["price"][k]
        if neg_curt and p0 < 0 and o["fec"] + sum(evm) - pb - o["fne"] < 0:
            curt = max(0.0, o["fec"] + sum(evm) - pb)
        if dbg is not None:
            dbg.append((k, T, pb, o["soc"]))
        return guard(o, pb, evm, curt)
    return c
