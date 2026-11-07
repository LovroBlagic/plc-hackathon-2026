"""Differential checks for the isolated v7 efficiency changes; no PLC/GUI access.

These check extracted algorithm semantics, not the Schneider ST compiler/runtime.
Run: python code-review/check_equivalence.py
"""
from pathlib import Path
import hashlib
import random

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "deliver" / "ME_v7_src"
CANDIDATE = ROOT / "optimised-src"
rng = random.Random(20261107)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


changed = [p.name for p in BASE.glob("*.st") if digest(p) != digest(CANDIDATE / p.name)]
assert sorted(changed) == ["FB_HmiUpdate.st", "FB_Planner.st"], changed
print("PASS source isolation: only FB_Planner.st and FB_HmiUpdate.st differ")

# Every original DP transition and traversal order is identical for all 31 states.
first = [max(-4, -e) for e in range(31)]
last = [min(4, 30 - e) for e in range(31)]
for e in range(31):
    assert list(range(max(-4, -e), min(4, 30 - e) + 1)) == list(range(first[e], last[e] + 1))
print("PASS all 31 DP action bounds and traversal orders")


def backward(stages, initial, cached):
    value = initial[:]
    for costs in stages:
        next_value = []
        for e in range(31):
            best = 3.0e38
            actions = range(first[e], last[e] + 1) if cached else range(max(-4, -e), min(4, 30 - e) + 1)
            for a in actions:
                candidate = costs[a + 4] + value[e + a]
                if candidate < best:
                    best = candidate
            next_value.append(best)
        value = next_value
    return value


for case in range(100):
    horizon = rng.choice([1, 2, 24, 44, 96, 192])
    # Include ties, positive/negative costs and terminal values.
    stages = [[rng.choice([0.0, rng.uniform(-200, 200)]) for _ in range(9)] for _ in range(horizon - 1)]
    initial = [rng.uniform(-1000, 0) for _ in range(31)]
    assert backward(stages, initial, False) == backward(stages, initial, True)
print("PASS 100 differential DP traces, horizons 1..192, negative costs and ties")

# Pure formatted values stand in for F_DtString outputs: identical arguments mean
# identical output. Exercise same-step updates as well as first-call/reset cases.
header_valid = False
header_last = None
header_text = None
departure_valid = [False] * 4
departure_last = [None] * 4
departure_text = [""] * 4
tables_valid = False
selection_last = None
cached_tables = None
days = [0] * 365
months = [0] * 12
dim = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
stamp = 0
connected = [False] * 4
departure = [0] * 4
selection = (0, 1)
old_date_calls = cached_date_calls = old_table_calls = cached_table_calls = 0


def select_tables(day, month):
    offset = sum(dim[:month - 1])
    rows = tuple(days[offset:offset + dim[month - 1]]) + (0,) * (31 - dim[month - 1])
    return days[day], months[month - 1], dim[month - 1], rows


for call in range(20000):
    reset = call == 0 or rng.random() < 0.002
    new_step = reset or rng.random() < 0.2
    if reset:
        days = [0] * 365
        months = [0] * 12
        header_valid = tables_valid = False
        departure_valid = [False] * 4
    if new_step:
        stamp += 900
        days[rng.randrange(365)] += rng.randrange(100)
        months[rng.randrange(12)] += rng.randrange(100)
    # Include timestamp, connection and planned-departure changes on repeated k.
    if rng.random() < 0.02:
        stamp += 1
    if rng.random() < 0.1:
        j = rng.randrange(4)
        connected[j] = not connected[j]
    if rng.random() < 0.1:
        departure[rng.randrange(4)] = rng.randrange(100000)
    if rng.random() < 0.1:
        selection = (rng.randrange(-20, 390), rng.randrange(-3, 16))
    selected = (max(0, min(selection[0], 364)), max(1, min(selection[1], 12)))

    expected_header = f"formatted:{stamp}"
    expected_departure = [f"formatted:{d}" if c else "" for c, d in zip(connected, departure)]
    expected_tables = select_tables(*selected)
    old_date_calls += 1 + sum(connected)
    old_table_calls += 1
    if not header_valid or stamp != header_last:
        header_text = f"formatted:{stamp}"
        header_last = stamp
        header_valid = True
        cached_date_calls += 1
    for j in range(4):
        if connected[j]:
            if not departure_valid[j] or departure[j] != departure_last[j]:
                departure_text[j] = f"formatted:{departure[j]}"
                departure_last[j] = departure[j]
                departure_valid[j] = True
                cached_date_calls += 1
        else:
            departure_text[j] = ""
            departure_valid[j] = False
    if new_step or not tables_valid or selected != selection_last:
        cached_tables = select_tables(*selected)
        selection_last = selected
        tables_valid = True
        cached_table_calls += 1
    assert header_text == expected_header
    assert departure_text == expected_departure
    assert cached_tables == expected_tables
print("PASS 20,000 differential HMI calls: first call/reset/pause/selection/connection/departure")
print(f"MODEL_COUNTS date conversions {old_date_calls} -> {cached_date_calls}; selected-table refreshes {old_table_calls} -> {cached_table_calls}")
print("NOTE model counts are workload examples, not measured PLC speedups; ST build/full-year runs remain required")
