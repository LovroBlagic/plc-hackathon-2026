"""crane_plan.py - EXACT greedy planner of CONTRACT v1.0 section 4 (reference for FB11 "Crane_Planner").

Usage:
  python tools/crane_plan.py <dataset.json> [--mmode 0] [--order 1] [--balmode 0]
         [--alpha 0,75,125,200] [--improve 3000] [--dist 0] [--lb] [--lim 5] [--trace]
         [--algo v1|v2] [--cmds] [--nocheck]
v1.3: plan = greedy multi-start (4.4/4.5) + IMPROVE phase (4.8, improve()); lower_bound() = 4.9.

Prints the parity CSV of CONTRACT 4.7. `--trace` adds '#'-prefixed lines with the chosen
candidate of every greedy step. `--cmds` adds '#CMD' lines (the crane command sequence).
Unless --nocheck, the plan is executed command by command through the FB1 emulator
(crane_model.FB1) with CheckCmd before every command; CumT_ds/CumM and balance are asserted.

Everything is integer (deciseconds). Tie-breaks: sources in ES order (unloads by index,
then loads by index), destinations x 0..3 outer / y 0..11 inner, strict '<'.
--algo v2 is an EXPERIMENT (not contract v1.0), see TEAM_NOTES.md "Model".
"""

import sys
import argparse

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crane_model as cm  # noqa: E402

M_W = cm.M_WEIGHT


class Src:
    __slots__ = ("kind", "idx", "id", "pos")

    def __init__(self, kind, idx, cid, pos):
        self.kind, self.idx, self.id, self.pos = kind, idx, cid, pos


def eligible(PU, PL, order):
    if order == 0:
        return PU + PL
    if order == 1:
        return PU[:1] + PL[:1]
    return PU[:1] if PU else PL[:1]


def wcost(p0, p1, mmode):
    t, m = cm.move_cost(p0[0], p0[1], p0[2], p1[0], p1[1], p1[2], mmode)
    return t, m, t + M_W * m


def step_candidates(g, crane, PU, PL, cfg, alpha, want_all=False):
    """One greedy step. Returns (pass, best) or, if want_all, (pass, [cands...]) with
    candidates in scan order. Candidate = (score, s, d, E_T, E_M, Lm_T, Lm_M, Nx)."""
    order, mmode, lim, balmode = cfg["order"], cfg["mmode"], cfg["lim"], cfg["balmode"]
    ceil = cfg.get("ceil", 0)
    bay0 = g[0]
    L, R = cm.lr(bay0)
    F, A = cm.fa(bay0)
    uL_tot = sum(1 for s in PU if s.pos[0] <= 1)
    uR_tot = len(PU) - uL_tot
    n_tot = len(PL)
    ES = eligible(PU, PL, order)
    free = [[(x, y, b) for x in range(cm.NX) for y in range(cm.NY) if g[b][x][y] == 0] for b in (0, 1)]

    # Nx helper. Mode 0: ES' = ES minus s -> best/second-best per destination (exactly equal
    # to the literal min). Modes 1/2: ES' recomputed literally (at most 2 entries).
    top2 = {}
    if order == 0:
        for b in (0, 1):
            for d in free[b]:
                b1 = b2 = None  # (value, sid)
                for s2 in ES:
                    v = wcost(d, s2.pos, mmode)[2]
                    if b1 is None or v < b1[0]:
                        b2 = b1
                        b1 = (v, id(s2))
                    elif b2 is None or v < b2[0]:
                        b2 = (v, id(s2))
                top2[d] = (b1, b2)

    for pas in (0, 1):  # 0 = Pass A, 1 = Pass B
        best = None
        allc = []
        for s in ES:
            sx, sy, sb = s.pos
            db = 1 - sb
            E_T, E_M, E = wcost(crane, s.pos, mmode)
            if order != 0:
                PU2 = [q for q in PU if q is not s]
                PL2 = [q for q in PL if q is not s]
                ES2 = eligible(PU2, PL2, order)
            for d in free[db]:
                dx, dy, _ = d
                if s.kind == 1:
                    if sx <= 1:
                        L2, R2 = L - 1, R
                    else:
                        L2, R2 = L, R - 1
                    if sy <= 5:
                        F2, A2 = F - 1, A
                    else:
                        F2, A2 = F, A - 1
                else:
                    if dx <= 1:
                        L2, R2 = L + 1, R
                    else:
                        L2, R2 = L, R + 1
                    if dy <= 5:
                        F2, A2 = F + 1, A
                    else:
                        F2, A2 = F, A + 1
                if not cm.step_ok(L, R, L2, R2, lim, ceil):
                    continue
                if balmode == 1 and not cm.step_ok(F, A, F2, A2, lim):
                    continue
                if pas == 0:
                    uL = uL_tot - (1 if (s.kind == 1 and sx <= 1) else 0)
                    uR = uR_tot - (1 if (s.kind == 1 and sx >= 2) else 0)
                    n = n_tot - (1 if s.kind == 2 else 0)
                    feas = cfg.get("_feas")
                    if feas is not None and order != 0:
                        # v1.4: exact per-list-order feasibility (feas_table), post-step state
                        nu0, nl0, FT = feas
                        if not (FT[nu0 - (uL + uR)][nl0 - n] >> L2) & 1:
                            continue
                    elif not cm.reachable(L2, R2, uL, uR, n, lim):
                        continue
                Lm_T, Lm_M, Lm = wcost(s.pos, d, mmode)
                if order == 0:
                    b1, b2 = top2[d]
                    if b1 is None:
                        Nx = 0
                    elif b1[1] != id(s):
                        Nx = b1[0]
                    else:
                        Nx = b2[0] if b2 is not None else 0
                else:
                    Nx = 0
                    first = True
                    for s2 in ES2:
                        v = wcost(d, s2.pos, mmode)[2]
                        if first or v < Nx:
                            Nx = v
                            first = False
                score = 100 * (E + Lm) + alpha * Nx
                c = (score, s, d, E_T, E_M, Lm_T, Lm_M, Nx)
                if want_all:
                    allc.append(c)
                if best is None or score < best[0]:
                    best = c
        if best is not None:
            return pas, (allc if want_all else best)
    return None, None


def cnt(grid):
    return sum(1 for x in range(cm.NX) for y in range(cm.NY) if grid[x][y] != 0)


def lmask(tot):
    """Bit mask of the L values 0..24 for which R = tot - L is in 0..24."""
    m = 0
    for L in range(25):
        if 0 <= tot - L <= 24:
            m |= 1 << L
    return m


def lmask_end(tot, lim, ceil):
    """Terminal mask: every L (lmask) for the step rule; v1.5 relaxed rule (ceil > 0): only the balanced
    end states |L - R| <= lim, so a relaxed plan always ends balanced (judge round 2 R2-J1)."""
    m = lmask(tot)
    if ceil:
        for L in range(25):
            if abs(2 * L - tot) > lim:
                m &= ~(1 << L)
    return m


def feas_table(bay0, bay1, PU, PL, order, lim, ceil=0):
    """v1.4 (CONTRACT 4.10): exact feasibility of the per-list order (order 1) / unloads-then-loads
    (order 2) under the step rule and the capacities. FT[i][j] = bit mask over L (0..24) of the states
    'i pending unloads done (list prefix), j pending loads done, L containers in x{0,1}' from which all
    remaining transfers can still be executed. R = S0 - i + j - L is implied. Unload sides are fixed
    (source x), a load may go to either half. FB11 builds the same table row by row (i = nu..0)."""
    nu, nl = len(PU), len(PL)
    S0, Y0 = cnt(bay0), cnt(bay1)
    usL = [1 if s.pos[0] <= 1 else 0 for s in PU]
    FT = [[0] * (nl + 1) for _ in range(nu + 1)]
    for i in range(nu, -1, -1):
        for j in range(nl, -1, -1):
            tot = S0 - i + j
            if i == nu and j == nl:
                FT[i][j] = lmask_end(tot, lim, ceil)
                continue
            m = 0
            for L in range(25):
                R = tot - L
                if R < 0 or R > 24:
                    continue
                ok = False
                if i < nu and Y0 + i - j < 48:
                    if usL[i]:
                        L2, R2 = L - 1, R
                    else:
                        L2, R2 = L, R - 1
                    if L2 >= 0 and R2 >= 0 and cm.step_ok(L, R, L2, R2, lim, ceil) and (FT[i + 1][j] >> L2) & 1:
                        ok = True
                if not ok and j < nl and (order == 1 or i == nu):
                    for side in (0, 1):
                        L2, R2 = (L + 1, R) if side == 0 else (L, R + 1)
                        if L2 <= 24 and R2 <= 24 and cm.step_ok(L, R, L2, R2, lim, ceil) and (FT[i][j + 1] >> L2) & 1:
                            ok = True
                            break
                if ok:
                    m |= 1 << L
            FT[i][j] = m
    return FT


def order_feasible(state, order, lim=5, ceil=0):
    """True iff the pending lists can be executed in order mode 1/2 (FT[0][0] contains L0)."""
    loc = locate([state["bay0"], state["bay1"]], state["PU"], state["PL"])
    if loc is None:
        return False
    if order == 0:
        return True
    ft = feas_table(state["bay0"], state["bay1"], loc[0], loc[1], order, lim, ceil)
    L0, _ = cm.lr(state["bay0"])
    return bool((ft[0][0] >> L0) & 1)


def seq_feas(kinds, sides, tot0, y0, lim, ceil=0):
    """v1.4: exact side feasibility of a FIXED sequence (IMPROVE replay Pass A).
    kinds[k] 1 unload / 2 load, sides[k] 0 left / 1 right (unloads), k = 1..n (index 0 unused).
    Returns FA[0..n]: FA[k] = mask of L after step k from which steps k+1..n can be completed."""
    n = len(kinds) - 1
    tot = [tot0] * (n + 1)
    yc = [y0] * (n + 1)
    for k in range(1, n + 1):
        d = -1 if kinds[k] == 1 else 1
        tot[k] = tot[k - 1] + d
        yc[k] = yc[k - 1] - d
    FA = [0] * (n + 1)
    FA[n] = lmask_end(tot[n], lim, ceil)
    for k in range(n, 0, -1):
        tb = tot[k - 1]
        m = 0
        for L in range(25):
            R = tb - L
            if R < 0 or R > 24:
                continue
            ok = False
            if kinds[k] == 1:
                if yc[k - 1] < 48:
                    L2, R2 = (L - 1, R) if sides[k] == 0 else (L, R - 1)
                    ok = L2 >= 0 and R2 >= 0 and cm.step_ok(L, R, L2, R2, lim, ceil) and (FA[k] >> L2) & 1
            else:
                for side in (0, 1):
                    L2, R2 = (L + 1, R) if side == 0 else (L, R + 1)
                    if L2 <= 24 and R2 <= 24 and cm.step_ok(L, R, L2, R2, lim, ceil) and (FA[k] >> L2) & 1:
                        ok = True
                        break
            if ok:
                m |= 1 << L
        FA[k - 1] = m
    return FA


def locate(g, PU_raw, PL_raw):
    """Build Src lists; returns None if a pending ID cannot be found."""
    PU, PL = [], []
    for (idx, cid) in PU_raw:
        p = find(g, 0, cid)
        if p is None:
            return None
        PU.append(Src(1, idx, cid, p))
    for (idx, cid) in PL_raw:
        p = find(g, 1, cid)
        if p is None:
            return None
        PL.append(Src(2, idx, cid, p))
    return PU, PL


def find(g, b, cid):
    for x in range(cm.NX):
        for y in range(cm.NY):
            if g[b][x][y] == cid:
                return (x, y, b)
    return None


def run_variant(state, cfg, alpha, trace=None, algo="v1"):
    """Greedy run of one variant. Returns (err, transfers, T, M)."""
    g = [[col[:] for col in state["bay0"]], [col[:] for col in state["bay1"]]]
    crane = tuple(state["crane"])
    T, M = state["base_t"], state["base_m"]
    loc = locate(g, state["PU"], state["PL"])
    if loc is None:
        return 3, [], T, M
    PU, PL = loc
    plan = []
    mmode = cfg["mmode"]
    step = 0
    while PU or PL:
        step += 1
        if algo == "v2":
            pas, best = step_v2(g, crane, PU, PL, cfg, alpha)
        else:
            pas, best = step_candidates(g, crane, PU, PL, cfg, alpha)
        if best is None:
            return 1, plan, T, M
        score, s, d, E_T, E_M, Lm_T, Lm_M, Nx = best[:8]
        if len(plan) >= 96:
            return 2, plan, T, M
        sx, sy, sb = s.pos
        dx, dy, db = d
        g[db][dx][dy] = g[sb][sx][sy]
        g[sb][sx][sy] = 0
        T += E_T + cm.LIFT_T + Lm_T + cm.PUT_T
        M += E_M + 1 + Lm_M + 1
        plan.append({"kind": s.kind, "id": s.id, "list_idx": s.idx,
                     "src": s.pos, "dst": d, "cum_t": T, "cum_m": M})
        if trace is not None:
            trace.append("# a=%d step=%d pass=%s kind=%d id=%d src=%s dst=%s E=%d Lm=%d Nx=%d score=%d" % (
                alpha, step, "AB"[pas], s.kind, s.id, s.pos, d,
                E_T + M_W * E_M, Lm_T + M_W * Lm_M, Nx, score))
        crane = d
        if s.kind == 1:
            PU = [q for q in PU if q is not s]
        else:
            PL = [q for q in PL if q is not s]
    return 0, plan, T, M


def step_v2(g, crane, PU, PL, cfg, alpha, k=3):
    """EXPERIMENT: 2-step lookahead over the top-k candidates (by v1 score, scan order on ties).
    Value = 100*(E+Lm) of the candidate + v1 score of the best next step (0 if none)."""
    pas, cands = step_candidates(g, crane, PU, PL, cfg, alpha, want_all=True)
    if not cands:
        return None, None
    order_idx = sorted(range(len(cands)), key=lambda i: (cands[i][0], i))[:k]
    best = None
    for i in order_idx:
        c = cands[i]
        score, s, d, E_T, E_M, Lm_T, Lm_M, Nx = c
        sx, sy, sb = s.pos
        dx, dy, db = d
        g[db][dx][dy] = g[sb][sx][sy]
        g[sb][sx][sy] = 0
        PU2 = [q for q in PU if q is not s]
        PL2 = [q for q in PL if q is not s]
        nxt = 0
        if PU2 or PL2:
            _, b2 = step_candidates(g, d, PU2, PL2, cfg, alpha)
            nxt = b2[0] if b2 is not None else 10 ** 9
        g[sb][sx][sy] = g[db][dx][dy]
        g[db][dx][dy] = 0
        val = 100 * (E_T + M_W * E_M + Lm_T + M_W * Lm_M) + nxt
        if best is None or val < best[0]:
            best = (val, c)
    return pas, best[1]


def build_state(ds, lim=5, crane=(0, 0, 1), base_t=0, base_m=0):
    iv = cm.init_validate(ds, lim)
    PU = [(i + 1, iv["UList"][i]) for i in range(48) if iv["UState"][i] == 0]
    PL = [(j + 1, iv["LList"][j]) for j in range(48) if iv["LState"][j] == 0]
    L0, R0 = cm.lr(ds["bay0"])
    return {"bay0": ds["bay0"], "bay1": ds["bay1"], "crane": crane, "carried": 0, "d0": abs(L0 - R0),
            "base_t": base_t, "base_m": base_m, "PU": PU, "PL": PL, "N": iv["N"], "init": iv}


def plan(state, cfg, alphas, trace=None, algo="v1"):
    """Multi-start (4.5). Returns dict(err, variant, plan, T, M, J, variants=[...])."""
    if state.get("carried", 0) != 0:
        return {"err": 4, "variant": 0, "plan": [], "variants": []}
    if (cfg["order"] not in (0, 1, 2) or cfg["balmode"] not in (0, 1) or cfg["mmode"] not in (0, 1, 2)
            or not (1 <= len(alphas) <= 4)):
        return {"err": 3, "variant": 0, "plan": [], "variants": []}
    if cfg["order"] != 0 and cfg.get("exact", True):
        loc = locate([state["bay0"], state["bay1"]], state["PU"], state["PL"])
        if loc is not None:
            ft = feas_table(state["bay0"], state["bay1"], loc[0], loc[1], cfg["order"], cfg["lim"], cfg.get("ceil", 0))
            cfg = dict(cfg, _feas=(len(loc[0]), len(loc[1]), ft))
            L0, _ = cm.lr(state["bay0"])
            if cfg.get("ceil", 0) and not (ft[0][0] >> L0) & 1:
                # v1.5: the relaxed rule is only used when the order is exactly feasible under it
                return {"err": 1, "variant": 0, "plan": [], "variants": []}
    results = []
    for v, a in enumerate(alphas, start=1):
        tr = [] if trace is not None else None
        err, p, T, M = run_variant(state, cfg, a, tr, algo)
        K = (T - state["base_t"]) + M_W * (M - state["base_m"])
        results.append({"v": v, "alpha": a, "err": err, "plan": p, "T": T, "M": M, "K": K})
        if trace is not None:
            trace.extend(tr)
            trace.append("# variant=%d alpha=%d err=%d T_ds=%d M=%d K=%d" % (v, a, err, T, M, K))
    best = None
    for r in results:
        if r["err"] != 0:
            continue
        if best is None or r["K"] < best["K"]:
            best = r
    if best is None:
        return {"err": results[0]["err"], "variant": 0, "plan": [], "variants": results}
    N = state["N"]
    return {"err": 0, "variant": best["v"], "plan": best["plan"], "T": best["T"], "M": best["M"],
            "J": cm.J(best["T"], best["M"], N), "N": N, "variants": results}


def plan_fb(state, cfg, alphas, trace=None, algo="v1", imp_evals=0, imp_dist=0, slot_sweeps=None):
    """FB10 behaviour (default since 7 Nov): plan with the preferred modes; on ErrCode 1 (dead end)
    retry with CfgOrderMode - 1 (2 -> 1 -> 0), then CfgBalMode 1 -> 0.
    res["order"] / res["balmode"] = modes actually used, res["cfg"] = that config.
    imp_evals > 0: FB11 IMPROVE phase (v1.3) on the successful job; res["J0"] = greedy J."""
    c = dict(cfg)
    c["ceil"] = 0
    d0 = state.get("d0")
    if d0 is None:
        L0, R0 = cm.lr(state["bay0"])
        d0 = abs(L0 - R0)
    while True:
        res = plan(state, c, alphas, trace, algo)
        if res["err"] == 1 and c["order"] > 0 and c["ceil"] < d0 and d0 > c["lim"] and RELAX_BAL:
            # v1.5 (judge round 2 R2-J1): the ship started out of balance and the list order is
            # infeasible under the step rule -> same order under the relaxed rule (|L-R| may go back
            # up to the ceiling while > lim) before the order is given up.
            # v1.6 (judge round 3 R3-E3 / R3-J2): ascending ceilings lim+1, lim+2, ..., d0, so the ship
            # never goes back above the SMALLEST imbalance that keeps the list order feasible
            # (FB11 rejects an infeasible ceiling at once via FtMask). RELAX_MIN = 0: v1.5 (ceil = d0).
            if not RELAX_MIN:
                c = dict(c, ceil=d0)
            elif c["ceil"] == 0:
                c = dict(c, ceil=c["lim"] + 1)
            else:
                c = dict(c, ceil=c["ceil"] + 1)
            continue
        if res["err"] != 1 or (c["order"] == 0 and c["balmode"] == 0):
            if res["err"] == 0:
                res["J0"], res["T0"], res["M0"] = res["J"], res["T"], res["M"]
                if imp_evals > 0:
                    res = improve(state, c, res, imp_evals, imp_dist)
                sw = SLOT_SWEEPS if slot_sweeps is None else slot_sweeps
                if sw > 0:
                    res = slot_search(state, c, res, sw)
            res["order"], res["balmode"], res["cfg"] = c["order"], c["balmode"], c
            return res
        if c["order"] > 0:
            c = dict(c, order=c["order"] - 1, ceil=0)
        else:
            c = dict(c, balmode=0, ceil=0)



# ============================================================== IMPROVE phase (CONTRACT v1.3 4.8)
# Deterministic first-improvement local search over the transfer ORDER of the winning greedy plan.
# Written array-style so that FB11 (tia-src/11_FB_Planner.scl, phase IMPROVE) is a transliteration.
#
#  * Sources are numbered 1..n exactly like FB11 (pending unloads by index, then pending loads).
#  * Cur = incumbent: sequence CurSeq[1..n] + per step Dst / cumulative T / M.  It starts as the
#    greedy winner itself (its own destinations, K_greedy), so the result is never worse than greedy.
#  * A candidate differs from Cur first at position p. Steps 1..p-2 are identical (same source, same
#    successor), so the replay starts at k0 = max(1, p-1) from Cur's cached state.
#  * Replay slot rule (per step, source s, successor nx): free cell d of the other bay, scan x 0..3
#    outer / y 0..11 inner, Pass A (step rule + reachability over the remaining sequence) else Pass B
#    (step rule only); value = W(s->d) + W(d->nx) (0 if last); strict '<'.
#  * A replay aborts as soon as K_partial + rest*REST_LB >= CurK (it cannot be accepted anyway).
#  * Neighbourhood, nested in this exact order: mv 0 = re-slot Cur (once, p = 1);
#    mv 1 relocate i -> j; mv 2 swap i < j; mv 3 relocate pair (i, i+1) -> j.  Positions 1-based,
#    j inner. |i - j| <= dist (0 = unlimited).  Order mode 1: a candidate is valid only if no element
#    passes an element of the same list (per-list order kept); order mode 2: no moves.
#  * Every replay counts as one evaluation; stop at `budget` evaluations or after a sweep (mv 1..3)
#    without improvement.  Accept iff K_cand < CurK.
SLOT_SWEEPS = 10                        # v1.4 World.CfgSlotSweeps (0 = no SLOT phase)
RELAX_BAL = os.environ.get("CRANE_RELAX_BAL", "1") == "1"  # v1.5 relaxed balance fallback (R2-J1)
RELAX_MIN = os.environ.get("CRANE_RELAX_MIN", "0") == "1"  # v1.6 World.CfgRelaxMin: ascending relaxed ceilings (R3-E3), default off
IMP_PAT = os.environ.get("CRANE_IMP_PAT", "1") == "1"  # v1.5: order 1 mv 1 = pattern-token relocate (R2-SCORE-1)
REST_LB = 400 + 180 + 2 * M_W          # every remaining transfer: lift+put 40 s, loaded move >= 3 cols, 2 M
BIG_K = 2000000000


class ImpCtx:
    """Snapshot + incumbent for the improve phase (FB11 statics)."""

    def __init__(self, state, cfg, res):
        g0 = [[col[:] for col in state["bay0"]], [col[:] for col in state["bay1"]]]
        self.sG = g0
        self.crane0 = tuple(state["crane"])
        self.baseT, self.baseM = state["base_t"], state["base_m"]
        self.mmode, self.order, self.lim, self.balmode = cfg["mmode"], cfg["order"], cfg["lim"], cfg["balmode"]
        self.ceil = cfg.get("ceil", 0)
        PU, PL = locate(g0, state["PU"], state["PL"])
        self.src = [None] + PU + PL                           # 1-based like FB11 Src*
        self.n = len(PU) + len(PL)
        key = {(s.kind, s.idx): k for k, s in enumerate(self.src) if s is not None}
        plan = res["plan"]
        self.CurSeq = [0] + [key[(tr["kind"], tr["list_idx"])] for tr in plan]
        self.CurDst = [None] + [tuple(tr["dst"]) for tr in plan]
        self.CurT = [self.baseT] + [tr["cum_t"] for tr in plan]
        self.CurM = [self.baseM] + [tr["cum_m"] for tr in plan]
        self.CurK = (self.CurT[-1] - self.baseT) + M_W * (self.CurM[-1] - self.baseM)
        self.evals = 0
        self.accepts = 0
        self.exact = cfg.get("exact", True)

    def kind(self, s):
        return self.src[s].kind


def imp_replay(ctx, cand, p):
    """Replay candidate sequence cand[1..n] from k0 = max(1, p-1) using Cur's cached prefix.
    Returns (K, {k: (dst, T, M)}) for steps k0..n, or (BIG_K, None) on dead end / abort."""
    n, mm, lim = ctx.n, ctx.mmode, ctx.lim
    k0 = max(1, p - 1)
    g = [[col[:] for col in ctx.sG[0]], [col[:] for col in ctx.sG[1]]]
    for k in range(1, k0):
        s = ctx.src[ctx.CurSeq[k]]
        dx, dy, db = ctx.CurDst[k]
        g[db][dx][dy] = s.id
        g[s.pos[2]][s.pos[0]][s.pos[1]] = 0
    if k0 > 1:
        crane = ctx.CurDst[k0 - 1]
    else:
        crane = ctx.crane0
    T, M = ctx.CurT[k0 - 1], ctx.CurM[k0 - 1]
    L, R = cm.lr(g[0])
    F, A = cm.fa(g[0])
    uL = uR = nl = 0
    for k in range(k0, n + 1):
        s = ctx.src[cand[k]]
        if s.kind == 1:
            if s.pos[0] <= 1:
                uL += 1
            else:
                uR += 1
        else:
            nl += 1
    FA = None
    if ctx.exact:
        # v1.4: exact side feasibility of the remaining fixed sequence (replaces reachable() in Pass A)
        kinds = [0] + [ctx.src[cand[k]].kind for k in range(k0, n + 1)]
        sides = [0] + [0 if ctx.src[cand[k]].pos[0] <= 1 else 1 for k in range(k0, n + 1)]
        FA = seq_feas(kinds, sides, L + R, cnt(g[1]), lim, ctx.ceil)
        if not (FA[0] >> L) & 1:
            return BIG_K, None                               # no side assignment completes it
    out = {}
    for k in range(k0, n + 1):
        s = ctx.src[cand[k]]
        sx, sy, sb = s.pos
        nx = ctx.src[cand[k + 1]].pos if k < n else None
        if crane != s.pos:
            t, m = cm.move_cost(crane[0], crane[1], crane[2], sx, sy, sb, mm)
            T += t
            M += m
        if s.kind == 1:
            if sx <= 1:
                uL -= 1
            else:
                uR -= 1
        else:
            nl -= 1
        db = 1 - sb
        best = None
        for pas in (0, 1):
            for x in range(cm.NX):
                for y in range(cm.NY):
                    if g[db][x][y] != 0:
                        continue
                    if s.kind == 1:
                        L2, R2 = (L - 1, R) if sx <= 1 else (L, R - 1)
                        F2, A2 = (F - 1, A) if sy <= 5 else (F, A - 1)
                    else:
                        L2, R2 = (L + 1, R) if x <= 1 else (L, R + 1)
                        F2, A2 = (F + 1, A) if y <= 5 else (F, A + 1)
                    if not cm.step_ok(L, R, L2, R2, lim, ctx.ceil):
                        continue
                    if ctx.balmode == 1 and not cm.step_ok(F, A, F2, A2, lim):
                        continue
                    if pas == 0:
                        if FA is not None:
                            if not (FA[k - k0 + 1] >> L2) & 1:
                                continue
                        elif not cm.reachable(L2, R2, uL, uR, nl, lim):
                            continue
                    d = (x, y, db)
                    v = wcost(s.pos, d, mm)[2]
                    if nx is not None:
                        v += wcost(d, nx, mm)[2]
                    if best is None or v < best[0]:
                        best = (v, d, L2, R2, F2, A2)
            if best is not None:
                break
        if best is None:
            return BIG_K, None
        d = best[1]
        L, R, F, A = best[2], best[3], best[4], best[5]
        g[db][d[0]][d[1]] = s.id
        g[sb][sx][sy] = 0
        t, m = cm.move_cost(sx, sy, sb, d[0], d[1], d[2], mm)
        T += 400 + t
        M += 2 + m
        out[k] = (d, T, M)
        crane = d
        kp = (T - ctx.baseT) + M_W * (M - ctx.baseM)
        if kp + (n - k) * REST_LB >= ctx.CurK:
            return BIG_K, None                               # cannot beat the incumbent
    K = (T - ctx.baseT) + M_W * (M - ctx.baseM)
    return K, out


def imp_valid(ctx, mv, i, j):
    """Order-mode validity of move (mv, i, j) on CurSeq without building it (FB11: same scan)."""
    if ctx.order == 0:
        return True
    if ctx.order == 2:
        return False
    seq = ctx.CurSeq
    if mv == 1 and IMP_PAT:
        # v1.5 (judge round 2 R2-SCORE-1): order mode 1, mv 1 = relocate the KIND TOKEN at i to j and
        # re-derive the sequence (k-th U = k-th pending unload, k-th L = k-th load). Valid iff the
        # pattern changes, i.e. some element between i and j is of the other kind. Superset of the
        # old mv 1 (a run of the other kind only) and also shifts whole blocks.
        ki = ctx.kind(seq[i])
        lo, hi = (i + 1, j) if i < j else (j, i - 1)
        for q in range(lo, hi + 1):
            if ctx.kind(seq[q]) != ki:
                return True
        return False
    if mv == 1:
        ki = ctx.kind(seq[i])
        lo, hi = (i + 1, j) if i < j else (j, i - 1)
        for q in range(lo, hi + 1):
            if ctx.kind(seq[q]) == ki:
                return False
        return True
    if mv == 2:
        return j == i + 1 and ctx.kind(seq[i]) != ctx.kind(seq[j])
    # mv 3: pair (i, i+1) moved so that it starts at j
    ka, kb = ctx.kind(seq[i]), ctx.kind(seq[i + 1])
    if j < i:
        lo, hi = j, i - 1
    else:
        lo, hi = i + 2, j + 1
    for q in range(lo, hi + 1):
        kq = ctx.kind(seq[q])
        if kq == ka or kq == kb:
            return False
    return True


def imp_build(ctx, mv, i, j):
    """Candidate sequence (1-based list) and first changed position p."""
    seq = ctx.CurSeq
    if mv == 0:
        return seq[:], 1
    c = seq[1:]
    if mv == 1 and IMP_PAT and ctx.order == 1:
        # pattern-token relocate (see imp_valid); p = first position that differs
        kinds = [ctx.kind(e) for e in c]
        t = kinds.pop(i - 1)
        kinds.insert(j - 1, t)
        us = [e for e in c if ctx.kind(e) == 1]
        ls = [e for e in c if ctx.kind(e) == 2]
        iu = il = 0
        out = [0]
        for k in kinds:
            if k == 1:
                out.append(us[iu])
                iu += 1
            else:
                out.append(ls[il])
                il += 1
        p = 1
        while out[p] == seq[p]:
            p += 1
        return out, p
    if mv == 1:
        e = c.pop(i - 1)
        c.insert(j - 1, e)
    elif mv == 2:
        c[i - 1], c[j - 1] = c[j - 1], c[i - 1]
    else:
        seg = c[i - 1:i + 1]
        del c[i - 1:i + 1]
        c[j - 1:j - 1] = seg
    return [0] + c, min(i, j)


def imp_moves(n, dist):
    """The exact neighbourhood iteration order (generator of (mv, i, j); None = end of sweep)."""
    yield (0, 1, 1)
    while True:
        for mv in (1, 2, 3):
            imax = n - 1 if mv == 3 else n
            for i in range(1, imax + 1):
                for j in range(1, imax + 1):
                    if j == i or (mv == 2 and j < i):
                        continue
                    if dist > 0 and abs(i - j) > dist:
                        continue
                    yield (mv, i, j)
        yield None


def improve(state, cfg, res, budget, dist=0):
    """Improve phase on a successful plan() result. Returns a new result dict (same format) with
    extra keys imp_evals, imp_accepts, imp_K0, imp_K. Never worse than the input."""
    if res["err"] != 0 or budget <= 0 or len(res["plan"]) < 2:
        out = dict(res)
        out.update(imp_evals=0, imp_accepts=0)
        return out
    ctx = ImpCtx(state, cfg, res)
    K0 = ctx.CurK
    if ctx.order != 2:
        sweep_imp = False
        for mvij in imp_moves(ctx.n, dist):
            if mvij is None:
                if not sweep_imp:
                    break
                sweep_imp = False
                continue
            if ctx.evals >= budget:
                break
            mv, i, j = mvij
            if mv != 0 and not imp_valid(ctx, mv, i, j):
                continue
            cand, p = imp_build(ctx, mv, i, j)
            K, steps = imp_replay(ctx, cand, p)
            ctx.evals += 1
            if K < ctx.CurK:
                ctx.accepts += 1
                sweep_imp = True
                for k, (d, T, M) in steps.items():
                    ctx.CurDst[k] = d
                    ctx.CurT[k] = T
                    ctx.CurM[k] = M
                ctx.CurSeq = cand
                ctx.CurK = K
    plan = []
    for k in range(1, ctx.n + 1):
        s = ctx.src[ctx.CurSeq[k]]
        plan.append({"kind": s.kind, "id": s.id, "list_idx": s.idx, "src": s.pos, "dst": ctx.CurDst[k],
                     "cum_t": ctx.CurT[k], "cum_m": ctx.CurM[k]})
    out = dict(res)
    out.update(plan=plan, T=ctx.CurT[ctx.n], M=ctx.CurM[ctx.n],
               J=cm.J(ctx.CurT[ctx.n], ctx.CurM[ctx.n], res["N"]),
               imp_evals=ctx.evals, imp_accepts=ctx.accepts, imp_K0=K0, imp_K=ctx.CurK)
    return out


# ============================================================== SLOT phase (CONTRACT v1.4 4.11)
# After IMPROVE the transfer sequence is fixed; only the drop cells are re-optimised. The cost of a
# drop cell d of step k is separable: c_k(d) = W(s_k -> d) + W(d -> s_{k+1}) (0 for the last step).
#  * Avail[b,x,y] = first step at which a drop may use the cell: 1 if empty at plan time, k+1 if it is
#    the source cell of step k, never otherwise. A cell holds at most one drop (Used).
#  * Per sweep, k = 1..n: (a) relocate Dst[k] to every free cell c of its bay (x 0..3 / y 0..11) with
#    Avail[c] <= k; (b) swap Dst[k] <-> Dst[q] for q = k+1..n in the same bay with Avail[Dst[q]] <= k.
#    First improvement, strict '<'. A change of a load's ship half (or fore/aft half, BalMode 1)
#    re-checks the step rule over the whole sequence.
#  * Stop after a sweep without improvement or after `sweeps` sweeps. FB11: one k per OB1 call.
def slot_search(state, cfg, res, sweeps):
    if res["err"] != 0 or sweeps <= 0 or len(res["plan"]) < 1:
        out = dict(res)
        out.update(slot_sweeps=0, slot_accepts=0)
        return out
    mm, lim, balmode = cfg["mmode"], cfg["lim"], cfg["balmode"]
    ceil = cfg.get("ceil", 0)
    plan = res["plan"]
    n = len(plan)
    SP = [None] + [tuple(tr["src"]) for tr in plan]
    KD = [0] + [tr["kind"] for tr in plan]
    DX = [0] + [tr["dst"][0] for tr in plan]
    DY = [0] + [tr["dst"][1] for tr in plan]
    DB = [0] + [tr["dst"][2] for tr in plan]
    NEVER = 999
    Avail = [[[NEVER] * 12 for _ in range(4)] for _ in range(2)]
    Used = [[[0] * 12 for _ in range(4)] for _ in range(2)]
    g0 = [state["bay0"], state["bay1"]]
    for b in (0, 1):
        for x in range(4):
            for y in range(12):
                if g0[b][x][y] == 0:
                    Avail[b][x][y] = 1
    for k in range(1, n + 1):
        sx, sy, sb = SP[k]
        Avail[sb][sx][sy] = k + 1
        Used[DB[k]][DX[k]][DY[k]] = k
    L0, R0 = cm.lr(state["bay0"])
    F0, A0 = cm.fa(state["bay0"])

    def cost(k, x, y, b):
        v = wcost(SP[k], (x, y, b), mm)[2]
        if k < n:
            v += wcost((x, y, b), SP[k + 1], mm)[2]
        return v

    def traj_ok():
        L, R, F, A = L0, R0, F0, A0
        for k in range(1, n + 1):
            if KD[k] == 1:
                sx, sy, _ = SP[k]
                L2, R2 = (L - 1, R) if sx <= 1 else (L, R - 1)
                F2, A2 = (F - 1, A) if sy <= 5 else (F, A - 1)
            else:
                L2, R2 = (L + 1, R) if DX[k] <= 1 else (L, R + 1)
                F2, A2 = (F + 1, A) if DY[k] <= 5 else (F, A + 1)
            if not cm.step_ok(L, R, L2, R2, lim, ceil):
                return False
            if balmode == 1 and not cm.step_ok(F, A, F2, A2, lim):
                return False
            L, R, F, A = L2, R2, F2, A2
        if ceil and abs(L - R) > lim:
            return False                      # v1.5: a relaxed plan must end balanced
        return True

    def side_change(k, x, y):
        if KD[k] != 2:
            return False
        if (x <= 1) != (DX[k] <= 1):
            return True
        return balmode == 1 and (y <= 5) != (DY[k] <= 5)

    nsw = acc = 0
    while nsw < sweeps:
        nsw += 1
        imp = False
        for k in range(1, n + 1):
            b = DB[k]
            for x in range(4):
                for y in range(12):
                    if Used[b][x][y] != 0 or Avail[b][x][y] > k:
                        continue
                    if cost(k, x, y, b) >= cost(k, DX[k], DY[k], b):
                        continue
                    ox, oy = DX[k], DY[k]
                    chk = side_change(k, x, y)
                    DX[k], DY[k] = x, y
                    if chk and not traj_ok():
                        DX[k], DY[k] = ox, oy
                        continue
                    Used[b][ox][oy] = 0
                    Used[b][x][y] = k
                    imp = True
                    acc += 1
            for q in range(k + 1, n + 1):
                if DB[q] != b or Avail[b][DX[q]][DY[q]] > k:
                    continue
                old = cost(k, DX[k], DY[k], b) + cost(q, DX[q], DY[q], b)
                new = cost(k, DX[q], DY[q], b) + cost(q, DX[k], DY[k], b)
                if new >= old:
                    continue
                chk = side_change(k, DX[q], DY[q]) or side_change(q, DX[k], DY[k])
                DX[k], DX[q] = DX[q], DX[k]
                DY[k], DY[q] = DY[q], DY[k]
                if chk and not traj_ok():
                    DX[k], DX[q] = DX[q], DX[k]
                    DY[k], DY[q] = DY[q], DY[k]
                    continue
                Used[b][DX[k]][DY[k]] = k
                Used[b][DX[q]][DY[q]] = q
                imp = True
                acc += 1
        if not imp:
            break
    # cumulative T / M along the (unchanged) sequence
    T, M = state["base_t"], state["base_m"]
    crane = tuple(state["crane"])
    newplan = []
    for k in range(1, n + 1):
        tr = dict(plan[k - 1])
        if crane != SP[k]:
            t, m = cm.move_cost(crane[0], crane[1], crane[2], SP[k][0], SP[k][1], SP[k][2], mm)
            T += t
            M += m
        d = (DX[k], DY[k], DB[k])
        t, m = cm.move_cost(SP[k][0], SP[k][1], SP[k][2], d[0], d[1], d[2], mm)
        T += 400 + t
        M += 2 + m
        tr.update(dst=d, cum_t=T, cum_m=M)
        newplan.append(tr)
        crane = d
    out = dict(res)
    if (T - res["T"]) + M_W * (M - res["M"]) <= 0:
        out.update(plan=newplan, T=T, M=M, J=cm.J(T, M, res["N"]))
    out.update(slot_sweeps=nsw, slot_accepts=acc)
    return out


# ============================================================== closed-form lower bound (4.9)
def lower_bound(state):
    """Closed-form relaxation (plans/CRANE_RESEARCH.md 2.1), valid for any order/balance/capacity
    and every M rule: x-travel X (columns) depends only on the source order:
      X = 2*sum(x_ship of unloads) + 2*sum(3 - x_yard of loads) + 3P + 3S + F,
    S = forced same-kind neighbours given the first kind, F = 3 + |G(crane) - G(first)| - v(first),
    v = x+3 (unload) / 6-x (load).  y-travel ignored (max(60dG, 23dy) >= 60dG).
    T_LB = 400 P + 60 X_min (ds), M_LB = 4P - [some pending source at the crane position].
    Returns (T_LB_ds, M_LB, J_LB) with N = state["N"] (0, 0, 0.0 if nothing pending)."""
    g = [state["bay0"], state["bay1"]]
    loc = locate(g, state["PU"], state["PL"])
    if loc is None:
        return 0, 0, 0.0
    PU, PL = loc
    u, l = len(PU), len(PL)
    P = u + l
    if P == 0:
        return 0, 0, 0.0
    cx, cy, cb = state["crane"]
    cG = cm.G(cx, cb)
    base = 2 * sum(s.pos[0] for s in PU) + 2 * sum(3 - s.pos[0] for s in PL) + 3 * P
    best = None
    for first in (1, 2):
        grp = PU if first == 1 else PL
        if not grp:
            continue
        if first == 2:
            S = (u - l) if u > l else max(0, l - u - 1)
        else:
            S = max(0, u - l - 1) if u >= l else (l - u)
        Fm = None
        for s in grp:
            v = (s.pos[0] + 3) if first == 1 else (6 - s.pos[0])
            f = 3 + abs(cG - cm.G(s.pos[0], s.pos[2])) - v
            if Fm is None or f < Fm:
                Fm = f
        x = base + 3 * S + Fm
        if best is None or x < best:
            best = x
    T = 400 * P + 60 * best
    at = any(tuple(s.pos) == (cx, cy, cb) for s in PU + PL)
    M = 4 * P - (1 if at else 0)
    return T, M, cm.J(T, M, state["N"])


def commands(plan_list, crane0):
    """Crane command sequence with the skip rule (phase 0 skipped when crane already at Src)."""
    cmds = []
    pos = tuple(crane0)
    for i, tr in enumerate(plan_list, start=1):
        if tuple(tr["src"]) != pos:
            cmds.append((3, tr["src"], i, 0))
        cmds.append((1, tr["src"], i, 1))
        cmds.append((3, tr["dst"], i, 2))
        cmds.append((2, tr["dst"], i, 3))
        pos = tuple(tr["dst"])
    return cmds


def simulate(state, plan_list, cfg, base_ok=True):
    """Execute through FB1 + CheckCmd. Raises AssertionError on any mismatch.
    Returns list of executed commands with cumulative (T_ds, M)."""
    fb = cm.FB1(cfg["mmode"])
    fb.x, fb.y, fb.bay = state["crane"]
    fb.T_ds, fb.M = state["base_t"], state["base_m"]
    w = cm.World(state["bay0"], state["bay1"])
    L0, R0 = cm.lr(w.g[0])
    init_bal = abs(L0 - R0) <= cfg["lim"]
    out = []
    for (c, p, tri, ph) in commands(plan_list, state["crane"]):
        x, y, b = p
        rc = cm.check_cmd(w, c, x, y, b, fb.pos() if c != 3 else None, cfg["lim"], cfg["balmode"], cfg.get("ceil", 0))
        assert rc == 0, "CheckCmd rc=%d at transfer %d phase %d" % (rc, tri, ph)
        if c in (1, 2):
            assert fb.pos() == (x, y, b), "crane not at lift/put position"
        fb.command(c, x, y, b)
        if c in (1, 2):
            cm.apply_cmd(w, c, fb.pos())
            L, R = cm.lr(w.g[0])
            if init_bal:
                assert abs(L - R) <= cfg["lim"], "balance violated |%d-%d| at transfer %d" % (L, R, tri)
        out.append({"cmd": c, "x": x, "y": y, "bay": b, "tr": tri, "phase": ph, "t_ds": fb.T_ds, "m": fb.M})
        if ph == 3:
            tr = plan_list[tri - 1]
            assert fb.T_ds == tr["cum_t"] and fb.M == tr["cum_m"], \
                "cum mismatch at transfer %d: fb=(%d,%d) plan=(%d,%d)" % (tri, fb.T_ds, fb.M, tr["cum_t"], tr["cum_m"])
    # every list container at its destination
    for tr in plan_list:
        dx, dy, db = tr["dst"]
        assert w.g[db][dx][dy] == tr["id"]
    return out


def csv_lines(res):
    lines = ["i,kind,id,list_idx,src_bay,src_x,src_y,dst_bay,dst_x,dst_y,cum_t_ds,cum_m"]
    if res["err"] != 0:
        lines.append("RESULT error=%d" % res["err"])
        return lines
    for i, tr in enumerate(res["plan"], start=1):
        sx, sy, sb = tr["src"]
        dx, dy, db = tr["dst"]
        lines.append("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d" % (
            i, tr["kind"], tr["id"], tr["list_idx"], sb, sx, sy, db, dx, dy, tr["cum_t"], tr["cum_m"]))
    tail = (" order=%d" % res["order"]) if "order" in res else ""
    lines.append("RESULT variant=%d T_ds=%d M=%d J=%.4f N=%d%s" % (res["variant"], res["T"], res["M"], res["J"], res["N"], tail))
    return lines


def parse_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--mmode", type=int, default=0, help="v1.7 default 0 = spec rule; 2 = FB1 per command")
    ap.add_argument("--order", type=int, default=1, help="preferred CfgOrderMode (PLC default 1)")
    ap.add_argument("--nofallback", action="store_true", help="no 2->1->0 fallback on ErrCode 1 (raw FB11)")
    ap.add_argument("--balmode", type=int, default=0)
    ap.add_argument("--alpha", default="0,75,125,200", help="CfgAlpha (v1.7 default 0,75,125,200)")
    ap.add_argument("--improve", type=int, default=3000, help="IMPROVE evaluations (CfgImproveEvals, 0 = off)")
    ap.add_argument("--dist", type=int, default=0, help="CfgImproveDist (0 = unlimited)")
    ap.add_argument("--slot", type=int, default=SLOT_SWEEPS, help="SLOT phase sweeps (CfgSlotSweeps, 0 = off)")
    ap.add_argument("--noexact", action="store_true", help="v1.3 behaviour: reachable() instead of the exact DP")
    ap.add_argument("--lb", action="store_true", help="print the closed-form lower bound")
    ap.add_argument("--lim", type=int, default=5)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--cmds", action="store_true")
    ap.add_argument("--nocheck", action="store_true")
    ap.add_argument("--algo", default="v1", choices=["v1", "v2"])
    return ap.parse_args(argv)


def main(argv=None):
    a = parse_args(argv if argv is not None else sys.argv[1:])
    ds = cm.load_dataset(a.dataset)
    cfg = {"mmode": a.mmode, "order": a.order, "balmode": a.balmode, "lim": a.lim, "exact": not a.noexact}
    alphas = [int(v) for v in a.alpha.split(",") if v.strip() != ""]
    state = build_state(ds, a.lim)
    trace = [] if a.trace else None
    if state["init"]["blocking"]:
        print("i,kind,id,list_idx,src_bay,src_x,src_y,dst_bay,dst_x,dst_y,cum_t_ds,cum_m")
        print("RESULT error=capacity(bit7)")
        return 0
    if a.nofallback:
        res = plan(state, cfg, alphas, trace, a.algo)
        if res["err"] == 0 and a.improve > 0:
            res = improve(state, cfg, res, a.improve, a.dist)
        if res["err"] == 0 and a.slot > 0:
            res = slot_search(state, cfg, res, a.slot)
    else:
        res = plan_fb(state, cfg, alphas, trace, a.algo, imp_evals=a.improve, imp_dist=a.dist, slot_sweeps=a.slot)
        cfg = res["cfg"]
    if a.lb:
        lt, lm, lj = lower_bound(state)
        print("# LB T_ds=%d M=%d J=%.4f" % (lt, lm, lj))
        if res["err"] == 0:
            print("# greedy J=%.4f  improved J=%.4f  evals=%s accepts=%s  gap=%.2f %%" % (
                res.get("J0", res["J"]), res["J"], res.get("imp_evals", 0), res.get("imp_accepts", 0),
                100.0 * (res["J"] / lj - 1) if lj > 0 else 0.0))
    if trace:
        print("\n".join(trace))
    print("\n".join(csv_lines(res)))
    if res["err"] == 0:
        if a.cmds:
            for c in commands(res["plan"], state["crane"]):
                print("#CMD %d,%d,%d,%d,tr=%d,ph=%d" % (c[0], c[1][0], c[1][1], c[1][2], c[2], c[3]))
        if not a.nocheck:
            simulate(state, res["plan"], cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
