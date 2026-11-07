#!/usr/bin/env python3
"""gen_hmi.py - generate the crane HMI (WinCC RT Advanced, HMI Classic) from layout.json.

stdlib only. Everything is CLONED from human-made prototypes exported by HmiGen.exe --export,
so the generator never invents SimaticML schema it has not seen; it only patches geometry,
texts, tag links and a few known attributes.

  python gen_hmi.py all     [--export DIR] [--out DIR] [--layout layout.json]
  python gen_hmi.py tags    ...      -> OUT/tags/HMI_IF_gen.xml        (one HMI tag per HMI_IF member/element)
  python gen_hmi.py textlists ...    -> OUT/textlists/TL_*.xml
  python gen_hmi.py screens ...      -> OUT/screens/{Main,Manual,Lists,AlarmLog}.xml [+ OUT/templates/Tpl.xml]
  python gen_hmi.py check   [--out DIR]   validate generated XML (well-formed, unique IDs/ObjectNames, tag refs exist)

Prototype sources, searched in this order: --export DIR (HmiGen export: screens/Proto.xml, templates/Tpl.xml,
tags/<any>.xml, textlists/TL_State.xml), then hmi-tia/mock/ (dry-run only; mock schema is a best guess).

Prototype screen "Proto" must contain these ObjectNames (see README / HUMAN_STEPS):
  P_Text P_IO P_SymIO P_Btn P_NavBtn P_CellRect P_Lamp P_LampAlarm P_Bar P_CraneX P_CraneY   (+ optional P_BtnInv)
"""
import argparse, copy, json, os, re, sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REQUIRED_PROTOS = ["P_Text", "P_IO", "P_SymIO", "P_Btn", "P_NavBtn", "P_CellRect", "P_Lamp",
                   "P_LampAlarm", "P_Bar", "P_CraneX", "P_CraneY"]
TYPE_LEN = {"Bool": 1, "SInt": 1, "USInt": 1, "Byte": 1, "Int": 2, "UInt": 2, "Word": 2,
            "DInt": 4, "UDInt": 4, "Real": 4, "DWord": 4}

LOG = []
def log(msg):
    LOG.append(msg)
    print(msg)

# ------------------------------------------------------------------ XML helpers
def load(path):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return ET.ElementTree(ET.fromstring(data))

def save(tree, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    renumber_ids(tree.getroot())
    indent(tree.getroot())
    body = ET.tostring(tree.getroot(), encoding="unicode")
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n' + body + "\n")

def indent(el, level=0):
    """Pretty-print like TIA exports, but never touch the inside of <Text> (formatted <body><p> content)."""
    if el.tag == "Text" or len(el) == 0:
        return
    pad = "\n" + "  " * (level + 1)
    if not (el.text or "").strip():
        el.text = pad
    for c in el:
        indent(c, level + 1)
        c.tail = pad
    el[-1].tail = "\n" + "  " * level

def renumber_ids(root):
    n = 0
    for el in root.iter():
        if "ID" in el.attrib:
            el.set("ID", format(n, "X"))
            n += 1

def attrs(el):
    return el.find("AttributeList")

def get_attr(el, name):
    al = attrs(el)
    c = al.find(name) if al is not None else None
    return None if c is None else (c.text or "")

def set_attr(el, name, value, must=False):
    al = attrs(el)
    c = al.find(name) if al is not None else None
    if c is None:
        if must:
            if al is None:
                al = ET.SubElement(el, "AttributeList")
            c = ET.SubElement(al, name)
        else:
            return False
    c.text = str(value)
    return True

def own_objlist(el):
    return el.find("ObjectList")

def set_ml_text(ml, text):
    """Set every MultilingualTextItem/Text of a MultilingualText element, keeping the <body><p> form if present."""
    for t in ml.iter("Text"):
        if t.find("body") is not None:
            for c in list(t):
                t.remove(c)
            t.text = None
            body = ET.SubElement(t, "body")
            lines = str(text).split("§")   # multi-line text: <p>line1<br />line2</p> (format of real exports)
            p = ET.SubElement(body, "p")
            p.text = lines[0]
            for line in lines[1:]:
                br = ET.SubElement(p, "br")
                br.tail = line
        else:
            t.text = text

def set_texts(el, text):
    """Set the visible text(s) of a screen item / button (not HelpText/Tooltip)."""
    ol = own_objlist(el)
    hit = 0
    if ol is None:
        return 0
    for ml in ol.findall("MultilingualText"):
        cn = ml.get("CompositionName", "")
        if cn in ("HelpText", "Tooltip", "ToolTipText"):
            continue
        set_ml_text(ml, text)
        hit += 1
    return hit

def set_font(el, size=None, bold=None):
    for fi in el.iter("Hmi.Globalization.FontItem"):
        if size is not None:
            set_attr(fi, "FontSize", size)
        if bold is not None:
            set_attr(fi, "FontStyle", "Bold" if bold else "Regular")

def set_tag_links(el, tag):
    n = 0
    for t in el.iter("Tag"):
        if t.get("TargetID") == "@OpenLink" and t.find("Name") is not None:
            t.find("Name").text = tag
            n += 1
    # system-function parameters (SetBit/InvertBit ...): <FunctionListEntryParameter Name=Tag><LinkList><Value>
    for prm in el.iter("Hmi.Event.FunctionListEntryParameter"):
        if get_attr(prm, "Name") == "Tag":
            for v in prm.iter("Value"):
                if v.get("TargetID") == "@OpenLink" and v.find("Name") is not None:
                    v.find("Name").text = tag
                    n += 1
    return n

def set_textlist_link(el, tl):
    n = 0
    for t in el.iter():
        if t.tag in ("TextList", "TextListGraphicList") and t.get("TargetID") == "@OpenLink" and t.find("Name") is not None:
            t.find("Name").text = tl
            n += 1
    return n

def replace_text_values(el, old, new):
    n = 0
    for t in el.iter():
        if t.text == old:
            t.text = new
            n += 1
    return n

# ------------------------------------------------------------------ config / tags
class Cfg:
    def __init__(self, layout_path):
        with open(layout_path, encoding="utf-8") as f:
            self.L = json.load(f)
        self.base = os.path.dirname(os.path.abspath(layout_path))
        self.pal = self.L["palette"]
        self.members = parse_hmi_if(os.path.join(self.base, self.L["hmi_if_source"]))
        self.scale = float(self.L["canvas"].get("scale", 1.0))

    def color(self, c):
        if c is None:
            return None
        v = self.pal.get(c, c)
        return v if isinstance(v, str) else c

    def tag(self, ref):
        """HMI_IF member ref ('M', 'Cell0[5]') -> HMI tag name."""
        m = re.match(r"^(\w+)\[(\d+)\]$", ref)
        if not m:
            if ref not in self.members:
                raise SystemExit("layout refers to unknown HMI_IF member: " + ref)
            return ref
        name, i = m.group(1), int(m.group(2))
        mem = self.members.get(name)
        if mem is None or mem["lo"] is None or not (mem["lo"] <= i <= mem["hi"]):
            raise SystemExit("layout refers to bad array element: " + ref)
        if self.L["tag_mode"] == "element":
            return self.L["elem_name_fmt"].format(m=name, i=i)
        return self.L["array_ref_fmt"].format(m=name, i=i)


def parse_hmi_if(path):
    """Read-only parse of tia-src/03_HMI_IF.db (runtime-owned) -> {member: {type, lo, hi}} in declaration order."""
    out = {}
    with open(path, encoding="utf-8") as f:
        src = f.read()
    body = src.split("VAR", 1)[1].split("END_VAR", 1)[0]
    for m in re.finditer(r"^\s*(\w+)\s*:\s*(?:Array\[(\d+)\.\.(\d+)\]\s+of\s+(\w+)|(\w+))", body, re.M):
        if m.group(4):
            out[m.group(1)] = {"type": m.group(4), "lo": int(m.group(2)), "hi": int(m.group(3))}
        else:
            out[m.group(1)] = {"type": m.group(5), "lo": None, "hi": None}
    return out

# ------------------------------------------------------------------ prototype discovery
def find_file(dirs, sub, names):
    for d in dirs:
        if not d:
            continue
        for n in names:
            p = os.path.join(d, sub, n)
            if os.path.isfile(p):
                return p
        if names == ["*"]:
            p = os.path.join(d, sub)
            if os.path.isdir(p):
                xs = sorted(x for x in os.listdir(p) if x.lower().endswith(".xml"))
                if xs:
                    return os.path.join(p, xs[0])
    return None

def proto_dirs(args):
    # exactly ONE source dir: never mix real exports with mock pieces
    if args.export:
        return [os.path.abspath(args.export)]
    if os.path.isfile(os.path.join(HERE, "export", "screens", "Proto.xml")):
        return [os.path.join(HERE, "export")]
    return [os.path.join(HERE, "mock")]

# ------------------------------------------------------------------ tags
def gen_tags(cfg, args):
    dirs = proto_dirs(args)
    # prefer a tag table that contains a tag linked to HMI_IF
    src = None
    for d in dirs:
        p = os.path.join(d, "tags")
        if not os.path.isdir(p):
            continue
        for x in sorted(os.listdir(p)):
            if x.lower().endswith(".xml") and "HMI_IF" in open(os.path.join(p, x), encoding="utf-8-sig", errors="ignore").read() \
                    and not x.startswith(cfg.L["tag_table"]):
                src = os.path.join(p, x)
                break
        if src:
            break
    if src is None:
        raise SystemExit("no prototype tag table with an HMI_IF-linked tag found in " + str(dirs))
    log("tags: prototype " + src)
    tree = load(src)
    root = tree.getroot()
    table = next(e for e in root.iter() if e.tag.endswith("TagTable") and attrs(e) is not None)
    set_attr(table, "Name", cfg.L["tag_table"], must=True)
    ol = own_objlist(table)
    tags = [e for e in list(ol) if e.tag.endswith(".Tag") or e.tag == "Hmi.Tag.Tag"]
    proto = next(t for t in tags if "HMI_IF" in ET.tostring(t, encoding="unicode"))
    for t in tags:
        ol.remove(t)
    pref = None
    for lk in proto.iter("ControllerTag"):
        nm = lk.find("Name").text
        mm = re.match(r'^(.*HMI_IF"?\.)', nm)
        pref = mm.group(1) if mm else '"%s".' % cfg.L["plc_db"]
    count = 0
    for name, mem in cfg.members.items():
        idxs = [None] if mem["lo"] is None else list(range(mem["lo"], mem["hi"] + 1))
        if cfg.L["tag_mode"] != "element" and mem["lo"] is not None:
            log("tags: array mode not implemented for generation; use element mode")
            idxs = list(range(mem["lo"], mem["hi"] + 1))
        for i in idxs:
            t = copy.deepcopy(proto)
            hname = name if i is None else cfg.L["elem_name_fmt"].format(m=name, i=i)
            ref = pref + name + ("" if i is None else "[%d]" % i)
            set_attr(t, "Name", hname, must=True)
            if "Length" in [c.tag for c in attrs(t)]:
                set_attr(t, "Length", TYPE_LEN.get(mem["type"], 2))
            for lk in t.find("LinkList") if t.find("LinkList") is not None else []:
                if lk.tag == "ControllerTag":
                    lk.find("Name").text = ref
                elif lk.tag in ("DataType", "HmiDataType"):
                    lk.find("Name").text = mem["type"]
            # comment: member path
            for ml in t.iter("MultilingualText"):
                if ml.get("CompositionName") == "Comment":
                    set_ml_text(ml, ref)
            ol.append(t)
            count += 1
    out = os.path.join(args.out, "tags", cfg.L["tag_table"] + ".xml")
    save(tree, out)
    log("tags: %d tags -> %s (prefix %s)" % (count, out, pref))
    return count

# ------------------------------------------------------------------ text lists
def gen_textlists(cfg, args):
    src = find_file(proto_dirs(args), "textlists", ["TL_State.xml", "*"])
    if src is None:
        raise SystemExit("no prototype text list export found")
    log("textlists: prototype " + src)
    n = 0
    for name, entries in cfg.L["textlists"].items():
        tree = load(src)
        tl = next(e for e in tree.getroot().iter() if e.tag.endswith("TextList") and attrs(e) is not None)
        set_attr(tl, "Name", name, must=True)
        ol = own_objlist(tl)
        ents = [e for e in list(ol) if e.tag.endswith("TextListEntry")]
        if not ents:
            raise SystemExit("prototype text list has no entries: " + src)
        proto = ents[0]
        for e in ents:
            ol.remove(e)
        for val, text in entries:
            e = copy.deepcopy(proto)
            for a in ("From", "To", "Value", "RangeFrom", "RangeTo"):
                set_attr(e, a, val)
            set_attr(e, "DefaultEntry", "false")
            for ml in e.iter("MultilingualText"):
                set_ml_text(ml, text)
            ol.append(e)
        save(tree, os.path.join(args.out, "textlists", name + ".xml"))
        n += 1
    log("textlists: %d lists" % n)
    return n

# ------------------------------------------------------------------ screen items
class Builder:
    def __init__(self, cfg, protos, name):
        self.cfg, self.P, self.items, self.names = cfg, protos, [], {}
        self.screen = name

    def _new(self, proto, prefix, x, y, w, h):
        if proto not in self.P:
            raise SystemExit("prototype object missing on Proto screen: " + proto)
        el = copy.deepcopy(self.P[proto])
        k = self.names.get(prefix, 0) + 1
        self.names[prefix] = k
        s = self.cfg.scale
        set_attr(el, "ObjectName", "%s_%d" % (prefix, k), must=True)
        set_attr(el, "Left", int(round(x * s)), must=True)
        set_attr(el, "Top", int(round(y * s)), must=True)
        set_attr(el, "Width", max(1, int(round(w * s))), must=True)
        set_attr(el, "Height", max(1, int(round(h * s))), must=True)
        self.items.append(el)
        return el

    def text(self, it):
        el = self._new("P_Text", "txt", it["x"], it["y"], it["w"], it["h"])
        set_texts(el, it.get("t", ""))
        set_font(el, self._fs(it.get("size", self.cfg.L["font"]["size"])), it.get("bold", False))
        if it.get("fg"):
            set_attr(el, "ForeColor", self.cfg.color(it["fg"]))
        if it.get("align"):
            set_attr(el, "HorizontalAlignment", it["align"])
        return el

    def frame(self, it):
        el = self._new("P_Text", "frm", it["x"], it["y"], it["w"], it["h"])
        set_texts(el, "")
        set_attr(el, "BackFillStyle", "Transparent" if it.get("bg") is None else "Solid")
        if it.get("bg"):
            set_attr(el, "BackColor", self.cfg.color(it["bg"]))
        set_attr(el, "BorderWidth", it.get("border", 1))
        set_attr(el, "BorderColor", self.cfg.color(it.get("bc", "frame")))
        set_attr(el, "EdgeStyle", "Solid" if it.get("border", 1) else "None")
        set_attr(el, "CornerRadius", 0)
        set_attr(el, "FitToLargest", "false")
        return el

    def io(self, it):
        el = self._new("P_IO", "io", it["x"], it["y"], it["w"], it["h"])
        set_tag_links(el, self.cfg.tag(it["tag"]))
        set_attr(el, "Mode", it.get("mode", "Output"))
        fmt = it.get("fmt", "99999")
        set_attr(el, "FormatPattern", fmt)
        set_attr(el, "FieldLength", len(fmt))
        set_attr(el, "HorizontalAlignment", it.get("align", "Right"))
        if it.get("transparent"):
            set_attr(el, "BackFillStyle", "Transparent")
            set_attr(el, "BorderWidth", 0)
        if it.get("size"):
            set_font(el, self._fs(it["size"]), it.get("bold"))
        set_attr(el, "TabIndex", -1 if it.get("mode", "Output") == "Output" else self._tab())
        return el

    def sym(self, it):
        el = self._new("P_SymIO", "sym", it["x"], it["y"], it["w"], it["h"])
        set_tag_links(el, self.cfg.tag(it["tag"]))
        if not set_textlist_link(el, it["tl"]):
            log("WARNING %s: no TextList link found in P_SymIO clone" % self.screen)
        set_attr(el, "Mode", it.get("mode", "Output"))
        set_attr(el, "TabIndex", -1 if it.get("mode", "Output") == "Output" else self._tab())
        return el

    def btn(self, it):
        fn = it.get("fn", "SetBit")
        proto = "P_BtnInv" if fn == "InvertBit" and "P_BtnInv" in self.P else "P_Btn"
        el = self._new(proto, "btn", it["x"], it["y"], it["w"], it["h"])
        set_texts(el, it["t"])
        set_tag_links(el, self.cfg.tag(it["tag"]))
        if fn == "InvertBit" and proto == "P_Btn":
            n = replace_text_values(el, "SetBit", "InvertBit")
            for e in el.iter():
                if "SetBit" in e.tag:
                    e.tag = e.tag.replace("SetBit", "InvertBit"); n += 1
            if not n:
                log("WARNING: could not turn SetBit into InvertBit (add P_BtnInv to Proto)")
        set_attr(el, "TabIndex", self._tab())
        return el

    def nav(self, it):
        el = self._new("P_NavBtn", "nav", it["x"], it["y"], it["w"], it["h"])
        set_texts(el, it["t"])
        if not replace_text_values(el, self.cfg.L["proto_nav_target"], it["screen"]):
            log("WARNING: P_NavBtn has no reference to '%s'" % self.cfg.L["proto_nav_target"])
        set_attr(el, "TabIndex", self._tab())
        return el

    def lamp(self, it, alarm=False):
        el = self._new("P_LampAlarm" if alarm else "P_Lamp", "lmp", it["x"], it["y"], it["w"], it["h"])
        set_tag_links(el, self.cfg.tag(it["tag"]))
        return el

    def datetime(self, it):
        # judge round 2 R2-J4: date/time field on every screen (template footer). Optional prototype
        # P_DateTime (WinCC "Date/time field", system time, HUMAN_STEPS B); skipped with a warning if absent.
        if "P_DateTime" not in self.P:
            log("WARNING: prototype P_DateTime missing on Proto screen - date/time field skipped (HUMAN_STEPS B)")
            return None
        return self._new("P_DateTime", "dtm", it["x"], it["y"], it["w"], it["h"])

    def bar(self, it):
        el = self._new("P_Bar", "bar", it["x"], it["y"], it["w"], it["h"])
        set_tag_links(el, self.cfg.tag(it["tag"]))
        for a, v in (("MinimumValue", it.get("min", 0)), ("MaximumValue", it.get("max", 100))):
            set_attr(el, a, v)
        return el

    def cell(self, x, y, w, h, st_ref, id_ref, idw, idh, size):
        r = self._new("P_CellRect", "cel", x, y, w, h)
        set_tag_links(r, self.cfg.tag(st_ref))
        self.io({"x": x + (w - idw) / 2.0, "y": y + (h - idh) / 2.0, "w": idw, "h": idh, "tag": id_ref,
                 "fmt": self.cfg.L["grid"]["id_fmt"], "transparent": True, "align": "Center", "size": size, "bold": True})

    def crane(self, proto, x, y, w, h, motion):
        el = self._new(proto, "crn", x, y, w, h)
        patched = patch_motion(el, motion, self.cfg.scale)
        return el, patched

    def _fs(self, size):
        return max(int(self.cfg.L["font"].get("min_size", 8)), int(round(size * self.cfg.scale)))

    _t = 0
    def _tab(self):
        Builder._t += 1
        return Builder._t

    def render(self, items):
        for it in items:
            k = it["k"]
            if k == "text": self.text(it)
            elif k == "frame": self.frame(it)
            elif k == "io": self.io(it)
            elif k == "sym": self.sym(it)
            elif k == "btn": self.btn(it)
            elif k == "nav": self.nav(it)
            elif k == "lamp": self.lamp(it)
            elif k == "lampA": self.lamp(it, alarm=True)
            elif k == "bar": self.bar(it)
            elif k == "datetime": self.datetime(it)
            elif k == "kv":
                self.text({"x": it["x"], "y": it["y"], "w": it["lw"], "h": it["h"], "t": it["label"]})
                self.io({"x": it["x"] + it["lw"], "y": it["y"], "w": it["w"], "h": it["h"], "tag": it["tag"], "fmt": it.get("fmt", "99999")})
            elif k == "ks":
                self.text({"x": it["x"], "y": it["y"], "w": it["lw"], "h": it["h"], "t": it["label"]})
                self.sym({"x": it["x"] + it["lw"], "y": it["y"], "w": it["w"], "h": it["h"], "tag": it["tag"], "tl": it["tl"]})
            elif k.startswith("@"):
                self.render(self.cfg.L["panels"][k])
            else:
                raise SystemExit("unknown item kind: " + k)


def patch_motion(el, motion, s):
    """Set the movement animation of a crane marker. Real V21 schema (hmi-tia/lab/r2_exp): the start position is the
    object's own Left/Top; Hmi.Dynamic.HorizontalMovementAnimation has RangeStart/RangeEnd/XPosEnd/XDelta/YDelta,
    VerticalMovementAnimation RangeStart/RangeEnd/YPosEnd/YDelta/XDelta. Returns the list of patched attributes."""
    out = []
    for e in el.iter():
        if not e.tag.endswith("MovementAnimation"):
            continue
        sx, ex = int(round(motion["start_x"] * s)), int(round(motion["end_x"] * s))
        sy, ey = int(round(motion["start_y"] * s)), int(round(motion["end_y"] * s))
        vals = {"RangeStart": motion.get("range", (0, 9))[0], "RangeEnd": motion.get("range", (0, 9))[1]}
        if e.tag.endswith("HorizontalMovementAnimation"):
            vals.update({"XPosEnd": ex, "XDelta": ex - sx, "YDelta": 0})
        else:
            vals.update({"YPosEnd": ey, "YDelta": ey - sy, "XDelta": 0})
        for k, v in vals.items():
            set_attr(e, k, v, must=True)
            out.append("%s=%s" % (k, v))
    return out

# ------------------------------------------------------------------ screen bodies
def body_grid(b, cfg, info):
    g = cfg.L["grid"]
    pal = cfg.pal
    x0, y0, cw, ch, px, py = g["x0"], g["y0"], g["cw"], g["ch"], g["px"], g["py"]
    gx = lambda G: x0 + G * px
    # titles
    b.text({"x": gx(g["bay1_g"]), "y": g["title_y"], "w": 4 * px - 10, "h": 28, "t": "BAY 1 - SKLADIŠTE (yard)", "bold": True})
    b.text({"x": gx(g["bay0_g"]), "y": g["title_y"], "w": 4 * px - 10, "h": 28, "t": "BAY 0 - BROD (ship)", "bold": True})
    # crane rail (horizontal) and y-rail (in the 2-column quay gap)
    b.frame({"x": gx(0) - 4, "y": g["rail_y"], "w": 10 * px - (px - cw) + 8, "h": g["rail_h"], "bg": "panel_bg", "border": 1})
    ry = g["crane_y_rail_x"]
    b.frame({"x": ry, "y": y0 - 4, "w": g["crane_y_rail_w"], "h": 12 * py - (py - ch) + 8, "bg": "panel_bg", "border": 1})
    b.text({"x": ry, "y": y0 + 12 * py + 2, "w": g["crane_y_rail_w"], "h": 22, "t": "OBALA / kran y", "size": 11, "fg": "text_dim", "align": "Center"})
    # outlines: yard and ship; ship split line between x1 and x2 (left half x0-1 vs right half x2-3)
    b.frame({"x": gx(g["bay1_g"]) - 8, "y": y0 - 8, "w": 4 * px - (px - cw) + 16, "h": 12 * py - (py - ch) + 16, "border": 2, "bc": "yard_frame"})
    b.frame({"x": gx(g["bay0_g"]) - 8, "y": y0 - 8, "w": 4 * px - (px - cw) + 16, "h": 12 * py - (py - ch) + 16, "border": 3, "bc": "ship_frame"})
    split = gx(g["bay0_g"] + 2) - (px - cw) / 2.0 - 2
    b.frame({"x": split, "y": y0 - 8, "w": 4, "h": 12 * py - (py - ch) + 16, "bg": "ship_frame", "border": 0})
    # row labels (left) and column labels (below)
    for y in range(12):
        b.text({"x": 16, "y": y0 + y * py + (ch - 22) / 2.0, "w": 40, "h": 22, "t": "y%d" % y, "size": g["label_size"], "fg": "text_dim"})
    for bay, G0 in ((1, g["bay1_g"]), (0, g["bay0_g"])):
        for x in range(4):
            b.text({"x": gx(G0 + x), "y": y0 + 12 * py - (py - ch) + 10, "w": cw, "h": 20, "t": "x%d" % x,
                    "size": g["label_size"], "fg": "text_dim", "align": "Center"})
    # ship half labels with live counts
    yl = y0 + 12 * py - (py - ch) + 34
    b.render([{"k": "kv", "x": gx(g["bay0_g"]), "y": yl, "lw": 120, "w": 60, "h": 28, "label": "LIJEVO L =", "tag": "BalL", "fmt": "99"},
              {"k": "kv", "x": gx(g["bay0_g"] + 2), "y": yl, "lw": 120, "w": 60, "h": 28, "label": "DESNO R =", "tag": "BalR", "fmt": "99"}])
    # 96 cells
    n = 0
    for bay, G0 in ((1, g["bay1_g"]), (0, g["bay0_g"])):
        for x in range(4):
            for y in range(12):
                i = x * 12 + y
                b.cell(gx(G0 + x), y0 + y * py, cw, ch, "CellSt%d[%d]" % (bay, i), "Cell%d[%d]" % (bay, i),
                       g["id_w"], g["id_h"], g["id_size"])
                n += 1
    info["cells"] = info.get("cells", 0) + n
    # crane markers (movement animations configured on the prototypes; positions computed here)
    mw = cw - 4
    xm, pX = b.crane("P_CraneX", gx(0) + 2, g["rail_y"] + 2, mw, g["rail_h"] - 4,
                     {"start_x": gx(0) + 2, "end_x": gx(9) + 2, "start_y": g["rail_y"] + 2, "end_y": g["rail_y"] + 2, "range": (0, 9)})
    ym, pY = b.crane("P_CraneY", ry + 10, y0 + (ch - 36) / 2.0, g["crane_y_rail_w"] - 20, 36,
                     {"start_x": ry + 10, "end_x": ry + 10, "start_y": y0 + (ch - 36) / 2.0, "end_y": y0 + 11 * py + (ch - 36) / 2.0, "range": (0, 11)})
    info["crane_motion"] = {
        "P_CraneX (horizontal movement, tag CraneGX, range 0..9)": {"start_left": gx(0) + 2, "end_left": gx(9) + 2, "top": g["rail_y"] + 2, "patched": pX},
        "P_CraneY (vertical movement, tag CraneY, range 0..11)": {"left": ry + 10, "start_top": y0 + (ch - 36) / 2.0, "end_top": y0 + 11 * py + (ch - 36) / 2.0, "patched": pY}}


def body_legend(b, cfg):
    L = cfg.L["panels"]["legend"]
    b.frame({"x": L["x"], "y": L["y"], "w": L["w"], "h": L["h"], "bg": "panel_bg", "border": 1})
    b.text({"x": L["x"] + 12, "y": L["y"] + 4, "w": 300, "h": 24, "t": "LEGENDA ĆELIJA", "bold": True})
    codes = sorted(cfg.pal["cellst"].items(), key=lambda kv: int(kv[0]))
    for j, (code, (rgb, label)) in enumerate(codes):
        col, row = j // 4, j % 4
        x = L["x"] + 12 + col * 336
        y = L["y"] + 34 + row * (L["row"] + 18)
        b.frame({"x": x, "y": y, "w": L["sw"] * 1.6, "h": L["sw"], "bg": rgb, "border": 1})
        b.text({"x": x + L["sw"] * 1.6 + 8, "y": y, "w": 280, "h": L["sw"], "t": "%s %s" % (code, label), "size": 12})


def body_lists(b, cfg, info):
    C = cfg.L["lists"]
    sy = C["settings_y"]
    b.frame({"x": 16, "y": sy, "w": 1888, "h": 84, "bg": "panel_bg", "border": 1})
    b.text({"x": 28, "y": sy + 4, "w": 400, "h": 28, "t": "POSTAVKE (mijenjati kad sustav ne radi)", "bold": True})
    b.render([
        {"k": "text", "x": 28, "y": sy + 40, "w": 160, "h": 34, "t": "Redoslijed"},
        {"k": "sym", "x": 188, "y": sy + 40, "w": 330, "h": 34, "tag": "CfgOrderMode", "tl": "TL_Order", "mode": "InOutput"},
        {"k": "text", "x": 560, "y": sy + 40, "w": 290, "h": 34, "t": "POLUAUT.: klik = cijeli transfer"},
        {"k": "sym", "x": 850, "y": sy + 40, "w": 110, "h": 34, "tag": "CfgSemiPerTransfer", "tl": "TL_YesNo", "mode": "InOutput"},
        {"k": "text", "x": 1000, "y": sy + 40, "w": 180, "h": 34, "t": "Ravnoteža"},
        {"k": "sym", "x": 1180, "y": sy + 40, "w": 260, "h": 34, "tag": "CfgBalMode", "tl": "TL_BalMode", "mode": "InOutput"},
        {"k": "kv", "x": 1480, "y": sy + 40, "lw": 80, "w": 60, "h": 34, "label": "Istovar", "tag": "UTotal", "fmt": "99"},
        {"k": "kv", "x": 1640, "y": sy + 40, "lw": 80, "w": 60, "h": 34, "label": "Ukrcaj", "tag": "LTotal", "fmt": "99"},
    ])
    titles = ["LISTA ZA ISTOVAR (DB20) 1-24", "LISTA ZA ISTOVAR 25-48", "LISTA ZA UKRCAJ (DB21) 1-24", "LISTA ZA UKRCAJ 25-48"]
    n = 0
    for blk in range(4):
        bx = C["block_x"][blk]
        lst, st = ("UList", "UState") if blk < 2 else ("LList", "LState")
        first = 1 + (blk % 2) * C["rows"]
        b.text({"x": bx, "y": C["y0"] - 34, "w": C["block_w"], "h": 28, "t": titles[blk], "bold": True})
        for r in range(C["rows"]):
            i = first + r
            y = C["y0"] + r * C["row"]
            b.text({"x": bx, "y": y, "w": C["col_idx"], "h": C["row"] - 3, "t": "%d" % i, "size": 12, "fg": "text_dim", "align": "Right"})
            b.io({"x": bx + C["col_idx"] + 6, "y": y, "w": C["col_id"], "h": C["row"] - 3, "tag": "%s[%d]" % (lst, i), "fmt": "999"})
            b.sym({"x": bx + C["col_idx"] + C["col_id"] + 12, "y": y, "w": C["col_st"], "h": C["row"] - 3, "tag": "%s[%d]" % (st, i), "tl": "TL_ListSt"})
            n += 1
    info["list_rows"] = n


def body_alarmlog(b, cfg, info):
    A = cfg.L["alarmlog"]
    b.text({"x": A["x"], "y": 156, "w": 1000, "h": 30, "t": "POVIJEST ALARMA (zadnjih 16 pojava, [0] najnoviji). Puna povijest s vremenom: zaslon ALARMI.", "bold": True})
    for i in range(16):
        y = A["y"] + i * A["row"]
        b.text({"x": A["x"], "y": y, "w": 60, "h": A["row"] - 8, "t": "[%d]" % i, "fg": "text_dim"})
        b.sym({"x": A["x"] + 64, "y": y, "w": A["w"] - 64, "h": A["row"] - 8, "tag": "AlarmHist[%d]" % i, "tl": "TL_Alarm"})
    b.frame({"x": 1220, "y": 200, "w": 684, "h": 300, "bg": "panel_bg", "border": 1})
    b.render([
        {"k": "text", "x": 1232, "y": 206, "w": 600, "h": 28, "t": "NAJNOVIJI ALARM - DETALJI", "bold": True},
        {"k": "lampA", "x": 1232, "y": 246, "w": 22, "h": 22, "tag": "LampAlarm"},
        {"k": "kv", "x": 1262, "y": 240, "lw": 150, "w": 80, "h": 34, "label": "Kontejner ID", "tag": "AlarmId", "fmt": "999"},
        {"k": "kv", "x": 1232, "y": 284, "lw": 120, "w": 50, "h": 34, "label": "Lokacija x", "tag": "AlarmX", "fmt": "s9"},
        {"k": "kv", "x": 1420, "y": 284, "lw": 30, "w": 50, "h": 34, "label": "y", "tag": "AlarmY", "fmt": "s99"},
        {"k": "ks", "x": 1540, "y": 284, "lw": 60, "w": 240, "h": 34, "label": "Bay", "tag": "AlarmBay", "tl": "TL_Bay"},
        {"k": "kv", "x": 1232, "y": 328, "lw": 180, "w": 100, "h": 34, "label": "Riječ alarma", "tag": "AlarmWord", "fmt": "99999"},
        {"k": "kv", "x": 1232, "y": 372, "lw": 180, "w": 100, "h": 34, "label": "Broj pojava", "tag": "AlarmHistSeq", "fmt": "999999"},
        {"k": "text", "x": 1232, "y": 420, "w": 660, "h": 60, "t": "Blokirajući alarm zaustavlja dizalicu. Uklonite uzrok i pritisnite POTVRDA; rad se nastavlja.", "size": 12, "fg": "text_dim"},
    ])
    # v1.4 (judge round 1 J7 / R1-E1): which list IDs are missing, and whether the list order was abandoned
    b.frame({"x": 1220, "y": 516, "w": 684, "h": 236, "bg": "panel_bg", "border": 1})
    b.render([
        {"k": "text", "x": 1232, "y": 522, "w": 660, "h": 28, "t": "PROVJERA LISTA (POČETNO STANJE)", "bold": True},
        {"k": "kv", "x": 1232, "y": 558, "lw": 330, "w": 80, "h": 34, "label": "Istovar: prvi ID koji nije u Bay 0", "tag": "AlarmUId", "fmt": "999"},
        {"k": "kv", "x": 1660, "y": 558, "lw": 90, "w": 60, "h": 34, "label": "ukupno", "tag": "AlarmUCnt", "fmt": "99"},
        {"k": "kv", "x": 1232, "y": 600, "lw": 330, "w": 80, "h": 34, "label": "Ukrcaj: prvi ID koji nije u Bay 1", "tag": "AlarmLId", "fmt": "999"},
        {"k": "kv", "x": 1660, "y": 600, "lw": 90, "w": 60, "h": 34, "label": "ukupno", "tag": "AlarmLCnt", "fmt": "99"},
        {"k": "ks", "x": 1232, "y": 642, "lw": 330, "w": 100, "h": 34, "label": "Redoslijed liste napušten", "tag": "OrderFallback", "tl": "TL_YesNo"},
        {"k": "ks", "x": 1232, "y": 684, "lw": 330, "w": 300, "h": 34, "label": "Korišteni način redoslijeda", "tag": "OrderModeAct", "tl": "TL_Order"},
    ])
    info["alarmlog_rows"] = 16

# ------------------------------------------------------------------ screens
def collect_protos(tree):
    P = {}
    for el in tree.getroot().iter():
        if el.get("CompositionName") == "ScreenItems":
            n = get_attr(el, "ObjectName")
            if n:
                P[n] = el
    return P

def screen_root(tree, kind):
    for el in tree.getroot().iter():
        if el.tag.startswith("Hmi.Screen.") and el.tag.endswith(kind) and attrs(el) is not None:
            return el
    raise SystemExit("no %s root element in prototype" % kind)

def layer_lists(root):
    return [l.find("ObjectList") for l in root.iter("Hmi.Screen.ScreenLayer")]

def fill(root, items):
    lists = [ol for ol in layer_lists(root) if ol is not None]
    if not lists:
        raise SystemExit("prototype screen has no ScreenLayer/ObjectList")
    for ol in lists:
        for c in list(ol):
            if c.get("CompositionName") == "ScreenItems":
                ol.remove(c)
    for el in items:
        lists[0].append(el)

def gen_screens(cfg, args):
    dirs = proto_dirs(args)
    psrc = find_file(dirs, "screens", ["Proto.xml"])
    if psrc is None:
        raise SystemExit("no prototype screen Proto.xml found in " + str(dirs))
    log("screens: prototype " + psrc)
    ptree = load(psrc)
    P = collect_protos(ptree)
    missing = [p for p in REQUIRED_PROTOS if p not in P]
    if missing:
        raise SystemExit("Proto screen lacks objects: " + ", ".join(missing))
    tsrc = None
    if cfg.L["header_in"] in ("auto", "template"):
        tsrc = find_file([psrc.rsplit(os.sep + "screens", 1)[0]], "templates", [cfg.L["template_name"] + ".xml"])
        if tsrc is None and cfg.L["header_in"] == "template":
            raise SystemExit("header_in=template but no templates/%s.xml export" % cfg.L["template_name"])
    info = {"screens": {}}
    W, H = cfg.L["canvas"]["w"], cfg.L["canvas"]["h"]
    if tsrc:
        b = Builder(cfg, P, "Tpl")
        b.render(cfg.L["header"])
        tt = load(tsrc)
        troot = screen_root(tt, "ScreenTemplate")
        set_attr(troot, "Name", cfg.L["template_name"], must=True)
        fill(troot, b.items)
        save(tt, os.path.join(args.out, "templates", cfg.L["template_name"] + ".xml"))
        info["screens"]["Tpl (template)"] = len(b.items)
        log("screens: header -> template %s (%d objects)" % (cfg.L["template_name"], len(b.items)))
    for name, sc in cfg.L["screens"].items():
        b = Builder(cfg, P, name)
        if not tsrc:
            b.render(cfg.L["header"])
        for part in sc["body"]:
            if part == "grid": body_grid(b, cfg, info)
            elif part == "legend": body_legend(b, cfg)
            elif part == "lists": body_lists(b, cfg, info)
            elif part == "alarmlog": body_alarmlog(b, cfg, info)
            else: b.render(cfg.L["panels"][part])
        st = load(psrc)
        root = screen_root(st, "Screen")
        set_attr(root, "Name", name, must=True)
        set_attr(root, "Number", sc["number"], must=True)
        # WinCC requires the screen size to equal the device resolution (else the import aborts TIA)
        set_attr(root, "Width", int(cfg.L["canvas"].get("device_w", W * cfg.scale)), must=True)
        set_attr(root, "Height", int(cfg.L["canvas"].get("device_h", H * cfg.scale)), must=True)
        set_attr(root, "BackColor", cfg.pal["screen_bg"])
        fill(root, b.items)
        save(st, os.path.join(args.out, "screens", name + ".xml"))
        info["screens"][name] = len(b.items)
        log("screens: %s -> %d objects" % (name, len(b.items)))
    with open(os.path.join(args.out, "gen_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1, ensure_ascii=False)
    return info

# ------------------------------------------------------------------ check
def check(cfg, args):
    bad = 0
    tagnames = set()
    tp = os.path.join(args.out, "tags")
    for f in sorted(os.listdir(tp)) if os.path.isdir(tp) else []:
        for t in load(os.path.join(tp, f)).getroot().iter():
            if t.get("CompositionName") == "Tags":
                tagnames.add(get_attr(t, "Name"))
    tls = set(cfg.L["textlists"].keys())
    for sub in ("tags", "textlists", "templates", "screens"):
        d = os.path.join(args.out, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            tr = load(os.path.join(d, f))
            ids = [e.get("ID") for e in tr.getroot().iter() if "ID" in e.attrib]
            if len(ids) != len(set(ids)):
                log("CHECK %s/%s: duplicate IDs" % (sub, f)); bad += 1
            if sub in ("screens", "templates"):
                names = [get_attr(e, "ObjectName") for e in tr.getroot().iter() if e.get("CompositionName") == "ScreenItems"]
                if len(names) != len(set(names)):
                    log("CHECK %s/%s: duplicate ObjectNames" % (sub, f)); bad += 1
                for t in tr.getroot().iter("Tag"):
                    nm = t.find("Name").text if t.find("Name") is not None else None
                    if tagnames and nm not in tagnames:
                        log("CHECK %s/%s: tag link '%s' not in generated tag table" % (sub, f, nm)); bad += 1
                for t in tr.getroot().iter("TextList"):
                    nm = t.find("Name").text if t.find("Name") is not None else None
                    if nm not in tls:
                        log("CHECK %s/%s: text list '%s' not generated" % (sub, f, nm)); bad += 1
                for e in tr.getroot().iter():
                    if e.get("CompositionName") == "ScreenItems":
                        l, t_, w, h = (int(get_attr(e, a)) for a in ("Left", "Top", "Width", "Height"))
                        if l < 0 or t_ < 0 or l + w > cfg.L["canvas"].get("device_w", cfg.L["canvas"]["w"] * cfg.scale) or t_ + h > cfg.L["canvas"].get("device_h", cfg.L["canvas"]["h"] * cfg.scale):
                            log("CHECK %s/%s: %s outside canvas" % (sub, f, get_attr(e, "ObjectName"))); bad += 1
    log("CHECK_RESULT problems=%d tags=%d" % (bad, len(tagnames)))
    return bad

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["all", "base", "tags", "textlists", "screens", "check"],
                    help="all = tags+textlists+screens+check; base = tags+textlists+check (round 1, before Proto exists)")
    ap.add_argument("--layout", default=os.path.join(HERE, "layout.json"))
    ap.add_argument("--export", default=None, help="HmiGen --export dir with the human prototypes (default hmi-tia/export, then hmi-tia/mock)")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    args = ap.parse_args()
    cfg = Cfg(args.layout)
    if args.cmd in ("all", "base", "tags"): gen_tags(cfg, args)
    if args.cmd in ("all", "base", "textlists"): gen_textlists(cfg, args)
    if args.cmd in ("all", "screens"):
        info = gen_screens(cfg, args)
        for k, v in info.get("crane_motion", {}).items():
            log("MOTION %s: %s" % (k, v))
    if args.cmd in ("all", "base", "check"):
        sys.exit(1 if check(cfg, args) else 0)

if __name__ == "__main__":
    main()
