"""r1_search.py - judge round 1: random search with the team's own generators (crane_gen.random_set /
stress_one) for (a) needless fallback to free order (order-1 plan exists, PLC breaks list order) and
(b) false 'plan infeasible' (bit 8) although a balanced plan exists. Saves hits as judge datasets.

  python tools/judge_sets/r1_search.py [--n 600] [--seed 777] [--save 3]
"""
import json
import os
import random
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402
import crane_gen as cg    # noqa: E402
import r1_feas as rf      # noqa: E402

FAMS = ("rand", "big", "full", "left", "right", "limit", "mixed", "rand")


def gen(i, seed):
    rng = random.Random(seed * 100003 + i)
    f = FAMS[i % len(FAMS)]
    for _ in range(500):
        try:
            if f == "rand":
                return cg.random_set(rng, "s%d_%s_%04d" % (seed, f, i))
            return cg.stress_one(rng, f, "s%d_%s_%04d" % (seed, f, i))
        except (RuntimeError, ValueError):
            continue
    return None


def one(args):
    i, seed = args
    ds = gen(i, seed)
    if ds is None:
        return None
    st = cp.build_state(ds)
    if st["init"]["blocking"]:
        return None
    feas = {o: rf.feasible(ds, st, o) for o in (1, 2, 0)}
    res = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])
    kind = None
    if res["err"] == 0 and res["order"] == 0 and feas[1]:
        kind = "needless_fallback"
    elif res["err"] != 0 and feas[0]:
        kind = "false_infeasible"
    return {"i": i, "fam": FAMS[i % len(FAMS)], "feas": feas, "err": res["err"], "used": res.get("order"),
            "kind": kind, "ds": ds if kind else None, "n": len(st["PU"]) + len(st["PL"])}


def main():
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 600
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 777
    save = int(a[a.index("--save") + 1]) if "--save" in a else 3
    with Pool() as p:
        rs = [r for r in p.map(one, [(i, seed) for i in range(n)]) if r]
    tot = len(rs)
    fb = [r for r in rs if r["used"] == 0 and r["err"] == 0]
    nf = [r for r in rs if r["kind"] == "needless_fallback"]
    fi = [r for r in rs if r["kind"] == "false_infeasible"]
    o1 = [r for r in rs if r["feas"][1]]
    print("sets=%d  order1-feasible=%d  PLC fell back to free order=%d  of which order1 WAS feasible=%d  false-infeasible=%d"
          % (tot, len(o1), len(fb), len(nf), len(fi)))
    byfam = {}
    for r in nf:
        byfam[r["fam"]] = byfam.get(r["fam"], 0) + 1
    print("needless fallback by family:", byfam)
    for kind, lst in (("needless_fallback", nf), ("false_infeasible", fi)):
        lst = sorted(lst, key=lambda r: r["n"])
        for r in lst[:save]:
            ds = dict(r["ds"])
            nm = "r1_elimination_%s_%s" % (kind, ds["name"])
            ds["name"] = nm
            ds["note"] = "judge r1: %s; exact feas order1/2/0=%s; plan_fb err=%d used order=%s" % (
                kind, (r["feas"][1], r["feas"][2], r["feas"][0]), r["err"], r["used"])
            with open(os.path.join(HERE, nm + ".json"), "w") as f:
                json.dump(ds, f)
            print("saved", nm, "n=%d" % r["n"])


if __name__ == "__main__":
    main()
