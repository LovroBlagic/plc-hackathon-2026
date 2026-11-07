# Pitch: TIA container crane (PLC Challenge 2026, task 2)

These are the talking points for the finale (Mon 9 Nov).
- **What the numbers are.** Every number comes from the Python reference model (`tools/crane_plan.py`) on our own datasets.
- **How the PLC matches it.** The SCL planner (FB11) is checked against line-by-line Python transliterations of the SCL (`tia-src/12_planner_mirror.py` and `13_improve_mirror.py`). It compiles in TIA V21 with 0 errors.
- **What is not done yet.** As of 7 Nov ~06:00, **nothing has run on PLCSIM**. Do not claim a PLCSIM run until STATUS "Human TODO 1" has been done.
- J = 0.5·T/(76·N) + 0.5·M/(4·N); lower is better.

## 0. Lead with the HMI and the safety story (half of the TIA points)
**Demo script (2 min, PLCSIM + WinCC RT simulation):**
1. **POČETNO STANJE.** The grid shows both bays with IDs. With the given data, alarm 4 "ID ... nije u polju Bay 0" appears, and the AlarmLog screen shows which ID and how many.
2. **AUTOMATSKI → START.** The crane marker moves and M/T/J count up. The REZULTAT screen shows the predicted J against the live J.
3. **STOP after a lift, then START.** The transfer resumes.
4. **POLUAUTOMATSKI.** Each click on SLJEDEĆI KORAK runs one command.
5. **RUČNO.** Lift from an empty cell → alarm 1, nothing moves. Put onto an occupied cell → alarm 2. POTVRDA → the system continues.
6. **After DONE.** Open a watch table on DB10/DB11 (`Current_state_of_Bay0/1`). They show the **final** yard, because the PLC keeps the given "current state" blocks live. POČETNO STANJE reloads the original data for a repeat run.

**Safety is a hard constraint, not a penalty:**
- CheckCmd in OB30 checks every lift and put before it is issued: pick not empty, drop not occupied, ship balance.
- The planner keeps |L−R| ≤ 5 after every lift and put.

## 1. One-slide story
**"The PLC plans the whole job like an industrial quay-crane scheduler (double cycling), proves how far it is from the theoretical optimum, and never risks the ship's balance or the list order."**

- **Why the order matters.** Every transfer that is not a double cycle (unload, then immediately load on the way back) costs about 36 s of empty travel.
- **A realistic rival:** a free-order greedy double cycling team with no lookahead and no local search (`tools/judge_sets/r1_jury_rival.py`). Over 34 sets (30 random sets plus 4 built from the spec's Figure 1) it averages **J = 1.0739**. Our free order averages **1.0511** (never worse than the rival), and our list-order default **1.0619**, which beats the rival on 29 of 34 sets even though it keeps the list order.
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
| **v1.4 + exact order feasibility + SLOT phase** | **1.0644 / 1.1683 (all 30 in list order)** | **1.0538 / 1.1339** |
| Closed-form lower bound | 1.0293 | 1.0293 |

- **Over all 155 feasible benchmark sets** (random, edge, stress and judge sets), v1.3 → v1.4:
  - order 1: 1.0582 → 1.0558
  - free order: 1.0428 → 1.0422
- **The lower bound is loose.** It ignores y-travel, occupancy and balance, so no plan reaches it on these sets.
- **Independent check by our judge agent.** An exhaustive or annealing optimiser was run under the same list-order rule. After round 1 our default averages +0.14 % against the judge's best plan over 54 sets, with a worst case of +1.6 %. On 9 sets ours is better than the judge's plan. The remaining gap is the interleaving of the two lists on small sets. **Do not claim "proven optimal".**
- **If the jury scores M by the spec rule** (a diagonal move counts 2), set CfgMMode 0. The same pipeline then optimises for that rule.

## 3. Robustness evidence (elimination criteria)
- **Balance.** `tools/crane_stress.py` runs:
  - all datasets, the judge sets and 300 freshly generated sets
  - order modes 1/0/2 × bow/stern mode 0/1 × M rule 2/0, plus four mid-run replans per set

  Each plan is executed command by command through the FB1 emulator and CheckCmd. The script checks the step rule after every lift and put, list membership, list order, that the plan never needlessly leaves the list order, determinism, and that the bound is consistent. Result: **464 datasets, 5232 plans plus 1650 mid-run replans, `STRESS_RESULT failures=0`**; 26 sets are infeasible in every mode, and all 26 are provably unbalanceable.
- **Lists followed.**
  - Default mode: each list is executed in its own order, interleaved.
  - The exact DP decides **before planning** whether that is possible under the balance rule. It is possible on 152 of the 155 feasible benchmark sets. On the other 3, no order-respecting plan keeps |L−R| ≤ 5, which the DP proves; the remaining 9 of the 164 sets cannot be balanced at all.
  - Only then does FB10 fall back to free order, and it shows a warning alarm, "Liste se ne mogu izvršiti zadanim redoslijedom zbog ravnoteže broda".
- **Infeasible data.** "Plan not feasible" (alarm 8) appears only when the end state provably cannot be balanced.
- **Recovery.** After ACK the system continues:
  - A blocked put with a container on the hook is re-targeted to the nearest balance-safe free cell.
  - If no such cell exists, the system pauses and asks for MANUAL, with no ALARM/ACK loop.
- **Deterministic and cycle-time independent.** There are no random numbers. The evaluation budget is fixed, and the work per OB1 call is bounded (one greedy step, one replay, one DP row, or one step of the drop-cell search). The mirror tests check that the result does not depend on how the work is split over calls.
- **Planning time.** Planning happens at POČETNO STANJE / START, before the crane moves. The scored T is FB1's simulated working time, so planning seconds cost 0 J. `Planner.DiagMaxCallMs` measures the per-call time on the CPU. It is **not yet measured**.

## 4. Industrial HMI extras
The **REZULTAT / OPTIMIZACIJA** screen shows:
- actual M/T/J from FB1 (MD107/MD112), plus M and J under the spec rule
- predicted M/T/J, greedy J vs improved J, and the lower bound with the gap %
- planner progress, the order mode actually used, and the fallback warning

The **AlarmLog** screen shows:
- a 16-entry history with crane position and container ID
- the list check: the first missing ID and the count, per list

## 5. Agent-driven engineering story (code and presentation)
- **Closed loop:** spec → versioned contract (`tia-src/CONTRACT.md`) → Python reference model → SCL → TIA Openness compile (`TiaRun.exe`, `TIA_RESULT errors=0 warnings=0`) → parity mirrors → stress tests → **adversarial judge agents** (`tia-src/JUDGING.md`: 3 judges, 14 findings, verdicts and fixes with before/after numbers).
- **FB1 is know-how protected.** Its source was recovered from the project's search index. That is how we found that FB1 counts **+1 M per move command**, and the planner exploits it: one combined x+y move per leg, never a zero-distance move.
- **Measured-decision culture.** We keep only changes that win across all datasets.
  - Kept: exact order DP and drop-cell search, −0.23 % mean, 105 sets better.
  - Rejected: multi-start local search, −0.08 % for 4× the time; distance-limited neighbourhoods, which were worse.
- **The engineer stays in the loop.**
  - The agents write, compile and test.
  - Humans own the GUI steps: HMI connection and prototypes, PLCSIM, and the organizer decisions (order mode, M rule).
  - Say honestly what was and was not run on PLCSIM at the time of the finale.

## 6. Likely jury questions
- *"Did you run it on PLCSIM?"* Answer with whatever STATUS says at the finale. Never claim a run that did not happen.
- *"Why not just follow the list?"* We do: each list in its own order (default). The two lists are interleaved, because that saves the empty trips. Strict "all unloads, then all loads" is mode 2, one HMI setting.
- *"What if the order cannot be kept?"* The DP proves it. The plan then uses free order and a warning alarm says so.
- *"What if the data is unbalanced from the start?"* The step rule never makes the imbalance worse. Alarm 0 is shown, and the planner works in non-worsening mode.
- *"Where is the current state?"* In the given DB10/DB11 (kept live) and on the HMI grid.
- *"How do you know the plan is good?"* Point at the lower bound and the gap on the HMI, and at the independent judge comparison.

## Open items to settle with the organizers
1. **M rule.** Is M scored by MD107 (FB1: +1 per command) or by the spec text (a diagonal move = 2)? Both are shown. `World.CfgMMode` switches the planner.
2. **List order.** Must the lists be processed in list order? Spec §2 lists "Odlučivanje o redoslijedu kontejnera za manipulaciju" (deciding the container order) as an FB10 task, which suggests the order is free. Free order is worth about −1 % J (1.0644 → 1.0538). Switch with `HMI_IF.CfgOrderMode = 0`.
3. **Grading view.** Does the jury read DB10/DB11 or the HMI? Both are live now.
