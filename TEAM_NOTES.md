# Team notes

Write findings for the agents here (FB1 behaviour, organizer answers, HMI status). Newest on top.

## TIA crane v1.5: judge round 2 fixes (builder, 7 Nov 2026)
- **Elimination fixes (FB10):** a bogus unload entry no longer kills the valid load entry with the same ID; DB10/DB11 (and DB20/DB21) changed in ANY state are new data at POČETNO STANJE; ACK with no re-target cell → PAUSED with MANUAL usable after one ACK; POČETNO STANJE ignored while RADI/PLANIRANJE.
- **Unbalanced start (R2-J1):** if the list order is infeasible under the step rule and the ship was loaded with |L−R| = d0 > 5, the plan keeps the list order with a relaxed rule (never above d0, once ≤ 5 stays ≤ 5, ends ≤ 5) before falling back to free order. HMI alarm ID 18.
- **Planner:** order-1 IMPROVE move 1 is a kind-pattern relocate (block shifts). Gap to the judge's best plans +1.29 % → +0.35 %.
- **Demo:** the given data has 0 transfers. Use `tools/demo_db/fig1_half` (made by `tools/json_to_db.py`) in a TEST COPY of the project. Alarm numbers = WinCC IDs (bit + 1).
- **HMI humans:** optional new prototype `P_DateTime` (HUMAN_STEPS B) for the date/time in the footer; alarm import now has 18 alarms.
- Contract **v1.5**; details `tia-src/JUDGING.md` "Round 2".

## TIA crane v1.4: judge round 1 fixes (builder, 7 Nov 2026 ~06:00)
- **Changes:**
  - Exact list-order feasibility DP in FB11. The order-1 default no longer falls back to free order when an in-order plan exists: fallbacks went 11 → 3, and those 3 are provably infeasible.
  - New SLOT phase (drop-cell local search) and new FC21 `Crane_DropCost`.
  - DB10/DB11 are kept live, and POČETNO STANJE restores the loaded data.
  - ACK of a rejected put goes to PAUSED instead of an ALARM/ACK loop.
  - Order-fallback warning `AlarmWord2` bit 0, and missing-ID tags `AlarmUId`/`AlarmLId`.
  - Contract **v1.4**.
- **J over 30 random sets:** default 1.0684 → **1.0644**, free order 1.0549 → **1.0538**.
- **Checks:** compile 0/0, mirrors 774/774 and 570/570, stress 0 failures (464 sets).
- **Details:** `tia-src/JUDGING.md`. New tool `tools/crane_bench.py` (per-set benchmark, `--compare`, `--legacy`).
- **HMI humans:** the `Alarms` screen is now **number 15**, created in step A6 (see HUMAN_STEPS).

## TIA crane v1.3 optimisation (optimisation engineer, 7 Nov 2026 ~04:00)
- **FB11 now runs greedy → IMPROVE → publish.** IMPROVE is a deterministic local search (relocate, swap, pair) with a fixed budget of `World.CfgImproveEvals` = 3000, and it is never worse than the greedy. FB11 also publishes a closed-form **lower bound** (`World.LbJ`). CfgAlpha is now [0,100,200,300]. Contract **v1.3** (§4.8, §4.9).
- **J over 30 random sets, mmode 2:**
  - default order 1: **1.0751 → 1.0684**
  - free order: 1.0651 → **1.0549**
  - lower bound 1.0293, gap 2.5 % (free order)
- **Build:** `TIA_RESULT errors=0 warnings=0`, and `deliver/TIA_crane_v1_plc.zap21` was re-archived.
- **Parity:** mirrors 774/774 (greedy) and 570/570 (improve + bound).
- **Stress:** `tools/crane_stress.py`, 0 failures (see STATUS).
- **HMI:** new screen **Score** ("REZULTAT / OPTIMIZACIJA"), generated from `hmi-tia/layout.json`. 483 tags, check clean. Humans: nothing extra to draw; it uses the existing prototypes.
- **Ask the organizers:** may we choose the order freely? Spec §2 makes "deciding the container order" an FB10 task. If yes, set `HMI_IF.CfgOrderMode = 0` for −1.3 % J.
- **New tools:**
  - `crane_plan.py --improve N --lb`
  - `crane_eval.py --mmode --evals`
  - `crane_stress.py`
  - `crane_gen.py --stress N` writes `tools/crane_data_stress/`
- Talking points are in `plans/PITCH_CRANE.md`.

## TIA crane: FB1 findings and status (orchestrator final pass, 7 Nov 2026)
- **FB1 (recovered source, `tia-src/FB1_ANALYSIS.md`):**
  - **+1 M per move command**, so a diagonal x+y move = 1, not the 2 that spec p. 10 says.
  - A zero-distance move = +1 M, 0 s.
  - Lift and put = 20 s + 1 M each.
  - Reset goes to (0,0,1) and zeroes M and T.
  - Every command finishes in one FB1 call, and MB103 returns to 0.
  - Our PLC shows FB1's M/J and also the spec count `HMI_IF.MSpec/JSpec`.
- **Build:** `TIA_RESULT errors=0 warnings=0`. `deliver/TIA_crane_v1_plc.zap21` was re-archived; it is the PLC only.
- **Default order mode is now 1** (each list in its own order), with an automatic fallback to free order when the balance rule dead-ends (4 of 30 random sets).
- **Model J** (30 random sets): **1.0751 mean / 1.1683 max**. Free order gives 1.0651.
- **Review fixes:** duplicate-ID list states, drop-occupied re-target after ACK, DB10/DB11 online edits adopted, SEMI click latch, ACK race, bit 0 history spam, MANUAL reset with a load, literal MB103 = 0 check, alarm classes plus single ACK.
- **Not run on a PLC yet** (no PLCSIM here), and **no HMI imported yet**. Human TODOs and organizer questions are in `tia-src/STATUS.md`.

## Planner (planner worker, 7 Nov 2026)
**Files** in `tia-src/`:
- `10_FC_MoveCost.scl`: FC20 `"Crane_MoveCost"`, exactly per CONTRACT §4.1.
- `11_FB_Planner.scl`: FB11 `"Crane_Planner"`, interface exactly per §1.4. The STUB in `tia-work/stubs` is now obsolete.
- `12_planner_mirror.py`: a Python transliteration of the SCL, checked against `tools/crane_plan.py`. TiaRun ignores `.py` files.

**Compile:** all of tia-src imports cleanly, with **0 errors / 0 warnings**. The run used the shared `tia-work/crane` project with `--lock planner`, `--numbers` and `--ob30-ms 1000`. FC20 and FB11 were numbered as specified.

**Parity:**
- The mirror (the SCL logic step by step, in Python) gives the **same plan as the oracle in 774 of 774 runs**:
  - all 43 datasets × CfgMMode 0/1/2 × CfgOrderMode 0/1/2 × CfgBalMode 0/1
  - capacity-blocked sets are skipped
- "Same" means identical rows (kind, id, list_idx, src, dst, cum_t_ds, cum_m), the same variant, PredT_ds and PredM, and PredJ within 1e-9.
- Every error code matches the oracle, including all ErrCode 1 cases (OrderMode 2 fails on 20–28 of 43 sets).
- ErrCode 4 (Carried ≠ 0) and ErrCode 3 (CfgVariants = 5) were also checked.
- **PLCSIM parity is NOT done yet: there is no harness.** When one exists:
  - Load a dataset into DB10/11/20/21, press INIT and read `"World".Plan[1..PlanLen]`.
  - Compare against `python tools/crane_plan.py <set>.json --mmode 2`. Note that the stored `*.plan.csv` files were generated with **mmode 0**, while World.CfgMMode is now 2.

**Runtime behaviour:**
- Req edge call: snapshot only. Every following call runs CfgStepsPerCall greedy steps (one transfer each). Opening and closing a variant costs no step.
- Calls per job ≤ 1 + transfers × CfgVariants. The maximum seen on the datasets is **322 calls**, i.e. 322 OB1 cycles, well under 1 s at a normal scan time.
- Inner-loop work per step is at most **4608 iterations** (rand_04 class: lookahead table plus candidates). I estimate about 5–10 ms on a 1515 (an estimate; PLCSIM timing is not representative).
- Measured values are in the instance statics `"Crane_Control_DB".Planner.DiagMaxCallMs`, `DiagJobMs`, `DiagCalls` and `DiagSteps`. They come from `RUNTIME` and are diagnostics only; they do not affect the plan. Per-variant K/err are in `DiagVarK[1..4]` / `DiagVarErr[1..4]`.
  - **Please read DiagMaxCallMs on PLCSIM/HW.** If it is > 20 ms, keep CfgStepsPerCall = 1. The result does not depend on it.
- Req = FALSE during a job aborts it without touching World. Done/Error stay TRUE while Req stays TRUE. ErrCode keeps the last value until the next job.
- On success, World.Plan[PlanLen+1..96] is zeroed. PlanLen ≤ 96 is guaranteed (ErrCode 2 otherwise).
- On error: PlanValid = FALSE, PlanLen = 0, PlanVariant = 0.
- **ErrCode 3** covers:
  - CfgVariants ∉ 1..4, CfgOrderMode > 2, CfgBalMode > 1 or CfgMMode > 2
  - crane position out of range
  - a pending list entry with ID 0
  - a pending ID that is not found in its bay (as in the oracle)
- CfgStepsPerCall < 1 is treated as 1.

**TIA SCL gotcha (for everyone):**
- Identifiers are **case-insensitive**: `sg` vs `sG`, or `Lm` vs `lM`, is a duplicate declaration.
- Worse, one of the temp names `db`, `dx`, `dy`, `dg`, `e`, `s`, `L0`, `R0`, `D0`, `lo`, `hi`, `first`, `ok` or `rc` made the import **silently drop the whole VAR_TEMP section**. The import reports "ok", and the compile then shows hundreds of "Tag #x not defined". I suspect `db` or `L0`/`D0` (address-like). Renaming all of them fixed it. Avoid these names.

**Contract notes (no change needed, for the orchestrator):**
- I agree with the model worker's ambiguities 1 and 3. FB11 implements the same choices as Python: pending not found → 3; reachability over all pending entries.
- FB11 snapshots `World.N` at the Req edge for PredJ (§4.5 says World.N).

## HMI (hmi worker, 7 Nov 2026)
**Status: generator pipeline built and dry-run tested on mock prototypes.** Nothing has been imported into `tia-work/crane` yet: the Openness lock was held and the human prototypes don't exist yet.

Everything lives in `hmi-tia/`:
- See `README.md`.
- Human click list: `HUMAN_STEPS.md`.
- One command: `.\hmi-tia\regen.ps1 [-Export] [-DryRun]`.

**Verified:**
- `HmiGen.exe` compiles with csc (0 errors).
- `gen_hmi.py all` against the mock writes:
  - 472 tags
  - 11 text lists
  - template Tpl (49 objects)
  - Main (305), Manual (298), Lists (304), AlarmLog (49)
- `CHECK_RESULT problems=0`: unique IDs/ObjectNames, every tag and text-list link resolves, everything is inside 1920×1080.
- `alarms_gen.py` writes a 16-alarm xlsx/csv. The xlsx round-trips through its own `--sample` reader.
- PNG previews are in `hmi-tia/mock/preview/`.

**Not verified yet:**
- the real import, HMI compile (`HMI_RESULT`) and runtime
- schema of Rectangle/Button/SymbolicIO/Bar/animations, tag table and text list. These come from the human prototypes (HUMAN_STEPS A+B). Only TextField/IOField are confirmed from a real export.

**Spec §2.1 checklist (where each item is):**
- [x] ON/OFF + READY/OFF indication: Tpl, UKLJ./ISKLJ. (InvertBit SwOn) + SPREMAN/ISKLJUČEN lamps
- [x] INITIAL STATE: Tpl, POČETNO STANJE (BtnInit)
- [x] AUTO/SEMI/MANUAL buttons + indication: Tpl, 3 buttons + LampAuto/Semi/Manual bars + Mode text
- [x] START/STOP/ACK: Tpl (+ SLJEDEĆI KORAK; it is always visible, with a StepWaiting bar)
- [x] Graphical Bay 0 and Bay 1 with IDs: Main/Manual, 2×48 cells coloured by CellSt with ID, crane X/Y markers, ship L/R split
- [x] Manipulations + working time: Tpl, M, T (+ J, predicted M/T/J)
- [x] Alarms incl. "ID kontejnera postoji u listi za istovar, ali ne postoji u polju Bay 0": 16 discrete alarms on AlarmWord (alarm ID 4 = bit 3) + Tpl banner
- [ ] Alarm history: hand-made `Alarms` screen (alarm buffer view, HUMAN_STEPS D) + generated `AlarmLog` (AlarmHist[0..15])
- [ ] RT Advanced runs against PLCSIM: **blocked, PLCSIM is not installed**

**Notes for other workers:**
- Runtime: the HMI uses only `HMI_IF`. The alarm trigger is `HMI_IF.AlarmWord` bit n = `%Xn` of the Word value; please keep that convention.
- Runtime: `AlarmHist[i] = -1` = empty is handled (text list entry -1 → "-").
- Orchestrator/tooling: the HMI device has **no PLC connection** (U12). The human must create `HMI_Connection_1` (HUMAN_STEPS A1-A2) before tags can be imported.
- Screen resolution: the given `Screen_1` is 1024×768. The layout is 1920×1080. Either change the HMI_RT_1 runtime resolution (A3) or set `canvas.scale` in `layout.json`.

## Runtime (runtime worker, 7 Nov 2026 ~01:35)
**Files** in `tia-src/`:
- `01_types.udt`, `02_World.db` (DB100) and `03_HMI_IF.db` (DB101): exactly as CONTRACT §1.1–1.3
- `20_FC_CheckCmd.scl` (FC10)
- `21_FB_CraneControl.scl` (FB10)
- `22_DB_CraneControl.db` (DB110)
- `30_OB1_Main.scl` (OB1)
- `31_OB30_Cyclic.scl` (OB30, SCL, replaces the given LAD body with the same FB1 wiring)

**Compile:** all imports OK and **0 errors / 0 warnings**. The run used a private copy of the project (`tia-work/rt_proj`) and sources `tia-work/rt_src` = tia-src plus a planner STUB (`tia-work/stubs/11_FB_Planner_STUB.scl`, empty plan, never in tia-src). Numbers FB10/FB11/FC10/DB100/101/110/OB1 were applied, and OB30 stays at 1000 ms. The shared `tia-work/crane` project was NOT touched.
- Lock note: TiaRun took over the stale lock `tooling-smoke 01:11:35` (>10 min) at 01:21.

**Not yet verified on PLCSIM:** there is no harness yet, and the real planner FB11 does not exist yet.

**Data changes** (start values, announced per CONTRACT §1.2):
- `World.CfgMMode := 2`, per the FB1 findings (M +1 per move command).
- `HMI_IF.Mode := 1` (AUTO default).

**Deviations from the contract (reasons):**
1. **Mode buttons are applied at once, except during INIT.** They are not held until "not Busy": in AUTO, OB30 issues the next command in the same tick that it detects completion, so Busy is almost always TRUE and the switch would never apply. MANUAL while RUNNING still means PAUSED plus withdrawal of the staged command; the command already in FB1 completes.
2. **START with a container on the hook** is allowed when it resumes the transfer in progress: PlanValid, Phase ≥ 2 and Plan[PlanIdx].Id = Carried. This is the case after STOP following a lift. Otherwise alarm 11. Without this exception, STOP/START would be impossible mid-transfer.
3. **ACK sets PlanValid := FALSE only when an OB30 fault (World.Fault) was present AND the hook is empty.** With a load on the hook the plan is kept and resumed from the done pointer, because the planner cannot start with Carried ≠ 0 (ErrCode 4). ACK of INIT warnings alone (bits 3–6) does not force a replan.
4. **Continuous alarm bit 0 (|L−R| > 5) is a warning, not blocking, also in RUNNING.** With an imbalanced start, the planner runs in non-worsening mode and |L−R| > 5 legitimately persists for a while. Blocking would deadlock. Every lift or put that would make the ship worse is still blocked by CheckCmd in OB30 (World.Fault bit 0, which is blocking).
5. **Any World.Fault bit stops issuing until ACK**, including warning bits 9 and 14 (CONTRACT §3.4, step 3: `Fault = 0`). FB10 therefore treats every World.Fault bit as blocking, so the state goes to ALARM.
6. **INIT failures go to ALARM with PrevState = READY.**
   - Capacity (bit 7): Initialized stays FALSE; press INIT again after fixing the data.
   - Planner error (bit 8): Initialized := TRUE, so MANUAL can be used to fix things.
   - A PLANNING failure (bit 8), or PLANNING with a load on the hook (bit 11), returns to PAUSED after ACK, so there is no replan/alarm loop.
7. **A MANUAL zero-distance move** (target = crane position) is dropped silently, because FB1 would add +1 M for nothing (U6).
8. **OB30 forces X/Y/Bay of lift/put to the crane position before CheckCmd**, as a safety measure. On reset (10) it does not clear Carried; INIT clears it.
9. **Race protection.**
   - Resync, INIT step 4 and PLANNING step 1 wait for `NOT Busy AND SeenSeq = DoneSeq`, so the done pointer and list states include the last completion before restaging or planning.
   - DoneSeq/LastDone are read as seq → LastDone → seq again.

**For the HMI worker:**
- `HMI_IF.AlarmHist[i] = -1` means an empty entry. It is initialised on the first scan, because bit number 0 is a real alarm (imbalance).
- The M/T stamp of each history entry is in `"Crane_Control_DB".AlarmHistM[0..15]` (UDInt) and `.AlarmHistT[0..15]` (Real), parallel to AlarmHist. These are FB10 statics, so the contract is unchanged.
- **Before INIT**, Cell0/Cell1 show the raw DB10/DB11, and CellSt only uses 0, 1 and 7. **After INIT** they show the container model (World).
- Buttons: use SetBit on press. FB10 clears each bit in the next OB1 cycle. SwOn is a level (InvertBit).
- AlarmX/AlarmY = -1 for the list alarms (bits 3/4), which have no cell.
- `HMI_IF.Heartbeat` and `OB30Ticks` come from OB30 / FB10. Use them for a "PLC alive" indicator.
- The toy archive data gives this after INIT:
  - bits 3 and 4: 111..666 are not anywhere, 777 is in Bay1, 123 is in Bay0, 124/125 are not anywhere
  - N = 10, UTotal = LTotal = 0
  - an empty plan, so START goes straight to DONE (bit 15)

**For the planner worker:**
- FB10 calls `#Planner(Req := #PlanReq)` once per OB1 cycle and holds Req TRUE until Done or Error is seen, then drops it.
- Before each request FB10 sets World.BaseT_ds = ROUND("time"·10) and BaseM = MD107, and guarantees: no FB1 command in flight, CmdReady = FALSE, Carried = 0, list states refreshed.
- On Done FB10 requires `World.PlanValid = TRUE`. It then sets PlanIdx = StageIdx = 1 and Phase = StagePhase = 1 if the crane (at plan time) is already at Plan[1].Src, else 0. The same rule applies between transfers (Dst[i−1] = Src[i]).
- Please clamp PlanLen ≤ 96.

## FB1 findings (tooling worker, 7 Nov 2026 ~01:15)
FB1 is know-how protected, but its **full SCL body was recovered** from the archive's search index. Details, with the recovered code, are in `tia-src/FB1_ANALYSIS.md` (and `tia-work/FB1_ANALYSIS.md`).

**>>> ORGANIZER QUESTION, ask now: FB1 counts M = +1 per MOVE COMMAND. <<<** A diagonal x+y move counts 1. The spec (p. 10) says a diagonal x+y move counts 2. FB1 is the source of MD107. Use **CfgMMode = 2** until the organizers answer.

- **U1. One-call completion.** Each command completes in ONE call. `command_id := 0` at the end of every call (also for 0 and invalid IDs), and the outputs are refreshed every call.
- **U2. M counting.** M is +1 per move (cmd 3), whatever the number of axes changed. **Contradicts the spec.**
- **U3. Bay change.** It is irrelevant to M. For time, the global column is G = x+6 (Bay0) or x (Bay1).
- **U4. Move time.** T_move = max(|ΔG|·6.0, |Δy|·2.3)/1.0 in REAL, using the DB1 constants. Expect float drift of about 1e-6 s per command; compare with a tolerance.
- **U5. Lift and put.** Each adds 20.0 s (from DB1) and +1 M. Neither reads x, y or bay, and neither checks anything.
- **U6. Move to the current position.** It adds **+1 M** and 0 s. NEVER issue a zero-distance move.
- **U7. No range checks.** For bay ≠ 0/1 the time is garbage (stale temp), yet the bay is still set. Only send bay 0/1, x 0..3, y 0..11.
- **U8. Reset (10).** M=0, T=0, x=0, y=0, bay=1, all in one call. Unknown IDs are no-ops that also clear command_id.
- **U9. Given OB30 and OB100.**
  - OB30 "Cyclic interrupt" is **LAD**, with 1 network calling `"Crane_manipulation_DB"`:
    - IN: "new_x_position", "new_y_position", "new_bay_ID"
    - INOUT: "new_command_ID"
    - OUT: "x_position", "y_position", "bay_ID", "number_of_manipulations", "time"
  - OB30 runs at **CyclicTime = 1 000 000 µs**, priority 10.
  - OB100 "Startup" (SCL) sets DB2 command 0, bay 1, x/y 0, M/T 0, and tags new_x/y = 0, new_bay = 1, new_cmd = 0.
- **U10. Tag names.** MD112 is named **`"time"`** (Real), in **`"Default tag table"`**. That table also holds x_position MB104, y_position MB105, bay_ID MB106 and number_of_manipulations MD107. MB100..103 are in table **`"Crane_command"`**.
- **U11. Protection.** Only FB1 and DB2 are know-how protected. There are no UDTs.
- **U12. HMI.** `PC-System_1` / `HMI_RT_1` has **NO connection** to PLC_1. Its only screen is `Screen_1`, and its only HMI tag is "time".
- **Given data:**
  - DB10: [0,0]=123, [0,1]=326, [0,2]=987
  - DB11: [0,1]=246, [0,7]=675, [1,5]=777
  - DB20: 111..777 (7 IDs)
  - DB21: 123, 124, 125
  - This is an alarm-test set. The JSON is in `tia-src/given_data.json`. The orchestrator's "bay unknown" placement is now resolved: 123/326/987 are in **Bay0**.
- **Model worker: action required.**
  - Set the FB1 emulator to M = 1 per move, plus 1 for each lift and put, and 0 s / +1 M for a zero move.
  - Regenerate the plans with CfgMMode 2.
  - `sample_archive_b0` is the correct placement of the archive sample.

## Tooling (tooling worker, 7 Nov 2026 ~01:15)
**Project (retrieved headless, compiles with 0 errors):** `C:\Users\lovro\Documents\claudio\plc-hackathon-2026\tia-work\crane\PLC_hackathon_2026_V21\PLC_hackathon_2026_V21.ap21`. Its project dir is `...\tia-work\crane\PLC_hackathon_2026_V21`.

**Exports** are in `tia-work\export\`:
- `inventory.txt`: blocks, languages, KHP, OB attributes, tags, HMI
- `src\*.db` / `*.scl`: generated sources of the open blocks
- `xml\*.xml`: SimaticML of all blocks, tag tables and Screen_1

**TiaRun:**
- Location: `.claude\skills\tia-portal\scripts\TiaRun.exe`. Rebuild with `build.ps1` in the same folder.
- It attaches to a running TIA, otherwise it starts TIA headless.
- It refuses to run if another project is open in that TIA. **Do not open the crane project in the TIA GUI while agents compile.**

Flags:
- `--project <dir>`
- `--retrieve x.zap21 --to <dir>`
- `--headless`
- `--lock <worker>`: CONTRACT §5 lock, `tia-work\openness.lock`. It waits up to 15 min, takes over a stale lock older than 10 min, and is released on exit.
- `--src <dir>`
- `--numbers <file>`
- `--ob30-ms 1000`
- `--no-compile`
- `--export <dir>`
- `--archive <out.zap21>`
- `--no-save`

**Compile loop for runtime and planner** (run from the repo root, Git Bash):
```
.claude/skills/tia-portal/scripts/TiaRun.exe --project "C:\Users\lovro\Documents\claudio\plc-hackathon-2026\tia-work\crane\PLC_hackathon_2026_V21" --headless --lock <worker> --src "C:\Users\lovro\Documents\claudio\plc-hackathon-2026\tia-src" --numbers "C:\Users\lovro\Documents\claudio\plc-hackathon-2026\tia-src\numbers.txt" --ob30-ms 1000
```

Output lines:
- `IMPORT <file> ok -> blocks` or `[ERROR] IMPORT <file>: <message>`
- `NUMBERS ...`
- `OB30 ... CyclicTime`
- `[ERROR] <block path> :: <msg>`, one per compiler message
- `TIA_RESULT errors=N warnings=M [import_errors=K]`

Exit code: 0 ok, 1 errors, 2 fatal.

A headless run takes 1–3 min. Only `*.udt`, `*.db`, `*.scl` and `*.awl` files in tia-src are imported, in alphabetical order. `.md` and `.json` files are ignored.

**Archive a build:** add `--archive C:\...\deliver\TIA_crane_vX.zap21`.

**Verified on a throwaway copy** (`tia-work\smoke_proj`):
- An SCL `ORGANIZATION_BLOCK "Main"` imports as **OB1 ProgramCycle** once `--numbers` sets Main=OB:1. No pre-creation is needed.
- An SCL `"Cyclic interrupt"` source replaces the given LAD OB30. It keeps number 30, CyclicTime 1000 ms and priority 10.
- `--numbers` and `--ob30-ms` are idempotent: the second run prints "(unchanged)".
- `--archive` works.
- Compile errors are printed as `[ERROR] PLC_1/Program blocks/<Block> (FC1) [<file>.scl:<source line>] line <body line> :: msg`.

**Waiting on the planner.** `tia-src` has no `10_FC_MoveCost.scl` or `11_FB_Planner.scl` yet, so a full compile fails on FB10's `"Crane_Planner"` multi-instance until the planner delivers them.

**BLOCKER: PLCSIM.** Neither PLCSIM nor PLCSIM Advanced is installed on this laptop. No uninstall entry exists and there is no `Siemens.Simatic.Simulation.Runtime` DLL. PlcsimHarness (task 8) can't be built or tested until someone installs **S7-PLCSIM Advanced V8** (or PLCSIM V21 from the TIA ISO).

## Model (model worker, 7 Nov 2026)
**Files:**
- `tools/crane_model.py`: FB1 emulator, cost model, balance, CheckCmd, INIT validation, J
- `tools/crane_plan.py`: the exact CONTRACT §4 planner, parity CSV, `--trace`, `--cmds`, execution simulation
- `tools/crane_gen.py`: datasets, `*.plan.csv` files and `tools/crane_golden.json`
- `tools/crane_eval.py`: statistics
- `tools/crane_data/`: 43 sets, each with a `.plan.csv`

**Assumptions:**
- FB1 findings were not yet available, so the model uses CfgMMode 0 (spec rule, global X), one-call completion and max(60·dG, 23·dy) ds.
- `sample_archive_b0/_b1` are APPROXIMATE: the bay holding 123/326/987 is unknown, so both placements were written.

**Verified:**
- Two runs give byte-identical output.
- Every plan was executed command by command through the FB1 emulator, with CheckCmd = 0 before each command. Cum T/M matched the plan at every put, and |L−R| ≤ 5 held after every lift and put.
- Only one set fails: `edge_all_left_unloads_noload_infeasible`. This failure is expected (ErrCode 1, balance cannot be held).

**Parity CLI:**
```
python tools/crane_plan.py tools/crane_data/<set>.json [--trace] [--cmds]
```
On error it prints `RESULT error=<code>`.

**J results**, mean / max over 30 random sets. Default config: order 0, balmode 0, α {0,50,100,150}.

| Config | mean J | max J |
|---|---|---|
| **v1 winner (default)** | **1.1301** | 1.2444 |
| variant α=0 / 50 / 100 / 150 alone | 1.1466 / 1.1371 / 1.1359 / 1.1411 | |
| CfgOrderMode 1 (per-list order) | 1.1837 (+0.054) | 1.3146 |
| CfgOrderMode 2 (unloads then loads) | 1.3110 on the 14/30 sets where feasible; **ErrCode 1 on 16/30** | |
| CfgBalMode 1 | 1.1301 (same); **ErrCode 1 on rand_18** | |
| naive (list order, nearest slot) | 1.3185 on 14/30 feasible | |
| lower bound (58 s + 3 M per transfer) | 0.7566 | |
| algo v2 (2-step lookahead, top-3) | 1.1284 (−0.0017) | 1.2385 |

**Variant win counts** for v1..v4: 5 / 8 / 11 / 6 on the random sets, and 8 / 9 / 15 / 8 on all 40 feasible sets.

**Alpha sets tried:**

| Alpha set | mean J |
|---|---|
| {0,50,100,150} | **1.1301** |
| {0,50,100,200} | 1.1303 |
| {0,75,100,150} | 1.1308 |
| {25,50,75,100} | 1.1310 |
| {50,100,150,200} | 1.1313 |

**Recommendation:**
- Keep CfgAlpha [0,50,100,150] and CfgOrderMode 0.
- Mode 2 is often infeasible under the balance rule. Keep it only if the organizers mandate list order.
- Do not adopt v2. Its gain is 0.15 %, it costs 4× the CPU per step, and it is behind `--algo v2` only.

**PLC budget warning for the planner worker:**
- A literal Nx is 96 sources × 48 destinations × 95 ES' = about 440k W evaluations per step, which is far over 20 ms.
- In OrderMode 0, ES' = ES∖{s}. Precompute, per free d, the best and second-best W(d→s') over ES. Then Nx = best, unless best belongs to s, in which case Nx = second-best (or 0). This is exactly equal to the literal min, and `crane_plan.py` does it this way.
- 4 variants × ≤ 96 steps = 384 calls, which is within the 500-call budget.

**Contract ambiguities (for the orchestrator):**
1. §4.2: a pending ID that cannot be found in its bay at plan time (possible after MANUAL moves) has no ErrCode defined. Python returns **3**.
2. §3.2.4: "already seen in either list" leaves two things open:
   - the scan order across the lists. Python scans UList 1..48 and then LList 1..48.
   - whether rejected entries count as seen. Python counts every earlier non-zero entry, whatever its state.
3. §4.3: reachability counts u_L, u_R and n over **all** pending entries (PU/PL), not over ES. Python uses all pending, in every order mode.
4. §4.7: the RESULT line for an error is not defined. Python prints `RESULT error=<code>`, and `RESULT error=capacity(bit7)` when INIT blocks. PredJ is a Real, so the harness should compare J with a tolerance and T_ds/M exactly.
5. §4.5: N = raw non-zero entries, which includes invalid, duplicate and missing IDs. That lowers J (edge_invalid_dup_ids: J 0.86). Is this intended?
6. §4.4: in CfgBalMode 1, Pass A reachability is x-split only, so the F/A rule can dead-end (rand_18 gives ErrCode 1). Consider falling back to BalMode 0, or a y-reachability check.
7. §4.6: OrderMode 2 plus the step rule is infeasible on about half of the random sets, because unloads in list order unbalance the ship and no load may interleave.


## Orchestrator integration (7 Nov 2026 ~02:05)
- **CONTRACT.md is now v1.1:**
  - FB1 counts +1 M per move command, so CfgMMode defaults to 2.
  - A zero-distance move is never issued.
  - The tag tables are `"Crane_command"` and `"Default tag table"`.
  - U1–U12 are answered.
  - The runtime deviations 1–9 are accepted.
- **`tools/crane_*.py` default to mmode 2**, and the FB1 emulator charges +1 M for a zero-distance move. The `crane_data/*.plan.csv` files and `crane_golden.json` were regenerated; the golden now includes `tia-src/given_data.json`. The dataset JSONs are unchanged.
- **Full tia-src build** into `tia-work/crane` gives **TIA_RESULT errors=0 warnings=0**. OB1 calls FB10, and OB30 runs at 1000 ms. The archive is `deliver/TIA_crane_v1_plc.zap21`.
- Status, gaps and human TODOs are in `tia-src/STATUS.md`.
