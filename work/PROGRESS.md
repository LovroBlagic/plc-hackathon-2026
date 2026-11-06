# ME Energy Manager: progress (implementation agent)

STATUS: ME_v2_dp_planner archived: S1 206 341 € (−35.4k vs baseline), S2 171 579 € (−51.9k), no trip, EV 100 %, logging 0.00000 %. Working on v5 tuning (Fri 23:20)

## Results
| Version | Scen | finished | tripped | cost_total € | E_ev kWh | E_ev_unmet kWh | EV % | max log dev |
|---|---|---|---|---|---|---|---|---|
| v1 baseline §2.6 (ME) | S1 | yes | no | 241 770.34 | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| v1 baseline §2.6 (ME) | S2 | yes | no | 223 428.54 | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| v2 DP planner, k1.5σ (S1) / none (S2) (ME) | S1 | yes | no | 207 457.58 | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| v3 = v2 + intraday correction W=4, k1σ (ME) | S1 | yes | no | **206 327.86** | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| v3 (ME) | S2 | – | – | aborted: online connection lost (step > 10 ms, see log) | | | | |
| **v4 = ME_v2_dp_planner**: v3 + DP 40 kWh levels, horizon ≤ 96 (ME) | S1 | yes | no | **206 341.27** | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| **v4 = ME_v2_dp_planner** (ME) | S2 | yes | no | **171 578.56** | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| twin: DP oracle (perfect forecast, reference only) | S1 | | | 201 921 | | 0 | 100 | |
| twin: DP oracle | S2 | | | 167 859 | | 0 | 100 | |
| twin: DP + EMA forecast (default) | S1 | | | 210 332 | | 0 | 100 | |
| twin: DP + EMA forecast (default) | S2 | | | 174 204 | | 0 | 100 | |

Robust twin evaluation (mean over 4 synthetic datasets with the same statistics: FEC shifted by whole weeks, PV by days, EV by weeks; tools/grid.py):
| Config | S1 mean € | S2 mean € |
|---|---|---|
| baseline §2.6 | 241 641 | 222 726 |
| DP, expected forecast (nohi) | 210 493 | **171 773** |
| DP + pessimistic load (EMA + 1.5σ) in cap and penalty | **206 902** | 177 806 |
→ chosen per price mode: S1 = k1.5σ reserve, S2 = no reserve (Team_Cfg FC_KSIG_TT/DA, PLAN_HI_TT/DA).

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

- 21:45 ME login failed once ("No connection to the gateway") while 15 CPU-bound twin processes were running; retry with ≤10 twin workers worked. DP planner in ST runs ~94 steps/s at 10 ms (same as baseline) → fits the cycle.
- 21:55 ST: reserved word `s` and case-insensitive name clash (NCAND vs nCand) fixed. Per-mode reserve settings ported. ME S1/S2 run of v2 in progress; twin grid 2 (intraday forecast correction) and EV deadline scheduling test running.

- 22:30 Twin grid 2/3: intraday correction (ratio actual/profile over last 4 steps, fading τ=16) helps both modes (S1 205.6k with k=1σ, S2 170.1k). The "split cap" idea (free import level from the expected forecast) is worse in both modes (+1.6k/+1.7k), so it is kept off (PLAN_TSPLIT=FALSE, code kept). EV deadline scheduling: only −10 €/−180 €, parked.
- 22:36 ME v3 S2 run hung at k≈26k (simulator idle, script blocked on read). My hung LogicBuilderShell was terminated; killing the simulator runtime process is not permitted (auto-mode). Stale .~u of my own run removed; S2 rerun started 22:44.

- 22:55 Root cause of the S2 hangs: DP too heavy (DA horizon up to 140 steps × 61 levels × 18 actions ≈ 154k ops/step → ~20 ms/step > 10 ms cycle → online connection starves). Fixed: 40 kWh levels (31 × 9) and horizon ≤ 96 → ≈ 27k ops/step; both scenarios now run at ~94 steps/s like the baseline. Twin: no loss in S1, +0.8k in S2.
- 23:15 v4 verified in ME (table) and archived: deliver/ME_v2_dp_planner.projectarchive (+ source snapshot deliver/ME_v2_src/). Twin = ME within 200 € (S1) / 7 € (S2).
- 23:15 Next (v5): cold-start fallback (unlearned quarter-hours use the highest FEC seen so far): twin −330 € S1, ±0 S2.

## BLOCKERS / pending confirmation
- Price tables in our own GVL `Team_Prices` (allowed as "cjenici" per spec §4.1/§5; spec §3.7 says prices come as separate CSVs): **pending organizer confirmation** that the evaluation dataset uses the same 2025 prices.

## Next
- Check baseline S1/S2 results and logging deviation; archive ME_v1_baseline; HMI_VARIABLES.md; then optimisations (Python twin first).
