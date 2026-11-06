# Plan: TIA "PLC Challenge 2026" container crane (planning agent, 6 Nov ~21:15)

## ORGANIZER CLARIFICATION (6 Nov ~22:10)
**There is only ONE yard bay, Bay 1. Bay 2 (right of the ship) does not exist.** The PDF mentions it by mistake.
- Drop the "no Bay2" assumption and question 5 (Bay2 part).
- Planner and manual validation accept bay ∈ {0, 1} only.

## Corrections and key facts
- **Global column:** Bay1 X = x, Bay0 X = x + 6. (Bay2 does not exist; see the clarification.) Travel t = max(|ΔX|·6, |Δy|·2.3) s. Bay1 x=3 is only 18 s from Bay0 x=0. Tav = 76 s, the Bay1 x=0 → Bay0 x=0 case.
- **Orientation:** plan view, so no stacking constraints. The ship's long axis is y, so **left = x{0,1}, right = x{2,3}**.
- **Cost weighting:** J = 0.5·T/(76N) + 0.5·M/(4N). **1 manipulation ≈ 19 s.** Cost every action as t + 19·m.
- **FB1:** the PDF says number_of_manipulations = "commands", which conflicts with the "x+y = 2" scoring rule. **Read the FB1 source first; it is the ground truth.** Reset = Bay1 (0,0).
- **Sample DBs are a toy alarm-test set:** DB20 = 111..777, most of which are not in Bay0; DB21 = 123, 124, 125. The competition data will differ.
- **HMI:** the user confirmed (20:28) that the WinCC RT Advanced 17.0 device can be added. Still to verify: can its **screens actually be edited** (needs WinCC Advanced/Professional ES)? If not, re-run the ISO setup and add `InstData\ES_PRO` (WinCC Professional ES) with a trial licence.

## Assumptions (design hedges both ways)
- Order within the lists is free (plus a `StrictOrder` flag). Interleaving is allowed.
- Any free target slot. No Bay2. No rehandling of other containers.
- Balance is checked after every lift and put-down; the container on the crane counts as off the ship.
- Work on copies of DB10/DB11. INITIAL STATE = cmd 10 + copy + validate + plan.
- An invalid list entry raises an alarm; after ACK, skip it.
- SEMI-AUTO = 1 click per crane command (parameter).

## Optimization
- Lower bound per transfer is M = 4 (empty move, lift, loaded move, put).
- Never use diagonal moves (+1 M = 19 s). Loaded moves keep y and change x only.
- **Dual cycling:** alternate unload and load. Put the loaded container into the column of the next one to leave, so balance is unchanged and the empty move is y-only.
- **y-sweep** ordering. Leftover single cycles go row by row.
- **Planner:** greedy, cost-driven with one-step lookahead, multi-start over 3–4 variants; keep the lowest T/152 + M/8. In FB10, plan one transfer per OB1 cycle into Plan[1..400].
- **Expected J ≈ 1.00–1.05** (a naive plan gives ≈ 1.45).
- **Possible exploit:** if FB1 counts M by local x/y, then (x,y) → (x,y) across bays costs 0 M and J ≈ 0.88. Verify in the FB1 code and ask the organizers.

## PLC architecture (SCL)
- **Given, never touch:** FB1/DB2, DB1, DB10, DB11, DB20, DB21, tags MB100–103, MD107, MD112.
- **UDTs:** typeCmd {cmd, x, y, bay}, typeBay.
- **DB100 World:**
  - working copies and Carried ID; crane position, busy flag
  - Plan, PlanLen, PlanIdx
  - NextCmd + CmdReady/StepDone handshake (OB30 preempts OB1)
  - UStat/LStat
- **DB101 HMI_IF:**
  - buttons; manual command fields
  - State/Mode/Ready, AlarmWord + AlarmID
  - M, T, J and predicted M/T/J; BalL/BalR
  - crane pixel position
  - CellSt0/1[0..47] for colours
- **FB10 (OB1):**
  - list validation
  - balance monitor
  - planner
  - state machine: OFF → READY → RUNNING ⇄ PAUSED, ALARM (ACK resumes), DONE
- **OB30 (1 s), the only place FB1 is called:**
  - command finished → update World
  - else, if permitted → FC CheckCmd (pick not empty, drop free, balance) → write MB100–103
  - call FB1
  - watchdog
- **Alarms:**
  - imbalance
  - pick empty / drop occupied
  - unload ID not in Bay0 / load ID not in Bay1
  - duplicate / invalid ID
  - no free slot
  - plan infeasible
  - invalid manual command
  - FB1 timeout
  - done

## Toolchain
1. Retrieve the .zap21 into `tia-work\` (GUI, or `TiaRun --retrieve` via Projects.Retrieve). Export FB1 and the DBs, and analyse how FB1 counts M and T.
2. Python reference model `tools/crane_sim.py`: FB1 cost, the planner, a random dataset generator. It also acts as the parity oracle.
3. SCL loop: `tia-src\*.scl` → TiaRun import + compile. Create OB30/FB10 numbers once.
4. `TiaRun --download` to PLCSIM. The first download is done in the GUI.
5. `tools/PlcsimHarness.cs` (PLCSIM Advanced API): write a dataset → Init/Auto/Start → poll until done → compare M/T with Python and check balance.
6. HMI is human work in the GUI: a 1920×1080 ISA-101 layout with two 4×12 grids. Shortcut: export one prototype cell with Openness → generate the 96 cells + tags → import.

## Timeline
| When | Agent | Humans |
|---|---|---|
| 20:30–21:00 | retrieve, export FB1/DBs | email the organizers |
| 21:00–22:00 | Python model + planner, SCL skeletons | ES_PRO install if needed |
| **CP1 22:30** | FB1 semantics known | PC station editable, PLCSIM download works |
| 22:30–03:00 | DBs/FB10/OB30/states, compile loop, harness | screens, alarms, prototype cell |
| **CP2 03:00** | AUTO passes on 3+ synthetic sets | – |
| 03:00–08:00 | SEMI/MANUAL, alarms, tuning | sleep in shifts |
| **CP3 08:00** | feature complete | – |
| 08:00–14:00 | edge cases | HMI polish, end-to-end |
| **CP4 14:00** | full demo via HMI | – |
| 18:00 | code freeze | archive .zap21 at 19:00 |

## Questions for the organizers (plc@eestec.hr)
1. Must DB20/DB21 be processed in list order?
2. Is interleaving allowed?
3. Is balance checked at every step or only at the end? Does the container on the crane count?
4. Is left/right = x{0,1} vs x{2,3}?
5. Is the target slot a free choice? Is rehandling allowed? (Bay2 is answered: it doesn't exist.)
6. How is a bay change with the same local x/y counted in M?
7. Are T and M taken from FB1's outputs?
8. Should the final state be written back to DB10/DB11?
9. How do the evaluators load their data and start a run?
10. SEMI-AUTO granularity: one command or one transfer?
11. Will there be a WinCC Advanced licence?
