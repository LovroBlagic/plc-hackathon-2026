"""r1_dpfix_proto.py - judge round 1: proof-of-fix prototype for the needless order fallback.
In order mode 1 the remaining unloads/loads are always a SUFFIX of each list, so the counts passed to
crane_model.reachable(L2, R2, uL, uR, n) identify the suffix exactly. We monkey-patch reachable() with
the exact order-1 DP (tools/judge_sets/r1_feas logic) and re-run plan_fb on every needless-fallback set.
Every plan is re-checked with the team's simulate() (CheckCmd + balance) and list order.

  python tools/judge_sets/r1_dpfix_proto.py [--n 800] [--seed 777]
"""
import os
import sys
from functools import lru_cache
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402
import r1_feas as rf      # noqa: E402
import r1_search as rs    # noqa: E402

ORIG = cm.reachable


def plan_with_dp(ds, st):
    PU, PL = cp.locate([ds["bay0"], ds["bay1"]], st["PU"], st["PL"])
    us = [0 if s.pos[0] <= 1 else 1 for s in PU]
    nu, nl = len(us), len(PL)
    occ1 = sum(1 for x in range(4) for y in range(12) if ds["bay1"][x][y] != 0)

    @lru_cache(maxsize=None)
    def f(i, j, L, R):
        if i == nu and j == nl:
            return True
        if i < nu and occ1 + i - j < 48:
            L2, R2 = (L - 1, R) if us[i] == 0 else (L, R - 1)
            if rf.ok(L, R, L2, R2) and f(i + 1, j, L2, R2):
                return True
        if j < nl:
            for side in (0, 1):
                L2, R2 = (L + 1, R) if side == 0 else (L, R + 1)
                if (L2 if side == 0 else R2) <= 24 and rf.ok(L, R, L2, R2) and f(i, j + 1, L2, R2):
                    return True
        return False

    def reach_dp(L2, R2, uL, uR, n, lim=5):
        return f(nu - (uL + uR), nl - n, L2, R2)

    cm.reachable = reach_dp
    try:
        res = cp.plan(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])
    finally:
        cm.reachable = ORIG
    return res


def one(i):
    ds = rs.gen(i, 777)
    if ds is None:
        return None
    st = cp.build_state(ds)
    if st["init"]["blocking"] or not rf.feasible(ds, st, 1):
        return None
    r = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])
    base_fb = r["err"] == 0 and r["order"] == 0
    r2 = plan_with_dp(ds, st)
    ok = r2["err"] == 0
    if ok:
        cp.simulate(st, r2["plan"], {"mmode": 2, "order": 1, "balmode": 0, "lim": 5})
        for k in (1, 2):
            seq = [t["list_idx"] for t in r2["plan"] if t["kind"] == k]
            assert seq == sorted(seq)
    return (ds["name"], base_fb, ok, r.get("J"), r2.get("J"))


if __name__ == "__main__":
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 800
    with Pool() as p:
        rr = [x for x in p.map(one, range(n)) if x]
    nf = [r for r in rr if r[1]]
    print("order1-feasible sets=%d  baseline needless fallbacks=%d  DP-filter planner succeeds in order 1 on %d/%d; "
          "DP-filter fails on %d order1-feasible sets" % (len(rr), len(nf), sum(1 for r in nf if r[2]), len(nf),
                                                          sum(1 for r in rr if not r[2])))
    for r in nf:
        print("  %s  free-order J=%.4f  in-order(DP) J=%s" % (r[0], r[3], ("%.4f" % r[4]) if r[4] else "-"))
