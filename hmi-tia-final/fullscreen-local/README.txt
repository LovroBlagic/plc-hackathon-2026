TIA CRANE - FULLSCREEN DEMO V4

Complete PLC + HMI project: TIA_HMI_fullscreen_final_v4.zap21.
Engineering: TIA Portal V21. Native HMI: WinCC Runtime Advanced V17.

DISPLAY-SPECIFIC VERSION
This fullscreen variant is tested on this laptop at2880x1800 with Windows200% scaling. Native layout1440x900; process-scoped DPIUNAWARE launch scales it to the full display. Normal TIA simulation without the launcher does not give the same font/layout scaling. The separately preserved v3 archive is the standard1920x1080 portable baseline.

LOCAL DEMO
1. Existing dedicated PLCSIM instance crane_hmi_side must be running with this project's PLC code.
2. Open the project in TIA. Compile HMI > Software(rebuild all), then start simulation once.
3. Double-click Start-Fullscreen.cmd. It restarts only the runtime matching this project path; PLC state is retained.
4. For a retrieved project in another folder, run Start-Fullscreen.ps1 -ProjectDirectory 'C:\path\to\project-folder'.

The launcher changes only the child process environment. No Windows display settings or registry entries are modified. Do not move generated runtime files to a standalone folder; that copied-runtime experiment was not reliable. Generate them from the project instead.

VERIFICATION
PLC and HMI compile:0 errors,0 warnings.
Original starter DBs: exact fresh-download input arrays checked. N10,zero valid transfers,M0,T0,J0;7 missing unload IDs and3 missing load IDs. Python result identical.
Fuller synthetic rand_01:27/27 transfers,M130,T2503.2002,J~1.211793; both final grids match Python. This matches our planner configuration, not a proof of a global optimum.
Blink fix:240 samples across96 stationary cells,zero colour changes;27 non-base coloured cells included.
AUTO and SEMI STOP/resume,manual PUT,alarm ACK/history,and navigation tested. All six v4 pages visually reviewed.
Physical hardware and unseen organizer judging inputs were not tested.

Project start values remain the original starter data. The fuller dataset was loaded ONLINE for testing only. TEST_RESULTS.json records the comparisons.
