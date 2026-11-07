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


## Round 2 (7 Nov 2026, builder response). Contract **v1.5**

Benchmark files (all CfgMMode 2, IMPROVE 3000, SLOT 10):
- `tools/bench/v14r2_base_m2.json`: v1.4 planner, order 1, on all 347 sets now in crane_data, crane_data_stress and judge_sets (incl. the round-2 judge sets).
- `tools/bench/v15_m2.json`: v1.5, orders 1 and 0.
- Compare: `python tools/crane_bench.py --compare tools/bench/v14r2_base_m2.json tools/bench/v15_m2.json`.

| ID | Judge | Severity | Verdict | Action | Before → after |
|---|---|---|---|---|---|
| R2-SCORE-1 | score | major | **Real.** Reproduced: on the judge's 11 "best plan" sets our v1.4 default was +1.01…+1.79 % above the judge plan. | **Fixed (main part).** In order mode 1, IMPROVE move 1 is now the kind-pattern token relocate (CONTRACT §4.8): it contains the old move 1 and also shifts whole blocks. Same replay, same budget, Python + SCL + mirror 13. Tested both judge variants: an extra move 4 (judge `r2_score_patmove.py`) gives the same mean (1.06615 vs ours 1.06620 on 320 common sets) but needs a 4th move type, so the simpler replacement was kept. **Not done:** slot-aware acceptance (a SLOT run inside every IMPROVE candidate). It needs SLOT as a sub-routine inside the replay loop in FB11 (≈ 10–15× the evaluation cost). | Gap to the judge's best plans (11 sets): mean **+1.29 % → +0.35 %**, max **+1.79 % → +0.73 %** (rand_03), 0 sets above 1 %. hunt_11_062 1.0625 → 1.0502 (judge 1.0439), rand_23 1.0381 → 1.0265, rand_01 1.1123 → 1.1001, edge_initial_imbalance 1.0108 → 1.0034. All 334 feasible sets, order 1: mean 1.05885 → **1.05765** (−0.11 %), 103 better, 30 worse (max +0.55 % rnd_22; the 3 worst are the unbalanced-start sets that now keep list order, see R2-J1), 0 newly infeasible. Round-1 set (155): 1.05575 → 1.05460. |
| R2-SCORE-2 | score | minor | **Real.** The round-1 gap numbers came from a weaker judge. | PITCH_CRANE.md §2 rewritten with the round-2 numbers and the correct cause (greedy-cell acceptance + missing block move, not set size). The "ours better than the judge on 9 sets" claim was removed. Small sets: the judge's exact enumeration found ours optimal on 50 of 58 sets with N ≤ 13, worst +0.53 %. | — |
| R2-SCORE-3 | score | minor | **Real, but only under the spec M rule** (CfgMMode 0), which is still an open organizer question. | **Not done.** An exact per-bay assignment in SLOT for mode 0 is a Hungarian solve in SCL. Recorded as an open item; it is relevant only if the organizers answer "diagonal = 2". | — |
| R2-E1 | elimination | major | **Real.** Reproduced: `r2_elim_dup.py` → `lost_valid_load_entries=2`. | **Fixed.** FB10 INIT and `crane_model.init_validate`: a duplicate is an ID seen in an earlier **accepted** entry. New stress check L0 (independent list check, not via init_validate) and `tools/fb10_init_model.py` check E1. | `R2_DUP_RESULT lost_valid_load_entries=2 → 0`. Bogus unload 555 still raises alarm ID 4; load 555 is planned. |
| R2-E2 | elimination | major | **Real** (code path confirmed). | **Fixed.** Region 2a sets ExtEdit on an external DB10/DB11 edit in every state, and PlanValid := FALSE outside RUNNING/PLANNING with an empty hook (START replans). INIT step 3 also takes changed DB20/DB21 as a new data set. New Python transliteration `tools/fb10_init_model.py` (states 0/2/3/4/5/6 × new yard+lists / yard only / nothing changed) is run by crane_stress as check E2. | Judge transliteration: wrong data after POČETNO STANJE in states 4/5. v1.5 model: `FB10_INIT_RESULT failures=0` (18 scenarios: new data always loaded, the same data set restored when nothing changed). **Not run on PLCSIM** (STATUS Human TODO 1.12). |
| R2-E3 | elimination | minor | **Real** (code reading: bit 7 was in the blocking mask, so ACK → PAUSED → ALARM again in the same cycle). | **Fixed.** Bit 7 raised by the ACK re-target sets FB10 static `NoCellWarn` and is then excluded from the blocking mask; it is still shown. One ACK → PAUSED with MANUAL enabled; the next ACK or INIT clears it. | Not testable without PLCSIM (Human TODO 1.10). |
| R2-J1 | jury | major | **Real.** Reproduced: `r2_jury_imb_order.py --random 60 --seed 9` lists sets that fell back to free order although an in-order plan exists. | **Fixed.** Relaxed balance rule as a fallback **before** the order is given up (CONTRACT §4.3): with the ship loaded at d0 > 5, while |L−R| > 5 a step may go up to d0; once ≤ 5 it stays ≤ 5 (memoryless, so FtMask/FaMask stay one DWord per cell); the plan must end balanced. Used only when FtMask proves the order feasible under it. New World `BalCeil`, FB10 `BalD0`, CheckCmd reads `World.BalCeil`, HMI alarm ID 18 (AlarmWord2 bit 1). Python + FB11 + FB10 + FC10 + both mirrors. New stress check J1 (no needless fallback under the relaxed rule; relaxed never used when the step rule works). | Witnesses: r2_jury_imb_a free order → **order 1** (max |L−R| 10 = d0, end 4), imb_c free → **order 1** (end 0), imbrand_008 free → **order 1** (max 12 = d0, end 5). Fallbacks to free order over 347 sets: 6 → **3**. Price: J +0.36…+1.47 % on those 3 sets (keeping list order costs time). |
| R2-J2 | jury | major | **Real.** Given data = 0 transfers; no dataset loader. | **Fixed (tooling + docs).** New `tools/json_to_db.py` writes DB10/11/20/21 sources (same block names/members, NON_RETAIN) and a watch-table value list from any dataset JSON, for a TEST COPY only. Generated demo sets: `tools/demo_db/fig1_half` (6 U + 6 L in the style of Figure 1) and `tools/demo_db/listcheck_bogus_unload` (alarm ID 4 + R2-E1 demo). Demo script in PITCH_CRANE.md §0 and HUMAN_STEPS E4 rewritten: given data first ("alarms 4/5, nothing to move"), then the demo set. One alarm numbering everywhere: WinCC alarm ID = PLC bit + 1. | — |
| R2-J3 | jury | minor | Same as R2-E2. | Fixed with R2-E2. | — |
| R2-J4 | jury | minor | **Real.** | **Fixed.** (1) BtnInit is ignored in RUNNING/PLANNING (STOP first). (2) Generator item `datetime` in the template footer with the optional prototype `P_DateTime` (HUMAN_STEPS B); without it the generator only warns. Footer: OB30 counter moved left. | `CHECK_RESULT problems=0 tags=490`. |
| R2 (jury, carry-over J1/J2) | jury | critical | Still real. | HMI import and PLCSIM need the human GUI steps; unchanged. | HMI still 0/10 until HUMAN_STEPS A–D are done. |

### Verification after the round-2 fixes
- **Compile:** TiaRun `TIA_RESULT errors=0 warnings=0` (`tia-work/r2_compile1.log`); TIA closed afterwards.
- **Parity:**
  - `tia-src/12_planner_mirror.py`: **822/822** (greedy + FtMask, now including the relaxed rule on every unbalanced-start set, orders 1/2 × M rule 2/0 × bal mode 0/1).
  - `tia-src/13_improve_mirror.py` (run in parallel by `tools/mirror13_par.py 400 3`): **620/620** (IMPROVE with the pattern move, FaMask, SLOT, bound; now also on the r2_jury_imb sets).
- **FB10 data-load model:** `python tools/fb10_init_model.py` → `FB10_INIT_RESULT failures=0`.
- **Judge repros:** `r2_elim_dup.py` → 0 lost entries.
- **Stress:** `python tools/crane_stress.py --random 300 --seed 11 --evals 600` → **`STRESS_RESULT failures=0`** (`tools/bench/stress_v15.txt`): 647 sets (2 capacity-blocked), 7380 plans plus 2338 mid-run replans, with the new checks L0 (independent list check), E2 (FB10 data-load model) and J1 (no needless fallback under the relaxed rule, relaxed rule never used when the step rule works). 30 sets are infeasible in every mode, all provably unbalanceable (0 suspects).
- **Judge repros re-run:** `r2_elim_dup.py` → `lost_valid_load_entries=0`; `r2_jury_imb_order.py --random 300 --seed 9` → order-1 fallbacks to free order **42 → 2**. The judge's DP still finds an in-order plan for 1 of the 2 (imbrand_221), but only if the ship may become unbalanced again after it was balanced (non-sticky rule). Its own sticky DP says infeasible, and we deliberately do not allow re-unbalancing.
- **Golden:** `tools/crane_golden.json` and `tools/crane_data/*.plan.csv` regenerated (`python tools/crane_gen.py --plans-only`).
- **Deliverable:** `deliver/TIA_crane_v1_plc.zap21` re-archived (PLC only, `tia-work/r2_compile2.log`, 0/0).

### Current J table (v1.5, CfgMMode 2, IMPROVE 3000, SLOT 10)
Source: `python tools/crane_eval.py` (`tools/bench/eval_v15.txt`), `tools/crane_bench.py` (`tools/bench/v15_m2.json`).

| Set group | Config | v1.4 mean / max | **v1.5 mean / max** | Lower bound |
|---|---|---|---|---|
| 30 random | order 1 + fallback (PLC default) | 1.0644 / 1.1683 | **1.0626 / 1.1683** | 1.0293 |
| 30 random | free order | 1.0538 / 1.1339 | 1.0538 / 1.1339 (unchanged) | 1.0293 |
| 40 feasible crane_data | order 1 default | 1.0414 | **1.0399** | 1.0016 |
| 40 feasible crane_data | free order | 1.0310 | 1.0310 | 1.0016 |
| 155 feasible round-1 sets | order 1 default | 1.05575 | **1.05460** | — |
| 334 feasible sets (all, incl. round-2 judge sets) | order 1 default | 1.05885 (6 fallbacks) | **1.05765 (3 fallbacks)** | — |
| 334 feasible sets | free order | — | 1.04667 | — |
| 11 judge "best plan" sets | order 1, gap to the judge | +1.29 % mean, +1.79 % max | **+0.35 % mean, +0.73 % max** | — |

### What remains open after round 2
- **HMI (J1) and PLCSIM (J2):** human GUI steps; PLCSIM is not installed on this laptop. All new FB10 paths (data load in any state, R2-E3 PAUSED path, relaxed fallback, INIT guard) are verified only by compiling, by `tools/fb10_init_model.py` (data load) and by reading the code. STATUS Human TODO 1.12–1.14 cover them.
- **R2-SCORE-1, second half:** slot-aware acceptance in IMPROVE (judge prototype: residual gap +0.13 %) is not ported. It would run SLOT inside the replay loop of FB11.
- **R2-SCORE-3:** exact drop-cell assignment for the spec M rule (CfgMMode 0); only if the organizers score M by the spec text.
- **Planning time:** the pattern move makes more order-1 candidates valid, so IMPROVE uses its full 3000-evaluation budget more often (Python bench time per run about ×4). The scored T is FB1 time, so J is unaffected, but `DiagJobMs` on the real CPU is still unmeasured.
- **Organizer questions:** list order, M rule, grading view, and now also "may the ship pass through an imbalance up to the given one?" (relaxed rule R2-J1).


## Round 3 (7 Nov 2026, builder response). Contract **v1.6**

Changes are in FB10 (`21_FB_CraneControl.scl`) and World (`CfgRelaxMin`) only; FB11, FC10 and OB30 logic is unchanged, and so is the planner default, so the J tables below are the v1.5 numbers re-confirmed. Python reference for the new FB10 paths: `tools/fb10_init_model.py` (region 2a, INIT step 3, REGION 5 re-target, `ft00`).

| ID | Judge | Severity | Verdict | Action | Before → after |
|---|---|---|---|---|---|
| R3-E1 | elimination | major | **Real.** Reproduced with `r3_elim_obstacle_then_init.py`: rand_05 obstacle + cleanup → POČETNO STANJE loads the final yard (0 of 12 pending), with a load on the hook container 721 is lost; rand_16 the same (0 / 31 of 37, 143 lost). | **Fixed.** Region 2a marks each externally edited cell (EditMark, EditVal = value before the edit). Edited with no job in progress (nothing executed since INIT, or DONE) → NewCnt = new data; edited during a job → ObstCnt = obstacle. Writing a cell back to EditVal unmarks it. INIT takes DB10/DB11 as a new yard only if NewCnt > 0, or new lists AND ObstCnt > 0, or ObstCnt ≥ 8, or no copy yet / DB ≠ Snap; otherwise it restores InitBay (with the container that was on the hook). `fb10_init_model.selftest` gained the obstacle, obstacle-kept, lists-only, zero-transfer and load-on-hook scenarios (crane_stress E2). | `OBSTACLE_INIT_RESULT failures=2 → 0` on rand_05 and rand_16 (12/12 and 37/37 pending after reload, 0 containers lost). `FB10_INIT_RESULT failures=0` (49 scenarios, was 18). |
| R3-E2 | elimination | minor | **Real.** Reproduced with the same procedure on all 418 sets: the v1.4 rule breaks the list order needlessly in **38 of 4725** obstacle cases (judge: 16 of 1705 on 97 sets). | **Fixed.** REGION 5 builds the exact FtMask[0,0] of the remaining lists after the put (bit-parallel, two row buffers, per-total move masks; ≤ 2 × (49 × 25 × 4 + 49 × 49) cheap operations, once per ACK) and keeps only cells whose side keeps the preferred order feasible: try 1 step rule, try 2 relaxed ceiling BalD0, try 3 the v1.4 nearest cell. `ft00` equals `crane_plan.feas_table[0][0]` on 400 random instances. New crane_stress check **T1**. | Needless order breaks after a re-target: **38 → 0** (4725 cases; 210 cases where no free cell keeps the order are inherent). |
| R3-E3 | elimination | minor | **Real as described**, but a trade-off, not a bug. Measured on the 14 unbalanced-start sets: the smallest feasible ceiling costs J +6.85 % (imb_a), +8.81 % (imbrand_008), +5.06 % (imb_31_01), +0.92 % (imb_31_05), and the lifts/puts above 5 only drop 24 → 20, 20 → 20, 26 → 26, 33 → 32. The max stays d0 (the start). | **Config added, default unchanged.** `World.CfgRelaxMin` (FALSE): TRUE tries BalCeil = 6, 7, … BalD0 ascending in both FB10 fallback chains (Python `CRANE_RELAX_MIN=1`). Added to the organizer questions and the pitch Q&A. | Default J unchanged. With CfgRelaxMin: imb_a 1.0084 → 1.0774 (ceil 10 → 7). |
| R3-J1 | jury | major | **Real.** Both problems reproduced: watch_values.txt listed only non-zero values (36 lines; HUMAN_STEPS said 13 + 12); `r3_jury_lists_only.py` → after a full rand_05 run, new lists alone gave 21 cells different and 0 pending. | **Fixed.** (1) `json_to_db.py` writes all 96 cells + 96 entries (192 lines, zeros included); `tools/demo_db/fig1_half` and `listcheck_bogus_unload` regenerated; HUMAN_STEPS and the pitch now say "import and download", the watch route only with all 192 lines. (2) INIT: new lists alone keep the loaded yard (InitBay) and take the new lists (R3-E1 rule). | `r3_jury_lists_only.py`: lists-only change after 3 / all transfers: cells differing from the loaded yard **6 / 21 → 0 / 0**, pending U/L 6/3 and 0/0 → **7/5 and 7/5**, alarm bits [3,4] → none. |
| R3-J2 | jury | minor | **Real** (same cause as R3-E3). | **Not changed in the planner** (a K penalty per op above 5 would touch greedy, IMPROVE and SLOT in FB11 plus both mirrors). The measured trade-off (above) is in the pitch Q&A and the organizer questions; `CfgRelaxMin` is the available knob. | — |
| R3-J3 | jury | minor | **Real.** | **Fixed.** Pitch §1: default 1.0603, rival ahead on 3 of 34; Figure-1 demo Q&A (free order 0.981 vs 1.005, rival 0.990); §2 round-3 residual gap; §3 v1.6 stress numbers. FB11 header now says "mirrored line by line by 12/13_*_mirror.py" and states the budgets (13: 400 evaluations, 3 per call; stress: 600). | — |
| R3-SCORE-1 | score | minor | **Real** (residual ~+0.5 % on large / near-full sets; +1.06 % on nearfull_61_00), and the judge's analysis that more budget does not help is consistent with our round-2 tests. | **No PLC change**, as the judge recommends. Pitch §2 now quotes the fresh-set gap (≈ +0.5 % on large/near-full, 1 of 64 above 1 %). Note added: do not raise `CfgImproveEvals` without re-benchmarking (30 000 was worse on big_42_04). The joint kick-and-restart search stays a post-HMI idea. | — |

### Verification after the round-3 fixes
- **Compile:** TiaRun `TIA_RESULT errors=0 warnings=0` (`tia-work/r3_compile1.log`); archive run `tia-work/r3_compile2.log`; TIA closed afterwards.
- **Parity (FB11 unchanged, re-run on all current sets):** `tia-src/12_planner_mirror.py` **886/886** (`tools/bench/r3_mirror12.txt`); `tools/mirror13_par.py 400 3` **620/620** (`tools/bench/r3_mirror13.txt`).
- **FB10 model:** `python tools/fb10_init_model.py` → `FB10_INIT_RESULT failures=0`.
- **Judge repros:** `r3_elim_obstacle_then_init.py` (rand_05, rand_16) → `failures=0`; `r3_jury_lists_only.py` → 0 cells differ, all entries pending; T1 (= the judge's `r3_elim_retarget_order.py` procedure with the v1.6 rule, all 418 sets) → 0 needless.

## v1.7: spec M rule as default (7 Nov 2026, builder). Contract **v1.7**

Team decision: M is scored by the spec text (diagonal = 2), `World.CfgMMode` = 0, CfgAlpha [0, 75, 125, 200]. FB11 logic unchanged. Details: `tia-src/STATUS.md` "v1.7".

### Current J table (v1.7, CfgMMode 0 = spec M rule, order 1 default, IMPROVE 3000, SLOT 10)
Source: `python tools/crane_bench.py --mmode 0 --orders 1` (`tools/bench/v16_m0_before.json` = v1.6 planner run with mmode 0, `tools/bench/m0_a0_75_125_200.json` = v1.7), judge optimiser `python tools/judge_sets/r2_score_batch.py --mmode 0 --order 1 --iters 6000 "tools/crane_data/rand_*.json"`.

| Set group | v1.6 planner, mmode 0 | **v1.7** | Lower bound (§4.9) | Judge best plan |
|---|---|---|---|---|
| 30 random | 1.16423 / max 1.3146 | **1.16390 / 1.3146** | 1.02926 | 1.15632 (v1.7 gap +0.65 % mean, +1.55 % max, 9 of 30 above 1 %) |
| 401 feasible sets (crane_data, stress, all judge sets) | 1.16802 (4 fallbacks) | **1.16787** (4 fallbacks) | 1.01674 | — |

- The lower bound is loose under mode 0 (it ignores y-travel, and each y change now also costs 1 M): 13–15 % "gap" vs about +0.65 % to the judge's best plans.
- **R2-SCORE-3 re-measured:** exact per-bay drop-cell assignment for our own final sequence gains **+0.36 %** mean (max 1.17 %, 2 of 30 above 1 %; `r2_score_slotgap.py 0`). Re-entering IMPROVE after SLOT (`r3_score_iterate` idea, mode 0) gains +0.02 %. Alpha retune: −0.03 % on 30 random, −0.01 % on 401. **Not implemented:** the Hungarian solve in SCL (sliced over OB1 calls + mirror) for ≈ 0.36 % was judged not worth the risk before the deadline. It stays the main open score item under the spec rule, together with slot-aware IMPROVE acceptance.
- Mode-2 reference (FB1 counting) for the same build: 30 random, order 1 **1.06231** (v1.6: 1.0626), free order **1.05364** (v1.6: 1.0538), i.e. the new alphas do not hurt mode 2 (`tools/bench/v17_m2_rand.json`). Under the spec rule **free order (CfgOrderMode 0) is worth much more than under FB1 counting: 30 random 1.16390 → 1.10693 (−4.9 %, max 1.2385)**, vs −0.8 % in mode 2 (`tools/bench/v17_m0_rand_o0.json`); this raises the stakes of the open list-order question.
