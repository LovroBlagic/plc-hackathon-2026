"""crane_model.py - reference model for the TIA container-crane task (CONTRACT v1.0).

Integer deciseconds everywhere (1 ds = 0.1 s). Standard library only.

Contents
  * cost model (CONTRACT 4.1): G(), move_cost(), W()
  * FB1 emulator (commands 1/2/3/10), parameterised by mmode 0/1/2
  * World (grids + Carried), balance (4.3), step rule, reachability
  * CheckCmd emulation (1.4) with the contract return codes (100 = balance / bit 0)
  * INIT list validation (3.2 step 4) -> UState/LState/N/alarm bits
  * J computation

Grid convention: grid[x][y], x 0..3, y 0..11; bay0 = ship (DB10), bay1 = yard (DB11).
FB1 findings (TEAM_NOTES.md) were not available when this was written: defaults
are the spec rule (one-call completion, CfgMMode 0, max(60*dG, 23*dy) ds).
"""

import copy
import json

NX, NY = 4, 12
LIFT_T = 200
PUT_T = 200
M_WEIGHT = 190          # 1 manipulation == 19 s == 190 ds  (J = (T_s + 19 M) / (152 N))
TAV_S = 76.0
BAL_LIMIT = 5

# alarm bits (CONTRACT 3.3)
BIT_BAL, BIT_PICK_EMPTY, BIT_DROP_OCC = 0, 1, 2
BIT_U_NOTFOUND, BIT_L_NOTFOUND, BIT_INVALID, BIT_DUP = 3, 4, 5, 6
BIT_CAPACITY, BIT_PLAN, BIT_BADCMD = 7, 8, 9
BIT_CARRYING, BIT_EMPTYHOOK = 11, 12


# ---------------------------------------------------------------- cost model
def G(x, b):
    """Global column: Bay0 X = x + 6, Bay1 X = x."""
    return x + 6 if b == 0 else x


def move_cost(x0, y0, b0, x1, y1, b1, mmode=0):
    """(T_ds, M) of a move. Mirrors FC20 "Crane_MoveCost"."""
    if x0 == x1 and y0 == y1 and b0 == b1:
        return 0, 0
    dg = abs(G(x1, b1) - G(x0, b0))
    dy = abs(y1 - y0)
    t = max(60 * dg, 23 * dy)
    if mmode == 0:
        m = (1 if dg != 0 else 0) + (1 if dy != 0 else 0)
    elif mmode == 1:
        m = (1 if x1 != x0 else 0) + (1 if dy != 0 else 0)
    elif mmode == 2:
        m = 1
    else:
        raise ValueError("mmode must be 0/1/2")
    return t, m


def W(p0, p1, mmode=0):
    """Weighted cost T + 190*M of moving between positions (x, y, bay)."""
    t, m = move_cost(p0[0], p0[1], p0[2], p1[0], p1[1], p1[2], mmode)
    return t + M_WEIGHT * m


def J(T_ds, M, N):
    if N <= 0:
        return 0.0
    return 0.5 * (T_ds / 10.0) / (TAV_S * N) + 0.5 * M / (4.0 * N)


# ---------------------------------------------------------------- FB1 emulator
class FB1:
    """Emulates FB1 "Crane_manipulation" (spec rule; one-call completion)."""

    def __init__(self, mmode=0):
        self.mmode = mmode
        self.reset()

    def reset(self):
        self.x, self.y, self.bay = 0, 0, 1
        self.M = 0
        self.T_ds = 0

    def pos(self):
        return (self.x, self.y, self.bay)

    def command(self, cmd, x=0, y=0, bay=0):
        """Execute one command; returns (dT_ds, dM)."""
        if cmd == 10:
            self.reset()
            return 0, 0
        if cmd in (1, 2):
            self.T_ds += LIFT_T if cmd == 1 else PUT_T
            self.M += 1
            return (LIFT_T if cmd == 1 else PUT_T), 1
        if cmd == 3:
            t, m = move_cost(self.x, self.y, self.bay, x, y, bay, self.mmode)
            self.x, self.y, self.bay = x, y, bay
            self.T_ds += t
            self.M += m
            return t, m
        return 0, 0  # 0 = nothing


# ---------------------------------------------------------------- world / balance
def empty_grid():
    return [[0] * NY for _ in range(NX)]


class World:
    def __init__(self, bay0, bay1):
        self.g = [copy.deepcopy(bay0), copy.deepcopy(bay1)]
        self.carried = 0

    def cell(self, b, x, y):
        return self.g[b][x][y]

    def find(self, b, cid):
        """First match scanning x 0..3 outer, y 0..11 inner."""
        grid = self.g[b]
        for x in range(NX):
            for y in range(NY):
                if grid[x][y] == cid:
                    return (x, y, b)
        return None

    def occupied(self, b):
        return sum(1 for x in range(NX) for y in range(NY) if self.g[b][x][y] != 0)


def lr(bay0):
    L = sum(1 for x in (0, 1) for y in range(NY) if bay0[x][y] != 0)
    R = sum(1 for x in (2, 3) for y in range(NY) if bay0[x][y] != 0)
    return L, R


def fa(bay0):
    F = sum(1 for x in range(NX) for y in range(0, 6) if bay0[x][y] != 0)
    A = sum(1 for x in range(NX) for y in range(6, 12) if bay0[x][y] != 0)
    return F, A


def step_ok(a, b, a2, b2, lim=BAL_LIMIT):
    """Step rule: OK iff |a2-b2| <= lim or |a2-b2| <= |a-b|."""
    d2 = abs(a2 - b2)
    return d2 <= lim or d2 <= abs(a - b)


def reachable(L2, R2, uL, uR, n, lim=BAL_LIMIT):
    L0 = L2 - uL
    R0 = R2 - uR
    FL = 24 - L0
    FR = 24 - R0
    lo = max(0, n - FR)
    hi = min(n, FL)
    D0 = L0 - R0 - n
    return lo <= hi and D0 + 2 * lo <= lim and D0 + 2 * hi >= -lim


# ---------------------------------------------------------------- CheckCmd (FC10)
def check_cmd(world, cmd, x, y, bay, crane, lim=BAL_LIMIT, balmode=0):
    """Returns 0 OK, 100 = balance (bit 0), else alarm bit number.
    For lift/put the cell checked is the crane position (crane = (x, y, bay))."""
    if cmd == 3:
        if 0 <= x <= 3 and 0 <= y <= 11 and bay in (0, 1):
            return 0
        return BIT_BADCMD
    if cmd == 10:
        return 0
    if cmd not in (1, 2):
        return BIT_BADCMD
    cx, cy, cb = crane
    if cmd == 1:
        if world.carried != 0:
            return BIT_CARRYING
        if world.g[cb][cx][cy] == 0:
            return BIT_PICK_EMPTY
        delta = -1
    else:
        if world.carried == 0:
            return BIT_EMPTYHOOK
        if world.g[cb][cx][cy] != 0:
            return BIT_DROP_OCC
        delta = +1
    if cb == 0:
        L, R = lr(world.g[0])
        L2, R2 = (L + delta, R) if cx <= 1 else (L, R + delta)
        if not step_ok(L, R, L2, R2, lim):
            return 100
        if balmode == 1:
            F, A = fa(world.g[0])
            F2, A2 = (F + delta, A) if cy <= 5 else (F, A + delta)
            if not step_ok(F, A, F2, A2, lim):
                return 100
    return 0


def apply_cmd(world, cmd, crane):
    """World effect of a completed lift/put at the crane position (OB30 step 2)."""
    cx, cy, cb = crane
    if cmd == 1:
        world.carried = world.g[cb][cx][cy]
        world.g[cb][cx][cy] = 0
    elif cmd == 2:
        world.g[cb][cx][cy] = world.carried
        world.carried = 0


# ---------------------------------------------------------------- dataset / INIT
def load_dataset(path):
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    for k in ("bay0", "bay1"):
        assert len(d[k]) == NX and all(len(c) == NY for c in d[k]), k
    for k in ("unload", "load"):
        assert len(d[k]) == 48, k
    return d


def valid_id(i):
    return 100 <= i <= 999


def init_validate(ds, lim=BAL_LIMIT):
    """CONTRACT 3.2 step 4.  Returns dict with UList/UState/LList/LState/N/alarm bits.
    Ordering interpretation: UList 1..48 first, then LList 1..48; "already seen"
    means the same non-zero ID appeared in an earlier entry (any state)."""
    bay0, bay1 = ds["bay0"], ds["bay1"]
    bits = set()
    seen_cells = {}
    for b, grid in ((0, bay0), (1, bay1)):
        for x in range(NX):
            for y in range(NY):
                v = grid[x][y]
                if v == 0:
                    continue
                if not valid_id(v):
                    bits.add(BIT_INVALID)
                if v in seen_cells:
                    bits.add(BIT_DUP)
                seen_cells[v] = True
    w = World(bay0, bay1)
    UList, LList = list(ds["unload"]), list(ds["load"])
    N = sum(1 for v in UList if v != 0) + sum(1 for v in LList if v != 0)
    seen = set()
    UState, LState = [0] * 48, [0] * 48
    for lst, st, bay, nbit in ((UList, UState, 0, BIT_U_NOTFOUND), (LList, LState, 1, BIT_L_NOTFOUND)):
        for i, v in enumerate(lst):
            if v == 0:
                st[i] = 2
            elif not valid_id(v):
                st[i] = 2
                bits.add(BIT_INVALID)
            elif v in seen:
                st[i] = 2
                bits.add(BIT_DUP)
            elif w.find(bay, v) is None:
                st[i] = 2
                bits.add(nbit)
            else:
                st[i] = 0
            if v != 0:
                seen.add(v)
    pu = sum(1 for s in UState if s == 0)
    pl = sum(1 for s in LState if s == 0)
    if w.occupied(1) - pl + pu > 48 or w.occupied(0) - pu + pl > 48:
        bits.add(BIT_CAPACITY)
    L, R = lr(bay0)
    if abs(L - R) > lim:
        bits.add(BIT_BAL)
    return {"UList": UList, "UState": UState, "LList": LList, "LState": LState,
            "N": N, "bits": sorted(bits), "blocking": BIT_CAPACITY in bits}
