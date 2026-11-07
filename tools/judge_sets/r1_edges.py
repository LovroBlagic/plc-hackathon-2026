"""r1_edges.py - judge round 1: hand-crafted extreme datasets (full bays, 1 free cell, 48-entry lists,
list holes, duplicates, IDs already at destination, unbalanced-at-limit). Writes them to
tools/judge_sets/r1_elimination_<name>.json and runs each through plan_fb (PLC default: order 1 +
fallback, 3000 improve evals), the exact DP (r1_feas) and the team's simulate().

  python tools/judge_sets/r1_edges.py
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402
import r1_feas as rf      # noqa: E402

CELLS = [(x, y) for x in range(4) for y in range(12)]


def blank():
    return [[0] * 12 for _ in range(4)]


def pad(l):
    return list(l) + [0] * (48 - len(l))


def save(name, bay0, bay1, un, ld, note):
    d = {"name": "r1_elimination_" + name, "bay0": bay0, "bay1": bay1, "unload": pad(un), "load": pad(ld),
         "note": "judge r1: " + note}
    p = os.path.join(HERE, d["name"] + ".json")
    with open(p, "w") as f:
        json.dump(d, f)
    return p


def build():
    rng = random.Random(4242)
    out = []
    ids = rng.sample(range(100, 1000), 200)
    # 1 ship full 48, yard 47 (1 free), unload all 48 shuffled, load all 47 -> 95 transfers, 1 free cell
    b0, b1 = blank(), blank()
    for (x, y) in CELLS:
        b0[x][y] = ids.pop()
    free1 = rng.choice(CELLS)
    for (x, y) in CELLS:
        if (x, y) != free1:
            b1[x][y] = ids.pop()
    un = [b0[x][y] for (x, y) in CELLS]
    rng.shuffle(un)
    ld = [b1[x][y] for (x, y) in CELLS if b1[x][y]]
    rng.shuffle(ld)
    out.append(save("full_95_onefree", b0, b1, un, ld, "ship 48 full, yard 47, unload 48, load 47 (95 transfers)"))
    # 2 ship 47, yard 48 full: no free yard cell -> first transfer must be a load
    ids = rng.sample(range(100, 1000), 200)
    b0, b1 = blank(), blank()
    free0 = (3, 11)
    for (x, y) in CELLS:
        if (x, y) != free0:
            b0[x][y] = ids.pop()
        b1[x][y] = ids.pop()
    un = [b0[x][y] for (x, y) in CELLS if b0[x][y]]
    rng.shuffle(un)
    ld = [b1[x][y] for (x, y) in CELLS]
    rng.shuffle(ld)
    out.append(save("full_95_yardfull", b0, b1, un, ld, "ship 47, yard 48 full, unload 47, load 48 (95 transfers)"))
    # 3 unload-only, all from the left half, ship L=24 R=19 (|5|): needs loads? none -> impossible beyond 0
    ids = rng.sample(range(100, 1000), 200)
    b0, b1 = blank(), blank()
    for (x, y) in CELLS:
        if x <= 1 or (x >= 2 and len([1 for xx in (2, 3) for yy in range(12) if b0[xx][yy]]) < 19):
            b0[x][y] = ids.pop()
    for (x, y) in rng.sample(CELLS, 10):
        b1[x][y] = ids.pop()
    lefts = [b0[x][y] for x in (0, 1) for y in range(12)]
    rights = [b0[x][y] for x in (2, 3) for y in range(12) if b0[x][y]]
    # unload list alternates sides in an order where list order forces a temporary imbalance
    un = lefts[:12] + rights[:12]
    ld = []
    out.append(save("unload_only_leftfirst", b0, b1, un, ld, "ship L24/R19, unload 12 left then 12 right, no loads"))
    # 4 holes + duplicates + invalid + already-at-destination entries
    ids = rng.sample(range(100, 1000), 200)
    b0, b1 = blank(), blank()
    for (x, y) in rng.sample(CELLS, 30):
        b0[x][y] = ids.pop()
    for (x, y) in rng.sample(CELLS, 20):
        b1[x][y] = ids.pop()
    s0 = [v for c in b0 for v in c if v]
    s1 = [v for c in b1 for v in c if v]
    un = [0, s0[0], 0, s0[1], s0[1], 1234, s1[0], 0, s0[2], 99, s0[3]] + [0] * 30 + [s0[4]]
    ld = [s1[1], 0, s0[5], s1[1], s0[0], s1[2]] + [0] * 41 + [s1[3]]
    out.append(save("holes_dups_invalid", b0, b1, un[:48], ld[:48],
                    "list holes, dup in same list, dup across lists, invalid IDs, unload ID that is in Bay1, load ID in Bay0, entries at index 48"))
    return out


def run(p):
    ds = cm.load_dataset(p)
    st = cp.build_state(ds)
    iv = st["init"]
    feas = None if iv["blocking"] else {o: rf.feasible(ds, st, o) for o in (1, 2, 0)}
    print("==", os.path.basename(p), "N=%d pending=%d bits=%s blocking=%s LR=%s" % (
        iv["N"], len(st["PU"]) + len(st["PL"]), iv["bits"], iv["blocking"], cm.lr(ds["bay0"])))
    if iv["blocking"]:
        return
    print("   exact feasible order1/2/0:", feas[1], feas[2], feas[0])
    res = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300], imp_evals=3000)
    print("   plan_fb err=%d order_used=%s len=%d J=%s" % (res["err"], res.get("order"), len(res.get("plan", [])), res.get("J")))
    if res["err"] == 0:
        cp.simulate(st, res["plan"], res["cfg"])
        print("   simulate OK")


if __name__ == "__main__":
    for p in build():
        run(p)
