# TIA crane (TASK 2): integration status

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
5. Our program never writes DB10/DB11, so they keep the initial state. The live state is World/HMI grid. If the jury expects DB10/DB11 to be updated as "current state", that needs a decision. Writing runtime values is allowed; changing the given block structure is not.

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
2. **HMI** (`hmi-tia/HUMAN_STEPS.md`, about 25 min): connection, seed objects, round 1, Proto, round 2, alarm import, Alarms screen, start screen. Optionally add I/O fields for `MSpec`, `JSpec` and `OrderModeAct`. Then compile the HMI and **re-archive with PLC_1 + HMI_RT_1**.
3. **Organizer questions (ask now):**
   1. Is M scored by MD107 (1 per move) or by the spec rule (diagonal = 2)? For the spec rule, set `World.CfgMMode := 0`.
   2. Must the lists be followed in list order? We default to per-list order (1) with a fallback to free. For free order, set HMI_IF.CfgOrderMode = 0 (HMI). For strict order, choose 2.
   3. Balance: left/right = x{0,1} vs x{2,3} only? Must it hold after every manipulation?
   4. Does N count invalid, duplicate or missing list entries?
   5. Should DB10/DB11 be updated live?
