"""r2_elim_init_restore.py - judge round 2 (elimination): POČETNO STANJE reloads the OLD data set.

Line-by-line transliteration of FB10 "Crane_Control" (tia-src/21_FB_CraneControl.scl):
  REGION 2a (lines 152-177): DB10/DB11 <-> World mirror with Snap0/Snap1; ExtEdit only in states 0/2/6
  INIT step 3 (lines 643-679): extE := ExtEdit OR NOT HaveInit OR (DB <> Snap); extE -> InitBay := DB,
                               else DB := InitBay (restore the previous data set); World := DB
Scenario (jury loads the competition data while the system is not OFF/READY/DONE):
  1. INIT with data set A, START, a few transfers, STOP (state 4 PAUSED) - or an alarm test (state 5)
  2. jury writes data set B into DB10/DB11 (watch table / download with re-initialisation, PLC in RUN)
  3. jury presses POČETNO STANJE
Expected (spec 2.1: "učitavanje stanja iz DB10 i DB11"): World = B.  Team: DB10/DB11 := A again, World = A,
while DB20/DB21 (re-read at every INIT) already hold B's lists -> bits 3/4, B's containers never moved.

  python tools/judge_sets/r2_elim_init_restore.py
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402


class FB10:
    def __init__(self):
        z = lambda: [[0] * 12 for _ in range(4)]   # noqa: E731
        self.Snap0, self.Snap1, self.InitBay0, self.InitBay1 = z(), z(), z(), z()
        self.HaveInit = self.ExtEdit = self.Initialized = False
        self.State = 0
        self.W0, self.W1 = z(), z()          # "World".Bay0 / Bay1

    def region_2a(self, DB10, DB11):
        if self.Initialized and self.State != 1:
            for x in range(4):
                for y in range(12):
                    for DB, Snap, W in ((DB10, self.Snap0, self.W0), (DB11, self.Snap1, self.W1)):
                        if DB[x][y] != Snap[x][y]:
                            Snap[x][y] = DB[x][y]
                            W[x][y] = Snap[x][y]
                            if self.State in (0, 2, 6):
                                self.ExtEdit = True
                        elif W[x][y] != Snap[x][y]:
                            Snap[x][y] = W[x][y]
                            DB[x][y] = Snap[x][y]

    def init_step3(self, DB10, DB11):
        extE = self.ExtEdit or not self.HaveInit
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
        self.Initialized = True
        self.State = 2


def scenario(A, B, stop_state):
    fb = FB10()
    DB10, DB11 = copy.deepcopy(A["bay0"]), copy.deepcopy(A["bay1"])
    fb.State = 1
    fb.init_step3(DB10, DB11)                                  # INIT with data set A -> READY
    st = cp.build_state(A)
    res = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])
    fb.State = 3                                               # START
    for tr in res["plan"][:3]:                                 # OB30 executes 3 transfers
        (sx, sy, sb), (dx, dy, db) = tr["src"], tr["dst"]
        g = (fb.W0, fb.W1)
        g[db][dx][dy], g[sb][sx][sy] = g[sb][sx][sy], 0
        fb.region_2a(DB10, DB11)
    fb.State = stop_state                                      # STOP -> 4 PAUSED, or an alarm test -> 5 ALARM
    fb.region_2a(DB10, DB11)
    for x in range(4):                                         # jury loads data set B into DB10 / DB11
        for y in range(12):
            DB10[x][y], DB11[x][y] = B["bay0"][x][y], B["bay1"][x][y]
    for _ in range(3):                                         # a few OB1 cycles
        fb.region_2a(DB10, DB11)
    fb.State = 1                                               # POČETNO STANJE
    fb.init_step3(DB10, DB11)
    loadedB = fb.W0 == B["bay0"] and fb.W1 == B["bay1"]
    loadedA = fb.W0 == A["bay0"] and fb.W1 == A["bay1"]
    iv = cm.init_validate({"bay0": fb.W0, "bay1": fb.W1, "unload": B["unload"], "load": B["load"]})
    skipped = sum(1 for s, v in zip(iv["UState"] + iv["LState"], B["unload"] + B["load"]) if v and s == 2)
    print("state at data load=%d  World after POCETNO STANJE: B(new)=%s A(old)=%s  DB10==B:%s  "
          "B list entries skipped=%d of %d  alarm bits=%s" % (
              stop_state, loadedB, loadedA, DB10 == B["bay0"], skipped,
              sum(1 for v in B["unload"] + B["load"] if v), iv["bits"]))
    return not loadedB


def main():
    A = cm.load_dataset(os.path.join(HERE, "..", "crane_data", "rand_05.json"))
    B = cm.load_dataset(os.path.join(HERE, "..", "crane_data", "rand_11.json"))
    bad = 0
    for s in (6, 2, 0, 4, 5):
        bad += 1 if scenario(A, B, s) else 0
    print("R2_INIT_RESTORE_RESULT wrong_data_after_initial_state=%d (states 4 PAUSED and 5 ALARM)" % bad)


if __name__ == "__main__":
    main()
