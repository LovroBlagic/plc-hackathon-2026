# TIA crane (TASK 2): integration status

## v1.7 spec M rule (diagonal = 2) (7 Nov, builder). Contract **v1.7**
- **Team decision (binding, replaces the open organizer question on the M rule):** M is counted by the spec text p. 10: +1 lift, +1 put, a move +1 if the global column G changes (a Bay0↔Bay1 change counts as an x change) and +1 if y changes, so a diagonal move = 2; a zero-distance move = 0 (never issued). `World.CfgMMode` start value **2 → 0**; mode 2 (FB1 counting) stays selectable.
- **FB1 is unchanged** (given, know-how protected): MD107 still counts +1 per command. MD107 and the spec count differ **by design** (spec ≥ MD107); both are shown on the HMI. OB30's `World.MSpec` counting was re-checked against CONTRACT §4.1 mode 0 (bay change via G, zero-distance = 0, cleared by cmd 10, i.e. by POČETNO STANJE and MANUAL reset).
- **FB10:** HMI_IF.M/J now = spec values; `BaseM` for a (re)plan = `World.MSpec` in mode 0 (MD107 otherwise), so PredM/PredJ/LbJ on the Score screen are spec-rule values; alarm history M (`AlarmHistM`) = MSpec.
- **CfgAlpha** retuned for mode 0: **[0, 75, 125, 200]** (was [0, 100, 200, 300] for mode 2). Greedy multi-start over 400 sets: 1.18701 → 1.18570; after IMPROVE + SLOT the effect is small (see table). CfgImproveEvals 3000 / CfgSlotSweeps 10 / IMPROVE move set unchanged: re-entering IMPROVE after SLOT gains +0.02 % (1 of 30 sets), SLOT never hits its 10-sweep cap.
- **FB11 / FC10 / FC20 / FC21 / OB30 logic unchanged**, so Python ⇄ SCL parity is untouched; mirrors re-run with the new defaults (mirror 13 now covers mode 0 fully: bal 0/1, dist 0/6).
- **Build:** `TIA_RESULT errors=0 warnings=0` (`tia-work/v17_compile1.log`); `deliver/TIA_crane_v1_plc.zap21` re-archived (PLC only, `tia-work/v17_compile2.log`, 0/0).
- **Verification:** mirror 12 **886/886**, mirror 13 **620/620** (`tools/bench/v17_mirror1*.txt`), `FB10_INIT_RESULT failures=0`, stress: STRESS_PLACEHOLDER. Golden + plan CSVs regenerated for mode 0 (`tools/crane_golden.json` now also carries `M_FB1` and per-command `m_fb1` = expected MD107).
- **J (spec M rule, order 1 default), v1.6 planner run with mmode 0 → v1.7:**

| Set group | v1.6 (α 0,100,200,300) | **v1.7 (α 0,75,125,200)** | Lower bound | Judge best plan |
|---|---|---|---|---|
| 30 random | 1.16423 / max 1.3146 | **1.16390 / 1.3146** | 1.02926 (gap 13.1 %) | 1.15632 (we are +0.65 % mean, +1.55 % max; judge exact on 7 small sets, ours optimal on 3 of them) |
| 401 feasible bench sets | 1.16802 (4 fallbacks) | **1.16787** (4 fallbacks) | 1.01674 (gap 14.8 %) | — |

  The closed-form bound (§4.9) ignores y-travel, and under the spec rule every y change also costs 19 s of M, so the 13–15 % "gap" is mostly bound weakness; the judge optimiser (`r2_score_batch.py --mmode 0`) puts the real gap at about +0.65 %. Of that, about +0.36 % is drop-cell choice (exact per-bay assignment for our own sequence, `r2_score_slotgap.py 0`); the R2-SCORE-3 Hungarian assignment in SCL was **not** implemented (≈ 0.36 % for an O(n³) solve sliced over OB1 calls plus a new mirror, not worth the risk this late).
  Reference, same build under mode 2 (FB1 counting): 30 random, order 1 **1.06231** (v1.6: 1.0626), free order **1.05364** (v1.6: 1.0538), i.e. the new alphas do not hurt mode 2 (`tools/bench/v17_m2_rand.json`). Under the spec rule **free order (CfgOrderMode 0) is worth much more than under FB1 counting: 30 random 1.16390 → 1.10693 (−4.9 %, max 1.2385)**, vs −0.8 % in mode 2 (`tools/bench/v17_m0_rand_o0.json`); this raises the stakes of the open list-order question.
- **PLCSIM tool note (not changed, owned by the PLCSIM agent):** `tools/plcsim/crane_sim_test.py` takes the model M from `simulate()`, which now (mode 0 default) is the spec count, but compares it with MD107 → `M_match` will fail by design. Compare MD107 with the number of commands (golden `M_FB1`) and `HMI_IF.MSpec`/`HMI_IF.M` with the model M. Its `plc_J` (`HMI_IF.J`) is now the spec J.

### DB101 `HMI_IF` score members after v1.7 (for the HMI generator)
| Member | Type | Meaning |
|---|---|---|
| `M` | UDInt | **primary**: M by the spec rule (= `World.MSpec`, counted in OB30) |
| `T` | Real | `"time"` MD112, working time [s] (unchanged) |
| `J` | Real | **primary**: 0.5·T/(76·N) + 0.5·M/(4·N) with the spec M |
| `MFb1` | UDInt | **new**, secondary: FB1 counter `"number_of_manipulations"` MD107 (+1 per command) |
| `JFb1` | Real | **new**, secondary: J with MFb1 |
| `MSpec`, `JSpec` | UDInt, Real | kept for compatibility; now identical copies of `M` / `J` |
| `PredM`, `PredT`, `PredJ`, `PredJ0`, `LbJ`, `GapPct` | | planner values, now under the spec rule (CfgMMode 0) |

Layout (`hmi-tia/layout.json`, Score screen): row 1 "M (pravilo zadatka), stvarno" → `M`, `T`, `J`; row 2 "M (FB1 brojač, MD107)" → `MFb1`, `JFb1`; row 3 "Plan (predviđeno, pravilo zadatka)" → `PredM/PredT/PredJ`. The top bar M/J use `M`/`J`. `python hmi-tia/gen_hmi.py all` → `CHECK_RESULT problems=0 tags=492`.

---

## PLCSIM run (7 Nov, PLCSIM test engineer): the v1.6 build runs on S7-PLCSIM V21 and matches the model exactly
- 8 data sets in AUTO give PLC = model for MD107, MD112, MSpec, J, the final DB10/DB11 and the full command sequence (up to 74 transfers / 296 commands). HUMAN_STEPS 1.1, 1.3–1.15 pass through tag writes. CPU always in RUN, planner max call 10.4 ms. **No PLC bug found, tia-src unchanged.**
- Online Openness download to PLCSIM fails ("Connect to module failed"). It works through a virtual memory card plus an sim_hwdb.ini article-number edit. Details, steps and the table: `tia-src/PLCSIM_RESULTS.md`; tools: `tools/plcsim/`.

---

## v1.6 judge round 3 fixes (7 Nov, builder). Contract **v1.6**. Details and numbers: `tia-src/JUDGING.md` "Round 3"
- **Build:** `TIA_RESULT errors=0 warnings=0` (`tia-work/r3_compile1.log`); `deliver/TIA_crane_v1_plc.zap21` re-archived (PLC only, `tia-work/r3_compile2.log`). TIA closed afterwards.
- **FB10 data load (R3-E1, R3-J1):** an online DB10/DB11 edit is new data only while no job is in progress (before the first command after POČETNO STANJE, or in DONE); edits during a job are obstacles (EditMark / ObstCnt) and POČETNO STANJE restores the loaded data set (also with a container on the hook). New yard during a job only with new lists or ≥ 8 rewritten cells; new lists alone keep the loaded yard. A cell written back to its old value is no edit.
- **FB10 ACK re-target (R3-E2):** a rejected ship put goes to the nearest balance-safe cell that keeps the remaining lists feasible in the preferred order (bit-parallel FtMask[0,0] in FB10); v1.4 rule only if no such cell exists.
- **World.CfgRelaxMin (R3-E3, default FALSE):** TRUE = relaxed ceilings ascending from CfgBalLimit+1 (smallest feasible). Costs +5…9 % J on the affected sets, barely shortens the time above 5, so off by default; organizer question.
- **FB11 / FC10 / OB30:** logic unchanged (FB11 header no longer claims "bit-identical", R3-J3). Planner default unchanged, so golden and plan CSVs are unchanged.
- **Tools:** `tools/fb10_init_model.py` (v1.6 transliteration of region 2a + INIT step 3 + REGION 5 re-target, `ft00` checked against `feas_table`), `crane_stress.py` checks E2 (extended) and **T1** (re-target never breaks the list order needlessly), `json_to_db.py` writes ALL 192 watch values (demo_db regenerated).
- **Human TODO changes:** 1.7 / 1.10 obstacle tests may now be followed by 1.9 (POČETNO STANJE restores the data set); new 1.15: during AUTO write 999 into the next ship drop cell, ACK → the put goes to a cell on the side that keeps OrderModeAct = 1 (no alarm 17); 1.12 must write a new yard **and** new lists (or ≥ 8 cells).

---

## v1.5 judge round 2 fixes (7 Nov, builder). Contract **v1.5**. Details and numbers: `tia-src/JUDGING.md` "Round 2"
- **Build:** `TIA_RESULT errors=0 warnings=0` (`tia-work/r2_compile1.log`); `deliver/TIA_crane_v1_plc.zap21` re-archived (PLC only, `tia-work/r2_compile2.log`).
- **FB10:** list duplicate check counts only accepted entries (R2-E1); external DB10/DB11 edits are new data in every state, changed DB20/DB21 too, an idle edit invalidates the plan (R2-E2/J3); bit 7 from the ACK re-target is non-blocking (R2-E3); POČETNO STANJE ignored in RUNNING/PLANNING (R2-J4); relaxed-balance fallback step and `BalD0`, HMI alarm ID 18 (R2-J1).
- **FB11:** order-1 IMPROVE move 1 = kind-pattern relocate (R2-SCORE-1); relaxed balance rule `World.BalCeil` in FtMask/FaMask/greedy/replay/SLOT with balanced end (R2-J1). **FC10 CheckCmd** reads `World.BalCeil`.
- **Parity:** mirror 12 **822/822**, mirror 13 **620/620** (`tools/mirror13_par.py`). `tools/fb10_init_model.py` 0 failures.
- **J (order 1, 334 feasible sets):** 1.05885 → **1.05765**; gap to the judge's best plans mean +1.29 % → **+0.35 %**, max +0.73 %.
- **New tools:** `tools/json_to_db.py` (dataset JSON → DB10/11/20/21 sources + watch values, TEST COPY only), demo sets `tools/demo_db/`, `tools/fb10_init_model.py`, `tools/mirror13_par.py`.
- **HMI generator:** date/time footer item (prototype `P_DateTime`, optional), alarm 18. `CHECK_RESULT problems=0 tags=490`.
- **Human TODO additions:** 1.12 (PLCSIM) PAUSE → write a new data set into DB10/11/20/21 → POČETNO STANJE → DB10 must equal the new set; 1.13 load `tools/judge_sets/r2_jury_imb_a.json` → OrderModeAct = 1, alarm ID 18, |L−R| never above 10, ends ≤ 5; 1.14 POČETNO STANJE during RADI does nothing.

---

## v1.4 judge round 1 fixes (7 Nov ~06:00, builder). Contract **v1.4**. Details and numbers: `tia-src/JUDGING.md`
- **Build:** `TIA_RESULT errors=0 warnings=0` (`tia-work/r1_compile1.log`, `r1_compile2.log`). New FC21 `"Crane_DropCost"` (`10b_FC_DropCost.scl`, numbers.txt). `deliver/TIA_crane_v1_plc.zap21` re-archived (PLC only).
- **FB11:** exact order feasibility table `FtMask` (order 1/2, built one row per call before the variants) replaces the reachability test in Pass A; exact `FaMask` side feasibility in every IMPROVE replay; new **SLOT phase** (drop-cell relocate/swap after IMPROVE, one step k per call, `World.CfgSlotSweeps` = 10). Publishes `World.OrderFeasible`, `World.SlotAccepts`.
- **FB10:**
  - region 2a mirrors World into **DB10/DB11** (live state); INIT restores the loaded data from InitBay0/1 for a repeat run (unless DB10/DB11 were edited online while idle or reloaded).
  - ACK after a rejected plan put (bit 0 or 2, load on hook): re-target; if no cell → PAUSED + bit 7 (no ALARM/ACK loop).
  - `HMI_IF.OrderFallback` / `AlarmWord2` bit 0 warning when the preferred order is provably infeasible; `AlarmUId/UCnt/LId/LCnt` for bits 3/4.
- **Parity:** greedy mirror `12_planner_mirror.py` **774/774**; IMPROVE + SLOT + bound mirror `13_improve_mirror.py` **570/570** (budget 400, 3 evaluations per call).
- **Order 1 (PLC default) no longer leaves list order when an in-order plan exists:** fallbacks over all 164 benchmark sets 11 → 3, all 3 provably infeasible (exact DP).
- **HMI generator:** AlarmLog screen gets a "PROVJERA LISTA" panel (missing IDs, order fallback); alarm 17 on `AlarmWord2`; HUMAN_STEPS: `Alarms` = screen 15, created in step A. `CHECK_RESULT problems=0 tags=490`.

---

## v1.3 optimisation pass (7 Nov ~04:00, optimisation engineer). Contract **v1.3**
- **Build:** `TIA_RESULT errors=0 warnings=0` (`tia-work/opt_compile1.log`, `opt_compile2.log`). `deliver/TIA_crane_v1_plc.zap21` re-archived with v1.3 (same file name, PLC only).
- **New in FB11:**
  - IMPROVE phase: deterministic local search after the greedy, never worse than it (CONTRACT §4.8).
  - Closed-form lower bound (§4.9).
  - CfgAlpha start values are now [0,100,200,300].
- **New in World:** `CfgImproveEvals` (3000), `CfgImproveDist` (0), `CfgImprovePerCall` (1), `PredJ0`, `LbT_ds`, `LbM`, `LbJ`, `ImpEvals`, `ImpAccepts`.
- **New in HMI_IF:** `PredJ0`, `LbJ`, `GapPct`, `ImpGainPct`, `ImpEvals`, `PlanProgress` (FB10 fills them). HMI screen **Score** (14) plus a nav button. Generator check is clean: `CHECK_RESULT problems=0 tags=483`.
- **Parity:**
  - IMPROVE + bound line-by-line mirror `tia-src/13_improve_mirror.py`: **570/570** runs, with work split 2–3 evaluations per call.
  - Greedy mirror `12_planner_mirror.py`: still **774/774**.
  - Golden (`tools/crane_golden.json`) and every `*.plan.csv` regenerated with the v1.3 default (order 1 + fallback, α {0,100,200,300}, 3000 evaluations). The golden now also carries `J_greedy`, `imp_evals`, `imp_accepts` and `LbT_ds`/`LbM`/`LbJ`.

Model J over 30 random sets, mmode 2 (mean / max):

| Config | greedy v1.2 | greedy v1.3 | **v1.3 + IMPROVE** | lower bound | gap |
|---|---|---|---|---|---|
| order 1 + fallback (PLC default) | 1.0751 / 1.1683 | 1.0708 / 1.1683 | **1.0684 / 1.1683** | 1.0293 | 3.8 % |
| free order (CfgOrderMode 0) | 1.0651 / 1.1508 | 1.0634 / 1.1437 | **1.0549 / 1.1339** | 1.0293 | 2.5 % |

- In mmode 0 (spec M rule), free order goes 1.1301 → 1.1072 and order 1 goes 1.1837 → 1.1750.
- Over all 40 feasible sets: default 1.0508 → 1.0455; free order 1.0403 → 1.0319.
- Order 1 stops early: about 300 evaluations on average, so planning takes about 300–600 OB1 cycles. Free order uses about 2500.
- **Planning time on HW is unmeasured.** Read `"Crane_Control_DB".Planner.DiagMaxCallMs` / `DiagJobMs` on PLCSIM. If a call takes > 20 ms, keep CfgImprovePerCall = 1. If INIT feels too slow, lower `World.CfgImproveEvals` (1000 gives about 75 % of the free-order gain: 1.0569 vs 1.0549).
- **Robustness:** `python tools/crane_stress.py`, result: **`STRESS_RESULT failures=0`** (`--random 300 --seed 11 --evals 600`).
  - 407 sets; 4548 plans checked command by command (order 1/0/2 × bal 0/1 × mmode 2/0), plus 1435 mid-run replans.
  - Checks: step rule after every lift/put, list membership and order, determinism, improve ≤ greedy, bound ≤ plan.
  - 26 sets are infeasible in every mode, and all 26 are provably unbalanceable; 0 false "plan infeasible" alarms.
- **OB80 not added.** Per-call work is bounded (≤ 1 greedy step or 1 replay, ≤ 4.6k inner iterations). If the jury asks, add an OB80 "Time error interrupt" in the GUI (an empty body is enough).
- **Recommendation to the orchestrator:** spec §2 lists "Odlučivanje o redoslijedu kontejnera za manipulaciju" (deciding the container order) as an FB10 duty, which suggests free order is intended. If the organizers confirm, set `HMI_IF.CfgOrderMode := 0` for −1.3 % J.

---

Orchestrator final pass, 7 Nov 2026 (review fixes). Contract: `CONTRACT.md` **v1.2**. Previous integration was at 7 Nov ~02:05 (v1.1).

## Build result
```
TIA_RESULT errors=0 warnings=0
```
- **Project:** `tia-work/crane/PLC_hackathon_2026_V21/PLC_hackathon_2026_V21.ap21`, retrieved from the given .zap21.
- **Import:** all 10 tia-src sources imported OK, compile 0/0. Logs: `tia-work/final_compile1.log` (import + compile) and `tia-work/final_archive.log` (recompile + archive).
- **Block numbers** as the contract specifies: World DB100, HMI_IF DB101, Crane_Control FB10 + DB110, Crane_Planner FB11, CheckCmd FC10, Crane_MoveCost FC20.
- **OB1 "Main":** ProgramCycle. It calls only `"Crane_Control_DB"();`, i.e. FB10.
- **OB30 "Cyclic interrupt":** the SCL replacement of the given LAD OB30, with identical FB1 wiring. CyclicTime is 1000 ms, phase 0, priority 10, verified by TiaRun `--ob30-ms 1000`.
- **Not touched:** FB1/DB2, DB1, DB10/11/20/21, OB100 and the given tags.
- **Archive:** `deliver/TIA_crane_v1_plc.zap21`, re-archived after this pass. It contains the PLC only; the HMI is still the given empty device.

Rebuild, holding the lock:
```
.claude/skills/tia-portal/scripts/TiaRun.exe --project "<repo>\tia-work\crane\PLC_hackathon_2026_V21" --headless --lock <name> --src "<repo>\tia-src" --numbers "<repo>\tia-src\numbers.txt" --ob30-ms 1000 [--archive "<repo>\deliver\TIA_crane_v1_plc.zap21"]
```

## Model J estimate (`python tools/crane_eval.py`, mmode 2 = real FB1)
These are J values over the 30 random sets (mean / max):

| Config | J mean / max |
|---|---|
| **PLC default: order 1 (per-list order) + fallback** | **1.0751 / 1.1683** |
| free order (CfgOrderMode 0) | 1.0651 / 1.1508 |
| lower bound | 0.7566 |

- On 4 of the 30 sets (rand_04/07/16/18), order 1 dead-ends under the balance rule. The fallback then plans with order 0.
- Over all 40 feasible sets, the default gives 1.0508 and free order gives 1.0403.
- The hedge costs about +0.010 J (≈ 0.9 %).

## Review fixes in this pass
| # | Finding | Result |
|---|---|---|
| 3 (major) | Default free order risked elimination criterion 1 ("u skladu sa zadanom listom") | **Fixed.** CfgOrderMode := 1 in HMI_IF and World. FB10 keeps the HMI choice as the preferred mode (statics CfgOrdHmi/CfgBalHmi). On FB11 ErrCode 1 it retries with order 2→1→0, then bal 1→0. `HMI_IF.OrderModeAct` shows the mode used. Tools: `crane_plan.plan_fb`, CLI `--order 1` (`--nofallback` = raw FB11). Plans and golden regenerated (golden has `order_used`); datasets unchanged. |
| 4 (major) | Pick/drop pre-check only against the private World copy; endless ALARM/ACK on drop occupied | **Fixed.** (1) Region 2a: after INIT, any cell of DB10/DB11 changed online is adopted into World, so editing DB10/DB11 in a watch table during AUTO triggers the OB30 alarm and shows on the grid. (2) ACK of bit 2 on a plan put with a load re-targets Plan[PlanIdx] to the nearest free, balance-safe cell of the same bay (Phase := 2), and the plan is redone after that put. If there is no cell, bit 7 is raised. (3) Before every replan, pending entries whose ID left its source bay become done or skipped (bit 3/4), so "pick empty" → ACK → replan no longer loops on ErrCode 3. |
| 10 (major) | Duplicate IDs flip list states, causing extra transfers or a false DONE | **Fixed.** A plan put (Src 1/2, Phase 3, cell = Plan[TrIdx].Id) marks exactly its ListIdx done. A MANUAL put uses the presence check, done only if the ID is in the destination and not the source (and the reverse for re-pending). An ID present in both bays never changes state. |
| 5 (minor) | OB30 did not literally check `"new_command_ID" = 0` | **Fixed.** Added to the issue condition, with a spec 2.2 comment. |
| 6 (minor) | Alarm classes vs PLC blocking; double ACK | **Fixed in the generator.** Bits 9 and 14 are now "Errors" (bits 0 and 9 are documented as mixed). Errors get the HMI ack tag `AlarmHmiAck` (FB10 treats it as POTVRDA) and the PLC ack tag `AlarmAckWord` (= NOT AlarmWord), so one ACK clears both. `hmi-tia/out/alarms` was regenerated; tag count is 477 (< 512). |
| 7 (minor) | SEMI step ignored before START or while busy | **Fixed.** The click is latched (PendStep). In READY/PAUSED it acts as START + 1 step. It is cleared by STOP, OFF, mode change, alarm and DONE. |
| 8 (minor) | MANUAL reset with a load lost the container | **Fixed.** CheckCmd returns 11 for cmd 10 with Src = 3 and Carried ≠ 0. The INIT reset (Src 4) is still always allowed. |
| 9 (minor) | Spec M (diagonal = 2) not shown | **PLC done:** OB30 counts `World.MSpec`, and FB10 writes `HMI_IF.MSpec/JSpec`. **HMI placement not done:** the header row is full; a human places 2 I/O fields. |
| 11 (minor) | ACK in the same cycle as a new fault | **Fixed.** ACK is ignored when newFault ≠ 0; Fault clears only the bits seen at ACK. |
| 12 (minor) | Config change applied with a load on the hook | **Fixed.** The region 4 guard adds `Carried = 0 AND NOT Busy`. |
| 13 (minor) | Bit 0 spams history on every ACK | **Fixed.** ACK keeps bit 0 latched while the imbalance persists. |
| 1 (critical) | No HMI in the project | **Not fixable by an agent.** It needs the GUI steps in `hmi-tia/HUMAN_STEPS.md` (connection, seed objects, prototypes). The generator is ready, with alarms regenerated. |
| 2 (critical) | Nothing run on PLC | **Not fixable here.** PLCSIM is not installed on this laptop (no S7-PLCSIM in `_InstalledSW`). See the TODO list. |

Known limitation of the re-target: OB1 stages one command ahead of FB1. After the re-targeted put, the next transfer's first move from the old plan may still be issued before the replan starts. That costs one extra move but is never a wrong lift. A zero-skip lift cannot happen there, because no transfer starts at a cell that has just been filled.

## What is implemented
| Part | File | State |
|---|---|---|
| UDTs, World DB100, HMI_IF DB101 | 01/02/03 | done. CfgMMode = 2, CfgOrderMode = 1, Mode = AUTO by default |
| FC20 Crane_MoveCost | 10 | done. 774/774 parity runs vs the Python oracle |
| FB11 Crane_Planner | 11 | done, unchanged in this pass. 4-variant greedy, balance step rule, reachability, ≤ 322 OB1 calls per job |
| FC10 CheckCmd | 20 | done. Pick not empty, drop not occupied, slot range, carried/empty hook, balance, MANUAL reset with a load |
| FB10 Crane_Control | 21/22 | done. Modes, ON/OFF, INIT, START/STOP/ACK, alarms + 16-entry history, order fallback, DB10/11 edit adoption, drop re-target, SEMI latch |
| OB1 / OB30 | 30/31 | done. OB30 checks completion and MB103 = 0, then CheckCmd, then issues, then calls FB1 every 1 s. It also counts the spec M |
| Python reference | `tools/crane_*.py` | done. mmode 2, order 1 + fallback (`plan_fb`) |
| HMI generator | `hmi-tia/` | offline run OK (477 tags, 0 problems); **not imported** |

## Known gaps / risks
1. **Nothing has run on a PLC yet** (no PLCSIM). All of the following is verified only by compiling and by the Python mirror: the handshake, the done pointer, the new fallback/re-target paths and the SEMI latch.
2. **Planner per-call time** on a 1515 is unmeasured; read `"Crane_Control_DB".Planner.DiagMaxCallMs`. With the fallback, a dead-end set plans up to 2–3 times, which is still ≲ 1000 OB1 cycles.
3. **The HMI is not built in TIA.**
4. **N counts raw non-zero list entries**, including invalid, duplicate and missing IDs (contract §3.2). Ask the organizers.
5. ~~Our program never writes DB10/DB11~~ **Fixed in v1.4:** DB10/DB11 are mirrored from World every OB1 cycle (CONTRACT §3.5). Still ask the organizers which view they grade.

## Human TODO (in order)
1. **Install PLCSIM** (S7-PLCSIM V21 from the TIA ISO, or PLCSIM Advanced V8), or run on the other laptop. Load `deliver/TIA_crane_v1_plc.zap21`. Then test:
   1. INIT
   2. AUTO to DONE on rand_05, checking MD107/MD112 against `tools/crane_golden.json` (default config: order 1)
   3. SEMI clicks, including a click before START
   4. STOP/START after a lift
   5. OFF/ON
   6. MANUAL lift on an empty cell and put on an occupied cell, then ACK
   7. During AUTO, write an obstacle ID into DB10/DB11 at the next drop cell: expect the bit 2 alarm, then ACK, then the put goes to the nearest free cell and the run continues
   8. Read `DiagMaxCallMs`
   9. v1.4: after DONE, check that DB10/DB11 show the final yard; press POČETNO STANJE and check that the original data is restored (a repeat run gives the same MD107/MD112).
   10. v1.4 (judge R1-E3): during AUTO, with a load lifted for a Bay 0 put, write IDs into empty LEFT cells of DB10 until L−R = 5. Expect alarm 0 → ACK → re-target to a balance-safe cell, or bit 7 + PAUSED. There must be no endless ALARM/ACK loop.
   11. v1.4: load `tools/judge_sets/r1_elimination_needless_fallback_s777_rand_0223.json` and check that `HMI_IF.OrderModeAct = 1` and `OrderFallback = 0`.
   12. v1.5 (R2-E2): START, STOP (PAUZA), write a new data set into DB10/DB11/DB20/DB21 (`tools/json_to_db.py` → watch values), press POČETNO STANJE: World and DB10/DB11 must be the NEW set.
   13. v1.5 (R2-J1): load `tools/judge_sets/r2_jury_imb_a.json`: OrderModeAct = 1, alarm ID 18, |L−R| never above 10 and ≤ 5 at the end.
   14. v1.5 (R2-J4): POČETNO STANJE during RADI does nothing; after STOP it works.
   15. v1.6 (R3-E2): on a list-order plan, during AUTO write 999 into the next SHIP drop cell (alarm 3), POTVRDA: the put goes to a free cell whose side keeps the list order (OrderModeAct stays 1, no alarm 17). Then remove the 999, finish, POČETNO STANJE: the original data set comes back (R3-E1).
2. **HMI** (`hmi-tia/HUMAN_STEPS.md`, about 25 min): connection, seed objects, round 1, Proto, round 2, alarm import, Alarms screen, start screen. Optionally add I/O fields for `MSpec`, `JSpec` and `OrderModeAct`. Then compile the HMI and **re-archive with PLC_1 + HMI_RT_1**.
3. **Organizer questions (ask now):**
   1. Is M scored by MD107 (1 per move) or by the spec rule (diagonal = 2)? For the spec rule, set `World.CfgMMode := 0`.
   2. Must the lists be followed in list order? We default to per-list order (1) with a fallback to free. For free order, set HMI_IF.CfgOrderMode = 0 (HMI). For strict order, choose 2.
   3. Balance: left/right = x{0,1} vs x{2,3} only? Must it hold after every manipulation?
   4. Does N count invalid, duplicate or missing list entries?
   5. Should DB10/DB11 be updated live?
