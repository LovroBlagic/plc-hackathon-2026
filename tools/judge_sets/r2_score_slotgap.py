"""r2_score_slotgap.py - SCORE judge (round 2): how far is the SLOT phase from the optimal drop cells
for OUR OWN final transfer sequence?  Optimal cells for a fixed sequence = per-bay min-cost
assignment with exact side enumeration (r2_score_opt.Prob2.best_for_seq).

  python tools/judge_sets/r2_score_slotgap.py --mmode 0|2 <glob> ...
"""
import glob
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402
import r2_score_opt as r2  # noqa: E402

MM = 2


def one(f):
    ds = cm.load_dataset(f)
    r, st = r2.ours(ds, 1, MM)
    if r["err"] != 0 or not r["plan"]:
        return None
    pr = r2.Prob2(ds, MM, 5, r["order"])
    key = {(s.kind, s.idx): k for k, s in enumerate(pr.src)}
    seq = [key[(t["kind"], t["list_idx"])] for t in r["plan"]]
    K, d, sv = pr.best_for_seq(seq)
    if K >= r2.BIG:
        return None
    plan, T, M, J = pr.check(seq, d)
    return {"name": ds["name"], "N": st["N"], "ours": r["J"], "opt": J}


def init(m):
    global MM
    MM = m


def main():
    mm = 2
    files = []
    for a in sys.argv[1:]:
        if a.startswith("--mmode"):
            continue
        if a in ("0", "1", "2"):
            mm = int(a)
            continue
        files += sorted(glob.glob(a))
    with Pool(4, initializer=init, initargs=(mm,)) as p:
        res = [o for o in p.map(one, files, chunksize=1) if o]
    gs = sorted(((100 * (o["ours"] / o["opt"] - 1), o) for o in res), key=lambda t: -t[0])
    for g, o in gs[:12]:
        print("%-30s N=%3d ours=%.4f same-seq-optimal-cells=%.4f gap=%+.2f%%" % (o["name"], o["N"], o["ours"], o["opt"], g))
    print("mmode %d: %d sets, mean %.3f%%, max %.2f%%, >0.5%%: %d, >1%%: %d" % (
        mm, len(gs), sum(g for g, _ in gs) / len(gs), gs[0][0], sum(1 for g, _ in gs if g > 0.5),
        sum(1 for g, _ in gs if g > 1)))


if __name__ == "__main__":
    main()
