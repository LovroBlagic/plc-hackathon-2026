# Full-year HMI simulator test - HEP mode

Completed 7 November 2026 with the complete seven-page HMI loaded and the live Trends page open for most of the run. Restarted from zero after the user inspected/paused the earlier attempt. Test mode 0 (HEP two-tariff), period 10 ms.

- Finished: 35040 / 35040 steps; no trip.
- Logged intervals: 35040.
- Official cost: EUR 204598.62193357; matches frozen v7 EUR 204598.62 at cent precision.
- Team logged cost: EUR 204598.62052681.
- EV fulfilment: 99.9999999997%; unmet energy 2.82128720356e-08 kWh (numerical residue).
- Largest logging discrepancy across 7 energy and 4 cost totals: 5.244796969e-06%; tolerance 0.1%.
- Completion observed after 396.3 seconds; this includes the polling interval, not an exact finish timestamp.
- All 26 frozen v7 source files matched after the run.

Evidence: full_year_result.json (final official/logged values), full_year_progress.jsonl (snapshots, including prior interrupted attempt), full_year_start.json (latest run start), full_year_proof.png (year-end HMI).

The application remains online at year-end with SimCtrl.run=FALSE for inspection. The archive was not rewritten because no project/source changes were needed for the test. Browser WebVisu remains untested on this simulator. This file records S1 only. S2 was subsequently rerun successfully; see FULL_YEAR_S2_RESULT.md.
