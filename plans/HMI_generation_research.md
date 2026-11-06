# HMI generation research (research agent, 6 Nov ~22:30)

## Bottom line
- **TIA (WinCC RT Advanced): generate the screens.** Use the Openness XML round-trip: export a prototype, generate with Python, import with C#. It is officially supported and ideal for the 96 grid cells.
- **Vijeo Designer: no official screen import.** Fastest robust route: the agent writes a "build sheet" from a JSON layout and the human builds it using **Duplicate with array-index increment**. Optionally time-box 30–45 min on the undocumented .hmix XML round-trip.
- **windows-mcp drawing: no.** It is too slow and fragile on MFC/WPF canvases, and it pauses whenever a human touches the input devices. Use it only for small property fixes.

## TIA V21, WinCC RT Advanced
**Verified locally:**
- `Siemens.Engineering.WinCC.dll` has the Classic API: HmiTarget, ScreenFolder/Composition, ScreenTemplateFolder, TagTableComposition.
- There is **no alarm API**.
- **TiaMcpServer hmi_read/write work with WinCC Unified only**, so they are useless for RT Advanced. We need our own C# (extend TiaRun.cs into HmiGen).
- Plugin refs `tia-import-export/references/hmi-screens.md` and `hmi-tags-and-data.md` contain C# snippets.

**Objects Openness can export/import:**
- **Supported:** line, polyline, polygon, ellipse, circle, rectangle, text field, graphic view, I/O field, graphic/symbolic I/O field, button, illuminated button, switch, date/time field, bar, gauge, clock, slider, symbol library, groups, faceplates, user view.
- **Not supported:** alarm view, alarm window, alarm indicator, f(t)/f(x) trends, screen window, recipe/table view, list/combo/check box, option buttons.

**Workflow (~2 h agent + ~20 min human):**
1. **Human, once:**
   - HMI connection to the PLC.
   - Template "Tpl" with the header buttons (ON/OFF, READY, INIT, AUTO/SEMI/MANUAL, START/STOP/ACK).
   - An "Alarms" screen with an alarm view; it is never regenerated.
   - A prototype screen with one grid cell (rectangle + appearance animation, I/O field for the ID, text) and one button with a SetBit event.
2. **Agent, HmiGen.exe --export:**
   - `HmiTarget = (HmiTarget)deviceItem.GetService<SoftwareContainer>().Software`
   - `screen.Export(FileInfo, ExportOptions.WithDefaults)`
   - `TagTables.Export`
3. **Agent, Python generator:**
   - `layout.json` → `tags.xml` (96+ tags, ControllerTag `HMI_IF.grid1[r,c]`; quote names with dots)
   - `layout.json` → `Grid.xml` (96 cell groups, unique IDs, Left/Top, tag links)
4. **Agent, HmiGen.exe --import:**
   - `TagTables.Import(tags.xml, Override)`, then `Screens.Import(Grid.xml, Override)`
   - compile the HMI with `ICompilable`, then save
   - To relayout: edit the JSON and rerun.
5. **Alarms:** export one hand-made discrete alarm to .xlsx, generate the rest with openpyxl (`pip install openpyxl`), and a human clicks Import (3 clicks). Or type about 10 alarms by hand.

**Risks:**
- Advanced ES licence/editing: verify that a screen can be edited and compiled.
- **Override replaces the whole screen.** Never hand-edit generated screens.
- Tags and template must exist before import.
- XML IDs must be unique.

**Cheap fallback:** the PLC formats each grid row as a STRING, so only 8 I/O fields are needed, without per-cell colour.

## Machine Expert + HMIG2U, Vijeo Designer 6.3.2
**Verified locally:**
- No scripting or command line for screens. The CLI handles runtime data only.
- **Documented imports cover variables only:**
  - variables as XML/CSV/TXT; XML includes the alarm flag
  - Target export `.hmix` (alarms, logging, variables, languages)
  - `.vdz` project import/export
  - Toolchest with `$placeholder$` variables
- **Undocumented:** `Vijeo-Frame\XML\public.xsd` is a full project schema including panels. XML import code exists in INDEXMLImport.dll and INDEFileManager.dll. Panel import is unconfirmed.
- The ME .project embeds the HMI as an **opaque blob**. Do not edit it outside the GUI.
- ME has **File → Import Vijeo-Designer project (.vdz)**, which replaces the HMI application. Check the menu in V2.3.

**Recommended (~3–4 h human with agent support):**
- The agent writes a panel build sheet from a JSON layout.
- The human uses:
  - a **master panel** for the sim-control header
  - **Duplicate** with rows × columns, "Increase Variable Name/Array Index" and X/Y offset: 4 EVs `aEv*[j]`, 12 months `aMonth[1..12]`, 31 days
  - **XY Graph** (≤ 256 samples from arrays, 8 arrays per graph) for the 96-sample trends `aTr*[0..95]`. Add a constant X array 0..95 in Team_HMI and trigger on change of `SimCtrl.k`. **Do not use the Vijeo data-logging trend**, because it runs on real time.
  - **Alarms:** tick "Alarm" on BOOL variables, or Export Variables XML → edit → Import (overwrite). Then add an Alarm Summary part.
- **Optional XML experiment (30–45 min):**
  1. Draw one panel with all object types.
  2. Export the Target as single XML (.hmix) and check for `<Panel>`.
  3. If present: generate panels in Python, import into a standalone Vijeo project, export .vdz, then ME → Import Vijeo-Designer project, and re-check variable links.
- **Probe for the ME worker when the engine is free:** `export_native` of the "HMI Application" object.

**Alternative: CODESYS Visualization / WebVisu** (only if the organizers accept it instead of HMIG2U):
- No visu API in the stubs, but `export_native`/`import_native` carry visu objects.
- ME ships Visualization 4.6 with **HTML5 custom elements (JS)** supported.
- Route: create one visu in the GUI, `export_native`, generate in Python, `import_native`. The format is undocumented: 2–3 h, medium risk.

## Effort summary
| | Automate | Human clicks | Time | Main risk |
|---|---|---|---|---|
| TIA | tags + 96-cell screens (Openness XML), compile | template, alarm screen, prototype cell, alarm xlsx import | ~2 h agent + 20 min human | Advanced ES licence; Override wipes hand edits |
| Vijeo | build sheet, variable XML (alarms) | drawing with master panel + Duplicate + XY Graph | 3–4 h human (+45 min optional XML experiment) | XY Graph on HMIG2U unverified; .hmix import unconfirmed |

Vendor help extracted locally (NOT in git) at `research/hmi/vjdhelp/`. Useful pages: Draw\Duplicate.htm, Graphs\XY_Graphs.htm, InputAddress\csv_files.htm, EfficientOperations\Exporting_Targets.htm, EfficientOperations\Template_Objects.htm.

## Sources
- Openness V21 exportable screen objects: https://docs.tia.siemens.cloud/r/en-us/v21/tia-portal-openness-api-for-automation-of-engineering-workflows/export/import/importing/exporting-data-of-an-hmi-device/screens/overview-of-exportable-screen-objects
- Openness export screen: https://docs.tia.siemens.cloud/r/en-us/v21/tia-portal-openness-api-for-automation-of-engineering-workflows/export/import/importing/exporting-data-of-an-hmi-device/screens/exporting-a-screen-from-a-screen-folder
- Importing alarms (xlsx), RT Advanced: https://docs.tia.siemens.cloud/r/en-us/v21/using-global-functions-basic-panels-panels-comfort-panels-rt-advanced-rt-professional/importing-and-exporting-project-data-basic-panels-panels-comfort-panels-rt-advanced-rt-professional/importing-and-exporting-alarms-basic-panels-panels-comfort-panels-rt-advanced-rt-professional/importing-alarms-basic-panels-panels-comfort-panels-rt-advanced
- SE FAQ .hmix: https://www.se.com/ca/en/faqs/FA231435/
- SE FAQ .vdz: https://www.se.com/ca/en/faqs/FA290366/
- ME File menu, Import Vijeo-Designer project: https://product-help.schneider-electric.com/Machine%20Expert/V1.1/en/SoMMenu/SoMMenu/File_Menu/File_Menu-11.htm
- CODESYS forge, native export carries visu: https://forge.codesys.com/forge/talk/Visualization/thread/35ee036484
- TiaMcpServer HMI ops (Unified only): https://github.com/Czarnak/tia-portal-mcp/blob/main/docs/SupportedOperations/HMI_OPERATIONS_SUMMARY.md
