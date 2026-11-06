# ME Energy Manager: progress (implementation agent)

STATUS: M1 tooling done; M2 baseline + loggers + HMI GVL built (0 errors); full-year S1/S2 baseline run in progress (Fri 22:50)

## Results
| Version | Scen | finished | tripped | cost_total € | E_ev kWh | E_ev_unmet kWh | EV % | max log dev |
|---|---|---|---|---|---|---|---|---|
| (pending) | S1 | | | | | | | |
| (pending) | S2 | | | | | | | |

## Log
- 22:05 Read AGENTS/plan/skill/spec/dump. SR_Main_Sim and Init_All bodies are graphical (not in the dump); Sim_Core is fully readable ST.
- 22:20 M1: `me_run.py` extended: `--folder Team` (new objects go into an app folder), `--year 0,1` (login → run=FALSE, price_mode, cycle_time_ms=10 + change_cycle edge, reset → run; poll k/finished/tripped every 5 s; read SimScore.total.* and Team_Results.*; print YEAR_RESULT), `--extra exprs`, `--save-archive path`. Verified: untouched Team_Main trips at k=7142 (export). Speed ≈ 95 steps/s → full year ≈ 6.2 min.
- 22:45 M2/M3 code: Team folder with typeTeamAgg, typeTeamAlarm, Team_Cfg, Team_Prices (TT 2×4 + DA 35040 REAL, from CSV, run-length init), Team_Results, Team_Log, Team_HMI, F_* helpers, FB_EnergyLogger, FB_CostLogger, FB_Strategy (baseline §2.6), FB_GridGuard, FB_HmiUpdate, Team_Main (interface unchanged). Build 0 errors.

## Findings (simulator behaviour, from Sim_Core)
- Trip if import > 1000+1e-6 or export > 499+1e-6 (strict >, LREAL). Clamps: charge ≤ (90−SoC)/100·1500/(0.25·0.95), discharge ≤ (SoC−10)/100·1500·0.95/0.25, EV ≤ min(22, E_req/(0.25·0.9)).
- **EV departure quirk:** when an EV departs at step k, Sim_Core sets evPact[j]=0 *before* publishing, so EV[j].P_charge_act = 0 for the interval k−1 even though SimScore counted that energy. Logger uses our own (already feasibility-clamped) command for the departing interval.
- TT price = 4 quarters × VT/NT (changes on 1 Apr, 1 Jul, 1 Oct). DA is hourly until 30 Sep, 15-min from 1 Oct. 1029 negative quarter-hours.
- Memory: TM241 data/code area 10.4 MB, 4.19 MB used before our code → a 35040-REAL table (140 kB) fits.

## BLOCKERS / pending confirmation
- Price tables in our own GVL `Team_Prices` (allowed as "cjenici" per spec §4.1/§5; spec §3.7 says prices come as separate CSVs): **pending organizer confirmation** that the evaluation dataset uses the same 2025 prices.

## Next
- Check baseline S1/S2 results and logging deviation; archive ME_v1_baseline; HMI_VARIABLES.md; then optimisations (Python twin first).
