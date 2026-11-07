# CONTRACT: TIA container crane (TASK 2)

This file is the single source of truth for every crane worker. **Workers may only read it.** Only the orchestrator changes it. To request a change, add a dated note under "Contract change requests" in `TEAM_NOTES.md`.
Version **1.7**, spec M rule as default, 7 Nov 2026 (v1.6 judge round 3, v1.5 judge round 2, v1.4 judge round 1 ~06:00, v1.3 optimisation pass ~04:00, v1.2 orchestrator final pass, v1.1 7 Nov ~02:05, v1.0 6 Nov ~23:40).

**v1.7 changes (builder, spec M rule as default, see `tia-src/STATUS.md` "v1.7"):** World, HMI_IF, FB10 only; FB11, FC10, FC20, FC21, OB30 logic unchanged.
- **Team decision: M is counted by the spec text p. 10** (diagonal = 2, bay change = x change). `World.CfgMMode` start value **0** (was 2); mode 2 (= FB1 MD107, +1 per command) stays selectable. FB1 is not changed; MD107 and `World.MSpec` differ by design.
- **CfgAlpha start values [0, 75, 125, 200]** (retuned for mode 0).
- **HMI_IF:** `M` / `J` = spec rule (primary, from `World.MSpec`); new `MFb1` / `JFb1` = FB1 counter MD107 and its J (secondary); `MSpec` / `JSpec` kept as copies of `M` / `J`.
- **FB10:** `BaseM` at a plan request = `World.MSpec` if CfgMMode = 0, else MD107, so PredM/PredJ/LbJ follow the active M rule. `AlarmHistM` records MSpec.
- Tools default to mmode 0 and the new alphas (`crane_plan`, `crane_eval`, `crane_bench`, `crane_gen`, `crane_stress`, mirrors, `fb10_init_model`); golden carries `M_FB1` / `m_fb1` (expected MD107).

**v1.6 changes (builder, judge round 3, see `tia-src/JUDGING.md` "Round 3"):** FB10 and World only; FB11, FC10, OB30 unchanged.
- **New data at POČETNO STANJE (§3.5), replaces the v1.5 rule:** region 2a marks every externally edited cell (`EditMark`, value before the edit `EditVal`). An edit while **no job is in progress** (`JobActive` = a Src 1..3 command completed since INIT; DONE also counts as "no job") counts in `NewCnt`; an edit during a job (obstacle) counts in `ObstCnt`. Writing a cell back to `EditVal` removes its mark. INIT step 3: new yard (InitBay := DB10/DB11) iff NOT HaveInit OR NewCnt > 0 OR (DB20/DB21 changed AND ObstCnt > 0) OR ObstCnt ≥ 8 OR DB10/DB11 ≠ Snap; otherwise DB10/DB11 := InitBay (the loaded data set, including a container that was on the hook). The lists are always read from DB20/DB21, so new lists alone keep the loaded yard. JobActive/EditMark/NewCnt/ObstCnt are cleared (R3-E1, R3-J1). `ExtEdit` is unused.
- **ACK re-target of a rejected ship put (§3.3):** among the free cells that pass the one-step balance rule, the nearest one whose side keeps the remaining lists feasible in the preferred order is chosen (exact FtMask[0,0] of the state after the put, bit-parallel in FB10: try 1 step rule, try 2 relaxed ceiling BalD0); only if no such cell exists, the nearest cell as in v1.4 (R3-E2). Python reference `tools/fb10_init_model.retarget()` / `ft00()`.
- **World.CfgRelaxMin (Bool, FALSE):** TRUE makes the relaxed fallback try BalCeil = CfgBalLimit+1, +2, … BalD0 (smallest feasible ceiling) instead of BalD0 at once (R3-E3; costs +5…9 % J on the affected sets, default off). Python `CRANE_RELAX_MIN=1`.

**v1.5 changes (builder, judge round 2, see `tia-src/JUDGING.md` "Round 2"):**
- **List check (§3.2):** an entry is a duplicate only if the same ID was in an earlier **accepted** entry. A rejected bogus entry (e.g. an unload entry naming a yard container) no longer kills the valid load entry with that ID (R2-E1).
- **New data at POČETNO STANJE (§3.5):** an external DB10/DB11 edit sets ExtEdit in **every** state (not only OFF/READY/DONE), and with an empty hook outside RUNNING/PLANNING it also sets PlanValid := FALSE (START replans). INIT step 3 also treats changed DB20/DB21 (≠ World.UList/LList of the last INIT) as new data (R2-E2, R2-J3).
- **ACK re-target without a cell (§3.3):** bit 7 raised by the ACK re-target is shown but **not blocking** (FB10 static `NoCellWarn`), so one ACK leaves the system PAUSED with MANUAL enabled; the next ACK or INIT clears it (R2-E3).
- **POČETNO STANJE is ignored while RUNNING / PLANNING** (§3.1): STOP first (R2-J4).
- **Relaxed balance rule (§4.3) for a ship loaded out of balance (R2-J1):** new World member `BalCeil` (Int, 0). FB10 stores the loaded imbalance `BalD0` at INIT. Fallback chain on ErrCode 1: (order k, step rule) → if BalD0 > CfgBalLimit: (order k, BalCeil := BalD0) → (order k−1, step rule) → … The relaxed rule is used only when FtMask proves the order feasible under it (else FB11 ErrCode 1), and the plan must end balanced (terminal masks, SLOT trajectory). CheckCmd reads `World.BalCeil`. Warning `HMI_IF.AlarmWord2` bit 1 (HMI alarm ID 18) while such a plan is active.
- **IMPROVE move 1 in order mode 1 (§4.8)** is the kind-pattern token relocate (R2-SCORE-1): the U/L token at i moves to j and the sequence is re-derived (k-th U = k-th pending unload, k-th L = k-th load); valid iff an element of the other kind lies between i and j; p = first changed position. Order modes 0/2 unchanged.
- HMI: date/time field (optional prototype `P_DateTime`) in the template footer (R2-J4).

**v1.4 changes (builder, judge round 1, see `tia-src/JUDGING.md`):**
- **Exact order feasibility** (§4.10) replaces the reachability test in Pass A for order modes 1/2 (greedy) and in every IMPROVE replay. The order-1 default no longer falls back to free order when an in-order balanced plan exists (judge R1-E1); FB10 falls back only when the preferred mode is provably infeasible and then raises warning `HMI_IF.AlarmWord2` bit 0 (`HMI_IF.OrderFallback`).
- **SLOT phase** (§4.11) after IMPROVE: drop-cell local search with a fixed sequence (relocate / swap, separable cost). New FC21 `"Crane_DropCost"`.
- **DB10/DB11 are the live state** (§3.5): FB10 region 2a mirrors every World cell change into `"Current_state_of_Bay0/1"`; POČETNO STANJE restores the loaded data from a private copy (judge R1-E2 / J4).
- **ACK after a rejected plan put** (bit 0 or bit 2 with a load): re-target to the nearest balance-safe free cell; if none, PAUSED + bit 7 instead of re-staging the same put (judge R1-E3).
- New World members: `CfgSlotSweeps` (Int, 10), `SlotAccepts`, `OrderFeasible`. New HMI_IF members: `OrderFallback`, `SlotAccepts`, `AlarmWord2`, `AlarmUId`, `AlarmUCnt`, `AlarmLId`, `AlarmLCnt`.

**v1.3 changes (optimisation engineer, see §4.8, §4.9 and `plans/PITCH_CRANE.md`):**
- **IMPROVE phase** in FB11 after the multi-start greedy (§4.8): deterministic first-improvement local search over the transfer order, never worse than the greedy, respects the order mode (1 = per-list order kept, 2 = phase skipped) and every balance rule. Python reference `crane_plan.improve()`, `plan_fb(..., imp_evals=)`; SCL mirror `tia-src/13_improve_mirror.py`.
- **Closed-form lower bound** (§4.9) computed by FB11 at the Req edge, published with the plan.
- **CfgAlpha start values [0, 100, 200, 300]** (retuned for CfgMMode 2; was [0, 50, 100, 150]).
- New World members: `CfgImproveEvals` (DInt, 3000), `CfgImproveDist` (Int, 0), `CfgImprovePerCall` (Int, 1), `PredJ0`, `LbT_ds`, `LbM`, `LbJ`, `ImpEvals`, `ImpAccepts`.
- New HMI_IF members: `PredJ0`, `LbJ`, `GapPct`, `ImpGainPct`, `ImpEvals`, `PlanProgress`; HMI screen `Score` (14).
- FB11 interface unchanged. Calls per job ≤ 1 + transfers·CfgVariants + CfgImproveEvals/CfgImprovePerCall (≈ 3400 OB1 cycles at the defaults); work per call ≤ one greedy step or CfgImprovePerCall replays.

**v1.2 changes (review fixes, see `tia-src/STATUS.md`):**
- **CfgOrderMode default = 1** (per-list order; hedge for elimination criterion 1) in HMI_IF and World. FB10 keeps the HMI choice as the preferred mode and, when FB11 returns ErrCode 1, retries with order 2 → 1 → 0, then CfgBalMode 1 → 0. `HMI_IF.OrderModeAct` shows the mode actually used. Tools: `crane_plan.plan_fb`, CLI default `--order 1`.
- List states: a plan put marks exactly `Plan[TrIdx].ListIdx` done. A MANUAL put uses the presence check, and a duplicate ID (in both bays) never changes a state. Before every replan, pending entries whose ID left its source bay become done (in the destination bay) or skipped (bit 3/4).
- Online edits of DB10/DB11 after INIT are adopted cell by cell into World (test hook for the pick/drop pre-check).
- ACK of bit 2 (drop occupied) on a plan put with a load: the put is re-targeted to the nearest free, balance-safe cell of the same bay, and the plan is redone after that put.
- An ACK in the same OB1 cycle as a new OB30 fault is ignored. ACK keeps bit 0 latched while the ship is still unbalanced.
- Config changes apply only with an empty hook and FB1 idle. MANUAL reset (cmd 10) with a load is rejected (bit 11).
- SEMI: a NEXT STEP click is latched; in READY/PAUSED it acts as START plus one step.
- OB30 issues only if `"new_command_ID" = 0` (literal spec 2.2 check). OB30 also counts `World.MSpec` (spec rule: +1 per changed axis, +1 lift/put).
- New HMI_IF members: `AlarmHmiAck` (WinCC acknowledgement tag = POTVRDA), `AlarmAckWord` (= NOT AlarmWord, WinCC PLC acknowledgement tag), `MSpec`, `JSpec`, `OrderModeAct`.

**v1.1 changes (FB1 source recovered, see `tia-src/FB1_ANALYSIS.md`):**
- FB1 counts **+1 M per move command** (diagonal = 1, not 2 as spec p. 10 says). **CfgMMode default = 2** (World start value). Organizer question open; mode 0 stays selectable.
- A move to the current position costs +1 M and 0 s in FB1. **Never issue a zero-distance move** (skip rule in AUTO/SEMI; MANUAL drops it).
- Tag table names: `"Crane_command"` (MB100..103), `"Default tag table"` (MB104..106, MD107, MD112 = `"time"`).
- U1..U12 answered (§2). Runtime deviations accepted as documented in TEAM_NOTES "Runtime" (mode buttons immediate, START with load finishes the transfer, bit 0 continuous = warning, any OB30 fault halts until ACK, default Mode = AUTO).
- `tools/crane_*.py` default to mmode 2; the FB1 emulator reproduces the zero-distance +1 M.

Spec: `task/tia/PLC_hackathon_2026_HR.pdf`. Plan: `plans/TIA_crane_plan.md`. Rules: AGENTS.md (TASK 2 + ORGANIZER CLARIFICATIONS).
**Official clarification:** there is only ONE yard bay. Valid bays are **0 = ship** and **1 = yard**. Bay 2 does not exist; ignore every Bay 2 formula.

---

## 0. Ground facts read from the archive

Read by the orchestrator from `PLC_hackathon_2026_V21.zap21` strings. The tooling worker must confirm them (see U-list in §2).

| Given object | Name in project | Content |
|---|---|---|
| FB1 | `"Crane_manipulation"` | see §2 |
| DB2 | `"Crane_manipulation_DB"` | instance of FB1 |
| DB1 | `"Global_constants"` | Real: `container_width_in_m`=2.3, `container_length_in_m`=6.0, `velocity_of_the_crane_in_m_per_s`=1.0, `time_to_lift_a_container_in_s`=20.0, `time_to_put_down_a_container_in_s`=20.0 |
| DB10 | `"Current_state_of_Bay0"` | `Bay0 : Array[0..3, 0..11] of UInt` (ship, 0 = empty) |
| DB11 | `"Current_state_of_Bay1"` | `Bay1 : Array[0..3, 0..11] of UInt` (yard) |
| DB20 | `"From_Bay0_to_Bay1"` | `IDs_of_the_containers : Array[1..48] of UInt` (**unload list**) |
| DB21 | `"From_Bay1_to_Bay0"` | `Bay1_IDs_of_the_containers : Array[1..48] of UInt` (**load list**) |
| OB30 | `"Cyclic interrupt"` | given as LAD, 1 network calling FB1 (1000 ms, prio 10); **replaced by our SCL source** with identical FB1 wiring |
| OB100 | `"Startup"` | already exists. **Do not touch it.** |
| OB1 | – | **does NOT exist.** We create `"Main"`. |
| HMI | PC station `PC-System_1`, WinCC RT Advanced | already in the project |

**Given PLC tags** (MB100..103 in tag table `"Crane_command"`; MB104..MD112 in `"Default tag table"`, confirmed by tooling):

| Tag | Address | Type | Meaning |
|---|---|---|---|
| `"new_x_position"` | %MB100 | SInt | FB1 input x |
| `"new_y_position"` | %MB101 | SInt | FB1 input y |
| `"new_bay_ID"` | %MB102 | USInt | FB1 input bay |
| `"new_command_ID"` | %MB103 | USInt | FB1 InOut command_id |
| `"x_position"` | %MB104 | SInt | FB1 out pos_x_after_command |
| `"y_position"` | %MB105 | SInt | FB1 out pos_y_after_command |
| `"bay_ID"` | %MB106 | USInt | FB1 out bay_ID_after_command |
| `"number_of_manipulations"` | %MD107 | UDInt | FB1 out number_of_manipulations (**M**) |
| `"time"` (confirmed, U10) | %MD112 | Real | FB1 out working_time (**T**, seconds) |

Our code accesses these **only by symbolic name**. If the MD112 tag turns out to have a different name, the runtime worker uses whatever the tooling worker reports in TEAM_NOTES.md.

Archive start values (toy alarm-test set): one list holds 111, 222, 333, 444, 555, 666, 777; one bay has [0,0]=123, [0,1]=326, [0,2]=987. Competition data will differ: **never hard-code data**.

---

## 1. Block list, numbers, owners

All PLC code is SCL **external sources** in `tia-src/`. Import uses `TiaRun.exe --src` (alphabetical order = dependency order), then `--numbers tia-src/numbers.txt` renumbers blocks.

| File (tia-src/) | Blocks | No. | Lang | Owner |
|---|---|---|---|---|
| `01_types.udt` | TYPE `"typeCmd"`, `"typeTransfer"` | – | UDT | runtime |
| `02_World.db` | DATA_BLOCK `"World"` | DB100 | – | runtime |
| `03_HMI_IF.db` | DATA_BLOCK `"HMI_IF"` | DB101 | – | runtime |
| `10_FC_MoveCost.scl` | FUNCTION `"Crane_MoveCost"` : DInt | FC20 | SCL | planner |
| `11_FB_Planner.scl` | FUNCTION_BLOCK `"Crane_Planner"` | FB11 | SCL | planner |
| `12_planner_*.scl/.db` (optional) | planner self-test blocks, numbers ≥ FC/FB/DB 50 | – | SCL | planner |
| `20_FC_CheckCmd.scl` | FUNCTION `"CheckCmd"` : Int | FC10 | SCL | runtime |
| `21_FB_CraneControl.scl` | FUNCTION_BLOCK `"Crane_Control"` (contains multi-instance `Planner : "Crane_Planner"`) | FB10 | SCL | runtime |
| `22_DB_CraneControl.db` | instance DATA_BLOCK `"Crane_Control_DB"` of FB10 | DB110 | – | runtime |
| `30_OB1_Main.scl` | ORGANIZATION_BLOCK `"Main"` (program cycle) | OB1 | SCL | runtime |
| `31_OB30_Cyclic.scl` | ORGANIZATION_BLOCK `"Cyclic interrupt"` (replaces the given body) | OB30 | SCL | runtime |
| `numbers.txt` | `Name=Kind:Number` lines, e.g. `World=DB:100` | – | – | tooling |

Rules:
- **FB1 is called ONLY in OB30.** MB100..MB103 are written ONLY in OB30. Nothing else writes FB1 tags or DB2.
- **OB30 cycle time = 1000 ms** (spec: once per second). Tooling verifies and enforces this after every import.
- OB1 `"Main"` body is exactly `"Crane_Control_DB"();`. It may also do diagnostics, but **no crane logic**.
- `{ S7_Optimized_Access := 'TRUE' }`, `VERSION : 0.1`, and `NON_RETAIN` on DBs. Syntax templates are in `prototype-tia/src/`.
- OB headers. Copy them exactly from the tooling export of the given OB30 if it differs; otherwise use:
  ```
  ORGANIZATION_BLOCK "Cyclic interrupt"
  { S7_Optimized_Access := 'TRUE' }
  VERSION : 0.1
     VAR_INPUT
        Initial_Call : Bool;
        Event_Count : Int;
     END_VAR
  BEGIN ... END_ORGANIZATION_BLOCK
  ```
  For `"Main"`, `VAR_INPUT Initial_Call : Bool; Remanence : Bool; END_VAR`.
- No timers in planning. OB30 tick counting is the only time base we create.

### 1.1 UDTs (`01_types.udt`)
```
TYPE "typeCmd"
VERSION : 0.1
   STRUCT
      Cmd : USInt;     // 0 none, 1 lift, 2 put down, 3 move to (X,Y,Bay), 10 reset
      X : SInt;        // 0..3   (for lift/put: current crane x)
      Y : SInt;        // 0..11  (for lift/put: current crane y)
      Bay : USInt;     // 0 ship, 1 yard
      Src : USInt;     // origin: 1 AUTO, 2 SEMI, 3 MANUAL, 4 INIT(reset)
      TrIdx : Int;     // plan transfer index (0 = not from plan)
      Phase : USInt;   // 0 move-to-src, 1 lift, 2 move-to-dst, 3 put (only if TrIdx>0)
   END_STRUCT;
END_TYPE

TYPE "typeTransfer"
VERSION : 0.1
   STRUCT
      Kind : USInt;    // 1 unload (Bay0->Bay1), 2 load (Bay1->Bay0)
      Id : UInt;
      ListIdx : Int;   // index into UList (Kind 1) or LList (Kind 2)
      SrcX : SInt; SrcY : SInt; SrcBay : USInt;
      DstX : SInt; DstY : SInt; DstBay : USInt;
      CumT_ds : DInt;  // predicted total time after this transfer, deciseconds, incl. BaseT_ds
      CumM : DInt;     // predicted total manipulations after this transfer, incl. BaseM
   END_STRUCT;
END_TYPE
```

### 1.2 DB100 `"World"` (`02_World.db`). The process image of our logic.
| Member | Type | Init | Writer | Meaning |
|---|---|---|---|---|
| Bay0 | Array[0..3,0..11] of UInt | 0 | FB10 (INIT copy) / OB30 (lift/put effect) | working copy of the ship |
| Bay1 | Array[0..3,0..11] of UInt | 0 | same | working copy of the yard |
| CraneX | SInt | 0 | OB30 | crane x after last completed command (from `"x_position"`) |
| CraneY | SInt | 0 | OB30 | |
| CraneBay | USInt | 1 | OB30 | |
| Carried | UInt | 0 | OB30 | ID on the hook (0 = none) |
| Busy | Bool | FALSE | OB30 | command issued to FB1, not finished yet |
| BusyTicks | Int | 0 | OB30 | OB30 ticks since issue (watchdog) |
| ActCmd | "typeCmd" | – | OB30 | command currently executing |
| NextCmd | "typeCmd" | – | FB10 | staged command (valid when CmdReady) |
| CmdReady | Bool | FALSE | FB10 sets / OB30 clears | handshake, see §3.4 |
| Permit | Bool | FALSE | FB10 | OB30 may issue NextCmd |
| DoneSeq | UDInt | 0 | OB30 | +1 per completed command |
| LastDone | "typeCmd" | – | OB30 | last completed command |
| Fault | Word | 0 | OB30 sets bits / FB10 clears on ACK | OB30-detected alarms (bit = alarm bit, §3.3) |
| FaultCmd | "typeCmd" | – | OB30 | command rejected by CheckCmd |
| UList | Array[1..48] of UInt | 0 | FB10 | copy of DB20 |
| UState | Array[1..48] of USInt | 0 | FB10 | 0 pending, 1 done, 2 skipped (invalid / not found / dup / empty entry) |
| LList | Array[1..48] of UInt | 0 | FB10 | copy of DB21 |
| LState | Array[1..48] of USInt | 0 | FB10 | as UState |
| N | Int | 0 | FB10 | number of **non-zero** entries in DB20 + DB21 (used for J) |
| Plan | Array[1..96] of "typeTransfer" | – | planner | |
| PlanLen | Int | 0 | planner | |
| PlanValid | Bool | FALSE | planner (TRUE on success); FB10 (FALSE on invalidation) | |
| PlanVariant | Int | 0 | planner | winning variant 1..4 |
| PredT_ds | DInt | 0 | planner | predicted final T, deciseconds |
| PredM | DInt | 0 | planner | predicted final M |
| PredJ | Real | 0 | planner | predicted final J |
| BaseT_ds | DInt | 0 | FB10 | ROUND(T·10) at plan request (0 after INIT) |
| BaseM | DInt | 0 | FB10 | M at plan request |
| PlanIdx | Int | 1 | FB10 | transfer being executed (done pointer) |
| Phase | USInt | 0 | FB10 | next phase of PlanIdx to complete |
| StageIdx | Int | 1 | FB10 | staging cursor (transfer) |
| StagePhase | USInt | 0 | FB10 | staging cursor (phase) |
| BalL, BalR | Int | 0 | FB10 | ship count x∈{0,1} / x∈{2,3} |
| BalF, BalA | Int | 0 | FB10 | ship count y∈0..5 / y∈6..11 (info, used if CfgBalMode=1) |
| CfgOrderMode | USInt | 0 | FB10 (copied from HMI_IF when not running) | §4.6 |
| CfgBalLimit | Int | 5 | const | |
| CfgBalMode | USInt | 0 | FB10 (from HMI_IF) | 0 x-halves only, 1 also y-halves |
| CfgMMode | USInt | **0** (v1.7; was 2) | const (0 = spec rule, diagonal = 2; 2 = FB1 +1 per move command, still selectable) | §4.1 |
| CfgVariants | Int | 4 | const | 1..4 |
| CfgAlpha | Array[1..4] of Int | [0, 75, 125, 200] (v1.7, tuned for CfgMMode 0; v1.3 mode 2: [0, 100, 200, 300]) | const | lookahead weight (%) per variant |
| CfgStepsPerCall | Int | 1 | const | planner greedy steps per OB1 call |
| CfgTimeoutTicks | Int | 10 | const | FB1 watchdog (OB30 ticks) |
| OB30Ticks | UDInt | 0 | OB30 | |

"const" means the start value in the DB file. Changing a start value is a data change, not a contract change, but announce it in TEAM_NOTES.md.

### 1.3 DB101 `"HMI_IF"` (`03_HMI_IF.db`). The only DB the HMI touches.
**Buttons** (HMI: event *Press* → `SetBit`; FB10 resets the bit after evaluating it, in the same cycle):

| Member | Type | Meaning |
|---|---|---|
| SwOn | Bool | main switch level (HMI: `InvertBit`). TRUE = ON |
| BtnInit | Bool | INITIAL STATE (POČETNO STANJE) |
| BtnAuto / BtnSemi / BtnManual | Bool | mode select |
| BtnStart / BtnStop / BtnAck | Bool | |
| BtnStep | Bool | SEMI: run the next manipulation |
| BtnManExec | Bool | MANUAL: execute ManCmd |
| ManCmd | USInt | 1 lift, 2 put down, 3 move, 10 reset |
| ManX | SInt | 0..3 |
| ManY | SInt | 0..11 |
| ManBay | USInt | 0/1 |
| CfgOrderMode | USInt (init 0) | 0 free, 1 per-list order, 2 strict (§4.6) |
| CfgSemiPerTransfer | Bool (init FALSE) | SEMI click = one command (FALSE) or one whole transfer (TRUE) |
| CfgBalMode | USInt (init 0) | |

**Indicators** (written by FB10 every OB1 cycle):

| Member | Type | Meaning |
|---|---|---|
| State | USInt | §3.1 code |
| Mode | USInt | 1 AUTO, 2 SEMI, 3 MANUAL |
| LampOn, LampOff, LampReady | Bool | LampReady = SwOn ∧ Initialized ∧ State∈{READY,RUNNING,PAUSED,DONE} ∧ no blocking alarm |
| LampAuto, LampSemi, LampManual | Bool | |
| LampRunning, LampAlarm, LampDone | Bool | |
| Initialized, CraneBusy, Planning, StepWaiting | Bool | StepWaiting: SEMI is waiting for a click |
| M | UDInt | **v1.7:** = `World.MSpec` (spec M rule, diagonal = 2; primary) |
| T | Real | = MD112 working time [s] |
| J | Real | 0.5·T/(76·N) + 0.5·M/(4·N) with the spec M (v1.7); 0 if N = 0 |
| MFb1 | UDInt | **v1.7:** = `"number_of_manipulations"` (FB1 MD107, +1 per command; secondary) |
| JFb1 | Real | **v1.7:** J with MFb1 |
| MSpec, JSpec | UDInt, Real | v1.2 members; since v1.7 copies of M / J |
| N | Int | |
| PredM | DInt | |
| PredT | Real | PredT_ds / 10 |
| PredJ | Real | |
| PlanVariant | Int | |
| TrDone, TrTotal | Int | transfers done / total in current plan + done before |
| UDone, UTotal, LDone, LTotal | Int | list progress (valid entries only) |
| CraneX, CraneY | SInt | |
| CraneBay | USInt | |
| CraneGX | Int | global column: x + 6 if bay 0, else x (0..9); for the crane-marker movement animation |
| Carried | UInt | |
| CurCmd | USInt | command executing (or last staged) |
| CurX, CurY | SInt | |
| CurBay | USInt | |
| CurId | UInt | container of current transfer |
| CurKind | USInt | 1 unload, 2 load, 0 none |
| CurPhase | USInt | |
| Cell0, Cell1 | Array[0..47] of UInt | IDs, **index i = x·12 + y** (Bay0 / Bay1) |
| CellSt0, CellSt1 | Array[0..47] of USInt | colour code, see below |
| UList, LList | Array[1..48] of UInt | |
| UState, LState | Array[1..48] of USInt | 0 pending, 1 done, 2 skipped, 3 in progress |
| BalL, BalR, BalDiff | Int | BalDiff = BalL − BalR |
| BalF, BalA | Int | |
| BalOk | Bool | \|BalDiff\| ≤ 5 |
| AlarmWord | Word | §3.3. HMI discrete alarms trigger on these bits |
| AlarmId | UInt | container ID related to the newest alarm (0 if none) |
| AlarmX, AlarmY | SInt | location related to the newest alarm |
| AlarmBay | USInt | |
| AlarmHist | Array[0..15] of Int | alarm-bit numbers of the last 16 raise events, [0] newest |
| AlarmHistSeq | UDInt | |
| OB30Ticks | UDInt | |
| Heartbeat | Bool | toggles each OB30 tick |

**CellSt codes:**
- 0 empty
- 1 occupied (not in a pending list entry)
- 2 pending unload (in Bay0, in UList, pending)
- 3 pending load (in Bay1, in LList, pending)
- 4 transferred (a list container at its new place)
- 5 source of current transfer
- 6 destination of current transfer (empty)
- 7 invalid ID (outside 100..999, treated as an occupied obstacle)

### 1.4 Instance/FB interfaces
- **FB10 `"Crane_Control"`**: no parameters. It reads DB10/DB11/DB20/DB21, `"World"`, `"HMI_IF"` and the FB1 tags (read-only), and writes `"World"` (its members) and `"HMI_IF"`. Statics are runtime-private, except the multi-instance `Planner : "Crane_Planner";`.
- **FB11 `"Crane_Planner"`** (planner owns the body; the interface is fixed):
  ```
  VAR_INPUT  Req : Bool;  END_VAR                  // rising edge starts a job from the current "World" snapshot
  VAR_OUTPUT Busy : Bool; Done : Bool; Error : Bool; ErrCode : Int; END_VAR
  // Done/Error stay TRUE while Req stays TRUE; Req=FALSE clears them. Busy during job.
  // ErrCode: 0 ok, 1 no feasible transfer (deadlock/balance/capacity), 2 plan > 96 transfers, 3 bad config/input, 4 crane carrying (World.Carried<>0)
  ```
  - **Reads:** World.Bay0, Bay1, CraneX/Y/Bay, Carried, UList/UState, LList/LState, N, BaseT_ds, BaseM, Cfg*.
  - **Writes, only when the job finishes:** World.Plan, PlanLen, PlanValid, PlanVariant, PredT_ds, PredM, PredJ. On error: PlanValid := FALSE, PlanLen := 0.
  - Must snapshot inputs at the rising edge, and run CfgStepsPerCall greedy steps per call. **Budget: ≤ 20 ms per call on a 1515** (no cycle-time overflow), total job ≤ 500 calls.
- **FC20 `"Crane_MoveCost"` : DInt**. Returns T_ds of a move.
  ```
  VAR_INPUT X0 : Int; Y0 : Int; B0 : Int; X1 : Int; Y1 : Int; B1 : Int; MMode : Int; END_VAR
  VAR_OUTPUT M : Int; END_VAR
  ```
  Formula is in §4.1. The runtime may also use it.
- **FC10 `"CheckCmd"` : Int**. Returns 0 OK, else an alarm bit (§3.3). Reads `"World"` grids.
  ```
  VAR_INPUT C : "typeCmd"; CraneX : SInt; CraneY : SInt; CraneBay : USInt; Carried : UInt; BalLimit : Int; BalMode : USInt; END_VAR
  ```
  | Cmd | Rules (first failing rule decides the return code) |
  |---|---|
  | 3 move | X∈0..3, Y∈0..11, Bay∈{0,1}, else **9** |
  | 1 lift | Carried=0, else **11**; cell(crane pos) ≠ 0, else **1**; if Bay=0, ship balance after removal OK (§4.3 step rule), else **0** |
  | 2 put | Carried≠0, else **12**; cell(crane pos) = 0, else **2**; if Bay=0, balance after placement OK, else **0** |
  | 10 | always OK |
  | anything else | **9** |

  Return value convention: since 0 = OK, imbalance returns **100** (it means alarm bit 0). Every other failure returns its bit number. OB30 maps code 100 → bit 0.

---

## 2. FB1 `"Crane_manipulation"` (DB2): known vs UNKNOWN

**Known** (spec p. 8 + archive):
- Inputs: `new_x_position : SInt`, `new_y_position : SInt`, `new_bay_ID : USInt`.
- InOut: `command_id : USInt`. Values: 0 nothing, 1 lift, 2 put down, 3 move to (X,Y,Bay), 10 reset to x=0, y=0, Bay=1, M=0, T=0.
- **FB1 sets command_id := 0 when the command has finished.**
- Outputs: `pos_x_after_command : SInt`, `pos_y_after_command : SInt`, `bay_ID_after_command : USInt`, `number_of_manipulations : UDInt`, `working_time : Real`.
- Statics: `current_x_position_in_bay`, `current_y_position_in_bay`, `current_bay_ID`, `total_number_of_manipulations`, `total_time`.
- Temps: `difference_in_x_position`, `difference_in_y_position` (Real), `x_position_recalibratin_of_the_current_position`, `x_position_recalibratin_of_the_new_position` (SInt), `time_needed_for_move_command_in_s` (Real). The x is "recalibrated" to a global column.
- **FB1 does NOT know the container contents.** We track Bay0/Bay1/Carried ourselves.
- Spec scoring rule: an x change = 1 M, a y change = 1 M (x+y = 2), lift = 1, put = 1. Move time = max(|ΔX|·6, |Δy|·2.3) s with Bay0 X = x+6, Bay1 X = x. Lift and put are 20 s each.

**UNKNOWN until the tooling worker exports and reads FB1** (answers go to TEAM_NOTES.md "FB1 findings", one line each):
- U1. Does a command complete within ONE call (command_id → 0 in the same call), or over several calls?
- U2. How is M counted for a move: per changed axis (spec), or +1 per command?
- U3. Does a bay change with the same local x count as an x change? The recalibrated x suggests yes.
- U4. Is the move time exactly max(|ΔX|·6, |Δy|·2.3)? Is it read from DB1 or hard-coded?
- U5. Do lift/put add 20 s + 1 M regardless of inputs? Do they use x/y/bay inputs?
- U6. Does a move to the current position add M or time?
- U7. Does FB1 reject bay ≠ 0/1, x>3, y>11, or does it execute them? Does it handle bay 2?
- U8. Reset (10): confirm the effect and that it completes in one call.
- U9. What do the given OB30 and OB100 contain (FB1 call wiring)? What is OB30's cycle time?
- U10. Exact tag table name and the exact name of the MD112 tag.
- U11. Is any given block know-how protected?
- U12. Does the HMI device already have a connection to the PLC, and are there screens?

**ANSWERED (v1.1):** U1 one call; command_id := 0 every call. U2 +1 per move command. U3 bay change uses global column (Bay0 x+6). U4 max(|ΔG|·6.0, |Δy|·2.3)/1.0 from DB1, REAL (float error ~1e-6 per move). U5 lift/put +20 s +1 M, no inputs read, no checks. U6 zero-distance move: +1 M, 0 s. U7 no range checks (bay ≠ 0/1 gives garbage time). U8 reset → (0,0,1), M=0, T=0, one call. U9 OB30 LAD, FB1 only, 1000 ms; OB100 resets DB2 statics and tags. U10 see §0. U11 only FB1/DB2 know-how protected. U12 HMI has no PLC connection, one empty screen.

(v1.0 text:) Until the answers are in, everyone uses the defaults: one-call completion, the spec M rule with global X (CfgMMode 0), and the spec time formula. **The code must not depend on U1:** the OB30 handshake works for multi-call commands too.

---

## 3. Behaviour

### 3.1 States (`HMI_IF.State`)
| Code | State | Entered when | Leaves when |
|---|---|---|---|
| 0 | OFF | SwOn = FALSE (from any state; an in-flight FB1 command still completes) | SwOn = TRUE: if not Initialized → INIT, else → PAUSED (or DONE) |
| 1 | INIT | BtnInit (if SwOn and not Busy; v1.5: ignored in RUNNING / PLANNING), or first ON after PLC start | sequence §3.2 done → READY; failure → ALARM |
| 2 | READY | INIT ok | START (AUTO/SEMI) → RUNNING (via PLANNING if plan invalid) |
| 3 | RUNNING | START | STOP → PAUSED; blocking alarm → ALARM; plan finished → DONE |
| 4 | PAUSED | STOP, mode change to MANUAL, ON after OFF | START → RUNNING (via PLANNING if plan invalid) |
| 5 | ALARM | a blocking alarm is raised | ACK and the cause is gone → back to the previous state (RUNNING if it was running: "nakon potvrde sustav nastavlja s radom"), via PLANNING if the plan was invalidated |
| 6 | DONE | all transfers of the plan completed | BtnInit, or MANUAL commands |
| 7 | PLANNING | START with PlanValid = FALSE, or after an ACK that invalidated the plan | planner Done → RUNNING; planner Error → ALARM (bit 8) |

**Modes** (`HMI_IF.Mode`; default AUTO at PLC start):
- Mode buttons are accepted when not Busy (a pending press waits until the command completes).
- Switching to MANUAL while RUNNING → PAUSED.
- AUTO ↔ SEMI switch while RUNNING keeps running.
- **AUTO:** while RUNNING, the plan is staged continuously, at one command per OB30 tick.
- **SEMI:** while RUNNING, each BtnStep allows exactly one crane command, or one whole transfer if CfgSemiPerTransfer. StepWaiting = TRUE while waiting.
- **MANUAL:** BtnManExec stages `{ManCmd, ManX, ManY, ManBay, Src=3}` if SwOn ∧ Initialized ∧ not Busy ∧ no blocking alarm. It runs in any state except OFF/INIT/PLANNING and does not need START.
  - For lift/put, the X/Y/Bay fields are replaced by the crane position.
  - Any completed manual command sets PlanValid := FALSE (replan on the next START).
- **START in AUTO/SEMI with World.Carried ≠ 0** → alarm 11 ("crane is carrying, put it down in MANUAL"). It does not start.
- **STOP:** Permit := FALSE immediately. The command already in FB1 completes, and a staged-but-not-issued command is withdrawn (CmdReady := FALSE). START resumes from PlanIdx/Phase: the stage cursor is reset to the done pointer.
- **OFF:** same as STOP, plus state OFF and lamps.

### 3.2 INIT sequence (FB10, state 1)
1. Permit := FALSE, CmdReady := FALSE. Clear AlarmWord and World.Fault. Wait until NOT Busy.
2. Stage `NextCmd := {Cmd 10, Src 4}`, CmdReady := TRUE, Permit := TRUE. Wait for DoneSeq to increment with LastDone.Cmd = 10. Then Permit := FALSE.
3. Copy DB10.Bay0 → World.Bay0 and DB11.Bay1 → World.Bay1. Carried := 0. Crane := FB1 outputs, expected (0,0,1).
4. **Validate** and set alarms (all are *warnings*: latched, shown, cleared by ACK; they do not block):
   - Every cell ID ∉ {0} ∪ [100..999] → bit 5. The cell stays an occupied obstacle.
   - The same ID in two cells (either bay) → bit 6.
   - Lists: copy DB20 → UList and DB21 → LList. N := count of non-zero entries in both raw lists. For each entry in index order:
     - 0 → state 2 (empty entry, silent)
     - ID ∉ [100..999] → 2, bit 5
     - already seen in either list in an earlier entry with state 0 (accepted) → 2, bit 6 (v1.5: a rejected earlier entry does not count)
     - unload ID not found in Bay0 → 2, bit 3 ("ID kontejnera postoji u listi za istovar, ali ne postoji u polju Bay 0"); AlarmId := ID
     - load ID not found in Bay1 → 2, bit 4
     - else 0 (pending)
   - **Capacity:** occupied(Bay1) − pendingLoads + pendingUnloads > 48, or the same for Bay0 → bit 7 (**blocking**).
   - |BalL − BalR| > 5 initially → bit 0 (warning at INIT; the planner then works in non-worsening mode).
5. BaseT_ds := 0, BaseM := 0. Request the planner (Req edge) and wait. Done → PlanIdx := StageIdx := 1, Phase := StagePhase := 0. Error → bit 8 (blocking).
6. Initialized := TRUE → READY.

### 3.3 Alarms (`HMI_IF.AlarmWord` bits)
**Blocking** alarms set Permit := FALSE and state ALARM. **Warnings** only display. All are latched: ACK clears the bits whose cause is gone. Bit 0 re-raises while |L−R| > 5. Every raise pushes the bit number into AlarmHist and sets AlarmId/X/Y/Bay when known.

| Bit | Class | Text (HR / EN) | Raised by |
|---|---|---|---|
| 0 | blocking (if raised by CheckCmd or during RUNNING), warning (at INIT) | Neuravnoteženost broda: razlika lijeve i desne polovice > 5 / Ship imbalance \|L−R\| > 5 | FB10 continuous, CheckCmd |
| 1 | blocking | Lokacija s koje se podiže kontejner je prazna / Pick location empty | CheckCmd (OB30) |
| 2 | blocking | Lokacija na koju se spušta kontejner je zauzeta / Drop location occupied | CheckCmd (OB30) |
| 3 | warning | ID kontejnera postoji u listi za istovar, ali ne postoji u polju Bay 0 / Unload ID not in Bay 0 | INIT |
| 4 | warning | ID kontejnera postoji u listi za ukrcaj, ali ne postoji u polju Bay 1 / Load ID not in Bay 1 | INIT |
| 5 | warning | Neispravan ID kontejnera (izvan 100–999) / Invalid container ID | INIT |
| 6 | warning | Dvostruki ID kontejnera / Duplicate container ID | INIT |
| 7 | blocking | Nema slobodnog mjesta u odredišnom polju / No free slot | INIT capacity |
| 8 | blocking | Plan istovara/ukrcaja nije izvediv / Plan infeasible | planner Error |
| 9 | warning (command is dropped) | Neispravna ručna naredba (Bay mora biti 0/1, x 0–3, y 0–11) / Invalid manual command | FB10 pre-check of manual input + CheckCmd |
| 10 | blocking | Dizalica nije izvršila naredbu (timeout) / FB1 timeout | OB30 watchdog: Busy ∧ BusyTicks > CfgTimeoutTicks |
| 11 | blocking | Dizalica već nosi kontejner / Crane already carrying | CheckCmd, START with load |
| 12 | blocking | Dizalica ne nosi kontejner / Crane is empty (put down) | CheckCmd |
| 13 | warning | Sustav nije inicijaliziran: pritisnite POČETNO STANJE / Not initialized | START/manual without INIT |
| 14 | warning | Položaj dizalice ne odgovara naredbi / Crane position mismatch after move | OB30: FB1 out ≠ ActCmd after move |
| 15 | info | Istovar i ukrcaj završeni / Unloading and loading finished | DONE |

- When CheckCmd fails in OB30, OB30 sets World.Fault bit, FaultCmd := NextCmd and CmdReady := FALSE, and **does not issue**.
- FB10 ORs World.Fault into AlarmWord.
- **ACK** clears World.Fault and the latched bits. In AUTO/SEMI it then sets PlanValid := FALSE (replan from the actual World), so the system continues.
- v1.4: ACK of bit 0 or bit 2 for a rejected plan put with a container on the hook re-targets the put to the nearest free cell of the same bay that passes the step rule, then replans after that put. If there is no such cell: bit 7 and state PAUSED (MANUAL needed), never an automatic retry of the same put. v1.5: that bit 7 is not blocking (NoCellWarn), so the state stays PAUSED and MANUAL works after one ACK. v1.6: for a ship put the cell must also keep the remaining lists feasible in the preferred order (FtMask[0,0] after the put, step rule then relaxed BalD0), if any free balance-safe cell does.
- v1.4: `HMI_IF.AlarmWord2` bit 0 (warning, HMI alarm ID 17, not in AlarmHist): the plan uses a weaker order/balance mode than the HMI setting because the preferred one is provably infeasible (§4.10). `HMI_IF.AlarmUId/AlarmUCnt`, `AlarmLId/AlarmLCnt`: first list ID missing from its bay and the count (bits 3/4).

### 3.5 DB10 / DB11 = live state (v1.4)
- After INIT, FB10 region 2a compares every cell of `"Current_state_of_Bay0/1"` with its snapshot Snap0/Snap1: a DB cell that differs is an external online edit → adopted into World (as before; v1.5: in every state it also sets ExtEdit, and with an empty hook outside RUNNING/PLANNING PlanValid := FALSE). Otherwise a World cell that differs from Snap (the crane moved a container) is written into the DB cell. So DB10/DB11 always show the current yard (≤ 1 OB1 cycle behind OB30).
- INIT step 3 (v1.6, see the v1.6 change list for the exact rule): if there is no private copy yet, a cell was edited while no job was in progress (NewCnt > 0), DB20/DB21 changed and a cell was edited during the job (ObstCnt > 0), ≥ 8 cells were edited during the job, or any DB cell differs from Snap, DB10/DB11 are copied into InitBay0/InitBay1 (new initial data). Otherwise DB10/DB11 are restored from InitBay0/InitBay1, so POČETNO STANJE after a finished run starts the same data set again. Then World := DB10/DB11 as before.

### 3.4 OB30 algorithm (runtime). Exactly this order, every 1 s tick
```
1  OB30Ticks += 1; HMI heartbeat
2  IF World.Busy THEN                                  // "check whether the previous manipulation is done"
     IF "new_command_ID" = 0 THEN                       // FB1 finished
        CraneX/Y/Bay := "x_position"/"y_position"/"bay_ID"
        CASE ActCmd.Cmd: 1 → Carried := cell(ActCmd pos); cell := 0
                         2 → cell(ActCmd pos) := Carried; Carried := 0
                         3 → IF crane ≠ (ActCmd.X,Y,Bay) THEN Fault bit 14
        LastDone := ActCmd; DoneSeq += 1; Busy := FALSE; BusyTicks := 0
     ELSE BusyTicks += 1; IF BusyTicks > CfgTimeoutTicks THEN Fault bit 10
3  IF NOT Busy AND CmdReady AND Permit AND Fault = 0 THEN   // issue only after the previous one finished
     rc := "CheckCmd"(NextCmd, crane, Carried, CfgBalLimit, CfgBalMode)
     IF rc = 0 THEN "new_x_position" := NextCmd.X; "new_y_position" := NextCmd.Y;
                    "new_bay_ID" := NextCmd.Bay; "new_command_ID" := NextCmd.Cmd;
                    ActCmd := NextCmd; Busy := TRUE; BusyTicks := 0
     ELSE Fault bit (rc, 100→0); FaultCmd := NextCmd
     CmdReady := FALSE
4  "Crane_manipulation_DB"(new_x_position := "new_x_position", new_y_position := "new_y_position",
       new_bay_ID := "new_bay_ID", command_id := "new_command_ID",
       pos_x_after_command => "x_position", pos_y_after_command => "y_position",
       bay_ID_after_command => "bay_ID", number_of_manipulations => "number_of_manipulations",
       working_time => <MD112 tag>);              // called EVERY tick (cmd 0 = no-op)
```
Use the given OB30's original call wiring if it differs (U9).

**Handshake (OB30 preempts OB1):**
- FB10 writes NextCmd only while CmdReady = FALSE, and sets CmdReady := TRUE **last**.
- OB30 is the only one that sets CmdReady := FALSE, except FB10 withdrawing on STOP/OFF/ACK/INIT, which it does after first setting Permit := FALSE.
- **Staging ahead:** FB10 may stage the next plan command while Busy is TRUE. OB30 then issues it in the same tick that it detects completion, which gives ≈1 command/s.
- The staging cursor (StageIdx/StagePhase) advances when FB10 stages. The done pointer (PlanIdx/Phase) advances when FB10 sees DoneSeq increase with LastDone.TrIdx = PlanIdx ∧ LastDone.Phase = Phase. After phase 3, PlanIdx += 1 and Phase := 0.
- **Skip rule:** phase 0 (move to src) is skipped (not staged) when the predicted crane position equals Src. The predicted position is the Dst of transfer StageIdx−1, or the crane position at plan time for StageIdx = 1. The planner uses the identical rule (E = 0).
- For lift/put, NextCmd.X/Y/Bay = the transfer's Src (lift) or Dst (put). That equals the crane position at execution time.
- After any completed PUT, FB10 refreshes the list states:
  - unload entry pending → done when its ID is now in Bay1
  - load entry pending → done when its ID is now in Bay0
  - (MANUAL may also re-pend an entry: done unload found back in Bay0 → pending.)
- **DONE:** PlanIdx > PlanLen with no pending entries → DONE + bit 15. If entries are still pending when the plan is exhausted, set PlanValid := FALSE and replan.

---

## 4. Planning algorithm (Python `tools/crane_plan.py` and SCL `"Crane_Planner"` MUST be bit-identical)

Everything is **integer** (DInt), in deciseconds (ds). No floats in decisions.

### 4.1 Cost model
- Global column: G(x, b) = x + 6 if b = 0, else x.
- **Move** (x0,y0,b0) → (x1,y1,b1). If all equal: T = 0, M = 0. Else dG = |G1−G0|, dy = |y1−y0|, and **T = max(60·dG, 23·dy)**. M depends on CfgMMode:
  - 0 = spec/global: M = [dG ≠ 0] + [dy ≠ 0]
  - 1 = local x: M = [x1 ≠ x0] + [dy ≠ 0]
  - 2 = per command: M = 1
- **Lift:** T = 200, M = 1. **Put:** T = 200, M = 1.
- **Weighted cost:** W = T + 190·M. Since J = (T_s + 19·M)/(152·N), 1 M ≡ 19 s ≡ 190 ds.
- **v1.7: CfgMMode default = 0 (spec rule, team decision).** The spec text p. 10 (a simultaneous x+y change = 2 manipulations) is what we optimise and show as the primary M (`World.MSpec`, counted by OB30 exactly by the mode-0 rule: +1 lift, +1 put, a move +[dG ≠ 0] +[dy ≠ 0] with G the global column, so a bay change counts as an x change; a zero-distance move counts 0; reset (cmd 10, also at POČETNO STANJE) clears it). FB1 (given, know-how protected, unchanged) still counts +1 per command in MD107; that count is shown as the secondary `HMI_IF.MFb1/JFb1`. Mode 2 stays selectable (it reproduces MD107 exactly). FB10 sets `BaseM` for a replan from `World.MSpec` in mode 0 and from MD107 otherwise. The planner cost for an all-equal move stays T=0, M=0, because such a move is never issued (skip rule); the real FB1 would charge +1 M.

### 4.2 Planner state
- Grids G0, G1. Crane (cx, cy, cb). Carried must be 0 (else ErrCode 4).
- Pending unloads PU = { i | UState[i] = 0 }, ordered by i. Each unload is located by scanning Bay0, x 0..3 outer, y 0..11 inner, first match. Pending loads PL = { j | LState[j] = 0 }, located in Bay1 the same way.
- Totals T := BaseT_ds, M := BaseM.

### 4.3 Balance
- L = #occupied Bay0 cells with x ≤ 1; R = #with x ≥ 2. Optionally (CfgBalMode 1) also F = #y ≤ 5 and A = #y ≥ 6. Lim = CfgBalLimit.
- **Step rule** for a resulting state (L', R'): OK iff |L'−R'| ≤ Lim **or** |L'−R'| ≤ |L−R|, i.e. never worsen an already-bad state. With CfgBalMode 1, the same rule must also hold for (F', A').
- **v1.5 relaxed rule** (x-split only, only while World.BalCeil = C > Lim): additionally OK iff |L−R| > Lim **and** |L'−R'| ≤ C. Memoryless: once |L−R| ≤ Lim the ship stays balanced; before that it never exceeds C = the imbalance of the loaded data. Terminal states must have |L−R| ≤ Lim (FtMask[nu, nl], FaMask[n], SLOT trajectory end). Python `cm.step_ok(..., ceil)`, `cfg["ceil"]`.
  - An unload changes the ship at the lift. A load changes the ship at the put. The hook container counts as off-ship.
- **Reachability** (x-split only), evaluated on the state after the candidate:
  - u_L, u_R = pending unloads (excluding the candidate) in Bay0 with x ≤ 1 / x ≥ 2. n = pending loads excluding the candidate.
  - L0 = L' − u_L, R0 = R' − u_R. FL = 24 − L0, FR = 24 − R0.
  - lo = max(0, n − FR), hi = min(n, FL), D0 = L0 − R0 − n.
  - Reachable iff lo ≤ hi ∧ D0 + 2·lo ≤ Lim ∧ D0 + 2·hi ≥ −Lim.

### 4.4 One greedy step (variant with weight α = CfgAlpha[v])
1. **Eligible sources ES** (order matters):
   - OrderMode 0: all PU in index order, then all PL in index order.
   - OrderMode 1: first pending of PU (if any), then first pending of PL (if any).
   - OrderMode 2: first pending of PU if PU ≠ ∅, else first pending of PL.
2. For each s in ES (in order):
   - Position (sx, sy, sb); destination bay db = 1 − sb.
   - E = W(crane → s), which is 0 if the crane is already there.
   - For each free cell d in bay db, scanning dx 0..3 outer, dy 0..11 inner:
     - Compute (L', R') after the transfer and apply the step rule and reachability. **Pass A** requires both; **Pass B** (used only if Pass A found no candidate in the whole step) requires the step rule only.
     - Lm = W(s → d).
     - Nx = min over s' ∈ ES' of W(d → pos(s')), where ES' is the eligible set of the next step computed with s removed (OrderMode rules on the reduced sets). Positions are unchanged except s. Nx = 0 if ES' = ∅.
     - **Score = 100·(E + Lm) + α·Nx** (DInt).
     - Keep it if Score < BestScore (strict, so the first in scan order wins ties).
3. No candidate in Pass A or Pass B → ErrCode 1.
4. **Apply the best (s, d):**
   - Move the ID from the source cell to d.
   - Append a transfer {Kind, Id, ListIdx, Src, Dst}.
   - T += E_T + 200 + Lm_T + 200 and M += E_M + 1 + Lm_M + 1, where E_T and E_M are 0 when the crane is already at s.
   - Store CumT_ds := T and CumM := M. Crane := d. Remove s from PU/PL.
5. Repeat until PU = PL = ∅. More than 96 transfers → ErrCode 2.

### 4.5 Variants (multi-start)
- Run v = 1..CfgVariants with α = CfgAlpha[v].
- Score each completed variant with K_v = (T − BaseT_ds) + 190·(M − BaseM).
- **Winner:** the smallest K_v; ties go to the lower v. Failed variants are skipped; all failed → Error with the ErrCode of variant 1.
- Results: PlanVariant := v; PredT_ds := T; PredM := M; PredJ := 0.5·(PredT_ds/10)/(76·N) + 0.5·PredM/(4·N) (Real, N = World.N, 0 if N = 0).

### 4.6 Order modes and other hedges (organizer questions open)
- CfgOrderMode is selectable on the HMI. Default 0 (free order, interleaving allowed: best J).
  - Mode 1: each list in its own order, interleaved.
  - Mode 2: the unload list completely in order, then the load list in order.
- Switch the default if the organizers answer that the order is mandatory.
- **CfgBalMode 1** additionally keeps bow/stern (y-halves) balanced, as insurance if the jury reads "halves" differently.

### 4.7 Parity output format (Python prints, harness reads from PLC)
```
i,kind,id,list_idx,src_bay,src_x,src_y,dst_bay,dst_x,dst_y,cum_t_ds,cum_m
1,1,111,1,0,2,5,1,3,5,1214,4
...
RESULT variant=2 T_ds=... M=... J=0.9876 N=...
```

### 4.8 IMPROVE phase (v1.3)
Runs inside the same FB11 job after the last variant, only if a variant succeeded, `CfgImproveEvals > 0`, `CfgOrderMode ≠ 2` and the plan has ≥ 2 transfers. `World` is still written only once, when the job finishes.
- **Sources** are numbered 1..n as in §4.2 (pending unloads by list index, then pending loads). **Incumbent** = sequence `LsSeq[1..n]` with, per step k, the destination and the cumulative T/M (`LsT[0]`/`LsM[0]` = Base). It starts as the greedy winner itself (its own destinations), K_inc = K of the winner.
- **Neighbourhood**, in exactly this order: move 0 once (re-slot the incumbent, p = 1); then sweeps of move 1 (relocate the element at i to position j, i, j ∈ 1..n, j ≠ i), move 2 (swap i < j), move 3 (relocate the pair (i, i+1) to start at j, i, j ∈ 1..n−1, j ≠ i); i outer, j inner; skip if `CfgImproveDist > 0` and |i−j| > CfgImproveDist. Order mode 1: a move is valid only if no moved element passes an element of its own list. p = min(i, j).
- **Replay** of a candidate from k0 = max(1, p−1): grid = snapshot + incumbent transfers 1..k0−1, crane = incumbent destination k0−1 (or the plan-time crane), T/M = incumbent cumulative at k0−1. For each step k = k0..n with source s and successor nx (none at k = n): E as in §4.4 (skipped if the crane is at s); destination d = free cell of the other bay (x 0..3 outer, y 0..11 inner) minimising **W(s→d) + W(d→nx)** (strict '<'), Pass A = step rule (+ bow/stern if CfgBalMode 1) + reachability over the remaining sequence, Pass B = step rule only; none → reject. T += 400 + Lm_T, M += 2 + Lm_M. **Abort** (reject) as soon as K_partial + 960·(n−k) ≥ K_inc (960 = 400 + 180 + 2·190 is a lower bound of every remaining transfer).
- **v1.5, order mode 1, move 1 = pattern-token relocate:** let P be the U/L kind pattern of the incumbent; P' = P with the token at i moved to position j; candidate position q gets the next not yet used element of kind P'[q] (in incumbent order). Valid iff some element strictly between i and j (inclusive of j) is of the other kind. p = first q with candidate ≠ incumbent. It contains the old order-1 move 1 and also shifts whole blocks.
- **Accept** iff the replay completes (then K < K_inc). Every replay counts one evaluation. Stop at `CfgImproveEvals` evaluations or after a sweep (moves 1..3) with no acceptance. The incumbent becomes the plan (CumT/CumM from the replay).
- Per call: ≤ `CfgImprovePerCall` evaluations and ≤ 3000 iterator positions. The result does not depend on the split.

### 4.10 Exact order feasibility (v1.4)
Replaces the reachability test of §4.3 in **Pass A** wherever the remaining order is fixed. Python reference `crane_plan.feas_table()` / `seq_feas()`.
- **Greedy, CfgOrderMode 1/2** (`FtMask`, built at the start of the job, one row per OB1 call): sources 1..nu = pending unloads (list order), nu+1..nSrc = pending loads. `FtMask[i, j]` bit L (L = 0..24) is set iff from "i unloads done, j loads done, L containers in x 0..1" (R = S0 − i + j − L, S0 = ship count at plan time, 0 ≤ R ≤ 24) every remaining transfer can still be executed: the next unload (side fixed by its source x) needs yard count Y0 + i − j < 48, L'/R' ≥ 0, the step rule and bit L' of FtMask[i+1, j]; the next load (order 1 always, order 2 only when i = nu) may go to either half if the half has < 24 containers, step rule and bit L' of FtMask[i, j+1]. FtMask[nu, nl] = all valid L. Pass A accepts a candidate iff L' ∈ FtMask[i', j'] of the post-step state. CfgOrderMode 0 keeps the §4.3 reachability.
- `OrderOk` = L0 ∈ FtMask[0, 0] (published as `World.OrderFeasible`). Exact (balance mode 0): if it is set, Pass A never runs empty, so the preferred order only fails when it is provably infeasible.
- **IMPROVE replay** (every order mode, §4.8): before the replay of steps k0..n, `FaMask[k]` (mask over L after step k) is computed backwards for the fixed candidate sequence with the same rules (yard count and ship count follow the sequence). If L(k0−1) ∉ FaMask[k0−1] the candidate is rejected without a replay (still one evaluation). Pass A of step k = L' ∈ FaMask[k].

### 4.11 SLOT phase (v1.4)
After IMPROVE (or directly after the variants if IMPROVE does not run), when `CfgSlotSweeps > 0` and n ≥ 1. The sequence stays fixed; only destinations change. Python reference `crane_plan.slot_search()`; SCL branches SlStart / SlActive / FinStart; mirror `13_improve_mirror.py`.
- Avail[cell] = 1 if empty at plan time, k+1 if it is the source cell of step k, never otherwise; Used[cell] = step whose drop uses it.
- Cost of cell d for step k: c_k(d) = W(s_k → d) + W(d → s_k+1) (second term 0 at k = n), FC21 `"Crane_DropCost"`. K = const + Σ c_k(d_k), so changes are evaluated in O(1).
- Sweep: k = 1..n (one k per OB1 call): (a) relocate Dst[k] to every cell of its bay (x 0..3 outer, y 0..11 inner) with Used = 0 and Avail ≤ k; (b) swap Dst[k] ↔ Dst[q], q = k+1..n, same bay, Avail[Dst[q]] ≤ k. First improvement, strict '<'. If a load changes ship half (or bow/stern half with CfgBalMode 1), the step rule is re-checked over the whole sequence; failure → revert.
- Stop after a sweep without improvement or after CfgSlotSweeps sweeps. Then CumT/CumM are recomputed along the sequence and the plan is published (never worse than before).

### 4.9 Lower bound (v1.3)
For the pending sources at the Req edge (u unloads, l loads, P = u + l, crane at global column cG):
- X = 2·Σ x(unloads) + 2·Σ (3 − x(loads)) + 3P + 3S + F, minimised over the kind of the first transfer: S = (u − l if u > l else max(0, l − u − 1)) if a load is first, (max(0, u − l − 1) if u ≥ l else l − u) if an unload is first; F = min over sources s of that kind of 3 + |cG − G(s)| − v(s), v = x + 3 (unload) / 6 − x (load).
- T_LB = 400·P + 60·X_min [ds]; M_LB = 4P − [a pending source is at the crane position]. Valid for every order mode, balance rule and CfgMMode (it ignores y-travel, occupancy and balance).
- Published: `LbT_ds = BaseT_ds + T_LB`, `LbM = BaseM + M_LB`, `LbJ` = J of those. `crane_plan.lower_bound()` is the reference.

Optional improvements, such as a pair lookahead or a v2 algorithm, are proposed by the model worker in TEAM_NOTES.md with measured J gains. They become contract v1.1 only after orchestrator approval.

---

## 5. File ownership (disjoint; never edit another worker's files)

| Worker | Owns |
|---|---|
| **tooling** | `.claude/skills/tia-portal/scripts/TiaRun.cs`, `build.ps1`, new `PlcsimHarness.cs` (+ its build script) in the same folder, `tia-src/numbers.txt`, everything under `tia-work/` (retrieved project `tia-work/crane/`, exports `tia-work/export/`), the "FB1 findings" + "Tooling" sections of `TEAM_NOTES.md` |
| **model** | `tools/crane_model.py`, `tools/crane_plan.py`, `tools/crane_gen.py`, `tools/crane_eval.py`, `tools/crane_data/` (datasets `*.json`, expected plans `*.plan.csv`), "Model" section of TEAM_NOTES.md |
| **runtime** | `tia-src/01_types.udt`, `02_World.db`, `03_HMI_IF.db`, `20_FC_CheckCmd.scl`, `21_FB_CraneControl.scl`, `22_DB_CraneControl.db`, `30_OB1_Main.scl`, `31_OB30_Cyclic.scl`, "Runtime" section of TEAM_NOTES.md |
| **planner** | `tia-src/10_FC_MoveCost.scl`, `11_FB_Planner.scl`, `12_planner_*`, "Planner" section of TEAM_NOTES.md |
| **hmi** | everything under `hmi-tia/` (layout.json, generators, HmiGen.cs, alarm xlsx, HUMAN_STEPS.md), "HMI" section of TEAM_NOTES.md |
| **orchestrator** | `tia-src/CONTRACT.md` |

Dataset JSON (`tools/crane_data/*.json`):
```
{"name": "...", "bay0": [[id y0..y11] for x0..x3], "bay1": [[...] x4], "unload": [48 ints, 0 = empty], "load": [48 ints]}
```
`bay0[x][y]` equals DB10.Bay0[x,y].

Shared rules:
- **No git.**
- **Never modify** FB1/DB2, DB1, DB10, DB11, DB20, DB21 or the given tags. Writing **runtime values** into DB10/11/20/21 on PLCSIM for tests is allowed; changing their **start values or structure in the project** is not.
- **Openness is single-writer.** Anyone may run `TiaRun.exe` against `tia-work/crane` **only while holding the lock**:
  1. Create `tia-work/openness.lock` containing `<worker> <time>`.
  2. If the lock already exists and is younger than 10 min, wait. Older than that: take it over and say so in TEAM_NOTES.md.
  3. Delete the lock when the run ends.
  - Runtime and planner run their compile loop with `TiaRun.exe --project <crane dir> --src tia-src --numbers tia-src/numbers.txt` (exact flags per the tooling section of TEAM_NOTES.md).
  - Until tooling reports the project ready, runtime and planner write code against this contract and syntax-check later.
- Compile **all** of tia-src together (it is one program). A broken file of another worker blocks you: report it in TEAM_NOTES.md, never fix it yourself.
- A denied tool call is not retried verbatim. Work around it and report it.
