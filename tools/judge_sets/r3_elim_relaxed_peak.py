"""r3_elim_relaxed_peak.py - judge round 3 (elimination): how hard does the v1.5 relaxed balance
fallback (R2-J1, World.BalCeil = BalD0) push an already-unbalanced ship?

For every dataset whose ship starts with |L-R| = d0 > 5 and where FB10's default chain ends up using
the relaxed rule (order 1, ceil = d0), report:
  - trajectory of |L-R| after every lift/put (PLC default: plan_fb + IMPROVE 3000 + SLOT),
  - number of steps that INCREASE |L-R| while it is > 5 ("makes the imbalance worse" events),
  - peak |L-R| reached AFTER the first decrease (i.e. the ship going back up),
  - c_min = smallest ceiling c in [6..d0] for which list order is exactly feasible (same rule, ceil=c).
If peak > c_min the PLC drives the ship back to a worse imbalance than necessary.

  python tools/judge_sets/r3_elim_relaxed_peak.py [files...]
"""
import glob
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm  # noqa: E402
import crane_plan as cp  # noqa: E402

ALPHAS = [0, 100, 200, 300]
CFG = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}


def traj(st, plan):
    g0 = [c[:] for c in st["bay0"]]
    L, R = cm.lr(g0)
    out = [abs(L - R)]
    for tr in plan:
        (sx, sy, sb), (dx, dy, db) = tr["src"], tr["dst"]
        if sb == 0:
            if sx <= 1:
                L -= 1
            else:
                R -= 1
            out.append(abs(L - R))
        if db == 0:
            if dx <= 1:
                L += 1
            else:
                R += 1
            out.append(abs(L - R))
    return out


def analyse(path, evals=3000):
    ds = cm.load_dataset(path)
    st = cp.build_state(ds)
    d0 = st["d0"]
    if d0 <= 5:
        return None
    res = cp.plan_fb(st, CFG, ALPHAS, imp_evals=evals)
    if res["err"] != 0:
        return {"name": os.path.basename(path), "d0": d0, "err": res["err"]}
    used_ceil = res["cfg"].get("ceil", 0)
    t = traj(st, res["plan"])
    worse = sum(1 for a, b in zip(t, t[1:]) if a > 5 and b > a)
    mn = min(t)
    first_min = t.index(mn)
    # peak after the first strict decrease below d0
    k = next((i for i, v in enumerate(t) if v < d0), None)
    peak_after = max(t[k:]) if k is not None else d0
    cmin = None
    if used_ceil:
        for c in range(6, d0 + 1):
            if cp.order_feasible(st, 1, 5, c):
                cmin = c
                break
    return {"name": os.path.basename(path), "d0": d0, "order": res["order"], "ceil": used_ceil,
            "worse_steps": worse, "peak_after_first_decrease": peak_after, "c_min": cmin,
            "end": t[-1], "traj": t, "J": round(res["J"], 5)}


def main(argv):
    files = argv[1:] or sorted(glob.glob(os.path.join(HERE, "*imb*.json"))
                               + glob.glob(os.path.join(HERE, "..", "crane_data", "edge_initial_imbalance.json"))
                               + glob.glob(os.path.join(HERE, "r3_elimination_*.json")))
    bad = 0
    for f in files:
        r = analyse(f)
        if r is None:
            continue
        print(json.dumps({k: v for k, v in r.items() if k != "traj"}))
        if r.get("ceil"):
            print("   |L-R| trajectory:", r["traj"])
            if r["c_min"] is not None and r["peak_after_first_decrease"] > r["c_min"]:
                bad += 1
    print("RELAXED_PEAK_RESULT sets_with_unneeded_peak=%d" % bad)


if __name__ == "__main__":
    main(sys.argv)
