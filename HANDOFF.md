# HANDOFF: ME energy manager (updated Sat 7 Nov 2026 afternoon)

Resumed by user in Codex. V7 full-year ME validation passed in both modes and the archive was saved. The earlier twin workflow and cron were not restarted. Sections describing the noon pause below are historical.

## Latest result and next action
- V7 cap floor verified: **S1 204,598.62 € / S2 169,833.86 €**, saving 355.50 € in S2 versus v6, S1 unchanged.
- Both years finished without trip, EV delivery 100 %, logging deviation at most 0.00001 %.
- Verified project: `work/ME_v7_validation.project`; sources: `deliver/ME_v7_src/`; full log: `deliver/ME_v7_validation.log` (local, gitignored).
- **Current safe deliverable: `deliver/ME_v7_capfloor.projectarchive`**, 39,671,850 bytes; ARCHIVE_SAVED confirmed in `work/archive_v7.log`. V6 remains the fallback.
- **work/src is now verified v7**, superseding the mid-edit warning below.
- Requested 5 ms stress-test cycle: S1 216 s/year (~6.16 ms/step); S2 263 s/year (~7.51 ms/step, initially slower), with steady segments ~5.8–6.0 ms/step. Worst-case execution time has not been instrumented. Normal simulation cycle must be at least 10 ms.
- **OPTIMISATION PLATEAU** recorded in work/PROGRESS.md: S2 gain 0.209 %, below the 0.5 % threshold.
- **Next: ME HMI** from `work/HMI_VARIABLES.md`, then code quality and slides. Price-table / evaluation-price / HMIG2U-vs-WebVisu organizer questions remain open. Optional twin evaluation is deferred.
Deadline: **Sat 7 Nov 20:00**. TIA is handled by teammates (see `tia-src/STATUS.md`), so this file covers only ME task A.

## 1. Previous confirmed result at the noon pause (historical)
**`deliver/ME_v6_late.projectarchive`** with sources in `deliver/ME_v6_src/`. **This is the safe deliverable.**

| Version | S1 € | S2 € |
|---|---|---|
| v1 baseline | 241,770 | 223,429 |
| v5_k075 | 205,231 | 170,189 |
| **v6_late (best, archived)** | **204,598.62** | **170,189.36** |
| LP true lower bound (perfect foresight) | 199,779 | 162,592 |

- All archived versions: no trip, EV 100 %, logging deviation ≤ 0.00001 %.
- Gap to the bound: S1 2.41 %, S2 4.67 %. About 88 % of the gap is monthly peak cost.
- v6 change: late-discharge DP tie-breaker (`PLAN_LATE_EPS_TT := 0.05`, TT/S1 only).

## 2. Work in progress when paused
### 2a. v7 = v6 + capmodel S2 floor (historical pause notes; now verified above)
- **`work/src/` is mid-edit and is NOT equal to v6.** Changed: FB_Planner, FB_Strategy, Team_Cfg, Team_Main. New: FB_CapFloor.st, F_DayReq.st.
- The worker had finished the code and was about to build and run S2 in ME when it was stopped. That code is **unverified**.
- **To resume:** run `me_run.py` with the current work/src (full-year S2, then S1). Acceptance:
  - S2 < 170,189.36
  - S1 stays exactly 204,598.62
  - no trip, EV 100 %, logging ≤ 0.00001 %
  - step time < ~7 ms
  Then archive `deliver/ME_v7_*`.
- **To roll back:** copy `deliver/ME_v6_src/*` over `work/src/` and delete FB_CapFloor.st and F_DayReq.st.
- Twin reference: `tools/candidates/capmodel.py`, `make_mode(1)` / `config(1)` (bounded S2 feedback floor, f=0.95, nm=3). config(0) is exactly v5, so S1 is untouched.

### 2b. Twin evaluation leaderboard: `work/TWIN_LEADERBOARD.md` (253/291 runs, stopped before completion)
- Raw data: `tools/eval_runs.jsonl`, `tools/eval_results.csv`. Script: `tools/eval_all.py`.
- Datasets: 31 accepted (practice, variants 1–5, synthetic, stress and real-world). 4 were rejected by the dataset reviewer.

| Candidate | Mode | Mean vs v5 | Better on | Worst | Status |
|---|---|---|---|---|---|
| **capmodel** | S2 | **−549** | **31/31** | −118 | **PASS → being ported as v7** |
| capwrap_s2 | S2 | −857 | 5/5 (incomplete) | −141 | promising, finish the evaluation |
| combo_s2 | S2 | −522 | 30/31 | +80 | within the 200 € rule, not reviewed |
| longhorizon | S2 | −135 | 30/31 | +134 | weaker |
| lprules | S1 | −422 | 27/31 | +106 | **already in ME as v6** |
| scenario | both | +45 / +16 | – | – | rejected |

- **User acceptance rule (7 Nov):** a candidate must beat v5 on average and be never worse than v5 by more than 200 € on any dataset.
- To finish the evaluation: resume the workflow with `Workflow({scriptPath: <session>/workflows/scripts/me-twin-optimisation-loop-wf_b13c9d8e-3cf.js, resumeFromRunId: "wf_b13c9d8e-3cf"})`. That works only in the same Claude session; in another session, run `python tools/eval_all.py` directly.

## 3. Key facts and gotchas
- **Twin vs ME:** ME matched the twin within 1 € for v6 (−632 vs −633). Earlier validation was within ~200 € in S1 and ~7 € in S2.
- **ME load:** many parallel python processes slow the ME build from ~1 to ~8 min. Keep ≤ 8 python processes while ME runs.
- **Simulator connection:** above ~20 ms per step it gets lost. The DP uses 40 kWh levels and a horizon of at most 96 steps (~5.7 ms per step).
- **Tooling:** skill `machine-expert` (scripts `me_run.py`, `me.ps1`), the twin (`tools/twin.py`, `tools/strategies.py`), `tools/lp_bound.py`, `tools/loss.py` and the dataset loader (`tools/datasets/loader.py`).
- **Git:** `sync.ps1` mirrors the skills, then pulls with rebase and autostash, commits and pushes. Worker agents run only `sync.ps1`, never raw git.

## 4. Remaining before 20:00 (after optimisation)
1. Verify or finish v7 (section 2a). Optionally finish the evaluation and port capwrap_s2 if it passes on all datasets.
2. **Write "OPTIMISATION PLATEAU" in work/PROGRESS.md**, since the gains are now well under 0.5 % per round.
3. ME HMI (HMIG2U / Vijeo Designer): build sheet from `work/HMI_VARIABLES.md`.
4. Code quality pass (comments, naming, GVL structure).
5. Slides and pitch: version history table, LP-bound gap, loss breakdown, robustness across 31 datasets.
6. Open organizer questions:
   - Are price tables in our own GVL OK?
   - Does the evaluation use the same 2025 prices?
   - HMIG2U or WebVisu?

## 5. Decisions on record
- Workers are Opus/high. The orchestrator talks to the user. No TIA worker (teammates handle TIA).
- 200 € tolerance rule (above). **No git history purge** of the Vijeo help commit 07b9c07.
