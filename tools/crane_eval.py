"""crane_eval.py - evaluate the planner on every dataset in tools/crane_data.

  python tools/crane_eval.py [--data tools/crane_data] [--quick]

Reports mean/max J per variant and for the winner, variant win counts, a naive baseline
(list order: all unloads then all loads, nearest free slot by W that passes the step rule),
a lower bound (per transfer lift+put 40 s + minimal loaded move 18 s and 1 M), an alpha
sweep, CfgOrderMode 1/2, CfgBalMode 1 and the experimental --algo v2.
Also checks determinism (two identical runs) and executes every plan through the FB1
emulator (crane_plan.simulate) - any assertion failure aborts.
"""

import argparse
import glob
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402

ALPHAS = [0, 50, 100, 150]
SWEEP = [0, 25, 50, 75, 100, 150, 200, 300]


def naive(state, cfg):
    g = [[c[:] for c in state["bay0"]], [c[:] for c in state["bay1"]]]
    loc = cp.locate(g, state["PU"], state["PL"])
    if loc is None:
        return None
    PU, PL = loc
    crane = tuple(state["crane"])
    T = M = 0
    mm, lim = cfg["mmode"], cfg["lim"]
    for s in PU + PL:
        sx, sy, sb = s.pos
        db = 1 - sb
        L, R = cm.lr(g[0])
        best = None
        for x in range(4):
            for y in range(12):
                if g[db][x][y] != 0:
                    continue
                if s.kind == 1:
                    L2, R2 = (L - 1, R) if sx <= 1 else (L, R - 1)
                else:
                    L2, R2 = (L + 1, R) if x <= 1 else (L, R + 1)
                if not cm.step_ok(L, R, L2, R2, lim):
                    continue
                w = cp.wcost(s.pos, (x, y, db), mm)[2]
                if best is None or w < best[0]:
                    best = (w, (x, y, db))
        if best is None:
            return None
        d = best[1]
        et, em, _ = cp.wcost(crane, s.pos, mm)
        lt, lm, _ = cp.wcost(s.pos, d, mm)
        T += et + 400 + lt
        M += em + 2 + lm
        g[db][d[0]][d[1]] = g[sb][sx][sy]
        g[sb][sx][sy] = 0
        crane = d
    return T, M


def eval_one(path):
    ds = cm.load_dataset(path)
    name = os.path.basename(path)[:-5]
    st = cp.build_state(ds)
    out = {"name": name, "N": st["N"], "P": len(st["PU"]) + len(st["PL"])}
    if st["init"]["blocking"]:
        out["status"] = "capacity"
        return out
    base = {"mmode": 0, "order": 0, "balmode": 0, "lim": 5}
    r = cp.plan(st, base, ALPHAS)
    r2 = cp.plan(st, base, ALPHAS)
    out["deterministic"] = cp.csv_lines(r) == cp.csv_lines(r2)
    if r["err"] != 0:
        out["status"] = "err%d" % r["err"]
        return out
    cp.simulate(st, r["plan"], base)
    N = st["N"]
    out["status"] = "ok"
    out["J"] = r["J"]
    out["winner"] = r["variant"]
    out["Jv"] = [cm.J(v["T"], v["M"], N) if v["err"] == 0 else None for v in r["variants"]]
    out["sweep"] = {}
    for a in SWEEP:
        rr = cp.plan(st, base, [a])
        out["sweep"][a] = rr["J"] if rr["err"] == 0 else None
    for key, cfg, alg in (("order1", dict(base, order=1), "v1"), ("order2", dict(base, order=2), "v1"),
                          ("bal1", dict(base, balmode=1), "v1"), ("v2", base, "v2")):
        rr = cp.plan(st, cfg, ALPHAS, None, alg)
        if rr["err"] == 0:
            cp.simulate(st, rr["plan"], cfg)
        out[key] = rr["J"] if rr["err"] == 0 else None
    nv = naive(st, base)
    out["naive"] = cm.J(nv[0], nv[1], N) if nv else None
    P = out["P"]
    out["lb"] = cm.J(P * 580, P * 3, N)
    return out


def stats(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return "   -      -   "
    return "%.4f %.4f" % (sum(v) / len(v), max(v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "crane_data"))
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.data, "*.json")))
    with Pool() as p:
        res = p.map(eval_one, files)
    print("%-42s %3s %3s %-6s %6s %2s %6s %6s %6s %6s %6s %6s %6s" % (
        "dataset", "N", "P", "status", "J", "v", "naive", "LB", "ord1", "ord2", "bal1", "v2", "det"))
    for r in res:
        if r["status"] != "ok":
            print("%-42s %3d %3d %-6s" % (r["name"], r["N"], r["P"], r["status"]))
            continue
        f = lambda x: "  -   " if x is None else "%.4f" % x  # noqa: E731
        print("%-42s %3d %3d %-6s %s %2d %s %s %s %s %s %s %s" % (
            r["name"], r["N"], r["P"], r["status"], f(r["J"]), r["winner"], f(r["naive"]), f(r["lb"]),
            f(r["order1"]), f(r["order2"]), f(r["bal1"]), f(r["v2"]), r["deterministic"]))
    ok = [r for r in res if r["status"] == "ok" and r["P"] > 0]
    groups = (("random (rand_*)", [r for r in ok if r["name"].startswith("rand_")]), ("all feasible, P>0", ok))
    for gname, grp in groups:
        print("\n== %s: %d sets  (mean max)" % (gname, len(grp)))
        print("winner v1 (alpha 0/50/100/150) : %s" % stats([r["J"] for r in grp]))
        for i, al in enumerate(ALPHAS):
            print("  variant %d alpha=%-3d        : %s" % (i + 1, al, stats([r["Jv"][i] for r in grp])))
        wins = [0] * len(ALPHAS)
        for r in grp:
            wins[r["winner"] - 1] += 1
        print("  win counts v1..v4           : %s" % wins)
        for al in SWEEP:
            print("  single alpha=%-3d            : %s" % (al, stats([r["sweep"][al] for r in grp])))
        print("order mode 1                  : %s" % stats([r["order1"] for r in grp]))
        print("order mode 2                  : %s" % stats([r["order2"] for r in grp]))
        print("bal mode 1                    : %s" % stats([r["bal1"] for r in grp]))
        print("algo v2 (2-step top-3)        : %s" % stats([r["v2"] for r in grp]))
        print("naive baseline                : %s" % stats([r["naive"] for r in grp]))
        print("lower bound                   : %s" % stats([r["lb"] for r in grp]))
        print("deterministic all             : %s" % all(r["deterministic"] for r in grp))


if __name__ == "__main__":
    main()
