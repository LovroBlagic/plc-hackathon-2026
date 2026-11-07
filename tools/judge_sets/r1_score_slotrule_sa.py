"""r1_score_slotrule_sa.py - SA over the transfer ORDER, but destinations from OUR OWN replay slot
rule (crane_plan.imp_replay, the exact FB11 IMPROVE rule).  Isolates how much of the order-1 gap
is just the IMPROVE neighbourhood stalling (vs. needing better slots).

  python tools/judge_sets/r1_score_slotrule_sa.py <set.json> [...] [--order 1] [--iters 6000]
"""
import argparse
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402
import r1_score_opt as o  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--order", type=int, default=1)
    ap.add_argument("--mmode", type=int, default=2)
    ap.add_argument("--iters", type=int, default=6000)
    a = ap.parse_args()
    for f in a.files:
        ds = cm.load_dataset(f)
        r, st = o.ours(ds, a.order, a.mmode)
        if r["err"] != 0 or len(r["plan"]) < 2:
            continue
        cfg = dict(r["cfg"])
        ctx = cp.ImpCtx(st, cfg, r)
        ctx.CurK = cp.BIG_K + 1  # disable the abort bound
        nu = sum(1 for s in ctx.src[1:] if s.kind == 1)
        seq = ctx.CurSeq[:]

        def ev(c):
            K, _ = cp.imp_replay(ctx, c, 1)
            return K

        def valid(c):
            if cfg["order"] != 1:
                return True
            u = [i for i in c[1:] if i <= nu]
            l = [i for i in c[1:] if i > nu]
            return u == sorted(u) and l == sorted(l)

        rng = random.Random(7)
        Kc = ev(seq)
        best = (Kc, seq[:])
        n = ctx.n
        for it in range(a.iters):
            temp = 300.0 * (1 - it / a.iters) + 1e-3
            c = seq[:]
            i = rng.randrange(1, n + 1)
            j = rng.randrange(1, n + 1)
            if i == j:
                continue
            ln = rng.choice((1, 1, 2, 3))
            seg = c[i:i + ln]
            del c[i:i + ln]
            c[j:j] = seg
            if len(c) != n + 1 or not valid(c):
                continue
            K = ev(c)
            if K >= cp.BIG_K:
                continue
            if K <= Kc or rng.random() < math.exp(-(K - Kc) / temp):
                seq, Kc = c, K
                if K < best[0]:
                    best = (K, c[:])
        K0 = (r["T"] - st["base_t"]) + 190 * (r["M"] - st["base_m"])
        # J from K: K = T + 190 M; M = 4P (-1) is unchanged by order (mmode 2), so recover T
        K, steps = cp.imp_replay(ctx, best[1], 1)
        if steps is None:
            print("%-34s order=%d ours J=%.4f  slot-rule SA found no feasible order" % (os.path.basename(f), cfg["order"], r["J"]))
            continue
        T, M = steps[n][1], steps[n][2]
        J = cm.J(T, M, st["N"])
        print("%-34s order=%d ours J=%.4f  ours-slot-rule + SA order J=%.4f  (%.2f%%)" % (
            os.path.basename(f), cfg["order"], r["J"], J, 100 * (r["J"] / J - 1)))


if __name__ == "__main__":
    main()
