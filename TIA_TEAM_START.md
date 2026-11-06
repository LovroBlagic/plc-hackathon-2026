# TIA team: start here (container crane task)

Read first:
- `plans/TIA_crane_plan.md`: the full plan (strategy, PLC architecture, timeline)
- AGENTS.md sections "ORGANIZER CLARIFICATIONS" and "TASK 2"
- Spec: `task/tia/PLC_hackathon_2026_HR.pdf`

**Official clarification:** there is only ONE yard bay (Bay 1) next to the ship. Bay 2 does not exist. Valid bays are 0 = ship and 1 = yard.

## 1. Open the project (10 min)
1. `git pull`
2. In TIA Portal V21: **Project → Retrieve** → `siemens-tia-portal/PLC_hackathon_2026_V21.zap21` → target folder `tia-work/` in the repo. This folder is gitignored; share builds as `.zap21` in `deliver/`.
3. Check that it opens. Look at **FB1 "Crane_manipulation"**: how does it count `number_of_manipulations` and `working_time`? This decides our optimization, so please **write what you find in TEAM_NOTES.md**.
4. Check that you can **add/edit a screen on the PC station "WinCC RT Advanced" (device version 17.0)** and compile it. If editing is blocked (licence/ES missing), tell us immediately. Fix: re-run the TIA ISO setup and add *WinCC Professional ES* with a trial licence.

## 2. HMI verdict (research result: `plans/HMI_generation_research.md`)
**Generate the crane HMI. Don't draw all 96 cells by hand.** TIA Openness can export a screen to XML and import generated XML. That covers rectangles, I/O fields, text, buttons, groups, bars and animations.

**Humans draw only this, once (about 20 min):**
1. The HMI connection to the PLC (PLCSIM).
2. A **screen template "Tpl"** with the header: ON/OFF + READY/OFF lamp, INITIAL STATE, AUTO / SEMI-AUTO / MANUAL (with an active-mode indicator), START / STOP / ACK, plus counters (manipulations, working time).
3. An **"Alarms" screen with an Alarm view**. Openness cannot create alarm views or trends, so these screens stay hand-made and are **never regenerated**.
4. **One prototype screen** with:
   - ONE grid cell: rectangle with colour animation, I/O field showing the container ID, small text
   - ONE button with a SetBit event

**Then the agent generates the rest:**
- export the prototype → Python generator from `layout.json` → **both 4×12 grids (96 cells) + HMI tags** → import → compile
- To change the layout: edit the JSON and regenerate (about 1 min).
- ⚠️ Generated screens are **overwritten** on every regeneration. **Never hand-edit them**; put manual objects on the template or alarm screens.

**Alarms:**
- About 10 discrete alarms: imbalance, pick slot empty, drop slot occupied, ID in unload list but not in Bay0, ID in load list but not in Bay1, duplicate/invalid ID, no free slot, invalid manual command, FB1 timeout, done.
- Either type them by hand (about 10 min), or export one alarm to xlsx and the agent generates the rest for the "Import" button.

Note: the `tia-portal` MCP (TiaMcpServer) handles **WinCC Unified only**, not RT Advanced. The agent uses its own Openness tool (TiaRun/HmiGen).

## 3. PLC logic (agent + you)
- The agent writes **FB10** (planner: container order, slot choice, balance check |L−R| ≤ 5 with left = x{0,1}, right = x{2,3}) and the **OB30** logic (1 s: check that the previous command finished, validate pick/drop, issue the next command, AUTO/SEMI/MANUAL) in **SCL sources** under `tia-src/`, imported and compiled by `TiaRun.exe`.
- Strategy (from the plan):
  - 1 manipulation ≈ 19 s in J, so **never move diagonally** (an x+y move counts 2)
  - **alternate unload and load** (dual cycling): put each loaded container into the column of the container about to leave, so balance holds automatically
  - sweep row by row
  - Target J ≈ 1.0; a naive solution is about 1.45.
- **Never modify** the given FB1/DB2, DB1, DB10/11/20/21 or tags MB100–103/MD107/MD112.

## 4. Questions for the organizers (still open, plc@eestec.hr)
1. Must DB20/DB21 be processed in list order, or may we choose the order and interleave unload and load?
2. Is balance checked after every move or only at the end? Does the container on the crane count?
3. Is the target slot a free choice? Is moving other (non-list) containers allowed?
4. How does FB1 count a bay change with the same local x/y?
5. SEMI-AUTO: one click = one crane command, or one whole container transfer?

## 5. Git rules
- On every change: `.\sync.ps1 "message"` (pull → commit → push).
- Put HMI work and notes in `hmi-tia/` and `TEAM_NOTES.md`. Don't edit agent-owned files (`work/src`, `work/PROGRESS.md`, `tia-src/`).
