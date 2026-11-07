"""r3_elim_relaxed_free.py - judge round 3: sets where the PLC default chain ends with bit 8 "plan
infeasible" (nothing moves) although a plan exists under the same relaxed rule in FREE order
(FB10 never tries order 0 with BalCeil = BalD0: order1 step -> order1 relaxed -> order0 step -> bal0 -> error).
  python tools/judge_sets/r3_elim_relaxed_free.py
"""
import os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm, crane_plan as cp
A = [0, 100, 200, 300]
files = sorted(set(glob.glob(os.path.join(HERE, "..", "crane_data*", "*.json")) + glob.glob(os.path.join(HERE, "*.json"))))
n = hit = 0
for f in files:
    try:
        ds = cm.load_dataset(f)
    except Exception:
        continue
    st = cp.build_state(ds)
    if st["d0"] <= 5 or st["init"]["blocking"]:
        continue
    n += 1
    r = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, A)
    if r["err"] == 0:
        continue
    r2 = cp.plan(st, {"mmode": 2, "order": 0, "balmode": 0, "lim": 5, "ceil": st["d0"]}, A)
    ok = False
    if r2["err"] == 0:
        c = {"mmode": 2, "order": 0, "balmode": 0, "lim": 5, "ceil": st["d0"]}
        cp.simulate(st, r2["plan"], c)
        ok = True
    print("%-55s d0=%2d default_err=%d relaxed_free=%s" % (os.path.relpath(f, os.path.join(HERE, "..")), st["d0"], r["err"], "FEASIBLE" if ok else "err%d" % r2["err"]))
    hit += ok
print("RELAXED_FREE_RESULT unbalanced_sets=%d default_infeasible_but_relaxed_free_feasible=%d" % (n, hit))
