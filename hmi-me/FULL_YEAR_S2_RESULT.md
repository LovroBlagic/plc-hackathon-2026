# Full-year HMI simulator test - S2 day-ahead

Completed 7 November 2026 with all seven HMI pages loaded and the live Trends page displayed during the run. Fresh reset, price_mode=1 (S2), cycle_time_ms=10.

- PASS: 35040 / 35040 steps, finished=TRUE, no trip.
- Logged intervals: 35040.
- Official total cost: EUR 169833.86433741; matches frozen v7 EUR 169833.86 at cent precision.
- Team logged total cost: EUR 169833.86306666.
- EV fulfilment: 99.9999999997%; unmet energy 2.82128720356e-08 kWh (roundoff).
- Maximum discrepancy across 7 energy and 4 cost totals: 3.958681115e-06% (allowed 0.1%).
- Completion observed after 428.8 s, including polling delay; not an exact finish timestamp.
- Frozen-source parity after completion: all 26 files match.

Evidence: full_year_s2_result.json, full_year_s2_start.json, full_year_s2_progress.jsonl, full_year_s2_proof.png. S1 evidence remains in FULL_YEAR_RESULT.md and full_year_result.json.

Application left online at year end with run=FALSE for inspection. No source or deliverable archive changes were necessary. Both S1 and S2 now pass full-year tests with the native HMI attached. Browser WebVisu remains untested on this simulator.
