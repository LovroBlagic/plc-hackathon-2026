"""r2_score_opt.py - SCORE judge (round 2): exact small-N solver + joint (order, side) annealer.

Builds on r1_score_opt.Prob (per-bay min-cost assignment of drop cells for a FIXED transfer order,
which is exact for that order once the load SIDES (ship L/R) are fixed).  Round 1 chose sides with
a greedy repair, which is why its "EX" runs could lose to our planner.  Here:

  exact():  order 1 -> every interleaving of the two lists; order 0 -> every permutation (small n).
            For each sequence: relaxed assignment (no side masks) is a lower bound; if it is balance-ok
            it is optimal for that sequence, else EVERY balance-feasible side vector is enumerated
            (DFS with the step rule + side capacity).  => true optimum under our cost model.
  anneal(): state = (sequence, explicit side vector); moves = order moves (single / block),
            side flip, side swap; evaluation always with masks (+ relaxed shortcut).

Every reported plan is re-executed through crane_plan.simulate (FB1 emulator + CheckCmd + balance).

  python tools/judge_sets/r2_score_opt.py <set.json> [...] [--order 1] [--mmode 2] [--iters 40000]
         [--exact-limit 400000] [--seeds 3] [--save]
"""
import argparse
import itertools
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402
import r1_score_opt as r1  # noqa: E402

BIG = r1.BIG


class Prob2(r1.Prob):
    def side_vectors(self, seq, limit=5000):
        """All balance-feasible side vectors (dict load-src-index -> 0 L / 1 R) for seq."""
        L0, R0 = cm.lr(self.g0[0])
        fL0 = sum(1 for x in (0, 1) for y in range(12) if self.g0[0][x][y] == 0)
        fR0 = sum(1 for x in (2, 3) for y in range(12) if self.g0[0][x][y] == 0)
        out = []
        cur = {}

        def rec(k, L, R, fL, fR):
            if len(out) >= limit:
                return
            if k == len(seq):
                out.append(dict(cur))
                return
            i = seq[k]
            s = self.src[i]
            if s.kind == 1:
                if s.pos[0] <= 1:
                    L2, R2, fL2, fR2 = L - 1, R, fL + 1, fR
                else:
                    L2, R2, fL2, fR2 = L, R - 1, fL, fR + 1
                if not cm.step_ok(L, R, L2, R2, self.lim):
                    return
                rec(k + 1, L2, R2, fL2, fR2)
                return
            for side in (0, 1):
                if side == 0:
                    if fL <= 0:
                        continue
                    L2, R2, fL2, fR2 = L + 1, R, fL - 1, fR
                else:
                    if fR <= 0:
                        continue
                    L2, R2, fL2, fR2 = L, R + 1, fL, fR - 1
                if not cm.step_ok(L, R, L2, R2, self.lim):
                    continue
                cur[i] = side
                rec(k + 1, L2, R2, fL2, fR2)
                del cur[i]

        rec(0, L0, R0, fL0, fR0)
        return out

    def best_for_seq(self, seq, ub=BIG):
        """Exact optimum for a fixed sequence (relaxation, else side enumeration)."""
        K, d = self.evaluate(seq)
        if K < BIG:
            return K, d, None
        if d is None:
            return BIG, None, None
        # relaxed (balance-ignoring) cost is a lower bound
        Krel = self.relaxed(seq)
        if Krel >= ub:
            return BIG, None, None
        best = (BIG, None, None)
        for sv in self.side_vectors(seq):
            K2, d2 = self.evaluate(seq, sv)
            if K2 < best[0]:
                best = (K2, d2, sv)
        return best

    def relaxed(self, seq):
        saved = self.balance_ok
        self.balance_ok = lambda a, b: True
        try:
            K, _ = self.evaluate(seq)
        finally:
            self.balance_ok = saved
        return K

    def exact(self, limit=400000):
        best = (BIG, None, None, None)
        if self.order == 1:
            cnt = math.comb(self.n, self.nu)
            if cnt > limit:
                return None
            for pos in itertools.combinations(range(self.n), self.nu):
                pat = [1] * self.n
                for p in pos:
                    pat[p] = 0
                seq = self.seq_from_pattern(pat)
                K, d, sv = self.best_for_seq(seq, best[0])
                if K < best[0]:
                    best = (K, seq, d, sv)
        else:
            if math.factorial(self.n) > limit:
                return None
            for seq in itertools.permutations(range(self.n)):
                seq = list(seq)
                K, d, sv = self.best_for_seq(seq, best[0])
                if K < best[0]:
                    best = (K, seq, d, sv)
        return best

    # -------------------------------------------------------------- joint annealing
    def eval_sides(self, seq, sides):
        K, d = self.evaluate(seq)
        if K < BIG:
            return K, d
        return self.evaluate(seq, sides)

    def fix_sides(self, seq, sides):
        """Make the side vector balance-feasible for seq (greedy keep-preferred), or None."""
        L, R = cm.lr(self.g0[0])
        fL = sum(1 for x in (0, 1) for y in range(12) if self.g0[0][x][y] == 0)
        fR = sum(1 for x in (2, 3) for y in range(12) if self.g0[0][x][y] == 0)
        uL = sum(1 for i in seq if self.src[i].kind == 1 and self.src[i].pos[0] <= 1)
        uR = sum(1 for i in seq if self.src[i].kind == 1 and self.src[i].pos[0] >= 2)
        nl = sum(1 for i in seq if self.src[i].kind == 2)
        out = {}
        for i in seq:
            s = self.src[i]
            if s.kind == 1:
                if s.pos[0] <= 1:
                    L -= 1; fL += 1; uL -= 1
                else:
                    R -= 1; fR += 1; uR -= 1
                continue
            nl -= 1
            want = sides.get(i, 0)
            ch = None
            for pas in (0, 1):
                for sd in (want, 1 - want):
                    if (fL if sd == 0 else fR) <= 0:
                        continue
                    L2, R2 = (L + 1, R) if sd == 0 else (L, R + 1)
                    if not cm.step_ok(L, R, L2, R2, self.lim):
                        continue
                    if pas == 0 and not cm.reachable(L2, R2, uL, uR, nl, self.lim):
                        continue
                    ch = sd
                    break
                if ch is not None:
                    break
            if ch is None:
                return None
            out[i] = ch
            if ch == 0:
                L += 1; fL -= 1
            else:
                R += 1; fR -= 1
        return out

    def anneal2(self, seq0, sides0, iters=40000, T0=400.0, seed=1):
        rng = random.Random(seed)
        cur = list(seq0)
        sc = self.fix_sides(cur, dict(sides0)) or dict(sides0)
        Kc, dc = self.evaluate(cur, sc)
        if Kc >= BIG:
            Kc, dc = self.eval_sides(cur, sc)
        best = (Kc, list(cur), dc, dict(sc))
        n = self.n
        loads = [i for i in range(self.n) if self.src[i].kind == 2]
        if n < 2:
            return best
        for it in range(iters):
            temp = T0 * (1 - it / iters) + 1e-3
            c = list(cur)
            sd = dict(sc)
            r = rng.random()
            if r < 0.25 and loads:
                k = rng.choice(loads)
                sd[k] = 1 - sd.get(k, 0)
            elif r < 0.35 and len(loads) >= 2:
                a, b = rng.sample(loads, 2)
                sd[a], sd[b] = sd.get(b, 0), sd.get(a, 0)
            else:
                if self.order == 1:
                    i = rng.randrange(n)
                    rr = rng.random()
                    if rr < 0.4:
                        j = i + rng.choice((-1, 1))
                        if not (0 <= j < n) or (c[i] < self.nu) == (c[j] < self.nu):
                            continue
                        c[i], c[j] = c[j], c[i]
                    elif rr < 0.7:
                        j = rng.randrange(n)
                        e = c.pop(i)
                        c.insert(j, e)
                        if not self.valid_seq(c):
                            continue
                    else:
                        ln = rng.randint(2, max(2, min(8, n - 1)))
                        if i + ln > n:
                            continue
                        blk = c[i:i + ln]
                        rest = c[:i] + c[i + ln:]
                        j = rng.randrange(len(rest) + 1)
                        c = rest[:j] + blk + rest[j:]
                        if not self.valid_seq(c):
                            continue
                else:
                    i, j = rng.randrange(n), rng.randrange(n)
                    if i == j:
                        continue
                    rr = rng.random()
                    if rr < 0.3:
                        c[i], c[j] = c[j], c[i]
                    elif rr < 0.6:
                        e = c.pop(i)
                        c.insert(j, e)
                    elif rr < 0.8:
                        a, b = min(i, j), max(i, j)
                        c[a:b + 1] = c[a:b + 1][::-1]
                    else:
                        ln = rng.randint(2, max(2, min(8, n - 1)))
                        if i + ln > n:
                            continue
                        blk = c[i:i + ln]
                        rest = c[:i] + c[i + ln:]
                        j = rng.randrange(len(rest) + 1)
                        c = rest[:j] + blk + rest[j:]
            sd2 = self.fix_sides(c, sd)
            if sd2 is None:
                continue
            K, d = self.evaluate(c, sd2)
            if K >= BIG:
                continue
            if K <= Kc or rng.random() < math.exp(-(K - Kc) / temp):
                cur, Kc, sc = c, K, sd2
                if K < best[0]:
                    best = (K, list(c), d, dict(sd2))
        return best


def ours(ds, order=1, mmode=2, evals=3000):
    st = cp.build_state(ds)
    cfg = {"mmode": mmode, "order": order, "balmode": 0, "lim": 5}
    r = cp.plan_fb(st, cfg, [0, 100, 200, 300], imp_evals=evals)
    return r, st


def solve(ds, order=1, mmode=2, iters=40000, seeds=3, exact_limit=400000, verbose=True, t_budget=None):
    t0 = time.time()
    r, st = ours(ds, order, mmode)
    pr = Prob2(ds, mmode, 5, order)
    lbT, lbM, lbJ = cp.lower_bound(st)
    out = {"name": ds.get("name"), "N": st["N"], "P": pr.n, "ours_J": r.get("J"), "ours_order": r.get("order"),
           "lb": lbJ, "err": r["err"]}
    if r["err"] != 0 or pr.n == 0:
        out["judge_J"] = None
        return out
    pr.order = r["order"]
    cands = []
    ex = pr.exact(exact_limit)
    if ex is not None and ex[1] is not None:
        cands.append(ex)
        out["exact"] = True
    else:
        out["exact"] = False
        key = {(s.kind, s.idx): k for k, s in enumerate(pr.src)}
        seq_ours = [key[(t["kind"], t["list_idx"])] for t in r["plan"]]
        sides0 = {key[(t["kind"], t["list_idx"])]: (0 if t["dst"][0] <= 1 else 1) for t in r["plan"] if t["kind"] == 2}
        for sd in range(1, seeds + 1):
            cands.append(pr.anneal2(seq_ours, sides0, iters, seed=sd))
        # restart from best so far with a cooler schedule
        b = min(cands, key=lambda c: c[0])
        cands.append(pr.anneal2(b[1], b[3], iters, T0=120.0, seed=99))
    cands = [c for c in cands if c[1] is not None and c[0] < BIG]
    if not cands:
        out["judge_J"] = None
        return out
    best = min(cands, key=lambda c: c[0])
    plan, T, M, J = pr.check(best[1], best[2])
    out.update(judge_J=J, judge_T=T, judge_M=M, ours_T=r["T"], ours_M=r["M"], judge_plan=plan,
               gain_pct=100.0 * (r["J"] / J - 1), secs=time.time() - t0)
    if verbose:
        print("%s N=%d P=%d order=%d ours J=%.4f (T=%d M=%d)  judge J=%.4f (T=%d M=%d)  %s  ours/judge-1=%+.2f%%  LB=%.4f  %.0fs" % (
            out["name"], out["N"], pr.n, pr.order, r["J"], r["T"], r["M"], J, T, M,
            "EXACT" if out["exact"] else "SA2", out["gain_pct"], lbJ, out["secs"]))
    return out


def save_plan(name, o, order, mmode):
    fn = os.path.join(HERE, "r2_score_plan_%s_o%d_m%d.csv" % (name, order, mmode))
    res = {"err": 0, "plan": o["judge_plan"], "variant": 0, "T": o["judge_T"], "M": o["judge_M"],
           "J": o["judge_J"], "N": o["N"]}
    with open(fn, "w") as fh:
        fh.write(chr(10).join(cp.csv_lines(res)) + chr(10))
    return fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--order", type=int, default=1)
    ap.add_argument("--mmode", type=int, default=2)
    ap.add_argument("--iters", type=int, default=40000)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--exact-limit", type=int, default=400000)
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()
    for f in a.files:
        ds = cm.load_dataset(f)
        o = solve(ds, a.order, a.mmode, a.iters, a.seeds, a.exact_limit)
        if a.save and o.get("judge_plan"):
            print("  saved", save_plan(os.path.basename(f)[:-5], o, a.order, a.mmode))
        if a.plan and o.get("judge_plan"):
            for i, t in enumerate(o["judge_plan"], 1):
                print("  %2d kind=%d id=%d idx=%d src=%s dst=%s cumT=%d cumM=%d" % (
                    i, t["kind"], t["id"], t["list_idx"], t["src"], t["dst"], t["cum_t"], t["cum_m"]))


if __name__ == "__main__":
    main()
