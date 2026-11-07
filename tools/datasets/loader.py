"""Dataset loader for the twin (tools/twin.py).

Folder format: tools/datasets/<name>/ with
  fne.csv, fec.csv  one float per line, 35040 lines, no header (kW)
  ev.json           [[ [arr_k, dep_k, energy_kWh], ... ] x 4 chargers]
  meta.json         {"name", "kind": "synthetic"|"real"|"stress", "description", "source_urls": [...], "prices": "2025"}
Prices / VT are never stored: vt, tt, da always come from twin.load() (2025 series built into the simulator).

Usage:
  from datasets.loader import load_dataset, list_datasets     (with tools/ on sys.path)
  d = load_dataset("syn_boot1"); r = twin.simulate(ctrl, mode, data=d)
Special names: "practice" -> twin.load(); "variant1".."variant5" -> twin.variant(i).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import twin  # noqa: E402

N = 35040


def _floats(path):
    with open(path) as f:
        xs = [float(x) for x in f.read().split()]
    if len(xs) != N:
        raise ValueError("%s: %d values, expected %d" % (path, len(xs), N))
    return xs


def meta(name):
    with open(os.path.join(HERE, name, "meta.json")) as f:
        return json.load(f)


def load_dataset(name):
    """Return a twin-compatible dict: fne, fec, ev from files; vt, tt, da from twin.load()."""
    if name == "practice":
        return twin.load()
    if name.startswith("variant") and name[7:].isdigit():
        return twin.variant(int(name[7:]))
    folder = os.path.join(HERE, name)
    base = twin.load()
    fne = [min(max(x, 0.0), 750.0) for x in _floats(os.path.join(folder, "fne.csv"))]
    fec = [max(x, 0.0) for x in _floats(os.path.join(folder, "fec.csv"))]
    with open(os.path.join(folder, "ev.json")) as f:
        evj = json.load(f)
    if len(evj) != 4:
        raise ValueError("%s: ev.json must hold 4 chargers" % name)
    ev = [[(int(a), int(d), float(e)) for (a, d, e) in ch] for ch in evj]
    return dict(fne=fne, fec=fec, ev=ev, vt=base["vt"], tt=base["tt"], da=base["da"], name=name)


def list_datasets(kind=None):
    """Names of dataset folders (those with a meta.json), optionally filtered by meta kind."""
    out = []
    for n in sorted(os.listdir(HERE)):
        p = os.path.join(HERE, n, "meta.json")
        if os.path.isfile(p):
            if kind is None or meta(n).get("kind") == kind:
                out.append(n)
    return out


def write_dataset(name, fne, fec, ev, meta_dict):
    """Write a dataset folder in the standard format (used by the generators)."""
    folder = os.path.join(HERE, name)
    os.makedirs(folder, exist_ok=True)
    assert len(fne) == N and len(fec) == N and len(ev) == 4
    with open(os.path.join(folder, "fne.csv"), "w") as f:
        f.write("\n".join("%.4f" % min(max(float(x), 0.0), 750.0) for x in fne) + "\n")
    with open(os.path.join(folder, "fec.csv"), "w") as f:
        f.write("\n".join("%.4f" % max(float(x), 0.0) for x in fec) + "\n")
    with open(os.path.join(folder, "ev.json"), "w") as f:
        json.dump([[[int(a), int(d), round(float(e), 4)] for (a, d, e) in ch] for ch in ev], f)
    m = dict(meta_dict)
    m.setdefault("name", name)
    m.setdefault("source_urls", [])
    m.setdefault("prices", "2025")
    with open(os.path.join(folder, "meta.json"), "w") as f:
        json.dump(m, f, indent=1)


def stats(d):
    """Key statistics of a dataset dict."""
    fec, fne = d["fec"], d["fne"]
    sess = [s for ch in d["ev"] for s in ch]
    return dict(fec_MWh=round(sum(fec) * 0.25 / 1000, 1), fec_max=round(max(fec), 1),
                pv_MWh=round(sum(fne) * 0.25 / 1000, 1), ev_MWh=round(sum(e for _, _, e in sess) / 1000, 3),
                ev_sessions=len(sess), ev_per_charger=[len(ch) for ch in d["ev"]])


if __name__ == "__main__":
    for n in list_datasets(sys.argv[1] if len(sys.argv) > 1 else None):
        print(n, meta(n).get("kind"), stats(load_dataset(n)))
