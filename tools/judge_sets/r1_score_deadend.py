"""r1_score_deadend.py - count how many IMPROVE candidates (crane_plan.improve, the FB11 rule) die
because the replay slot rule dead-ends (no free cell passes step rule), vs. are simply worse.
  python tools/judge_sets/r1_score_deadend.py <set.json> [...] [--order 1]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402

orig = cp.imp_replay
STATS = {"dead": 0, "worse": 0, "better": 0}


def wrapped(ctx, cand, p):
    keep = ctx.CurK
    ctx.CurK = cp.BIG_K + 1
    K, steps = orig(ctx, cand, p)
    ctx.CurK = keep
    if steps is None:
        STATS["dead"] += 1
        return cp.BIG_K, None
    if K >= keep:
        STATS["worse"] += 1
        return cp.BIG_K, None
    STATS["better"] += 1
    return K, steps


cp.imp_replay = wrapped
ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+")
ap.add_argument("--order", type=int, default=1)
a = ap.parse_args()
for f in a.files:
    for k in STATS:
        STATS[k] = 0
    ds = cm.load_dataset(f)
    st = cp.build_state(ds)
    r = cp.plan_fb(st, {"mmode": 2, "order": a.order, "balmode": 0, "lim": 5}, [0, 100, 200, 300], imp_evals=3000)
    tot = sum(STATS.values())
    print("%-28s order=%d J0=%.4f J=%.4f evals=%d  dead-end=%d (%.0f%%) worse=%d accepted=%d" % (
        os.path.basename(f), r["order"], r["J0"], r["J"], r.get("imp_evals", 0), STATS["dead"],
        100.0 * STATS["dead"] / max(1, tot), STATS["worse"], STATS["better"]))
