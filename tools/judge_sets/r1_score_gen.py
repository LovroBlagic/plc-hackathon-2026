"""r1_score_gen.py - adversarial dataset families for the SCORE judge (round 1).
Writes tools/judge_sets/r1_score_<name>.json (same format as tools/crane_data).

  python tools/judge_sets/r1_score_gen.py
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402

CELLS = [(x, y) for x in range(4) for y in range(12)]


def blank():
    return [[0] * 12 for _ in range(4)]


def pad(lst):
    return list(lst) + [0] * (48 - len(lst))


def save(name, bay0, bay1, unload, load, note):
    d = {"name": "r1_score_" + name, "bay0": bay0, "bay1": bay1, "unload": pad(unload), "load": pad(load),
         "note": note}
    L, R = cm.lr(bay0)
    assert abs(L - R) <= 5 or "imbal" in name, (name, L, R)
    ids = [v for b in (bay0, bay1) for c in b for v in c if v]
    assert len(ids) == len(set(ids)), name
    iv = cm.init_validate(d)
    assert not iv["blocking"], name
    with open(os.path.join(HERE, "r1_score_%s.json" % name), "w") as f:
        json.dump(d, f)
    return d


def place(cells, rng_ids):
    g = blank()
    out = []
    for (x, y) in cells:
        g[x][y] = rng_ids.pop()
        out.append(g[x][y])
    return g, out


def fam(rng, name, ship_cells, yard_cells, u_pick, l_pick, shuffle_lists=True, note=""):
    ids = rng.sample(range(100, 1000), len(ship_cells) + len(yard_cells))
    bay0 = blank()
    bay1 = blank()
    ship_ids = {}
    yard_ids = {}
    for (x, y) in ship_cells:
        v = ids.pop()
        bay0[x][y] = v
        ship_ids[(x, y)] = v
    for (x, y) in yard_cells:
        v = ids.pop()
        bay1[x][y] = v
        yard_ids[(x, y)] = v
    unload = [ship_ids[c] for c in u_pick]
    load = [yard_ids[c] for c in l_pick]
    if shuffle_lists:
        rng.shuffle(unload)
        rng.shuffle(load)
    return save(name, bay0, bay1, unload, load, note)


def balanced_cells(rng, n):
    nl = n // 2
    left = [c for c in CELLS if c[0] <= 1]
    right = [c for c in CELLS if c[0] >= 2]
    return rng.sample(left, nl) + rng.sample(right, n - nl)


def main():
    rng = random.Random(2026)
    made = []
    # 1. N=1 / N=2 trivial
    made.append(fam(rng, "n1_unload", [(1, 5), (2, 5)], [(0, 0)], [(1, 5)], [], note="N=1 unload"))
    made.append(fam(rng, "n2_mixed", [(0, 11), (3, 11)], [(3, 0), (0, 11)], [(0, 11)], [(0, 11)], note="N=2"))
    made.append(fam(rng, "n2_far", [(0, 0), (3, 0), (0, 11), (3, 11)], [(0, 11)], [(0, 0), (3, 11)], [],
                    note="2 unloads far apart"))
    # 2. corner: all unloads in ship far corner x=0 rows 0-5; loads in yard x=0 rows 6-11
    ship = [(x, y) for x in (0, 1) for y in range(0, 6)] + [(x, y) for x in (2, 3) for y in range(0, 6)]
    yard = [(0, y) for y in range(6, 12)] + [(1, y) for y in range(6, 12)]
    made.append(fam(rng, "corner", ship, yard, [(0, y) for y in range(6)] + [(1, y) for y in range(3)],
                    [(0, y) for y in range(6, 12)], note="corner sources"))
    # 3. scattered rows: unloads alternate y 0/11, loads alternate y 11/0
    ship = balanced_cells(rng, 30)
    yard = rng.sample(CELLS, 20)
    us = sorted([c for c in ship if c[1] in (0, 1, 10, 11)])[:8]
    ls = sorted([c for c in yard if c[1] in (0, 1, 10, 11)])[:8]
    made.append(fam(rng, "scatter_y", ship, yard, us, ls, note="sources at y extremes"))
    # 4. unequal lengths: many unloads, few loads
    for i in range(3):
        ship = balanced_cells(rng, 40)
        yard = rng.sample(CELLS, 6)
        us = rng.sample([c for c in ship], 30)
        ls = rng.sample(yard, 2)
        # keep balance feasible: random; checked by planner
        made.append(fam(rng, "unequal_u%d" % i, ship, yard, us, ls, note="30 U / 2 L"))
    for i in range(3):
        ship = balanced_cells(rng, 10)
        yard = rng.sample(CELLS, 40)
        us = rng.sample(ship, 2)
        ls = rng.sample(yard, 30)
        made.append(fam(rng, "unequal_l%d" % i, ship, yard, us, ls, note="2 U / 30 L"))
    # 5. nearly full yard with unloads: yard col 3 full -> forced far drops
    ship = balanced_cells(rng, 36)
    yard = [(x, y) for x in (2, 3) for y in range(12)] + rng.sample([(x, y) for x in (0, 1) for y in range(12)], 8)
    us = rng.sample(ship, 14)
    made.append(fam(rng, "yard_near_full", ship, yard, us, [], note="yard cols 2,3 full"))
    # load list forcing far drops: ship cols near yard? ship x=0 is nearest the yard (G=6).
    ship = [(x, y) for x in (0, 1) for y in range(12)][:22] + [(x, y) for x in (2, 3) for y in range(12)][:22]
    yard = rng.sample(CELLS, 30)
    ls = rng.sample(yard, 4)
    made.append(fam(rng, "ship_near_full_load", ship, yard, [], ls, note="ship 44 full, 4 loads"))
    # 6. N=96 is infeasible by construction (both bays full, no free cell); N=95/94 near-full swaps
    for i in range(2):
        ship = list(CELLS)
        ship.remove(rng.choice(CELLS))
        yard = list(CELLS)
        made.append(fam(rng, "n95_%d" % i, ship, yard, list(ship), list(CELLS), note="N=95 swap, 1 free ship cell"))
    ship = [c for c in CELLS if c not in ((0, 0), (3, 11))]
    yard = [c for c in CELLS if c != (1, 6)]
    made.append(fam(rng, "n93_free3", ship, yard, list(ship), list(yard), note="N=93 swap, 3 free cells"))
    # 7. random medium with mixed structures
    for i in range(8):
        ns = rng.randint(20, 46)
        ny = rng.randint(10, 46)
        ship = balanced_cells(rng, ns)
        yard = rng.sample(CELLS, ny)
        nu = rng.randint(0, min(ns, 30))
        nl = rng.randint(0, min(ny, 30))
        us = rng.sample(ship, nu)
        ls = rng.sample(yard, nl)
        if 48 - ny + nl < nu or 48 - ns + nu < nl:
            continue
        made.append(fam(rng, "mix_%d" % i, ship, yard, us, ls, note="random mix"))
    # 8. sorted lists (list order = far-to-near / alternating sides)
    ship = balanced_cells(rng, 40)
    yard = rng.sample(CELLS, 24)
    us = sorted(rng.sample(ship, 16), key=lambda c: (c[1] % 2, c[0]))
    ls = sorted(rng.sample(yard, 16), key=lambda c: (-c[1] % 2, -c[0]))
    made.append(fam(rng, "zigzag_lists", ship, yard, us, ls, shuffle_lists=False, note="zigzag list order"))
    print("wrote %d sets" % len(made))


if __name__ == "__main__":
    main()
