"""mirror13_par.py - runs tia-src/13_improve_mirror.py's check() over the same job list in parallel.

  python tools/mirror13_par.py [budget=400] [percall=3]   -> IMPROVE_MIRROR runs=N fails=F (same as the serial script)
"""
import glob
import importlib.util
import itertools
import os
import sys
from multiprocessing import Pool

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("mirror13", os.path.join(REPO, "tia-src", "13_improve_mirror.py"))
m13 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m13)


def job(a):
    f, mm, od, bm, dist, budget, percall = a
    r = m13.check(f, {"mmode": mm, "order": od, "balmode": bm, "lim": 5}, budget, dist, percall, [0, 75, 125, 200])
    return (os.path.basename(f), (mm, od, bm, dist), r)


if __name__ == "__main__":
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    percall = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    files = sorted(glob.glob(os.path.join(REPO, "tools", "crane_data", "*.json")))
    files += sorted(glob.glob(os.path.join(REPO, "tools", "crane_data_stress", "*.json")))[::4]
    files += sorted(glob.glob(os.path.join(REPO, "tools", "judge_sets", "r2_jury_imb*.json")))
    jobs = []
    for f in files:
        for mm, od, bm, dist in itertools.product((0, 2), (0, 1), (0, 1), (0, 6)):
            if mm == 2 and (bm == 1 or dist == 6):   # v1.7: full coverage for the default mode 0
                continue
            jobs.append((f, mm, od, bm, dist, budget, percall))
    with Pool() as p:
        res = p.map(job, jobs, chunksize=1)
    tot = fails = 0
    for name, key, r in res:
        if r is None:
            continue
        tot += 1
        if not r[0]:
            fails += 1
            print("FAIL", name, key, r[3], r[4])
    print("IMPROVE_MIRROR runs=%d fails=%d (budget %d, %d/call)" % (tot, fails, budget, percall))
