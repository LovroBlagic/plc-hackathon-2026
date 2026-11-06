# -*- coding: utf-8 -*-
# Usage: LogicBuilderShell.exe apply_and_build.py <project.project> <src_dir>
# Each <src_dir>/*.st file = one POU. Declaration part, then a line "// ---IMPL---", then implementation.
# POU type is inferred from the first keyword (PROGRAM / FUNCTION_BLOCK / FUNCTION name : RET).
# Existing POUs (any where in Application) are overwritten; missing ones are created under Application.
# Then builds the Application and prints all compiler messages. Last line: BUILD_RESULT errors=N warnings=M
from __future__ import print_function
import sys, os, re, glob, codecs
proj_path, src_dir = sys.argv[1], sys.argv[2]
proj = projects.open(proj_path, primary=True)
app = proj.active_application
SEP = "// ---IMPL---"
for f in sorted(glob.glob(os.path.join(src_dir, "*.st"))):
    name = os.path.splitext(os.path.basename(f))[0]
    raw = open(f, "rb").read()
    if raw.startswith("\xef\xbb\xbf"): raw = raw[3:]  # strip UTF-8 BOM (PowerShell 5.1 Set-Content adds it)
    txt = raw.decode("utf-8").lstrip(u"﻿").replace(u"\r\n", u"\n")
    if SEP not in txt:
        print("SKIP (no separator):", f); continue
    decl, impl = txt.split(SEP, 1)
    # find() also returns same-named non-code objects (e.g. the MAST task's "SR_Main" call entry) -> keep only textual POUs
    found = [o for o in app.find(name, True) if getattr(o, "has_textual_declaration", False)]
    if found:
        pou = found[0]; action = "updated"
    else:
        m = re.search(r"^\s*(PROGRAM|FUNCTION_BLOCK|FUNCTION)\b[^:\n]*(?::\s*(\w+))?", decl, re.M)
        kind = m.group(1)
        if kind == "PROGRAM": pou = app.create_pou(name=name, type=PouType.Program)
        elif kind == "FUNCTION": pou = app.create_pou(name=name, type=PouType.Function, return_type=m.group(2))
        else: pou = app.create_pou(name=name, type=PouType.FunctionBlock)
        action = "created"
    pou.textual_declaration.replace(decl.strip("\n") + "\n")
    pou.textual_implementation.replace(impl.strip("\n") + "\n")
    print("POU %s %s" % (name, action))
proj.save()
app.build()
errs = warns = 0
seen = set()
for cat in system.get_message_categories(True):
    for msg in system.get_message_objects(cat):
        sev = str(msg.severity)
        key = (sev, msg.text, msg.position_text if hasattr(msg, "position_text") else "")
        if key in seen: continue
        seen.add(key)
        obj = msg.object.get_name() if msg.object else "-"
        print("[%s] %s @ %s %s" % (sev, msg.text, obj, key[2]))
        if "Error" in sev: errs += 1
        elif "Warning" in sev: warns += 1
print("BUILD_RESULT errors=%d warnings=%d" % (errs, warns))
proj.close()
