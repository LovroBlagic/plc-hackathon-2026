#!/usr/bin/env python3
"""alarms_gen.py - discrete alarms for HMI_IF.AlarmWord (CONTRACT §3.3) as an importable .xlsx (stdlib, no openpyxl)
plus .csv/.json.  WinCC RT Advanced: HMI alarms editor -> Discrete alarms -> Import (button) -> select the xlsx.

  python alarms_gen.py [--sample exported.xlsx] [--out hmi-tia/out/alarms] [--trigger-tag AlarmWord]

--sample: an .xlsx exported by TIA from ONE hand-made discrete alarm. Its header row (column names, sheet name) is
reused, so the import matches the installed TIA exactly. Without it, the V21 default column set below is used.
Trigger bit n = bit n of the PLC Word value (HMI_IF.AlarmWord.%Xn). After import check in the alarm editor that
alarm 4 ("Unload ID not in Bay 0", bit 3) shows trigger address bit 3 of AlarmWord.
"""
import argparse, csv, json, os, re, zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))

# bit, class key, HR text, EN text  (CONTRACT §3.3, verbatim)
ALARMS = [
    (0, "blocking", "Neuravnoteženost broda: razlika lijeve i desne polovice > 5", "Ship imbalance |L-R| > 5"),
    (1, "blocking", "Lokacija s koje se podiže kontejner je prazna", "Pick location empty"),
    (2, "blocking", "Lokacija na koju se spušta kontejner je zauzeta", "Drop location occupied"),
    (3, "warning", "ID kontejnera postoji u listi za istovar, ali ne postoji u polju Bay 0", "Unload ID not in Bay 0"),
    (4, "warning", "ID kontejnera postoji u listi za ukrcaj, ali ne postoji u polju Bay 1", "Load ID not in Bay 1"),
    (5, "warning", "Neispravan ID kontejnera (izvan 100–999)", "Invalid container ID"),
    (6, "warning", "Dvostruki ID kontejnera", "Duplicate container ID"),
    (7, "blocking", "Nema slobodnog mjesta u odredišnom polju", "No free slot"),
    (8, "blocking", "Plan istovara/ukrcaja nije izvediv", "Plan infeasible"),
    (9, "warning", "Neispravna ručna naredba (Bay mora biti 0/1, x 0–3, y 0–11)", "Invalid manual command"),
    (10, "blocking", "Dizalica nije izvršila naredbu (timeout)", "FB1 timeout"),
    (11, "blocking", "Dizalica već nosi kontejner", "Crane already carrying"),
    (12, "blocking", "Dizalica ne nosi kontejner", "Crane is empty (put down)"),
    (13, "warning", "Sustav nije inicijaliziran: pritisnite POČETNO STANJE", "Not initialized"),
    (14, "warning", "Položaj dizalice ne odgovara naredbi", "Crane position mismatch after move"),
    (15, "info", "Istovar i ukrcaj završeni", "Unloading and loading finished"),
]
# RT Advanced default classes: "Errors" (must be acknowledged), "Warnings" (no ack). "System" is reserved for
# system events in RT Advanced, so the info alarm uses "Warnings" by default; change with --info-class.
CLASS = {"blocking": "Errors", "warning": "Warnings", "info": "Warnings"}

DEFAULT_SHEET = "DiscreteAlarms"
DEFAULT_HEADERS = ["ID", "Name", "Alarm text [en-US], Alarm text", "FieldInfo [Alarm text]", "Class", "Trigger tag",
                   "Trigger bit", "Acknowledgement tag", "Acknowledgement bit", "PLC acknowledgement tag",
                   "PLC acknowledgement bit", "Group", "Report", "Info text [en-US], Info text"]


def row_values(headers, a, trigger, info_class):
    bit, cls, hr, en = a
    klass = info_class if cls == "info" else CLASS[cls]
    out = []
    for h in headers:
        k = h.lower()
        if k == "id": v = bit + 1
        elif k == "name": v = "Crane_bit%02d" % bit
        elif k.startswith("alarm text"): v = hr
        elif k.startswith("fieldinfo"): v = ""
        elif k == "class": v = klass
        elif k == "trigger tag": v = trigger
        elif k == "trigger bit": v = bit
        elif k.startswith("acknowledgement tag") or k.startswith("plc acknowledgement tag"): v = "<No value>"
        elif k.startswith("acknowledgement bit") or k.startswith("plc acknowledgement bit"): v = 0
        elif k == "group": v = "<No value>"
        elif k == "report": v = "False"
        elif k.startswith("info text"): v = "EN: %s. Blokirajući: %s. Bit %d u HMI_IF.AlarmWord." % (en, "DA" if cls == "blocking" else "NE", bit)
        else: v = ""
        out.append(v)
    return out


def col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, sheet, headers, rows):
    def cell(r, c, v):
        ref = "%s%d" % (col(c), r)
        if isinstance(v, int):
            return '<c r="%s"><v>%d</v></c>' % (ref, v)
        return '<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (ref, escape(str(v)))
    data = []
    for r, vals in enumerate([headers] + rows, start=1):
        data.append('<row r="%d">%s</row>' % (r, "".join(cell(r, c, v) for c, v in enumerate(vals))))
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="%s" sheetId="1" r:id="rId1"/></sheets></workbook>' % escape(sheet),
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>%s</sheetData></worksheet>' % "".join(data),
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in files.items():
            z.writestr(n, d)


def read_sample(path):
    """Header row + first sheet name of a TIA-exported xlsx (shared or inline strings)."""
    z = zipfile.ZipFile(path)
    wb = z.read("xl/workbook.xml").decode("utf-8")
    sheet = re.search(r'<sheet [^>]*name="([^"]+)"', wb).group(1)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        ss = z.read("xl/sharedStrings.xml").decode("utf-8")
        for si in re.findall(r"<si>(.*?)</si>", ss, re.S):
            shared.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)))
    s1 = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    row1 = re.search(r'<row [^>]*r="1"[^>]*>(.*?)</row>', s1, re.S).group(1)
    heads = []
    for attrs, body in re.findall(r"<c ([^>]*)>(.*?)</c>", row1, re.S):
        if 't="s"' in attrs:
            heads.append(shared[int(re.search(r"<v>(\d+)</v>", body).group(1))])
        else:
            heads.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", body, re.S)))
    unesc = lambda s: s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return sheet, [unesc(h) for h in heads]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "alarms"))
    ap.add_argument("--trigger-tag", default="AlarmWord")
    ap.add_argument("--info-class", default=CLASS["info"])
    a = ap.parse_args()
    sheet, headers = (read_sample(a.sample) if a.sample else (DEFAULT_SHEET, DEFAULT_HEADERS))
    rows = [row_values(headers, al, a.trigger_tag, a.info_class) for al in ALARMS]
    os.makedirs(a.out, exist_ok=True)
    write_xlsx(os.path.join(a.out, "crane_alarms.xlsx"), sheet, headers, rows)
    with open(os.path.join(a.out, "crane_alarms.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(headers)
        w.writerows(rows)
    with open(os.path.join(a.out, "crane_alarms.json"), "w", encoding="utf-8") as f:
        json.dump([{"bit": b, "class": c, "hr": hr, "en": en} for b, c, hr, en in ALARMS], f, indent=1, ensure_ascii=False)
    print("ALARMS %d -> %s (sheet '%s', %d columns%s)" % (len(rows), a.out, sheet, len(headers), ", headers from sample" if a.sample else ""))

if __name__ == "__main__":
    main()
