# Converts the simulator's Init_Prof_*.st init code into CSV files (k, value). Dev/analysis only.
import re, os, sys, statistics
src = r"C:/Users/sajic/Documents/plc-hackathon/work/dump/MyController/Plc Logic/Application"
out = r"C:/Users/sajic/Documents/plc-hackathon/work/data"
for name in ["PriceTT", "PriceDA", "VT", "FNE", "FEC"]:
    txt = open(os.path.join(src, "Init", f"Init_Prof_{name}.st"), encoding="utf-8").read()
    hdr = open(os.path.join(src, "Profiles", f"Prof_{name}.st"), encoding="utf-8").read().splitlines()[2]
    vals = {int(i): v for i, v in re.findall(r"Data\[(\d+)\]\s*:=\s*([^;]+);", txt)}
    with open(os.path.join(out, f"{name}.csv"), "w") as f:
        f.write("k,value\n")
        for k in sorted(vals): f.write(f"{k},{vals[k]}\n")
    nums = [1.0 if v == "TRUE" else 0.0 if v == "FALSE" else float(v) for v in vals.values()]
    print(f"{name:8} n={len(vals):5}  min={min(nums):.4f} max={max(nums):.4f} mean={statistics.mean(nums):.4f}  distinct={len(set(nums))}  {hdr.strip()}")
