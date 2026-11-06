---
name: machine-expert
description: Drive Schneider EcoStruxure Machine Expert (Logic Builder, CODESYS-based) headlessly from the agent. Covers creating projects, writing Structured Text POUs, compiling with exact error feedback, and testing logic in the built-in simulator, plus safe GUI handling via windows-mcp. Use whenever the task involves Machine Expert, Logic Builder, SoMachine, Schneider M241/M251/M262 PLCs, .project files, or CODESYS-style ST on this machine.
---

# Machine Expert (Logic Builder V2.3): agent workflow

Everything here was verified on this laptop (6 Nov 2026). Tools live in
`C:\Users\sajic\Documents\plc-hackathon\me-tools\`. **Keep this skill updated:** when you
discover a new API, gotcha or working pattern, add it here and log it in the project's AGENTS.md.

## Core loop: write ST as files, never through the GUI
```
edit src/*.st  →  apply_and_build.py  →  read BUILD_RESULT / errors  →  fix  →
sim_test.py    →  read PASS/FAIL      →  fix  →  repeat
```
- `apply_and_build.py` takes about 40 s and `sim_test.py` about 55 s. Each run starts a fresh engine, so batch your edits.
- Run the scripts with the wrapper. **Use absolute paths.**
  ```powershell
  $T="C:\Users\sajic\Documents\plc-hackathon\me-tools"
  & "$T\run_me.ps1" "$T\templates\create_project.py"  "C:\abs\X.project"            # new project, TM241CE24T/U
  & "$T\run_me.ps1" "$T\templates\apply_and_build.py" "C:\abs\X.project" "C:\abs\src"
  & "$T\run_me.ps1" "$T\templates\sim_test.py"        "C:\abs\X.project"            # edit TESTS list first
  ```
  `LogicBuilderShell.exe` is `C:\Program Files\Schneider Electric\EcoStruxure Machine Expert\V2.3\LogicBuilderShell.exe`. It is IronPython 2.7, so **no Python 3 syntax**: no f-strings, use `from __future__ import print_function`.

## Source file convention (`src/<PouName>.st`)
```
FUNCTION_BLOCK FB_Name        // or PROGRAM X / FUNCTION X : RET
VAR_INPUT ... END_VAR
VAR_OUTPUT ... END_VAR
VAR ... END_VAR
// ---IMPL---
<implementation statements>
```
- The file name is the POU name. The type comes from the first keyword.
- Existing POUs are overwritten and missing ones are created under Application.
- The TM241 template auto-creates `Application`, `GVL`, `Task Configuration/MAST` calling **`SR_Main`**, and DI/DQ/etc. Put the top-level logic in `SR_Main.st`.
- Write files with the Write tool or bash. The tool strips the UTF-8 BOM, but avoid PowerShell `Set-Content`.

## Simulator tests (`sim_test.py`)
- `TESTS = [(name, {expr: value}, wait_ms, {expr: expected}), ...]`. It writes inputs, waits, then reads outputs. It prints `PASS/FAIL` lines and a final `SIM_RESULT fails=N`.
- **Expressions are relative to the application:** `SR_Main.xStartPB`, `SR_Main.fbConveyor.xMotor`. `Application.SR_Main.x` gives "Invalid expression".
- Write booleans as `"TRUE"`/`"FALSE"` strings. Timers run in real time, so allow `wait_ms` > PT.
- API used: `dev.set_simulation_mode(True)`, `online.create_online_application(app)`, `oa.login(OnlineChangeOption.Never, True)`, `oa.start()`, `oa.set_prepared_value(e, v)`, `oa.write_prepared_values()`, `oa.read_value(e)`, `oa.logout()`.
- Treat the tests as the spec. Derive them from the task statement **before** writing logic.

## Scripting API cheat sheet
Stubs: `...\V2.3\LogicBuilder\ScriptLib\Stubs\scriptengine\*.pyi`. **Grep these for anything else.**

| Need | Call |
|---|---|
| open/create | `projects.open(p, primary=True)`, `projects.create(p, True)`, `proj.save()`, `proj.close()` |
| add controller | `proj.add("Name", 4096, "<id>", "<ver>")`. Run `templates/probe_devices.py` for IDs |
| application | `proj.active_application` |
| find object | `app.find(name, True)`. **Filter by `has_textual_declaration`**: it also returns the same-named MAST task call entry |
| create | `app.create_pou(name=, type=PouType.Program/FunctionBlock/Function, return_type=)`, `app.create_gvl(n)`, `app.create_dut(n)` |
| set code | `obj.textual_declaration.replace(txt)`, `obj.textual_implementation.replace(txt)` |
| build | `app.build()`, then `system.get_message_categories(True)` and `system.get_message_objects(cat)`. Each message has `.severity .text .object .position_text` |
| libraries | `ScriptLibManObject.pyi`: `add_library` |
| tasks | `ScriptTaskConfigObject.pyi`: `create_task` |

Device IDs (type 4096):
- TM241CE24T/U: `101a 0711` 5.3.12.51
- TM241CEC24T/U: `101a 0706` 5.3.12.51
- TM251MESE: `101a 0750` 5.3.12.51
- TM262L20MESE8T: `101a 0810` 5.3.9.26

## ST conventions that compile cleanly here
- Use Hungarian-ish prefixes (`xBool`, `iInt`, `rReal`, `tTime`, `fbInstance`, `eEnum`). They match the Schneider style.
- Build state machines as `CASE eState OF` with an `ENUM` DUT. Keep timers (`TON`/`TOF`) as FB instance vars and call them every cycle.
- Model NC stop buttons as `xStop : BOOL` where TRUE means healthy, and use seal-in `(start OR run) AND stop AND NOT fault`.
- The "CheckBounds POU missing" warning is harmless.

## GUI (only when no script API exists: HW/IO config, visualisations)
- Launch: windows-mcp `App launch_executable` on `...\V2.3\LogicBuilder.exe` with the project path.
- On startup, close the **DTM Repository** dialog.
- Show the project tree with View → Navigators → **Applications tree**.
- **Never double-click a tree label.** A slow double-click starts a rename. Use right-click → Edit Object instead. If rename mode opens, press Esc.
- windows-mcp pauses (`USER_CONTROL`) whenever the user touches the mouse or keyboard. Ask them to keep hands off and don't fight for control.
- **Don't run scripts on a project the GUI has open.** Copy it, e.g. `X_sim.project`, or ask the user to close it.
- Manual simulator path for the user: Online → Simulation, then Login (Alt+F8), then Start (F5). Write values with Ctrl+F7.

## me_run.py extras (verified 6 Nov, EESTEC energy task)
Call LogicBuilderShell.exe directly (me.ps1 mangles `--out`/`--o*` args):
`"...\V2.3\LogicBuilderShell.exe" ...\scripts\me_run.py --project P --src DIR [--folder Team] [--year 0,1] [--extra "GVL.x,GVL.y"] [--save-archive X.projectarchive]`
- `--folder NAME`: NEW objects are created inside application folder NAME (`app.create_folder(name)`, then find it among `app.get_children(False)` with `is_folder`; folder objects have the same `create_pou/create_gvl/create_dut`). Existing objects anywhere are updated in place.
- `--year`: login to the simulator, per price mode: run=FALSE, set price_mode, cycle_time_ms, change_cycle edge, reset=TRUE, run=TRUE; poll SimCtrl.k/finished/tripped every 5 s; print SimScore.total.* vs Team_Results.* and a `YEAR_RESULT` line. Full year at 10 ms ≈ 6.2 min (≈95 steps/s on the PC simulator).
- `--save-archive`: `proj.save_archive(path)` after success.
- GVL expressions are `GVLName.var` / `GVLName.struct.member` (e.g. `SimScore.total.cost_total`). `read_value` returns typed literals like `DINT#0`; strip `TYPE#` before float().
- Build log prints device memory usage; TM241 sim: "Data, Code and Nonsafe data" area 10.4 MB.
- A GVL with a 35040-entry REAL array initialiser (IEC repeat syntax `4(0.135)` to compress) compiles fine; `4.32E-05` literals are accepted.
- Graphical POUs (LD/CFC, e.g. SR_Main_Sim) have no textual implementation: the dump shows only their declaration.

## Limits
- Graphical languages (LD/FBD/SFC) can't be authored via script. Write ST, or import PLCopenXML.
- Trial licences for Code Analysis and the ETEST library are not activated (Help → Manage licenses).
