"""Full-year LP lower bound (perfect knowledge of FEC, PV, prices, EV sessions).
Variables per step k: c (charge, bus), d (discharge, bus), imp, exp, pv (used PV <= available), E (stored energy after k).
Monthly peak P_m >= imp_k. Objective = sum ts*((p+fee)*imp - 0.9*p*exp) + PEAK * sum P_m.
EV demand: fixed to the max-power profile (what our controller delivers) or flexible (session energy by deadline).
Same grid limits as the PLC guard (import <= 999, export <= 498 kW).
Relaxation note: simultaneous c and d in one step is allowed (simulator forbids it); it can only lower the bound.
Usage: python tools/lp_bound.py [mode=0,1] [variant=0] [--evflex]
"""
import sys, os, time
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import twin

P = twin.P; TS = twin.TS; N = twin.N; CUM = twin.CUM
LIM_IMP = P["IMP"] - 1.0
LIM_EXP = P["EXP"] - 1.0
E_MIN = P["SOC_MIN"] / 100 * P["CAP"]
E_MAX = P["SOC_MAX"] / 100 * P["CAP"]
E_INIT = P["SOC_INIT"] / 100 * P["CAP"]


def ev_maxpower(d):
    """EV bus power per step when every connected EV charges at max feasible power (simulator rules)."""
    ev = np.zeros(N)
    for j in range(4):
        for (a, dep, e) in d["ev"][j]:
            rem = e
            for k in range(max(a, 0), min(dep, N)):
                if rem <= 1e-9:
                    break
                pe = min(P["EV_MAX"], rem / (TS * P["EV_ETA"]))
                rem -= pe * TS * P["EV_ETA"]
                ev[k] += pe
    return ev


def month_of_k(k):
    day = k // 96
    m = 1
    while m < 12 and day >= CUM[m]:
        m += 1
    return m


def solve(mode=0, vid=0, evflex=False, verbose=True):
    d = twin.variant(vid)
    fec = np.array(d["fec"]); pva = np.array(d["fne"])
    price = np.array(d["da"] if mode == 1 else d["tt"])
    fee = np.where(np.array(d["vt"]), P["GRID_VT"], P["GRID_NT"])
    months = np.array([month_of_k(k) for k in range(N)])
    NV = 6  # c, d, imp, exp, pv, E
    sessions = []
    if evflex:
        for j in range(4):
            for (a, dep, e) in d["ev"][j]:
                a0, d0 = max(a, 0), min(dep, N)
                if d0 > a0:
                    sessions.append((a0, d0, e))
        nev = sum(s[1] - s[0] for s in sessions)
    else:
        nev = 0
    nx = NV * N + 12 + nev
    iP = NV * N
    iEV = NV * N + 12
    cost = np.zeros(nx)
    lb = np.zeros(nx); ub = np.full(nx, np.inf)
    ks = np.arange(N)
    c_ = NV * ks; d_ = c_ + 1; im_ = c_ + 2; ex_ = c_ + 3; pv_ = c_ + 4; E_ = c_ + 5
    cost[im_] = TS * (price + fee)
    cost[ex_] = -TS * P["EXPF"] * price
    cost[iP:iP + 12] = P["PEAK"]
    ub[c_] = P["BCH"]; ub[d_] = P["BDC"]; ub[im_] = LIM_IMP; ub[ex_] = LIM_EXP; ub[pv_] = pva
    lb[E_] = E_MIN; ub[E_] = E_MAX
    rows, cols, vals = [], [], []
    beq = []
    r = 0
    # balance: imp - exp + pv - c + d - sum(ev_k) = fec (+ ev fixed)
    ev_fixed = ev_maxpower(d) if not evflex else np.zeros(N)
    for k in range(N):
        rows += [r] * 5; cols += [im_[k], ex_[k], pv_[k], c_[k], d_[k]]; vals += [1, -1, 1, -1, 1]
        beq.append(fec[k] + ev_fixed[k]); r += 1
    # EV flexible: ev vars enter balance with -1
    ev_cols_per_k = [[] for _ in range(N)]
    if evflex:
        col = iEV
        sess_rows = []
        for (a0, d0, e) in sessions:
            idx = []
            for k in range(a0, d0):
                ev_cols_per_k[k].append(col); idx.append(col)
                ub[col] = P["EV_MAX"]
                col += 1
            sess_rows.append((idx, e))
        for k in range(N):
            for cc in ev_cols_per_k[k]:
                rows.append(k); cols.append(cc); vals.append(-1)
    # SoC dynamics
    for k in range(N):
        rows += [r, r, r]; cols += [E_[k], c_[k], d_[k]]; vals += [1, -TS * P["ETA_C"], TS / P["ETA_D"]]
        if k > 0:
            rows.append(r); cols.append(E_[k - 1]); vals.append(-1); beq.append(0.0)
        else:
            beq.append(E_INIT)
        r += 1
    if evflex:
        # deliver exactly the session energy (simulator caps at the requirement)
        for (idx, e) in sess_rows:
            for cc in idx:
                rows.append(r); cols.append(cc); vals.append(TS * P["EV_ETA"])
            beq.append(e); r += 1
    Aeq = coo_matrix((vals, (rows, cols)), shape=(r, nx)).tocsr()
    # peaks: imp_k - P_m <= 0
    rr = np.repeat(np.arange(N), 2)
    cc = np.empty(2 * N, dtype=int); cc[0::2] = im_; cc[1::2] = iP + months - 1
    vv = np.empty(2 * N); vv[0::2] = 1; vv[1::2] = -1
    Aub = coo_matrix((vv, (rr, cc)), shape=(N, nx)).tocsr()
    t0 = time.time()
    res = linprog(cost, A_ub=Aub, b_ub=np.zeros(N), A_eq=Aeq, b_eq=np.array(beq),
                  bounds=list(zip(lb, ub)), method="highs")
    if res.status != 0:
        print("LP status", res.status, res.message)
        return None
    x = res.x
    imp = x[im_]; exp_ = x[ex_]; c = x[c_]; dd = x[d_]
    out = dict(cost=res.fun, t=time.time() - t0,
               energy=float(np.sum(TS * price * imp) - np.sum(TS * P["EXPF"] * price * exp_)),
               grid=float(np.sum(TS * fee * imp)), peak=float(P["PEAK"] * np.sum(x[iP:iP + 12])),
               peaks=[round(v) for v in x[iP:iP + 12]], simult=int(np.sum((c > 0.5) & (dd > 0.5))),
               curt=float(np.sum(pva - x[pv_]) * TS), E=x[E_], imp=imp, exp=exp_, months=months,
               price=price, fee=fee)
    # monthly breakdown
    mb = []
    for m in range(1, 13):
        sel = months == m
        mb.append((m, float(np.sum(TS * price[sel] * imp[sel])), float(np.sum(TS * P["EXPF"] * price[sel] * exp_[sel])),
                   float(np.sum(TS * fee[sel] * imp[sel])), float(P["PEAK"] * x[iP + m - 1])))
    out["monthly"] = mb
    if verbose:
        print("LP mode=%d v%d evflex=%s cost=%.2f (energy %.0f grid %.0f peak %.0f) simult_steps=%d curt=%.0f kWh solve=%.1fs"
              % (mode, vid, evflex, out["cost"], out["energy"], out["grid"], out["peak"], out["simult"], out["curt"], out["t"]))
        print("   peaks", out["peaks"])
    return out


if __name__ == "__main__":
    modes = [int(m) for m in (sys.argv[1] if len(sys.argv) > 1 else "0,1").split(",")]
    vids = [int(v) for v in (sys.argv[2] if len(sys.argv) > 2 else "0").split(",")]
    evflex = "--evflex" in sys.argv
    for vid in vids:
        for m in modes:
            solve(m, vid, evflex)
