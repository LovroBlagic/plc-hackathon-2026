# PLCSIM run: crane PLC (v1.6 build) on a simulated S7-1500

Run on 7 Nov 2026 by the PLCSIM test engineer. This is the first time the program has run on a simulated PLC.

**Bottom line:** the v1.6 PLC program behaves like the Python model, command for command, on every data set tested. M (MD107), T (MD112), MSpec, J, the final DB10/DB11 and the command sequence all match exactly. The CPU stayed in RUN the whole time, with no STOP and no cycle-time problem. No PLC bug was found, and tia-src was not changed.

## Setup that worked
The build under test is a copy of `tia-work/crane/PLC_hackathon_2026_V21` (contract v1.6, World.CfgMMode = 2), placed in `tia-work/simtest/`. Nothing was re-imported.

The tools are in `tools/plcsim/`. Build them with `powershell -ExecutionPolicy Bypass -File tools\plcsim\build.ps1` (output goes to `bin/`, which is gitignored).
- **`SimHost.exe`** keeps one instance alive. It uses the Simulation Runtime API 8.0 installed with S7-PLCSIM V21 at `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\8.0\`. It serves a line protocol on 127.0.0.1:50123 (R/RB/W/WB/STATE/PON/POFF/RUN/STOP/TAGS/LIST/QUIT).
  - The instance is unregistered when the process that registered it exits, which is why a host process is needed.
  - Licence status is **OK**, and no ALM action was needed.
- **`TiaDownload.exe`** handles the Openness download: `--list [--scan] [--attrs]`, `--card <dir>`, and the online `--target "1 X1" --address ip`.
- **`simclient.py`** is the Python client. `crane_sim_test.py` runs one data set end to end against the model. `crane_scenarios.py` runs the HUMAN_STEPS 1.x checks through tag writes.

Steps, in this order:
1. `tools/plcsim/bin/SimHost.exe --name crane --cpu CPU1515` (run it in the background), then `python tools/plcsim/simclient.py PON`.
2. **Online download fails.** The Openness `DownloadProvider.Download` over `PN/IE` / `PLCSIM` / `1 X1` returns "Connect to module PLC_1 failed". That happens with and without an explicit address of 192.168.0.1, even though `GetAccessibleDevices()` does see "S7-1500 CPU:192.168.0.1". The cause was not found; possibilities are headless certificate trust or the virtual CPU's firmware.
3. **What works is a virtual memory card.** Holding `tia-work/openness.lock`, run `TiaDownload.exe --project <copy> --card <dir>`. This is a download to a Windows folder with **TargetForSoftware = PlcSimulationAdvanced**. The result is `DOWNLOAD_RESULT state=Success errors=0` (KHP FB1 included).
4. `simclient POFF`. Copy `<dir>\SIMATIC.S7S` and `S7_JOB.S7S` into `%USERPROFILE%\Documents\Siemens\Simatic\Simulation\Runtime\Persistence\crane\SIMATIC_MC\`.
5. **Required:** in `...\Persistence\crane\sim_hwdb.ini`, set `"CPU Ordering Number": "6ES7 515-2AM01-0AB0 "` (the project's CPU, with the trailing space). The default is `6ES7 515-2AN03-0AB0`, and with it RUN gives error -52 IsEmpty. The original is saved as `tia-work/simtest/sim_hwdb.ini.orig`.
6. `simclient PON`, then `RUN` (the state becomes Run), then `TAGS` (11479 tags). Tag syntax is `HMI_IF.State`, `Current_state_of_Bay0.Bay0[x,y]`, `From_Bay0_to_Bay1.IDs_of_the_containers[i]`, `From_Bay1_to_Bay0.Bay1_IDs_of_the_containers[i]`, `number_of_manipulations`, `time`, `Crane_Control_DB.Planner.DiagMaxCallMs`.
7. To load data, write all 192 DB10/11/20/21 values online (`crane_sim_test.load_data`), then press POČETNO STANJE. No re-download is needed per data set.
8. Run `python tools/plcsim/crane_sim_test.py <set.json>` or `python tools/plcsim/crane_scenarios.py`. Finish with `simclient QUIT`.

Everything ran in real time at ScaleFactor 1. OB30 runs at 1000 ms, so wall time is about 1 s per command.

## 4a/4b: AUTO runs, PLC vs model
The model is `crane_plan` with default config: order 1 with fallback, mmode 2, improve 3000, slot 10. **MSpec** is the model command sequence replayed through `crane_model.FB1(0)`, the spec rule where a diagonal counts 2. For these runs, "cmds" means the full command sequence, reconstructed from FB1's position and M at every OB30 tick, compared with `crane_plan.commands()`.

| Data set | N | model M / T_ds / MSpec / J | PLC MD107 / MD112·10 / MSpec / J | cmds | DB10/DB11 final | max \|L−R\| | OrderModeAct | planner max call / job |
|---|---|---|---|---|---|---|---|---|
| judge `r1_jury_fig1_half` | 12 | 48 / 9216 / 68 / 1.00526 | 48 / 9216 / 68 / 1.00526 | 48/48 = | = | 5 | 1 | 3.3 ms / 0.35 s |
| `rand_05` (golden) | 12 | 48 / 9267 / 66 / 1.00806 | 48 / 9267 / 66 / 1.00806 | = | = | 2 | 1 | 3.0 ms |
| `edge_initial_imbalance` | 24 | 96 / 18363 / 130 / 1.00337 | 96 / 18363 / 130 / 1.00337 | = | = | 9 → 5 (start 9, falls step by step, then stays ≤ 5) | 1 | 5.8 ms |
| `edge_invalid_dup_ids` | 25 | 80 / 15591 / 110 / 0.81029 | 80 / 15591 / 110 / 0.81029 | = (\*) | = | 5 | 1 | 5.3 ms |
| `edge_full_ship` | 20 | 80 / 17040 / 110 | 80 / 17040 / 110 | = | = | ≤ 5 | 1 | 3.3 ms |
| judge `r2_jury_imb_a` (1.13) | 16 | 64 / 12363 / 92 / 1.00835 | 64 / 12363 / 92 / 1.00835 | = | = | 10 → 4 (never above 10, ends 4); AlarmWord2 bit 1 (ID 18) | 1 | 4.0 ms |
| `rand_04` (large) | 74 | 296 / 61113 / 401 / 1.04332 | 296 / 61113 / 401 / 1.04332 | 296/296 = | = | 5 | 1 | **10.4 ms / 13.7 s** (3561 calls) |
| judge `r1_elimination_needless_fallback_s777_rand_0223` (1.11) | – | 32 / 6892 / 46 | 32 / 6892 / 46 | = | = | 5 | 1, OrderFallback 0 | 1.9 ms |
| `rand_05` after STOP on another set (1.12) | 12 | 48 / 9267 / 66 | 48 / 9267 / 66 | – | new set adopted | – | – | – |

- `rand_05` also matches `tools/crane_golden.json` (T_ds 9267, M 48).
- (\*) One OB30 tick was missed by the 100 ms Python sampler, so two commands showed up in one sample. This is a sampling artifact, not a difference: all other commands, M, T and the final yard match.
- `edge_full_ship` failed on the first attempt because of a harness race: START was pressed while the PLC was still in INIT, giving warning bit 13. After the harness fix it passes.
- AlarmWord at DONE is bit 15 (info, finished). On the imbalanced and invalid sets the expected INIT warnings are also present (bit 0, bits 4/5/6).

## 4c: HUMAN_STEPS 1.x checks (tag writes), data set fig1_half
Run with `crane_scenarios.py` plus two inline scripts. All checks pass. The one FAIL printed in `results/batch2.txt` was a harness bug: it compared True with 5. The alarm itself was raised correctly (AlarmWord 4, state ALARM).

| Item | Check | Result |
|---|---|---|
| 1.1 | ON → POČETNO STANJE → READY, N correct, M = T = 0 after reset | PASS |
| 1.3 | SEMI: a click before START runs exactly 1 command (and implies START). 4 clicks give 4 commands. No progress without a click (StepWaiting = 1). Switching to AUTO finishes with M/T = model | PASS |
| 1.4 | STOP right after a lift gives PAUSED and the crane holds with the load (Carried 101). START resumes and ends DONE with M/T exactly = model (48 / 921.6) | PASS |
| 1.5 | OFF mid-run: State OFF, no commands, LampOff. ON: PAUSED with LampReady (does not run by itself). START: DONE, 12/12 transfers | PASS |
| 1.6 | MANUAL: move to bay 2 rejected, bit 9 (hist[0] = 9). Lift on an empty cell rejected, bit 1, ALARM, then ACK gives READY. Lift on an occupied cell OK. Put on an occupied cell rejected, bit 2. Put back OK. Reset (10) with an empty hook OK | PASS |
| 1.7 / 1.15 | AUTO, load 104 on the hook, 999 written into its ship drop cell (0,2): ALARM bit 2. ACK re-targets the put to (0,3) and the run finishes DONE with M 49 (+1 move). OrderModeAct stays 1, no alarm 17, final \|L−R\| = 3. After removing the 999, POČETNO STANJE restores the original data set (R3-E1) | PASS |
| 1.8 | Planner `DiagMaxCallMs` ≤ 10.4 ms on every set (74-transfer set: job 13.7 s over 3561 OB1 calls). CPU always in RUN | PASS |
| 1.9 | After DONE, DB10/DB11 = model final yard. POČETNO STANJE restores the original. The repeat run gives identical M/T (48 / 921.6) | PASS |
| 1.10 | AUTO with 104 on the hook for a LEFT ship cell: 5 IDs written into empty left cells (L−R = 5) gives ALARM bit 0. **One** ACK re-targets the put to the right side (2,0), RUNNING, DONE, final L 10 / R 7. No ALARM/ACK loop | PASS |
| 1.11 | needless-fallback set: OrderModeAct = 1, OrderFallback = 0, plan = model | PASS |
| 1.12 | START, STOP (PAUSED), write the rand_05 data set, POČETNO STANJE: DB10/DB11 = new set, and the run equals the rand_05 model | PASS |
| 1.13 | r2_jury_imb_a: OrderModeAct 1, AlarmWord2 bit 1 (ID 18), \|L−R\| max 10, ends 4 | PASS |
| 1.14 | POČETNO STANJE during RUNNING is ignored (M keeps counting). After STOP it works (READY, M = 0, data restored) | PASS |

Not tested here: 1.2 (given toy data; trivially 0 transfers), the HMI (not built), and the OB1 cycle time itself. Only the planner per-call time was read; the CPU never went to STOP.

## Bugs
- **PLC:** none found.
- **Harness, fixed:** a race in the INIT wait, and the obstacle check comparison.

## Notes for the M-rule change (contract v1.7, CfgMMode 0)
- The PLC's `HMI_IF.MSpec` equals the model's mode-0 replay of the same command sequence on all 8 sets. These are plans made with mmode 2.
- After the v1.7 build, re-run `crane_sim_test.py` on the same sets. The model in the harness reads its defaults from `crane_plan.parse_args`, so check that its `--mmode` default matches World.CfgMMode, then follow the steps above. A new card image is needed: repeat steps 3–6. sim_hwdb.ini keeps the 515-2AM01 number once it is set.

## Files
- `tools/plcsim/`: `SimHost.cs`, `TiaDownload.cs`, `build.ps1`, `simclient.py`, `crane_sim_test.py`, `crane_scenarios.py`.
- `tools/plcsim/results/`: `*.result.json` and `*.ticks.csv` (per OB30 tick: state, crane position, M, T, L/R, Carried, alarms, planner diagnostics), plus `batch1.txt`, `batch2.txt`, `scenarios.json`.
