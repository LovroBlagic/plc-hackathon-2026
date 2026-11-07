"""crane_stress.py - elimination-safety stress test of the v1.3 planner (greedy + IMPROVE).

  python tools/crane_stress.py [--random 300] [--seed 11] [--evals 600]

Datasets: tools/crane_data + tools/crane_data_stress + N freshly generated sets (random and
stress families, crane_gen.stress_one / random_set with a fixed seed).
Configs: CfgOrderMode 1 (PLC default, with fallback), 0, 2 x CfgBalMode 0/1 x CfgMMode 2/0.
For every plan the checks are (any failure is printed and counted):
  B1  every command passes CheckCmd and the FB1 emulator reproduces CumT/CumM (crane_plan.simulate)
  B2  ship balance after every lift/put: |L-R| <= 5, or never worse than before if the ship
      started out of balance (step rule); same for bow/stern when CfgBalMode = 1
  L1  the plan contains every pending list entry exactly once and nothing else
  L2  order mode actually used is respected: 1 = each list in its own order, 2 = unloads (in
      order) then loads (in order)
  D1  determinism: a second run gives an identical plan
  I1  IMPROVE never worse than the greedy, and the lower bound never above the plan
  R1  replan from the middle (after k transfers, crane at the last drop, Base T/M carried over;
      what FB10 does after STOP/ACK/MANUAL) - checks B1..L2 again on the rest
  F1  planner error 1 only when the end state is provably unbalanceable or the greedy dead-ends;
      sets where the end state is reachable but every mode fails are listed as 'suspect'
"""
import argparse
import glob
import os
import random
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crane_model as cm   # noqa: E402
import crane_plan as cp    # noqa: E402
import crane_gen as cg     # noqa: E402

AL = [0, 100, 200, 300]
EVALS = 600


def bal_trace_ok(state, plan, lim, balmode):
    g = [[c[:] for c in state["bay0"]], [c[:] for c in state["bay1"]]]
    L, R = cm.lr(g[0])
    F, A = cm.fa(g[0])
    for tr in plan:
        sx, sy, sb = tr["src"]
        dx, dy, db = tr["dst"]
        for (b, x, y, v) in ((sb, sx, sy, 0), (db, dx, dy, tr["id"])):
            g[b][x][y] = v
            if b == 0:
                L2, R2 = cm.lr(g[0])
                F2, A2 = cm.fa(g[0])
                if not cm.step_ok(L, R, L2, R2, lim):
                    return False, "B2 |L-R| %d->%d at id %d" % (abs(L - R), abs(L2 - R2), tr["id"])
                if balmode == 1 and not cm.step_ok(F, A, F2, A2, lim):
                    return False, "B2 |F-A| at id %d" % tr["id"]
                L, R, F, A = L2, R2, F2, A2
    return True, ""


def list_ok(state, plan, order):
    want = sorted([(1, i) for i, _ in state["PU"]] + [(2, j) for j, _ in state["PL"]])
    got = sorted((tr["kind"], tr["list_idx"]) for tr in plan)
    if want != got:
        return False, "L1 plan entries != pending entries"
    if order >= 1:
        for k in (1, 2):
            seq = [tr["list_idx"] for tr in plan if tr["kind"] == k]
            if seq != sorted(seq):
                return False, "L2 list %d out of order" % k
    if order == 2:
        kinds = [tr["kind"] for tr in plan]
        if kinds != sorted(kinds):
            return False, "L2 strict: load before an unload"
    return True, ""


def check_plan(state, res, tag):
    errs = []
    cfg = res["cfg"]
    try:
        cp.simulate(state, res["plan"], cfg)
    except AssertionError as e:
        errs.append("%s B1 %s" % (tag, e))
    ok, msg = bal_trace_ok(state, res["plan"], cfg["lim"], cfg["balmode"])
    if not ok:
        errs.append("%s %s" % (tag, msg))
    ok, msg = list_ok(state, res["plan"], res["order"])
    if not ok:
        errs.append("%s %s" % (tag, msg))
    if "J0" in res and res["J"] > res["J0"] + 1e-12:
        errs.append("%s I1 improve worse than greedy" % tag)
    lb = cp.lower_bound(state)
    if res["plan"] and lb[0] + state["base_t"] > res["T"] or (res["plan"] and lb[1] + state["base_m"] > res["M"]):
        errs.append("%s I1 lower bound above plan" % tag)
    return errs


def mid_state(state, plan, k):
    """State after the first k transfers of plan (crane at the k-th drop, Base T/M carried)."""
    g = [[c[:] for c in state["bay0"]], [c[:] for c in state["bay1"]]]
    done = set()
    for tr in plan[:k]:
        sx, sy, sb = tr["src"]
        dx, dy, db = tr["dst"]
        g[db][dx][dy] = g[sb][sx][sy]
        g[sb][sx][sy] = 0
        done.add((tr["kind"], tr["list_idx"]))
    st = dict(state)
    st.update(bay0=g[0], bay1=g[1], crane=tuple(plan[k - 1]["dst"]), base_t=plan[k - 1]["cum_t"],
              base_m=plan[k - 1]["cum_m"],
              PU=[(i, c) for (i, c) in state["PU"] if (1, i) not in done],
              PL=[(j, c) for (j, c) in state["PL"] if (2, j) not in done])
    return st


def run_set(ds):
    out = {"name": ds["name"], "errs": [], "plans": 0, "err1": 0, "suspect": False, "replans": 0}
    st = cp.build_state(ds)
    if st["init"]["blocking"]:
        out["blocking"] = True
        return out
    PU, PL = cp.locate([ds["bay0"], ds["bay1"]], st["PU"], st["PL"])
    L, R = cm.lr(ds["bay0"])
    uL = sum(1 for s in PU if s.pos[0] <= 1)
    end_reach = cm.reachable(L, R, uL, len(PU) - uL, len(PL))
    all_fail = True
    for mm in (2, 0):
        for order in (1, 0, 2):
            for bm in (0, 1):
                cfg = {"mmode": mm, "order": order, "balmode": bm, "lim": 5}
                tag = "%s m%d o%d b%d" % (ds["name"], mm, order, bm)
                res = cp.plan_fb(st, cfg, AL, imp_evals=EVALS)
                if res["err"] != 0:
                    out["err1"] += 1
                    continue
                all_fail = False
                out["plans"] += 1
                out["errs"] += check_plan(st, res, tag)
                if mm == 2 and bm == 0 and order == 1:
                    res2 = cp.plan_fb(st, cfg, AL, imp_evals=EVALS)
                    if cp.csv_lines(res2) != cp.csv_lines(res):
                        out["errs"].append("%s D1 not deterministic" % tag)
                    n = len(res["plan"])
                    for k in sorted(set([1, n // 3, n // 2, (2 * n) // 3])):
                        if 1 <= k < n:
                            ms = mid_state(st, res["plan"], k)
                            r3 = cp.plan_fb(ms, dict(cfg, order=order), AL, imp_evals=EVALS)
                            out["replans"] += 1
                            if r3["err"] != 0:
                                out["errs"].append("%s R1 replan after %d failed err %d" % (tag, k, r3["err"]))
                            else:
                                out["errs"] += check_plan(ms, r3, "%s R1@%d" % (tag, k))
    L0ok = abs(L - R) <= 5
    out["suspect"] = all_fail and end_reach and L0ok and (len(PU) + len(PL)) > 0
    return out


def gen_sets(n, seed):
    rng = random.Random(seed)
    fams = ("big", "full", "left", "right", "limit", "small", "loadonly", "mixed")
    sets = []
    for i in range(n):
        f = "rand" if i % 2 == 0 else fams[(i // 2) % len(fams)]
        for _ in range(500):
            try:
                if f == "rand":
                    d = cg.random_set(rng, "gen_rand_%03d" % i)
                else:
                    d = cg.stress_one(rng, f, "gen_%s_%03d" % (f, i))
                sets.append(d)
                break
            except (RuntimeError, ValueError):
                continue
    return sets


def _init(ev):
    global EVALS
    EVALS = ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--random", type=int, default=300)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--evals", type=int, default=600)
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    sets = [cm.load_dataset(p) for p in sorted(glob.glob(os.path.join(here, "crane_data", "*.json")))
            + sorted(glob.glob(os.path.join(here, "crane_data_stress", "*.json")))]
    sets += gen_sets(a.random, a.seed)
    with Pool(initializer=_init, initargs=(a.evals,)) as p:
        res = p.map(run_set, sets, chunksize=2)
    nerr = sum(len(r["errs"]) for r in res)
    for r in res:
        for e in r["errs"][:5]:
            print("FAIL", e)
    sus = [r["name"] for r in res if r["suspect"]]
    print("sets=%d (capacity-blocked %d)  plans checked=%d  mid-run replans=%d  planner err1 runs=%d" % (
        len(res), sum(1 for r in res if r.get("blocking")), sum(r["plans"] for r in res),
        sum(r["replans"] for r in res), sum(r["err1"] for r in res)))
    print("infeasible-in-every-mode sets=%d, of which end state reachable (suspect)=%d %s" % (
        sum(1 for r in res if r["plans"] == 0 and not r.get("blocking")), len(sus), sus[:10]))
    print("STRESS_RESULT failures=%d" % nerr)
    return 1 if nerr else 0


if __name__ == "__main__":
    sys.exit(main())
