"""r1_score_slotswap.py - cheap PLC-friendly fix check: after our planner, run a slot-only local
search on the FIXED sequence: (a) move a transfer's drop to another cell free at that time,
(b) swap the drops of two transfers into the same bay.  Cost is separable
(c_k(d) = W(s_k->d) + W(d->s_{k+1})), so each delta is O(1); balance re-checked with the step rule.
  python tools/judge_sets/r1_score_slotswap.py <set.json> [...] [--order 1]
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
    a = ap.parse_args()
    for f in a.files:
        ds = cm.load_dataset(f)
        r, st = o.ours(ds, a.order, 2)
        if r["err"] != 0 or len(r["plan"]) < 2:
            continue
        pr = o.Prob(ds, 2, 5, r["order"])
        key = {(s.kind, s.idx): k for k, s in enumerate(pr.src)}
        seq = [key[(t["kind"], t["list_idx"])] for t in r["plan"]]
        dst = [tuple(t["dst"]) for t in r["plan"]]
        n = len(seq)
        avail = {}
        for b in (0, 1):
            for (x, y) in o.CELLS:
                avail[(x, y, b)] = 0 if pr.g0[b][x][y] == 0 else 10 ** 9
        for k, i in enumerate(seq):
            s = pr.src[i]
            avail[s.pos] = k + 1

        def c(k, d):
            v = o.W(pr.src[seq[k]].pos, d, 2)
            if k + 1 < n:
                v += o.W(d, pr.src[seq[k + 1]].pos, 2)
            return v

        def used_after(d, k):  # cell d is a drop of some transfer: occupied from then on
            return any(dst[q] == d for q in range(n))

        improved = True
        sweeps = 0
        while improved and sweeps < 50:
            improved = False
            sweeps += 1
            for k in range(n):
                b = dst[k][2]
                for (x, y) in o.CELLS:
                    d = (x, y, b)
                    if avail[d] > k or used_after(d, k):
                        continue
                    if c(k, d) < c(k, dst[k]):
                        old = dst[k]
                        dst[k] = d
                        if pr.balance_ok(seq, dst):
                            improved = True
                        else:
                            dst[k] = old
                for q in range(k + 1, n):
                    if dst[q][2] != b:
                        continue
                    if avail[dst[q]] > k:
                        continue
                    if c(k, dst[q]) + c(q, dst[k]) < c(k, dst[k]) + c(q, dst[q]):
                        dst[k], dst[q] = dst[q], dst[k]
                        if pr.balance_ok(seq, dst):
                            improved = True
                        else:
                            dst[k], dst[q] = dst[q], dst[k]
        plan, T, M, J = pr.check(seq, dst)
        print("%-30s ours J=%.4f  + slot move/swap LS J=%.4f (%.2f%%, %d sweeps)" % (
            os.path.basename(f), r["J"], J, 100 * (r["J"] / J - 1), sweeps))


if __name__ == "__main__":
    main()
