"""r1_score_decomp.py - split the gap: our plan's SEQUENCE re-slotted with optimal (Hungarian)
destinations vs our plan as is.  Shows how much is lost purely by the sequential slot rule.

  python tools/judge_sets/r1_score_decomp.py <set.json> [...] [--order 1]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import r1_score_opt as o  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--order", type=int, default=1)
    ap.add_argument("--mmode", type=int, default=2)
    a = ap.parse_args()
    for f in a.files:
        ds = cm.load_dataset(f)
        r, st = o.ours(ds, a.order, a.mmode)
        if r["err"] != 0 or not r["plan"]:
            continue
        pr = o.Prob(ds, a.mmode, 5, r["order"])
        key = {(s.kind, s.idx): k for k, s in enumerate(pr.src)}
        seq = [key[(t["kind"], t["list_idx"])] for t in r["plan"]]
        sides0 = {key[(t["kind"], t["list_idx"])]: (0 if t["dst"][0] <= 1 else 1) for t in r["plan"] if t["kind"] == 2}
        K, d, _ = pr.eval_full(seq, sides0)
        if d is None:
            print("%s: re-slot infeasible" % os.path.basename(f))
            continue
        plan, T, M, J = pr.check(seq, d)
        print("%-34s ours J=%.4f  same sequence + optimal slots J=%.4f  (slot-rule loss %.2f%%)" % (
            os.path.basename(f), r["J"], J, 100 * (r["J"] / J - 1)))


if __name__ == "__main__":
    main()
