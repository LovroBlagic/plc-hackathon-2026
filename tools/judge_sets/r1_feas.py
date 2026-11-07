"""r1_feas.py - judge round 1 (elimination): EXACT feasibility of list orders under the balance rule.

For a dataset, decides by DP whether a plan exists that
  order 1: keeps each list in its own order (interleaving allowed)
  order 2: all unloads in list order, then all loads in list order
  order 0: any order
and keeps the ship balanced (step rule, x-split, lim 5) after EVERY transfer, with capacity
(24 per ship half, 48 yard). Positions inside a half do not matter for balance, so the DP is exact.
Then it runs the team's planner exactly as FB10 does (crane_plan.plan_fb, preferred order 1 + fallback)
and reports where the planner FALLS BACK (violates order) or FAILS although an exact plan exists.

  python tools/judge_sets/r1_feas.py [files/dirs ...] [--evals 0]
"""
import glob
import json
import os
import sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402

LIM = 5


def ok(L, R, L2, R2):
    return abs(L2 - R2) <= LIM or abs(L2 - R2) <= abs(L - R)


def sides(ds, st):
    PU, PL = cp.locate([ds["bay0"], ds["bay1"]], st["PU"], st["PL"])
    us = [0 if s.pos[0] <= 1 else 1 for s in PU]
    return us, len(PL)


def feasible(ds, st, order):
    us, nl = sides(ds, st)
    L0, R0 = cm.lr(ds["bay0"])
    occ1 = sum(1 for x in range(4) for y in range(12) if ds["bay1"][x][y] != 0)
    nu = len(us)
    sys.setrecursionlimit(10000)

    if order in (1, 2):
        @lru_cache(maxsize=None)
        def f(i, j, L, R):
            if i == nu and j == nl:
                return True
            yard = occ1 + i - j
            if i < nu and yard < 48 and (order == 1 or True):
                L2, R2 = (L - 1, R) if us[i] == 0 else (L, R - 1)
                if ok(L, R, L2, R2) and f(i + 1, j, L2, R2):
                    return True
            if j < nl and (order == 1 or i == nu):
                for side in (0, 1):
                    L2, R2 = (L + 1, R) if side == 0 else (L, R + 1)
                    if (L2 if side == 0 else R2) > 24:
                        continue
                    if ok(L, R, L2, R2) and f(i, j + 1, L2, R2):
                        return True
            return False
        r = f(0, 0, L0, R0)
        f.cache_clear()
        return r
    # order 0: (a left unloads done, b right unloads done, j loads, L, R)
    uL = sum(1 for s in us if s == 0)
    uR = nu - uL

    @lru_cache(maxsize=None)
    def g(a, b, j, L, R):
        if a == uL and b == uR and j == nl:
            return True
        yard = occ1 + a + b - j
        if yard < 48:
            if a < uL and ok(L, R, L - 1, R) and g(a + 1, b, j, L - 1, R):
                return True
            if b < uR and ok(L, R, L, R - 1) and g(a, b + 1, j, L, R - 1):
                return True
        if j < nl:
            if L + 1 <= 24 and ok(L, R, L + 1, R) and g(a, b, j + 1, L + 1, R):
                return True
            if R + 1 <= 24 and ok(L, R, L, R + 1) and g(a, b, j + 1, L, R + 1):
                return True
        return False
    r = g(0, 0, 0, L0, R0)
    g.cache_clear()
    return r


def check(path, evals=0):
    ds = cm.load_dataset(path)
    st = cp.build_state(ds)
    if st["init"]["blocking"]:
        return None
    feas = {o: feasible(ds, st, o) for o in (1, 2, 0)}
    cfg = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}
    res = cp.plan_fb(st, cfg, [0, 100, 200, 300], imp_evals=evals)
    raw = cp.plan(st, cfg, [0, 100, 200, 300])
    out = {"name": os.path.basename(path), "feas": feas, "err": res["err"], "order_used": res.get("order"),
           "raw_o1_err": raw["err"], "n": len(st["PU"]) + len(st["PL"]),
           "L0R0": cm.lr(ds["bay0"])}
    issues = []
    if res["err"] == 0 and res["order"] == 0 and feas[1]:
        issues.append("NEEDLESS_FALLBACK order1 feasible but PLC uses free order")
    if res["err"] != 0 and feas[0]:
        issues.append("FALSE_INFEASIBLE planner err %d but free order feasible" % res["err"])
    if res["err"] != 0 and feas[1]:
        issues.append("FALSE_INFEASIBLE_O1 err %d but order1 feasible" % res["err"])
    if res["err"] == 0 and res["order"] == 0 and not feas[1]:
        issues.append("INFO order1 impossible -> forced free order")
    out["issues"] = issues
    return out


def main(argv):
    evals = 0
    paths = []
    it = iter(argv)
    for a in it:
        if a == "--evals":
            evals = int(next(it))
        elif os.path.isdir(a):
            paths += sorted(glob.glob(os.path.join(a, "*.json")))
        else:
            paths.append(a)
    if not paths:
        for d in ("crane_data", "crane_data_stress"):
            paths += sorted(glob.glob(os.path.join(HERE, "..", d, "*.json")))
        paths += sorted(glob.glob(os.path.join(HERE, "r1_elimination_*.json")))
    cnt = {}
    for p in paths:
        try:
            r = check(p, evals)
        except Exception as e:  # noqa
            print("ERR", p, e)
            continue
        if r is None:
            continue
        for i in r["issues"]:
            k = i.split()[0]
            cnt[k] = cnt.get(k, 0) + 1
        if r["issues"]:
            print("%-40s n=%2d LR=%s feas(o1,o2,o0)=%s err=%d used=%s rawO1=%d  %s" % (
                r["name"], r["n"], r["L0R0"], (r["feas"][1], r["feas"][2], r["feas"][0]), r["err"],
                r["order_used"], r["raw_o1_err"], "; ".join(r["issues"])))
    print("FEAS_SUMMARY", cnt, "files", len(paths))


if __name__ == "__main__":
    main(sys.argv[1:])
