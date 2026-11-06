# Plan: Machine Expert "Energetski menadžer" (planning agent, 6 Nov ~21:00)

## Facts not in the PDF summary
- The archive contains **no price CSVs**. Ask the organizers; fallback is to extract the prices from the Profiles init code in the dump. A price list in our own DB is allowed (§5).
- `projects.open_archive(zip, projectpath, overwrite)` is in ScriptProjects.pyi:193.
- Simulator clamps to replicate, to be confirmed in the dump:
  - BcMax = min(750, (90 − SoC)/100·1500/(0.95·0.25))
  - BdMax = min(750, (SoC − 10)/100·1500·0.95/0.25)
  - EV = min(22, E_req/(0.9·0.25))

## Key risks
1. Any change to the sim package scores 0 on criteria 1–3. Dump the package at T0 and diff before submitting. Keep the Team_Main interface byte-identical.
2. The evaluation imports Team_Main plus our blocks into a clean project. Keep everything in a `Team` folder, add no libraries, reference only SimIO, SimParam, SimCtrl, GVL_HMI and our own objects.
3. Logging rules:
   - Log interval k−1, using the remembered FEC, day, month and tariff.
   - At k = 0, reset everything.
   - The final call (k = 35040 or sim_finished) logs only and writes zero commands.
   - Use LREAL accumulators.
   - Daily cost has 3 components; monthly and yearly have 4.
4. **New-step guard:** `xNew := k <> kLast`. Stateful updates run only on a new step. Commands are a pure function of the inputs. No TON/TOF anywhere, so results don't depend on cycle time.
5. Build a zeroed local cmd every call, then `simCmd := cmd`. Derive both BESS enables from one signed setpoint so they can never both be TRUE.
6. A trip is catastrophic. Predict P_grid from the bus balance using the feasible (clamped) values, with about a 5 kW margin. Keep a SoC reserve for import. Handle export by **curtailing PV**.
7. Peak cost is large: about 46 k€/yr at a 1000 kW peak. Once a month's peak is set, import below it is "free" for that month.
8. Trends and alarms must run in simulated time (PLC-side 96-sample buffer and alarm ring with simulated stamps).

## Architecture (`Team` folder, ST only)
**DUTs:** typeTeamEnergy, typeTeamCost, typeTeamDay, typeTeamMonth (+P_peak), typeTeamAlarm, E_TeamAlarm, typeTrendSample.

**GVLs:**
- **Team_Results:** yearly LREAL `E_fne, E_fec, E_bess_chg, E_bess_dch, E_ev, E_import, E_export`, plus C_energy_buy, C_energy_sell, C_grid_fee, C_peak, C_total, plus E_ev_ch[0..3].
- **Team_Log:** aDay[0..364], aMonth[1..12].
- **Team_Prices:** grid fees, peak price, VT/NT, and aDA[0..35039] if needed.
- **Team_Cfg:** constants.
- **Team_HMI:** date string, progress, predicted vs actual grid power, monthly peak, aTrend[0..95], alarm ring, iSelMonth/iSelDay.

**FBs:**
- Team_Main (sequencer)
- FB_StepContext
- F_BessMaxChg / F_BessMaxDch / F_EvMaxFeasible
- FB_EnergyLogger
- FB_CostLogger
- FB_Forecast (EMA per day type × qh)
- FB_PeakCap
- FB_Arbitrage
- FB_EvCharger ×4
- FB_Dispatcher
- FB_GridGuard (always last)
- FB_AlarmMgr
- FB_Trend96

**Team_Main order:**
1. Detect a new step.
2. At k = 0, reset.
3. Log k−1.
4. On the final call, zero the cmd and exit.
5. Control: forecast/cap → arbitrage → EV → dispatch → guard.
6. Remember the values needed for the next step.

## Baseline (§2.6) + GridGuard pseudocode
```
Pev[j]:=EvMax[j]; Pnet:=L+ΣPev-PVa; Pb:=LIMIT(-BcMax,Pnet,BdMax)
IMP_LIM:=1000-5; EXP_LIM:=499-5; Pg:=Pnet-Pb
IF Pg>IMP_LIM: Pb+=… up to BdMax; then shed EV; else alarm
IF Pg<-EXP_LIM: Pb-=… down to -BcMax; then curtail_val:=MAX(0,L+ΣPev-Pb+EXP_LIM)
charge:=Pb<-0.01, discharge:=Pb>0.01 (exclusive)
store P_grid_pred, compare next step with EGC (diagnostics)
```

## Improvements, ranked
1. **Predictive peak shaving:** a monthly running peak plus a bisection cap from a virtual SoC run over 96 qh of forecast. About 10–20 k€/yr.
2. **Price/tariff arbitrage:** one routine for both modes, K-th highest/lowest value rule. Two-tariff mode means filling the battery overnight. About 10–25 k€/yr.
3. **Negative DA price:** curtail export, and charge at max when c + fee < 0.
4. **PV room:** discharge in the morning to leave space for the midday surplus.
5. **EV least-laxity:** must-run plus opportunistic charging. Small gain and a risk to EV points, so do it last.
6. **Forecast quality:** EMA α tuned in the twin.

## Verification
me_run.py extensions:
- `--archive`: extract with open_archive into `work\`.
- `--dump`: export every textual object to `.st`, as a baseline for the diff.
- `--folder Team`
- `--year`: SimCtrl price_mode, cycle 10 ms, reset, run; poll k/finished/tripped; then read SimScore vs Team_Results at 0.1 %.
- `--no-build`

Tests:
- S1/S2 full year with no trip.
- Team_Results within 0.1 %.
- Σday = month = year.
- Bus balance holds.
- 10 ms and 20 ms give identical totals.
- Pause/reset mid-year still matches.
- Diagnostics: prediction error, both-enables count = 0.

**Offline Python twin:** replicate the model from the dump, validate it against the ME baseline to about 0.05 %, tune parameters there (about 1 s per year), port to ST, then confirm in ME. Do robustness sweeps on perturbed data.

## Timeline
| Time | Agent | Humans |
|---|---|---|
| 20:30–21:30 | archive/dump/folder tooling; report the real names | ask organizers; verify the HMIG2U/Vijeo HMI opens and connects to the ME simulator; header/nav template |
| 21:30–23:30 | baseline + loggers + Team_Results + HMI vars; full-year S1/S2; **freeze the HMI variable list at 23:00** | sim control, flows, BESS, EV screens |
| 23:30–02:00 | Python twin, validated | tables and cost screens |
| **02:00 A** | baseline with no trip, within 0.1 %; archive v1 | one person sleeps |
| 02:00–08:00 | peak → arbitrage → negative price → PV room → EV laxity | supervise in shifts |
| **08:00 B** | optimized v2 archived | trends, alarms |
| 08:00–14:00 | tuning, comments; integration windows (GUI closed → push src) | finish Table 13/18; screenshots |
| 14:00–17:00 | **freeze at 17:00**; final regression; package diff = 0 | slides |
| 17:00–19:30 | final archive and submit | rehearse |

## Open questions for organizers
1. Price CSVs? Same 2025 prices in the evaluation set?
2. Is DA look-ahead allowed, and how far?
3. Required Team_Results cost names? Is E_ev bus-side?
4. Must the HMI be HMIG2U/Vijeo, or is ME WebVisu acceptable?
5. Compute budget per step?
6. Submission format and slides deadline?

## Check ourselves in the dump
- typeSimOut, typeSimCmd, SimScore, SimCtrl and GVL_HMI fields.
- How SR_Main_Sim calls Team_Main (paused? finished?).
- Trip comparison `>` vs `>=`; clamp formulas.
- Price/tariff structure.
- DST in the stamp.
- TM241 memory for a 35040-entry REAL table.
- Is Vijeo Designer installed?
