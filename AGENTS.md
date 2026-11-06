# PLC Hackathon: agent working notes

Shared memory for AI-agent sessions (Claude Code and others). **Read this first, and update the Session log at the end of every session.**

## Event
- EESTEC LC Zagreb PLC hackathon, 5th edition (https://plc.eestec.hr/). Contact: plc@eestec.hr
- Hackathon: **Fri 6 Nov 2026 20:00 → Sat 7 Nov 20:00**, at Bird Incubator. Sun 8 Nov 09–12: prepare the presentation. **Mon 9 Nov: finale** at FER Siva vijećnica.
- The task is announced at kick-off by Filip Rukavina. The site gives no AI-tool rules or judging criteria.
- Prizes: €1200 / €600 / €300.
- Tools in use: Schneider **EcoStruxure Machine Expert – Logic Builder** and Siemens **TIA Portal**.

## THE TASK (received 6 Nov ~20:15): "Energetski menadžer"
Files in `task/`:
- `EESTEC_Hackathon_Energetski_menadzer.pdf`: the 19-page spec, in Croatian.
- `EESTEC_hackaton_students.projectarchive.zip`: the **Machine Expert V2.3** project archive with a TM241CEC24R controller and an HMIG2U HMI. This task is Machine Expert. The TIA crane task (TASK 2 below) must **also** be delivered.

**What we write:**
- Our logic goes **only** in FB `Team_Main`. Its interface is fixed: input `simOut : typeSimOut`, output `simCmd : typeSimCmd`.
- We may add our own FBs, functions and DBs, plus the HMI.
- **Never modify** SR_Main_Sim, the simulator, SimIO, SimParam, SimCtrl, or the profiles.

**Simulator:**
- One call is one 15-min step (TS_H = 0.25 h). A year is 35040 steps.
- Control it via SimCtrl: price_mode (0 = two-tariff HEP, 1 = day-ahead), cycle_time_ms ≥ 10, reset, then run.
- simOut contains:
  - `t_sim` {k, stamp, qh_of_day, day_of_year, month, weekday, tariff_high}
  - `FNE_output_power` (available PV)
  - `FEC_P_fix` (fixed load)
  - `BESS_SoC` (%)
  - `EV[0..3]` {connected, planned_departure (DT), energy_required, energy_delivered, P_charge_act}
  - **previous-step** values: `FNE_P_act`, `BESS_P_*_act`, `EGC_P_import/export`, `EGC_overload_*`
  - `sim_finished`, `sim_tripped`
- simCmd contains:
  - `FNE_enable_curtail`, `FNE_curtail_value`
  - `BESS_enable_charge`/`BESS_P_charge`, `BESS_enable_discharge`/`BESS_P_discharge` (**never both enables at once**)
  - `EV[j].P_charge`
  - **All members must be written every step.**

**Parameters:** FNE 750 kW, BESS 1500 kWh with ±750 kW and SoC limits 10–90 % (η 0.95/0.95), EV max 22 kW each (η_EV 0.9), grid **import ≤ 1000 kW, export ≤ 499 kW**. **Exceeding either trips the plant and stops the sim** (big penalty).

**Balance:** P_grid = P_fix − P_FNE − P_BESS(dch +, chg −) + ΣP_EV. **Predict it ourselves**, because the EGC_* readings are one step late. To protect export, prefer FNE curtailment.

**Cost:**
- Energy: import·c_en − 0.9·export·c_en
- Grid fee (on import only): 0.020811 €/kWh high tariff, 0.010404 €/kWh low tariff
- Peak: 3.865 €/kW × monthly max import

**Task 2: energy logging.**
- Log daily (365), monthly (12) and yearly kWh for FNE_P_act, FEC (remember the previous step's value), BESS chg/dch, EV per charger and total, import and export, plus the monthly peak.
- Log interval k−1 at step k, using the day and month of k−1. At k = 0 reset everything.
- A final call with k = 35040 and sim_finished logs the last interval.
- Use LReal accumulators.
- DB **`Team_Results`** must hold LReal `E_fne, E_fec, E_bess_chg, E_bess_dch, E_ev, E_import, E_export` and the costs. It is checked against the official totals with a 0.1 % tolerance.

**Task 3: cost logging.**
- Daily, monthly and yearly purchase, revenue, grid fee, peak and total.
- Daily totals exclude peak.

**Task 4: HMI (25 pts).** Required content:
- sim control
- flows (requested vs actual)
- SoC
- EVs
- daily/monthly energy tables
- costs
- 24 h trends
- alarms with history
- date and time on every screen

**Scoring:**
- No trip: 10
- EV energy delivered: 20
- Cost ranking vs other teams: 30
- HMI: 25
- Code and presentation: 15

**Rules:**
- No system clock or time functions.
- No embedded or recorded profiles (forecasting from past data is allowed).
- Results must be independent of the cycle time.
- Evaluation uses an unseen dataset with the same statistics.

**Start with the baseline from §2.6:**
- no curtailment
- EVs at max power
- BESS charges from PV surplus only and discharges on deficit
- BESS corrects grid-limit violations

Then improve: peak shaving, tariff and price arbitrage, EV deadline scheduling.

> **TIA HMI verified (6 Nov 20:28):** Add new device → PC systems → SIMATIC HMI application → **WinCC RT Advanced** is available, version **17.0.0.0** (it matches the installed WinCC RT Advanced V17 UPD8 runtime). The "WinCC Advanced ES missing" concern is resolved.
> **Confirmed by user (6 Nov): the team must deliver BOTH tasks (ME energy manager + TIA container crane).**

> **Plans:** `plans/ME_energy_manager_plan.md` and `plans/TIA_crane_plan.md`, written by the Opus planning agents on 6 Nov.
> TIA corrections from the plan:
> - Travel uses global columns: Bay1 X = x, Bay0 X = x + 6, Bay2 X = x + 12.
> - Left/right halves are x{0,1} vs x{2,3}.
> - 1 manipulation ≈ 19 s in J.
> - Read the FB1 source to learn how it counts M.

## ME project extracted (6 Nov ~21:30)
- **Working copy:** `work/EESTEC_hackaton_students.project`, extracted via `me_dump.py --archive`. **The GUI must use a different copy.**
- **Full source dump** (including the unprotected Sim_Core): `work/dump/` plus `tree.txt`.
- **Price and profile CSVs** in `work/data/` (k, value), made by `tools_extract_profiles.py`:
  - **PriceTT** (Elektra two-tariff, €/kWh). It changes **quarterly**:

    | From | NT | VT |
    |---|---|---|
    | Jan | 0.0900 | 0.1531 |
    | Apr | 0.1051 | 0.1786 |
    | Jul | 0.0934 | 0.1588 |
    | Oct | 0.0949 | 0.1613 |

  - **VT** (BOOL high-tariff window): 07–21 h in winter, 08–22 h in summer. Used for the grid fee and equal to t_sim.tariff_high.
  - **PriceDA** (day-ahead): −0.163 to 0.621 €/kWh, mean 0.114, **1029 negative quarter-hours**.
  - **FNE, FEC:** profiles; use them only for the Python twin, never embed them.
- The HEP web pages show their tables as images and currently list **2026** prices, so the simulator's own data is the authoritative source for 2025.
- `me.ps1` gotcha: PowerShell treats `--out` as its own `-OutVariable`. Call LogicBuilderShell.exe directly for scripts with `--out`.

## ORGANIZER CLARIFICATIONS (official, always apply)
- **6 Nov ~22:10, TIA crane task** (the organizers call it "zadatak 1"): "U tekstu zadatka je greškom ostalo zapisano da postoji bay i s lijeve i s desne strane broda. Samo je jedan bay." There is only **one yard bay, Bay 1**, next to the ship. **Bay 2 does not exist.**
  - Ignore every Bay 2 formula and the FB1 description "2 – field right of ship".
  - Valid bays are **0 = ship** and **1 = yard**. Reject bay ≠ 0/1 in manual mode with an alarm.
  - Travel time uses only the Bay0⇄Bay1 formula (+6 columns) and the same-bay formula.

## TASK 2 (received 6 Nov 20:17): TIA "PLC Challenge 2026": container terminal crane
Files in `task/tia/`: `PLC_hackathon_2026_HR.pdf` (12 pages) and `PLC_hackathon_2026_V21.zap21` (TIA V21 project archive).
The Machine Expert task lives in `task/machine-expert/`.

**System:**
- A ship (Bay 0) and a yard (Bay 1) each have 4 columns (x 0..3) × 12 rows (y 0..11). Container IDs are 100–999; 0 means empty.
- The CPU is a **1515-2 PN**. The HMI is a **PC station, WinCC Runtime Advanced**. Testing uses **PLCSIM**.

**Given blocks:**
- DB10 `Current_state_of_Bay0`: Bay0 Array[0..3, 0..11] of UInt
- DB11 `Current_state_of_Bay12`: Bay1 Array[0..3, 0..11]
- DB20 `From_Bay0_to_Bay12`: unload list, Array[1..48] of UInt
- DB21 `From_Bay12_to_Bay0`: load list
- DB1 globals: container 2.3 m × 6.0 m, crane 1 m/s, lift 20 s, put-down 20 s
- **FB1 "Crane_manipulation"** (DB2):
  - inputs: new_x_position MB100, new_y_position MB101, new_bay_ID MB102
  - In/Out: command_id MB103
    - 0 = none, 1 = lift, 2 = put down, 3 = move to (x, y, bay), 10 = reset
    - **it goes back to 0 when the command is done**
  - outputs: x/y/bay after the command, number_of_manipulations (MD107), working_time (MD112)

**We write:**
- **OB30** (1 s cyclic):
  - check that the previous command finished
  - issue the next command in AUTO, or in SEMI-AUTO after an HMI click
  - MANUAL commands come from the HMI
  - **before each command, check that the pick location is not empty and the drop location is not occupied.** Otherwise raise an alarm and stop, and resume after acknowledge.
- **FB10** (called from OB1): decide the container order, and check ship balance. Left vs right half (along the long axis) must not differ by more than 5 containers, otherwise raise an alarm.

**HMI must have:**
- ON/OFF with READY/OFF indication
- an INITIAL STATE button that reloads DB10/DB11
- AUTO / SEMI-AUTO / MANUAL buttons with mode indication
- START / STOP / ACK
- a graphical display of Bay 0 and Bay 1 showing IDs
- manipulation count and working time
- alarms, e.g. "ID in unload list but not in Bay 0"

**Scoring:**
- **Elimination criteria:** balance must hold (|L − R| ≤ 5) and the given lists must be followed.
- **Ranking (0–10 points):** minimise J = 0.5·T/(N·Tav) + 0.5·M/(4N), where Tav = 76 s and N = unload list length + load list length.
- **HMI:** 0–10 points.

**Counting manipulations:**
- Each x change is 1 manipulation and each y change is 1 (a simultaneous x+y move counts as 2).
- Each lift and each put-down is 1.

**Travel time:**
- Same bay: max(|Δx|·6, |Δy|·2.3) s.
- Bay 0 ↔ Bay 1 and Bay 0 ↔ Bay 2 add 6 columns (36 m). Bay 1 ↔ Bay 2 adds 12 columns.

**Optimisation ideas:**
- Order the moves to minimise travel.
- Choose drop slots that are close and keep the ship balanced.
- Avoid separate x and y moves when one diagonal move suffices.
- Note that M counts both axes.

## Team repo & git workflow (since 6 Nov ~22:00)
- **Repo:** https://github.com/LovroBlagic/plc-hackathon-2026 (branch `main`). This folder (`Documents\plc-hackathon`) **is** the clone.
- **On every change: pull → commit → push.** Run `.\sync.ps1 "message"`. It:
  1. mirrors the skills `~/.claude/skills/{machine-expert,tia-portal}` ⇄ `.claude/skills/` (newer file wins)
  2. `git pull --rebase --autostash`
  3. `add -A`
  4. commits with Claude attribution
  5. pushes
- **Single git operator on this laptop:** the orchestrator Claude session runs sync.ps1, on changes and in its 15-minute monitoring loop. **Worker agents must NOT run git**; they just write files.
- **Not committed** (see .gitignore):
  - live binary `*.project` / TIA project folders
  - simulation caches, `.~u` locks, `*.Application.map`
  - task archives in `task/`; the canonical copies are `schneider-machine-expert/` and `siemens-tia-portal/`
  - Share builds as archives in `deliver/`.
- **Ownership, to avoid merge conflicts:**
  - `work/src`, `work/PROGRESS.md`: ME worker agent
  - HMI work: put it in `hmi-me/`, `hmi-tia/` or a `deliver/` archive
  - Teammates: don't edit agent-owned files; write notes in `TEAM_NOTES.md` instead.
- **Claude Code for teammates:** clone the repo and run `claude` in it. CLAUDE.md loads AGENTS.md, and the `.claude/skills/` folder gives you the machine-expert and tia-portal skills.

## Folder layout
```
plc-hackathon/
  AGENTS.md           <- this file (CLAUDE.md just imports it)
  me-tools/
    run_me.ps1        <- run any ME IronPython script headless
    templates/
      probe_devices.py    list controller device IDs
      create_project.py   new project with TM241CE24T/U (edit the device ID for others)
      apply_and_build.py  push src/*.st into project, build, print messages
  prototype-me/       <- working ME prototype (Proto.project + src/*.st)
  prototype-tia/      <- TIA prototype (pending TIA install)
```

## Machine inventory (laptop, Windows 11)
| Tool | Status / path |
|---|---|
| Machine Expert V2.3 | `C:\Program Files\Schneider Electric\EcoStruxure Machine Expert\V2.3\` (`LogicBuilder.exe` GUI, `LogicBuilderShell.exe` headless IronPython 2.7.12) |
| ME scripting API stubs | `...\V2.3\LogicBuilder\ScriptLib\Stubs\scriptengine\*.pyi` (**grep these for the API**) |
| TIA Portal | **Not installed as of 6 Nov ~18:50.** ISO downloaded: `Downloads\TIA_Portal_STEP7_Safety_WinCC_V21.iso` (8.7 GB). After install, expect `C:\Program Files\Siemens\Automation\Portal V21\` |
| PLCSIM V21, PLCSIM Advanced V8.0 | Installed |
| Python 3.14, git | Installed |
| Windows-MCP (desktop click/type/screenshot) | Registered at user scope: `uvx.exe windows-mcp serve` (the **`serve` arg is required**). Can't drive admin (elevated) windows unless Claude Code itself runs as admin. Use it for GUI-only steps (HW config, HMI). |
| Node 26.13 / npm 11.20, .NET SDK 10.0.403 | Installed 6 Nov via winget. Open a new terminal so PATH refreshes. |

## Workflow: Machine Expert (verified working)
Edit ST as plain files, then let the script push them into the project and compile. Read the errors, fix, repeat.
```powershell
cd C:\Users\sajic\Documents\plc-hackathon
.\me-tools\run_me.ps1 .\me-tools\templates\create_project.py "C:\...\X.project"   # once
.\me-tools\run_me.ps1 .\me-tools\templates\apply_and_build.py "C:\...\X.project" "C:\...\src"
```
- Source format: one file per POU, `src/<PouName>.st`. Write the declaration, then a line `// ---IMPL---`, then the body. The type comes from `PROGRAM`/`FUNCTION_BLOCK`/`FUNCTION X : RET`. Existing POUs are overwritten. New ones go under Application.
- Output ends with `BUILD_RESULT errors=N warnings=M`. Errors include the POU, line and Decl/Impl.
- The TM241 template auto-creates `Application`, `GVL`, a `MAST` task calling **`SR_Main`**, plus DI/DQ etc. Put the main logic in `SR_Main`.
- **Close the project in the GUI before running scripts against it.** A project open in both can conflict.
- Device IDs (type 4096, version 5.3.12.51): TM241CE24T/U `101a 0711`, TM241CEC24T/U `101a 0706`, TM251MESE `101a 0750`. TM262 uses version 5.3.9.26 (L20MESE8T `101a 0810`). Run `probe_devices.py` for others.
- Useful API: `projects.create/open`, `proj.add(name,4096,id,ver)`, `proj.active_application`, `app.find(name,True)`, `app.create_pou(name=,type=PouType.X)`, `app.create_gvl`, `app.create_dut`, `obj.textual_declaration.replace(text)`, `app.build()`, `system.get_message_objects(cat)`. Online/login/download are in `ScriptOnline.pyi`.

### Simulator test loop (verified 6 Nov, 9/9 PASS)
`me-tools/templates/sim_test.py <project>` does the following:
- Sets the device to simulation mode and builds.
- Logs in to the ME simulator, which downloads the program, then starts the PLC.
- For each step in the `TESTS` list, it writes inputs, waits, and asserts outputs.
- Logs out and prints `SIM_RESULT fails=N`.

Notes:
- Edit `TESTS` per task. These are effectively unit tests for PLC logic.
- **Expression syntax is relative to the application:** `SR_Main.xStartPB`, `SR_Main.fbConveyor.xMotor`. The forms `Application.SR_Main.x` and `Device.Application...` give "Invalid expression".
- Calls used: `dev.set_simulation_mode(True)`, `online.create_online_application(app)`, `oa.login(OnlineChangeOption.Never, True)`, `oa.start()`, `oa.set_prepared_value(expr, "TRUE")` then `oa.write_prepared_values()`, `oa.read_value(expr)`.
- Run it against a **copy** of the project (e.g. `ProtoSim.project`) if the GUI has the original open.
- Full agent loop: **edit .st → apply_and_build.py → sim_test.py → fix**.

### Gotchas found
- **A UTF-8 BOM breaks the ST parser** ("Unexpected token 'ï'"). PowerShell 5.1 `Set-Content -Encoding utf8` writes a BOM. `apply_and_build.py` now strips it, but prefer the Write tool or bash.
- Each headless run starts a full LogicBuilder engine. Measured: apply+build about 40 s, sim_test about 55 s.
- `app.find(name, True)` also returns non-code objects with the same name, such as the MAST task's `SR_Main` call entry. Filter on `has_textual_declaration` (fixed in apply_and_build.py).
- The "CheckBounds missing" warning is harmless.

## TIA tooling status (6 Nov ~19:45)
- TIA Portal V21 is **installed**. The Openness assemblies are at `C:\Program Files\Siemens\Automation\Portal V21\PublicAPI\V21\net48`.
- `tia-mcp doctor` gives 7 pass / 2 warn / **1 FAIL: user not in `Siemens TIA Openness`**. In an admin terminal run `net localgroup "Siemens TIA Openness" sajic /add`, then sign out and back in.
- **TiaMcpServer 4.3.0** is installed (dotnet global tool) and registered in Claude Code as the `tia-portal` MCP in **read-only** mode. To build, re-register with read-write (`tia-mcp install claude-code` plus the access-mode option; check `tia-mcp --help`).
- **Plugin `totally-integrated-claude`** is installed at user scope. It has 18 skills (tia-openness-roadmap, tia-plc-operations, tia-python, tia-doctor, plc-code-analysis, tia-import-export, tia-testsuite, …) and the `siemens-docs` MCP (`uvx siemens-docs-mcp`) for searching Siemens docs.
- Skill for ME: `C:\Users\sajic\.claude\skills\machine-expert\SKILL.md` (user-level). **Keep it updated.**

## Workflow: TIA Portal (pending Openness group)
1. Install TIA Portal V21 with the **Openness** option. Add the user to the `Siemens TIA Openness` group (admin), then log off and on.
2. `dotnet tool install -g TiaMcpServer`, then `tia-mcp doctor`, then `tia-mcp install claude-code`. Use read-write mode.
3. Write the logic in SCL (same FB as the ME prototype). Use `compile_check` and fix errors.
4. Optional: download to PLCSIM Advanced and read/write tags via python-snap7 or OPC UA to test.

## Research: MCP servers and agent capability (6 Nov 2026)
**TIA Portal.** All of these use the Openness API, so they need TIA installed plus the Openness group.
- **TiaMcpServer** (Czarnak/tia-portal-mcp, MIT, NuGet 4.3, V21). **Recommended.** It has 19 tools: plc_read/write, compile_check, create/open/save_project, HMI, network and cross-refs. It supports read-only, read-write and full modes. Needs the .NET 10 SDK or a self-contained zip, plus the .NET Framework 4.8 worker.
- heilingbrunner/tiaportal-mcp: simpler, open source.
- OpenTIA-MCP (omirko00): Openness plus PLCSIM Advanced instance lifecycle.
- TiaCommander: proprietary beta. Skip it.
- `mcp-snap7`: start/stop only. Extend it or use python-snap7 directly for DB read/write.

**Machine Expert.** Schneider ships no official MCP. ME is CODESYS-based.
- **Our own `LogicBuilderShell` scripts (above).** Primary path. Verified.
- `@codesys/mcp-toolkit` (johannesPettersson80, npm) runs `--noUI --runscript`. It is made for CODESYS 3.5 and is untested with LogicBuilder.exe.
- L-Ron9974/codesys-mcp-python: a Python equivalent.
- The official CODESYS MCP Server needs CODESYS ≥3.5.22.1 plus a paid Pro subscription. It does **not** work with ME.

**How good are agents.** Agents4PLC (arXiv 2410.14209), LLM4PLC and AutoPLC show LLMs are good at **ST/SCL** when there is a closed loop: generate, compile, read errors, fix, then simulate or verify. They are weak at graphical languages (LAD/FBD/SFC). Even the CODESYS MCP can only read those. Siemens Engineering Copilot / Eigen Agent claims are vendor marketing with no independent benchmarks.
→ **Strategy: write everything in ST/SCL, compile from the agent each iteration, and test in simulation. Humans do HW config, wiring and HMI screens in the GUI where scripting is thin.**

## Blockers / open items
- [x] TIA Portal V21 installed.
- [x] TiaMcpServer and the TIA plugin installed.
- [x] User added to `Siemens TIA Openness` and re-logged in. `tia-mcp doctor`: 8 PASS, 0 FAIL (6 Nov).
- [x] The `tia-portal` MCP was re-registered in **read-write** mode. It needs a Claude Code restart to load.
- [ ] Next: start TIA Portal → bind_project → build the SCL prototype (S7-1500, FB motor) → compile_check → PLCSIM Advanced test.
- [ ] `@codesys/mcp-toolkit` is not installed. It isn't needed, because the machine-expert skill covers it.
- [x] ME simulation via script works (sim_test.py).
- [x] Windows-MCP drives the Logic Builder GUI. The UI tree is fully readable and clicks work.
  - On startup, close the "DTM Repository" dialog.
  - Show the project tree with View > Navigators > Applications tree (or Devices tree).
  - **Don't double-click a tree item:** a slow double-click starts a rename. Select it and press Enter instead.
  - The tool pauses (USER_CONTROL) whenever the user touches the mouse or keyboard, so ask them to keep hands off during GUI work.

## More ME research (6 Nov)
- **No ME MCP exists.** CODESYS launched an integrated MCP server (shown at SPS 2026), but it needs CODESYS ≥3.5.22 with a Pro subscription, and ME V2.3 is an older CODESYS base.
- Community CODESYS MCPs that could be adapted to `LogicBuilderShell`:
  - zbest1000/mcptoolkit-for-codesys (82 tools, SP22)
  - codesys-mcp-sp21-plus (fixes IronPython 2.7 compile issues, runs with the UI)
  - NPavii/codesys-mcp-server
  - johannesPettersson80/codesys-mcp-toolkit
- **PLCopenXML export/import** is an alternative way to move code, including graphical languages, in and out. Enable "declarations as plain text" in Tools > Options > PLCOpenXML.
- There is a Scripting Immediate view in the GUI for running Python interactively.
- r/PLC sentiment is skeptical of autonomous agents and favours human-supervised use. That is good framing for the jury pitch: the agent writes and tests, the engineer reviews.

## Session log
- **2026-11-06 (session 1):**
  - Researched MCPs and created this folder.
  - ME prototype: a headless project with TM241CE24T/U, `FB_MotorStartStop` (seal-in, NC stop, fault, 2 s start-horn TON) called from `SR_Main`. The build gives **0 errors**. An injected error was reported precisely, then fixed. Opened in the GUI.
  - Installed Node and the .NET 10 SDK.
  - TIA is pending install.
- **2026-11-06 evening (orchestrator + workers):**
  - TIA V21 installed; Openness group OK; TiaMcpServer read-write; TiaRun.exe Openness CLI (attach/create/CPU/import/compile).
  - Both tasks received. Plans are in `plans/`. ME project extracted to `work/`, with the sim source dump and price CSVs.
  - The ME worker agent (Opus/high) is running, with progress in `work/PROGRESS.md`. By 21:17 (laptop clock):
    - **M1 tooling done:** `me_run.py --folder/--year/--extra/--save-archive`; a full year takes ≈ 6.2 min at about 95 steps/s.
    - **M2/M3 code built with 0 errors:** Team folder, loggers, GridGuard, baseline strategy, HMI GVL.
    - The baseline S1/S2 full-year runs are in progress.
    - Findings: trip uses strict `>`; exact clamps; the **EV departure quirk** (P_charge_act = 0 in the departure interval); the DA price is hourly until 30 Sep and 15-min after that.
  - Team git repo set up; sync.ps1; push works as AnalenaS (write access granted).
  - Organizer clarification: the TIA crane task has only one yard bay (no Bay 2).
