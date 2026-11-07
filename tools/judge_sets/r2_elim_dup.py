"""r2_elim_dup.py - judge round 2 (elimination): a bogus unload entry kills a valid load entry.

FB10 INIT (21_FB_CraneControl.scl lines 727-734) and crane_model.init_validate mark a list entry as
'duplicate' (state 2, skipped) when the same ID appeared in ANY earlier list entry, also an entry that
was itself rejected (bit 3 'unload ID not in Bay 0'). UList is scanned before LList, so a container
that sits in Bay 1 and is in the LOAD list is never loaded if the unload list (wrongly) names it too.
That is exactly the spec's example alarm case ("ID kontejnera postoji u listi za istovar, ali ne postoji
u polju Bay 0") with the ID taken from the yard.

  python tools/judge_sets/r2_elim_dup.py            # builds the dataset(s), runs the team planner
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402
import crane_gen as cg    # noqa: E402

AL = [0, 100, 200, 300]
CFG = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}


def run(ds, tag):
    st = cp.build_state(ds)
    iv = st["init"]
    res = cp.plan_fb(st, CFG, AL, imp_evals=0)
    moved = {(tr["kind"], tr["id"]) for tr in res.get("plan", [])}
    lost = []
    for j, cid in enumerate(ds["load"]):
        if cid and cm.valid_id(cid):
            in_b1 = any(cid in col for col in ds["bay1"])
            in_b0 = any(cid in col for col in ds["bay0"])
            if in_b1 and not in_b0 and (2, cid) not in moved:
                lost.append((j + 1, cid, iv["LState"][j]))
    print("%-38s bits=%s err=%d plan_len=%d  VALID load entries NOT executed: %s" % (
        tag, iv["bits"], res["err"], len(res.get("plan", [])), lost))
    return lost


def main():
    rng = random.Random(2026)
    out = []
    # 1) minimal hand-made set: yard container 555 is in the load list; unload list wrongly names it too
    bay0, bay1 = cg.blank(), cg.blank()
    for k, (x, y) in enumerate([(0, 0), (1, 0), (2, 0), (3, 0)]):
        bay0[x][y] = 101 + k
    bay1[0][0], bay1[0][1], bay1[1][0] = 555, 556, 557
    ds = cg.ds_dict("r2_elimination_bogus_unload_kills_load", bay0, bay1,
                    [101, 555, 103], [555, 556],
                    "unload list names yard container 555 (spec alarm 'ID ... ne postoji u polju Bay 0'); "
                    "555 is also in the load list and must be loaded. Team: load entry 1 skipped as duplicate.")
    out.append(ds)
    # 2) realistic: team random set rand_05 + one bogus unload entry taken from the load list
    base = cm.load_dataset(os.path.join(HERE, "..", "crane_data", "rand_05.json"))
    ld = [c for c in base["load"] if c]
    if ld:
        victim = ld[len(ld) // 2]
        un = [c for c in base["unload"] if c]
        un.insert(1, victim)
        ds2 = cg.ds_dict("r2_elimination_rand05_bogus_unload", base["bay0"], base["bay1"], un, ld,
                         "rand_05 + unload entry 2 = %d, a yard container that is also in the load list" % victim)
        out.append(ds2)
    total = 0
    for d in out:
        p = os.path.join(HERE, d["name"] + ".json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f)
        total += len(run(cm.load_dataset(p), d["name"]))
    print("R2_DUP_RESULT lost_valid_load_entries=%d" % total)


if __name__ == "__main__":
    main()
