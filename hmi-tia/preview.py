#!/usr/bin/env python3
"""preview.py - stdlib wireframe of generated screens (template + screen) as PNG and SVG, to check the layout
without TIA.  python preview.py [--out hmi-tia/out] [--scale 0.5]  -> OUT/preview/<Screen>.png/.svg
PNG: filled boxes per object type (no text). SVG: boxes + texts/tag names (open in a browser)."""
import argparse, os, struct, zlib, html
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
COL = {"TextField": (200, 200, 200), "IOField": (255, 255, 255), "SymbolicIOField": (235, 235, 255), "Button": (150, 150, 150),
       "Rectangle": (120, 170, 120), "Bar": (90, 120, 200)}

def load(p):
    d = open(p, "rb").read()
    return ET.fromstring(d[3:] if d.startswith(b"\xef\xbb\xbf") else d)

def items(root):
    out = []
    for e in root.iter():
        if e.get("CompositionName") != "ScreenItems":
            continue
        a = {c.tag: (c.text or "") for c in e.find("AttributeList")}
        kind = e.tag.split(".")[-1]
        txt = ""
        for t in e.iter("p"):
            txt = t.text or ""; break
        tags = [t.find("Name").text for t in e.iter("Tag") if t.find("Name") is not None]
        bg = a.get("BackColor") if a.get("BackFillStyle", "Solid") != "Transparent" else None
        out.append((kind, int(a["Left"]), int(a["Top"]), int(a["Width"]), int(a["Height"]), txt, tags, bg, a.get("ObjectName", "")))
    return out

def png(path, W, H, objs, s):
    w, h = int(W * s), int(H * s)
    px = bytearray([214, 214, 214] * (w * h))
    def fill(x0, y0, x1, y1, c):
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        for y in range(y0, y1):
            row = (y * w) * 3
            for x in range(x0, x1):
                px[row + 3 * x:row + 3 * x + 3] = bytes(c)
    for kind, l, t, ww, hh, txt, tags, bg, name in objs:
        c = COL.get(kind, (255, 0, 255))
        if kind == "TextField":
            if bg is None:
                if not txt:   # transparent frame: outline only
                    x0, y0, x1, y1 = int(l * s), int(t * s), int((l + ww) * s), int((t + hh) * s)
                    for (a, b_, cc, d) in ((x0, y0, x1, y0 + 1), (x0, y1 - 1, x1, y1), (x0, y0, x0 + 1, y1), (x1 - 1, y0, x1, y1)):
                        fill(a, b_, cc, d, (60, 60, 60))
                    continue
                c = (185, 185, 185)
            else:
                c = tuple(int(v) for v in bg.split(","))
        fill(int(l * s), int(t * s), int((l + ww) * s), int((t + hh) * s), c)
    raw = b"".join(b"\x00" + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    chunk = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))

def svg(path, W, H, objs):
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Tahoma" font-size="12">' % (W, H),
         '<rect width="100%" height="100%" fill="rgb(214,214,214)"/>']
    for kind, l, t, ww, hh, txt, tags, bg, name in objs:
        fillc = "rgb(%s)" % bg if bg else ("none" if kind == "TextField" else "rgb(%d,%d,%d)" % COL.get(kind, (255, 0, 255)))
        o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" stroke="#555" stroke-width="0.5"><title>%s %s</title></rect>'
                 % (l, t, ww, hh, fillc, html.escape(name), html.escape(",".join(tags))))
        lab = txt or (tags[0] if tags and kind in ("IOField", "SymbolicIOField", "Bar") else "")
        if lab:
            o.append('<text x="%d" y="%d">%s</text>' % (l + 3, t + hh / 2 + 4, html.escape(lab)))
    o.append("</svg>")
    open(path, "w", encoding="utf-8").write("\n".join(o))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--scale", type=float, default=0.5)
    a = ap.parse_args()
    tpl = []
    tp = os.path.join(a.out, "templates")
    if os.path.isdir(tp):
        for f in os.listdir(tp):
            tpl += items(load(os.path.join(tp, f)))
    pd = os.path.join(a.out, "preview")
    os.makedirs(pd, exist_ok=True)
    for f in sorted(os.listdir(os.path.join(a.out, "screens"))):
        r = load(os.path.join(a.out, "screens", f))
        al = {c.tag: c.text for c in r.find(".//Hmi.Screen.Screen/AttributeList")}
        W, H = int(al["Width"]), int(al["Height"])
        objs = tpl + items(r)
        n = os.path.splitext(f)[0]
        png(os.path.join(pd, n + ".png"), W, H, objs, a.scale)
        svg(os.path.join(pd, n + ".svg"), W, H, objs)
        print("preview", n, len(objs), "objects")

if __name__ == "__main__":
    main()
