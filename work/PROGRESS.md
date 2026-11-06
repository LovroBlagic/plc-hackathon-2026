# ME Energy Manager: progress (implementation agent)

STATUS: M1–M4 done (baseline no trip, EV 100 %, logging dev 0.00000 %, archived ME_v1_baseline). M5 in progress: DP planner tuned in Python twin, ST port written (Fri 21:30 local)

## Results
| Version | Scen | finished | tripped | cost_total € | E_ev kWh | E_ev_unmet kWh | EV % | max log dev |
|---|---|---|---|---|---|---|---|---|
| v1 baseline §2.6 (ME) | S1 | yes | no | 241 770.34 | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| v1 baseline §2.6 (ME) | S2 | yes | no | 223 428.54 | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| twin: DP oracle (perfect forecast, reference only) | S1 | | | 201 921 | | 0 | 100 | |
| twin: DP oracle | S2 | | | 167 859 | | 0 | 100 | |
| twin: DP + EMA forecast (default) | S1 | | | 210 332 | | 0 | 100 | |
| twin: DP + EMA forecast (default) | S2 | | | 174 204 | | 0 | 100 | |

Twin (tools/twin.py) reproduces ME baseline exactly (241 770.34 / 223 428.54).
Baseline diagnostics: Team_Main called once per step (nCalls = nSteps = 35041), grid prediction error max 0.0005 kW, BESS both-enables 0, guard curtailed PV 173 steps, 1 step predicted import 999.9 kW (> 999 kW guard limit, < 1000 trip limit; FEC alone = 999.9 with empty battery).
Archive: deliver/ME_v1_baseline.projectarchive (39.5 MB).

## Log
- 20:50 Read AGENTS/plan/skill/spec/dump. SR_Main_Sim and Init_All bodies are graphical (not in the dump); Sim_Core is fully readable ST.
- 20:58 M1: `me_run.py` extended: `--folder Team` (new objects go into an app folder), `--year 0,1` (login → run=FALSE, price_mode, cycle_time_ms=10 + change_cycle edge, reset → run; poll k/finished/tripped every 5 s; read SimScore.total.* and Team_Results.*; print YEAR_RESULT), `--extra exprs`, `--save-archive path`. Verified: untouched Team_Main trips at k=7142 (export). Speed ≈ 95 steps/s → full year ≈ 6.2 min.
- 21:03 M2/M3 code: Team folder with typeTeamAgg, typeTeamAlarm, Team_Cfg, Team_Prices (TT 2×4 + DA 35040 REAL, from CSV, run-length init), Team_Results, Team_Log, Team_HMI, F_* helpers, FB_EnergyLogger, FB_CostLogger, FB_Strategy (baseline §2.6), FB_GridGuard, FB_HmiUpdate, Team_Main (interface unchanged). Build 0 errors.
- 21:23 M2/M3 verified in ME (results table). M4: archive saved. HMI variable list written: work/HMI_VARIABLES.md.
- 21:30 M5: Python twin (tools/twin.py, strategies.py, tune.py, analyze.py) + rolling-horizon DP planner (battery energy 0..1200 kWh in 20 kWh levels, 96-step horizon, monthly peak cap by bisection). ST port: FB_Forecast, FB_Planner, F_StageCost, F_DayType, FB_Strategy mode 1 (not yet built/run in ME).

## Findings (simulator behaviour, from Sim_Core)
- Trip if import > 1000+1e-6 or export > 499+1e-6 (strict >, LREAL). Clamps: charge ≤ (90−SoC)/100·1500/(0.25·0.95), discharge ≤ (SoC−10)/100·1500·0.95/0.25, EV ≤ min(22, E_req/(0.25·0.9)).
- **EV departure quirk:** when an EV departs at step k, Sim_Core sets evPact[j]=0 *before* publishing, so EV[j].P_charge_act = 0 for the interval k−1 even though SimScore counted that energy. Logger uses our own (already feasibility-clamped) command for the departing interval.
- TT price = 4 quarters × VT/NT (changes on 1 Apr, 1 Jul, 1 Oct). DA is hourly until 30 Sep, 15-min from 1 Oct. 1029 negative quarter-hours.
- Memory: TM241 data/code area 10.4 MB, 4.19 MB used before our code → a 35040-REAL table (140 kB) fits.

## BLOCKERS / pending confirmation
- Price tables in our own GVL `Team_Prices` (allowed as "cjenici" per spec §4.1/§5; spec §3.7 says prices come as separate CSVs): **pending organizer confirmation** that the evaluation dataset uses the same 2025 prices.

## Next
- Check baseline S1/S2 results and logging deviation; archive ME_v1_baseline; HMI_VARIABLES.md; then optimisations (Python twin first).
