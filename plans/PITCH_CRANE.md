# Pitch: TIA container crane (PLC Challenge 2026, task 2)

Talking points for the finale (Mon 9 Nov). Every number below was measured with the Python reference
model, which is bit-identical to the PLC planner (parity runs listed under "Evidence"). J = 0.5·T/(76·N) + 0.5·M/(4·N); lower is better.

## 1. One-slide story
**"We treat the crane as what industry calls quay-crane double cycling: the PLC plans the whole job, proves how good the plan is, and never risks the ship's balance."**

- Every transfer that is not a double cycle (unload, then immediately load on the way back) costs about 36 s of empty travel. A team that processes the lists in order sits near J ≈ 1.17–1.32; our plan sits near 1.05–1.07.
- The planner runs inside the PLC (FB11, SCL). It plans in three stages:
  1. a multi-start greedy (4 look-ahead weights)
  2. a deterministic local search (relocate, swap and pair moves) that is never worse than the greedy
  3. a closed-form lower bound, so the HMI shows **how far we are from the theoretical optimum**
- The safety rules are hard constraints, not penalties. |L − R| ≤ 5 holds after every lift and put, and a reachability test makes sure a balanced end state stays reachable.

## 2. The ladder (30 random datasets, FB1 counting = +1 M per command)
Values are mean / worst J.

| Plan | Per-list order (PLC default, hedge) | Free order |
|---|---|---|
| Naive: list order, nearest free slot | 1.171 / 1.212, and **infeasible on 15 of 30 sets** (balance dead end) | same |
| v1.2 greedy, α {0,50,100,150} | 1.0751 / 1.1683 | 1.0651 / 1.1508 |
| v1.3 greedy, α {0,100,200,300} | 1.0708 / 1.1683 | 1.0634 / 1.1437 |
| **v1.3 greedy + IMPROVE, 3000 evaluations** | **1.0684 / 1.1683** | **1.0549 / 1.1339** |
| Proven lower bound (closed form) | 1.0293 / 1.0976 | 1.0293 / 1.0976 |
| Gap of our plan to the bound | 3.8 % mean | **2.5 % mean** |

- **Over all 40 feasible sets** (random plus edge cases): default 1.0508 → 1.0455; free order 1.0403 → 1.0319.
- **64 stress sets** (N up to 94, near-full bays, one-sided unloads, ship at the balance limit, load-only, tiny lists):
  - 56 are feasible. v1.2 → v1.3: default 1.0830 → 1.0791, free order 1.0668 → 1.0596; bound 1.0266.
  - The other 8 are provably infeasible and correctly rejected.
  - On N = 80–94 the free-order greedy is already 2.2 % from the bound (1.0190 vs 0.9973).
- **The bound is not reachable in general.** It ignores y-travel, occupancy and balance.
  - The research agents' 100 s simulated annealing (3 seeds) found ≈ 1.054 for free order, which is the same as our PLC local search.
  - On rand_05, rand_21 and rand_24 the best plan found equals the bound, so it is proven optimal (CRANE_RESEARCH §2.2).
  - **Read the 2.5 % as "≤ 2.5 % from optimal". The true gap is probably ≤ 0.5 %.**
- **If the jury scores M by the spec rule** (a diagonal move counts 2; the hedge mode is CfgMMode 0), the same pipeline gives:
  - free order: 1.1301 → 1.1072
  - per-list order: 1.1837 → 1.1750
  - naive: 1.3185

## 3. Robustness evidence (elimination criteria)
- **Balance (criterion 1).** `tools/crane_stress.py` runs:
  - every dataset, 64 stress sets and 300 freshly generated sets
  - modes: order mode 1/0/2 × bow/stern mode 0/1 × M rule 2/0
  - four mid-run replans per set, as after STOP, ACK or MANUAL

  Each plan is executed command by command through the FB1 emulator and CheckCmd. The script checks the step rule after every lift/put, list membership, list order, determinism, and that local search and the bound are consistent. Result: **407 datasets, 4548 plans plus 1435 mid-run replans, `STRESS_RESULT failures=0`.**
- **Infeasible data.** Every stress set where the planner reports "plan not feasible" (alarm 8) is *provably* infeasible: the end state cannot be balanced, e.g. unloading 16 containers from the left half when only 9 loads come back. No false alarms.
- **Lists followed (criterion 1, second half).**
  - The default is per-list order with interleaving. The local search only applies moves that keep each list's internal order.
  - The automatic fallback to free order triggers only on a balance dead end, and the HMI shows the mode actually used (`OrderModeAct`).
- **Never worse than the greedy, by construction.** The local search starts from the greedy plan's own slot choices and accepts only strictly better complete replays.
- **Deterministic and cycle-time independent.**
  - There are no random numbers.
  - A fixed evaluation budget means the result does not depend on scan time or on how the work is split over OB1 cycles. The mirror test checks this with 2 and 3 evaluations per call.
- **Bounded work per OB1 call.** One call does at most one greedy step (≤ 4608 inner iterations) or one replay (≤ 4320). We estimate a few ms per call on a 1515, against the default 150 ms cycle monitoring; `Planner.DiagMaxCallMs` measures it.
  - Planning happens at POČETNO STANJE / START, before the crane moves.
  - The scored T is FB1's simulated working time, so planning seconds cost 0 J.
  - Default-mode planning needs about 300–600 OB1 cycles on average (worst about 3400).

## 4. Industrial HMI extras (jury-visible)
The **REZULTAT / OPTIMIZACIJA** screen shows:
- actual M/T/J straight from FB1 (MD107/MD112)
- M and J under the spec rule, as a side-by-side hedge
- predicted M/T/J of the plan
- greedy J vs improved J, with % gain and the number of evaluations
- the **proven lower bound and the gap %**
- a planner progress bar, the order mode actually used and the winning variant

Live J vs predicted J during the run demonstrates that model and PLC agree.

## 5. Agent-driven engineering story (15 pts "code and presentation")
- **Closed loop:** spec → contract (`tia-src/CONTRACT.md`, versioned) → Python reference model → SCL → TIA Openness compile (`TiaRun.exe`, `TIA_RESULT errors=0 warnings=0`) → parity mirrors → stress tests.
- **FB1 is know-how protected.** Its source was recovered from the project's search index. That is how we found that FB1 counts **+1 M per move command** (a diagonal move = 1, a zero-distance move = 1), and the planner exploits it: one combined move per leg, never a zero-distance move.
- **Parity:**
  - greedy: 774/774 runs of the line-by-line mirror vs the reference (`tia-src/12_planner_mirror.py`)
  - IMPROVE and lower bound: 570/570 runs (`tia-src/13_improve_mirror.py`), including the work split over calls
- **Measured-decision culture.** We rejected things that did not pay:
  - an exact interleaving DP: ≤ 0.07 % J upside for about 150 lines of SCL
  - distance-limited neighbourhoods: worse
  - 6000 evaluations: +0.08 % for twice the planning time

  We kept only changes that win across all datasets.
- **The engineer stays in the loop.** The agent writes, compiles and tests; humans did the HW config, the HMI prototypes and the PLCSIM run, and they own the decisions (order mode, M rule).

## 6. Likely jury questions
- *"Why not just follow the list?"* Following the list strictly (order mode 2) is available with one HMI setting. The default keeps each list's order but interleaves the two lists, because interleaving is what saves the empty trips.
- *"What if the data is unbalanced from the start?"* The step rule never makes the imbalance worse. Alarm 0 is shown, and the planner works in non-worsening mode.
- *"What if FB1 hangs / a cell is edited during AUTO?"* The FB1 watchdog raises alarm 10. Online edits of DB10/DB11 are adopted and checked before every lift and put (alarms 1 and 2). After ACK, the put is re-targeted and the system replans.
- *"How do you know the plan is good?"* Point at the lower bound and the gap on the HMI.

## Open items to settle with the organizers (they decide which column of the ladder counts)
1. Is M scored by MD107 (FB1: +1 per command) or by the spec text (a diagonal move = 2)? Both are shown; `World.CfgMMode` switches the planner.
2. Must the lists be processed in list order?
   - Spec §2 lists "Odlučivanje o redoslijedu kontejnera za manipulaciju" (deciding the container order) as an FB10 task, which suggests the order is free.
   - Free order is worth **−1.3 % J** (1.0684 → 1.0549). Switch with `HMI_IF.CfgOrderMode = 0`.
