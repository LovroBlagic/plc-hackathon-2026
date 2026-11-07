# ME Energy Manager: progress (implementation agent)

STATUS: best archived ME_v5_k075 (S1 205 231 / S2 170 189 €). True LP bound S1 199 779 / S2 162 592 → gap 2.7 % / 4.7 %, ~88 % of it monthly peak. Testing peak-focused ideas (Sat 01:20)

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
| **v5 = ME_v3_coldstart** (ME, 5 ms cycle) | S1 | yes | no | **205 877.07** | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| **v5 = ME_v3_coldstart** (ME, 5 ms cycle) | S2 | yes | no | **171 602.67** | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| **v6 = ME_v4_pvf_da** (S1 code identical to v5) | S1 | yes | no | 205 877.07 (v5 run) | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| **v6 = ME_v4_pvf_da**: S2 PV derate 0.2 (ME) | S2 | yes | no | **170 231.63** | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| **v7 = ME_v5_k075**: S1 σ-factor 0.75, 41 first-step candidates (ME) | S1 | yes | no | **205 231.01** | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| **v7 = ME_v5_k075** (ME) | S2 | yes | no | **170 189.36** | 10 363.06 | 0.00 | 100.000 | 0.00000 % |
| twin: DP oracle (perfect forecast, reference only) | S1 | | | 201 921 | | 0 | 100 | |
| twin: DP oracle | S2 | | | 167 859 | | 0 | 100 | |
| twin: DP + EMA forecast (default) | S1 | | | 210 332 | | 0 | 100 | |
| twin: DP + EMA forecast (default) | S2 | | | 174 204 | | 0 | 100 | |

### TRUE LOWER BOUND: full-year LP (tools/lp_bound.py, HiGHS, ~5 s per solve)
Perfect knowledge of FEC, PV, prices and EV sessions; EV fixed at max power; same guard limits (999 / 498 kW); monthly peak variables. The S2 LP uses about 150 steps of simultaneous charge+discharge at negative prices (a relaxation the simulator forbids), so the S2 bound is slightly optimistic.
| Dataset | LP S1 € | LP S2 € |
|---|---|---|
| v0 practice | 199 779 | 162 592 |
| v1 | 198 738 | 162 988 |
| v2 | 198 719 | 163 083 |
| v3 | 198 336 | 157 957 |
| **mean** | **198 893** | **161 655** |

**Honest gap, ME practice data:**
| Version | S1 | S2 |
|---|---|---|
| ME_v4 | 205 877 → +6 098 (3.05 %) | 170 232 → +7 640 (4.70 %) |
| ME_v5 | 205 231 → +5 452 (2.73 %) | 170 189 → +7 597 (4.67 %) |

**Twin mean over 4 datasets:**
| Version | S1 | S2 |
|---|---|---|
| v7 | 204 392 → +5 499 (2.76 %) | 169 189 → +7 534 (4.66 %) |

### LOSS BREAKDOWN (twin v7 vs LP, practice data, tools/loss.py)
| Scen | total gap | energy (buy−revenue) | grid fee | **peak** |
|---|---|---|---|---|
| S1 | 5 445 € | 480 | 107 | **4 858 (89 %)** |
| S2 | 7 608 € | 772 | 277 | **6 558 (86 %)** |

- Our monthly peaks are 50–230 kW above the LP's. S1 example: Jan 669 vs 520, Jul 553 vs 381, Nov 748 vs 565.
- Energy arbitrage is within 0.3–0.7 % of the bound.
- Peak analysis: many monthly peaks are set with the battery still 70–88 % full. The DP imports right up to the cap computed from the pessimistic forecast, because import below the cap looks free. That commits the month's peak, while the pessimistic afternoon never comes.
- → Next ideas are aimed only at the peak: the "lazy peak" rule (do not raise the paid peak while holding it is feasible under the expected forecast), and reserve sizing.

### Gap to oracle (DP with perfect forecast, no reserve; twin). This measures forecast loss only.
Mean over 4 datasets (v0 = practice data, v1–v3 = synthetic with the same statistics):
| Version | S1 mean € | S1 gap | S2 mean € | S2 gap |
|---|---|---|---|---|
| oracle bound | 200 927 | – | 166 079 | – |
| baseline §2.6 | 241 641 | +40 714 (20.3 %) | 222 726 | +56 647 (34.1 %) |
| v4 = ME_v2_dp_planner | 205 358 | +4 431 (2.2 %) | 170 919 | +4 840 (2.9 %) |
| v5 = ME_v3_coldstart | 205 027 | +4 100 (2.0 %) | 170 944 | +4 865 (2.9 %) |
| v6 = ME_v4_pvf_da (S2 PV derate 0.2) | 205 027 | +4 100 (2.0 %) | 169 214 | +3 135 (1.9 %) |

Practice data only (ME vs oracle v0 S1 201 921 / S2 167 859): ME_v3 S1 205 877 (+3 956, 1.96 %), S2 171 603 (+3 744, 2.23 %); ME_v4 S2 170 232 (+2 373, 1.41 %).

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

## Strategy summary (for slides / code review)
- **Structure (folder `Team`):** Team_Main sequences the work. On each new step it runs: 1) detect new step / reset, 2) FB_EnergyLogger + FB_CostLogger for interval k−1, 3) FB_Strategy (FB_Forecast → FB_Planner) → FB_GridGuard → simCmd, 4) remember k values, 5) FB_HmiUpdate. Everything is keyed on simOut.t_sim.k and stamp, with no timers and no PLC clock, so the result is independent of the cycle time (5 ms and 10 ms give the same cost).
- **Grid protection (FB_GridGuard, always last):** it predicts P_grid = FEC − PV + ΣEV − P_bess using the simulator's own clamps (SoC limits, EV remaining energy, available PV), with a 1 kW margin.
  - Import over the limit: release voluntary curtailment, then discharge more, then shed EV power (largest slack first).
  - Export over the limit: charge more, then curtail PV.
  - The two BESS enables come from one signed setpoint, so they are never both TRUE.
  - Measured max prediction error is 0.001 kW.
- **Forecast (FB_Forecast), past data only:**
  - FEC: EMA per day type (Mon–Fri / Sat / Sun) × quarter-hour (α 0.5), plus the mean absolute deviation σ.
  - PV: EMA per quarter-hour (α 0.3).
  - Intraday correction: actual/profile ratio over the last 4 intervals, fading with τ = 16 steps.
  - Cold start: unlearned quarter-hours assume the highest load seen so far.
  - EVs: remaining energy, charged as soon as possible.
- **Planner (FB_Planner), rolling-horizon MPC re-solved every step:**
  1. Monthly peak cap: the peak already reached this month is sunk, so import up to it is free. A bisection finds the lowest cap the battery can hold over the pessimistic forecast (PV × 0.6, FEC + 1σ in two-tariff mode).
  2. Dynamic programming over stored energy (31 levels × 9 actions × 96 steps ≈ 27k operations per step). The cost is import·(price + grid fee) − export·0.9·price (export at a negative price is worth 0, so PV is curtailed instead), plus a penalty above the cap. The terminal value is 0.9 × the mean import price.
  3. The first step is chosen from 21+ continuous candidates using the exact current values.
- **Prices:** Team_Prices holds the price lists. The two-tariff energy price is a 2×4 table (quarter × VT/NT). Day-ahead prices are 35040 REALs. With day-ahead prices the horizon only reaches as far as prices are published: tomorrow becomes visible after 13:00, and the horizon is capped at 96 steps.
- **EVs:** always charged at maximum feasible power, so EV energy is 100 %. Deadline-aware scheduling was tested in the twin and gave only −10 € (S1) / −180 € (S2), so it was not adopted.
- **Logging check:** every value in Team_Results equals SimScore.total to within 0.00001 % in both scenarios.
  - Interval k−1 is logged at step k, using the FEC, day, month and tariff remembered from the previous step.
  - At k = 0 everything resets, and the final call (k = 35040) logs the last interval.
  - An EV that departs at step k is reported with P_charge_act = 0 for interval k−1, so we log our own feasibility-clamped command for that interval instead.
- **Tuning method:** a Python twin of Sim_Core (tools/twin.py) reproduces ME exactly for the baseline and within 0.1 % for the planner. Parameters were chosen on the mean over 4 synthetic datasets with the same statistics (FEC shifted by whole weeks, PV and EV shifted), to avoid overfitting the practice data.
  - Perfect-forecast reference: S1 201.9k, S2 167.9k.
  - Ours: S1 205.9k, S2 171.6k.
  - Baseline: S1 241.8k, S2 223.4k.

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
- 23:40 v5 verified in ME at 5 ms cycle (≈176 steps/s → full step incl. simulator ≈ 5.7 ms, ~45 % headroom vs 10 ms) and archived: deliver/ME_v3_coldstart.projectarchive (+ deliver/ME_v3_src/).
- 23:15 v5: cold-start fallback (unlearned quarter-hours use the highest FEC seen so far): twin −330 € S1, ±0 S2.

- 00:35 (Sat) Orchestrator: keep optimising toward the oracle bound. Oracle recomputed properly (no reserve in DP; earlier run with hi_in_dp default was not a valid bound). Tested: explicit monthly cap selection by DP cost × remaining days (+6k worse; with weight 0.05 only −255 €, not worth ST complexity); S2 PV derate 0.2 in the cap (−1.7k, robust on all 4 datasets) → ported to ST (PLAN_PVF_TT/DA), confirmed in ME (S2 170 231.63, −1 371) and archived as deliver/ME_v4_pvf_da.projectarchive (+ ME_v4_src). Median-of-N forecasts: no gain. S1 sweep: σ factor 0.75 −400 €, a_fec 0.3 −140 € (small).

- 01:10 Round: soft peak penalty above the paid peak (no effect), Huber-clipped EMA (±0), 7 day types (worse), median forecasts (±0), history-based terminal value (±0), cap selection by DP cost (no gain). Adopted S1 σ 0.75 + 41 first-step candidates → ME_v5_k075 (S1 −646 €, S2 −42 €), archived (+ ME_v5_src).
- 01:15 LP bound (tools/lp_bound.py, lp_all.py) and loss breakdown (tools/loss.py) done.

## BLOCKERS / pending confirmation
- Price tables in our own GVL `Team_Prices` (allowed as "cjenici" per spec §4.1/§5; spec §3.7 says prices come as separate CSVs): **pending organizer confirmation** that the evaluation dataset uses the same 2025 prices.

## Next
- Check baseline S1/S2 results and logging deviation; archive ME_v1_baseline; HMI_VARIABLES.md; then optimisations (Python twin first).
