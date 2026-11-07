# Crane planner research synthesis (TIA "PLC Challenge 2026")

Synthesizer agent, 7 Nov 2026. Inputs:
- Three research reports: OR literature, exact algorithms, tech community.
- `tia-src/CONTRACT.md` §4, `tia-src/FB1_ANALYSIS.md`, `plans/TIA_crane_plan.md` and `TEAM_NOTES.md`.
- One sweep I ran myself (below).

All J figures are means over the 30 `tools/crane_data/rand_*.json` sets unless stated otherwise.

**The M rule decides which numbers apply.**
- **CfgMMode 2** (FB1 adds +1 M per command) is what MD107 actually counts, and it is the current default.
- **CfgMMode 0** (spec p.10: a move that changes both x and y counts as 2) is the hedge. It applies if the organizers score by the spec text.

Both are quoted throughout.

> **Check I ran** (scratch script `C:\Users\lovro\AppData\Local\Temp\claude\66be7f3e70764d99\3bb00ff5-1acb-4157-866c-7a1fe6b593a0\scratchpad\syn\m2sweep.py`; it imports `crane_plan.py` read-only). It reproduced the exact-algorithms agent's greedy baseline: CfgMMode 2 with α {0,50,100,150} gives **1.0651**, max 1.1508.
> **Every alpha tuning result in TEAM_NOTES.md was measured under CfgMMode 0**, because `crane_eval.py` hardcodes `mmode: 0`. Under CfgMMode 2 the ranking changes:
>
> | α (single variant) | 0 | 25 | 50 | 75 | 100 | 150 | 200 | 300 |
> |---|---|---|---|---|---|---|---|---|
> | J, CfgMMode 2 | 1.0782 | 1.0689 | 1.0692 | 1.0692 | 1.0658 | **1.0655** | 1.0658 | 1.0671 |
> | J, CfgMMode 0 | 1.1466 | 1.1429 | 1.1371 | 1.1366 | **1.1359** | 1.1411 | 1.1443 | 1.1471 |
>
> | Multi-start set | CfgMMode 2 (mean / max) | CfgMMode 0 (mean / max) |
> |---|---|---|
> | {0,50,100,150} (current) | 1.0651 / 1.1508 | **1.1301** / 1.2444 |
> | {0,100,200,300} | **1.0634** / 1.1437 | 1.1328 / 1.2500 |
>
> An 8-variant set returned no result. CfgVariants is capped at 4, which is expected.

---

## 1. Executive summary: the 5 most actionable ideas

Ranked by expected J gain divided by (PLC implementation cost + risk). Below the table: how to test each one, and where it goes in SCL.

| # | Idea | Expected ΔJ (mode 2 / mode 0) | Cost | Risk |
|---|---|---|---|---|
| 1 | Retune multi-start α for the M rule actually in force | −0.0017 / +0.0027 (measured) | ~0, data only | none |
| 2 | Plan before START, and make long planning safe (OB80, cycle-time limit, per-call cap) | enables #3; prevents a CPU STOP | low | removes risk |
| 3 | Deterministic local-search improvement phase after the greedy | about −0.010 (−1.0 %) / −0.023 (−2.1 %) | medium (~200 SCL lines plus parity) | medium, behind a flag |
| 4 | OrderMode 1 hedge: improve the interleaving only (merge DP or restricted LS) | 0 unless list order becomes mandatory; then possibly several % | medium | low (dormant) |
| 5 | Closed-form lower bound plus a "gap to optimum" figure on the HMI and in the pitch | 0 J; scores HMI and presentation points | low (~30 SCL lines) | none |

### 1. Retune CfgAlpha for the active M rule
- **What.** Under CfgMMode 2 the M term is a constant 4 per transfer, so the planner is a pure-time minimiser. The look-ahead weight works best at higher α there.
  - Switch to `CfgAlpha = [0,100,200,300]` **if CfgMMode stays 2**.
  - Keep `[0,50,100,150]` if the organizers say the spec rule (CfgMMode 0) is scored.
  - Make the α set follow CfgMMode automatically. Two constant arrays are enough.
- **Test.** Give `tools/crane_eval.py` a `--mmode` argument (default 2, to match FB1) and use it in `base` and `naive()`. Then rerun the `ALPHAS`/`SWEEP` blocks. Also re-check `win counts` so that no variant is dead weight.
- **SCL.** Only the `World.CfgAlpha[1..4]` start values (or an FB10 INIT assignment keyed on CfgMMode). FB11 is unchanged, so Python/PLC parity is unaffected.

### 2. Plan before START; make planning time free and safe
- **Why.** T is FB1's accumulated working time, not wall-clock time (exact-algorithms report). Seconds of PLC computation before START therefore cost **nothing** in J. That is what makes idea #3 affordable.
- **What.**
  - Plan at INITIAL STATE / READY, before START.
  - Add an **OB80 time-error OB** that only sets an alarm bit. Without OB80, a cycle-time overrun sends the S7-1500 to STOP (Siemens V21 docs, "Cycle time and maximum cycle time").
  - Raise the maximum cycle time in the CPU properties, e.g. to 500 ms.
  - Keep the per-call work cap: CfgStepsPerCall, or a cap on evaluations per call.
  - Measure the worst call with `RUNTIME` and show it on a diagnostics field.
  - The CONTRACT §1.4 limit of "≤ 500 calls per job" must be raised for #3, to about 5000 calls (still ≈ 10–100 s of OB1 time).
- **Test.** Python cannot test this; it is a PLCSIM measurement. Log `RUNTIME` max per FB11 call on an N = 96 set (`edge_big_swap` or a generated 48+48 set).
- **SCL.** A new OB80 (an empty body plus an alarm bit in `HMI_IF.AlarmWord`), the CPU properties, and an FB11 statistic `MaxCall_us`.

### 3. Deterministic local search over the greedy plan
- **Gain.** Exact-algorithms experiments, 30 sets:

  | Evaluations | J, CfgMMode 2 | J, CfgMMode 0 |
  |---|---|---|
  | 0 (greedy only) | 1.0651 | 1.1301 |
  | 200 | 1.0608 | 1.1248 |
  | 1000 | 1.0571 | 1.1156 |
  | 3000 | **1.0542** | **1.1067** |

  - It improved 29 of 30 sets under CfgMMode 2.
  - It matched 20–300 s of simulated annealing, which the exact-algorithms agent ran three times for 100 s on the 8 hard sets; that annealing could not beat it.
- **What.**
  - The plan is a permutation of transfers. The evaluator re-simulates the whole permutation from the World snapshot using **the planner's own §4.4 slot rule** (Pass A, then Pass B, with Nx = the successor in the permutation). It also uses the §4.3 step rule and reachability. Cost is K = T + 190·M.
  - **Moves:** relocate one transfer, swap two, relocate an adjacent pair. Use first improvement, in a fixed nested-loop order, with no random numbers. Python and SCL then stay bit-identical.
  - Accept a candidate only if it is strictly better **and** the replay found a legal slot at every step.
  - Speed-up: cache the per-step state (L, R, T, M, crane, plus an undo log of grid writes) and replay only from min(i, j) − 1. This roughly halves the cost.
- **Caveat.** The exact-algorithms agent's own slot rule dead-ended when replaying some greedy sequences. The evaluator **must** be the planner's rule, so that the starting point is exactly the greedy plan and can only get better.
- **Budget.** About 115k basic operations per evaluation at N = 48, which estimates to 1–10 ms on a 1515. This is **not measured**. Use CfgImproveEvals = 1000 by default and 3000 if PLCSIM timing allows. A fixed evaluation budget keeps the result independent of scan timing.
- **Test.**
  1. Port the scratchpad `plcls.py` into `tools/crane_plan.py` as `--improve N`, using `step_candidates` for the slot choice.
  2. In `crane_eval.py`, add columns `ls200`, `ls1000` and `ls3000`, run `cp.simulate()` on every improved plan, and assert determinism.
  3. Check the parity CSV (§4.7) between Python and PLC on at least 5 sets.
- **SCL.** In FB11 `"Crane_Planner"`, add a new phase after the variant winner is chosen: `Phase := IMPROVE`. The rest:
  - Store the permutation in FB11 statics as `Perm[1..96]`. Run a re-entrant replay that processes k replay steps per call.
  - Write `World.Plan` only when the phase ends, so the contract still holds: written once, on Done.
  - Add `CfgImprove` (Bool) and `CfgImproveEvals` (DInt) as contract v1.1 members.
  - If the budget runs out, or on any error, keep the greedy plan. The plan never gets worse.

### 4. OrderMode 1 hedge: improve only the interleaving
- **Why.**
  - If the organizers answer "lists must be processed in order", the only freedom left is how the two lists interleave.
  - Under CfgMMode 0 the greedy in OrderMode 1 costs +0.054 J against free order (TEAM_NOTES).
  - The OR-literature agent proposes an exact merge DP over states (i, j, last_bay, D = L − R). That is about 49·49·2·25 ≈ 120k states.
- **Caveat.** The DP is exact only on the relaxed edge cost from §2 below. Real slot occupancy is history-dependent, so the DP result must be replayed through the §4.4 slot rule, the same way as in #3.
- **Cheaper equivalent.** Run #3 with only the moves that keep each list's internal order. That means swapping adjacent transfers from *different* lists and shifting a block of loads relative to the unloads. This reuses all of the #3 code.
- **Test.** `crane_eval.py`'s existing `order1` column, with and without `--improve`.
- **SCL.** No new block. It is the move filter of #3, keyed on CfgOrderMode = 1. Implement the DP only if the organizers mandate order **and** restricted LS leaves a large gap.

### 5. Closed-form lower bound and "gap to optimum" (J gain 0; jury value high)
- **What.** Compute the bound from §2 at INIT, in O(N). Show `PredJ`, `LB_J` and `Gap % = PredJ/LB_J − 1` on the HMI. Use it in the pitch: "our plan is provably within x % of the theoretical optimum".
- **Test.**
  - Replace `eval_one`'s `out["lb"] = cm.J(P*580, P*3, N)`. It is invalid as a reference: an empty move can be skipped only before the first transfer, because the next source cell is always occupied, so M ≥ 4N − 1. It is also loose, at 0.757.
  - Use the closed form from §2 instead.
  - Assert `lb <= J` on all 43 sets. Optionally assert it against a brute force (the OR-literature agent's `bf.py`) on small grids.
- **SCL.**
  - Add a new FC `"Crane_LowerBound"` : Real, called by FB10 at INIT. It reads UList/LList positions from the World grids.
  - Add `HMI_IF.LB_J` and `HMI_IF.GapPct` (contract v1.1).
  - The stronger assignment (Hungarian) bound, 1.0387 vs 1.0352, is optional. It needs about 1M inner iterations spread over scans, and it is not worth it before the code freeze.

---

## 2. Theoretical lower bound and how far the greedy is from it

### 2.1 Structure (OR-literature agent; my reading agrees with the model)
- Every loaded move crosses the 2-column gap between the yard (global columns G 0..3) and the ship (G 6..9).
- The drop cell is free. A drop column between the current source and the next source adds no x-time: the loaded leg is shortened by exactly as much as the empty leg is lengthened. This is the Steiner-point argument (Vis & Roodbergen 2009).
- **So total x-travel depends only on the order of the sources.** In columns (×6 s):

  ```
  X = 2·Σ_unload x_ship + 2·Σ_load (3 − x_yard) + 3·N + 3·S + F
  ```

  - **S** is the number of consecutive same-bay pairs (single cycles). It is forced by |u − l|:
    - first job a load: S = u − l if u > l, else max(0, l − u − 1)
    - first job an unload: S = max(0, u − l − 1) if u ≥ l, else l − u
  - **F** depends on the first job, with the crane starting at yard (0,0): F = 2·x_first − 3 for a load, 6 for an unload.
- **The bounds:**
  - **T_LB = 40·N + 6·X_min** seconds. This ignores y-travel, which in CfgMMode 2 is hidden inside each loaded move whenever 2.3·Δy ≤ 6·ΔG, i.e. up to 7 rows.
  - **M_LB = 4N − [first load sits at yard (0,0)]**.
- **Brute-force check** (4×4 grids, ≤ 3+3 jobs, all orders and all drop cells, **no balance**): the bound never exceeded the optimum.
  - Mode 2 gap: mean 1.4 s, max 9.2 s.
  - Mode 0 gap: mean 23 s, max 56 s. In mode 0 the y-changes cost extra M.
- **Sanity check against Tav.**
  - Balanced lists with uniform columns: 2·1.5 + 3 = 6 columns, i.e. 36 s of travel plus 40 s of lift/put = **76 s = Tav**. That gives J ≈ 1.00. The organizers calibrated Tav to perfect dual cycling.
  - Unload-only lists: ≈ 94 s per transfer, J ≈ 1.12. Absolute floor: J ≥ 0.897.
- **Balance.** The bound above ignores balance. Balance costs time only when a load is forced into the far half beyond the next unload's column, at +12 s per column (loaded leg plus empty leg).
  - The exact-algorithms agent's Lagrangian balance multiplier raises the assignment bound by up to 0.027 J. Examples: rand_01 1.030 → 1.057, rand_10 1.054 → 1.080.

### 2.2 Numbers (30 random sets)

| | CfgMMode 2 (FB1, default) | CfgMMode 0 (spec) |
|---|---|---|
| Naive (list order, nearest slot) | not measured (expected to be about the mode 0 value) | 1.3185 (feasible on only 14/30) |
| **Our greedy, multi-start (contract v1)** | **1.0651** (verified here) | **1.1301** |
| Greedy with α {0,100,200,300} | 1.0634 (verified here) | 1.1328 |
| Greedy + LS, 3000 evaluations | 1.0542 | 1.1067 |
| Best found (SA plus LS) | ≈ 1.0542–1.0551 | 1.1067 |
| Lower bound: assignment + balance multiplier | **1.0387** | **1.0623** |
| `crane_eval.py` current "LB" (58 s + 3 M) | 0.757, **not a valid reference** | 0.757 |

- **The greedy's distance from the true optimum:**
  - **CfgMMode 2:** 2.5 % above the proven bound, ≈ 1.0 % above the best plan found. The true optimum is probably within about 0.2 % of the best found; three seeds of 100 s annealing did not improve it. This is not proven.
  - **CfgMMode 0:** 6.4 % above the bound, 2.1 % above the best found. The bound is looser here, because its relaxation lets every loaded leg be a pure-x move.
- **Proven optima:**
  - rand_05, rand_21 and rand_24: the best plan equals the bound.
  - rand_08 by exhaustive search: optimum 1.1266 vs greedy 1.1365 in mode 2. In mode 0 the greedy is optimal.
- **What this means.** Every team that dual-cycles properly lands near J ≈ 1.0–1.1. Goodchild & Daganzo also report that results are not very sensitive to the algorithm used. Our remaining J upside is about 1 % (mode 2) to 2 % (mode 0). A team that does not interleave sits near 1.3. The differentiators are therefore:
  1. Never be infeasible on balance. Elimination is far worse than 1 % of J.
  2. Never waste M on a zero-distance move. FB1 adds +1 M for one, and the runtime already drops such moves in MANUAL; the planner never emits one.
  3. Maximise alternation between unload and load.
  4. Drop "between": next to the next source.
  5. Only then, local search.

---

## 3. Hackathon-winning takeaways

**Past editions were won by finishing.** In 2024, 1 of 11 teams solved the task, and it won (Montelektro article). The 2021 graders were the task authors (Montelektro plus FER) and asked about robustness. Expect industry commissioning engineers.

**Robustness (protects the elimination criteria and the "no trip" mindset):**
- OB80 plus a raised maximum cycle time (#2). A planner overrun must never STOP the CPU during the demo.
- Turn the likely jury questions into a scripted PLCSIM checklist, and run it before the code freeze:
  1. An unload ID that is not in Bay 0, a duplicate ID, or ID 0 in a list.
  2. An infeasible balance state.
  3. FB1 never returning to 0 (watchdog).
  4. STOP→RUN in the middle of a job with a container on the hook.
  5. START pressed twice, or the mode switched in the middle of a command (it takes effect only at a command boundary).
  6. MANUAL with bay ≠ 0/1, a pick from an empty cell, or a drop onto an occupied cell.
  7. Empty lists, N = 96, INITIAL STATE pressed during a run.
- Never trade a robustness feature for a J gain. Keep #3 behind `CfgImprove`. If the improve phase errors, keep the greedy plan.
- Ask the organizers which M rule is scored: FB1's MD107 or spec p.10. It is the biggest unknown. It changes the LS gain (1 % vs 2 %) and the α choice (#1).

**HMI (10 points TIA, ISA-101 style):**
- Grey background. Colour only for meaning: pending unload, pending load, done, empty. Strong highlights only for the next pick, the next drop and alarm cells.
- A balance bar for L − R with the ±5 limits marked.
- A crane/hook graphic using movement animations bound to CraneX/Y/Bay.
- Live actual vs predicted T, M and J, plus **the LB and gap % (#5)**.
- A "next command" panel for SEMI-AUTO.
- READY/OFF and the mode lamps on every screen.
- Alarm history: an alarm log assigned to the alarm class, plus an alarm view showing logged alarms.
  - Timestamps are logged in UTC. Check how they display.
  - Prefer HMI discrete alarms on the AlarmWord, since PLC alarm forwarding under PLCSIM is unverified for V21.
  - Byte order of a Word trigger tag (**unverified**): bit 0 may map to DBX(n+1).0. Toggle each bit once from a watch table to check.
- Generate the 96 grid cells via Openness export → generate → import (or SiVArc) instead of drawing them by hand.

**Presentation:**
- Structure: problem → model → measured impact.
- Frame it as "the industry's quay-crane double-cycling / AS-RS dual-command problem, solved with a bounded deterministic greedy plus local search that fits a PLC scan budget".
- Show one slide with the ladder:

  | Plan | J |
  |---|---|
  | naive | ≈ 1.32 |
  | greedy | 1.065 |
  | greedy + LS | ≈ 1.054 |
  | provable bound | 1.039 |

- Show the balance trace staying within |L − R| ≤ 5 at every step.
- Evidence slides:
  - 0 compile errors and 0 warnings.
  - Python oracle ↔ PLC parity, bit-identical, on N datasets.
  - The robustness checklist pass count.
  - Optionally, a TIA Test Suite Style Guide check (`tia-testsuite` skill) and a reference to the Siemens Programming Style Guide (S7-1200/1500).
- Record a demo video of an AUTO run (≤ 4 min) as a backup for the live demo.
- Ship a one-page tag/interface table: DB100 World, DB101 HMI_IF, MB100–103, MD107, MD112.

---

## 4. Annotated bibliography

The research agents found these sources. I did **not** re-fetch them; most were read from abstracts only. Flags: **[V]** means the agent quoted concrete content from the source. **[U]** means a detail is unverified, as noted. **[?]** means the agents described the source inconsistently, or it is a secondary aggregator.

### Quay-crane double cycling
- **[V]** Goodchild & Daganzo (2006). "Double-cycling strategies for container ships and their effect on ship loading and unloading operations." *Transportation Science* 40(4):473–483. doi:10.1287/trsc.1060.0148. https://its.berkeley.edu/node/4676 · PDF: https://urbanfreightlab.com/wp-content/uploads/2023/05/Double-Cycling_Strategies_for_Container_Ships_and_.pdf
  - Johnson's rule on a two-machine flow shop. About 20 % fewer cycles (about 40 % for hatchless ships), and results are not sensitive to the algorithm.
  - It gives our S_min / max(U, L) cycle bound. Its stacking precedence does not apply to us.
- **[V]** Goodchild & Daganzo (2007). "Crane double cycling in container ports: planning methods and evaluation." *Transportation Research Part B* 41(8):875–891. https://its.berkeley.edu/node/4661
- **[V]** Lee, Liu & Chu (2015). "Optimal algorithm for the general quay crane double-cycling problem." *Transportation Science* 49(4):957–967. https://pubsonline.informs.org/doi/pdf/10.1287/trsc.2014.0563
  - Precedence from hatch covers, solved by Sidney decomposition. It relates to our capacity precedence: when the yard is full, a load must go first.
- **[?]** Zhang & Kim (2009). "Maximizing the number of dual-cycle operations of quay cranes in container terminals." *Computers & Industrial Engineering* 56:979–992. doi:10.1016/j.cie.2008.09.008. Links: the DOI, or the aggregator https://www.bohrium.com/paper-details/maximizing-the-number-of-dual-cycle-operations-of-quay-cranes-in-container-terminals/811901423670263810-3899
  - Maximising dual cycles is the same as minimising S.
- **[V]** Zheng, Pang, Liu & Xu (2020). *Journal of Combinatorial Optimization* 39(3). https://link.springer.com/10.1007/s10878-019-00508-9 (DP with internal reshuffles; low relevance).
- **[V]** Meisel & Wichmann (2010). *OR Spectrum* 32(3):569–591. https://www.econbiz.de/Record/container-sequencing-for-quay-cranes-with-internal-reshuffles-meisel-frank/10003983250 (GRASP; low relevance, since we have no stacking).
- **[V]** Liu et al. (2015). *Transportation Research Part E*. https://hal.archives-ouvertes.fr/hal-01220019 (low relevance).
- **[?]** arXiv:2406.08534. https://arxiv.org/abs/2406.08534
  - One agent describes it as a hybrid GA for dual cycling plus yard rehandles, reporting 15–20 % less time. The other describes it as a 2024 general double-cycling paper with a related-work review.
  - The author and contents are not confirmed. It is a metaheuristic, not suitable for a PLC.
- **[?]** Zeng, Diabat & Zhang (2015). *Maritime Policy & Management* 42(8):806–826. https://ideas.repec.org/a/taf/marpmg/v42y2015i8p806-826.html (cited for the flow-shop framing only; not read).

### AS/RS dual-command sequencing (the closest analogue: Chebyshev travel and free slot choice)
- **[V]** Han, McGinnis, Shieh & White (1987). *IIE Transactions* 19(1):56–66. doi:10.1080/07408178708975370. https://scilit.com/publications/0359428acb8149938b47962437036f9f
  - A nearest-neighbour rule that stores each container in the open slot nearest the next retrieval, plus a dual-command lower bound. This is our "drop between" rule.
- **[V]** Lee & Schaefer (1996). "Retrieval sequencing for unit-load AS/RS with multiple openings." *International Journal of Production Research* 34(10):2943–2962. https://iaorifors.com/paper/18143
  - Hungarian algorithm, plus assignment ranking, plus tour breaking. Basis of the assignment lower bound.
- **[U]** Bozer & White (1984). *IIE Transactions* 16(4):329–338. https://apps.dtic.mil/sti/pdfs/ADA119463.pdf
  - Expected single- and dual-command times. The Chebyshev-metric details were not checked in the full text.
- **[V]** van den Berg & Gademann (1999). *IIE Transactions* 31. https://research.utwente.nl/en/publications/optimal-routing-in-an-automated-storageretrieval-system-with-dedi/
  - Polynomial only for dedicated storage. Free slot choice makes the problem TSP-like and NP-hard.
- **[V]** Gharehgozli, Yu, de Koster & Udding (2014). "An exact method for scheduling a yard crane." *European Journal of Operational Research* 235(2):431–447. doi:10.1016/j.ejor.2013.09.038. https://repub.eur.nl/pub/76426
  - Assignment, then patching, then branch-and-bound. Reports −30 % against random and −14 % against nearest-neighbour.
- **[V]** Gharehgozli, Yu, Zhang & de Koster (2017). "Polynomial time algorithms to minimize total travel time in a two-depot automated storage/retrieval system." *Transportation Science* 51(1):19–33. doi:10.1287/trsc.2014.0562. https://repub.eur.nl/pub/98935
  - Our two bays play the role of the two depots. This is an analogy, not a formal reduction.
- **[V]** Gharehgozli et al. (2015). *Transportation Science* 49(3):686–705 (twin cranes, adaptive large neighbourhood search). https://econpapers.repec.org/RePEc:inm:ortrsc:v:49:y:2015:i:3:p:686-705
- **[U]** Vis & Roodbergen (2009). "Scheduling of container storage and retrieval." *Operations Research* 57(2):456–467. doi:10.1287/opre.1080.0621. https://repub.eur.nl/pub/16463
  - Drop cells treated as Steiner points. The polynomial-complexity claim is unverified.

### Sequencing theory
- **[V]** Gilmore & Gomory (1964). "Sequencing a one state-variable machine: a solvable case of the traveling salesman problem." *Operations Research* 12(5):655–679. https://econpapers.repec.org/RePEc:inm:oropre:v:12:y:1964:i:5:p:655-679
  - Once x-cost is fixed, what remains is 1-D in y. It justifies the y-sweep.
- **[V]** Stacker crane problem: Frederickson, Hecht & Kim (1978), *SIAM Journal on Computing*, 9/5-approximation. Overview: https://en.wikipedia.org/wiki/Stacker_crane_problem
- **[V]** Atallah & Kosaraju (1988). *SIAM Journal on Computing* 17(5):849–869. https://epubs.siam.org/doi/10.1137/0217053
- **[U]** arXiv:2410.06764 (stacker crane NP-hard on trees, FPT by cycle rank). https://arxiv.org/abs/2410.06764
- **[V]** Chalasani & Motwani (1999). *SIAM Journal on Computing* (unit-capacity pickup and delivery, 2-approximation). https://iaorifors.com/paper/29413 · Anily & Hassin (1992), *Networks* 22 (no URL given).
- **[U]** ATSP assignment bound and Karp patching:
  - https://arxiv.org/pdf/2308.02946v5
  - https://repository.royalholloway.ac.uk/items/704dac27-e040-389b-bd24-dc35d696ffe4/6/gutin-construction_heuristics.pdf
  - Chebyshev TSP note: https://mdpi.com/2227-7390/10/21/4018/html
- **Not from the literature** (agents' own synthesis): the closed-form X bound in §2, the merge DP, and the claim that a y-sorted interleave is optimal. Treat them as our own work. The bound was checked by brute force without balance.

### Ship balance and stability
- **[V]** Ambrosino & Sciomachen (2004). *Transportation Research Part A* 38(2):81–99. https://ideas.repec.org/a/eee/transa/v38y2004i2p81-99.html · and (2009) *Maritime Economics & Logistics* 11(1):98–120. https://econpapers.repec.org/RePEc:pal:marecl:v:11:y:2009:i:1:p:98-120 (master bay plan, exchange local search to restore stability).
- **[V] [U]** Chu, Zhang & Yang (2017). *PLoS ONE* 12(7):e0180370. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0180370
  - Multiple quay cranes, double cycling with a balance constraint each period, Lagrangian relaxation. The gap to the exact optimum was under 6 %.
  - The exact form of the balance formula is unverified.
- **[U]** "The QCSP with stability constraints." *IEEE Transactions on Automation Science and Engineering*, 2018. No URL given.
- **[U]** Unidirectional QCSP with vessel stability. *European Journal of Operational Research*, 2021. doi:10.1016/j.ejor.2020.09.033.

### Event, Siemens practice and HMI
- **[V]** Montelektro, "Organization of the PLC hackathon" (2024: 11 teams, 1 solved it). https://www.montelektro.hr/organization-of-the-plc-hackathon/
- **[V]** UniZG Rector's Award report on the 2021 edition (docx, Croatian). https://apps.unizg.hr/rektorova-nagrada/javno/radovi/1616/preuzmi
- **[V]** Event site. https://plc.eestec.hr/
- **[V] [U]** Siemens press release on PLC Challenge 2019 (Slovenian). https://assets.new.siemens.com/siemens/assets/api/uuid:36fae5b5-79fa-4545-93ff-bb99b472744b/Sporocilo-za-medije-PLC-Challenge.pdf
  - Our TIA task may descend from this competition. That link is unverified.
- **[V]** Siemens Italy, OlimpiadiAutomazione 2022 rules (a judging rubric). https://assets.new.siemens.com/siemens/assets/api/uuid:74ee6ff1-ee37-447c-a531-dfca903ea90b/sce-olimpiadiautomazione-bando-regolamento-2022.pdf
- **[V]** Siemens V21 docs, cycle time and cycle monitoring (OB80, STOP behaviour). https://docs.tia.siemens.cloud/r/en-us/v21/functional-description-of-s7-1500-cpus-s7-1500/setting-the-operating-behavior-s7-1500/cpu-properties-s7-1500/cycle-time-and-maximum-cycle-time-cycle-monitoring-time-s7-1500
  - The "150 ms default" comes from a third-party blog and is **[U]**.
- **[V]** Siemens V21 docs, alarm logging for RT Advanced. https://docs.tia.siemens.cloud/r/en-us/v21/working-with-alarms-basic-panels-panels-comfort-panels-rt-advanced-rt-professional/alarm-logging-basic-panels-panels-comfort-panels-rt-advanced-rt-professional/configuring-alarm-logging-panels-comfort-panels-rt-advanced/basics-on-alarm-logging-panels-comfort-panels-rt-advanced
- **[V]** Siemens Programming Style Guide for S7-1200/S7-1500 (support entry 109478084; the link is v1.1). https://cache.industry.siemens.com/dl/files/084/109478084/att_851379/v1/81318674_Programming_Styleguide_DOCU_v11_en.pdf
- **[V]** ISA-101 "going gray". https://control.com/technical-articles/going-gray/ · https://www.dmcinfo.com/blog/20143/getting-started-with-wincc-oa-part-9-color-database-and-high-performance-best-practices/
- **[U]** Community knowledge-base posts. Each gotcha in them is unverified for V21.
  - https://industrialmonitordirect.com/blogs/knowledgebase/tia-portal-wincc-array-table-display-techniques
  - https://industrialmonitordirect.com/blogs/knowledgebase/simulating-alarm-logs-in-wincc-runtime-without-plc
  - https://industrialmonitordirect.com/blogs/knowledgebase/siemens-scl-timer-in-for-loop-fixing-the-freeze-issue
- **[?]** Hackathon demo advice (generic):
  - https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/
  - https://angelhack.com/blog/10-tips-to-help-you-rock-your-next-hackathon-demo/
  - https://dev.to/cloudinary/how-to-win-a-hackathon-1377
- **[U]** 1515-2 PN instruction timings (used for the LS budget estimate). https://mall.industry.siemens.com/mall/cs/cz/Catalog/Products/10204208 · https://sterowniki-plc.net/image/catalog/Karty%20katalogowe/Siemens/6ES7515-2AM00-0AB0.pdf

### Experiment artefacts
These are in the scratchpad, not in the repo; copy them into `tools/` if adopted.
- `...\scratchpad\lb\bf.py`: brute-force check of the bound.
- `...\scratchpad\exp\`:
  - `exact.py`: Hungarian algorithm and the assignment bound.
  - `plcls.py`: PLC-style local search; the reference for #3.
  - `ls.py` and `longsa.py`: local search and simulated annealing.
  - `lbbal.py`: bound with the balance multiplier.
  - `lagr.py`, `lb2.py` and `brute.py`.
  - Result files: `sa2.txt`, `sa0.txt`, `plcls2.txt`, `plcls0.txt`, `lbbal2.txt`, `lbbal0.txt`, `longsa*.txt`.
- `...\scratchpad\syn\m2sweep.py`: the α sweep in this document.

`...` stands for `C:\Users\lovro\AppData\Local\Temp\claude\66be7f3e70764d99\3bb00ff5-1acb-4157-866c-7a1fe6b593a0`.
