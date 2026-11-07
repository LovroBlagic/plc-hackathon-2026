"""r1_score_opt.py - SCORE judge (round 1): independent stronger optimizer for the crane task.

For a FIXED transfer order the cost is separable per transfer:
   c_k(d) = W(s_k -> d) + W(d -> s_{k+1})      (W = T_ds + 190*M, last transfer: no 2nd term)
so the optimal destination cells (distinct, free at that time) are a min-cost assignment
(Hungarian, scipy) per bay.  Ship balance (step rule) is enforced by a per-load side vector
(L/R) which is repaired greedily / searched.  Order search: exhaustive for small P, simulated
annealing otherwise.  Every result is re-executed through crane_plan.simulate (FB1 emulator +
CheckCmd + balance asserts), so the reported J is achievable under the same rules.

  python tools/judge_sets/r1_score_opt.py <set.json> [--order 1|0] [--mmode 2] [--iters 20000]
"""
import argparse
import itertools
import math
import os
import random
import sys

import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402

BIG = 10 ** 9
CELLS = [(x, y) for x in range(4) for y in range(12)]


def W(p0, p1, mm):
    t, m = cm.move_cost(p0[0], p0[1], p0[2], p1[0], p1[1], p1[2], mm)
    return t + 190 * m


class Prob:
    def __init__(self, ds, mmode=2, lim=5, order=1):
        self.st = cp.build_state(ds, lim)
        g = [ds["bay0"], ds["bay1"]]
        PU, PL = cp.locate(g, self.st["PU"], self.st["PL"])
        self.src = PU + PL
        self.nu, self.nl = len(PU), len(PL)
        self.n = len(self.src)
        self.mm, self.lim, self.order = mmode, lim, order
        self.g0 = g
        self.crane = tuple(self.st["crane"])
        # pre-computed W tables
        self.Wsc = {}
        for i, s in enumerate(self.src):
            db = 1 - s.pos[2]
            self.Wsc[i] = np.array([W(s.pos, (x, y, db), mmode) for (x, y) in CELLS], dtype=np.int64)
        self.Wcs = {}  # cell(bay) -> source j
        for j, s in enumerate(self.src):
            b = 1 - s.pos[2]  # predecessor puts into bay of s?  no: arrives at s from any bay
            for bb in (0, 1):
                self.Wcs[(bb, j)] = np.array([W((x, y, bb), s.pos, mmode) for (x, y) in CELLS], dtype=np.int64)
        self.init_free = [np.array([g[b][x][y] == 0 for (x, y) in CELLS]) for b in (0, 1)]
        self.cellidx = {}
        for i, s in enumerate(self.src):
            self.cellidx[i] = s.pos[0] * 12 + s.pos[1]

    # ------------------------------------------------------------ evaluation
    def evaluate(self, seq, sides=None, want_plan=False):
        """seq: list of source indices. sides: dict load-pos-index -> 0 (L) / 1 (R) or None.
        Returns (K, dests) or (BIG, None)."""
        n = len(seq)
        mm = self.mm
        # availability: step at which each cell becomes free (0 = initially)
        avail = [np.where(self.init_free[b], 0, BIG) for b in (0, 1)]
        avail = [a.copy() for a in avail]
        for k, i in enumerate(seq):
            s = self.src[i]
            avail[s.pos[2]][self.cellidx[i]] = k + 1
        K = 0
        # first empty move
        s0 = self.src[seq[0]]
        if self.crane != s0.pos:
            K += W(self.crane, s0.pos, mm)
        K += n * (400 + 2 * 190)
        dests = [None] * n
        for b in (0, 1):
            rows = [k for k in range(n) if 1 - self.src[seq[k]].pos[2] == b]
            if not rows:
                continue
            C = np.empty((len(rows), 48), dtype=np.int64)
            for r, k in enumerate(rows):
                c = self.Wsc[seq[k]].copy()
                if k + 1 < n:
                    c = c + self.Wcs[(b, seq[k + 1])]
                c = np.where(avail[b] <= k, c, BIG)
                if b == 0 and sides is not None and seq[k] in sides:
                    side = sides[seq[k]]
                    mask = np.array([(x <= 1) == (side == 0) for (x, y) in CELLS])
                    c = np.where(mask, c, BIG)
                C[r] = c
            ri, ci = linear_sum_assignment(C)
            tot = C[ri, ci].sum()
            if tot >= BIG:
                return BIG, None
            K += int(tot)
            for r, c in zip(ri, ci):
                dests[rows[r]] = (CELLS[c][0], CELLS[c][1], b)
        if not self.balance_ok(seq, dests):
            return BIG, dests
        return K, dests

    def balance_ok(self, seq, dests):
        L, R = cm.lr(self.g0[0])
        if abs(L - R) > self.lim:
            init_bad = True
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
        return True

    def repair_sides(self, seq, dests):
        """Greedy side vector (keyed by load source index): keep the preferred side when
        step-ok + side capacity + reachability, else flip."""
        L, R = cm.lr(self.g0[0])
        freeL = sum(1 for x in (0, 1) for y in range(12) if self.g0[0][x][y] == 0)
        freeR = sum(1 for x in (2, 3) for y in range(12) if self.g0[0][x][y] == 0)
        uL = sum(1 for i in seq if self.src[i].kind == 1 and self.src[i].pos[0] <= 1)
        uR = sum(1 for i in seq if self.src[i].kind == 1 and self.src[i].pos[0] >= 2)
        nl = sum(1 for i in seq if self.src[i].kind == 2)
        sides = {}
        for k, i in enumerate(seq):
            s = self.src[i]
            if s.kind == 1:
                if s.pos[0] <= 1:
                    L -= 1; freeL += 1; uL -= 1
                else:
                    R -= 1; freeR += 1; uR -= 1
                continue
            nl -= 1
            want = 0 if (dests is not None and dests[k] is not None and dests[k][0] <= 1) else 1
            chosen = None
            for pas in (0, 1):
                for side in (want, 1 - want):
                    if (freeL if side == 0 else freeR) <= 0:
                        continue
                    L2, R2 = (L + 1, R) if side == 0 else (L, R + 1)
                    if not cm.step_ok(L, R, L2, R2, self.lim):
                        continue
                    if pas == 0 and not cm.reachable(L2, R2, uL, uR, nl, self.lim):
                        continue
                    chosen = side
                    break
                if chosen is not None:
                    break
            if chosen is None:
                chosen = want
            sides[i] = chosen
            if chosen == 0:
                L += 1; freeL -= 1
            else:
                R += 1; freeR -= 1
        return sides

    def eval_full(self, seq, hint=None):
        K, d = self.evaluate(seq)
        if K < BIG:
            return K, d, None
        best = (BIG, None, None)
        if hint is not None:
            K2, d2 = self.evaluate(seq, hint)
            if K2 < BIG:
                best = (K2, d2, hint)
        sides = self.repair_sides(seq, d)
        for _ in range(4):
            K2, d2 = self.evaluate(seq, sides)
            if K2 < best[0]:
                best = (K2, d2, sides)
                break
            sides2 = self.repair_sides(seq, d2)
            if sides2 == sides:
                break
            sides = sides2
        return best

    # ------------------------------------------------------------ plan / check
    def to_plan(self, seq, dests):
        plan = []
        T = self.st["base_t"]
        M = self.st["base_m"]
        pos = self.crane
        for k, i in enumerate(seq):
            s = self.src[i]
            if pos != s.pos:
                t, m = cm.move_cost(pos[0], pos[1], pos[2], s.pos[0], s.pos[1], s.pos[2], self.mm)
                T += t
                M += m
            t, m = cm.move_cost(s.pos[0], s.pos[1], s.pos[2], dests[k][0], dests[k][1], dests[k][2], self.mm)
            T += 400 + t
            M += 2 + m
            plan.append({"kind": s.kind, "id": s.id, "list_idx": s.idx, "src": s.pos, "dst": dests[k],
                         "cum_t": T, "cum_m": M})
            pos = dests[k]
        return plan, T, M

    def check(self, seq, dests):
        plan, T, M = self.to_plan(seq, dests)
        cfg = {"mmode": self.mm, "order": self.order, "balmode": 0, "lim": self.lim}
        cp.simulate(self.st, plan, cfg)
        if self.order == 1:
            u = [p["list_idx"] for p in plan if p["kind"] == 1]
            l = [p["list_idx"] for p in plan if p["kind"] == 2]
            assert u == sorted(u) and l == sorted(l), "order 1 violated"
        return plan, T, M, cm.J(T, M, self.st["N"])

    # ------------------------------------------------------------ search
    def seq_from_pattern(self, pat):
        u = iter(range(self.nu))
        l = iter(range(self.nu, self.n))
        return [next(u) if c == 0 else next(l) for c in pat]

    def exhaustive(self, limit=200000):
        best = (BIG, None, None)
        if self.order == 1:
            cnt = math.comb(self.n, self.nu)
            if cnt > limit:
                return None
            for pos in itertools.combinations(range(self.n), self.nu):
                pat = [1] * self.n
                for p in pos:
                    pat[p] = 0
                seq = self.seq_from_pattern(pat)
                K, d, _ = self.eval_full(seq)
                if K < best[0]:
                    best = (K, seq, d)
        else:
            if math.factorial(self.n) > limit:
                return None
            for seq in itertools.permutations(range(self.n)):
                K, d, _ = self.eval_full(list(seq))
                if K < best[0]:
                    best = (K, list(seq), d)
        return best

    def valid_seq(self, seq):
        if self.order != 1:
            return True
        u = [i for i in seq if i < self.nu]
        l = [i for i in seq if i >= self.nu]
        return u == sorted(u) and l == sorted(l)

    def anneal(self, seq0, iters=20000, T0=300.0, seed=1, sides0=None):
        rng = random.Random(seed)
        cur = list(seq0)
        Kc, dc, sc = self.eval_full(cur, sides0)
        if sc is None:
            sc = sides0
        best = (Kc, list(cur), dc)
        n = self.n
        if n < 2:
            return best
        for it in range(iters):
            temp = T0 * (1 - it / iters) + 1e-3
            c = list(cur)
            mv = rng.random()
            hint = sc
            if sc is not None and rng.random() < 0.2:
                hint = dict(sc)
                kk = rng.choice(list(hint))
                hint[kk] = 1 - hint[kk]
            if self.order == 1:
                # move one element of a list past elements of the other list only
                i = rng.randrange(n)
                if mv < 0.5:
                    j = i + rng.choice((-1, 1))
                    if not (0 <= j < n) or (c[i] < self.nu) == (c[j] < self.nu):
                        continue
                    c[i], c[j] = c[j], c[i]
                else:
                    j = rng.randrange(n)
                    e = c.pop(i)
                    c.insert(j, e)
                    if not self.valid_seq(c):
                        continue
            else:
                i, j = rng.randrange(n), rng.randrange(n)
                if i == j:
                    continue
                if mv < 0.4:
                    c[i], c[j] = c[j], c[i]
                elif mv < 0.8:
                    e = c.pop(i)
                    c.insert(j, e)
                else:
                    a, b = min(i, j), max(i, j)
                    c[a:b + 1] = c[a:b + 1][::-1]
            K, d, sd = self.eval_full(c, hint)
            if K >= BIG:
                continue
            if K <= Kc or rng.random() < math.exp(-(K - Kc) / temp):
                cur, Kc = c, K
                if sd is not None:
                    sc = sd
                if K < best[0]:
                    best = (K, list(c), d)
        return best


def ours(ds, order=1, mmode=2, evals=3000):
    st = cp.build_state(ds)
    cfg = {"mmode": mmode, "order": order, "balmode": 0, "lim": 5}
    r = cp.plan_fb(st, cfg, [0, 100, 200, 300], imp_evals=evals)
    return r, st


def solve(ds, order=1, mmode=2, iters=20000, seeds=(1, 2), verbose=True):
    r, st = ours(ds, order, mmode)
    pr = Prob(ds, mmode, 5, order)
    lbT, lbM, lbJ = cp.lower_bound(st)
    out = {"name": ds.get("name"), "N": st["N"], "P": pr.n, "ours_J": r.get("J"), "ours_order": r.get("order"),
           "lb": lbJ}
    if r["err"] != 0 or pr.n == 0:
        out["judge_J"] = None
        return out
    used_order = r["order"]
    pr.order = used_order
    cands = []
    ex = pr.exhaustive()
    if ex is not None and ex[1] is not None:
        cands.append(ex)
        out["exact"] = True
    else:
        out["exact"] = False
        # seed with our planner's sequence
        key = {(s.kind, s.idx): k for k, s in enumerate(pr.src)}
        seq_ours = [key[(t["kind"], t["list_idx"])] for t in r["plan"]]
        sides0 = {key[(t["kind"], t["list_idx"])]: (0 if t["dst"][0] <= 1 else 1) for t in r["plan"] if t["kind"] == 2}
        for sd in seeds:
            cands.append(pr.anneal(seq_ours, iters, seed=sd, sides0=sides0))
    cands = [c for c in cands if c[1] is not None]
    if not cands:
        out["judge_J"] = None
        return out
    best = min(cands, key=lambda c: c[0])
    plan, T, M, J = pr.check(best[1], best[2])
    out.update(judge_J=J, judge_T=T, judge_M=M, ours_T=r["T"], ours_M=r["M"], judge_plan=plan,
               gain_pct=100.0 * (r["J"] / J - 1))
    if verbose:
        print("%s N=%d P=%d order=%d ours J=%.4f (T=%d M=%d)  judge J=%.4f (T=%d M=%d)  %s  ours/judge-1=%.2f%%  LB=%.4f" % (
            out["name"], out["N"], pr.n, used_order, r["J"], r["T"], r["M"], J, T, M,
            "EXACT" if out["exact"] else "SA", out["gain_pct"], lbJ))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--order", type=int, default=1)
    ap.add_argument("--mmode", type=int, default=2)
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--save", action="store_true", help="write r1_score_plan_<set>_o<order>_m<mmode>.csv next to this script")
    a = ap.parse_args()
    for f in a.files:
        ds = cm.load_dataset(f)
        o = solve(ds, a.order, a.mmode, a.iters)
        if a.save and o.get("judge_plan"):
            nm = os.path.basename(f)[:-5]
            fn = os.path.join(HERE, "r1_score_plan_%s_o%d_m%d.csv" % (nm, a.order, a.mmode))
            res = {"err": 0, "plan": o["judge_plan"], "variant": 0, "T": o["judge_T"], "M": o["judge_M"],
                   "J": o["judge_J"], "N": o["N"]}
            with open(fn, "w") as fh:
                fh.write(chr(10).join(cp.csv_lines(res)) + chr(10))
            print("  saved", fn)
        if a.plan and o.get("judge_plan"):
            for i, t in enumerate(o["judge_plan"], 1):
                print("  %2d kind=%d id=%d idx=%d src=%s dst=%s cumT=%d cumM=%d" % (
                    i, t["kind"], t["id"], t["list_idx"], t["src"], t["dst"], t["cum_t"], t["cum_m"]))


if __name__ == "__main__":
    main()
