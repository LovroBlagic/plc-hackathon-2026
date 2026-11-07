# V7 code efficiency review (7 November 2026)

Candidate only: `code-review/optimised-src/` (compile passed; simulator parity pending). Best verified deliverable remains
`deliver/ME_v7_capfloor.projectarchive` with `deliver/ME_v7_src/`.
Neither `work/src`, `hmi-me`, the simulator nor the verified archive was modified.
No strategy parameters, floating-point expressions, action traversal order,
logging calculations, grid protection or command interfaces were changed.

## Changes implemented

### FB_Planner: cache integer action bounds per call

The dynamic-programming loop previously evaluated `MAX(AMIN, -iE)` and
`MIN(AMAX, NS - iE)` for each of 31 energy states at each backward horizon stage.
The candidate computes the same 62 integer bounds during terminal-value
initialisation, then indexes them in the backward loop. At H=96, bound evaluations
fall from 5,890 to 62 per planning call (5,828 removed). The added arrays occupy
124 bytes of INT data, before any runtime alignment overhead.

The candidate visits exactly the same actions in exactly the same order and
performs the same floating-point operations. In particular, the strict `<`
tie-breaking comparison is untouched; this matters for the late-discharge rule.
At H=1 the new bound initialisation is unnecessary overhead (62 evaluations),
but that occurs only when the available planning horizon is one interval.

### FB_HmiUpdate: cache pure formatted dates

`F_DtString` walks calendar years from 1970 and constructs several strings.
Header formatting now runs on first call, reset or stamp change. Each EV's
departure formatting runs on first connected call, reset, reconnection or a
changed departure DT. Disconnection immediately clears the displayed string and
invalidates that cache. Other EV values and active/status flags still update on
every call. Same-step stamp/connection/departure changes remain visible.

### FB_HmiUpdate: avoid unchanged selected-table copies

Selected daily/monthly aggregates and the 31 selected-month rows now refresh
on first call, reset, any new simulator step, or either clamped HMI selection
changing. A selection change while paused is therefore handled immediately.
This relies on the existing contract: Team_Log changes only through team loggers
on a new step/reset; the HMI may write selections but not Team_Log or display
outputs. No refresh is skipped on the final logging step.

The simulator normally calls Team_Main once per simulation step, so selected-table
and header caching primarily save work on repeated/paused calls; EV departure
caching also saves work across successive simulation steps. This is not a claim
that all HMI work disappears during the full-year run.

## Verification completed

`python code-review/check_equivalence.py` passed:

- Source isolation: only FB_Planner.st and FB_HmiUpdate.st differ from v7.
- All 31 integer DP action bounds and traversal orders match.
- 100 differential DP traces, horizons 1..192, negative costs and exact ties.
- 20,000 differential HMI calls including first call, reset, paused/repeated calls,
  same-step selection/connection/departure/stamp changes, out-of-range selections,
  and final-style new-step table refreshes.
- Example model counts: 58,749 to 6,324 date conversions; 20,000 to 5,596 selected-table
  refreshes. These are synthetic workload counts, not PLC speed measurements.

These Python checks validate algorithm equivalence; they do not execute the
Structured Text.

### Machine Expert compile (follow-up, 7 November)

After parent coordination, a process check confirmed only the GUI with
`hmi-me/ControlSeed.project` open and no LogicBuilderShell or simulator process.
Copied `work/ME_v7_validation.project` to
`code-review/ME_v7_efficiency.project`, applied only the isolated candidate via
`me_run.py --src code-review/optimised-src --folder Team`, and compiled.

**BUILD_RESULT errors=0 warnings=1**, exit code 0. The sole warning is the existing
missing implicit CheckBounds POU. Full local log: `code-review/build_efficiency.log`
(gitignored). No `--year` or `--tests` was supplied; no simulator login/start,
archive, GUI operation, `hmi-me` change or `work/src` change occurred.

## Required before integration

1. Coordinate exclusive simulator test access with the HMI worker.
2. Use the compiled isolated `code-review/ME_v7_efficiency.project`.
3. Compile gate passed: 0 errors and only the existing CheckBounds warning.
4. Full-year S2 then S1: require S2 169,833.86 EUR and S1 204,598.62 EUR to cents,
   finished/no trip, EV 100 %, max logging deviation <= 0.00001 %.
5. Test HMI first-call/reset, selections while paused, EV disconnect/reconnect and
   changed departure/stamp within a repeated simulator step.
6. Measure actual task execution times if available. Existing wall-time throughput
   is not a worst-case timing measurement. Compare timings under the same host load.
7. Only after validation, integrate into the HMI copy and archive a new version;
   preserve the v7 rollback archive.

## Findings deliberately left unchanged

- FB_CapFloor continues recording history while disabled. Returning early in S1
  would be faster but changes diagnostics and later enabled behaviour unless
  mode changes are formally guaranteed to reset all state.
- F_DayReq runs 14 x up to 96 feasibility iterations in one call at quarter-hour
  CAPF_DELAY. Spreading its work over earlier steps could reduce a timing spike,
  but adds scheduling/state and parameter-stability assumptions. Defer until a
  measured timing bottleneck warrants it; no current measured worst-case exists.
- Do not reassociate DP REAL arithmetic, replace strict tie comparisons or change
  evaluation order: earlier results show floating-point tie sensitivity.
- Calendar conversion assumes the task's 2025-scale dates; broader date-range
  hardening is outside this behaviour-preserving pass.

## Remaining delivery priorities

Finish and browser-test the WebVisu HMI; confirm organizer acceptance; compile and
test the combined HMI+PLC project; archive the combined deliverable; document
launch instructions; prepare slides/demo. TIA simulation and HMI packaging remain
with teammates. Strategy/cost tuning remains frozen at v7.
