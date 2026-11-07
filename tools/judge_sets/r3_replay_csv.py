"""r3_replay_csv.py - re-execute a saved judge plan CSV through crane_plan.simulate (FB1 emulator +
CheckCmd + balance) and check the per-list order; prints the J of the plan and of our planner.
  python tools/judge_sets/r3_replay_csv.py <set.json> <plan.csv> [--ceil D]
"""
import sys, os, csv
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm, crane_plan as cp

ds_path, csv_path = sys.argv[1], sys.argv[2]
ceil = int(sys.argv[sys.argv.index("--ceil") + 1]) if "--ceil" in sys.argv else 0
d = cm.load_dataset(ds_path)
st = cp.build_state(d)
plan = []
with open(csv_path) as fh:
    for r in csv.DictReader(fh):
        if not r["i"].isdigit():
            continue
        plan.append({"kind": int(r["kind"]), "id": int(r["id"]), "list_idx": int(r["list_idx"]),
                     "src": (int(r["src_x"]), int(r["src_y"]), int(r["src_bay"])),
                     "dst": (int(r["dst_x"]), int(r["dst_y"]), int(r["dst_bay"])),
                     "cum_t": int(r["cum_t_ds"]), "cum_m": int(r["cum_m"])})
cfg = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5, "ceil": ceil}
cp.simulate(st, plan, cfg)
u = [p["list_idx"] for p in plan if p["kind"] == 1]
l = [p["list_idx"] for p in plan if p["kind"] == 2]
assert u == sorted(u) and l == sorted(l), "per-list order violated"
assert len(plan) == len(st["PU"]) + len(st["PL"]), "not all list entries executed"
Jp = cm.J(plan[-1]["cum_t"], plan[-1]["cum_m"], st["N"])
r = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300], imp_evals=3000)
print("REPLAY_OK judge_plan J=%.4f (T=%d M=%d)  ours J=%.4f (T=%d M=%d, order %d)  ours/judge-1=%+.2f%%" % (
    Jp, plan[-1]["cum_t"], plan[-1]["cum_m"], r["J"], r["T"], r["M"], r["order"], 100 * (r["J"] / Jp - 1)))
