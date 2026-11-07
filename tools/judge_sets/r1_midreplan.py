"""r1_midreplan.py - judge round 1: replan after EVERY transfer k of the PLC's in-order (order 1) plan,
exactly as FB10 does after an ACK with an empty hook / a MANUAL command / ReplanAfterPut (preferred
order 1 + fallback). Counts replans that fall back to free order although the remaining work is still
exactly order-1 feasible (it must be: the original plan continues in order).

  python tools/judge_sets/r1_midreplan.py [dataset dirs/files]   (default tools/crane_data + crane_data_stress)
"""
import glob
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import crane_model as cm      # noqa: E402
import crane_plan as cp       # noqa: E402
import crane_stress as cs     # noqa: E402

CFG = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}
AL = [0, 100, 200, 300]


def one(path):
    ds = cm.load_dataset(path)
    st = cp.build_state(ds)
    if st["init"]["blocking"]:
        return None
    res = cp.plan_fb(st, CFG, AL)
    if res["err"] != 0 or res["order"] != 1:
        return None
    n = len(res["plan"])
    bad = []
    for k in range(1, n):
        ms = cs.mid_state(st, res["plan"], k)
        r = cp.plan_fb(ms, CFG, AL)
        if r["err"] != 0:
            bad.append((k, "err%d" % r["err"]))
        elif r["order"] != 1:
            bad.append((k, "free"))
    return (os.path.basename(path), n, bad)


if __name__ == "__main__":
    paths = []
    for a in sys.argv[1:] or [os.path.join(HERE, "..", "crane_data"), os.path.join(HERE, "..", "crane_data_stress")]:
        paths += sorted(glob.glob(os.path.join(a, "*.json"))) if os.path.isdir(a) else [a]
    with Pool() as p:
        rr = [r for r in p.map(one, paths) if r]
    tot = sum(r[1] - 1 for r in rr)
    nb = sum(len(r[2]) for r in rr)
    print("in-order plans=%d  mid-run replans=%d  replans that leave list order or fail=%d" % (len(rr), tot, nb))
    for r in rr:
        if r[2]:
            print("  %s n=%d  bad k: %s" % (r[0], r[1], r[2][:12]))
