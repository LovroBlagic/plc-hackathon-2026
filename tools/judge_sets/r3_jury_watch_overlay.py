"""r3 jury: what the PLC sees when a demo set is typed into a watch table as HUMAN_STEPS E.4.3 says
("type the values of watch_values.txt ... and press POCETNO STANJE") on top of the data already in
DB10/11/20/21 (the given toy data, or the live final yard of a previous run).
watch_values.txt lists only the NON-ZERO demo values, so the cells/entries that are non-zero in the
current data but zero in the demo set keep their old values.
Writes r3_jury_overlay_<demo>_on_<base>.json and prints init_validate + plan summary."""
import json, os, re, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import crane_model as cm

def overlay(base, watch_path):
    d = json.loads(json.dumps(base))
    rx_c = re.compile(r'"Current_state_of_Bay(\d)"\.Bay\d\[(\d+),(\d+)\] := (\d+)')
    rx_l = re.compile(r'"(From_Bay0_to_Bay1|From_Bay1_to_Bay0)"\.\w+\[(\d+)\] := (\d+)')
    n = 0
    for line in open(watch_path, encoding="utf-8"):
        m = rx_c.search(line)
        if m:
            b, x, y, v = map(int, m.groups()); d["bay%d" % b][x][y] = v; n += 1; continue
        m = rx_l.search(line)
        if m:
            k = "unload" if m.group(1) == "From_Bay0_to_Bay1" else "load"
            d[k][int(m.group(2)) - 1] = int(m.group(3)); n += 1
    return d, n

def summary(tag, ds):
    iv = cm.init_validate(ds)
    L, R = cm.lr(ds["bay0"])
    pu = sum(1 for s in iv["UState"] if s == 0); pl = sum(1 for s in iv["LState"] if s == 0)
    print("%-40s N=%d pending U=%d L=%d  bits=%s  ship L=%d R=%d" % (tag, iv["N"], pu, pl, iv["bits"], L, R))

given = cm.load_dataset(os.path.join(ROOT, "tia-src", "given_data.json"))
for demo, src in (("fig1_half", "r1_jury_fig1_half.json"), ("listcheck_bogus_unload", None)):
    wp = os.path.join(ROOT, "tools", "demo_db", demo, "watch_values.txt")
    ov, n = overlay(given, wp)
    ov["name"] = "r3_jury_overlay_%s_on_given" % demo
    ov["note"] = "r3 jury: given toy data + only the %d non-zero values of tools/demo_db/%s/watch_values.txt" % (n, demo)
    out = os.path.join(HERE, ov["name"] + ".json")
    json.dump(ov, open(out, "w"), indent=1)
    print("watch lines applied:", n, "->", out)
    if src:
        summary("intended " + demo, cm.load_dataset(os.path.join(HERE, src)))
    summary("overlay  " + demo, ov)
    # what is left over from the given data
    left = [(b, x, y, ov["bay%d" % b][x][y]) for b in (0, 1) for x in range(4) for y in range(12)
            if given["bay%d" % b][x][y] and ov["bay%d" % b][x][y] == given["bay%d" % b][x][y]]
    print("   leftover given cells:", left)
    print("   leftover list entries U:", [(i + 1, v) for i, v in enumerate(ov["unload"]) if v and v == given["unload"][i]],
          " L:", [(i + 1, v) for i, v in enumerate(ov["load"]) if v and v == given["load"][i]])
