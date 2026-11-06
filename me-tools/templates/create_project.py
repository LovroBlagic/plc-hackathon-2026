# -*- coding: utf-8 -*-
# Usage: LogicBuilderShell.exe create_project.py <project_path.project>
# Creates a new ME project with a TM241CE24T/U controller and dumps the object tree.
from __future__ import print_function
import sys, os
path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\sajic\Documents\plc-hackathon\prototype-me\Proto.project"
if os.path.exists(path): os.remove(path)
proj = projects.create(path, True)
dev = proj.add("MyController", 4096, "101a 0711", "5.3.12.51")
def dump(o, ind=0):
    print("  " * ind + "- " + o.get_name() + ("  [app]" if getattr(o, "is_application", False) else ""))
    for c in o.get_children(): dump(c, ind + 1)
for c in proj.get_children(): dump(c)
proj.save()
print("SAVED", path)
