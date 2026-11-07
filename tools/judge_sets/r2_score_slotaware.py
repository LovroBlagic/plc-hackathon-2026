"""r2_score_slotaware.py - SCORE judge (round 2): root cause + prototype for the remaining order-1 gap.

Root cause shown on r2_score_hunt_11_062 (N=15, ship 43/48 full, 9 loads):
  our incumbent K = 24226; candidate "swap transfers 1,2" (mv2, valid in order 1) replays to K = 24410
  with IMPROVE's myopic per-step slot rule -> rejected; but the SAME sequence with optimal drop cells
  costs K = 23801 (-1.75 %), and it is the exact optimum of the whole set.  IMPROVE judges candidates
  by greedy cells, SLOT re-optimises cells only for the final order, so good orders get rejected when
  free cells are scarce (cell conflicts).

Prototype: IMPROVE whose acceptance is "replay (abort bound relaxed to +margin) + SLOT(sweeps)" vs the
slotted incumbent, with the team's own imp_replay / slot_search, optional mv4 (pattern-token relocate,
see r2_score_patmove.py).  Budget counted in replays.  Every plan re-checked with crane_plan.simulate.

  python tools/judge_sets/r2_score_slotaware.py [--mv4] [--margin 300] [--sweeps 3] <glob> ...
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


def plan_from(ctx, cand, steps, k0):
    plan = []
    for k in range(1, ctx.n + 1):
        s = ctx.src[cand[k]]
        if k < k0:
            d, T, M = ctx.CurDst[k], ctx.CurT[k], ctx.CurM[k]
        else:
            d, T, M = steps[k]
        plan.append({"kind": s.kind, "id": s.id, "list_idx": s.idx, "src": s.pos, "dst": d, "cum_t": T, "cum_m": M})
    return plan


def improve_sa(state, cfg, res, budget, margin, sweeps, mv4):
    res = cp.slot_search(state, cfg, res, sweeps)
    ctx = cp.ImpCtx(state, cfg, res)
    n = ctx.n
    if n < 2 or ctx.order == 2:
        return res, 0
    Kinc = ctx.CurK

    def pat_cand(i, j):
        seq = ctx.CurSeq
        kinds = [ctx.kind(seq[q]) for q in range(1, n + 1)]
        orig = list(kinds)
        t = kinds.pop(i - 1)
        kinds.insert(j - 1, t)
        if kinds == orig:
            return None, 0
        us = [seq[q] for q in range(1, n + 1) if ctx.kind(seq[q]) == 1]
        ls = [seq[q] for q in range(1, n + 1) if ctx.kind(seq[q]) == 2]
        iu = il = 0
        c = [0]
        for k in kinds:
            if k == 1:
                c.append(us[iu]); iu += 1
            else:
                c.append(ls[il]); il += 1
        p = next(q for q in range(1, n + 1) if c[q] != seq[q])
        return c, p

    moves = (1, 2, 3, 4) if (mv4 and ctx.order == 1) else (1, 2, 3)
    while True:
        improved = False
        for mv in moves:
            imax = n - 1 if mv == 3 else n
            for i in range(1, imax + 1):
                for j in range(1, imax + 1):
                    if ctx.evals >= budget:
                        break
                    if j == i or (mv == 2 and j < i):
                        continue
                    if mv == 4:
                        cand, p = pat_cand(i, j)
                        if cand is None:
                            continue
                    else:
                        if not cp.imp_valid(ctx, mv, i, j):
                            continue
                        cand, p = cp.imp_build(ctx, mv, i, j)
                    ctx.CurK = Kinc + margin
                    K, steps = cp.imp_replay(ctx, cand, p)
                    ctx.CurK = Kinc
                    ctx.evals += 1
                    if steps is None:
                        continue
                    k0 = max(1, p - 1)
                    pl = plan_from(ctx, cand, steps, k0)
                    rr = {"err": 0, "plan": pl, "T": pl[-1]["cum_t"], "M": pl[-1]["cum_m"], "N": res["N"],
                          "J": cm.J(pl[-1]["cum_t"], pl[-1]["cum_m"], res["N"])}
                    if K >= Kinc:
                        rr = cp.slot_search(state, cfg, rr, sweeps)
                    Ks = (rr["T"] - ctx.baseT) + cp.M_W * (rr["M"] - ctx.baseM)
                    if Ks < Kinc:
                        improved = True
                        ctx.CurSeq = cand
                        for k, tr in enumerate(rr["plan"], 1):
                            ctx.CurDst[k], ctx.CurT[k], ctx.CurM[k] = tuple(tr["dst"]), tr["cum_t"], tr["cum_m"]
                        Kinc = Ks
                        ctx.CurK = Kinc
        if not improved or ctx.evals >= budget:
            break
    plan = []
    for k in range(1, n + 1):
        s = ctx.src[ctx.CurSeq[k]]
        plan.append({"kind": s.kind, "id": s.id, "list_idx": s.idx, "src": s.pos, "dst": ctx.CurDst[k],
                     "cum_t": ctx.CurT[k], "cum_m": ctx.CurM[k]})
    out = dict(res)
    out.update(plan=plan, T=ctx.CurT[n], M=ctx.CurM[n], J=cm.J(ctx.CurT[n], ctx.CurM[n], res["N"]))
    out = cp.slot_search(state, cfg, out, cp.SLOT_SWEEPS)
    return out, ctx.evals


def one(f):
    ds = cm.load_dataset(f)
    st = cp.build_state(ds)
    cfg = {"mmode": 2, "order": A.order, "balmode": 0, "lim": 5}
    r = cp.plan_fb(st, cfg, [0, 100, 200, 300], imp_evals=3000)
    if r["err"] != 0 or r["order"] != A.order or len(r["plan"]) < 2:
        return None
    g = cp.plan(st, r["cfg"], [0, 100, 200, 300])
    res, ev = improve_sa(st, r["cfg"], g, A.budget, A.margin, A.sweeps, A.mv4)
    cp.simulate(st, res["plan"], r["cfg"])
    if A.order == 1:
        u = [t["list_idx"] for t in res["plan"] if t["kind"] == 1]
        l = [t["list_idx"] for t in res["plan"] if t["kind"] == 2]
        assert u == sorted(u) and l == sorted(l)
    return {"name": ds["name"], "N": st["N"], "ours": r["J"], "new": res["J"], "evals": ev}


def init(a):
    global A
    A = a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("globs", nargs="+")
    ap.add_argument("--order", type=int, default=1)
    ap.add_argument("--budget", type=int, default=3000)
    ap.add_argument("--margin", type=int, default=300)
    ap.add_argument("--sweeps", type=int, default=3)
    ap.add_argument("--mv4", action="store_true")
    a = ap.parse_args()
    files = []
    for g in a.globs:
        files += sorted(glob.glob(g))
    with Pool(4, initializer=init, initargs=(a,)) as p:
        res = p.map(one, files, chunksize=1)
    gs = []
    for o in res:
        if not o:
            continue
        g = 100 * (o["ours"] / o["new"] - 1)
        gs.append((g, o))
        print("%-34s N=%3d ours=%.4f new=%.4f gain=%+.2f%% evals=%d" % (o["name"], o["N"], o["ours"], o["new"], g, o["evals"]))
    print("sets %d, better %d, worse %d, mean gain %+.3f%%, max %+.2f%%, min %+.2f%%, mean J %.5f -> %.5f" % (
        len(gs), sum(1 for g, _ in gs if g > 0.001), sum(1 for g, _ in gs if g < -0.001),
        sum(g for g, _ in gs) / len(gs), max(g for g, _ in gs), min(g for g, _ in gs),
        sum(o["ours"] for _, o in gs) / len(gs), sum(o["new"] for _, o in gs) / len(gs)))


if __name__ == "__main__":
    main()
