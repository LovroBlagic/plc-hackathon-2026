"""fb10_init_model.py - Python transliteration of the FB10 data-load and ACK re-target paths (v1.6).

Covers the parts of FB10 "Crane_Control" (tia-src/21_FB_CraneControl.scl) that the planner mirrors do
not cover:
  REGION 2a   DB10/DB11 <-> World mirror with Snap0/Snap1.
              v1.6 (judge round 3 R3-E1 / R3-J1): every edited cell is marked (EditMark, EditVal = value
              before the edit). Edited while no job is in progress (noJob = nothing executed since INIT, or
              DONE) -> NewCnt (new data); during a job (obstacle for the "drop location occupied" test)
              -> ObstCnt. Writing the cell back to EditVal removes the mark. With an empty hook outside
              RUNNING/PLANNING any edit invalidates the plan.
  REGION 3    JobActive := TRUE when a plan / MANUAL command (Src 1..3) completes.
  INIT step 3 listsNew := DB20/21 <> last lists;
              extE := NewCnt > 0 OR NOT HaveInit OR (listsNew AND ObstCnt > 0) OR ObstCnt >= 8 OR DB10/11 <> Snap;
              extE -> InitBay := DB (new yard), else DB := InitBay (repeat the loaded yard). Lists are always
              taken from DB20/DB21. JobActive / EditMark / NewCnt / ObstCnt cleared.
  INIT step 3 list validation = crane_model.init_validate (v1.5: duplicate only against ACCEPTED
              earlier entries, judge round 2 R2-E1).
  REGION 5    v1.6 (judge round 3 R3-E2) ACK re-target of a rejected SHIP put: among the free cells that pass
              the one-step balance rule, prefer the nearest one whose side keeps the remaining lists feasible
              in the preferred order (bit-parallel FtMask[0,0], ft00() below), first under the step rule,
              then under the relaxed ceiling BalD0; only if no such cell exists the nearest cell (v1.4 rule).

  python tools/fb10_init_model.py        -> FB10_INIT_RESULT failures=N

crane_stress.py calls selftest() (check E2) and retarget() (check T1).
"""
import copy
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402

BULK_CELLS = 8            # FB10 INIT: >= 8 distinct cells rewritten during a job = new yard


def _z():
    return [[0] * 12 for _ in range(4)]


class FB10:
    def __init__(self):
        self.Snap0, self.Snap1, self.InitBay0, self.InitBay1 = _z(), _z(), _z(), _z()
        self.HaveInit = self.ExtEdit = self.Initialized = False
        self.JobActive = False
        self.EditMark, self.EditNew, self.EditVal = [False] * 96, [False] * 96, [0] * 96
        self.NewCnt = self.ObstCnt = 0
        self.State = 0
        self.PrevState = 0
        self.OffState = 0
        self.Carried = 0
        self.PlanValid = False
        self.UList, self.LList = [0] * 48, [0] * 48
        self.W0, self.W1 = _z(), _z()

    def command_done(self, src=1):
        """REGION 3: a command with Src 1..3 (plan / MANUAL) completed."""
        if 1 <= src <= 3:
            self.JobActive = True

    def region_2a(self, DB10, DB11):
        extE = False
        noJob = (not self.JobActive or self.State == 6 or (self.State == 5 and self.PrevState == 6)
                 or (self.State == 0 and self.OffState == 6))
        if self.Initialized and self.State != 1:
            for x in range(4):
                for y in range(12):
                    for b, DB, Snap, W in ((0, DB10, self.Snap0, self.W0), (1, DB11, self.Snap1, self.W1)):
                        if DB[x][y] != Snap[x][y]:
                            k = b * 48 + x * 12 + y
                            if not self.EditMark[k]:
                                self.EditMark[k], self.EditVal[k], self.EditNew[k] = True, Snap[x][y], noJob
                                if noJob:
                                    self.NewCnt += 1
                                else:
                                    self.ObstCnt += 1
                            elif DB[x][y] == self.EditVal[k]:
                                self.EditMark[k] = False
                                if self.EditNew[k]:
                                    self.NewCnt -= 1
                                else:
                                    self.ObstCnt -= 1
                            extE = True
                            Snap[x][y] = DB[x][y]
                            W[x][y] = Snap[x][y]
                        elif W[x][y] != Snap[x][y]:
                            Snap[x][y] = W[x][y]
                            DB[x][y] = Snap[x][y]
            if extE and self.State in (0, 2, 4, 5, 6) and self.Carried == 0:
                self.PlanValid = False

    def init_step3(self, DB10, DB11, DB20, DB21):
        listsNew = any(DB20[i] != self.UList[i] or DB21[i] != self.LList[i] for i in range(48))
        extE = (self.NewCnt > 0 or not self.HaveInit or (listsNew and self.ObstCnt > 0)
                or self.ObstCnt >= BULK_CELLS)
        for x in range(4):
            for y in range(12):
                if DB10[x][y] != self.Snap0[x][y] or DB11[x][y] != self.Snap1[x][y]:
                    extE = True
        for x in range(4):
            for y in range(12):
                if extE:
                    self.InitBay0[x][y], self.InitBay1[x][y] = DB10[x][y], DB11[x][y]
                else:
                    DB10[x][y], DB11[x][y] = self.InitBay0[x][y], self.InitBay1[x][y]
        self.HaveInit, self.ExtEdit = True, False
        self.JobActive = False
        self.EditMark, self.EditNew, self.EditVal = [False] * 96, [False] * 96, [0] * 96
        self.NewCnt = self.ObstCnt = 0
        for x in range(4):
            for y in range(12):
                self.W0[x][y] = self.Snap0[x][y] = DB10[x][y]
                self.W1[x][y] = self.Snap1[x][y] = DB11[x][y]
        self.UList, self.LList = list(DB20), list(DB21)
        self.Carried = 0
        self.Initialized = True
        self.PlanValid = True
        self.State = 2


# ------------------------------------------------------------------ REGION 5 re-target (v1.6, R3-E2)
def _step_ok(d, d2, lim, ceil):
    return d2 <= lim or d2 <= d or (d > lim and d2 <= ceil)


def ft00(side_left, nl, S0, Y0, order, lim, ceil):
    """Bit-parallel FtMask: returns FtMask[0,0] (bit L = from 'nothing done, L ship containers in x 0..1,
    S0 on the ship, Y0 in the yard' every pending transfer can still be done in order mode 1/2).
    side_left[i] = pending unload i+1 (list order) stands in x 0..1. Same table as crane_plan.feas_table,
    computed with two row buffers and per-total move masks (FB10 temp ftK / ftPrev / ftCur)."""
    nu = len(side_left)
    K = [[0] * 49 for _ in range(6)]       # 0 valid, 1 end, 2 unload-left, 3 unload-right, 4 load-left, 5 load-right
    for tot in range(49):
        for L in range(25):
            R = tot - L
            if 0 <= R <= 24:
                b = 1 << L
                d = abs(L - R)
                K[0][tot] |= b
                if ceil == 0 or d <= lim:
                    K[1][tot] |= b
                if L >= 1 and _step_ok(d, abs(L - 1 - R), lim, ceil):
                    K[2][tot] |= b
                if R >= 1 and _step_ok(d, abs(L - R + 1), lim, ceil):
                    K[3][tot] |= b
                if L <= 23 and _step_ok(d, abs(L + 1 - R), lim, ceil):
                    K[4][tot] |= b
                if R <= 23 and _step_ok(d, abs(L - R - 1), lim, ceil):
                    K[5][tot] |= b
    prev = [0] * 49
    cur = [0] * 49
    for i in range(nu, -1, -1):
        for j in range(nl, -1, -1):
            tot = S0 - i + j
            m = 0
            if 0 <= tot <= 48:
                if i == nu and j == nl:
                    m = K[1][tot]
                else:
                    if i < nu and Y0 + i - j < 48:
                        if side_left[i]:
                            m |= K[2][tot] & ((prev[j] << 1) & 0xFFFFFFFF)
                        else:
                            m |= K[3][tot] & prev[j]
                    if j < nl and (order == 1 or i == nu):
                        m |= K[4][tot] & (cur[j + 1] >> 1)
                        m |= K[5][tot] & cur[j + 1]
            cur[j] = m
        prev = cur[:]
    return cur[0]


def retarget(W0, W1, crane, UList, UState, LList, LState, excl_load_idx, order, lim, curceil, BalD0,
             balmode=0, dstB=0, use_feas=True):
    """FB10 REGION 5: new destination of a rejected plan put (container on the hook, crane at `crane`).
    excl_load_idx = 1-based list index of the load on the hook (not pending any more after the put).
    Returns (x, y) or None (bit 7, MANUAL)."""
    G = W0 if dstB == 0 else W1
    BalL = sum(1 for x in range(2) for y in range(12) if W0[x][y])
    BalR = sum(1 for x in range(2, 4) for y in range(12) if W0[x][y])
    BalF = sum(1 for x in range(4) for y in range(6) if W0[x][y])
    BalA = sum(1 for x in range(4) for y in range(6, 12) if W0[x][y])
    ft0 = 0
    ftUse = False
    side, nl = [], 0
    if dstB == 0 and order > 0 and use_feas:
        for i in range(48):
            cid = UList[i]
            if cid and UState[i] == 0:
                for x in range(4):
                    for y in range(12):
                        if W0[x][y] == cid:
                            side.append(x <= 1)
                            break
                    else:
                        continue
                    break
        for i in range(48):
            cid = LList[i]
            if cid and LState[i] == 0 and i + 1 != excl_load_idx:
                if any(W1[x][y] == cid for x in range(4) for y in range(12)):
                    nl += 1
        S0 = BalL + BalR + 1
        Y0 = sum(1 for x in range(4) for y in range(12) if W1[x][y])
    for tr in (1, 2, 3):
        if tr < 3:
            if not (dstB == 0 and order > 0 and use_feas):
                continue
            if tr == 1:
                ceil = 0
            elif BalD0 > lim:
                ceil = BalD0
            else:
                continue
            ft0 = ft00(side, nl, S0, Y0, order, lim, ceil)
            ftUse = True
        else:
            ftUse = False
        bestT, best = 32767, None
        for x in range(4):
            for y in range(12):
                if G[x][y] != 0:
                    continue
                okBal = True
                if dstB == 0:
                    nL, nR, nF, nA = BalL, BalR, BalF, BalA
                    if x <= 1:
                        nL += 1
                    else:
                        nR += 1
                    if y <= 5:
                        nF += 1
                    else:
                        nA += 1
                    okBal = (abs(nL - nR) <= lim or abs(nL - nR) <= abs(BalL - BalR)
                             or (abs(BalL - BalR) > lim and abs(nL - nR) <= curceil))
                    if balmode == 1 and not (abs(nF - nA) <= lim or abs(nF - nA) <= abs(BalF - BalA)):
                        okBal = False
                    if okBal and ftUse and not (ft0 >> nL) & 1:
                        okBal = False
                if okBal:
                    t = max(abs(x - crane[0]) * 60, abs(y - crane[1]) * 23)
                    if t < bestT:
                        bestT, best = t, (x, y)
        if best is not None:
            return best
    return None


# ------------------------------------------------------------------ scenarios
def _lists(ds):
    return list(ds["unload"]) + [0] * (48 - len(ds["unload"])), list(ds["load"]) + [0] * (48 - len(ds["load"]))


def _run(fb, plan, DB10, DB11, ntr):
    for tr in plan[:ntr]:
        (sx, sy, sb), (dx, dy, db) = tr["src"], tr["dst"]
        g = (fb.W0, fb.W1)
        g[db][dx][dy], g[sb][sx][sy] = g[sb][sx][sy], 0
        fb.command_done()
        fb.region_2a(DB10, DB11)


def scenario(A, B, stop_state, change, ntr=3):
    """INIT with A, run ntr transfers, go to stop_state, then change the data (change = 'all' new yard +
    lists, 'yard' new yard only, 'lists' new lists only, 'obst' one obstacle cell written and removed again,
    'obst_keep' one obstacle left in place, 'none'), press POČETNO STANJE.
    Returns (World and DB10/11 == expected yard and lists == expected lists, description)."""
    fb = FB10()
    DB10, DB11 = copy.deepcopy(A["bay0"]), copy.deepcopy(A["bay1"])
    DB20, DB21 = _lists(A)
    fb.State = 1
    fb.init_step3(DB10, DB11, DB20, DB21)
    plan = cp.plan_fb(cp.build_state(A), {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])["plan"]
    fb.State = 3
    _run(fb, plan, DB10, DB11, ntr)
    fb.State = stop_state
    fb.region_2a(DB10, DB11)
    if change in ("all", "yard"):
        for x in range(4):
            for y in range(12):
                DB10[x][y], DB11[x][y] = B["bay0"][x][y], B["bay1"][x][y]
    if change in ("all", "lists"):
        DB20, DB21 = _lists(B)
    if change in ("obst", "obst_keep"):
        cell = next((x, y) for x in range(4) for y in range(12) if DB10[x][y] == 0)
        DB10[cell[0]][cell[1]] = 999
        fb.region_2a(DB10, DB11)
        if change == "obst":
            DB10[cell[0]][cell[1]] = 0
    for _ in range(3):
        fb.region_2a(DB10, DB11)
    plan_invalid = not fb.PlanValid
    fb.State = 1
    fb.init_step3(DB10, DB11, DB20, DB21)
    noJob = ntr == 0 or stop_state == 6
    if change in ("all", "yard"):
        want = B
    elif change == "obst_keep" and noJob:
        want = None                                   # the edited yard is the new data
    else:
        want = A
    wl = _lists(B) if change in ("all", "lists") else _lists(A)
    if want is None:
        ok = fb.W0 == DB10 and fb.W0 != A["bay0"]
    else:
        ok = fb.W0 == want["bay0"] and fb.W1 == want["bay1"] and DB10 == want["bay0"] and DB11 == want["bay1"]
    ok = ok and (fb.UList, fb.LList) == wl
    if change in ("all", "yard", "obst_keep") and stop_state != 3:
        ok = ok and plan_invalid
    return ok, "state=%d ntr=%d change=%s World=%s planInvalidated=%s" % (
        stop_state, ntr, change, "new" if fb.W0 == B["bay0"] else ("old" if fb.W0 == A["bay0"] else "other"),
        plan_invalid)


def scenario_load_on_hook(A):
    """R3-E1: obstacle written + removed during AUTO, STOP right after a lift (container on the hook),
    POČETNO STANJE -> the loaded data set (with that container) must come back."""
    fb = FB10()
    DB10, DB11 = copy.deepcopy(A["bay0"]), copy.deepcopy(A["bay1"])
    DB20, DB21 = _lists(A)
    fb.State = 1
    fb.init_step3(DB10, DB11, DB20, DB21)
    plan = cp.plan_fb(cp.build_state(A), {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])["plan"]
    fb.State = 3
    _run(fb, plan, DB10, DB11, 2)
    dx, dy, db = plan[2]["dst"]
    (DB10, DB11)[db][dx][dy] = 999
    fb.region_2a(DB10, DB11)
    (DB10, DB11)[db][dx][dy] = 0
    fb.region_2a(DB10, DB11)
    _run(fb, plan[2:], DB10, DB11, 3)
    sx, sy, sb = plan[5]["src"]
    g = (fb.W0, fb.W1)
    fb.Carried, g[sb][sx][sy] = g[sb][sx][sy], 0
    fb.command_done()
    fb.region_2a(DB10, DB11)
    fb.State = 4
    fb.region_2a(DB10, DB11)
    fb.State = 1
    fb.init_step3(DB10, DB11, DB20, DB21)
    return fb.W0 == A["bay0"] and fb.W1 == A["bay1"]


def selftest():
    A = cm.load_dataset(os.path.join(HERE, "crane_data", "rand_05.json"))
    B = cm.load_dataset(os.path.join(HERE, "crane_data", "rand_11.json"))
    fails = []
    for s in (0, 2, 3, 4, 5, 6):
        for ch in ("all", "yard", "lists", "obst", "obst_keep", "none"):
            for ntr in ((0, 3) if s in (2, 6) else (3,)):
                ok, d = scenario(A, B, s, ch, ntr)
                if not ok:
                    fails.append("E2 " + d)
    if not scenario_load_on_hook(A):
        fails.append("E2 obstacle + cleanup, STOP with a load, POČETNO STANJE: loaded data not restored")
    # R2-E1: a bogus unload entry naming a yard container must not kill the valid load entry
    for name in ("r2_elimination_bogus_unload_kills_load", "r2_elimination_rand05_bogus_unload"):
        p = os.path.join(HERE, "judge_sets", name + ".json")
        if os.path.exists(p):
            ds = cm.load_dataset(p)
            iv = cm.init_validate(ds)
            for j, v in enumerate(ds["load"]):
                if v and cm.valid_id(v) and cm.World(ds["bay0"], ds["bay1"]).find(1, v) is not None \
                        and v not in [ds["load"][q] for q in range(j)] and iv["LState"][j] != 0:
                    fails.append("E1 %s load entry %d (%d) rejected" % (name, j + 1, v))
    # R3-E2: bit-parallel ft00 == crane_plan.feas_table[0][0] on random count-level instances
    rng = random.Random(5)
    for t in range(400):
        nu, nl = rng.randint(0, 20), rng.randint(0, 20)
        side = [rng.random() < 0.5 for _ in range(nu)]
        S0 = rng.randint(0, 48)
        Y0 = rng.randint(0, 47)
        order = rng.choice((1, 2))
        ceil = rng.choice((0, 0, 6, 8, 11))
        PU = [type("S", (), {"pos": ((0 if s else 2), 0, 0)})() for s in side]
        PL = [None] * nl
        b0 = _z()
        b1 = _z()
        for k in range(min(S0, 48)):
            b0[k // 12][k % 12] = 100 + k
        for k in range(Y0):
            b1[k // 12][k % 12] = 500 + k
        ref = cp.feas_table(b0, b1, PU, PL, order, 5, ceil)[0][0]
        got = ft00(side, nl, S0, Y0, order, 5, ceil)
        if ref != got:
            fails.append("T0 ft00 mismatch nu=%d nl=%d S0=%d Y0=%d order=%d ceil=%d ref=%x got=%x" % (
                nu, nl, S0, Y0, order, ceil, ref, got))
            break
    return fails


if __name__ == "__main__":
    f = selftest()
    for e in f:
        print("FAIL", e)
    print("FB10_INIT_RESULT failures=%d" % len(f))
    sys.exit(1 if f else 0)


# ------------------------------------------------------------------ check T1 (crane_stress, judge round 3 R3-E2)
def retarget_cases(ds, obst=998):
    """For every ship put of the PLC order-1 plan: transfers 1..k-1 done, container k lifted, crane at its
    planned drop cell, an obstacle written there, POTVRDA -> FB10 re-target (retarget()). Returns
    (cases, needless, inherent): needless = the chosen cell makes the list order infeasible (step rule and
    relaxed d0) although another balance-safe free cell keeps it feasible; inherent = no cell keeps it."""
    st0 = cp.build_state(ds)
    if st0["init"]["blocking"]:
        return 0, [], 0
    d0 = st0["d0"]
    res = cp.plan_fb(st0, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])
    if res["err"] != 0 or res["order"] != 1:
        return 0, [], 0
    curceil = res["cfg"].get("ceil", 0)
    plan = res["plan"]
    UL, LL = _lists(ds)
    g = [[c[:] for c in ds["bay0"]], [c[:] for c in ds["bay1"]]]
    cases, needless, inherent = 0, [], 0

    def feas(g2, rest):
        pu = sorted((t["list_idx"], t["id"]) for t in rest if t["kind"] == 1)
        pl = sorted((t["list_idx"], t["id"]) for t in rest if t["kind"] == 2)
        s = {"bay0": g2[0], "bay1": g2[1], "PU": pu, "PL": pl}
        return cp.order_feasible(s, 1, 5, 0) or (d0 > 5 and cp.order_feasible(s, 1, 5, d0))

    for k, tr in enumerate(plan):
        (sx, sy, sb), (dx, dy, db) = tr["src"], tr["dst"]
        if db == 0:
            gk = [[c[:] for c in g[0]], [c[:] for c in g[1]]]
            cid = gk[sb][sx][sy]
            gk[sb][sx][sy] = 0
            gk[0][dx][dy] = obst
            rest = plan[k + 1:]
            US = [1] * 48
            LS = [1] * 48
            for t in rest:
                (US if t["kind"] == 1 else LS)[t["list_idx"] - 1] = 0
            LS[tr["list_idx"] - 1] = 0
            choice = retarget(gk[0], gk[1], (dx, dy), UL, US, LL, LS, tr["list_idx"], 1, 5, curceil, d0)
            if choice is not None:
                cases += 1
                g2 = [[c[:] for c in gk[0]], [c[:] for c in gk[1]]]
                g2[0][choice[0]][choice[1]] = cid
                if not feas(g2, rest):
                    L, R = cm.lr(gk[0])
                    alt = []
                    for x in range(4):
                        for y in range(12):
                            if gk[0][x][y] or (x, y) == choice:
                                continue
                            nL, nR = (L + 1, R) if x <= 1 else (L, R + 1)
                            if not cm.step_ok(L, R, nL, nR, 5, curceil):
                                continue
                            g3 = [[c[:] for c in gk[0]], [c[:] for c in gk[1]]]
                            g3[0][x][y] = cid
                            if feas(g3, rest):
                                alt.append((x, y))
                    if alt:
                        needless.append("%s transfer %d id %d: cell %s breaks the order, %s keep it" % (
                            ds.get("name", "?"), k + 1, cid, choice, alt[:3]))
                    else:
                        inherent += 1
        g[db][dx][dy] = g[sb][sx][sy]
        g[sb][sx][sy] = 0
    return cases, needless, inherent
