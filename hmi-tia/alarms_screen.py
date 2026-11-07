#!/usr/bin/env python3
"""alarms_screen.py OUTDIR - write OUTDIR/screens/Alarms.xml: screen "Alarms" (no. 15, template Tpl, 1024x768).
Openness cannot import WinCC alarm views, so this only creates the screen; the two alarm views (current alarms,
alarm buffer) are placed in the TIA GUI (HUMAN_STEPS D). Re-importing this file would delete them, so the
generator imports it only when the screen does not exist yet (HmiLab --import-new-only screens/Alarms.xml)."""
import os, sys
sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab"))
import mklab2 as m
s = m.screen("Alarms", 15, [])
s = s.replace("<BackColor>182, 182, 182</BackColor>", "<BackColor>214, 214, 214</BackColor>")
m.w("screens", "Alarms", s)
print("ALARMS screen ->", os.path.join(m.OUT, "screens", "Alarms.xml"))
