# TIA GUI steps done with windows-mcp (orchestrator notes)

Recorded while driving TIA Portal V21 by windows-mcp, so the next run (agent or human) is faster.
Each step: what was clicked, where it lives in the GUI, gotchas, and whether a script shortcut exists.
Screen: laptop display, TIA window maximised.

## Session 1 (7 Nov ~17:00): hmibuild project, HMI connection + resolution
- Project: `tia-work\hmibuild\PLC_hackathon_2026_V21\PLC_hackathon_2026_V21.ap21`
- Lock: `tia-work/openness.lock` = `orchestrator-gui <time>` while the GUI is open.

(steps appended below as they are done)

### Tool: `tools/gui/gui.ps1` (use this when windows-mcp is stuck)
- windows-mcp went into a permanent `CONTROL_UNAVAILABLE` state (17:15) while TIA was loading, so I switched to our own user32 clicker.
- **Use `seq` to batch actions in one process** (each PowerShell start costs ~20–40 s on this loaded laptop):
  `powershell -NoProfile -ExecutionPolicy Bypass -File tools\gui\gui.ps1 seq "click 450 222 | wait 800 | keys {F2} | type P_SwOn | keys {ENTER} | wait 2500 | shot"`
  Then read `tia-work\gui\shot.png`.
- **Typing into TIA tables:** click the cell, press `{F2}`, type, then commit with `{TAB}` or `{ENTER}`. Without F2 the text is lost.
- **Start TIA with the project:** `Siemens.Automation.Portal.exe <path.ap21>` (about 2 min). The "Improve TIA Portal" dialog appears on first start: click "Continue with essential only" (≈693,522). Then "Project view" (bottom left, ≈88,714).

### Steps done (17:20–17:42), coordinates at 1366×768 with the TIA window maximised
1. **Project tree:** expand PC-System_1 (arrow ≈51,259), then HMI_RT_1 (≈69,316). Children: Device configuration, Runtime settings (≈162,354), Screens, Screen management, HMI tags (≈87,411), Connections (≈150,430), HMI alarms.
2. **Connections editor:** `HMI_Connection_1` already exists (SIMATIC S7 1500, partner PLC_1). No action needed.
   **So the Openness error `set_ControllerTag not supported` is NOT caused by a missing connection.**
3. **HMI tags → Default tag table** (≈188,468, double-click):
   - Existing tag `time` → PLC tag `time` (bound).
   - Added `P_SwOn`: `<Add new>` cell → F2 → name → Enter. Connection is filled in automatically (HMI_Connection_1). In the PLC tag cell (≈1040,222): F2 → `HMI_IF.SwOn` → TAB. Data type becomes Bool. Bound OK.
4. **Save:** Ctrl+S (click into the editor first).
5. **Runtime settings → General → Screen resolution:** a dropdown, currently 1024x768. **Kept** (the laptop is 1366×768; the generator scales 0.5333).
6. **Tag export to Excel:** tag table toolbar, 2nd icon "Export" (≈363,139) → dialog "Export HMI tags": path field (≈670,358) → Export (≈762,411).
   - Output: `hmi-tia/export/HMITags_sample.xlsx`.
   - Sheet "Hmi Tags", 33 columns; sheet "Multiplexing".
   - PLC tag syntax: `HMI_IF.SwOn`.
   - Default acquisition cycle is "1 s".
   - The 3rd icon (≈388,139) is "Import".

7. **Openness attach to the running GUI** (HmiLab/HmiGen without --headless):
   - TIA shows "Openness access (0033:000666)". Click **"Yes to all"** (≈806,464) to save the authorisation for that exe.
   - Done 17:53 for `hmi-tia\HmiLab.exe` (user clicked).
   - A **modal dialog left open in the GUI (e.g. "Export completed", OK ≈810,414) blocks the attach.** Close every dialog before an agent attaches.
   - TIA starts 2 helper `Siemens.Automation.Portal` child processes under the GUI process. That is normal and does not mean a second instance.

### GUI import route (much faster than the Openness XML route)
Agents generate the xlsx (tags: `hmi-tia/tags_xlsx_gen.py`; alarms: `hmi-tia/alarms_gen.py`), then one GUI import each. See `hmi-tia/GUI_IMPORT.md`.
