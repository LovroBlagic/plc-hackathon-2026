"""json_to_db.py - write SCL DATA_BLOCK sources for DB10/DB11/DB20/DB21 from a crane dataset JSON.

Judge round 2 (R2-J2): the given start values (tia-src/given_data.json) contain 0 executable transfers, so a
demo or a PLCSIM test needs another data set inside the PLC. This tool writes the four given data blocks with
the start values of any tools/crane_data*/ or tools/judge_sets/ JSON file, in exactly the format of the
original blocks (tia-work/export/src/DB1x_*.db: same names, same members, optimized, NON_RETAIN).

  python tools/json_to_db.py <dataset.json> [--out <dir>]      (default: tia-work/demo_db/<dataset name>/)

It writes 10_DB10_Current_state_of_Bay0.db, 11_DB11_Current_state_of_Bay1.db, 20_DB20_From_Bay0_to_Bay1.db,
21_DB21_From_Bay1_to_Bay0.db and numbers.txt (DB10/11/20/21 keep their numbers).

!! ONLY for a TEST / DEMO COPY of the project. The deliverable must keep the organizers' DB10/11/20/21.
   Import into a copy (retrieve deliver/TIA_crane_v1_plc.zap21 into another folder first):
     TiaRun.exe --project <COPY dir> --headless --lock demo --src <out dir> --numbers <out dir>/numbers.txt
   After the download the PLC does STOP -> RUN, the NON_RETAIN DBs start with these values, then press
   POČETNO STANJE on the HMI (FB10 takes them as new data: DB10/DB11 differ from its snapshot).
   Online alternative without a download: write the same values with a watch table (the file
   <out dir>/watch_values.txt lists ALL 96 cells and 96 list entries, zeros included, as "address := value";
   v1.6, judge round 3 R3-J1: writing only the non-zero values leaves the old data behind).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crane_model as cm  # noqa: E402

HEAD = 'DATA_BLOCK "%s"\n{ S7_Optimized_Access := \'TRUE\' }\nVERSION : 0.1\nNON_RETAIN\n   VAR \n      %s : %s;\n   END_VAR\n\n\nBEGIN\n'


def grid_db(name, member, grid):
    out = [HEAD % (name, member, "Array[0..3, 0..11] of UInt")]
    for x in range(4):
        for y in range(12):
            out.append("   %s[%d,%d] := %d;\n" % (member, x, y, grid[x][y]))
    out.append("\nEND_DATA_BLOCK\n\n")
    return "".join(out)


def list_db(name, member, lst):
    lst = list(lst) + [0] * (48 - len(lst))
    out = [HEAD % (name, member, "Array[1..48] of UInt")]
    for i in range(48):
        out.append("   %s[%d] := %d;\n" % (member, i + 1, lst[i]))
    out.append("\nEND_DATA_BLOCK\n\n")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--out")
    a = ap.parse_args()
    ds = cm.load_dataset(a.dataset)
    name = ds.get("name") or os.path.splitext(os.path.basename(a.dataset))[0]
    out = a.out or os.path.join(os.path.dirname(HERE), "tia-work", "demo_db", name)
    os.makedirs(out, exist_ok=True)
    files = {
        "10_DB10_Current_state_of_Bay0.db": grid_db("Current_state_of_Bay0", "Bay0", ds["bay0"]),
        "11_DB11_Current_state_of_Bay1.db": grid_db("Current_state_of_Bay1", "Bay1", ds["bay1"]),
        "20_DB20_From_Bay0_to_Bay1.db": list_db("From_Bay0_to_Bay1", "IDs_of_the_containers", ds["unload"]),
        "21_DB21_From_Bay1_to_Bay0.db": list_db("From_Bay1_to_Bay0", "Bay1_IDs_of_the_containers", ds["load"]),
        "numbers.txt": "# DB numbers of the given blocks (unchanged)\nCurrent_state_of_Bay0=DB:10\n"
                       "Current_state_of_Bay1=DB:11\nFrom_Bay0_to_Bay1=DB:20\nFrom_Bay1_to_Bay0=DB:21\n",
    }
    w = []
    for b, nm, mem in ((0, "Current_state_of_Bay0", "Bay0"), (1, "Current_state_of_Bay1", "Bay1")):
        g = ds["bay%d" % b]
        for x in range(4):
            for y in range(12):
                # v1.6 (judge round 3 R3-J1): EVERY cell, zeros included. Typing only the non-zero values
                # over another data set leaves its containers / list entries behind.
                w.append('"%s".%s[%d,%d] := %d' % (nm, mem, x, y, g[x][y]))
    for nm, mem, lst in (("From_Bay0_to_Bay1", "IDs_of_the_containers", ds["unload"]),
                         ("From_Bay1_to_Bay0", "Bay1_IDs_of_the_containers", ds["load"])):
        lst = list(lst) + [0] * (48 - len(lst))
        for i, v in enumerate(lst):
            w.append('"%s".%s[%d] := %d' % (nm, mem, i + 1, v))
    files["watch_values.txt"] = ("# ALL 96 cells + 96 list entries, zeros included: write every line, then POCETNO STANJE.\n"
                                 "# Preferred: import the .db files into a TEST COPY and download instead.\n"
                                 + "\n".join(w) + "\n")
    for fn, txt in files.items():
        with open(os.path.join(out, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
    iv = cm.init_validate(ds)
    pu = sum(1 for s in iv["UState"] if s == 0)
    pl = sum(1 for s in iv["LState"] if s == 0)
    L, R = cm.lr(ds["bay0"])
    print("JSON_TO_DB %s -> %s  (unloads %d, loads %d, alarm bits %s, ship L=%d R=%d)" % (
        name, out, pu, pl, iv["bits"], L, R))


if __name__ == "__main__":
    main()
