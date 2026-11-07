"""r3_elim_obstacle_then_init.py - judge round 3 (elimination): the v1.5 R2-E2 fix makes ANY online edit
of DB10/DB11 (also while RUNNING) "new data" for the next POČETNO STANJE. An obstacle written during an
AUTO run to provoke the required "drop location occupied" alarm (team's own PLCSIM test 1.7 / 1.10) -
even if the tester writes the cell back to 0 afterwards - therefore makes POČETNO STANJE load the
LIVE mid-run / final yard instead of the original data set.

Uses the team's transliteration tools/fb10_init_model.FB10 (region 2a + INIT step 3, v1.5).

  python tools/judge_sets/r3_elim_obstacle_then_init.py [dataset.json]
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm  # noqa: E402
import crane_plan as cp  # noqa: E402
import fb10_init_model as fm  # noqa: E402


def lift(fb, tr):
    sx, sy, sb = tr["src"]
    g = (fb.W0, fb.W1)
    fb.Carried = g[sb][sx][sy]
    g[sb][sx][sy] = 0


def put(fb, tr):
    dx, dy, db = tr["dst"]
    g = (fb.W0, fb.W1)
    g[db][dx][dy] = fb.Carried
    fb.Carried = 0


def scenario(A, k_obstacle, k_stop, stop_with_load, cleanup):
    fb = fm.FB10()
    DB10, DB11 = copy.deepcopy(A["bay0"]), copy.deepcopy(A["bay1"])
    DB20, DB21 = fm._lists(A)
    fb.State = 1
    fb.init_step3(DB10, DB11, DB20, DB21)                      # first POČETNO STANJE: data set A
    plan = cp.plan_fb(cp.build_state(A), {"mmode": 2, "order": 1, "balmode": 0, "lim": 5},
                      [0, 100, 200, 300])["plan"]
    fb.State = 3                                               # AUTO, START -> RADI
    obst = None
    for k, tr in enumerate(plan[:k_stop]):
        if k == k_obstacle:
            # tester provokes alarm 3 "drop location occupied": writes an ID into the next drop cell
            dx, dy, db = tr["dst"]
            (DB10, DB11)[db][dx][dy] = 999
            obst = (db, dx, dy)
            fb.region_2a(DB10, DB11)
            # ... alarm, POTVRDA, the PLC re-targets the put (not modelled: same effect on the yard) ...
            if cleanup:                                        # tester removes the obstacle again
                (DB10, DB11)[db][dx][dy] = 0
                fb.region_2a(DB10, DB11)
        lift(fb, tr)
        fb.region_2a(DB10, DB11)
        put(fb, tr)
        fb.region_2a(DB10, DB11)
    if stop_with_load and k_stop < len(plan):
        lift(fb, plan[k_stop])                                 # STOP right after the next lift
        fb.region_2a(DB10, DB11)
    fb.State = 4                                               # PAUZA
    fb.region_2a(DB10, DB11)
    carried = fb.Carried
    fb.State = 1
    fb.init_step3(DB10, DB11, DB20, DB21)                      # second POČETNO STANJE (scored run)
    same = fb.W0 == A["bay0"] and fb.W1 == A["bay1"]
    ds2 = {"bay0": fb.W0, "bay1": fb.W1, "unload": DB20, "load": DB21}
    iv = cm.init_validate(ds2)
    iv0 = cm.init_validate(A)
    pend0 = sum(1 for s in iv0["UState"] + iv0["LState"] if s == 0)
    pend = sum(1 for s in iv["UState"] + iv["LState"] if s == 0)
    ids_all = {v for g in (fb.W0, fb.W1) for c in g for v in c if v}
    lost = carried if carried and carried not in ids_all else 0
    return {"k_obstacle": k_obstacle, "k_stop": k_stop, "stop_with_load": stop_with_load, "cleanup": cleanup,
            "reloaded_original": same, "pending_original": pend0, "pending_after_reload": pend,
            "alarm_bits_after_reload": iv["bits"], "container_lost": lost,
            }


def main(argv):
    path = argv[1] if len(argv) > 1 else os.path.join(HERE, "..", "crane_data", "rand_05.json")
    A = cm.load_dataset(path)
    n = len(cp.plan_fb(cp.build_state(A), {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])["plan"])
    fails = 0
    for (ko, ks, wl, cl) in ((None, n, False, False),     # control: no edit at all -> original restored
                             (2, n, False, True),         # obstacle at transfer 3, removed again, run to DONE
                             (2, 5, True, True)):         # obstacle + cleanup, STOP after the 6th lift
        r = scenario(A, -1 if ko is None else ko, ks, wl, cl)
        bad = not r["reloaded_original"]
        fails += bad
        print(("FAIL " if bad else "ok   ") + str(r))
    print("OBSTACLE_INIT_RESULT failures=%d (of 2 obstacle scenarios; control must be ok)" % fails)


if __name__ == "__main__":
    main(sys.argv)
