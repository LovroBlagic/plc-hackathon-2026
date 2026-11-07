"""Candidate "longhorizon": v5 rolling DP + multi-day coarse tail (S2 only; S1 = plain v5).

Idea: keep the fine 15-min DP for the first Hf steps, then extend the look-ahead with coarse blocks of
B steps (constant battery power inside a block, coarse action grid of `nca` energy deltas) up to a total
horizon of Hf + Hc steps (48-72 h).  The monthly peak cap is computed over the whole horizon (fine part
per step, coarse part per block).

Chosen: S1 -> Hc=0 (identical to v5; the S1 tail failed the >200 EUR robustness rule on the dataset
suite).  S2 -> Hf=96, Hc=192, B=8, pfill='last', tcache=True: the tail value is computed as a background
job once per block boundary, spread over B=8 PLC cycles (see make(tcache=...) and ops_estimate()).

No future knowledge: FEC/PV come from the Forecaster (own history), EVs only from the sessions currently
connected, S1 prices from the TT table (quarter of the current month, forecast VT window), S2 prices from
the DA table ONLY up to the publication limit (end of today; end of tomorrow after 13:00).  Beyond the
limit the DA price is filled from the published history (`pfill`).

Usage:  from candidates.longhorizon import make, config
        ctrl = make(**config(mode));  twin.simulate(ctrl, mode, data=d)
"""
import os, sys, math
import numpy as np

_T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _T not in sys.path:
    sys.path.insert(0, _T)
from twin import P, TS, N  # noqa: E402
from strategies import (Forecaster, guard, bc_max, bd_max, ev_max, LIM_IMP, LIM_EXP, EUSE,  # noqa: E402
                        GRID_VT, GRID_NT, EXPF, TT_NT, TT_VT)


def v5_config(mode):
    """Exact v5 (ME_v5_k075) parameters = strategies.st_config(mode)."""
    kw = dict(realistic=True, cw=4, dE=40.0, hmax=96, coldmax=True, nacts=41)
    if mode == 0:
        kw.update(ksig=0.75, hi_in_dp=True, pvf=0.6)
    else:
        kw.update(ksig=0.0, hi_in_dp=False, pvf=0.2)
    return kw


def config(mode):
    """Chosen longhorizon parameters per price mode (S1 = 0, S2 = 1).

    S1: Hc=0, i.e. exactly v5 (the coarse tail failed the robustness rule on the dataset suite:
        syn_peaky +543 EUR, syn_shift +597 EUR vs v5).
    S2: fine part up to the DA publication limit (max Hf) + 48 h coarse tail (2 h blocks) with
        'last published day' prices; tail value computed once per block boundary and spread over
        B cycles (tcache=True), see ops_estimate()."""
    kw = dict(Hf=96, B=8, nca=9, dE=40.0, cw=4, coldmax=True, nacts=41, cap_h=None)
    if mode == 0:
        kw.update(Hc=0, tpess=1.0, ksig=0.75, hi_in_dp=True, pvf=0.6)
    else:
        kw.update(S2_CHOICE)
        kw.update(ksig=0.0, hi_in_dp=False, pvf=0.2, pfill="last", fine_pub=True)
    return kw


S2_CHOICE = dict(Hf=96, Hc=192, tpess=1.0, tcache=True)


FILL_OPS = 50   # forecast fill per horizon step: day-type lookup, 2 corr factors (EXP via table), 4-EV loop,
                # price lookup, ci/ce, npk + sigma  (~50 simple ops; v5 does the same per step)


def ops_estimate(Hf=96, Hc=0, B=8, nca=9, dE=40.0, nacts=41, tcache=False, fill=FILL_OPS, **_):
    """Inner-loop operations per step, worst case (fine part = full Hf, i.e. S2 after 13:00).

    Feasibility passes of the cap bisection = 1 initial check + 12 bisection iterations = 13.
    tcache=True: the tail (forecast fill + backward DP over the coarse blocks) is computed once per block
    boundary and spread over B cycles, so 1/B of it is charged per step; the bisection still uses the
    (cached) tail forecast every step.  Returned 'ratio' is relative to v5 (Hf=96, Hc=0) by the same count."""
    NS1 = int(round(EUSE / dE)) + 1
    amax = int(P["BCH"] * TS * P["ETA_C"] / dE)
    na = 2 * amax + 1
    nb = int(math.ceil(Hc / float(B))) if Hc > 0 else 0
    npass = 13
    fine = (Hf - 1) * (NS1 * na + na)
    coarse = nb * (NS1 * nca + nca * B)
    bis = npass * (Hf + nb * 2 + nb * B)           # fine per step; tail: block sums of need/room + per-block update
    fillf = Hf * fill
    fillt = (Hf + Hc) * fill if tcache else Hc * fill   # spread job re-runs the EV/forecast walk from step 0
    first = nacts * 3
    tail = coarse + fillt
    per_tail = tail / float(B) if tcache else tail
    total = fine + bis + fillf + first + per_tail
    v5 = (95 * (NS1 * na + na)) + npass * 96 + 96 * fill + nacts * 3
    return dict(fine=fine, coarse=coarse, bisection=bis, fill=fillf + (fillt if not tcache else 0),
                tail_job=tail if tcache else 0, first=first, total=int(total), v5=v5,
                ratio=round(total / v5, 3), tail_unspread=int(fine + bis + fillf + first + tail))


def make(Hf=96, Hc=96, B=8, nca=9, dE=40.0, pen=20.0, tvf=0.9, pvf=0.6, cap_margin=1.02,
         a_fec=0.5, a_pv=0.3, a_sig=0.3, nacts=41, neg_curt=True, ksig=0.0, hi_in_dp=True,
         cw=4, ctau=16.0, coldmax=True, cap_h=None, pfill="last", fine_pub=True, cpen=1.0,
         tv_h=None, realistic=True, fixtot=False, tpess=1.0, tcache=False, tcap=True, dbg=None):
    """Controller factory (same contract as strategies.dp_strategy).

    Hf      fine 15-min steps (S2 with fine_pub: limited to the published DA horizon)
    Hc      extra coarse steps after the fine part (0 = plain v5 DP); B = steps per coarse block
    nca     number of coarse energy-delta actions per block (strided grid incl. 0)
    cap_h   steps used for the peak-cap bisection (None = whole horizon)
    pfill   DA price beyond publication: 'last' (same qh, last published day), 'week' (same qh 7 days
            earlier), 'mean' (mean of 'last' and 'week')
    cpen    scale of the peak penalty in the coarse part
    tv_h    steps used for the terminal-value mean price (None = whole horizon)
    tpess   scale of the pessimistic margin ((1-pvf)*PV + ksig*sigma) in the coarse tail (1 = as fine part)
    fixtot  S2: keep the total horizon at Hf + Hc even when the fine part is cut at the publication limit
    tcache  PLC-portable tail: blocks aligned to absolute steps (multiples of B, or the DA publication
            limit); the tail value V(ts) + tail forecast is computed as a background job started at step
            k for the boundary ts needed at step k+B, and becomes usable B steps later (= the job spread
            over B PLC cycles, with the information of the start step: T, forecasts, published prices).
            Between boundaries the fine part runs from k to the cached ts (Hf-B+1 .. Hf steps).
    tcap    tcache only: include the coarse tail in the monthly-cap bisection (False = fine part only)
    """
    fc = Forecaster(a_fec, a_pv, a_sig, cw, ctau, True, True)
    fc.coldmax = coldmax
    NS = int(round(EUSE / dE))
    lev = np.arange(NS + 1)
    amax_c = int(P["BCH"] * TS * P["ETA_C"] / dE)
    amax_d = int(P["BDC"] * TS / P["ETA_D"] / dE)
    acts = np.arange(-amax_d, amax_c + 1)
    bus = np.where(acts > 0, -(acts * dE) / (TS * P["ETA_C"]), (-acts * dE) * P["ETA_D"] / TS)
    sidx = lev[:, None] + acts[None, :]
    valid = (sidx >= 0) & (sidx <= NS)
    sidx_c = np.clip(sidx, 0, NS)
    _cc = {}

    def coarse_acts(bl):
        """Strided level deltas for a block of bl steps, battery power per delta, index tables."""
        if bl in _cc:
            return _cc[bl]
        dc = min(NS, int(P["BCH"] * bl * TS * P["ETA_C"] / dE))
        dd = min(NS, int(P["BDC"] * bl * TS / P["ETA_D"] / dE))
        ds = sorted(set(int(round(x)) for x in np.linspace(-dd, dc, nca)) | {0})
        ds = np.array(ds)
        b = np.where(ds > 0, -(ds * dE) / (bl * TS * P["ETA_C"]), (-ds * dE) * P["ETA_D"] / (bl * TS))
        si = lev[:, None] + ds[None, :]
        va = (si >= 0) & (si <= NS)
        _cc[bl] = (ds, b, va, np.clip(si, 0, NS))
        return _cc[bl]

    st = dict(month=0, T=0.0)

    def stepcost(n, ci, ce, T, b, nh):
        g = n - b
        imp = np.maximum(g, 0.0)
        ex = np.minimum(np.maximum(-g, 0.0), LIM_EXP)
        return imp * TS * ci - ex * TS * ce + pen * np.maximum(nh - b - T, 0.0)

    def price_da(price, kk, pub_end):
        if kk < pub_end:
            return price[kk]
        m = (kk - pub_end) // 96 + 1
        last = price[kk - 96 * m]
        if pfill == "last":
            return last
        wk = price[kk - 96 * 7] if kk - 96 * 7 >= 0 else last
        if pfill == "week":
            return wk if kk - 96 * 7 < pub_end else last
        return 0.5 * (last + wk)

    cache = dict(cur=None, pend=None)

    def fill_arrays(o, h, pub_end):
        t = o["t"]; k = o["k"]; mode = o["mode"]
        n = np.zeros(h); ci = np.zeros(h); ce = np.zeros(h); pvh = np.zeros(h)
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
            n[i] = fec + ev - pv; pvh[i] = pv
            if mode == 1:
                p = price_da(o["price"], kk, pub_end if realistic else N)
            elif i == 0:
                p = o["price"][kk]
            else:
                p = (TT_VT if vt else TT_NT)[qq]
            ci[i] = p + (GRID_VT if vt else GRID_NT)
            ce[i] = max(0.0, EXPF * p)
        npk = n.copy(); npk[1:] += (1 - pvf) * pvh[1:]
        for i in range(1, h):
            npk[i] += ksig * fc.sig_at(k + i)
        return n, ci, ce, npk

    def tail_job(o, ts, T, pub_end):
        """Background job: tail forecast + backward coarse DP for the tail starting at absolute step ts."""
        k = o["k"]
        te = min(ts + Hc, N)
        h = max(1, te - k)
        n, ci, ce, npk = fill_arrays(o, h, pub_end)
        tv = float(np.mean(ci[:h])) * tvf
        V = -(lev * dE) * tv
        a = ts - k
        nt = n[a:]; cit = ci[a:]; cet = ce[a:]
        npt = nt + tpess * (npk[a:] - nt)
        nht = npt if hi_in_dp else nt
        L = len(nt)
        starts = list(range(0, L, B))
        for s0 in reversed(starts):
            bl = min(B, L - s0)
            ds, b, va, si = coarse_acts(bl)
            cost = np.zeros(len(ds))
            for i in range(s0, s0 + bl):
                cost += stepcost(nt[i], cit[i], cet[i], T, b, nht[i])
            V = np.where(va, cost[None, :] + V[si], 1e18).min(axis=1)
        return dict(ts=ts, te=te, V=V, tv=tv, npk=npt, starts=np.array(starts, dtype=int), ready=k + B)

    def c_cached(o):
        t = o["t"]; k = o["k"]
        fc.update(t, o["fec"], o["fne"], o["vt"])
        evm = [ev_max(e) for e in o["ev"]]
        mode = o["mode"]
        day = k // 96
        pub_end = (day + 1) * 96 + (96 if t["qh"] >= 52 else 0)
        pub_lim = pub_end if (mode == 1 and realistic and fine_pub) else None

        def target(base):
            ts = ((base + Hf) // B) * B
            if pub_lim is not None:
                ts = min(ts, pub_lim)
            return min(ts, N)

        if t["month"] != st["month"]:
            st["month"] = t["month"]; st["T"] = 0.0
        st["T"] = max(st["T"], o["mpeak"])
        cur, pend = cache["cur"], cache["pend"]
        if pend is not None and k >= pend["ready"]:
            cur, pend = pend, None
        if cur is None or cur["ts"] <= k or cur["ts"] - k > Hf:
            cur = tail_job(o, max(k + 1, target(k)), st["T"], pub_end)   # start-up / fallback (immediate)
            cache["nfb"] = cache.get("nfb", 0) + 1
        hf = cur["ts"] - k
        n, ci, ce, npk = fill_arrays(o, hf, pub_end)
        nh = npk if hi_in_dp else n
        E0 = (o["soc"] - P["SOC_MIN"]) / 100 * P["CAP"]
        tnp = cur["npk"]; rs = cur["starts"]

        def feasible(T):
            E = E0
            for i in range(hf):
                g = npk[i]
                if g > T:
                    need = g - T
                    if need > P["BDC"]: return False
                    E -= need * TS / P["ETA_D"]
                    if E < 0: return False
                else:
                    E += min(T - g, P["BCH"], (EUSE - E) / (TS * P["ETA_C"])) * TS * P["ETA_C"]
            if len(tnp) == 0 or not tcap:
                return True
            if float(tnp.max()) - T > P["BDC"]:
                return False
            need = np.add.reduceat(np.maximum(tnp - T, 0.0), rs)
            room = np.add.reduceat(np.minimum(np.maximum(T - tnp, 0.0), P["BCH"]), rs)
            for b_ in range(len(rs)):
                E -= need[b_] * TS / P["ETA_D"]
                if E < 0: return False
                E = min(EUSE, E + room[b_] * TS * P["ETA_C"])
            return True

        if feasible(st["T"]):
            T = st["T"]
        else:
            lo, hi = st["T"], LIM_IMP
            for _ in range(12):
                mid = 0.5 * (lo + hi)
                if feasible(mid): hi = mid
                else: lo = mid
            T = max(st["T"], min(LIM_IMP, hi * cap_margin))
        V = cur["V"]
        for i in range(hf - 1, 0, -1):
            ca = stepcost(n[i], ci[i], ce[i], T, bus, nh[i])
            V = np.where(valid, ca[None, :] + V[sidx_c], 1e18).min(axis=1)
        bc, bd = bc_max(o["soc"]), bd_max(o["soc"])
        bs = np.linspace(-bc, bd, nacts)
        if -bc < n[0] < bd:
            bs = np.append(bs, n[0])
        if -bc < n[0] - T < bd:
            bs = np.append(bs, n[0] - T)
        E1 = E0 + np.where(bs < 0, -bs * TS * P["ETA_C"], -bs * TS / P["ETA_D"])
        x = np.clip(E1 / dE, 0, NS)
        v1 = np.interp(x, lev, V)
        tot = stepcost(n[0], ci[0], ce[0], T, bs, n[0]) + v1
        pb = float(bs[int(np.argmin(tot))])
        if n[0] - pb > T:
            pb = min(bd, n[0] - T)
        # start the background job for the boundary needed B steps from now
        if pend is None:
            tt = target(k + B)
            if tt != cur["ts"] and tt > k + B:
                pend = tail_job(o, tt, T, pub_end)
        cache["cur"], cache["pend"] = cur, pend
        curt = None
        if neg_curt and o["price"][k] < 0 and o["fec"] + sum(evm) - pb - o["fne"] < 0:
            curt = max(0.0, o["fec"] + sum(evm) - pb)
        if dbg is not None:
            dbg.append((k, T, pb, o["soc"], hf))
        return guard(o, pb, evm, curt)

    def c(o):
        t = o["t"]; k = o["k"]
        fc.update(t, o["fec"], o["fne"], o["vt"])
        evm = [ev_max(e) for e in o["ev"]]
        mode = o["mode"]
        day = k // 96
        pub_end = (day + 1) * 96 + (96 if t["qh"] >= 52 else 0)
        if mode == 1 and realistic and fine_pub:
            hf = min(Hf, pub_end - k)
        else:
            hf = Hf
        hf = max(1, min(hf, N - k))
        htot = max(hf, min((Hf if fixtot else hf) + Hc, N - k)) if Hc > 0 else hf
        n = np.zeros(htot); ci = np.zeros(htot); ce = np.zeros(htot); pvh = np.zeros(htot)
        evrem = [e["rem"] if e["conn"] else 0.0 for e in o["ev"]]
        evsteps = [e["stepsLeft"] for e in o["ev"]]
        qq = (t["month"] - 1) // 3
        for i in range(htot):
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
            if mode == 1:
                p = price_da(o["price"], kk, pub_end if realistic else N)
            elif i == 0:
                p = o["price"][kk]
            else:
                p = (TT_VT if vt else TT_NT)[qq]
            ci[i] = p + (GRID_VT if vt else GRID_NT)
            ce[i] = max(0.0, EXPF * p)
        if t["month"] != st["month"]:
            st["month"] = t["month"]; st["T"] = 0.0
        st["T"] = max(st["T"], o["mpeak"])
        E0 = (o["soc"] - P["SOC_MIN"]) / 100 * P["CAP"]
        npk = n.copy(); npk[1:] += (1 - pvf) * pvh[1:]
        for i in range(1, htot):
            npk[i] += ksig * fc.sig_at(k + i)
        if tpess != 1.0 and htot > hf:
            npk[hf:] = n[hf:] + tpess * (npk[hf:] - n[hf:])
        nh = npk if hi_in_dp else n

        # block boundaries of the coarse tail
        starts = list(range(hf, htot, B))
        bls = [min(B, htot - s) for s in starts]
        hcap = htot if cap_h is None else max(1, min(htot, cap_h))

        def feasible(T):
            E = E0
            for i in range(min(hf, hcap)):
                g = npk[i]
                if g > T:
                    need = g - T
                    if need > P["BDC"]: return False
                    E -= need * TS / P["ETA_D"]
                    if E < 0: return False
                else:
                    E += min(T - g, P["BCH"], (EUSE - E) / (TS * P["ETA_C"])) * TS * P["ETA_C"]
            if hcap <= hf or not starts:
                return True
            nb = sum(1 for s in starts if s < hcap)
            seg = npk[hf:min(htot, hcap)]
            if len(seg) == 0:
                return True
            if float(seg.max()) - T > P["BDC"]:
                return False
            rs = np.array(starts[:nb]) - hf
            need = np.add.reduceat(np.maximum(seg - T, 0.0), rs)
            room = np.add.reduceat(np.minimum(np.maximum(T - seg, 0.0), P["BCH"]), rs)
            for b_ in range(nb):
                E -= need[b_] * TS / P["ETA_D"]          # discharge first (conservative order)
                if E < 0: return False
                E = min(EUSE, E + room[b_] * TS * P["ETA_C"])
            return True

        if feasible(st["T"]):
            T = st["T"]
        else:
            lo, hi = st["T"], LIM_IMP
            for _ in range(12):
                mid = 0.5 * (lo + hi)
                if feasible(mid): hi = mid
                else: lo = mid
            T = max(st["T"], min(LIM_IMP, hi * cap_margin))

        th = htot if tv_h is None else max(1, min(htot, tv_h))
        tv = float(np.mean(ci[:th])) * tvf
        V = -(lev * dE) * tv
        # coarse tail, backward
        for s, bl in zip(reversed(starts), reversed(bls)):
            ds, b, va, si = coarse_acts(bl)
            cost = np.zeros(len(ds))
            for i in range(s, s + bl):
                cost += stepcost(n[i], ci[i], ce[i], T, b, nh[i]) if cpen == 1.0 else (
                    stepcost(n[i], ci[i], ce[i], 1e9, b, nh[i]) + cpen * pen * np.maximum(nh[i] - b - T, 0.0))
            V = np.where(va, cost[None, :] + V[si], 1e18).min(axis=1)
        # fine part, backward (steps hf-1 .. 1)
        for i in range(hf - 1, 0, -1):
            ca = stepcost(n[i], ci[i], ce[i], T, bus, nh[i])
            V = np.where(valid, ca[None, :] + V[sidx_c], 1e18).min(axis=1)
        # first step: continuous candidates, exact current values
        bc, bd = bc_max(o["soc"]), bd_max(o["soc"])
        bs = np.linspace(-bc, bd, nacts)
        if -bc < n[0] < bd:
            bs = np.append(bs, n[0])
        if -bc < n[0] - T < bd:
            bs = np.append(bs, n[0] - T)
        E1 = E0 + np.where(bs < 0, -bs * TS * P["ETA_C"], -bs * TS / P["ETA_D"])
        x = np.clip(E1 / dE, 0, NS)
        v1 = np.interp(x, lev, V) if htot > 1 else -E1 * tv
        tot = stepcost(n[0], ci[0], ce[0], T, bs, n[0]) + v1
        pb = float(bs[int(np.argmin(tot))])
        if n[0] - pb > T:
            pb = min(bd, n[0] - T)
        curt = None
        if neg_curt and o["price"][k] < 0 and o["fec"] + sum(evm) - pb - o["fne"] < 0:
            curt = max(0.0, o["fec"] + sum(evm) - pb)
        if dbg is not None:
            dbg.append((k, T, pb, o["soc"]))
        return guard(o, pb, evm, curt)
    if tcache and Hc > 0:
        c_cached.cache = cache
        return c_cached
    return c


if __name__ == "__main__":
    import twin
    for kw in [dict(Hf=96, Hc=0), dict(Hf=96, Hc=192), dict(Hf=96, Hc=192, tcache=True),
               dict(Hf=64, Hc=160), dict(Hf=80, Hc=192, tcache=True), dict(Hf=64, Hc=192, tcache=True)]:
        print(kw, ops_estimate(**kw))
    mode = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    r = twin.simulate(make(**config(mode)), mode)
    print(twin.fmt(r))
