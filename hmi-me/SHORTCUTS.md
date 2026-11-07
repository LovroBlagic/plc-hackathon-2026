# Machine Expert WebVisu: working shortcuts

Keep this file current as new techniques are verified. Paths below are relative to `hmi-me/`.

## Verified: generate native visualization elements

1. Create one real element in the Visualization editor, configure its text and variable, save and close the project.
2. Export it with `obj.export_native(path)`. **`export_xml()` silently omits visualization objects** here: it returned a valid 1503-byte PLCopen project containing no visualization.
3. Parse the native export as XML, clone the editor-created element and change its member values. Preserve its type identifiers; give each clone its own element identifier, ID and identification GUID.
4. Import with `app.import_native([absolute_path])`. In the HMI copy, remove the previous Overview first to avoid a replace-conflict prompt.
5. Compile and inspect the editor rendering. This was verified for the 19-element Overview: **HMI_BUILD_RESULT errors=0**, and the elements were visible when reopened.

Scripts: `export_seed.py`, `generate_overview.py`, `import_overview.py`.
Templates: `Overview.export`, `Visualization_Manager.export`.
Generated file: `Overview_generated.export`.

### Rectangle member IDs observed in this installed version

These IDs come from our editor-created seed; they are not a portable API contract.

| Member ID | Meaning |
|---|---|
| 1649127785 | X |
| 357335551 | Y |
| 2422045748 | Width |
| 2134141914 | Height |
| 550940142 | Centre X |
| 1473355128 | Centre Y |
| 390574330 | Text, e.g. `SIM TIME: %s` |
| 2477733581 | Text variable, e.g. `Team_HMI.sDateTime` |
| 4253639993 | Font-size member; also inspect nested FontSize/style values |
| 823443203 | Text identifier in this seed; use distinct values for clones |

## Verified: find the right project tree

- **Tools tree** shows Overview, Visualization Manager and WebVisu. The Applications tree filters these out.
- View → Navigators → Tools tree.
- Visualization Manager → right-click → Add Object → WebVisu.
- The WebVisu target automatically picked `Overview` as its start visualization and `webvisu` as the HTML filename.
- Isotropic scaling preserves proportions. Selected and saved in this project.
- A `%s` or `%.1f` placeholder in the offline editor is expected; live substitution still requires runtime verification.

## UI automation: useful but not fully reliable

- `ui_inspect.ps1` reads UI Automation names, rectangles and patterns. Tree nodes support ExpandCollapse and SelectionItem patterns; expanding the application by name worked.
- Names can be duplicated between tabs and tree nodes. Selecting the first `WebVisu` match can hit a pane with no supported pattern. Filter by control type/pattern when extending the helper.
- Context-menu UIA names were incomplete/misaligned with the visible menu. An invocation labelled Visualization opened Relocation Table. **Inspect a screenshot and use the observed menu position for those menus.**
- Screenshots need DPI awareness; without it only the upper-left part of the desktop was captured. `SetProcessDPIAware()` is in the helper.
- **Never send keys unless the foreground process is LogicBuilder.** A focus change sent a variable name into the chat once. The helper now checks and refuses input outside Machine Expert.
- AppActivate/SetForegroundWindow do not always acquire focus. A refusal is preferable to typing into the wrong app. `root.SetFocus()` sometimes reports that the element cannot receive focus; it is not a reliable shortcut.
- A tree selection does not necessarily move keyboard focus; Shift+F10 after selection alone did not open the intended context menu.
- Property cells can require F2 before editing. Text is multiline: click another property to commit; Enter may add a newline.
- SendKeys treats `%` as Alt: send `{%}` for a literal percent character. Prefer direct value patterns when available.
- Let saves and dialog transitions finish before clicking the next control. Inputs sent immediately after Ctrl+S were sometimes ignored. Mouse helper currently waits 350 ms after an action; use observed UI readiness for longer operations.
- The native export shows the actual stored binding, so check it instead of assuming a GUI entry succeeded.
- Shrink the toolbox thumbnails: drag its bottom zoom-slider thumb all the way left. This exposes several controls at once; the Button appeared without scrolling through huge thumbnails.
- A native Button has Input configuration → Toggle → Variable. Its first attempted `SimCtrl.run` entry **did not persist** in native export. Do not treat the configured-looking GUI/label as evidence: verify the actual binding in the exported XML, then test it online. The Toggle group row and its child Variable row are different; inspect the current row coordinates after expansion/scroll.
- To open a tree object reliably, single-click its visible row then Enter. Avoid slow double-clicks (rename) and do not assume Invoke on the first matching name targets the tree object.
- Headless runs can leave an autosave recovery prompt visible when another copy is opened. Decline unrelated recovery data when starting from a deliberate saved copy.
- Closing the saved HMI window through UIA WindowPattern.Close worked without keyboard focus. Keep desktop input guarded separately from background UIA actions.
- Launching another LogicBuilder GUI while a headless simulator session was holding coincided with a lost connection on shutdown. Avoid concurrent simulator ownership; only one session should drive the runtime. The live short-run values were already captured before this happened.

## Not yet verified

- Browser connection to this Machine Expert simulator.
- Run/pause and other writable controls.
- Worst-case visualization overhead and unchanged full-year results with the HMI attached.
- Font-size/style precedence in generated native elements.

## Runtime observation: browser test, 7 Nov afternoon

- The 19-element HMI + WebVisu project compiled and downloaded to the built-in ME simulator with 0 errors.
- A short run reached k=1151 with `tripped=FALSE`; date/time, SoC, grid prediction and cost variables were readable online.
- Web assets were generated under `C:\ProgramData\CODESYS\Simulation\PlcLogic\visu`, including `webvisu.htm`, configuration and JavaScript.
- **No HTTP listener was present.** The simulator process listened only on 127.0.0.1:11739; `http://localhost:8080/webvisu.htm` refused connection. Generated web files alone do not establish browser support.
- Do not claim the browser HMI works, or serve static files and mistake that for live PLC connectivity. Investigate a supported controller runtime or use the native online visualization editor for the simulator test.

## Verified: export directly inside the open editor

- View → Scripting → Scripting Immediate, then select its bottom tab.
- Its command line accepts `execfile(r'C:\absolute\script.py')` and Enter.
- `projects.primary` accesses the currently open GUI project. Guard its `.path` before changing it.
- `export_in_editor.py` saved ControlSeed and exported `Controls_bound.export` without restarting the engine.
- The corrected export contains `ConfiguredComplexInputs` → `Visu_ToggleInput` with member **1186196937 = SimCtrl.run**. This is the actual button binding; the `<toggle/tap variable>` placeholder elsewhere is not the input action.
- Paste script commands via Clipboard/Ctrl+V after the foreground check; this preserves parentheses, braces and percent characters instead of interpreting them as SendKeys syntax.
- Export/build operations may automatically select the **Messages** pane. Before the next console command, explicitly select the **Scripting Immediate** bottom tab again, then its input line. Otherwise the command is pasted into the wrong pane and never executes.
- **Clicking an HMI button online can switch the bottom pane to Watch 1 as well.** Reselect Scripting Immediate after each click before pasting a diagnostic command. Two diagnostic strings were accidentally added as watch expressions; they were not executed as code.
- Direct online control verification succeeded: clicking the imported generated Button set `SimCtrl.run=TRUE` (k=2746), then clicking again paused. Two reads 2 seconds apart held k=5675 with run=FALSE and no trip. The HMI project's 26 team source files also matched frozen v7.

## Recovery: stalled native dashboard import
- Importing all seven generated pages hit a font-style assertion. Ignoring it left the editor unresponsive with zero CPU progress over 10 seconds. User authorized closing the HMI process and reopening the saved HMI project. Do not retry the same bulk import until a small corrected-style page compiles. The custom-style Null encoding remains unverified.


- Isolated three-element StyleProbe reproduced the assertion. Null font CanonicalName fails GenerateFontDescriptionInitializationIf; preserving Font-Standard advanced to a different assertion in GenerateStyleColorAssignment for Null colour CanonicalName. Both null/empty names are invalid in these typed named-style objects. Obtain the editor's custom-colour representation before bulk import. Probe changes were unsaved and discarded; saved prototype preserved.


## Editor-exported custom styles (7 Nov)
- Save the project before native export: unsaved editor property changes were absent in export_native output until p.save().
- A custom colour is a Single Type=uint ARGB scalar INSIDE the member's Value ArrayList; it is not a named-colour object with an empty/null CanonicalName.
- A custom font uses type GUID 896a5e54-96c3-433b-96d2-4f1442fef591 and no CanonicalName; the named font seed uses 9e842eb2-1463-4af2-b605-4fbb17044f94. Custom_style.export is the editor proof.
- The corrected three-element StyleProbe imported and reached normal compilation without assertion. Its compile errors came from an old input-dialog title on Overview; titles are ST expressions and need quoted string literals.
- Widen the Properties dock by dragging its left separator left. Otherwise the colour/font ellipsis selector is clipped beyond the narrow value column. F2 opens the property editor; allow a separate call before clicking its ellipsis.


## Seven-page build
- All seven generated pages (529 elements) built with 0 errors, one known CheckBounds warning after preserving typed named-style colour objects inside XY chart packets. Primitive colours use uint, but XY packet fields need their named-style representation. Changing chart fields to uint produced six ComplexElemInit errors; restoring valid named-style objects resolved them.
- Each cloned chart now has unique LMGuids. A rebuild alone did not resolve the six chart errors.
- Offline appearance exposed default font NamedColor overriding ExplicitColor; removing the entire NamedColor reference in custom fonts is being tested. Do not mark this readability fix verified yet.


- A later bulk replacement stalled with Overview open and a font-colour property selected. The saved seven-page build was already 0 errors. Close visualization editors/property edits before replacing objects; this is a suspected deadlock trigger, not yet proven. Recover from the saved HMI copy, not autosave recovery.


- VERIFIED readability fix: custom-font NamedColor must be a Null reference for ExplicitColor to control normal text colour. Nulling the entire NamedColor is valid; nulling CanonicalName inside a named-style object is invalid. With this change, white headings and coloured labels rendered correctly and the full build stayed 0 errors.
- Retrying replacement with the WebVisu configuration tab open (no visualization editor open) succeeded. Import completed in about 9 s; build completed about 32 s later. dashboard_import_stage.log records exact phases.
- Rechecked frozen-source parity after the complete HMI import: all 26 frozen v7 files matched.


## Simulator acceptance observations (seven-page version)
- Actual RUN/PAUSE clicks advanced then paused at k=937 with no trip. Live power, SoC and price graphs displayed 96 historical samples; native navigation opened all seven pages.
- Energy day/month selector clicks changed iSelDay to 1 and iSelMonth to 2. Important: frozen Team_HMI.stSelDay/stSelMonth copies refresh only when the simulation steps. Bind tables directly to Team_Log.aDay[iSelDay]/aMonth[iSelMonth] so paused selection updates immediately. This correction is being rebuilt.
- Actual controls changed price_mode=1 and cycle_time_ms=20. Alarm pagination changed iAlarmPage=1. Reset cancellation left k=937 and xResetArmed=FALSE; confirmed reset then set k=0. Team HMI/log values still represent the prior run until Team_Main is called again by starting simulation; preserve frozen source behavior.
- Online perspective bottom tabs moved slightly: Scripting Immediate at physical (130,1645), not y=1636 (border). Select it explicitly before pasting commands; input line around (900,1580).
- Chart named-style colours override explicit numeric colour values. Use distinct known built-ins and draw matching legend swatches; final correction maps FNE yellow, FEC blue, grid red, BESS green, EV black.


- FINAL paused-table check passed: at k=228 / 03 Jan, day 2 changed from day 1 totals immediately and February energy/cost columns were zero while year totals were populated. Trends displayed distinct yellow/blue/red/green/black curves matching legend swatches.
- Build message collection must filter categories Build and Additional code checks. An old Visualization-category 'Cannot enumerate subtags on a data tag' after logout persisted across builds; it was not a compiler error. dashboard_messages.log retains all categories; dashboard_build.log records compiler categories only.
- IronPython execfile shares globals. A helper can overwrite base paths used by its caller. Keep a uniquely named acceptance_dir or use absolute paths for subsequent helper calls.
- Drag the Interface Editor/visualization divider from physical (1428,530) to (1428,249) to collapse the declaration pane and expose the HMI. On-screen HMI geometry is then about 2 physical pixels per configured unit with origin (412,252).


## Full-year HMI run (7 Nov)
- Completed HEP mode 0 at 10 ms with Trends active for most of the run: 35040 steps/logged intervals, no trip, official EUR 204598.62193357, effectively 100% EV delivery. Max energy/cost logging discrepancy 0.000005244797%. Frozen-source parity 26/26 after run. Evidence FULL_YEAR_RESULT.md and full_year_result.json.
- Keep GUI scripts short while testing visualization overhead: start/reset in one command, return to the GUI message loop, then poll from separate commands. A long GUI-script sleep loop would prevent HMI rendering and would not test live visualization overhead.
- Runtime values are read sequentially, so moving-run snapshots are not atomic (k and nLogged may differ by ~100 steps between reads). Compare official/logged totals only after finished=TRUE and k=35040.
- Dock layouts can move Scripting Immediate input from y=1580 to y=1620. Inspect Go! button rectangle or a screenshot before typing. The last layout had Go! at (2198,1602,78,44), input around (900,1620). Closing the console removes its tab; reopen via View > Scripting > Scripting Immediate before another poll.


- S2 full-year native-HMI run also passed: day-ahead mode 1 / 10 ms, 35040 steps/logged intervals, no trip, official EUR 169833.86433741, effectively 100% EV delivery, max logging error 0.000003958681%. S1 evidence retained; S2 uses separate full_year_s2_* files and FULL_YEAR_S2_RESULT.md.
- Scenario-specific polling explicitly reads and asserts SimCtrl.price_mode=1, so a wrong scenario cannot silently pass. Keep each scenario's start/progress/result files separate.


- Cosmetic revision v2: upper bus stem originally y=250..404 protruded above the horizontal line y=294. Set y=294,height=110 so it begins at that line. Removed the shared footer in Scene.header and the Overview explanatory footer; 521 elements remain. Build 0 errors, frozen-source parity 26/26. Versioned archive v2 preserves the prior dashboard archive and full-year evidence.

