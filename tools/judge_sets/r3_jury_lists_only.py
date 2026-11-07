"""r3 jury: FB10 v1.5 data-load path when ONLY DB20/DB21 are rewritten online (watch table) after a run,
modelled with the team's own transliteration tools/fb10_init_model.FB10.
Same scenario as fb10_init_model.scenario(), plus the change kind 'lists' that its selftest does not cover.
Expected by a jury that leaves DB10/DB11 untouched: the yard of the loaded data (A), as with 'none'."""
import copy, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm, crane_plan as cp
from fb10_init_model import FB10, _lists

def run(A, Blists, ntr, change):
    fb = FB10()
    DB10, DB11 = copy.deepcopy(A["bay0"]), copy.deepcopy(A["bay1"])
    DB20, DB21 = _lists(A)
    fb.State = 1; fb.init_step3(DB10, DB11, DB20, DB21)
    res = cp.plan_fb(cp.build_state(A), {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300])
    fb.State = 3
    for tr in res["plan"][:ntr]:
        (sx, sy, sb), (dx, dy, db) = tr["src"], tr["dst"]
        g = (fb.W0, fb.W1)
        g[db][dx][dy], g[sb][sx][sy] = g[sb][sx][sy], 0
        fb.region_2a(DB10, DB11)
    fb.State = 6 if ntr >= len(res["plan"]) else 4
    fb.region_2a(DB10, DB11)
    if change == "lists":
        DB20, DB21 = _lists(Blists)
    for _ in range(3):
        fb.region_2a(DB10, DB11)
    fb.State = 1; fb.init_step3(DB10, DB11, DB20, DB21)
    moved = sum(1 for b, W in ((0, fb.W0), (1, fb.W1)) for x in range(4) for y in range(12) if W[x][y] != A["bay%d" % b][x][y])
    return moved, cm.init_validate({"bay0": fb.W0, "bay1": fb.W1, "unload": DB20, "load": DB21})

A = cm.load_dataset(os.path.join(HERE, "..", "crane_data", "rand_05.json"))
# B = same yard, lists in reverse order (a jury re-running the same yard with another list order)
B = copy.deepcopy(A)
B["unload"] = [v for v in reversed([v for v in A["unload"] if v])] + [0] * (48 - sum(1 for v in A["unload"] if v))
B["load"] = [v for v in reversed([v for v in A["load"] if v])] + [0] * (48 - sum(1 for v in A["load"] if v))
B["name"] = "r3_jury_lists_only_rand05_reversed"; B["note"] = "r3 jury: rand_05 yard, both lists reversed (lists-only online change)"
import json; json.dump(B, open(os.path.join(HERE, B["name"] + ".json"), "w"), indent=1)
for change in ("none", "lists"):
    for ntr in (3, 999):
        moved, iv = run(A, B, ntr, change)
        pu = sum(1 for s in iv["UState"] if s == 0); pl = sum(1 for s in iv["LState"] if s == 0)
        print("change=%-5s after %-4s transfers: cells differing from loaded yard A after INIT = %2d ; pending U=%d L=%d (of %d/%d), alarm bits %s" % (
            change, "all" if ntr == 999 else ntr, moved, pu, pl, sum(1 for v in B["unload"] if v), sum(1 for v in B["load"] if v), iv["bits"]))
