"""crane_bench.py - per-set J benchmark over ALL datasets (crane_data, crane_data_stress, judge_sets).

  python tools/crane_bench.py --out <file.json> [--evals 3000] [--mmode 0] [--orders 1,0]
  python tools/crane_bench.py --compare old.json new.json

For every dataset and preferred order mode: plan_fb (FB10 behaviour, fallback) + IMPROVE, plan executed
through simulate() (FB1 emulator + CheckCmd + step rule). Records err, J, order_used, list inversions.
--compare prints mean J (sets feasible in both), per-set regressions, newly infeasible sets and fallbacks.
"""
import argparse
import glob
import json
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402

ALPHAS = [0, 75, 125, 200]   # v1.7 World.CfgAlpha


def all_sets():
    fs = []
    for d in ("crane_data", "crane_data_stress", "judge_sets"):
        fs += sorted(glob.glob(os.path.join(HERE, d, "*.json")))
    return fs


def one(args):
    path, order, mmode, evals, legacy, alphas = args
    name = os.path.relpath(path, HERE).replace("\\", "/")
    try:
        ds = cm.load_dataset(path)
    except Exception as e:  # not a dataset
        return None
    if "bay0" not in ds:
        return None
    st = cp.build_state(ds)
    key = "%s|o%d" % (name, order)
    if st["init"]["blocking"]:
        return key, {"err": "cap"}
    cfg = {"mmode": mmode, "order": order, "balmode": 0, "lim": 5, "exact": not legacy}
    r = cp.plan_fb(st, cfg, alphas, imp_evals=evals, slot_sweeps=0 if legacy else None)
    if r["err"] != 0:
        return key, {"err": r["err"]}
    cp.simulate(st, r["plan"], r["cfg"])
    inv = 0
    for k in (1, 2):
        seq = [t["list_idx"] for t in r["plan"] if t["kind"] == k]
        inv += sum(1 for a in range(len(seq)) for b in range(a + 1, len(seq)) if seq[a] > seq[b])
    return key, {"err": 0, "J": r["J"], "T": r["T"], "M": r["M"], "order_used": r["order"], "inv": inv,
                 "J0": r.get("J0"), "evals": r.get("imp_evals", 0), "slot_sweeps": r.get("slot_sweeps", 0),
                 "pref_feasible": cp.order_feasible(st, order) if order else True}


def compare(a, b):
    A, B = json.load(open(a)), json.load(open(b))
    for o in ("o1", "o0", "o2"):
        ks = [k for k in A if k.endswith("|" + o) and k in B]
        if not ks:
            continue
        both = [k for k in ks if A[k].get("err") == 0 and B[k].get("err") == 0]
        newinf = [k for k in ks if A[k].get("err") == 0 and B[k].get("err") != 0]
        ja = sum(A[k]["J"] for k in both) / max(1, len(both))
        jb = sum(B[k]["J"] for k in both) / max(1, len(both))
        worse = sorted(((B[k]["J"] / A[k]["J"] - 1) * 100, k) for k in both if B[k]["J"] > A[k]["J"] + 1e-12 and A[k]["J"] > 0)
        better = sum(1 for k in both if B[k]["J"] < A[k]["J"] - 1e-12)
        fa = sum(1 for k in ks if A[k].get("err") == 0 and A[k]["order_used"] != int(o[1]))
        fb = sum(1 for k in ks if B[k].get("err") == 0 and B[k]["order_used"] != int(o[1]))
        print("%s: sets=%d feasible-both=%d  mean J %.5f -> %.5f (%+.3f %%)  better=%d worse=%d  "
              "newly-infeasible=%d  fallbacks %d -> %d  max-gain=%.2f %%" % (
                  o, len(ks), len(both), ja, jb, (jb / ja - 1) * 100, better, len(worse), len(newinf), fa, fb,
                  max([(1 - B[k]["J"] / A[k]["J"]) * 100 for k in both if A[k]["J"] > 0] or [0])))
        for w, k in worse[-8:]:
            print("   worse %+.3f %%  %s" % (w, k))
        for k in newinf:
            print("   NEWLY INFEASIBLE %s  %s" % (k, B[k]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--evals", type=int, default=3000)
    ap.add_argument("--mmode", type=int, default=0)
    ap.add_argument("--orders", default="1,0")
    ap.add_argument("--compare", nargs=2)
    ap.add_argument("--only", default="")
    ap.add_argument("--alphas", default=",".join(str(v) for v in ALPHAS), help="CfgAlpha (default = World start values)")
    ap.add_argument("--legacy", action="store_true", help="v1.3 planner: reachable(), no SLOT phase")
    a = ap.parse_args()
    if a.compare:
        compare(*a.compare)
        return
    al = [int(v) for v in a.alphas.split(",")]
    jobs = [(f, int(o), a.mmode, a.evals, a.legacy, al) for f in all_sets() if a.only in f for o in a.orders.split(",")]
    with Pool() as p:
        res = dict(r for r in p.map(one, jobs, chunksize=1) if r)
    json.dump(res, open(a.out, "w"), indent=0, sort_keys=True)
    for o in a.orders.split(","):
        ok = [v for k, v in res.items() if k.endswith("|o" + o) and v.get("err") == 0]
        print("o%s: feasible=%d  mean J=%.5f  fallbacks=%d" % (
            o, len(ok), sum(v["J"] for v in ok) / max(1, len(ok)), sum(1 for v in ok if v["order_used"] != int(o))))


if __name__ == "__main__":
    main()
