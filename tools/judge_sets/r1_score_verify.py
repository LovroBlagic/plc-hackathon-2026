"""r1_score_verify.py - re-execute a judge plan CSV through the FB1 emulator + CheckCmd + balance
asserts (crane_plan.simulate) and compare with our planner on the same set.

  python tools/judge_sets/r1_score_verify.py <set.json> <plan.csv> [--mmode 2] [--order 1]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("plan")
    ap.add_argument("--mmode", type=int, default=2)
    ap.add_argument("--order", type=int, default=1)
    a = ap.parse_args()
    ds = cm.load_dataset(a.dataset)
    st = cp.build_state(ds)
    plan = []
    for line in open(a.plan):
        line = line.strip()
        if not line or line.startswith("i,") or line.startswith("RESULT"):
            continue
        v = [int(x) for x in line.split(",")]
        plan.append({"kind": v[1], "id": v[2], "list_idx": v[3], "src": (v[5], v[6], v[4]),
                     "dst": (v[8], v[9], v[7]), "cum_t": v[10], "cum_m": v[11]})
    cfg = {"mmode": a.mmode, "order": a.order, "balmode": 0, "lim": 5}
    cp.simulate(st, plan, cfg)
    pend = {(1, i) for i, _ in st["PU"]} | {(2, j) for j, _ in st["PL"]}
    got = {(t["kind"], t["list_idx"]) for t in plan}
    assert got == pend and len(plan) == len(pend), "plan does not cover every pending list entry exactly once"
    if a.order == 1:
        for k in (1, 2):
            idx = [t["list_idx"] for t in plan if t["kind"] == k]
            assert idx == sorted(idx), "per-list order violated"
    T, M = plan[-1]["cum_t"], plan[-1]["cum_m"]
    J = cm.J(T, M, st["N"])
    r = cp.plan_fb(st, dict(cfg), [0, 100, 200, 300], imp_evals=3000)
    print("VALID  judge J=%.4f (T=%d M=%d)   ours (order %d pref, used %d) J=%.4f (T=%d M=%d)   ours worse by %.2f%%" % (
        J, T, M, a.order, r["order"], r["J"], r["T"], r["M"], 100 * (r["J"] / J - 1)))


if __name__ == "__main__":
    main()
