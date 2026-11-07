"""r3_elim_retarget_order.py - judge round 3 (elimination): does the ACK re-target of a rejected plan put
("drop location occupied", alarm 3) break list order although it need not?

FB10 REGION 5 (ACK, v1.4+): a rejected plan put with the container on the hook goes to the NEAREST free
cell of the same bay that passes only the one-step balance rule (min FB1 time from the crane, x 0..3
outer / y 0..11 inner, strict <). It does not look at whether the remaining lists can still be done in
list order. After that put, FB10 replans (ReplanAfterPut) with the preferred order 1; if the order is now
infeasible it falls back (relaxed rule if d0 > 5, then FREE ORDER = alarm 17, list order abandoned).

For every load transfer k (destination on the ship) of the order-1 PLC plan we simulate:
  transfers 1..k-1 done, crane lifted container k and moved to its planned drop cell, tester writes an
  obstacle ID into that drop cell (DB10 online edit, the only way to provoke alarm 3 in AUTO), POTVRDA.
We then compare FB10's re-target cell with every other balance-safe free ship cell:
  NEEDLESS = FB10's choice makes order 1 infeasible (-> free-order fallback) while another free cell
  that the step rule also allows keeps order 1 feasible.

  python tools/judge_sets/r3_elim_retarget_order.py [--max-sets N] [files...]
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm  # noqa: E402
import crane_plan as cp  # noqa: E402

ALPHAS = [0, 100, 200, 300]
CFG = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}
OBST = 998


def state_from(g, crane, pend_u, pend_l, d0):
    return {"bay0": g[0], "bay1": g[1], "crane": crane, "carried": 0, "d0": d0, "base_t": 0, "base_m": 0,
            "PU": pend_u, "PL": pend_l, "N": len(pend_u) + len(pend_l)}


def feasible_o1(st, ceil_d0):
    if cp.order_feasible(st, 1, 5, 0):
        return True
    return ceil_d0 > 5 and cp.order_feasible(st, 1, 5, ceil_d0)


def fb10_retarget(g, crane, ceil):
    """FB10 REGION 5 re-target for a ship put (dstB = 0). Returns (x, y) or None."""
    L, R = cm.lr(g[0])
    best = None
    bestT = 32767
    for x in range(4):
        for y in range(12):
            if g[0][x][y] != 0:
                continue
            nL, nR = (L + 1, R) if x <= 1 else (L, R + 1)
            ok = abs(nL - nR) <= 5 or abs(nL - nR) <= abs(L - R) or (abs(L - R) > 5 and abs(nL - nR) <= ceil)
            if ok:
                t = max(abs(x - crane[0]) * 60, abs(y - crane[1]) * 23)
                if t < bestT:
                    bestT, best = t, (x, y)
    return best


def check_set(path):
    ds = cm.load_dataset(path)
    st0 = cp.build_state(ds)
    if st0["init"]["blocking"]:
        return []
    d0 = st0["d0"]
    res = cp.plan_fb(st0, CFG, ALPHAS)
    if res["err"] != 0 or res["order"] != 1:
        return []
    ceil = res["cfg"].get("ceil", 0)
    plan = res["plan"]
    out = []
    g = [[c[:] for c in ds["bay0"]], [c[:] for c in ds["bay1"]]]
    for k, tr in enumerate(plan):
        (sx, sy, sb), (dx, dy, db) = tr["src"], tr["dst"]
        if db == 0:
            # container k lifted, crane at its planned drop cell, obstacle written there
            gk = [[c[:] for c in g[0]], [c[:] for c in g[1]]]
            cid = gk[sb][sx][sy]
            gk[sb][sx][sy] = 0
            gk[0][dx][dy] = OBST
            rest = plan[k + 1:]
            pu = [(t["list_idx"], t["id"]) for t in rest if t["kind"] == 1]
            pl = [(t["list_idx"], t["id"]) for t in rest if t["kind"] == 2]
            pu.sort()
            pl.sort()
            choice = fb10_retarget(gk, (dx, dy), ceil)
            if choice is None:
                continue
            L, R = cm.lr(gk[0])
            alts_ok = []
            choice_ok = None
            for x in range(4):
                for y in range(12):
                    if gk[0][x][y] != 0:
                        continue
                    nL, nR = (L + 1, R) if x <= 1 else (L, R + 1)
                    if not (abs(nL - nR) <= 5 or abs(nL - nR) <= abs(L - R) or (abs(L - R) > 5 and abs(nL - nR) <= ceil)):
                        continue
                    g2 = [[c[:] for c in gk[0]], [c[:] for c in gk[1]]]
                    g2[0][x][y] = cid
                    ok = feasible_o1(state_from(g2, (x, y, 0), pu, pl, d0), d0)
                    if (x, y) == choice:
                        choice_ok = ok
                    elif ok:
                        alts_ok.append((x, y))
            if choice_ok is False and alts_ok:
                # confirm with FB10's real fallback chain
                g2 = [[c[:] for c in gk[0]], [c[:] for c in gk[1]]]
                g2[0][choice[0]][choice[1]] = cid
                r2 = cp.plan_fb(state_from(g2, (choice[0], choice[1], 0), pu, pl, d0), CFG, ALPHAS)
                out.append({"set": os.path.basename(path), "transfer": k + 1, "id": cid, "planned_dst": (dx, dy),
                            "fb10_cell": choice, "replan_order": r2["order"] if r2["err"] == 0 else "err%d" % r2["err"],
                            "order1_cells": alts_ok[:6], "n_alt": len(alts_ok)})
        g[db][dx][dy] = g[sb][sx][sy]
        g[sb][sx][sy] = 0
    return out


def main(argv):
    args = argv[1:]
    mx = 10 ** 9
    if args[:1] == ["--max-sets"]:
        mx = int(args[1])
        args = args[2:]
    files = args or sorted(glob.glob(os.path.join(HERE, "..", "crane_data", "*.json"))
                           + glob.glob(os.path.join(HERE, "..", "crane_data_stress", "*.json")))
    files = files[:mx]
    nsets = nhit = 0
    for f in files:
        try:
            hits = check_set(f)
        except Exception as e:  # noqa: BLE001
            print("skip", f, e)
            continue
        nsets += 1
        for h in hits:
            print("NEEDLESS", h)
        nhit += 1 if hits else 0
    print("RETARGET_ORDER_RESULT sets=%d sets_with_needless_order_break=%d" % (nsets, nhit))


if __name__ == "__main__":
    main(sys.argv)
