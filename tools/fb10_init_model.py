"""fb10_init_model.py - Python transliteration of the FB10 data-load paths (v1.5).

Covers the parts of FB10 "Crane_Control" (tia-src/21_FB_CraneControl.scl) that the planner mirrors do
not cover:
  REGION 2a   DB10/DB11 <-> World mirror with Snap0/Snap1. v1.5: an external edit sets ExtEdit in EVERY
              state (INIT excluded) and, with an empty hook outside RUNNING/PLANNING, PlanValid := FALSE
              (judge round 2 R2-E2 / R2-J3).
  INIT step 3 extE := ExtEdit OR NOT HaveInit OR DB10/11 <> Snap OR (v1.5) DB20/21 <> last lists;
              extE -> InitBay := DB (new data), else DB := InitBay (repeat the same data set).
  INIT step 3 list validation = crane_model.init_validate (v1.5: duplicate only against ACCEPTED
              earlier entries, judge round 2 R2-E1).

  python tools/fb10_init_model.py        -> FB10_INIT_RESULT failures=N

crane_stress.py calls selftest() (check E2).
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402


def _z():
    return [[0] * 12 for _ in range(4)]


class FB10:
    def __init__(self):
        self.Snap0, self.Snap1, self.InitBay0, self.InitBay1 = _z(), _z(), _z(), _z()
        self.HaveInit = self.ExtEdit = self.Initialized = False
        self.State = 0
        self.Carried = 0
        self.PlanValid = False
        self.UList, self.LList = [0] * 48, [0] * 48
        self.W0, self.W1 = _z(), _z()

    def region_2a(self, DB10, DB11):
        extE = False
        if self.Initialized and self.State != 1:
            for x in range(4):
                for y in range(12):
                    for DB, Snap, W in ((DB10, self.Snap0, self.W0), (DB11, self.Snap1, self.W1)):
                        if DB[x][y] != Snap[x][y]:
                            Snap[x][y] = DB[x][y]
                            W[x][y] = Snap[x][y]
                            self.ExtEdit = True
                            extE = True
                        elif W[x][y] != Snap[x][y]:
                            Snap[x][y] = W[x][y]
                            DB[x][y] = Snap[x][y]
            if extE and self.State in (0, 2, 4, 5, 6) and self.Carried == 0:
                self.PlanValid = False

    def init_step3(self, DB10, DB11, DB20, DB21):
        extE = self.ExtEdit or not self.HaveInit
        for i in range(48):
            if DB20[i] != self.UList[i] or DB21[i] != self.LList[i]:
                extE = True
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
        for x in range(4):
            for y in range(12):
                self.W0[x][y] = self.Snap0[x][y] = DB10[x][y]
                self.W1[x][y] = self.Snap1[x][y] = DB11[x][y]
        self.UList, self.LList = list(DB20), list(DB21)
        self.Initialized = True
        self.PlanValid = True
        self.State = 2


def _lists(ds):
    return list(ds["unload"]) + [0] * (48 - len(ds["unload"])), list(ds["load"]) + [0] * (48 - len(ds["load"]))


def scenario(A, B, stop_state, change):
    """INIT with A, run 3 transfers, go to stop_state, then load B (change = 'all' / 'yard' / 'none'),
    press POČETNO STANJE. Returns (World == expected, description)."""
    fb = FB10()
    DB10, DB11 = copy.deepcopy(A["bay0"]), copy.deepcopy(A["bay1"])
    DB20, DB21 = _lists(A)
    fb.State = 1
    fb.init_step3(DB10, DB11, DB20, DB21)
    res = cp.plan_fb(cp.build_state(A), {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])
    fb.State = 3
    for tr in res["plan"][:3]:
        (sx, sy, sb), (dx, dy, db) = tr["src"], tr["dst"]
        g = (fb.W0, fb.W1)
        g[db][dx][dy], g[sb][sx][sy] = g[sb][sx][sy], 0
        fb.region_2a(DB10, DB11)
    fb.State = stop_state
    fb.region_2a(DB10, DB11)
    if change in ("all", "yard"):
        for x in range(4):
            for y in range(12):
                DB10[x][y], DB11[x][y] = B["bay0"][x][y], B["bay1"][x][y]
    if change == "all":
        DB20, DB21 = _lists(B)
    for _ in range(3):
        fb.region_2a(DB10, DB11)
    plan_invalid = not fb.PlanValid
    fb.State = 1
    fb.init_step3(DB10, DB11, DB20, DB21)
    want = B if change in ("all", "yard") else A
    ok = fb.W0 == want["bay0"] and fb.W1 == want["bay1"] and DB10 == want["bay0"] and DB11 == want["bay1"]
    if change != "none" and stop_state != 3:
        ok = ok and plan_invalid
    return ok, "state=%d change=%s World=%s planInvalidated=%s" % (
        stop_state, change, "new" if fb.W0 == B["bay0"] else ("old" if fb.W0 == A["bay0"] else "other"), plan_invalid)


def selftest():
    A = cm.load_dataset(os.path.join(HERE, "crane_data", "rand_05.json"))
    B = cm.load_dataset(os.path.join(HERE, "crane_data", "rand_11.json"))
    fails = []
    for s in (0, 2, 3, 4, 5, 6):
        for ch in ("all", "yard", "none"):
            ok, d = scenario(A, B, s, ch)
            if not ok:
                fails.append("E2 " + d)
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
    return fails


if __name__ == "__main__":
    f = selftest()
    for e in f:
        print("FAIL", e)
    print("FB10_INIT_RESULT failures=%d" % len(f))
    sys.exit(1 if f else 0)
