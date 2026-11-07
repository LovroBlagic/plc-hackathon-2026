"""r1_order2_rescue.py - judge round 1: of the needless fallbacks (order-1 plan exists, PLC uses free
order), how many would a 1 -> 2 -> 0 fallback chain (try strict order before free) rescue?

  python tools/judge_sets/r1_order2_rescue.py [--n 800] [--seed 777]
"""
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import crane_plan as cp   # noqa: E402
import r1_feas as rf      # noqa: E402
import r1_search as rs    # noqa: E402

SEED = 777


def f(i):
    ds = rs.gen(i, SEED)
    if ds is None:
        return None
    st = cp.build_state(ds)
    if st["init"]["blocking"] or not rf.feasible(ds, st, 1):
        return None
    r = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])
    if r["err"] != 0 or r["order"] != 0:
        return None
    r2 = cp.plan(st, {"mmode": 2, "order": 2, "balmode": 0, "lim": 5}, [0, 100, 200, 300])
    return (ds["name"], r2["err"], rf.feasible(ds, st, 2))


if __name__ == "__main__":
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 800
    with Pool() as p:
        rr = [x for x in p.map(f, range(n)) if x]
    print("needless=%d  order2-greedy-succeeds=%d  order2-exactly-feasible=%d" % (
        len(rr), sum(1 for r in rr if r[1] == 0), sum(1 for r in rr if r[2])))
    for r in rr:
        print(r)
