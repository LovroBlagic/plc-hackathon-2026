# -*- coding: utf-8 -*-
"""Extract a Machine Expert .projectarchive (optional) and dump every textual object as .st + a tree listing.
  me_dump.py --project C:/abs/X.project --out C:/abs/dumpdir [--archive C:/abs/X.projectarchive.zip]
Output: <out>/tree.txt and <out>/<Folder>/<Object>.st (declaration, '// ---IMPL---', implementation).
"""
from __future__ import print_function
import os, sys, argparse, codecs

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--archive")
a = ap.parse_args()

if a.archive:
    d = os.path.dirname(a.project)
    if not os.path.isdir(d):
        os.makedirs(d)
    proj = projects.open_archive(a.archive, d, True)
    print("EXTRACTED", a.archive, "->", d)
    if os.path.normcase(proj.path) != os.path.normcase(a.project):
        print("NOTE project file is", proj.path)
else:
    proj = projects.open(a.project, primary=True)

if not os.path.isdir(a.out):
    os.makedirs(a.out)
tree = codecs.open(os.path.join(a.out, "tree.txt"), "w", "utf-8")
n = [0]

def safe(s):
    return "".join(c if c.isalnum() or c in "_-. " else "_" for c in s)

def walk(o, path, depth):
    name = o.get_name()
    kind = []
    if getattr(o, "is_device", False): kind.append("device")
    if getattr(o, "is_folder", False): kind.append("folder")
    if getattr(o, "is_application", False): kind.append("app")
    if getattr(o, "has_textual_declaration", False): kind.append("text")
    tree.write(u"  " * depth + u"- " + name + (u"  [" + u",".join(kind) + u"]" if kind else u"") + u"\n")
    if getattr(o, "has_textual_declaration", False):
        d = os.path.join(a.out, *[safe(p) for p in path])
        if not os.path.isdir(d):
            os.makedirs(d)
        txt = o.textual_declaration.text
        if getattr(o, "has_textual_implementation", False):
            txt += u"\n// ---IMPL---\n" + o.textual_implementation.text
        f = codecs.open(os.path.join(d, safe(name) + ".st"), "w", "utf-8")
        f.write(txt)
        f.close()
        n[0] += 1
    for c in o.get_children():
        walk(c, path + [name], depth + 1)

for c in proj.get_children():
    walk(c, [], 0)
tree.close()
print("DUMPED", n[0], "textual objects to", a.out)
proj.close()
