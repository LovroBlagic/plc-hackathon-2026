#!/usr/bin/env python3
"""Render a progress snapshot PNG of the agent team's work (orchestrator tool).

usage: python tools/progress/snap.py [out.png]
Shows: time, TIA lock, RAM, TIA/PLCSIM processes, newest files per work area, last result lines
from HMI lab logs / verify reports / PLCSIM results, and git working-tree summary.
"""
import os, sys, glob, time, subprocess, datetime, re
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tia-work", "progress", "snap.png")

AREAS = [  # (label, glob patterns)
    ("Builder v1.7 (spec M rule)", ["tia-src/*.scl", "tia-src/*.db", "tia-src/*.md", "tools/crane_*.py", "tools/bench/*"]),
    ("HMI agent", ["hmi-tia/*", "hmi-tia/lab/**/*", "hmi-tia/out/**/*"]),
    ("Verifiers", ["tia-work/verify/*"]),
    ("Shortcuts", ["tools/shortcuts/*", ".claude/skills/tia-portal/SKILL.md"]),
    ("PLCSIM", ["tools/plcsim/results/*", "tia-src/PLCSIM_RESULTS.md"]),
    ("Deliverables", ["deliver/*.zap21"]),
]


def sh(cmd):
    try:
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30,
                              encoding="utf-8", errors="replace").stdout
    except Exception as e:
        return f"ERR {e}"


def newest(patterns, n=3):
    files = []
    for p in patterns:
        for f in glob.glob(os.path.join(ROOT, p), recursive=True):
            if os.path.isfile(f) and "__pycache__" not in f:
                files.append((os.path.getmtime(f), f))
    files.sort(reverse=True)
    return files[:n]


def ago(ts):
    m = int((time.time() - ts) // 60)
    return f"{m} min ago" if m < 120 else f"{m // 60} h ago"


def last_match(path, pat, n=2):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = [l.rstrip() for l in fh if re.search(pat, l)]
        return lines[-n:]
    except OSError:
        return []


def main():
    rows = []  # (text, colour)
    now = datetime.datetime.now().strftime("%a %d %b %H:%M")
    rows.append((f"Crane team progress  -  {now}   (deadline 20:00)", "title"))
    lock = os.path.join(ROOT, "tia-work", "openness.lock")
    lock_s = open(lock, encoding="utf-8", errors="replace").read().strip() if os.path.exists(lock) else "free"
    mem = sh(["powershell", "-NoProfile", "-Command",
              "$o=Get-CimInstance Win32_OperatingSystem; '{0:N1}' -f ($o.FreePhysicalMemory/1MB)"]).strip()
    procs = sh(["powershell", "-NoProfile", "-Command",
                "(Get-Process | Where-Object { $_.ProcessName -match 'Siemens.Automation.Portal|SimHost|TiaRun|HmiGen|HmiLab|TiaDownload' } | ForEach-Object ProcessName) -join ', '"]).strip()
    rows.append((f"TIA lock: {lock_s}    free RAM: {mem} GB    TIA/PLCSIM procs: {procs or 'none'}", "info"))
    rows.append(("", None))
    for label, pats in AREAS:
        rows.append((label, "head"))
        nf = newest(pats)
        if not nf:
            rows.append(("   (no files yet)", "dim"))
        for ts, f in nf:
            rows.append((f"   {os.path.relpath(f, ROOT)}   -  {ago(ts)}", "ok" if time.time() - ts < 900 else "dim"))
    rows.append(("", None))
    rows.append(("Latest results", "head"))
    logs = sorted(glob.glob(os.path.join(ROOT, "hmi-tia", "lab", "*.log")), key=os.path.getmtime)
    if logs:
        for l in last_match(logs[-1], r"RESULT|HMI_COMPILE", 2):
            rows.append((f"   HMI lab {os.path.basename(logs[-1])}: {l[:110]}", "bad" if "errors=0" not in l else "ok"))
    for f in sorted(glob.glob(os.path.join(ROOT, "tia-work", "*.log")), key=os.path.getmtime)[-2:]:
        for l in last_match(f, r"TIA_RESULT|HMI_RESULT", 1):
            rows.append((f"   {os.path.basename(f)}: {l[:110]}", "ok" if "errors=0" in l else "bad"))
    for f in glob.glob(os.path.join(ROOT, "tia-work", "verify", "*.md")):
        txt = open(f, encoding="utf-8", errors="replace").read()
        b, m = len(re.findall(r"BLOCKER", txt)), len(re.findall(r"MAJOR", txt))
        rows.append((f"   verify {os.path.basename(f)}: BLOCKER x{b}, MAJOR x{m} (mentions)", "bad" if b else "ok"))
    st = sh(["git", "status", "--short"]).splitlines()
    rows.append((f"   git: {len(st)} uncommitted paths   last commit: {sh(['git', 'log', '--oneline', '-1']).strip()[:80]}", "info"))

    W, LH = 1500, 26
    img = Image.new("RGB", (W, 40 + LH * len(rows)), (250, 250, 248))
    d = ImageDraw.Draw(img)
    try:
        f_reg = ImageFont.truetype("consola.ttf", 17)
        f_big = ImageFont.truetype("segoeuib.ttf", 24)
        f_head = ImageFont.truetype("segoeuib.ttf", 18)
    except OSError:
        f_reg = f_big = f_head = ImageFont.load_default()
    col = {"title": (20, 20, 20), "info": (60, 60, 60), "head": (25, 80, 160), "ok": (30, 120, 50),
           "dim": (120, 120, 120), "bad": (190, 40, 40), None: (0, 0, 0)}
    y = 18
    for text, kind in rows:
        font = f_big if kind == "title" else f_head if kind == "head" else f_reg
        d.text((24, y), text, fill=col[kind], font=font)
        y += LH + (8 if kind == "title" else 0)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
