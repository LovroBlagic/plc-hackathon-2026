"""Python twin of the EESTEC Sim_Core (work/dump/.../Simulation/Sim_Core.st), for fast strategy tuning.
NEVER used by the PLC code; profiles are only read here, on the PC.
Usage:  python tools/twin.py [strategy] [mode]      (strategy = name of a function in strategies.py)
"""
import csv, os, re, sys, math, importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "work", "data")
DUMP = os.path.join(ROOT, "work", "dump", "MyController", "Plc Logic", "Application")
N = 35040
TS = 0.25
P = dict(FNE_MAX=750.0, CAP=1500.0, BCH=750.0, BDC=750.0, SOC_MIN=10.0, SOC_MAX=90.0, SOC_INIT=50.0,
         ETA_C=0.95, ETA_D=0.95, EV_MAX=22.0, EV_ETA=0.9, IMP=1000.0, EXP=499.0,
         GRID_VT=0.020811, GRID_NT=0.010404, PEAK=3.865, EXPF=0.9)
CUM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]


def _rd(name):
    return [r[1] for r in list(csv.reader(open(os.path.join(DATA, name))))[1:]]


_cache = {}


def load():
    if _cache:
        return _cache
    _cache["fne"] = [min(max(float(x), 0.0), 750.0) for x in _rd("FNE.csv")]
    _cache["fec"] = [max(float(x), 0.0) for x in _rd("FEC.csv")]
    _cache["vt"] = [x.upper() == "TRUE" for x in _rd("VT.csv")]
    _cache["tt"] = [float(x) for x in _rd("PriceTT.csv")]
    _cache["da"] = [float(x) for x in _rd("PriceDA.csv")]
    txt = open(os.path.join(DUMP, "Init", "Init_Prof_EV.st")).read()
    cnt = [int(v) for v in re.findall(r"Prof_EV\.Count\[\d\] := (\d+);", txt)]
    arr = {int(i): int(v) for i, v in re.findall(r"Prof_EV\.Arr\[(\d+)\] := (-?\d+);", txt)}
    dep = {int(i): int(v) for i, v in re.findall(r"Prof_EV\.Dep\[(\d+)\] := (-?\d+);", txt)}
    en = {int(i): float(v) for i, v in re.findall(r"Prof_EV\.Energy\[(\d+)\] := ([-0-9.Ee]+);", txt)}
    _cache["ev"] = [[(arr[j * 300 + i], dep[j * 300 + i], en[j * 300 + i]) for i in range(cnt[j])] for j in range(4)]
    return _cache


def time_of(k):
    day = k // 96
    m = 1
    while m < 12 and day >= CUM[m]:
        m += 1
    return dict(k=k, qh=k % 96, day=day, month=m, weekday=((2 + day) % 7) + 1)


def simulate(ctrl, mode=0, data=None, verbose=False):
    """ctrl(obs) -> dict(curt=None|kW, pb=signed kW (+dch), ev=[4 kW]). Returns SimScore-like dict."""
    d = data or load()
    price = d["da"] if mode == 1 else d["tt"]
    soc = P["SOC_INIT"]
    evConn = [False] * 4; evRem = [0.0] * 4; evDel = [0.0] * 4; evDep = [0] * 4; evNext = [0] * 4
    tot = dict(E_fne=0, E_fne_curt=0, E_fec=0, E_chg=0, E_dch=0, E_ev=0, E_ev_req=0, E_ev_unmet=0, E_imp=0, E_exp=0,
               cost_energy=0.0, cost_grid=0.0)
    mpeak = [0.0] * 13
    tripped = None
    for k in range(N):
        t = time_of(k)
        for j in range(4):
            if evConn[j] and k >= evDep[j]:
                tot["E_ev_unmet"] += evRem[j]
                evConn[j] = False; evRem[j] = 0.0
            if not evConn[j] and evNext[j] < len(d["ev"][j]):
                a, dp, e = d["ev"][j][evNext[j]]
                if a <= k:
                    evConn[j] = True; evDep[j] = dp; evRem[j] = e; evDel[j] = 0.0
                    tot["E_ev_req"] += e
                    evNext[j] += 1
        fneA = d["fne"][k]; fec = d["fec"][k]
        obs = dict(t=t, k=k, fne=fneA, fec=fec, soc=soc, vt=d["vt"][k], mode=mode, price=price,
                   ev=[dict(conn=evConn[j], rem=evRem[j], dep=min(evDep[j], N - 1), stepsLeft=(min(evDep[j], N - 1) - k) if evConn[j] else 0) for j in range(4)],
                   mpeak=mpeak[t["month"]])
        c = ctrl(obs)
        pf = fneA if c.get("curt") is None else min(fneA, max(0.0, c["curt"]))
        pb = c.get("pb", 0.0)
        pc = pd = 0.0
        if pb < 0:
            pcl = (P["SOC_MAX"] - soc) / 100 * P["CAP"] / (TS * P["ETA_C"])
            pc = max(0.0, min(-pb, min(P["BCH"], pcl)))
        elif pb > 0:
            pdl = (soc - P["SOC_MIN"]) / 100 * P["CAP"] * P["ETA_D"] / TS
            pd = max(0.0, min(pb, min(P["BDC"], pdl)))
        sev = 0.0
        for j in range(4):
            pe = 0.0
            if evConn[j]:
                pe = max(0.0, min(c["ev"][j], P["EV_MAX"]))
                pe = min(pe, evRem[j] / (TS * P["EV_ETA"]))
                dE = TS * P["EV_ETA"] * pe
                evRem[j] = max(0.0, evRem[j] - dE); evDel[j] += dE
            sev += pe
        pg = fec - pf - (pd - pc) + sev
        imp = max(pg, 0.0); ex = max(-pg, 0.0)
        if imp > P["IMP"] + 1e-6 or ex > P["EXP"] + 1e-6:
            tripped = (k, imp, ex)
            break
        soc = soc + TS * (P["ETA_C"] * pc / P["CAP"] - pd / (P["ETA_D"] * P["CAP"])) * 100
        pe_ = price[k]
        fee = P["GRID_VT"] if d["vt"][k] else P["GRID_NT"]
        tot["E_fne"] += pf * TS; tot["E_fne_curt"] += (fneA - pf) * TS; tot["E_fec"] += fec * TS
        tot["E_chg"] += pc * TS; tot["E_dch"] += pd * TS; tot["E_ev"] += sev * TS
        tot["E_imp"] += imp * TS; tot["E_exp"] += ex * TS
        tot["cost_energy"] += imp * TS * pe_ - ex * TS * pe_ * P["EXPF"]
        tot["cost_grid"] += imp * TS * fee
        if imp > mpeak[t["month"]]:
            mpeak[t["month"]] = imp
    tot["cost_peak"] = sum(mpeak) * P["PEAK"]
    tot["cost_total"] = tot["cost_energy"] + tot["cost_grid"] + tot["cost_peak"]
    tot["tripped"] = tripped
    tot["mpeak"] = mpeak[1:]
    tot["ev_pct"] = 100.0 * (tot["E_ev_req"] - tot["E_ev_unmet"]) / tot["E_ev_req"] if tot["E_ev_req"] else 0
    return tot


def fmt(r):
    return "cost=%.2f (en %.0f grid %.0f peak %.0f) Eimp=%.0f Eexp=%.0f Ecurt=%.0f Eev=%.1f unmet=%.2f ev%%=%.3f trip=%s" % (
        r["cost_total"], r["cost_energy"], r["cost_grid"], r["cost_peak"], r["E_imp"], r["E_exp"], r["E_fne_curt"],
        r["E_ev"], r["E_ev_unmet"], r["ev_pct"], r["tripped"])


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    strat = importlib.import_module("strategies")
    name = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    modes = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "0,1").split(",")]
    for m in modes:
        c = getattr(strat, name)()
        r = simulate(c, m)
        print("TWIN %s mode=%d %s" % (name, m, fmt(r)))
        print("   peaks", [round(x) for x in r["mpeak"]])
