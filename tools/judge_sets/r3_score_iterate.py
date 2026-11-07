"""r3_score_iterate.py - SCORE judge (round 3): cheap fix candidate for the residual order-1 gap.

Instead of slot-aware acceptance inside every IMPROVE replay (R2-SCORE-1 second half, not ported),
simply alternate the team's own phases: IMPROVE -> SLOT -> IMPROVE (restart from the slotted plan) ->
SLOT ..., up to --rounds rounds, keeping the best.  Same code paths as FB11 (crane_plan.improve /
slot_search), only re-entered; each extra round costs at most one IMPROVE budget.
Every final plan is re-executed with crane_plan.simulate and the per-list order is asserted.

  python tools/judge_sets/r3_score_iterate.py [--rounds 4] [--evals 3000] <glob> ...
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
import crane_plan as cp   # noqa: E402

A = None


def one(f):
    d = cm.load_dataset(f)
    st = cp.build_state(d)
    cfg = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}
    r = cp.plan_fb(st, cfg, [0, 100, 200, 300], imp_evals=A.evals)
    if r["err"] != 0 or len(r["plan"]) < 2:
        return None
    c = r["cfg"]
    best = r
    cur = r
    rounds_used = 0
    for k in range(A.rounds - 1):
        nxt = cp.improve(st, c, dict(cur), A.evals, 0)
        nxt = cp.slot_search(st, c, nxt, cp.SLOT_SWEEPS)
        if nxt["J"] < best["J"] - 1e-12:
            best = nxt
            rounds_used = k + 1
        if abs(nxt["J"] - cur["J"]) < 1e-12:
            break
        cur = nxt
    cp.simulate(st, best["plan"], c)
    if c["order"] == 1:
        u = [t["list_idx"] for t in best["plan"] if t["kind"] == 1]
        l = [t["list_idx"] for t in best["plan"] if t["kind"] == 2]
        assert u == sorted(u) and l == sorted(l)
    return {"name": d["name"], "N": st["N"], "ours": r["J"], "new": best["J"], "rounds": rounds_used, "order": c["order"]}


def init(a):
    global A
    A = a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("globs", nargs="+")
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--evals", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    files = []
    for g in a.globs:
        files += sorted(glob.glob(g))
    with Pool(a.workers, initializer=init, initargs=(a,)) as p:
        res = [x for x in p.map(one, files, chunksize=1) if x]
    gs = []
    for o in res:
        g = 100 * (o["ours"] / o["new"] - 1)
        gs.append(g)
        print("%-30s N=%3d ord=%d ours=%.4f iter=%.4f gain=%+.2f%% extra_rounds=%d" % (
            o["name"], o["N"], o["order"], o["ours"], o["new"], g, o["rounds"]))
    print("R3_ITER sets=%d better=%d mean_gain=%+.3f%% max=%+.2f%% meanJ %.5f -> %.5f" % (
        len(gs), sum(1 for g in gs if g > 1e-6), sum(gs) / len(gs), max(gs),
        sum(o["ours"] for o in res) / len(res), sum(o["new"] for o in res) / len(res)))


if __name__ == "__main__":
    main()
