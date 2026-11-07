"""r2_score_dpseed.py - SCORE judge (round 2): what if FB11 also ran its OWN IMPROVE + SLOT phases on a
merge-DP interleaving (r2_score_mergedp.merge_dp) and kept the better of the two plans?

Uses the team's own crane_plan.improve / slot_search unchanged (3000 evals, default sweeps), so the
result is what a PLC change "add one more start candidate" would give.  Every plan is re-checked with
crane_plan.simulate.

  python tools/judge_sets/r2_score_dpseed.py <glob> ...
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
import r2_score_mergedp as md  # noqa: E402


def one(f):
    ds = cm.load_dataset(f)
    st = cp.build_state(ds)
    cfg = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}
    r = cp.plan_fb(st, cfg, [0, 100, 200, 300], imp_evals=3000)
    if r["err"] != 0 or r["order"] != 1:
        return None
    pr = r2.Prob2(ds, 2, 5, 1)
    if pr.n < 2:
        return None
    best = r["J"]
    for opt in (True, False):
        seq = md.merge_dp(pr, opt)
        K, d = pr.evaluate(seq)
        if K >= r2.BIG:
            sv = pr.fix_sides(seq, {})
            if sv is None:
                continue
            K, d = pr.evaluate(seq, sv)
            if K >= r2.BIG:
                continue
        plan, T, M, J = pr.check(seq, d)
        res = {"err": 0, "plan": plan, "T": T, "M": M, "J": J, "N": st["N"], "variant": 9}
        res = cp.improve(st, r["cfg"], res, 3000)
        res = cp.slot_search(st, r["cfg"], res, cp.SLOT_SWEEPS)
        cp.simulate(st, res["plan"], r["cfg"])
        best = min(best, res["J"])
    return {"name": ds["name"], "N": st["N"], "ours": r["J"], "seeded": best}


def main():
    files = []
    for a in sys.argv[1:]:
        files += sorted(glob.glob(a))
    with Pool(4) as p:
        res = p.map(one, files, chunksize=1)
    gs = []
    for o in res:
        if not o:
            continue
        g = 100 * (o["ours"] / o["seeded"] - 1)
        gs.append((g, o))
        print("%-34s N=%3d ours=%.4f best(ours,dpseed)=%.4f gain=%.2f%%" % (o["name"], o["N"], o["ours"], o["seeded"], g))
    if gs:
        print("sets %d, improved %d, mean gain %.3f%%, max %.2f%%, mean J ours %.5f -> %.5f" % (
            len(gs), sum(1 for g, _ in gs if g > 0), sum(g for g, _ in gs) / len(gs), max(g for g, _ in gs),
            sum(o["ours"] for _, o in gs) / len(gs), sum(o["seeded"] for _, o in gs) / len(gs)))


if __name__ == "__main__":
    main()
