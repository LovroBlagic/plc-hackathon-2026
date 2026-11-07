---
name: tia-portal
description: Drive Siemens TIA Portal V21 headlessly for the EESTEC container-crane task (S7-1515 + WinCC RT Advanced) - import/compile SCL from tia-src, archive, download to S7-PLCSIM V21 via a virtual memory card, run the PLC-vs-model regression, regenerate the HMI. Use for anything touching TIA Portal, Openness, TiaRun, PLCSIM, tia-work, tia-src or hmi-tia on this machine.
---

# TIA Portal V21 (crane task) - fast iteration recipes

Everything below was verified on this laptop on 7 Nov 2026 unless marked otherwise. Repo root =
`C:\Users\lovro\Documents\claudio\plc-hackathon-2026`. Run the scripts from the repo root with
`powershell -ExecutionPolicy Bypass -File tools\shortcuts\<name>.ps1 ...`. Every script prints ONE final
`*_RESULT ok=0|1 ...` line, exits non-zero on failure, writes a log to `tools\shortcuts\logs\`, and has `-DryRun`
(prints the exact commands, touches nothing).

## The shortcuts (tools/shortcuts/)
| Script | What | Needs TIA | Time |
|---|---|---|---|
| `crane_check.ps1 [-Quick] [-Only a,b]` | offline loop: World.CfgMMode == crane_plan default, `fb10_init_model.py`, `12_planner_mirror.py`, `crane_stress.py`, `crane_eval.py --mmode <CfgMMode>`, `mirror13_par.py` -> `CHECK_RESULT` | no | full ~15-25 min (4 cores), -Quick less |
| `tia_build.ps1 [-Project P] [-Archive x.zap21]` | TiaRun: import all of tia-src (+numbers, OB30 1000 ms), compile PLC -> `TIA_RESULT` + `BUILD_RESULT`. Archive copied only when errors=0 | yes | 3-6 min |
| `plcsim_regress.ps1 [-Project tia-work\simtest] [-Sets std\|a,b] [-SkipDownload] [-NoScenarios] [-KeepSim]` | card image -> SimHost -> copy card -> patch ini -> RUN -> crane_sim_test on 8 std sets + crane_scenarios -> table + `PLCSIM_RESULT` | yes (download step only) | ~20-25 min |
| `hmi_build.ps1 [-Project P] [-Export] [-Offline]` | PROVISIONAL wrapper of `hmi-tia\regen.ps1` (gen_hmi.py + HmiGen.exe import/compile) | yes | ? |
| `rebuild_tools.ps1 [-Only TiaRun,HmiGen,plcsim]` | rebuild Openness/PLCSIM exes from source; refuses while any of them runs | no | <1 min |
| `deliver.ps1 [-Project P] [-Out deliver\TIA_crane_final.zap21] [-SkipHmi]` | PROVISIONAL: tia_build + hmi_build + archive-only TiaRun; copies to -Out only if all steps ok | yes | ~10 min |

Typical loop: edit tia-src -> `crane_check.ps1 -Quick` -> `tia_build.ps1` (shared project) ->
`tia_build.ps1 -Project tia-work\simtest` -> `plcsim_regress.ps1` -> (final) `deliver.ps1`.

## Lock protocol (CONTRACT §5) and the RAM rule
- `tia-work\openness.lock` = `"<owner> yyyy-MM-dd HH:mm:ss"`; whoever runs Openness (TiaRun, HmiGen, HmiLab,
  TiaDownload) against any project under tia-work must hold it; delete it when done.
- **Incident 7 Nov ~16:20:** TiaRun/HmiGen used a 10-min "stale" rule. The builder's TiaRun took the HMI agent's
  ACTIVE lock (HmiLab ran > 10 min without touching it), and two TIA instances ran at once.
  **Rule since then (TiaRun.cs / HmiGen.cs, rebuilt 16:32):**
  - A lock is stale only when it is **≥ 45 min** old (file mtime) **and** no other
    `Siemens.Automation.Portal` / TiaRun / HmiGen / HmiLab / TiaDownload process runs. Otherwise the tool keeps
    waiting (`--lock-wait`, default 900 s), then FATAL.
  - Every holder **heartbeats**: it touches the lock every 150 s while it still holds it.
  - Release deletes the lock only if the content is still ours.
  - Any new tool that takes the lock MUST heartbeat too. HmiLab.cs is the HMI agent's tool; it is adding its own heartbeat.
- The shortcuts never take over a lock. They refuse (exit 3) if the lock exists. While they hold it, a hidden
  helper process heartbeats it (it stops on release, or when the script dies).
  - `hmi_build.ps1` only checks the lock; HmiGen (via regen.ps1) takes it as `hmi`.
- **Rebuilding tools:** `tools\shortcuts\rebuild_tools.ps1 [-Only TiaRun,HmiGen,plcsim]`. It refuses while any of
  those exes runs (check: `Get-Process TiaRun,HmiGen,HmiLab,TiaDownload,SimHost`). Never rebuild an exe in use.
- TiaDownload.exe has no lock option: hold the lock yourself (plcsim_regress does, only for the download step).
- **One TIA instance at a time (RAM).** A headless Openness session lives in the client exe (TiaRun/HmiGen/
  HmiLab/TiaDownload) and may also show a `Siemens.Automation.Portal` process; the shortcuts refuse when any of
  these runs (`-AllowRunningTia` overrides). Never open a project in the TIA GUI while agents compile it:
  TiaRun without `--headless` ATTACHES to a running GUI (first time: Openness "Yes to all" dialog) and refuses if
  another project is open there.
- Never work on `tia-work\crane` from two tools at once; use copies (`tia-work\simtest` for PLCSIM,
  `tia-work\hmibuild` = HMI agent's lab copy).

## TiaRun facts (.claude/skills/tia-portal/scripts/TiaRun.exe, rebuild with build.ps1)
- Imports only `*.udt|*.db|*.scl|*.awl` of `--src`, alphabetically; `.py/.md/.json` ignored.
- Output: `IMPORT <file> ok`, `[ERROR] PLC_1/Program blocks/<Block> (FCn) [<file>.scl:<line>] line <n> :: msg`,
  `TIA_RESULT errors=N warnings=M [import_errors=K]`; exit 0/1/2.
- `--archive` archives EVEN WHEN the compile has errors, and deletes an existing file of that name first -> archive
  to a staging path and copy on success (tia_build/deliver do this). `--no-compile --archive` = archive only.
- `--numbers tia-src\numbers.txt` and `--ob30-ms 1000` are idempotent ("(unchanged)").

## PLCSIM recipe (S7-PLCSIM V21, Simulation Runtime API 8.0) - what plcsim_regress.ps1 automates
1. Build tools once: `powershell -ExecutionPolicy Bypass -File tools\plcsim\build.ps1` -> `tools\plcsim\bin\`
   (SimHost.exe, TiaDownload.exe; bin is gitignored).
2. **Online Openness download FAILS**: `DownloadProvider.Download` over PN/IE / PLCSIM / "1 X1" returns
   "Connect to module PLC_1 failed" (with or without `--address 192.168.0.1`, although GetAccessibleDevices sees the
   CPU). Cause unknown. Do not retry it - use the memory card.
3. Card image (hold the lock): `TiaDownload.exe --project <copy> --card <dir>` -> `DOWNLOAD_RESULT state=Success
   errors=0` (KHP FB1 included). It deletes and recreates `<dir>`.
4. `SimHost.exe --name crane --cpu CPU1515` keeps the instance alive (an instance is unregistered when its
   registering process exits) and serves 127.0.0.1:50123: R/RB/W/WB/STATE/PON/POFF/RUN/STOP/TAGS/LIST/QUIT.
   Client: `python tools\plcsim\simclient.py STATE` / module `Sim`.
5. POFF, copy `<dir>\SIMATIC.S7S` (a FOLDER) and `S7_JOB.S7S` into
   `%USERPROFILE%\Documents\Siemens\Simatic\Simulation\Runtime\Persistence\crane\SIMATIC_MC\`.
6. **Gotcha:** `...\Persistence\crane\sim_hwdb.ini` must say `"CPU Ordering Number": "6ES7 515-2AM01-0AB0 "` (the
   project's CPU, WITH the trailing space). The default `6ES7 515-2AN03-0AB0` gives RUN error -52 IsEmpty. The value
   survives later power cycles (original saved as `tia-work\simtest\sim_hwdb.ini.orig`).
7. PON, RUN (state Run), TAGS (~11479 tags). Tag syntax: `HMI_IF.State`, `Current_state_of_Bay0.Bay0[x,y]`,
   `From_Bay0_to_Bay1.IDs_of_the_containers[i]`, `From_Bay1_to_Bay0.Bay1_IDs_of_the_containers[i]`,
   `number_of_manipulations`, `time`, `Crane_Control_DB.Planner.DiagMaxCallMs`.
8. A data set = write all 192 DB10/11/20/21 values online (`crane_sim_test.load_data`) + POČETNO STANJE; no
   re-download per set. Re-download (steps 3-6) only after a PLC code change.
9. Real time: OB30 = 1000 ms -> ~1 s per crane command. Licence status OK, no ALM action needed.
- Harness gotchas: START right after POČETNO STANJE while still INIT gives warning bit 13 (harness waits for
  READY); the 100 ms sampler can merge two commands into one sample (sampling artifact, not a bug).
- The harness model reads its defaults from `crane_plan.parse_args`: its `--mmode` default MUST equal
  `World.CfgMMode` (crane_check.ps1 step `mmode` checks this).

## HMI (WinCC RT Advanced, HMI Classic) Openness XML - confirmed by hmi-tia/lab/r1.log (7 Nov 15:36)
Pipeline is still being settled by the HMI agent (HmiGen.exe = generator round trip, HmiLab.exe = lab tool).
Confirmed so far:
- Every `ID="..."` inside one SimaticML document must be unique (hex counter). All-`ID="0"` files fail with
  "Duplicate Simatic ML ID '0' found at line ..." (text lists, tag tables, templates).
- Hand-written `Hmi.Dynamic.AppearanceAnimation` and `Hmi.Event.EventHandler` elements are rejected: "Class of the
  '...' type ... is not supported". Clone these from a TIA export of a hand-made prototype instead of writing them.
- `RangeFrom` is not a supported attribute of `Hmi.Dynamic.HorizontalMovementAnimation` /
  `VerticalMovementAnimation`.
- Imported OK when hand-written: Screen with Rectangle, Button (no events), SymbolicIOField, Bar, DateTimeField,
  Screen with a template link (`<LinkList><Template TargetID="@OpenLink"><Name>Tpl</Name></Template></LinkList>`).
- Compile follow-ups: a screen linked to a template that failed to import -> "Invalid template for screen"; a field
  whose tag table failed -> "The process tag is invalid"; SymbolicIOField needs a text list.
- Classes seen in real V21 exports: Hmi.Screen.{Screen,ScreenLayer,ScreenTemplate,TextField,IOField,
  SymbolicIOField,Button,Bar,Rectangle,DateTimeField,Property}, Hmi.Dynamic.TagConnectionDynamic,
  Hmi.Tag.{TagTable,Tag}, Hmi.Cycle.Cycle, Hmi.Globalization.{MultiLingualFont,FontItem}.
- The hmibuild project already has subnet PN/IE_1 with PLC_1 X2 192.168.1.1 and HMI_RT_1 192.168.1.2 and a valid
  HMI_Connection_1 (HmiLab --probe).
- `hmi-tia\regen.ps1` without `hmi-tia\export` silently runs a MOCK dry run and exits 0 (nothing imported);
  `hmi_build.ps1` refuses that case.

## Where results land
- `tools\shortcuts\logs\<script>_<stamp>.log` (gitignored *.log); crane_check: `check_<step>_<stamp>.log`.
- PLCSIM: `tools\shortcuts\logs\plcsim_<stamp>\<set>.result.json|.ticks.csv`, `scenarios.json`, `simhost.out`;
  history of the first run in `tools\plcsim\results\` and `tia-src\PLCSIM_RESULTS.md`.
- Status of the PLC build: `tia-src\STATUS.md` (top section = newest contract version); judges: `tia-src\JUDGING.md`.
- Deliverables: `deliver\` (only via deliver.ps1 / an explicit `-Archive`).
