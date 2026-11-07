#!/usr/bin/env python3
"""tags_xlsx_gen.py - HMI tag table HMI_IF_gen as a TIA GUI-importable .xlsx (WinCC RT Advanced, V21).

Source of truth for the tag list: hmi-tia/out/tags/HMI_IF_gen.xml (written by gen_hmi.py).
Format template: hmi-tia/export/HMITags_sample.xlsx (exported from the real TIA GUI; sheets 'Hmi Tags' + 'Multiplexing').
The sample is copied with openpyxl, its data rows are dropped, and one row per tag is written in its column layout.

  python hmi-tia/tags_xlsx_gen.py [--path HMI_IF_gen] [--cycle "100 ms"] [--mode "Cyclic in operation"]

Checks (CHECK line): every PLC member exists in tia-src/03_HMI_IF.db (array index within bounds, data type equal),
names unique, every tag name the generated screens (out/screens/*.xml) reference is present.
"""
import argparse, glob, os, re, sys
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SAMPLE = os.path.join(HERE, "export", "HMITags_sample.xlsx")
TAGS_XML = os.path.join(HERE, "out", "tags", "HMI_IF_gen.xml")
DB = os.path.join(ROOT, "tia-src", "03_HMI_IF.db")
OUT = os.path.join(HERE, "out", "xlsx", "HMI_IF_gen_tags.xlsx")

# (Length, Coding) per PLC data type, as TIA shows them (sample: Bool 1 Binary, Real 4 IEEE754)
TYPEINFO = {"Bool": (1, "Binary"), "SInt": (1, "Binary"), "USInt": (1, "Binary"), "Byte": (1, "Binary"),
            "Int": (2, "Binary"), "UInt": (2, "Binary"), "Word": (2, "Binary"),
            "DInt": (4, "Binary"), "UDInt": (4, "Binary"), "DWord": (4, "Binary"), "Real": (4, "IEEE754")}


def read_tags():
    x = open(TAGS_XML, encoding="utf-8-sig").read()
    out = []
    for t in re.findall(r"<Hmi\.Tag\.Tag .*?</Hmi\.Tag\.Tag>", x, re.S):
        g = lambda tag: (re.search(r"<%s[ >].*?<Name>(.*?)</Name>" % tag, t, re.S) or [None, None])[1]
        name = re.search(r"<AttributeList>.*?<Name>(.*?)</Name>", t, re.S).group(1)
        com = re.search(r"<Text>(.*?)</Text>", t, re.S)
        out.append(dict(name=name, plc=g("ControllerTag"), dt=g("DataType"), conn=g("Connection"),
                        cycle=g("AcquisitionCycle"), comment=com.group(1) if com else None))
    return out


def read_db():
    members = {}
    for line in open(DB, encoding="utf-8-sig"):
        m = re.match(r"\s*(\w+)\s*:\s*(Array\[(\d+)\.\.(\d+)\]\s*of\s*(\w+)|\w+)", line)
        if m and m.group(1) not in ("VERSION",):
            if m.group(3):
                members[m.group(1)] = (m.group(5), int(m.group(3)), int(m.group(4)))
            else:
                members[m.group(1)] = (m.group(2), None, None)
    return members


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="HMI_IF_gen")
    ap.add_argument("--cycle", default="100 ms")
    ap.add_argument("--mode", default="Cyclic in operation")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    tags = read_tags()
    db = read_db()
    errs = []

    wb = openpyxl.load_workbook(SAMPLE)
    ws = wb["Hmi Tags"]
    hdr = [c.value for c in ws[1]]
    tmpl = [c.value for c in ws[3]] if ws.max_row >= 3 else [c.value for c in ws[2]]
    ws.delete_rows(2, ws.max_row)
    col = {h: i for i, h in enumerate(hdr)}

    names = set()
    for t in tags:
        if t["name"] in names:
            errs.append("dup name " + t["name"])
        names.add(t["name"])
        m = re.match(r"HMI_IF\.(\w+)(?:\[(\d+)\])?$", t["plc"] or "")
        if not m or m.group(1) not in db:
            errs.append("no PLC member %s (%s)" % (t["plc"], t["name"]))
        else:
            dt, lo, hi = db[m.group(1)]
            if (m.group(2) is None) != (lo is None):
                errs.append("array/scalar mismatch " + t["plc"])
            elif m.group(2) is not None and not (lo <= int(m.group(2)) <= hi):
                errs.append("index out of bounds " + t["plc"])
            if dt != t["dt"]:
                errs.append("type %s vs DB %s for %s" % (t["dt"], dt, t["plc"]))
        if t["dt"] not in TYPEINFO:
            errs.append("unknown type " + str(t["dt"]))
        ln, coding = TYPEINFO.get(t["dt"], (None, None))
        row = list(tmpl)
        row[col["Name"]] = t["name"]
        row[col["Path"]] = a.path
        row[col["Connection"]] = t["conn"] or "HMI_Connection_1"
        row[col["PLC tag"]] = t["plc"]
        row[col["DataType"]] = t["dt"]
        row[col["Length"]] = ln
        row[col["Coding"]] = coding
        row[col["Acquisition mode"]] = a.mode
        row[col["Acquisition cycle"]] = a.cycle
        ws.append(row)

    # tag names referenced by the generated screens
    refs = set()
    for f in glob.glob(os.path.join(HERE, "out", "screens", "*.xml")):
        s = open(f, encoding="utf-8-sig").read()
        for blk in re.findall(r"<(?:Tag|ProcessValue|TagName)[^>]*>.*?</(?:Tag|ProcessValue|TagName)>", s, re.S):
            refs.update(re.findall(r"<Name>([^<]+)</Name>", blk))
        refs.update(re.findall(r"HMI_IF_gen\?[/\.]?([A-Za-z_]\w*)", s))
    rf = os.path.join(HERE, "out_notags", "referenced_tags.txt")  # list from the HMI agent (names the screens use)
    if os.path.exists(rf):
        refs.update(l.strip() for l in open(rf, encoding="utf-8-sig") if l.strip())
    missing = sorted(r for r in refs if r not in names and r not in ("time",))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    wb.save(a.out)
    print("WROTE %s rows=%d sheet='Hmi Tags' cols=%d path=%s cycle=%s" % (a.out, len(tags), len(hdr), a.path, a.cycle))
    print("SCREEN_REFS %d distinct, missing in table: %d %s" % (len(refs), len(missing), missing[:20]))
    for e in errs[:30]:
        print("ERR", e)
    print("CHECK %s tags=%d unique=%s plc_errors=%d screen_missing=%d" % (
        "OK" if not errs and not missing else "FAIL", len(tags), len(names) == len(tags), len(errs), len(missing)))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
