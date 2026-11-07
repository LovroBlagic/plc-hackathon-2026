"""r2_score_patmove.py - SCORE judge (round 2): IMPROVE with one extra move type for order mode 1.

In order mode 1 a sequence is fully determined by its KIND PATTERN (U/L per position): the k-th U is
always unload k, the k-th L load k.  FB11's IMPROVE moves (mv1 relocate, mv2 adjacent swap, mv3 pair
relocate) are only valid when the moved element passes no element of its own list, so they can only
move a pattern token inside a run of the OTHER kind.  They can never turn "... L4 L5 ... U12 U13 U14 U15"
into "... L4 U5 L5 ... L13 U15" (needs every load after L4 to shift one slot = a block shift).

mv 4 (proposed): relocate one pattern TOKEN from position i to j and re-derive the element sequence.
Validity is automatic (list order preserved).  Each candidate is evaluated with the team's own
crane_plan.imp_replay (same slot rule, same exact side feasibility, same abort bound), then the
team's SLOT phase runs unchanged.  Same budget as the PLC (3000 evals).  Every plan is re-checked
with crane_plan.simulate.

  python tools/judge_sets/r2_score_patmove.py <glob> ...
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


def improve_pat(state, cfg, res, budget):
    ctx = cp.ImpCtx(state, cfg, res)
    n = ctx.n
    if n < 2 or ctx.order != 1:
        return res, 0

    def pat_cand(i, j):
        seq = ctx.CurSeq
        kinds = [ctx.kind(seq[q]) for q in range(1, n + 1)]
        t = kinds.pop(i - 1)
        kinds.insert(j - 1, t)
        if kinds == [ctx.kind(seq[q]) for q in range(1, n + 1)]:
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

    while True:
        improved = False
        for mv in (1, 2, 3, 4):
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
                    K, steps = cp.imp_replay(ctx, cand, p)
                    ctx.evals += 1
                    if K < ctx.CurK:
                        improved = True
                        for k, (d, T, M) in steps.items():
                            ctx.CurDst[k], ctx.CurT[k], ctx.CurM[k] = d, T, M
                        ctx.CurSeq, ctx.CurK = cand, K
        if not improved or ctx.evals >= budget:
            break
    plan = []
    for k in range(1, n + 1):
        s = ctx.src[ctx.CurSeq[k]]
        plan.append({"kind": s.kind, "id": s.id, "list_idx": s.idx, "src": s.pos, "dst": ctx.CurDst[k],
                     "cum_t": ctx.CurT[k], "cum_m": ctx.CurM[k]})
    out = dict(res)
    out.update(plan=plan, T=ctx.CurT[n], M=ctx.CurM[n], J=cm.J(ctx.CurT[n], ctx.CurM[n], res["N"]))
    return out, ctx.evals


def one(f):
    ds = cm.load_dataset(f)
    st = cp.build_state(ds)
    cfg = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}
    r = cp.plan_fb(st, cfg, [0, 100, 200, 300], imp_evals=3000)
    if r["err"] != 0 or r["order"] != 1 or len(r["plan"]) < 2:
        return None
    g = cp.plan(st, r["cfg"], [0, 100, 200, 300])          # greedy winner (start of IMPROVE)
    res, ev = improve_pat(st, r["cfg"], g, 3000)
    res = cp.slot_search(st, r["cfg"], res, cp.SLOT_SWEEPS)
    cp.simulate(st, res["plan"], r["cfg"])
    u = [t["list_idx"] for t in res["plan"] if t["kind"] == 1]
    l = [t["list_idx"] for t in res["plan"] if t["kind"] == 2]
    assert u == sorted(u) and l == sorted(l)
    return {"name": ds["name"], "N": st["N"], "ours": r["J"], "pat": res["J"], "evals": ev}


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
        g = 100 * (o["ours"] / o["pat"] - 1)
        gs.append((g, o))
        print("%-34s N=%3d ours=%.4f +mv4=%.4f gain=%+.2f%% evals=%d" % (o["name"], o["N"], o["ours"], o["pat"], g, o["evals"]))
    if gs:
        print("sets %d, better %d, worse %d, mean gain %+.3f%%, max %+.2f%%, min %+.2f%%, mean J %.5f -> %.5f" % (
            len(gs), sum(1 for g, _ in gs if g > 0.001), sum(1 for g, _ in gs if g < -0.001),
            sum(g for g, _ in gs) / len(gs), max(g for g, _ in gs), min(g for g, _ in gs),
            sum(o["ours"] for _, o in gs) / len(gs), sum(o["pat"] for _, o in gs) / len(gs)))


if __name__ == "__main__":
    main()
