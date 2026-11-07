"""r3_elim_relaxed_cmin.py - judge round 3: compare the PLC's relaxed plan (ceil = d0) with the same
pipeline run at the smallest feasible ceiling c_min (FB10 would only need to try BalCeil = 6..d0).
  python tools/judge_sets/r3_elim_relaxed_cmin.py
"""
import os, sys, glob, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm, crane_plan as cp
from r3_elim_relaxed_peak import traj, ALPHAS

def run(st, ceil, evals=3000):
    c = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5, "ceil": ceil}
    res = cp.plan(st, c, ALPHAS)
    if res["err"]:
        return None
    res = cp.improve(st, c, res, evals, 0)
    res = cp.slot_search(st, c, res, cp.SLOT_SWEEPS)
    return res

for f in sorted(glob.glob(os.path.join(HERE, "*imb*.json"))):
    st = cp.build_state(cm.load_dataset(f))
    d0 = st["d0"]
    if d0 <= 5 or cp.order_feasible(st, 1, 5, 0):
        continue
    cmin = next((c for c in range(6, d0 + 1) if cp.order_feasible(st, 1, 5, c)), None)
    if cmin is None:
        continue
    a, b = run(st, d0), run(st, cmin)
    ta, tb = traj(st, a["plan"]), traj(st, b["plan"])
    w = lambda t: sum(1 for p, q in zip(t, t[1:]) if p > 5 and q > p)
    print("%-28s d0=%2d c_min=%2d | PLC(ceil=d0): J=%.5f worse=%d max_after_dec=%d | ceil=c_min: J=%.5f worse=%d max_after_dec=%d dJ=%+.2f%%" % (
        os.path.basename(f), d0, cmin, a["J"], w(ta), max(ta[1:]), b["J"], w(tb), max(tb[1:]), 100 * (b["J"] / a["J"] - 1)))
    print("    c_min trajectory:", tb)
