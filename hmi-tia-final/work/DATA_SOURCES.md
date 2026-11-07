# Data used by the HMI

The HMI communicates with the S7-PLCSIM CPU through the project HMI connection. Grid IDs, states, counters and alarms are live PLC data, not animation-only placeholders.

The two-container runtime_demo.json was created locally for focused HMI testing. It is not official competition input.

The organizer archive includes starter values; CONTRACT.md records these as a toy alarm-test set with IDs such as 123/326/987 and lists containing missing IDs. These were preserved as offline project start values. The task PDF (physical page 10, printed page 9, section 2.2) says testing uses DB10/DB11 for bay states and DB20/DB21 for load/unload lists, and operations start through the HMI.

For broader runtime verification we load tools/crane_data/rand_01.json ONLINE into those same input DBs: ship 35 containers, yard 24, requested transfers 27. This is a synthetic regression dataset, not official hidden judging data. Expected results are computed independently with the existing Python model and saved in rand01_expected.json. No synthetic input is written into the submission project start values.

The final judges input dataset is not available here. We cannot claim a run against that dataset.
