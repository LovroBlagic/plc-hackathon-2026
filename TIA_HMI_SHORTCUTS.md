# TIA HMI shortcuts and working notes

Purpose: record how to build and troubleshoot this project's WinCC Runtime Advanced HMI faster. Update after each useful discovery. Mark untested ideas explicitly; a successful script exit alone is not proof of a working HMI.

## Scope and safe working setup

- Repository: `C:\Users\sajic\Documents\plc-hackathon`.
- Software: TIA Portal V21, S7-1515 PLC, PC station with WinCC Runtime Advanced.
- HMI data contract: `tia-src/03_HMI_IF.db` (`HMI_IF`, DB101).
- Work in an isolated project under `tia-work/hmi-side/`. The other laptop's `tia-work/hmibuild/` is not present here.
- Do not overwrite the other team's `hmi-tia/` generator or shared deliverable while experimenting; copy tools and change the copies.
- Run one TIA instance per laptop. Check processes and `tia-work/openness.lock` first. Follow the lock/heartbeat rules in `.claude/skills/tia-portal/SKILL.md`.
- The archived PLC project is `deliver/TIA_crane_v1_plc.zap21`; despite its filename, the latest recorded contents are PLC v1.7. It is not the finished HMI project.

## Quick checks (read-only)

From the repository root in PowerShell:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'Siemens.Automation.Portal|TiaRun|HmiGen|HmiLab|TiaDownload|SimHost' } |
  Select-Object ProcessId, Name, CommandLine
Get-Content tia-work\openness.lock -ErrorAction SilentlyContinue
Get-Content hmi-tia\GUI_NOTES.md -Encoding UTF8
Get-Content hmi-tia\README.md -Encoding UTF8
```

## Existing tools and what they actually do

| Tool | Purpose | Caution |
|---|---|---|
| `HmiLab.cs` | Probe device/network attributes, configure network, import/export HMI objects, compile | Build/run an isolated copy; `--net` alone does not prove correct symbolic PLC bindings |
| `HmiGen.cs` | Export/import screens, templates, tags and text lists | Needs valid real prototypes and connections |
| `gen_hmi.py` | Clone prototypes using `layout.json` | Current PLC tag-link schema is unverified |
| `regen.ps1` | Generate then import/compile | Without `hmi-tia/export`, can silently use mocks and report success without a real import |
| `tools/shortcuts/hmi_build.ps1` | Provisional build wrapper | Read its checks before using it |
| `TiaRun.cs` | Retrieve archives, inspect/import/compile PLC, archive projects | Do not overwrite a good archive with a failed build |

## Current blocker: PLC-linked HMI tags

Observed in the other team's handoff: screen imports work, but tag import fails with `set_ControllerTag not supported`.

Local evidence (7 November):

- `hmi-tia/lab/r5/tags/T_V7.xml` contains a manually constructed `<ControllerTag>` link.
- Real exported tags in `hmi-tia/lab/r4_exp/tags/Default_tag_table.xml` show `AddressAccessMode=Symbolic`, an empty `LogicalAddress`, and links to AcquisitionCycle, Connection, DataType and HmiDataType; they do not demonstrate a valid PLC symbol binding.
- Neither the hand-written ControllerTag link nor the existing export proves a working symbolic binding in this project.
- Siemens V21 officially documents `<ControllerTag>` for external tags with an **integrated** connection. The PLC, symbol and integrated connection must exist before import. Thus absence from these local exports is not proof the XML feature is unsupported.
- Official reference: https://docs.tia.siemens.cloud/r/en-us/v21/tia-portal-openness-api-for-automation-of-engineering-workflows/export/import/importing/exporting-data-of-an-hmi-device/tag-tables/special-considerations-for-the-export/import-of-hmi-tags
- A missing HMI connection is a hypothesis, not a confirmed root cause.

### Next experiment (not yet verified)

1. Retrieve the PLC archive into a separate local HMI project.
2. Check the PC station/HMI Runtime and PLC network configuration.
3. Create or verify `HMI_Connection_1` in TIA.
4. Create **one** HMI Bool tag linked to `HMI_IF.SwOn` using TIA's own tag selector.
5. Export that table and inspect the real binding representation/API attributes.
6. Import a duplicate with a new name; compile and verify its PLC link.
7. Only then generate all tags and import the screens.

Do not solve a binding error by deleting the PLC link or making all tags internal: that can compile while producing a non-functional HMI.

## GUI navigation checklist (to verify on this laptop)

- HMI connection: PC station → HMI runtime → Connections.
- Tags: HMI runtime → HMI tags → tag table; choose the PLC tag through the editor, rather than typing an assumed XML link.
- Screens and navigation: HMI runtime → Screens; use a real exported button event as a prototype.
- Alarm configuration: HMI alarms plus an Alarm view; confirm trigger bits and one-click acknowledgement.
- Compile the HMI explicitly; a clean PLC compile does not validate the HMI.

Exact labels/click paths above are a checklist, not a record of completed GUI actions here.

## Acceptance checks before archiving

- Correct PLC connection and no unresolved process tags.
- ON/OFF, INIT, AUTO/SEMI/MANUAL, START/STOP/ACK and manual controls operate.
- Both 4×12 container grids display live IDs and states.
- Manipulation counters distinguish the spec rule from FB1/MD107; score uses the intended rule.
- Navigation, alarm display/history and acknowledgements work.
- HMI compile succeeds; runtime communicates with the intended simulated or real PLC.
- Final archive contains both PLC and HMI, and can be retrieved on a clean copy.

## Discovery log

| Date | Action | Result / next improvement |
|---|---|---|
| 2026-11-07 | Read HMI handoff, skill and local prototypes; checked active processes | No local TIA process or working HMI project. Create isolated copy before testing |
| 2026-11-07 | Compared tag-generation code with exported tag XML | Correct symbolic link still needs a real linked-tag export; avoid repeating invented schema imports |
| 2026-11-07 | Checked official Siemens V21 tag import documentation | ControllerTag is documented, but requires an integrated connection; test project prerequisites first |
| 2026-11-07 | Compiled isolated TiaRun/HmiLab copies under tia-work/hmi-side/tools | Both compile successfully on this laptop; original tools unchanged |
| 2026-11-07 | Retrieved PLC archive into tia-work/hmi-side/project/PLC_hackathon_2026_V21 | Success, no PLC source import/change; separate from other laptop's HMI copy |
| 2026-11-07 | Probed hardware HMI connection and tried Tags.Import on one ControllerTag-linked Bool | Existing HMI_Connection_1 is valid at hardware level (192.168.1.2 → PLC X2 192.168.1.1); single-tag import still fails with set_ControllerTag not supported. Do not assume per-tag import alone fixes it |
| 2026-11-07 | Compiled baseline HMI after failed probe | Read actual HMI_COMPILE line in tia-work/hmi-side/tag_probe.log; LAB_RESULT=1 is the failed link experiment, not proof all baseline screens fail |
| 2026-11-07 | GUI-created P_SwOn → HMI_IF.SwOn, then compiled/exported | GUI link works and HMI compile is 0 errors/0 warnings. Both individual and table Openness XML exports omit ControllerTag even for this linked tag; preserve project, do not round-trip tags through XML |
| 2026-11-07 | Native GUI Excel export/import from Show all tags | Excel preserves PLC tag column. Generated 492 tags; round-trip export confirms 492/492 correct symbol paths and connections, 0 binding errors. Generator: tia-work/hmi-side/generate_tags_xlsx.py |
| 2026-11-07 | Checked imported Real tags after warnings | Excel coding string must be IEEE754 (no space). IEEE 754 triggered warnings and left Real acquisition at 1 s. Corrected generator; second import completed successfully without warning dialog |
| 2026-11-07 | TIA GUI input on this display | Screenshot is 2880×1800; saved preview 1440×900 means click coordinates ×2. Hold mouse-down for ~100 ms; immediate down/up was unreliable. Wait for editor opening before next click |
| 2026-11-07 | Imported generated text lists/template/five screens | All imports succeed. Missing Alarms screen caused one navigation error; importing the empty native Alarms page fixes it |
| 2026-11-07 | Resolved 139 screen/template naming warnings | Prefix all 51 template ScreenItem ObjectNames with hdr_; subsequent HMI_COMPILE state=Success errors=0 warnings=0 (header_build.log) |
| 2026-11-07 | Native alarm sample export vs generic alarm workbook | Headers match, but generic generated workbook import failed. Prepared generate_alarms_xlsx.py cloning native sample package/metadata; retry not yet verified |
| 2026-11-07 | TIA exited during failed alarm-import investigation | Reopen saved project; last saved clean build at 17:44. Do not claim a confirmed crash cause without evidence |
| 2026-11-07 | Imported alarms using a workbook cloned from native alarm_sample.xlsx | Success: 18 discrete alarms. Round-trip export confirms all 18 IDs/classes/trigger bits/HMI and PLC acknowledgements, 0 mismatches (alarms_validation.json). Generic minimal XLSX failed; native package clone works |
| 2026-11-07 | Added native Alarm View control in Alarms | Toolbox → Controls → yellow alarm-table icon. Current view at X16/Y110/W992/H260; copied view at X16/Y420/W992/H260, General → Alarm buffer. Added AKTIVNI ALARMI and POVIJEST ALARMA labels |
| 2026-11-07 | Exported Alarms screen after adding native Alarm View | Openness XML omits the Advanced Alarm View control. Do not regenerate/import Alarms XML afterwards; preserve it in the saved project/archive |
| 2026-11-07 | Compile with original two acknowledgement tags | 10 errors: acknowledgement tag invalid. Removing only PLC acknowledgement tag AlarmAckWord restores HMI compile 0/0. HMI acknowledgement tag AlarmHmiAck remains mapped and can signal FB10; no PLC source changed. Original cross-ack design is NOT runtime-verified |
| 2026-11-07 | Configured current-alarm view | General: Pending alarms on, Unacknowledged alarms off (current-only). Toolbar: Acknowledge on. History view remains Alarm buffer. Runtime ACK behaviour still to test |

## Verified native Excel tag procedure

1. In Project view expand PC-System_1 → HMI_RT_1 → HMI tags → Show all tags.
2. Toolbar: Export HMI tags (right arrow); use `.xlsx`. Dismiss the success dialog before continuing.
3. Workbook `Hmi Tags` sheet includes Name, Path (table), Connection, PLC tag, DataType and acquisition settings.
4. Clone a real GUI-linked row. For this project use Connection `HMI_Connection_1`, symbol `HMI_IF.Member` or `HMI_IF.Array[index]`, table `HMI_IF_gen`.
5. Toolbar: Import HMI tags (left arrow) from **Show all tags**; import was not available from the individual-table editor in this session.
6. Export again and compare every PLC tag path/connection against the manifest; import counts alone do not prove bindings.
7. **Do not import generated XML tag tables afterwards**: that route failed and can destroy bindings. Import only text lists/templates/screens through Openness.

For each new entry record: exact command or GUI path, input project/version, observed output, time taken, and what to do differently next time.

### Runtime readability and live demo (7 Nov, 18:30)
- Local generator: `tia-work/hmi-side/gen_hmi_readable.py`, layout `layout_readable.json`; shared generator unchanged. Default fonts scale with geometry; header names retain hdr_ prefix.
- GUI: HMI_RT_1 > Runtime settings > General > Screen resolution. Dropdown Home, Down twice selects 1920x1080. Updated local layout scale=1, device 1920x1080 before importing screens.
- Native alarm controls do not resize automatically. Layout fields adjusted separately; do not reimport Alarms XML.
- Runtime can report configuration could not be loaded after Openness compilation. A GUI Software (rebuild all) followed by Start simulation worked; do not launch multiple runtime processes.
- Live HMI AUTO demo: loaded two-container input DBs online only, clicked INIT/AUTO/START. Finished 2/2 transfers, unload=1/load=1, MSpec=7, T=146, J=0.9177631. AlarmWord=32768 is completion information. STOP was clicked too late to test pause; do not count it as a passing STOP test.
- Main/results/native alarms navigation verified. Both current alarms and alarm history display real runtime messages. Native acknowledgment and SEMI/manual still need verification. Evidence: tia-work/hmi-side/runtime_checks.json.

### Final readability build and runtime checks (18:33)
- Native GUI Runtime settings > General > Screen resolution = 1920x1080, local layout scale=1. Existing alarm views needed manual Layout adjustment below 148px header.
- Frame colours were ignored because set_attr only edits existing attributes and prototype P_Text omitted BackColor. Add BackColor/BorderColor with must=True. Container IDs now carry their own copied RangeAppearanceAnimation, so numeric fields cannot hide state colours. Native range colours and legend now match.
- All six navigation targets opened. SEMI START waited; NEXT STEP advanced MSpec0->1; STOP State4, START State3/StepWaiting1. MANUAL dropdown2/IZVRSI returned carried201, MSpec1->2. Repeating PUT caused AlarmWord4096/State5. Native table ACK cleared AlarmWord0/State4 and history showed acknowledge/clear events.
- Final PLC/HMI compile0/0, archive integrity checked, identical copy in Downloads/solutions/TIA_HMI_readable_final.zap21 (8,441,506 bytes). Evidence runtime_checks.json and runtime_final.png under tia-work/hmi-side.
- HMI runtime left on initialized demo in dedicated simulator crane_hmi_side, port50124. No extended HMI dataset regression or physical deployment test. GUI project stays open; openness.lock remains owned hmi-side-gui.

### Larger text and full input grids (18:45)
- Font scaling now adds 28% for sizes <=16pt. Container ID fields enlarged from64x26 to90x40; shorter button labels avoid clipping (INIT/AUTO/SEMI/KORAK/PRIKAZ/RUCNO).
- PIL Tahoma width review: no generated static label exceeds its box width. Result font_width_review.json. Inspect runtime too; this measurement does not prove every possible live numeric value fits.
- Current test inputs rand_01:35 ship +24 yard containers,27 transfers. Synthetic regression input, NOT official judging data. Model expected MSpec130,T2503.2; final result pending. DATA_SOURCES.md explains the distinction.
- AUTO started through HMI after INIT completed; STOP during motion captured State4/CraneBusy1 and State4/CraneBusy0, START resumed. Do not press START while INIT is still in progress; doing so reports alarm13.
- monitor_runtime.py only observes the dedicated simulated CPU and compares final M/T, transfer count and both grids; no PLC writes. SimHost handles one client, so do not open another simclient while this monitor is running.

- 18:47 rand_01 HMI run PASS:27/27,MSpec130,T2503.2002,both bays exactly match model; AUTO pause/resume included. New archive TIA_HMI_large_text_v2.zap21 integrity checked and copied to Downloads/solutions.
- Archiving while simulation runs opens modal Close the simulation? dialog, blocking API archive. After run completes, close owned runtime and answer Yes in TIA; archive finishes and project reopens.

- After archive, first runtime launch again failed to load pdata.fwc. GUI HMI > Compile > Software(rebuild all), then Ctrl+Shift+X restored successful launch. Local UI helper now uses actual MainWindowHandle and AttachThreadInput fallback to activate only the owned TIA window; PID foreground guard remains enabled.

### Blinking diagnosis and original-data validation
- HMI animations FlashingType=No. Live PLC reads showed CellSt toggling1->2/3/4 even paused because FB10 first reset published colours then overlaid list/current-transfer colours every scan.
- Fix in isolated FB10: build visSt0/visSt1 VAR_TEMP arrays, then publish each final HMI colour once. Keep HMI interface and planning/motion logic unchanged. Compile/card download0/0.
- Fresh download inputs verified exactly against exported starter DB10/11/20/21. HMI run: N10,transfers0,MSpec0,T0,J0; seven unload +three load source IDs missing. Python same result.
- After fix,240 samples each96 cells:zero changed cells,including27 non-base-colour cells. Post-fix fuller runtime comparison pending.

### Full display scaling (in progress)
- RT Advanced fixed pixel layout does not automatically fill this2880x1800 desktop. Process-local __COMPAT_LAYER=DPIUNAWARE successfully scales runtime geometry by Windows200%, without registry/global display changes.
- Runtime layout changed to1440x900, generator scale_x=.75,scale_y=900/1080. Motion animation Y positions use scale_y too. All generated five screens plus template imported; native Alarms retained. Alarm views x12,width1416,top y160/h240,history y500/h300; native table/header fonts20px.
- Scoped ProcessStartInfo UseShellExecute=false + EnvironmentVariables[__COMPAT_LAYER]=DPIUNAWARE works. Start simulation through TIA once after generation before relaunching the scoped runtime. Direct first launch after compile can fail to load configuration.
- Fullscreen achieved; generated text remained tiny. Added font_display_multiplier=2.0 in local generator/layout; runtime visual validation pending.
