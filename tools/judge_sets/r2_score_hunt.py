"""r2_score_hunt.py - SCORE judge (round 2): broad hunt for sets where order-1 J is clearly beatable.

Generates <count> sets with crane_gen.random_set (N limited to 10..44 so the annealer converges),
writes them as tools/judge_sets/r2_score_hunt_<seed>_<i>.json, and runs r2_score_opt.solve
(exact if C(n,nu) <= 3000, else joint annealing seeded with our plan).

  python tools/judge_sets/r2_score_hunt.py --seed 11 --count 80 --iters 12000
"""
import argparse
import json
import os
import random
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import crane_gen as cg    # noqa: E402
import r2_score_opt as o  # noqa: E402

ITERS = 12000


def one(f):
    ds = cm.load_dataset(f)
    r = o.solve(ds, 1, 2, ITERS, 2, 3000, verbose=False)
    if r.get("judge_plan") and r.get("gain_pct", 0) > 1.0:
        r["saved"] = o.save_plan(os.path.basename(f)[:-5], r, 1, 2)
    r.pop("judge_plan", None)
    return r


def init(it):
    global ITERS
    ITERS = it


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--count", type=int, default=80)
    ap.add_argument("--iters", type=int, default=12000)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    files = []
    while len(files) < a.count:
        nu = rng.randint(3, 22)
        nl = rng.randint(3, 22)
        d = cg.random_set(rng, "r2_score_hunt_%d_%03d" % (a.seed, len(files)), nu=nu, nl=nl)
        nn = sum(1 for v in d["unload"] if v) + sum(1 for v in d["load"] if v)
        if not (10 <= nn <= 44):
            continue
        fn = os.path.join(HERE, d["name"] + ".json")
        with open(fn, "w") as fh:
            json.dump(d, fh)
        files.append(fn)
    with Pool(4, initializer=init, initargs=(a.iters,)) as p:
        res = p.map(one, files, chunksize=1)
    gains = []
    for r in res:
        if r.get("judge_J") is None:
            print("%-28s N=%3d skip err=%s" % (r["name"], r["N"], r.get("err")))
            continue
        gains.append(r["gain_pct"])
        print("%-28s N=%3d ours=%.4f judge=%.4f %s gap=%+.2f%% LB=%.4f%s" % (
            r["name"], r["N"], r["ours_J"], r["judge_J"], "EX" if r["exact"] else "SA", r["gain_pct"], r["lb"],
            "  <<< >1%" if r["gain_pct"] > 1 else ""))
    gains.sort()
    print("sets %d mean gap %.2f%% median %.2f%% max %.2f%% >1%%: %d >2%%: %d" % (
        len(gains), sum(gains) / len(gains), gains[len(gains) // 2], gains[-1],
        sum(1 for g in gains if g > 1), sum(1 for g in gains if g > 2)))


if __name__ == "__main__":
    main()
