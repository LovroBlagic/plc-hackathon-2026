"""r2_score_mergedp.py - SCORE judge (round 2): cheap PLC-friendly interleaving DP for order mode 1.

Observation: with the drop cell chosen per transfer as argmin_d W(s_k -> d) + W(d -> s_{k+1}) over the
free cells of the target bay, the plan cost depends only on CONSECUTIVE source pairs:
    K ~= W(crane -> s_1) + sum_k h(s_k, s_{k+1}) + h_last(s_n) + n*(400 + 2*190)
so for per-list order (order 1) the best interleaving of the two lists under that cost is a 2-D merge
DP over (i unloads done, j loads done, last kind) - at most 49*49*2 states, O(nu*nl) - trivially cheap
for FB11.  Cell conflicts and ship balance are then repaired exactly by the min-cost assignment of
r1/r2 (Prob.evaluate with side masks) = what the SLOT phase approximates.

Reports: ours (PLC default, plan_fb) vs DP-merge+assignment vs DP-merge seeded into the r2 annealer.

  python tools/judge_sets/r2_score_mergedp.py <set.json> ...
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402
import r2_score_opt as r2  # noqa: E402

INF = float("inf")


def merge_dp(pr, optimistic=True):
    n, nu = pr.n, pr.nu
    nl = n - nu
    mm = pr.mm
    g = pr.g0
    free = {b: [(x, y) for x in range(4) for y in range(12) if g[b][x][y] == 0] for b in (0, 1)}
    if optimistic:
        # cells that the other list frees during the plan
        for i in range(n):
            s = pr.src[i]
            free[s.pos[2]].append((s.pos[0], s.pos[1]))

    def W(a, b):
        return r2.r1.W(a, b, mm)

    def h(i, j):
        s = pr.src[i]
        tb = 1 - s.pos[2]
        nxt = pr.src[j].pos if j is not None else None
        best = INF
        for (x, y) in free[tb]:
            if (x, y, tb) == s.pos:
                continue
            c = W(s.pos, (x, y, tb)) + (W((x, y, tb), nxt) if nxt is not None else 0)
            if c < best:
                best = c
        return best if best < INF else 10 ** 7

    U = list(range(nu))
    Lr = list(range(nu, n))
    # dp[(i, j, last)] = min cost having done i unloads, j loads; last = 0 (U[i-1]) / 1 (L[j-1])
    dp = {}
    par = {}
    crane = pr.crane
    if nu:
        dp[(1, 0, 0)] = (W(crane, pr.src[U[0]].pos) if crane != pr.src[U[0]].pos else 0)
    if nl:
        dp[(0, 1, 1)] = (W(crane, pr.src[Lr[0]].pos) if crane != pr.src[Lr[0]].pos else 0)
    for tot in range(1, n):
        for i in range(0, min(nu, tot) + 1):
            j = tot - i
            if j > nl:
                continue
            for last in (0, 1):
                key = (i, j, last)
                if key not in dp:
                    continue
                cur = U[i - 1] if last == 0 else Lr[j - 1]
                for nk in (0, 1):
                    if nk == 0 and i < nu:
                        nxt, nkey = U[i], (i + 1, j, 0)
                    elif nk == 1 and j < nl:
                        nxt, nkey = Lr[j], (i, j + 1, 1)
                    else:
                        continue
                    c = dp[key] + h(cur, nxt)
                    if c < dp.get(nkey, INF):
                        dp[nkey] = c
                        par[nkey] = key
    ends = [(dp[(nu, nl, l)] + h(U[nu - 1] if l == 0 else Lr[nl - 1], None), (nu, nl, l))
            for l in (0, 1) if (nu, nl, l) in dp]
    _, key = min(ends)
    seq = []
    while key is not None:
        i, j, last = key
        seq.append(U[i - 1] if last == 0 else Lr[j - 1])
        key = par.get(key)
    seq.reverse()
    return seq


def run(f, sa_iters=0):
    ds = cm.load_dataset(f)
    r, st = r2.ours(ds, 1, 2)
    if r["err"] != 0 or r["order"] != 1:
        return None
    pr = r2.Prob2(ds, 2, 5, 1)
    if pr.n < 2:
        return None
    best = None
    for opt in (True, False):
        seq = merge_dp(pr, opt)
        assert pr.valid_seq(seq)
        K, d = pr.evaluate(seq)
        if K >= r2.BIG:
            sv = pr.fix_sides(seq, {})
            if sv is not None:
                K, d = pr.evaluate(seq, sv)
        if K < r2.BIG and (best is None or K < best[0]):
            best = (K, seq, d)
    out = {"name": ds["name"], "N": st["N"], "ours": r["J"]}
    if best:
        plan, T, M, J = pr.check(best[1], best[2])
        out["dp"] = J
        if sa_iters:
            sides = {i: (0 if best[2][k][0] <= 1 else 1) for k, i in enumerate(best[1]) if pr.src[i].kind == 2}
            b2 = pr.anneal2(best[1], sides, sa_iters, T0=150.0, seed=5)
            plan, T, M, J2 = pr.check(b2[1], b2[2])
            out["dp_sa"] = J2
    return out


def main():
    import glob
    from multiprocessing import Pool
    files = []
    sa = 0
    for a in sys.argv[1:]:
        if a.startswith("--sa="):
            sa = int(a[5:])
            continue
        files += sorted(glob.glob(a))
    with Pool(4) as p:
        res = p.starmap(run, [(f, sa) for f in files])
    g1, g2 = [], []
    for o in res:
        if not o or "dp" not in o:
            continue
        d = 100 * (o["ours"] / o["dp"] - 1)
        g1.append(d)
        s = "%-34s N=%3d ours=%.4f dp+assign=%.4f ours/dp-1=%+.2f%%" % (o["name"], o["N"], o["ours"], o["dp"], d)
        if "dp_sa" in o:
            d2 = 100 * (o["ours"] / o["dp_sa"] - 1)
            g2.append(d2)
            s += "  dp+SA=%.4f ours/dpSA-1=%+.2f%%" % (o["dp_sa"], d2)
        print(s)
    print("ours vs dp+assign: mean %+.2f%%  (positive = DP better), DP better on %d/%d, >1%% better on %d" % (
        sum(g1) / len(g1), sum(1 for x in g1 if x > 0), len(g1), sum(1 for x in g1 if x > 1)))
    if g2:
        print("ours vs dp+SA: mean %+.2f%% max %+.2f%%" % (sum(g2) / len(g2), max(g2)))


if __name__ == "__main__":
    main()
