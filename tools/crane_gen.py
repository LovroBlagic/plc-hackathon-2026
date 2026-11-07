"""crane_gen.py - dataset generator (CONTRACT section 5 JSON) + *.plan.csv writer.

  python tools/crane_gen.py [--n 30] [--seed 1] [--out tools/crane_data]

Random sets: ship fill 20..48, yard fill 10..48, list sizes 0..48 each, unload IDs drawn
from Bay0 and load IDs from Bay1, unique IDs 100..999, initial ship balanced (|L-R| <= 5,
L, R <= 24), capacity feasible.  Plus hand-made edge cases and the archive toy set.
"""

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402

CELLS = [(x, y) for x in range(4) for y in range(12)]


def blank():
    return [[0] * 12 for _ in range(4)]


def pad(lst):
    return list(lst) + [0] * (48 - len(lst))


def ds_dict(name, bay0, bay1, unload, load, note=""):
    d = {"name": name, "bay0": bay0, "bay1": bay1, "unload": pad(unload), "load": pad(load)}
    if note:
        d["note"] = note
    return d


def fill_ship(rng, n, ids, maxdiff=5):
    """Place n containers in the ship with |L-R| <= maxdiff (and L, R <= 24)."""
    lo = max(0, n - 24)
    hi = min(24, n)
    choices = [l for l in range(lo, hi + 1) if abs(l - (n - l)) <= maxdiff]
    nl = rng.choice(choices)
    left = [c for c in CELLS if c[0] <= 1]
    right = [c for c in CELLS if c[0] >= 2]
    cells = rng.sample(left, nl) + rng.sample(right, n - nl)
    g = blank()
    for (x, y) in cells:
        g[x][y] = ids.pop()
    return g


def fill_any(rng, n, ids):
    g = blank()
    for (x, y) in rng.sample(CELLS, n):
        g[x][y] = ids.pop()
    return g


def occupied_ids(g):
    return [g[x][y] for x in range(4) for y in range(12) if g[x][y] != 0]


def random_set(rng, name, ship=None, yard=None, nu=None, nl=None, unload_side=None):
    ids = rng.sample(range(100, 1000), 96)
    for _ in range(1000):
        s = ship if ship is not None else rng.randint(20, 48)
        y = yard if yard is not None else rng.randint(10, 48)
        u = nu if nu is not None else rng.randint(0, min(48, s))
        l = nl if nl is not None else rng.randint(0, min(48, y))
        u = min(u, s)
        l = min(l, y)
        # capacity: ship s-u+l <= 48 ; yard y-l+u <= 48
        if s - u + l <= 48 and y - l + u <= 48:
            break
    else:
        raise RuntimeError("no capacity-feasible sizes")
    bay0 = fill_ship(rng, s, ids)
    bay1 = fill_any(rng, y, ids)
    pool0 = occupied_ids(bay0)
    if unload_side == "left":
        pool0 = [bay0[x][yy] for x in (0, 1) for yy in range(12) if bay0[x][yy] != 0]
        u = min(u, len(pool0))
    unload = rng.sample(pool0, u)
    load = rng.sample(occupied_ids(bay1), l)
    return ds_dict(name, bay0, bay1, unload, load,
                   "ship=%d yard=%d unload=%d load=%d" % (s, y, u, l))


def edge_sets(rng):
    out = []
    # full ship, unload 10, load 10
    out.append(random_set(rng, "edge_full_ship", ship=48, yard=30, nu=10, nl=10))
    # full ship, only unload all 48
    out.append(random_set(rng, "edge_full_ship_unload_all", ship=48, yard=0, nu=48, nl=0))
    # full yard, full load
    out.append(random_set(rng, "edge_full_yard_load", ship=20, yard=48, nu=20, nl=28))
    # empty lists
    out.append(random_set(rng, "edge_empty_lists", ship=30, yard=30, nu=0, nl=0))
    # only unload / only load
    out.append(random_set(rng, "edge_only_unload", ship=36, yard=12, nu=30, nl=0))
    out.append(random_set(rng, "edge_only_load", ship=20, yard=40, nu=0, nl=28))
    # all-left unloads with loads (balance must be restored by loads to the left)
    out.append(random_set(rng, "edge_all_left_unloads", ship=40, yard=30, nu=18, nl=20, unload_side="left"))
    # all-left unloads, no loads -> provably infeasible balance (expect error 1)
    d = random_set(rng, "edge_all_left_unloads_noload_infeasible", ship=40, yard=10, nu=12, nl=0, unload_side="left")
    d["note"] += " (expected: planner ErrCode 1, balance cannot be held)"
    out.append(d)
    # max both lists 48/48 is impossible with 48 cells; 40/40 swap
    out.append(random_set(rng, "edge_big_swap", ship=44, yard=44, nu=40, nl=40))
    # invalid / duplicate / missing IDs
    d = random_set(rng, "edge_invalid_dup_ids", ship=30, yard=30, nu=10, nl=10)
    d["unload"][10] = 50          # invalid
    d["unload"][11] = d["unload"][0]   # duplicate within list
    d["load"][10] = 1200          # invalid
    d["load"][11] = d["unload"][1]     # same ID in both lists
    d["load"][13] = 999 if 999 not in occupied_ids(d["bay1"]) + occupied_ids(d["bay0"]) else 998  # missing
    d["bay1"][3][11] = 77 if d["bay1"][3][11] == 0 else d["bay1"][3][11]  # invalid cell id obstacle
    d["note"] += " + invalid(50,1200,cell 77), dup, missing, gap at idx 13"
    out.append(d)
    # initially imbalanced ship (|L-R| = 9): planner must not worsen it
    ids = rng.sample(range(100, 1000), 96)
    bay0 = blank()
    left = [c for c in CELLS if c[0] <= 1]
    right = [c for c in CELLS if c[0] >= 2]
    for (x, y) in rng.sample(left, 20) + rng.sample(right, 11):
        bay0[x][y] = ids.pop()
    bay1 = fill_any(rng, 30, ids)
    out.append(ds_dict("edge_initial_imbalance", bay0, bay1,
                       rng.sample(occupied_ids(bay0), 12), rng.sample(occupied_ids(bay1), 12),
                       "ship L=20 R=11 initially"))
    return out


def sample_archive():
    """Toy set from the given archive (CONTRACT 0): one list 111..777, other 123/124/125,
    one bay [0,0]=123, [0,1]=326, [0,2]=987. Which bay holds the 3 IDs is not yet confirmed
    (tooling export pending), so both placements are written."""
    out = []
    for b in (0, 1):
        g = [blank(), blank()]
        g[b][0][0], g[b][0][1], g[b][0][2] = 123, 326, 987
        out.append(ds_dict("sample_archive_b%d" % b, g[0], g[1],
                           [111, 222, 333, 444, 555, 666, 777], [123, 124, 125],
                           "APPROXIMATE toy set; IDs 123/326/987 placed in Bay%d. Verify vs tia-work/export." % b))
    return out


def write_plan_csv(path_json, path_csv):
    ds = cm.load_dataset(path_json)
    cfg = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}   # PLC default (order 1 + fallback)
    st = cp.build_state(ds)
    if st["init"]["blocking"]:
        lines = ["i,kind,id,list_idx,src_bay,src_x,src_y,dst_bay,dst_x,dst_y,cum_t_ds,cum_m",
                 "RESULT error=capacity(bit7)"]
    else:
        res = cp.plan_fb(st, cfg, [0, 50, 100, 150])
        lines = cp.csv_lines(res)
        if res["err"] == 0:
            cp.simulate(st, res["plan"], res["cfg"])
    with open(path_csv, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return lines[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "crane_data"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    sets = [random_set(rng, "rand_%02d" % i) for i in range(1, a.n + 1)]
    sets += edge_sets(rng)
    sets += sample_archive()
    for d in sets:
        p = os.path.join(a.out, d["name"] + ".json")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(d, separators=(",", ":")) + "\n")
        r = write_plan_csv(p, os.path.join(a.out, d["name"] + ".plan.csv"))
        print("%-45s %s" % (d["name"], r))
    write_golden(a.out, os.path.join(os.path.dirname(a.out), "crane_golden.json"))


def write_golden(data_dir, out_path):
    """Golden command sequences (default config) for PLCSIM end-to-end tests.
    Uses tia-src/given_data.json when it exists, else the sample/representative sets."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    given = os.path.join(root, "tia-src", "given_data.json")
    paths = [given] if os.path.exists(given) else []
    paths += [os.path.join(data_dir, n + ".json") for n in ("sample_archive_b1", "rand_05", "rand_08")]
    cfg = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}
    gold = {"config": {"CfgMMode": 2, "CfgOrderMode": 1, "CfgBalMode": 0, "CfgBalLimit": 5,
                       "CfgAlpha": [0, 50, 100, 150], "start": "after reset: crane (0,0,1), T=0, M=0",
                       "fallback": "on ErrCode 1 FB10 retries with order 1 -> 0; order_used per set"},
            "cmd_codes": "1 lift, 2 put, 3 move; phase 0 move-to-src (skipped if already there), 1 lift, 2 move-to-dst, 3 put",
            "sets": []}
    for p in paths:
        ds = cm.load_dataset(p)
        st = cp.build_state(ds)
        res = cp.plan_fb(st, cfg, [0, 50, 100, 150])
        entry = {"dataset": os.path.relpath(p, root).replace("\\", "/"), "N": st["N"],
                 "init_alarm_bits": st["init"]["bits"], "err": res["err"], "order_used": res["order"]}
        if res["err"] == 0:
            entry.update({"variant": res["variant"], "T_ds": res["T"], "M": res["M"], "J": round(res["J"], 6),
                          "commands": cp.simulate(st, res["plan"], res["cfg"])})
        gold["sets"].append(entry)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(gold, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
