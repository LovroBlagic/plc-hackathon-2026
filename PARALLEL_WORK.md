# Parallel work: second laptop + its subagent (7 Nov ~17:05, deadline 20:00)

Read this first on the second laptop. `git pull` first; AGENTS.md has the background.

## What laptop 1 (LovroBlagic, orchestrator) is doing right now. Do NOT touch these.
| Area | Owner on laptop 1 | Files |
|---|---|---|
| Crane HMI build (Openness XML + windows-mcp GUI) | HMI agent + orchestrator | `hmi-tia/**`, `tia-work/hmibuild/` (local only) |
| PLC sources v1.7 (spec M rule, diagonal = 2) | builder agent (finishing docs) | `tia-src/*.scl`, `*.db`, `CONTRACT.md`, `STATUS.md`, `tools/crane_*.py` |
| Shortcut scripts + tia-portal skill | shortcuts agent | `tools/shortcuts/`, `.claude/skills/tia-portal/SKILL.md` |
| Final archive | orchestrator | `deliver/TIA_crane_final.zap21` (does not exist yet) |

## Current state (verified)
- **PLC v1.7**: the spec M rule (diagonal = 2) is the default (`World.CfgMMode = 0`). TIA compiles it with 0 errors. Archive: `deliver/TIA_crane_v1_plc.zap21` (PLC only, v1.7).
- **v1.6 on PLCSIM**: identical to the Python model on 8 data sets. See `tia-src/PLCSIM_RESULTS.md`; the harness is in `tools/plcsim/`.
- **HMI**:
  - Screens import.
  - HMI tags do NOT import yet (`set_ControllerTag not supported`). The suspected cause is a missing HMI connection, which is being fixed in the GUI on laptop 1.
  - Alarms and the alarm view need GUI work.
  - Review: `tia-work/verify/hmi_review.md`.

## Tasks for laptop 2 (pick in order; each is independent of laptop 1)
1. **PLCSIM regression of v1.7** (highest value: nobody has run v1.7 on a PLC yet).
   - Retrieve `deliver/TIA_crane_v1_plc.zap21` into a local folder (e.g. `tia-work\simtest2\`, which is gitignored), then follow `tia-src/PLCSIM_RESULTS.md` "setup":
     1. card image via `tools/plcsim/TiaDownload.exe --card`
     2. `SimHost`
     3. copy `SIMATIC.S7S` + `S7_JOB.S7S` into the instance's `SIMATIC_MC`
     4. `sim_hwdb.ini` "CPU Ordering Number" = `6ES7 515-2AM01-0AB0 ` (note the trailing space)
     5. RUN
   - Or use `tools/shortcuts/plcsim_regress.ps1` if it is there; `-DryRun` first.
   - Run `tools/plcsim/crane_sim_test.py` on the same 8 sets.
   - The model must use `--mmode 0`. Compare MSpec, MD107, T, the final yard and the command sequence.
   - Write results to `tools/plcsim/results_v17/` and `tia-src/PLCSIM_RESULTS_v17.md` (new file; don't edit PLCSIM_RESULTS.md).
   - **Fix the harness first (verifier finding, 17:30).** `tools/plcsim/crane_sim_test.py:201` and `crane_scenarios.py:100,116` compare MD107 (FB1 counts +1 per command) with the model's `M`, which is now the spec-rule M (mode 0), so every v1.7 run would FAIL falsely.
     - Compare MD107 with `len(mod["commands"])`.
     - Compare `HMI_IF.M` (spec rule) with `mod["M"]`.
     - Download with re-initialisation, so that World gets `CfgMMode = 0`. Check that online.
   - Rebuild `tools/plcsim/bin` with `tools/plcsim/build.ps1`. It is gitignored because it contains a copied Siemens DLL.
2. **Pitch / presentation for the crane** (finale Mon 9 Nov; prep Sun 09–12): update `plans/PITCH_CRANE.md` → `plans/PITCH_CRANE_v17.md` (new file):
   - J numbers from `tia-src/JUDGING.md` / STATUS v1.7 (spec M rule)
   - PLCSIM proof
   - method: planner + improve + slot, Python twin, adversarial judges, PLCSIM regression
   - the FB1 MD107 vs spec M explanation
3. **Machine Expert energy manager** (paused; read `HANDOFF.md`): the safe deliverable is `deliver/ME_v6_late`. Only resume if 1 and 2 are done. The owner is fapitlovic's laptop; coordinate first.

## Rules for laptop 2
- **Your own working copies only.**
  - Never edit `tia-src/`, `hmi-tia/` or `deliver/TIA_crane_*` (laptop 1 owns them).
  - Write new files; if you find a PLC bug, write it to `TEAM_NOTES.md` (newest on top) and tell laptop 1.
- **Git:**
  - Only the laptop-2 orchestrator session runs `.\sync.ps1 "msg"` (pull --rebase --autostash, commit, push). Subagents never run git.
  - Sync often (every ~20 min) so conflicts stay small.
- **Openness lock:** `tia-work/openness.lock` is per laptop (the folder is local). Run one TIA instance at a time on your laptop, because of RAM.
- **Subagent brief template:** "Read PARALLEL_WORK.md and AGENTS.md TASK 2. Do task N. Don't run git. Don't edit files owned by laptop 1. Report results + files written."

## Status board (each laptop appends one line when it starts or finishes something)
- 17:05 laptop 1: GUI session on hmibuild (HMI connection, tags, alarms) with windows-mcp; HMI agent continues imports; then final archive `deliver/TIA_crane_final.zap21`.
