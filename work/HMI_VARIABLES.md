# HMI variable list (Machine Expert "Energetski menadžer")

For the HMI builder. All team variables are GVLs in the application folder `Team`, so a variable is addressed as `<GVL>.<name>` (for example `Team_HMI.sDateTime`). The simulator variables are in `SimIO`, `SimParam` and `SimCtrl`.

The HMI may **write** only to `SimCtrl.*` (simulation control) and to `Team_HMI.iSelDay` and `Team_HMI.iSelMonth` (table selection). Everything else is read-only.

**Time base:** all dates, times, trends and alarm stamps use **simulated** time, taken from `simOut.t_sim`, never the PLC clock. They therefore stay correct when the cycle time changes.

**Vijeo/HMIG2U:** if a variable is not visible in the HMI tag browser, add it in the ME **Symbol Configuration** (Application → Symbol Configuration → tick the `Team_*` GVLs → build).

## 1. Simulation control and status (Table 13 row 1; show the header on every screen)
| Variable | Type | R/W | Meaning |
|---|---|---|---|
| `SimCtrl.run` | BOOL | W | run / pause |
| `SimCtrl.reset` | BOOL | W | reset. Ask for confirmation. The simulator clears it itself. |
| `SimCtrl.price_mode` | INT | W | 0 = two-tariff (HEP), 1 = day-ahead. Set it before reset. |
| `SimCtrl.cycle_time_ms` | UDINT | W | SR_Main_Sim period in ms (≥ 10) |
| `SimCtrl.change_cycle` | BOOL | W | rising edge applies cycle_time_ms. Use a push button (TRUE, then FALSE). |
| `SimCtrl.k` | DINT | R | current step 0..35040 |
| `SimCtrl.finished`, `SimCtrl.tripped` | BOOL | R | end of year, grid trip |
| `Team_HMI.sDateTime` | STRING(20) | R | simulated date and time "DD.MM.YYYY HH:MM" (start of interval k) |
| `Team_HMI.rProgressPct` | REAL | R | year progress, 0..100 % (bar graph) |
| `Team_HMI.sTariff` / `Team_HMI.xTariffHigh` | STRING / BOOL | R | 'VT' / 'NT' |
| `Team_HMI.sPriceMode` | STRING(20) | R | price model as text |
| `Team_HMI.rPrice` | REAL | R | energy price of the current interval [€/kWh] |
| `Team_HMI.rGridFee` | REAL | R | grid fee of the current interval [€/kWh] |

## 2. Power flows: requested (interval k) vs actual (interval k−1) [kW] (Table 13 row 2)
| Quantity | Requested / now | Actual (previous interval) |
|---|---|---|
| PV (FNE) | `Team_HMI.rFneAvail` (available), `Team_HMI.rFneExpected` (after curtailment), `Team_HMI.xCurtActive`, `Team_HMI.rCurtValue` | `Team_HMI.rFneAct` |
| Fixed load | `Team_HMI.rFec` | `Team_HMI.rFecPrev` |
| Battery (+ discharge, − charge) | `Team_HMI.rBessReq`, `rBessChgReq`, `rBessDchReq` | `Team_HMI.rBessAct`, `rBessChgAct`, `rBessDchAct` |
| EV charger j = 0..3 | `Team_HMI.aEvReq[j]`, sum `rEvReqSum` | `Team_HMI.aEvAct[j]`, sum `rEvActSum` |
| Grid (+ import, − export) | `Team_HMI.rGridPred` (our prediction) | `Team_HMI.rImportAct`, `Team_HMI.rExportAct` |

The raw values are also available: `SimIO.simOut.*` (inputs) and `SimIO.simCmd.*` (commands).

## 3. Battery and EVs (Table 13 rows 3–4)
- `Team_HMI.rSoc` [%] (number plus bar), `Team_HMI.rSocMin`, `Team_HMI.rSocMax` (limit lines)
- `Team_HMI.sBessDir` ('PUNJENJE' / 'PRAZNJENJE' / 'MIROVANJE') with `Team_HMI.rBessReq`
- Per charger j = 0..3:
  - `Team_HMI.aEvConnected[j]`
  - `Team_HMI.aEvDeparture[j]` (STRING "DD.MM.YYYY HH:MM")
  - `Team_HMI.aEvRemaining[j]` [kWh], `Team_HMI.aEvDelivered[j]` [kWh]
  - `Team_HMI.aEvStepsLeft[j]` (15-min intervals until departure)
  - `Team_HMI.aEvReq[j]` / `Team_HMI.aEvAct[j]` [kW]
- Peak power: `Team_HMI.rPeakMonth` (this month's import peak so far) and `Team_HMI.rPeakTarget` (the cap the controller aims for) [kW]

## 4. Daily and monthly energies and costs (Table 13 rows 5–6)
The struct `typeTeamAgg` has these members:
- `E_fne`, `E_fec`, `E_bess_chg`, `E_bess_dch`, `E_ev`, `E_ev_ch[0..3]`, `E_import`, `E_export` [kWh]
- `P_peak` [kW]
- `C_purchase`, `C_revenue`, `C_grid`, `C_peak`, `C_total` [€]

All members are LREAL. Show them with 1–2 decimals.

| Table | Variables |
|---|---|
| Year | `Team_Results.*` (same names as above, plus `cost_energy/cost_grid/cost_peak/cost_total` as in SimScore), or `Team_Log.stYear.*` |
| Selected month | write `Team_HMI.iSelMonth` (1..12) → `Team_HMI.stSelMonth.*`. Its days are in `Team_HMI.aSelMonthDays[1..31].*` (`Team_HMI.iSelMonthDays` = number of valid days) |
| Selected day | write `Team_HMI.iSelDay` (0..364) → `Team_HMI.stSelDay.*` |
| All 12 months | `Team_Log.aMonth[1..12].*` (12-row table) |
| All days | `Team_Log.aDay[0..364].*` |

Daily cost has no peak component: `C_peak` is 0 and `C_total` = purchase − revenue + grid. Monthly and yearly cost includes the peak.

Official values for comparison: `SimScore.total.*` (E_fne, E_fec, E_bess_chg, E_bess_dch, E_ev, E_import, E_export, P_peak, cost_energy, cost_grid, cost_peak, cost_total).

## 5. 24 h trends (Table 13 row 7)
These are arrays `[0..95]` of REAL. **Index 95 is the newest interval (k−1) and index 0 is 24 h earlier.** They update once per simulation step.
- `Team_HMI.aTrFne` PV [kW]
- `Team_HMI.aTrFec` load [kW]
- `Team_HMI.aTrGrid` grid, + import / − export [kW]
- `Team_HMI.aTrBess` battery, + discharge / − charge [kW]
- `Team_HMI.aTrEv` EV total [kW]
- `Team_HMI.aTrSoc` SoC [%]
- `Team_HMI.aTrPrice` energy price [€/kWh]

## 6. Alarms and messages (Table 13 row 8)
Active flags (BOOL):

| Flag | Meaning |
|---|---|
| `Team_HMI.xAlmImport` | import overload, previous step |
| `Team_HMI.xAlmExport` | export overload |
| `Team_HMI.xAlmTripped` | plant disconnected (tripped) |
| `Team_HMI.xAlmFinished` | year finished |
| `Team_HMI.xAlmEvUnmet` | an EV left with undelivered energy (latched until reset) |
| `Team_HMI.xAlmGuardEv` | the guard reduced EV charging to hold the import limit |
| `Team_HMI.xAlmGuardCurt` | the guard curtailed PV to hold the export limit |
| `Team_HMI.xAlmGuardFail` | predicted import is above the limit |

History is in `Team_HMI.aAlarmHist[0..49]`, **newest at index 0**. Each entry has:
- `.k`
- `.sStamp` (simulated "DD.MM.YYYY HH:MM")
- `.iCode`
- `.sText`

Codes: 1 import overload, 2 export overload, 3 trip, 4 finished, 5 EV left with unmet energy, 6 EV charging reduced (guard), 7 PV curtailed (guard), 8 import-limit warning.

Other alarm variables:
- `Team_HMI.nAlarms`: number of messages since reset
- `Team_HMI.sLastAlarm`: last message text

## 7. Diagnostics (optional "info" screen)
- `Team_HMI.nSteps`, `Team_HMI.nCalls`
- `Team_HMI.nGuardEv`, `Team_HMI.nGuardCurt`, `Team_HMI.nGuardFail`
- `Team_HMI.nBothEnables` (must be 0)
- `Team_HMI.rGridPredErr` / `rGridPredErrMax` (|predicted − measured| grid power, kW)
- `Team_HMI.rEvUnmetSum` [kWh]
