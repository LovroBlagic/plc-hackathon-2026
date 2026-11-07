# Judging log: TIA container crane

The judges' reports, our verdicts and our actions, one section per round. All J values use the FB1 M rule (CfgMMode 2), unless a row says otherwise. "v1.3" is the planner before the round (legacy flags `--noexact --slot 0`, `crane_bench.py --legacy`). "v1.4" is the planner after it.

## Round 1 (7 Nov 2026, builder response)

Benchmark files:
- `tools/bench/v13_m2.json` and `tools/bench/v14_m2.json`: 164 sets (crane_data, crane_data_stress, judge_sets) × order 1 and order 0, IMPROVE at 3000 evaluations.
- Compare them with `python tools/crane_bench.py --compare tools/bench/v13_m2.json tools/bench/v14_m2.json`.

| ID | Judge | Severity | Verdict | Action | Before → after |
|---|---|---|---|---|---|
| R1-E1 | elimination | critical | **Real.** Reproduced: `r1_witness.py rand_07 --order 2` gives an in-order witness, while the PLC ran 22 unload inversions. | **Fixed.** Exact order-feasibility DP `FtMask` in FB11 Pass A for order 1/2 (CONTRACT §4.10). FB10 falls back only when the preferred mode is provably infeasible, and then raises warning `AlarmWord2` bit 0 / `OrderFallback`. crane_stress gained check O1 (no needless fallback, including mid-run replans), and the judge sets were added to the stress run. | Fallbacks on 164 sets: 11 → 3, and all 3 are provably infeasible. Inversions: rand_07 26 → 0, rand_16 188 → 0, st_mixed_64 211 → 0, st_mixed_24 100 → 0, s777_rand_0223 12 → 0, s777_mixed_0478 72 → 0. Judge search `r1_search.py --n 800 --seed 777`: needless fallbacks **18 → 0**; the 7 remaining fallbacks are all order-1 infeasible; 0 false 'infeasible'. The price of keeping list order on those sets is J +0.3…+1.3 %, e.g. s777_rand_0223 1.0527 (free) → 1.0668 (in order). |
| R1-SCORE-1 | score | major | **Real.** Reproduced: rand_22 judge plan VALID, 1.0732 vs ours 1.0962. | **Fixed (most of it).** (2) Exact `FaMask` side feasibility for the fixed remaining sequence in every IMPROVE replay, so no more dead-end waste. (1) New SLOT phase: drop-cell relocate/swap with a separable cost (§4.11, FC21). (3) Block moves and perturbation were **not** done; a multi-start IMPROVE was tested and gave only −0.08 %, so it was rejected. | Order 1, gap to the judge plan: edge_initial_imbalance +2.36 → +0.41 %, rand_22 +2.14 → +0.26 %, rand_12 +1.27 → +0.17 %, rnd_16 +2.17 → +0.89 %, rand_06 +1.05 → +0.41 %, rand_26 +1.00 → +0.47 %, rand_01 +1.96 → +1.11 %, rand_03 +1.79 → +1.45 %, rand_23 +1.65 → +1.60 %, rand_05 +1.18 → +1.11 %, rnd_04 +2.02 → +1.56 %, rnd_17 +1.36 → +0.96 %. Mean over 155 feasible sets, order 1: 1.05821 → 1.05575 (−0.23 %), 105 better and 5 worse; the 5 worse include the 3 former fallbacks, now in list order. No set became infeasible. |
| R1-SCORE-2 | score | minor | **Real.** | Same fixes as R1-SCORE-1. | rand_27 free order 1.0839 → 1.0790 (judge 1.0704, gap +1.26 → +0.81 %). Mean free order over 155 sets: 1.04277 → 1.04221 (43 better, 3 worse, max +0.43 %). |
| R1-SCORE-3 | score | minor | **Real.** No plan equals the bound: rand_05 free 1.0030 vs LB 0.9967, rand_21 1.0701 vs 1.0671, rand_24 1.0080 vs 0.9989. | Claim removed from PITCH_CRANE.md, together with the "true gap ≤ 0.5 %" and "exact DP ≤ 0.07 %" claims. | — |
| R1-E2 | elimination | major | **Real** (it was already known as STATUS risk 5). | **Fixed.** FB10 region 2a mirrors every World cell change into DB10/DB11. External edits are still adopted. INIT keeps a private copy, InitBay0/1, so POČETNO STANJE can repeat the same data set (CONTRACT §3.5). | Before: after DONE, DB10/DB11 equal the initial yard. After: they show the final yard, at most 1 OB1 cycle behind. **Not yet run on PLCSIM.** |
| R1-E3 | elimination | minor | **Real** by code reading: the bit 0 put had no re-target, and the bit-7 path re-staged the same put. | **Fixed.** The ACK re-target now covers bits 0 and 2. With no balance-safe cell the system goes to bit 7 + PAUSED (MANUAL needed) and never re-stages the rejected put automatically. | Not testable without PLCSIM: the Python model does not emulate FB10. Repro steps are in the judge text and are added to STATUS Human TODO 1.7. |
| J1 | jury | critical | **Real.** | **Not fixable by an agent here.** HMI import needs the GUI steps in `hmi-tia/HUMAN_STEPS.md`. We made the generator side ready: J6 numbering fix, list-check panel, alarm 17, check clean (490 tags). | HMI still 0/10 until a human runs steps A–D. |
| J2 | jury | critical | **Real.** | **Not fixable here:** PLCSIM is not installed on this laptop. Claims were downgraded in the pitch ("mirror-verified", "not yet run on PLCSIM"). | — |
| J3 | jury | major | **Partly real.** The cost of the order-1 hedge is real. With v1.4 the default lost less: the 30-set mean over rand gives default 1.0644 vs free 1.0538. | The organizer question stays open (STATUS Human TODO 3.2). The pitch quotes spec §2 FB10 duty 1 and keeps the live switch `HMI_IF.CfgOrderMode`. We did not change the default without the organizers' answer, because elimination risk outweighs about 1 % J. | See the rival table below. |
| J4 | jury | major | Same as R1-E2. | Fixed (see R1-E2). | — |
| J5 | jury | minor | **Real.** | PITCH_CRANE.md was rewritten: only verified claims, comparison against the realistic rival, a demo script, and HMI/safety first. | — |
| J6 | jury | minor | **Real** (Score = 14 and Alarms = 14). | **Fixed.** HUMAN_STEPS: an empty `Alarms` screen, number **15**, is created in step A6, so the nav target exists before round 2. Step D only fills it. | — |
| J7 | jury | minor | **Real.** | **Fixed (PLC + generator).** New `HMI_IF.AlarmUId/AlarmUCnt/AlarmLId/AlarmLCnt` are set at INIT. The AlarmLog screen gets a "PROVJERA LISTA" panel. HUMAN_STEPS C7 (optional) shows how to insert a tag field into alarm texts 4/5. | — |
| J8 | jury | minor | Real, low priority. | Not done. New code is in named branches (FtActive / SlStart / SlActive / FinStart) with CONTRACT references. A block diagram is still a TODO for the deck. | — |

### Verification after the fixes
- **Compile:** TiaRun `TIA_RESULT errors=0 warnings=0` (`tia-work/r1_compile1.log`); re-archive log `tia-work/r1_compile2.log`.
- **Parity:**
  - `tia-src/12_planner_mirror.py`: **774/774** (greedy with FtMask)
  - `tia-src/13_improve_mirror.py 400 3`: **570/570** (IMPROVE with FaMask + SLOT + bound, 3 evaluations per call)
- **Stress:** `python tools/crane_stress.py --random 300 --seed 11 --evals 600` → **`STRESS_RESULT failures=0`**: 464 sets (now including all judge sets), 5232 plans plus 1650 mid-run replans, with the new O1 check (no needless order fallback). 26 sets are infeasible in every mode, and all 26 are provably unbalanceable (0 suspects).
- **Golden:** `tools/crane_golden.json` and every `tools/crane_data/*.plan.csv` were regenerated (`python tools/crane_gen.py --plans-only`). rand_04/07/16/18 now run in order 1.

### Current J table (v1.4, CfgMMode 2, IMPROVE 3000, SLOT 10)
Source: `python tools/crane_eval.py` (`tools/bench/eval_v14.txt`), `tools/crane_bench.py`, `tools/judge_sets/r1_jury_rival.py`.

| Set group | Config | v1.3 mean / max | **v1.4 mean / max** | Lower bound |
|---|---|---|---|---|
| 30 random | order 1 + fallback (PLC default) | 1.0684 / 1.1683 (4 sets fell back to free order) | **1.0644 / 1.1683** (0 fallbacks) | 1.0293 |
| 30 random | free order (CfgOrderMode 0) | 1.0549 / 1.1339 | **1.0538 / 1.1339** | 1.0293 |
| 40 feasible crane_data | order 1 default | 1.0455 | **1.0414** | 1.0016 |
| 40 feasible crane_data | free order | 1.0319 | **1.0310** | 1.0016 |
| 155 feasible, all benchmark sets | order 1 default | 1.05821 | **1.05575** | — |
| 155 feasible, all benchmark sets | free order | 1.04277 | **1.04221** | — |
| 34 sets (30 random + 4 Figure-1), jury rival = 1.0739 | order 1 default | 1.0658 (rival better on 11/34) | **1.0619 (rival better on 5/34)** | — |
| 34 sets, jury rival = 1.0739 | free order | 1.0521 | **1.0511** | — |

**Judge optimiser re-run, order 1:** `python tools/judge_sets/r1_score_batch.py --order 1 --iters 4000 "tools/crane_data/rand_*.json" "tools/judge_sets/r1_score_rnd_*.json"` → `tools/bench/judge_batch_o1_v14.txt`.
- Over 54 sets the mean gap to the judge plan is **+0.14 %** and the max is **+1.60 %**.
- 6 of 54 sets are more than 1 % above the judge (rand_01/03/05/23, rnd_04/17).
- On 9 sets v1.4 is **better** than the judge's "exhaustive" plan, by up to −2.7 % (rnd_15). The judge searches with its own slot rule, so its "exhaustive" result is not a true optimum.

### What remains open after round 1
- **HMI (J1) and PLCSIM (J2).** Both need human GUI steps; this laptop has no PLCSIM. The new FB10 paths (DB10/DB11 mirror and restore, ACK → PAUSED, order-fallback warning) are verified only by compiling and by reading the code.
- **Order-1 interleaving gap.** On some sets our order-1 plan is still 1–1.6 % above the judge's exhaustive or annealed plan (rand_03, rand_23, rand_05, rnd_04). That gap is in the interleaving of the two lists. Fix (3) from R1-SCORE-1 (block moves or a merge DP) was not implemented. Multi-start IMPROVE was measured at −0.08 % and rejected.
- **Organizer questions.** Still open: list order (J3), the M rule, and which view they grade (DB10/DB11 vs HMI).
- **Readability (J8).** FB11 is now about 1,900 lines. Splitting it into FCs is a TODO.

