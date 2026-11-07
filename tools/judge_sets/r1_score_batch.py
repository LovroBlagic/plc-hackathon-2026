"""r1_score_batch.py - run r1_score_opt.solve over many datasets in parallel.

  python tools/judge_sets/r1_score_batch.py [--order 1] [--mmode 2] [--iters 6000] <glob> [<glob> ...]
"""
import argparse
import glob
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import r1_score_opt as o  # noqa: E402

ARGS = None


def one(f):
    ds = cm.load_dataset(f)
    try:
        r = o.solve(ds, ARGS.order, ARGS.mmode, ARGS.iters, verbose=False)
    except Exception as e:  # noqa: BLE001
        return {"name": os.path.basename(f), "err": repr(e)}
    r.pop("judge_plan", None)
    r["file"] = f
    return r


def init(a):
    global ARGS
    ARGS = a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("globs", nargs="+")
    ap.add_argument("--order", type=int, default=1)
    ap.add_argument("--mmode", type=int, default=2)
    ap.add_argument("--iters", type=int, default=6000)
    a = ap.parse_args()
    files = []
    for g in a.globs:
        files += sorted(glob.glob(g))
    with Pool(4, initializer=init, initargs=(a,)) as p:
        res = p.map(one, files)
    gains = []
    for r in res:
        if "err" in r:
            print("%-28s ERROR %s" % (r["name"], r["err"]))
            continue
        if r.get("judge_J") is None:
            print("%-28s N=%3d skip (ours=%s)" % (r["name"], r["N"], r.get("ours_J")))
            continue
        gains.append(r["gain_pct"])
        flag = "  <<< >1%" if r["gain_pct"] > 1.0 else ""
        print("%-28s N=%3d P=%3d ord=%s ours=%.4f judge=%.4f %s gap=%+.2f%% LB=%.4f%s" % (
            r["name"], r["N"], r["P"], r["ours_order"], r["ours_J"], r["judge_J"],
            "EX" if r["exact"] else "SA", r["gain_pct"], r["lb"], flag))
    if gains:
        print("mean gap %.2f%%  max %.2f%%  >1%%: %d / %d" % (sum(gains) / len(gains), max(gains),
                                                          sum(1 for g in gains if g > 1), len(gains)))


if __name__ == "__main__":
    main()
