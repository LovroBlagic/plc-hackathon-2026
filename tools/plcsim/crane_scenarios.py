"""crane_scenarios.py - interactive HUMAN_STEPS 1.x checks on PLCSIM by tag writes (SimHost.exe must run).

  python tools/plcsim/crane_scenarios.py [--only semi,stopstart,...] [--data tools/judge_sets/r1_jury_fig1_half.json]

Every scenario starts with: SwOn, load data set, POCETNO STANJE, READY. Prints one CHECK line per assertion and
SCEN_RESULT fails=N at the end; JSON log in tools/plcsim/results/scenarios.json.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import crane_sim_test as T  # noqa: E402
from simclient import Sim  # noqa: E402

LOG = []
FAILS = [0]


def check(name, ok, detail=""):
    LOG.append({"check": name, "ok": bool(ok), "detail": detail})
    if not ok:
        FAILS[0] += 1
    print("CHECK %-58s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
    sys.stdout.flush()


def st(s):
    return int(s.r("HMI_IF.State"))


def M(s):
    return int(s.r("number_of_manipulations"))


def aw(s):
    return int(s.r("HMI_IF.AlarmWord"))


def wait(cond, timeout, period=0.2):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = cond()
        if v:
            return v
        time.sleep(period)
    return None


def fresh(s, ds, mode="BtnAuto"):
    if st(s) in (3, 7):
        T.press(s, "BtnStop")
        time.sleep(1.5)
    if st(s) == 5:
        T.press(s, "BtnAck")
        time.sleep(1.5)
    s.w("HMI_IF.SwOn", 1)
    time.sleep(1.2)
    T.load_data(s, ds)
    time.sleep(1.2)
    T.press(s, "BtnInit")
    wait(lambda: st(s) in (1, 7), 5, 0.05)
    wait(lambda: st(s) == 2, 180)
    time.sleep(1.5)
    T.press(s, mode)
    time.sleep(0.6)


def finish(s, timeout=400):
    return wait(lambda: st(s) in (5, 6) and st(s), timeout, 0.3)


def sc_semi(s, ds, mod):
    fresh(s, ds, "BtnSemi")
    check("semi: mode = SEMI (2)", int(s.r("HMI_IF.Mode")) == 2, "Mode=%s" % s.r("HMI_IF.Mode"))
    m0 = M(s)
    T.press(s, "BtnStep")                      # click before START = START + 1 step
    wait(lambda: M(s) > m0, 30)
    time.sleep(3.5)
    m1 = M(s)
    check("semi: click before START executes exactly 1 command", m1 == m0 + 1, "M %d -> %d, State=%d" % (m0, m1, st(s)))
    ok = True
    for i in range(4):
        mb = M(s)
        T.press(s, "BtnStep")
        wait(lambda: M(s) > mb, 30)
        time.sleep(2.5)
        ok = ok and M(s) == mb + 1
    check("semi: 4 more clicks = 4 commands", ok, "M=%d" % M(s))
    time.sleep(3)
    check("semi: no progress without a click", M(s) == m0 + 5, "M=%d StepWaiting=%s" % (M(s), s.r("HMI_IF.StepWaiting")))
    T.press(s, "BtnAuto")
    time.sleep(0.6)
    T.press(s, "BtnStart")
    f = finish(s)
    check("semi->auto: finishes DONE, M/T = model", f == 6 and M(s) == mod["M"] and int(round(float(s.r("time")) * 10)) == mod["T_ds"],
          "state=%s M=%d T=%s model M=%d T=%.1f" % (f, M(s), s.r("time"), mod["M"], mod["T_ds"] / 10.0))


def sc_stopstart(s, ds, mod):
    fresh(s, ds)
    T.press(s, "BtnStart")
    wait(lambda: int(s.r("HMI_IF.Carried")) != 0, 120)
    T.press(s, "BtnStop")
    time.sleep(2.5)
    m0 = M(s)
    state_p = st(s)
    time.sleep(3)
    check("stop: after a lift -> PAUSED (4), crane holds", state_p == 4 and M(s) == m0, "state=%d M %d->%d Carried=%s" % (state_p, m0, M(s), s.r("HMI_IF.Carried")))
    T.press(s, "BtnStart")
    f = finish(s)
    check("stop/start: resumes to DONE, M/T = model", f == 6 and M(s) == mod["M"] and int(round(float(s.r("time")) * 10)) == mod["T_ds"],
          "state=%s M=%d T=%s model M=%d T=%.1f" % (f, M(s), s.r("time"), mod["M"], mod["T_ds"] / 10.0))


def sc_onoff(s, ds, mod):
    fresh(s, ds)
    T.press(s, "BtnStart")
    wait(lambda: M(s) >= 6, 60)
    s.w("HMI_IF.SwOn", 0)
    time.sleep(3)
    m0 = M(s)
    s0 = st(s)
    time.sleep(2)
    check("off: State OFF (0), no commands", s0 == 0 and M(s) == m0, "state=%d M=%d LampOff=%s" % (s0, M(s), s.r("HMI_IF.LampOff")))
    s.w("HMI_IF.SwOn", 1)
    time.sleep(3)
    s1 = st(s)
    check("on: leaves OFF (READY/PAUSED, not running by itself)", s1 in (2, 4), "state=%d LampReady=%s" % (s1, s.r("HMI_IF.LampReady")))
    T.press(s, "BtnStart")
    f = finish(s)
    check("off/on: START finishes DONE", f == 6, "state=%s M=%d T=%s TrDone=%s/%s" % (f, M(s), s.r("time"), s.r("HMI_IF.TrDone"), s.r("HMI_IF.TrTotal")))


def man(s, cmd, x, y, bay):
    s.wb([("HMI_IF.ManCmd", cmd), ("HMI_IF.ManX", x), ("HMI_IF.ManY", y), ("HMI_IF.ManBay", bay)])
    m0 = M(s)
    T.press(s, "BtnManExec")
    wait(lambda: M(s) > m0 or aw(s) & 0x7FFF, 6)
    time.sleep(1.5)
    return M(s) - m0, aw(s)


def ack(s):
    T.press(s, "BtnAck")
    time.sleep(1.5)


def sc_manual(s, ds, mod):
    fresh(s, ds, "BtnManual")
    check("manual: mode = MANUAL (3)", int(s.r("HMI_IF.Mode")) == 3, "Mode=%s" % s.r("HMI_IF.Mode"))
    dm, a = man(s, 3, 1, 1, 2)
    check("manual: move to bay 2 rejected, alarm bit 9", dm == 0 and a & (1 << 9), "dM=%d AlarmWord=%d AlarmId? hist0=%s" % (dm, a, s.r("HMI_IF.AlarmHist[0]")))
    ack(s)
    # an empty cell and an occupied cell of bay 1
    b1 = ds["bay1"]
    empty = next((x, y) for x in range(4) for y in range(12) if b1[x][y] == 0)
    full = [(x, y) for x in range(4) for y in range(12) if b1[x][y] != 0]
    dm, a = man(s, 3, empty[0], empty[1], 1)
    check("manual: move to empty yard cell executes", dm == 1, "dM=%d pos=%s,%s,%s" % (dm, s.r("x_position"), s.r("y_position"), s.r("bay_ID")))
    dm, a = man(s, 1, empty[0], empty[1], 1)
    check("manual: lift on empty cell rejected, alarm bit 1", dm == 0 and a & (1 << 1), "dM=%d AlarmWord=%d state=%d" % (dm, a, st(s)))
    ack(s)
    check("manual: ACK clears bit 1", not aw(s) & 2, "AlarmWord=%d state=%d" % (aw(s), st(s)))
    fx, fy = full[0]
    man(s, 3, fx, fy, 1)
    dm, a = man(s, 1, fx, fy, 1)
    check("manual: lift on occupied cell executes", dm == 1 and int(s.r("HMI_IF.Carried")) == b1[fx][fy], "dM=%d Carried=%s" % (dm, s.r("HMI_IF.Carried")))
    gx, gy = full[1]
    man(s, 3, gx, gy, 1)
    dm, a = man(s, 2, gx, gy, 1)
    check("manual: put on occupied cell rejected, alarm bit 2", dm == 0 and a & (1 << 2), "dM=%d AlarmWord=%d" % (dm, a))
    ack(s)
    dm, a = man(s, 2, fx, fy, 1) if False else (None, None)
    man(s, 3, fx, fy, 1)
    dm, a = man(s, 2, fx, fy, 1)
    check("manual: put back on its own (now empty) cell executes", dm == 1 and int(s.r(T.B1 % (fx, fy))) == b1[fx][fy],
          "dM=%d DB11[%d,%d]=%s" % (dm, fx, fy, s.r(T.B1 % (fx, fy))))
    dm, a = man(s, 10, 0, 0, 0)
    check("manual: reset (10) with empty hook executes", dm != 0 or (int(s.r("x_position")), int(s.r("bay_ID"))) == (0, 1),
          "M=%d pos=%s,%s,%s" % (M(s), s.r("x_position"), s.r("y_position"), s.r("bay_ID")))


def sc_obstacle(s, ds, mod):
    """1.7 / 1.15: write 999 into the next SHIP drop cell while the load is on the hook; ACK; continue."""
    fresh(s, ds)
    T.press(s, "BtnStart")
    plan = mod["plan"]
    k = next(i for i, p in enumerate(plan) if p[2][2] == 0 and i >= 1)   # 2nd+ transfer with a ship drop
    cid, src, dst = plan[k]
    got = wait(lambda: int(s.r("HMI_IF.Carried")) == cid, 300, 0.1)
    dx, dy, db = dst
    s.w(T.B0 % (dx, dy), 999)
    f = wait(lambda: st(s) == 5, 15, 0.2)
    a = aw(s)
    check("obstacle: 999 at next ship drop -> ALARM, bit 2", got and f and a & 4, "carried=%s cell=(%d,%d) state=%s AlarmWord=%d" % (got, dx, dy, f, a))
    ack(s)
    fin = finish(s)
    b0, b1 = T.read_bays(s)
    where = [(x, y) for x in range(4) for y in range(12) if b0[x][y] == cid]
    check("obstacle: after ACK run continues to DONE", fin == 6, "state=%s M=%d T=%s" % (fin, M(s), s.r("time")))
    check("obstacle: container put to another ship cell", len(where) == 1 and where[0] != (dx, dy), "id %d at %s" % (cid, where))
    check("obstacle (1.15): OrderModeAct stays 1, no alarm 17", int(s.r("HMI_IF.OrderModeAct")) == 1 and not int(s.r("HMI_IF.AlarmWord2")) & 1,
          "OrderModeAct=%s AlarmWord2=%s" % (s.r("HMI_IF.OrderModeAct"), s.r("HMI_IF.AlarmWord2")))
    L, R = int(s.r("HMI_IF.BalL")), int(s.r("HMI_IF.BalR"))
    check("obstacle: final balance |L-R| <= 5", abs(L - R) <= 5, "L=%d R=%d" % (L, R))
    s.w(T.B0 % (dx, dy), 0)
    time.sleep(1.5)
    T.press(s, "BtnInit")
    wait(lambda: st(s) in (1, 7), 5, 0.05)
    wait(lambda: st(s) == 2, 180)
    time.sleep(1.5)
    b0, b1 = T.read_bays(s)
    check("obstacle -> POCETNO STANJE restores the loaded data set (R3-E1)", b0 == ds["bay0"] and b1 == ds["bay1"],
          "state=%d" % st(s))


def sc_repeat(s, ds, mod):
    """1.9: after DONE, POCETNO STANJE without new data restores the set; repeat run gives the same M/T."""
    fresh(s, ds)
    T.press(s, "BtnStart")
    finish(s)
    m1, t1 = M(s), float(s.r("time"))
    b0, b1 = T.read_bays(s)
    check("repeat: DB10/DB11 show the final yard after DONE", b0 == mod["bay0"] and b1 == mod["bay1"], "")
    T.press(s, "BtnInit")
    wait(lambda: st(s) in (1, 7), 5, 0.05)
    wait(lambda: st(s) == 2, 180)
    time.sleep(1.5)
    b0, b1 = T.read_bays(s)
    check("repeat: POCETNO STANJE restores the original data", b0 == ds["bay0"] and b1 == ds["bay1"], "M after init=%d" % M(s))
    T.press(s, "BtnAuto")
    time.sleep(0.5)
    T.press(s, "BtnStart")
    finish(s)
    check("repeat: second run same M/T", M(s) == m1 and float(s.r("time")) == t1, "run1 M=%d T=%.1f run2 M=%d T=%s" % (m1, t1, M(s), s.r("time")))


def sc_initrun(s, ds, mod):
    """1.14: POCETNO STANJE during RADI does nothing; after STOP it works."""
    fresh(s, ds)
    T.press(s, "BtnStart")
    wait(lambda: M(s) >= 5, 60)
    m0 = M(s)
    T.press(s, "BtnInit")
    time.sleep(3)
    check("init during RUNNING ignored", st(s) == 3 and M(s) > m0, "state=%d M %d->%d" % (st(s), m0, M(s)))
    T.press(s, "BtnStop")
    time.sleep(2.5)
    T.press(s, "BtnInit")
    r = wait(lambda: st(s) == 2 and M(s) == 0, 60)
    b0, b1 = T.read_bays(s)
    check("init after STOP works (READY, M=0, data restored)", r and b0 == ds["bay0"], "state=%d M=%d" % (st(s), M(s)))


SCEN = {"semi": sc_semi, "stopstart": sc_stopstart, "onoff": sc_onoff, "manual": sc_manual, "obstacle": sc_obstacle,
        "repeat": sc_repeat, "initrun": sc_initrun}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=",".join(SCEN))
    ap.add_argument("--data", default=os.path.join(os.path.dirname(HERE), "judge_sets", "r1_jury_fig1_half.json"))
    a = ap.parse_args()
    ds = T.cm.load_dataset(a.data)
    mod = T.model(a.data)
    s = Sim()
    for n in a.only.split(","):
        print("== scenario", n)
        try:
            SCEN[n](s, ds, mod)
        except Exception as ex:  # noqa: BLE001
            check("scenario %s raised" % n, False, repr(ex))
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "scenarios.json"), "w", encoding="utf-8") as f:
        json.dump(LOG, f, indent=1)
    print("CPU", s.cmd("STATE"))
    print("SCEN_RESULT fails=%d" % FAILS[0])
