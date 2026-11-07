# ME WebVisu HMI

User selected WebVisu and froze optimisation at v7 on 7 November 2026.

## Working copy and safety

`ME_v7_WebVisu.project` is the HMI copy. Frozen `deliver/ME_v7_capfloor.projectarchive` and the 26 strategy sources have not been edited by this HMI work.

Fallback: `deliver/ME_v7_WebVisu_overview_prototype.projectarchive` (20-element numeric Overview). Its actual RUN/PAUSE button passed a mouse-click simulator test; the 26 source files matched frozen v7.

## Current implementation

Seven native pages have been generated, imported and saved: Overview, EVs, Trends, Energy, Costs, Alarms, Controls. They contain 521 elements with colour-coded flows, battery and EV bars, 24h charts, day/month/year tables, alarm history and simulation controls. Date/time appears on every page.

The complete seven-page HMI builds with **0 errors**, one existing CheckBounds warning. Custom fonts/colours render correctly. Chart legends now match five distinct line colours. Day/month tables bind directly to log entries and update while paused.

## Verification completed

- Actual mouse clicks verified RUN/PAUSE; first run paused at k=937, final run at k=228. Final k remained stable for 2 seconds, no trip.
- All seven pages opened through native navigation; power, SoC and price charts showed 96 live historical samples. EV bars/statuses and monthly cost chart rendered.
- Period input changed to 20 ms and Apply Period was clicked. Price-mode selection read back 1 (day-ahead). Day/month selection read back 1/2, alarm pagination read back 1.
- Reset cancellation preserved k=937; confirmed reset set k=0 and cleared the confirmation flag. Frozen Team_HMI/log values refresh on the next simulation step, so prior-run displays can remain until RUN.
- Paused table correction verified: selecting February produced zero monthly energy/cost values immediately while January/year totals remained populated.
- Final frozen-source parity passed for all 26 files.
- Acceptance receipt: `dashboard_acceptance.log`; categorized compiler evidence: `dashboard_messages.log`; runtime readbacks: `dashboard_runtime.log`.
- Screenshots: `energy_paused_proof.png`, `trends_online_proof.png`, `costs_online_proof.png`.

## Deliverable

The full dashboard archive is `deliver/ME_v7_WebVisu_dashboard_v2.projectarchive`; its completion receipt is `dashboard_archive_v2.log`. The numeric prototype and frozen optimizer archive are retained separately.

To test with the built-in simulator: open `ME_v7_WebVisu.project`, enable Online > Simulation, log in/download, start the application, open Overview and press RUN / PAUSE. Before replacing generated visualizations, close visualization editor tabs and leave the WebVisu configuration tab open. The generated target canvas is 1024x768; the native editor may require scrolling at 100% desktop zoom.

The archive is saved with simulation mode off for the configured controller. The full-year HEP (mode 0, 10 ms) run with this complete HMI attached passed: 35040 steps, no trip, effectively 100% EV delivery, EUR 204598.62 official cost, maximum logging error 0.000005245%. See FULL_YEAR_RESULT.md and full_year_result.json. The S2 day-ahead full-year run also passed: 35040 steps/logged intervals, no trip, effectively 100% EV delivery, EUR 169833.86 official cost, maximum logging error 0.000003958681%. See FULL_YEAR_S2_RESULT.md. Browser testing remains untested. Frozen optimizer sources remain unchanged.

## Browser limitation

WebVisu is configured with Overview as its start page and isotropic scaling. The earlier simulator build/download succeeded and generated web assets, but no HTTP listener was exposed (only simulator port 11739). Browser access is not verified. User has simulator only now and may receive a physical PLC later. Use native online visualization for current testing.

## Recipes and evidence

`SHORTCUTS.md` records verified procedures and failed attempts. Native export/import preserves visualization objects; PLCopen XML did not. GUI input is guarded by foreground process ID. `generate_dashboard.py` produces the native pages and `apply_dashboard_in_editor.py` imports/builds in the open HMI editor.

## Cosmetic revision v2 (7 Nov)

Shortened the vertical pipe above SABIRNICA to start at the horizontal bus (y=294), removing the unconnected upper stub. Removed the shared English footer from all seven pages and the Overview interval/sign explanatory footer. Build: 0 errors, existing CheckBounds warning. All 26 frozen sources still match. Previous full-year S1/S2 evidence is retained; these geometry/text-only changes were not subjected to another full-year run. Original dashboard archive retained separately.
