"""r3_score_hunt.py - SCORE judge (round 3): hunt for sets where the v1.5 PLC default (order 1 + fallback,
IMPROVE 3000, SLOT 10, relaxed rule R2-J1) is clearly beatable.

Judge optimiser = r2_score_opt.Prob2 (exact per-bay Hungarian cell assignment for a fixed sequence +
side vectors + joint annealing over (sequence, sides)), extended here with
  * the relaxed balance rule (World.BalCeil, used only when OUR plan used it, so the comparison is fair),
    including the "must end balanced" terminal condition,
  * long annealing seeded with our own plan (several seeds + a cool restart),
  * exact enumeration of every interleaving when C(n, nu) is small.
Every judge plan is re-executed with crane_plan.simulate under OUR plan's config (order, ceil) and the
per-list order is asserted.

Families (--family): big (N 45..90, free cells), imb (unbalanced start, relaxed rule), scatter (list
entries alternate far rows/columns), corner, farload, nearfull, uneq, file (existing json globs).

  python tools/judge_sets/r3_score_hunt.py --family big --seed 1 --count 12 --iters 30000 [--save]
  python tools/judge_sets/r3_score_hunt.py --family file tools/judge_sets/r3_score_*.json
"""
import argparse
import glob
import json
import math
import os
import random
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402
import crane_gen as cg    # noqa: E402
import r2_score_opt as o2  # noqa: E402

BIG = o2.BIG
_ORIG_STEP = cm.step_ok
CEIL = 0


def _step(a, b, a2, b2, lim=cm.BAL_LIMIT, ceil=0):
    return _ORIG_STEP(a, b, a2, b2, lim, ceil or CEIL)


class Prob3(o2.Prob2):
    def balance_ok(self, seq, dests):
        L, R = cm.lr(self.g0[0])
        for k, i in enumerate(seq):
            s = self.src[i]
            if s.pos[2] == 0:
                L2, R2 = (L - 1, R) if s.pos[0] <= 1 else (L, R - 1)
            else:
                d = dests[k]
                L2, R2 = (L + 1, R) if d[0] <= 1 else (L, R + 1)
            if not cm.step_ok(L, R, L2, R2, self.lim):
                return False
            L, R = L2, R2
        if CEIL and abs(L - R) > self.lim:
            return False
        return True


# ------------------------------------------------------------------ generators
def blank():
    return [[0] * 12 for _ in range(4)]


def ds(name, b0, b1, U, Lo, note):
    return cg.ds_dict(name, b0, b1, U, Lo, note)


def gen(family, rng, name):
    ids = rng.sample(range(100, 1000), 96)
    it = iter(ids)
    b0, b1 = blank(), blank()
    cells = [(x, y) for x in range(4) for y in range(12)]
    if family == "big":
        for _ in range(1000):
            s, y = rng.randint(24, 46), rng.randint(20, 46)
            u, l = rng.randint(18, min(44, s)), rng.randint(18, min(44, y))
            if s - u + l <= 48 and y - l + u <= 48 and u + l >= 45:
                break
        d = cg.random_set(rng, name, ship=s, yard=y, nu=u, nl=l)
        d["note"] = "r3 big: " + d["note"]
        return d
    if family == "imb":
        # ship starts with |L-R| = d0 in 6..14, heavy side unloads + light-side loads
        d0 = rng.randint(6, 14)
        s = rng.randint(14 + d0 // 2, 40)
        Lc = (s + d0) // 2
        Rc = s - Lc
        if Lc > 24:
            Lc, Rc = 24, s - 24
        if rng.random() < 0.5:
            Lc, Rc = Rc, Lc
        lcells = rng.sample([(x, y) for x in (0, 1) for y in range(12)], Lc)
        rcells = rng.sample([(x, y) for x in (2, 3) for y in range(12)], Rc)
        for (x, y) in lcells + rcells:
            b0[x][y] = next(it)
        yd = rng.randint(10, 40)
        for (x, y) in rng.sample(cells, yd):
            b1[x][y] = next(it)
        ship_ids = [b0[x][y] for x in range(4) for y in range(12) if b0[x][y]]
        yard_ids = [b1[x][y] for x in range(4) for y in range(12) if b1[x][y]]
        for _ in range(100):
            u = rng.randint(2, min(20, s))
            l = rng.randint(2, min(20, yd))
            if s - u + l <= 48 and yd - l + u <= 48:
                break
        U = rng.sample(ship_ids, u)
        Lo = rng.sample(yard_ids, l)
        # light side first in the unload list: the strict step rule cannot follow it -> relaxed rule (ceil=d0)
        light = (0, 1) if Lc < Rc else (2, 3)
        side = {b0[x][y]: (x in light) for x in range(4) for y in range(12) if b0[x][y]}
        U.sort(key=lambda i: 0 if side[i] else 1)
        return ds(name, b0, b1, U, Lo, "r3 imb: d0=%d L=%d R=%d u=%d l=%d light-side unloads first" % (abs(Lc - Rc), Lc, Rc, u, l))
    if family == "scatter":
        # lists alternate between far-apart rows/columns: row 0 <-> row 11, x 0 <-> x 3
        s = rng.randint(28, 40)
        yd = rng.randint(24, 40)
        b0 = cg.fill_ship(rng, s, ids[:48])
        for (x, y) in rng.sample(cells, yd):
            b1[x][y] = ids[48 + len([1 for xx in range(4) for yy in range(12) if b1[xx][yy]])]
        def far_order(g, n):
            occ = [(x, y) for x in range(4) for y in range(12) if g[x][y]]
            a = sorted(occ, key=lambda c: (c[1], c[0]))
            lo, hi = 0, len(a) - 1
            out = []
            while lo <= hi and len(out) < n:
                out.append(a[lo]); lo += 1
                if lo <= hi and len(out) < n:
                    out.append(a[hi]); hi -= 1
            return [g[x][y] for (x, y) in out]
        for _ in range(100):
            u = rng.randint(8, min(24, s))
            l = rng.randint(8, min(24, yd))
            if s - u + l <= 48 and yd - l + u <= 48:
                break
        U = far_order(b0, 2 * u)[:]
        rng.shuffle(U)
        U = far_order(b0, u)
        Lo = far_order(b1, l)
        return ds(name, b0, b1, U, Lo, "r3 scatter: ship=%d yard=%d u=%d l=%d (row 0/11 alternating)" % (s, yd, u, l))
    if family == "corner":
        # everything in one corner: ship unloads at x3 rows 9..11, yard loads at x0 rows 0..2, free cells far away
        s = rng.randint(30, 44)
        b0 = cg.fill_ship(rng, s, ids[:48])
        yd = rng.randint(20, 40)
        for k, (x, y) in enumerate(rng.sample(cells, yd)):
            b1[x][y] = ids[48 + k]
        cu = [b0[x][y] for x in (2, 3) for y in range(12) if b0[x][y]]
        cu.sort(key=lambda i: -[(x, y) for x in range(4) for y in range(12) if b0[x][y] == i][0][1])
        cl = [b1[x][y] for x in (0, 1) for y in range(12) if b1[x][y]]
        cl.sort(key=lambda i: [(x, y) for x in range(4) for y in range(12) if b1[x][y] == i][0][1])
        u = min(len(cu), rng.randint(4, 12))
        l = min(len(cl), rng.randint(4, 14))
        return ds(name, b0, b1, cu[:u], cl[:l], "r3 corner: right-aft unloads, yard-left-fore loads")
    if family == "nearfull":
        s = rng.randint(44, 47)
        yd = rng.randint(40, 46)
        for _ in range(100):
            u = rng.randint(6, 30)
            l = rng.randint(6, 30)
            if s - u + l <= 48 and yd - l + u <= 48:
                break
        d = cg.random_set(rng, name, ship=s, yard=yd, nu=u, nl=l)
        d["note"] = "r3 nearfull: " + d["note"]
        return d
    if family == "uneq":
        if rng.random() < 0.5:
            d = cg.random_set(rng, name, ship=rng.randint(34, 46), yard=rng.randint(6, 14), nu=rng.randint(25, 34), nl=rng.randint(1, 3))
        else:
            d = cg.random_set(rng, name, ship=rng.randint(6, 16), yard=rng.randint(34, 46), nu=rng.randint(1, 3), nl=rng.randint(25, 34))
        d["note"] = "r3 uneq: " + d["note"]
        return d
    raise ValueError(family)


# ------------------------------------------------------------------ solve
A = None


def solve(path):
    global CEIL
    d = cm.load_dataset(path)
    st = cp.build_state(d)
    cfg = {"mmode": 2, "order": A.order, "balmode": 0, "lim": 5}
    t0 = time.time()
    CEIL = 0
    cm.step_ok = _ORIG_STEP
    r = cp.plan_fb(st, cfg, [0, 100, 200, 300], imp_evals=A.evals)
    t_ours = time.time() - t0
    out = {"name": d["name"], "N": st["N"], "err": r["err"], "file": path}
    if r["err"] != 0 or not r["plan"]:
        return out
    rc = r["cfg"]
    out.update(ours=r["J"], order=r["order"], ceil=rc.get("ceil", 0), oursT=r["T"], oursM=r["M"], t_ours=t_ours)
    lbT, lbM, lbJ = cp.lower_bound(st)
    out["lb"] = lbJ
    CEIL = rc.get("ceil", 0)
    cm.step_ok = _step
    try:
        pr = Prob3(d, 2, 5, r["order"])
        cands = []
        ex = None
        if r["order"] == 1 and math.comb(pr.n, pr.nu) <= A.exact_limit:
            ex = pr.exact(A.exact_limit)
        elif r["order"] == 0 and math.factorial(pr.n) <= A.exact_limit:
            ex = pr.exact(A.exact_limit)
        if ex is not None and ex[1] is not None:
            cands.append(ex)
            out["exact"] = True
        else:
            out["exact"] = False
            key = {(s.kind, s.idx): k for k, s in enumerate(pr.src)}
            seq0 = [key[(t["kind"], t["list_idx"])] for t in r["plan"]]
            sides0 = {key[(t["kind"], t["list_idx"])]: (0 if t["dst"][0] <= 1 else 1) for t in r["plan"] if t["kind"] == 2}
            for sd in range(1, A.seeds + 1):
                cands.append(pr.anneal2(seq0, sides0, A.iters, seed=sd))
            b = min(cands, key=lambda c: c[0])
            cands.append(pr.anneal2(b[1], b[3], A.iters, T0=120.0, seed=99))
        cands = [c for c in cands if c[1] is not None and c[0] < BIG]
        if not cands:
            return out
        best = min(cands, key=lambda c: c[0])
        plan, T, M = pr.to_plan(best[1], best[2])
        cm.step_ok = _ORIG_STEP
        cp.simulate(st, plan, rc)
        if r["order"] == 1:
            u = [p["list_idx"] for p in plan if p["kind"] == 1]
            l = [p["list_idx"] for p in plan if p["kind"] == 2]
            assert u == sorted(u) and l == sorted(l), "order 1 violated"
        J = cm.J(T, M, st["N"])
        out.update(judge=J, judgeT=T, judgeM=M, gap=100.0 * (r["J"] / J - 1))
        if A.save and out["gap"] > 1.0:
            fn = os.path.join(HERE, "r3_score_plan_%s_o%d_m2.csv" % (d["name"], r["order"]))
            res = {"err": 0, "plan": plan, "variant": 0, "T": T, "M": M, "J": J, "N": st["N"]}
            with open(fn, "w") as fh:
                fh.write("\n".join(cp.csv_lines(res)) + "\n")
            out["saved"] = fn
    finally:
        cm.step_ok = _ORIG_STEP
        CEIL = 0
    out["secs"] = time.time() - t0
    return out


def init(a):
    global A
    A = a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--family", default="file")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--order", type=int, default=1)
    ap.add_argument("--evals", type=int, default=3000)
    ap.add_argument("--iters", type=int, default=30000)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--exact-limit", type=int, default=3000)
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    files = []
    if a.family == "file":
        for g in a.files:
            files += sorted(glob.glob(g))
    else:
        rng = random.Random(a.seed)
        for i in range(a.count):
            nm = "r3_score_%s_%d_%02d" % (a.family, a.seed, i)
            d = gen(a.family, rng, nm)
            fn = os.path.join(HERE, nm + ".json")
            with open(fn, "w") as fh:
                json.dump(d, fh)
            files.append(fn)
    with Pool(a.workers, initializer=init, initargs=(a,)) as p:
        res = p.map(solve, files, chunksize=1)
    gaps = []
    for r in res:
        if r.get("judge") is None:
            print("%-30s N=%3d err=%s ours=%s (no judge plan)" % (r["name"], r["N"], r["err"], r.get("ours")))
            continue
        gaps.append(r["gap"])
        print("%-30s N=%3d ord=%d ceil=%2d ours=%.4f (T=%d M=%d) judge=%.4f (T=%d M=%d) %s gap=%+.2f%% LB=%.4f t_ours=%.0fs%s" % (
            r["name"], r["N"], r["order"], r["ceil"], r["ours"], r["oursT"], r["oursM"], r["judge"], r["judgeT"],
            r["judgeM"], "EX" if r["exact"] else "SA", r["gap"], r["lb"], r["t_ours"], "  <<< >1%" if r["gap"] > 1 else ""))
    if gaps:
        gs = sorted(gaps)
        print("R3_HUNT sets=%d mean_gap=%+.3f%% median=%+.2f%% max=%+.2f%% n>1%%=%d n>2%%=%d" % (
            len(gs), sum(gs) / len(gs), gs[len(gs) // 2], gs[-1], sum(1 for g in gs if g > 1), sum(1 for g in gs if g > 2)))


if __name__ == "__main__":
    main()
