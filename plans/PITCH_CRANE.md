# Pitch: TIA container crane (PLC Challenge 2026, task 2)

These are the talking points for the finale (Mon 9 Nov).
- **What the numbers are.** Every number comes from the Python reference model (`tools/crane_plan.py`) on our own datasets.
- **How the PLC matches it.** The SCL planner (FB11) is checked against line-by-line Python transliterations of the SCL (`tia-src/12_planner_mirror.py` and `13_improve_mirror.py`). It compiles in TIA V21 with 0 errors.
- **What is not done yet.** As of 7 Nov (v1.6), **nothing has run on PLCSIM**. Do not claim a PLCSIM run until STATUS "Human TODO 1" has been done.
- J = 0.5·T/(76·N) + 0.5·M/(4·N); lower is better.

## 0. Lead with the HMI and the safety story (half of the TIA points)
**Alarm numbers below are the WinCC alarm IDs shown on screen (= PLC bit + 1):** 1 imbalance, 2 pick location empty, 3 drop location occupied, 4 unload ID not in Bay 0, 5 load ID not in Bay 1, 17 list order abandoned, 18 ship loaded out of balance (relaxed rule).

**Demo script (2–3 min, PLCSIM + WinCC RT simulation, on a TEST COPY of the project):**
1. **Given data, POČETNO STANJE.** The grid shows both bays with IDs. Alarms 4 and 5 appear: none of the unload IDs 111..777 is in Bay 0, and of the load IDs 123 is already on the ship and 124/125 do not exist. The AlarmLog screen shows the first missing ID and the count per list. **The given data has 0 executable transfers**, so START goes straight to ZAVRŠENO. Say so; it is the correct behaviour.
2. **Load the demo set** `tools/demo_db/fig1_half/` (6 unloads + 6 loads in the style of Figure 1, made by `tools/json_to_db.py`; import into the test copy and download; do **not** use the watch-table route in front of the jury, it needs all 192 lines of `watch_values.txt`), then POČETNO STANJE. About 50 commands, so about 1 min in AUTO.
3. **AUTOMATSKI → START.** The crane marker moves and M/T/J count up. The REZULTAT screen shows the predicted J against the live J.
4. **STOP after a lift, then START.** The transfer resumes. (POČETNO STANJE is ignored while the crane runs: STOP first.)
5. **POLUAUTOMATSKI.** Each click on SLJEDEĆI KORAK runs one command.
6. **RUČNO.** Lift from an empty cell → alarm 2, nothing moves. Put onto an occupied cell → alarm 3. POTVRDA → the system continues.
7. **After DONE.** Open a watch table on DB10/DB11 (`Current_state_of_Bay0/1`). They show the **final** yard, because the PLC keeps the given "current state" blocks live. POČETNO STANJE reloads the original data for a repeat run, also after an obstacle demo (an ID written into DB10 during AUTO to show alarm 3 is an obstacle, not a new data set; v1.6). A new data set is taken when DB10/DB11 are written while no job is in progress (before the first command, or after DONE), when new lists come together with yard changes, or when ≥ 8 cells are rewritten. New lists alone keep the loaded yard.
8. Optional list-check demo: `tools/demo_db/listcheck_bogus_unload/`. The unload list names yard container 555, which is also in the load list: alarm 4 for 555, and the valid load of 555 is still executed.

**Safety is a hard constraint, not a penalty:**
- CheckCmd in OB30 checks every lift and put before it is issued: pick not empty, drop not occupied, ship balance.
- The planner keeps |L−R| ≤ 5 after every lift and put. If the ship is loaded out of balance, it never makes the imbalance worse than the given data and it ends balanced (see §6).

## 1. One-slide story
**"The PLC plans the whole job like an industrial quay-crane scheduler (double cycling), proves how far it is from the theoretical optimum, and never risks the ship's balance or the list order."**

- **Why the order matters.** Every transfer that is not a double cycle (unload, then immediately load on the way back) costs about 36 s of empty travel.
- **A realistic rival:** a free-order greedy double cycling team with no lookahead and no local search (`tools/judge_sets/r1_jury_rival.py`). Over 34 sets (30 random sets plus 4 built from the spec's Figure 1) it averages **J = 1.0739** (these rival numbers use FB1 counting, mode 2). Our free order averages **1.0511** (never worse than the rival), and our list-order default **1.0603** (v1.5/v1.6), which beats the rival on 31 of 34 sets even though it keeps the list order. One of the 3 exceptions is the Figure-1 demo set (default 1.0053, rival 0.9897, our free order 0.9810): keeping the list order costs time there; see §6.
- **The planner runs inside the PLC** (FB11, SCL) and has five stages:
  1. **Exact list-order feasibility.** A dynamic-programming table proves whether the lists can be executed in their given order without breaking the balance rule.
  2. **Multi-start greedy**, with 4 look-ahead weights.
  3. **Local search over the transfer order** (relocate, swap and pair moves). It is never worse than the greedy, and in the default mode it keeps each list's order.
  4. **Local search over the drop cells** (relocate, swap).
  5. **Closed-form lower bound.** The HMI shows the gap to the theoretical optimum.

## 2. The ladder (30 random datasets, FB1 counting = +1 M per command)
Values are mean / worst J.

| Plan | Per-list order (PLC default) | Free order |
|---|---|---|
| Naive: list order, nearest free slot | 1.171 / 1.212, **infeasible on 15 of 30 sets** | same |
| Realistic rival: free-order greedy double cycling (34 sets) | n/a | 1.0739 (ours on the same 34: default 1.0619, free 1.0511) |
| v1.2 greedy | 1.0751 / 1.1683 | 1.0651 / 1.1508 |
| v1.3 greedy + IMPROVE (3000 evaluations) | 1.0684 / 1.1683 (4 sets fell back to free order) | 1.0549 / 1.1339 |
| v1.4 + exact order feasibility + SLOT phase | 1.0644 / 1.1683 (all 30 in list order) | 1.0538 / 1.1339 |
| **v1.5 + pattern move (block shifts in list order)** | **1.0626 / 1.1683** | **1.0538 / 1.1339** |
| Closed-form lower bound | 1.0293 | 1.0293 |

- **Over all 155 feasible round-1 benchmark sets** (random, edge, stress and judge sets), v1.3 → v1.4 → v1.5:
  - order 1: 1.0582 → 1.0558 → **1.0546**
  - free order: 1.0428 → 1.0422 → 1.0422 (unchanged; the v1.5 move only acts in order 1)
- **The lower bound is loose.** It ignores y-travel, occupancy and balance, so no plan reaches it on these sets.
- **Independent check by our judge agent (round 2).** The judge used an exact solver on small sets and a stronger annealer on the rest, under the same list-order rule.
  - **Small sets (N ≤ 13, 58 sets, exact enumeration):** our plan is optimal on 50, worst +0.53 %. That claim is defensible.
  - **Medium/large sets:** before round 2, the mean gap was +0.37 % over 123 sets, and 11 sets were more than 1 % above the best known plan. The cause was IMPROVE judging candidate orders with greedy drop cells and having no move that shifts a block of transfers.
  - **v1.5 fix (pattern move):** on those 11 worst sets, the gap went from +1.29 % to **+0.35 %** on average, and from at most +1.79 % to at most **+0.73 %**. Mean J over all 334 feasible sets in order 1: 1.0589 → 1.0577.
  - **Round 3, fresh sets (64 new adversarial sets, judge annealer with exact cell assignment):** on large (N 45–83) and near-full sets the default is on average **about +0.5 %** above the best plan the judge found (max +1.06 % on 1 of 64 sets, the only one above 1 %); scatter +0.23 %, unbalanced start +0.13 %, corner and very unequal lists ≈ 0. More IMPROVE budget does not close it (30 000 evaluations was worse on one set), so we did not raise it.
  - **Do not claim "proven optimal"** for larger sets.
- **v1.7: we score M by the spec rule** (a diagonal move counts 2; team decision). `World.CfgMMode` = 0 is the default, and the whole pipeline optimises for that rule. The ladder above is the FB1-counting history (mode 2, still selectable).

### 2b. Spec M rule (v1.7 default), order 1
| Set group | v1.6 planner run with the spec rule | **v1.7** (α retuned) | Lower bound | Judge best plan |
|---|---|---|---|---|
| 30 random | 1.1642 / 1.3146 | **1.1639 / 1.3146** | 1.0293 | 1.1563 (we are +0.65 % mean) |
| 401 feasible sets | 1.1680 | **1.1679** | 1.0167 | — |

- J is higher than under FB1 counting simply because every y change now costs an extra manipulation (19 s). The bound ignores y, so its 13 % "gap" is mostly bound weakness; the judge's annealer puts the real gap at about +0.65 %, of which +0.36 % is drop-cell choice (exact assignment not ported to SCL).

## 3. Robustness evidence (elimination criteria)
- **Balance.** `tools/crane_stress.py` runs:
  - all datasets, the judge sets and 300 freshly generated sets
  - order modes 1/0/2 × bow/stern mode 0/1 × M rule 2/0, plus four mid-run replans per set

  Each plan is executed command by command through the FB1 emulator and CheckCmd. The script checks the step rule after every lift and put, list membership, list order, that the plan never needlessly leaves the list order, determinism, and that the bound is consistent. Result: **464 datasets, 5232 plans plus 1650 mid-run replans, `STRESS_RESULT failures=0`**; 26 sets are infeasible in every mode, and all 26 are provably unbalanceable.
- **Lists followed.**
  - Default mode: each list is executed in its own order, interleaved.
  - The exact DP decides **before planning** whether that is possible under the balance rule. It is possible on 152 of the 155 feasible benchmark sets. On the other 3, no order-respecting plan keeps |L−R| ≤ 5, which the DP proves; the remaining 9 of the 164 sets cannot be balanced at all.
  - If the ship was loaded out of balance, FB10 first keeps the list order under the relaxed rule (never above the given imbalance, ends balanced, alarm 18). Over all 347 sets this cut the fallbacks to free order from 6 to 3.
  - Only then does FB10 fall back to free order, and it shows a warning alarm 17, "Liste se ne mogu izvršiti zadanim redoslijedom zbog ravnoteže broda".
  - A wrong list entry (for example an unload ID that is really a yard container) raises alarm 4 and is skipped, and since v1.5 it no longer blocks a valid entry with the same ID in the other list.
- **Infeasible data.** "Plan not feasible" (alarm 9, bit 8) appears only when the end state provably cannot be balanced.
- **Recovery.** After ACK the system continues:
  - A blocked put with a container on the hook is re-targeted to the nearest balance-safe free cell **that keeps the remaining lists feasible in their order** (v1.6: exact DP over the rest of the job; before, 38 of 4725 simulated obstacle cases broke the list order needlessly, now 0).
  - If no such cell exists, the system pauses and asks for MANUAL, with no ALARM/ACK loop.
- **Deterministic and cycle-time independent.** There are no random numbers. The evaluation budget is fixed, and the work per OB1 call is bounded (one greedy step, one replay, one DP row, or one step of the drop-cell search). The mirror tests check that the result does not depend on how the work is split over calls.
- **Relaxed rule (organizer question).** If the ship is loaded out of balance, the plan may pass through imbalances up to the given one in order to keep the list order. Ask whether that is acceptable. If not, remove the relaxed step from the FB10 fallback chain (one IF in INIT step 5 and PLANNING step 2); the plan then falls back to free order with alarm 17, as in v1.4.
- **Planning time.** Planning happens at POČETNO STANJE / START, before the crane moves. The scored T is FB1's simulated working time, so planning seconds cost 0 J. `Planner.DiagMaxCallMs` measures the per-call time on the CPU. It is **not yet measured**.

## 4. Industrial HMI extras
The **REZULTAT / OPTIMIZACIJA** screen shows:
- actual M/T/J under the spec rule (primary, v1.7), plus FB1's own counter MD107 and its J (secondary; they differ by design because FB1 counts +1 per command)
- predicted M/T/J, greedy J vs improved J, and the lower bound with the gap %
- planner progress, the order mode actually used, and the fallback warning

The **AlarmLog** screen shows:
- a 16-entry history with crane position and container ID
- the list check: the first missing ID and the count, per list

## 5. Agent-driven engineering story (code and presentation)
- **Closed loop:** spec → versioned contract (`tia-src/CONTRACT.md`) → Python reference model → SCL → TIA Openness compile (`TiaRun.exe`, `TIA_RESULT errors=0 warnings=0`) → parity mirrors → stress tests → **adversarial judge agents** (`tia-src/JUDGING.md`: 2 rounds, 3 judges per round, 24 findings, verdicts and fixes with before/after numbers).
- **FB1 is know-how protected.** Its source was recovered from the project's search index. That is how we found that FB1 counts **+1 M per move command**, and the planner exploits it: one combined x+y move per leg, never a zero-distance move.
- **Measured-decision culture.** We keep only changes that win across all datasets.
  - Kept: exact order DP and drop-cell search, −0.23 % mean, 105 sets better. Round 2: the pattern move, −0.11 % mean, 103 sets better and the worst gap to the judge from +1.8 % to +0.7 %.
  - Compared in round 2: the pattern relocate as a replacement for move 1, against an extra move type. The mean J was the same, so we kept the simpler one.
  - Rejected: multi-start local search, −0.08 % for 4× the time; distance-limited neighbourhoods, which were worse.
- **The engineer stays in the loop.**
  - The agents write, compile and test.
  - Humans own the GUI steps: HMI connection and prototypes, PLCSIM, and the organizer decisions (order mode, M rule).
  - Say honestly what was and was not run on PLCSIM at the time of the finale.

## 6. Likely jury questions
- *"Did you run it on PLCSIM?"* Answer with whatever STATUS says at the finale. Never claim a run that did not happen.
- *"Why not just follow the list?"* We do: each list in its own order (default). The two lists are interleaved, because that saves the empty trips. Strict "all unloads, then all loads" is mode 2, one HMI setting.
- *"What if the order cannot be kept?"* The DP proves it. The plan then uses free order and a warning alarm says so.
- *"What if the data is unbalanced from the start?"* Alarm 1 is shown. The planner first tries the step rule (never make it worse). If the list order is infeasible under that rule, it keeps the list order with a relaxed rule instead of giving up the order: |L−R| never exceeds the imbalance of the given data, once it is ≤ 5 it stays ≤ 5, and the plan ends balanced. Alarm 18 says so. Only if that is impossible too does it use free order (alarm 17).
- *"Where is the current state?"* In the given DB10/DB11 (kept live) and on the HMI grid.
- *"What would free order give on this demo set?"* On the Figure-1 demo set free order (HMI_IF.CfgOrderMode = 0) gives J 0.981 instead of 1.005 (−2.4 %), better than the naive rival's 0.990. It is one HMI setting once the organizers allow free order; we keep the list order by default because breaking it can eliminate.
- *"The ship gets worse at times on an unbalanced start?"* Only when the ship is loaded out of balance **and** the list order is impossible under "never worse" (the DP proves it). Then the plan may go back up to the given imbalance, never above it, and ends balanced (alarm 18). `World.CfgRelaxMin = TRUE` keeps the ship at the smallest imbalance ceiling that still allows the list order (e.g. 7 instead of 10), at +5…9 % J on those sets; it does not shorten the time spent above 5 much. Free order (alarm 17) is the other option. This is an organizer question.
- *"How do you know the plan is good?"* Point at the lower bound and the gap on the HMI, and at the independent judge comparison.

## Open items to settle with the organizers
1. **M rule (decided by the team, v1.7).** We follow the spec text: a diagonal move = 2. The given FB1 counts +1 per command (MD107); both are shown, the spec value as the primary M. If the organizers say MD107 is scored, set `World.CfgMMode` = 2 (and CfgAlpha [0, 100, 200, 300]).
2. **List order.** Must the lists be processed in list order? Spec §2 lists "Odlučivanje o redoslijedu kontejnera za manipulaciju" (deciding the container order) as an FB10 task, which suggests the order is free. Free order is worth about −0.8 % J (1.0626 → 1.0538). Switch with `HMI_IF.CfgOrderMode = 0`.
3. **Grading view.** Does the jury read DB10/DB11 or the HMI? Both are live now.
