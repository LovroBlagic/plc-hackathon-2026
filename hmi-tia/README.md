# hmi-tia: generated WinCC RT Advanced HMI for the crane (TIA task 2)

**Method (7 Nov 17:20, HMI builder agent): Openness XML import, with no hand-drawn prototypes.**
1. `proto_src.py` writes the prototype objects (`proto/`) in the real SimaticML schema. The schema was verified by importing each object type into HMI_RT_1; see "Verified SimaticML schema" below and `lab/r1.log`…`r5.log`.
2. `gen_hmi.py all --export proto --out out` clones the prototypes according to `layout.json`, producing tags, text lists, template `Tpl` and the screens.
3. `alarms_screen.py out` writes the empty `Alarms` screen.
4. `HmiLab.exe --import out --compile` imports everything. Use `--attach` to import into an open GUI TIA.
   - It imports one file at a time with the full error text and the Override option, and skips the hand-edited `Alarms` screen if it already exists.
   - It keeps `tia-work\openness.lock` alive with a heartbeat every 2 minutes.

One command, from the repo root:
```
python hmi-tia\proto_src.py; python hmi-tia\gen_hmi.py all --export hmi-tia\proto --out hmi-tia\out; python hmi-tia\alarms_screen.py hmi-tia\out
hmi-tia\HmiLab.exe --project <abs project dir> --lock hmi-builder --import <abs>\hmi-tia\out --compile [--attach]
```

### Verified SimaticML schema (WinCC RT Advanced, V21)
| What | XML |
|---|---|
| Events | `Hmi.Event.Event[Events]` (Name=Press) > `Hmi.Event.FunctionListEventHandler[EventHandler]` > `Hmi.Event.FunctionListEntry[FunctionListEntries]` (Name=SetBit, Type=SystemFunction) > `Hmi.Event.FunctionListEntryParameter[Parameters]` (Name=Tag, LinkList `<Value TargetID="@OpenLink"><Name>tag</Name></Value>`) |
| Screen change | ActivateScreen: parameter "Screen name" (Value link to the screen) plus "Object number" (`<Value Type="System.Int32">0</Value>`) |
| Appearance | `Hmi.Dynamic.RangeAppearanceAnimation[Animations]` > `Hmi.Dynamic.TagElementTrigger[RangeTag]` + `Hmi.Dynamic.Range[RangeValues]` (LowerLimit, UpperLimit, BackColor, ForeColor, FlashingType No/Medium) |
| Movement | `Hmi.Dynamic.Horizontal/VerticalMovementAnimation[Animations]` (RangeStart, RangeEnd, XPosEnd/YPosEnd, XDelta, YDelta; the start position is the object's Left/Top) > `Hmi.Dynamic.TagElementTrigger[MovementTag]` |
| Text list | `ListRange` is Decimal, Binary or Bit ("Range" is rejected) |
| Screen size | Must equal the device size. HMI_RT_1 is 1024×768, and a 1920×1080 screen aborts TIA (NonRecoverableException). `layout.json` therefore uses scale 0.5333 with device_w/h 1024×768 |
| Not importable | Alarm view (`Hmi.Screen.AlarmView` gives "not supported"); there is no Openness API for Classic discrete alarms. Screen resolution and start screen are not exposed as attributes |

Main view = the existing screen `Screen_1`, which is the device start screen, so no start-screen setting is needed. Nav "GLAVNI PRIKAZ" → Screen_1.

**Old method (superseded):** a human drew the prototypes, `HmiGen.exe --export` exported them, `gen_hmi.py` cloned them, and `HmiGen.exe --import` imported the result.

The HMI touches only DB101 `"HMI_IF"` (CONTRACT §1.3).

The human click list is in **[HUMAN_STEPS.md](HUMAN_STEPS.md)** (about 25 min).

## Files
| File | Purpose |
|---|---|
| `layout.json` | **Source of truth** (1920×1080): palette (ISA-101 grey, colour only for state/alarm), text lists, header (template), side panels, grid/list geometry |
| `gen_hmi.py` | stdlib generator. Commands:<br>• `all`: tags + text lists + screens + check<br>• `base`: tags + text lists (round 1)<br>• `check` |
| `alarms_gen.py` | 16 discrete alarms on `AlarmWord`, texts verbatim from CONTRACT §3.3. Writes xlsx (stdlib), csv and json. `--sample` reuses the header row of a TIA-exported xlsx |
| `preview.py` | wireframe PNG/SVG of the generated screens (`out\preview\`) |
| `HmiGen.cs` / `build_hmigen.ps1` | Openness tool (C# 5, .NET 4.8):<br>• `--export`: screens, templates, tag tables, text lists, connections<br>• `--import`: text lists → tags → templates → screens, Override<br>• `--compile`<br>• `--lock`<br>It prints `HMI_RESULT errors=N warnings=M` |
| `regen.ps1` | **one command:** `.\hmi-tia\regen.ps1 [-Export] [-DryRun]` |
| `mock\` | `make_mock.py` writes mock prototype exports (TextField/IOField copied from a real V21 export, everything else a best guess) for dry runs. `mock\preview\*.png` shows the current layout |

Generated (gitignored): `out\{tags,textlists,templates,screens,alarms,preview}`. Human exports (gitignored): `export\`.

## What gets generated
- **Tag table `HMI_IF_gen`:** 483 tags (v1.3), one per HMI_IF scalar plus one per array element (`Cell0_05` → `HMI_IF.Cell0[5]`, `UList_01`…). Members are parsed read-only from `tia-src/03_HMI_IF.db`, so a DB change only needs a regeneration.
  - Tag mode "element" was chosen because it needs no array-index syntax in screen links.
  - PowerTag count is 483, so it fits a 512 licence.
- **Text lists (11):** TL_State, TL_Mode, TL_Cmd, TL_Kind, TL_Phase, TL_Bay, TL_ListSt, TL_Order, TL_YesNo, TL_BalMode, TL_Alarm.
- **Template `Tpl`** (header on every screen, 49 objects):
  - UKLJ./ISKLJ. (InvertBit SwOn) with SPREMAN/ISKLJUČEN lamps
  - POČETNO STANJE
  - AUTOMATSKI/POLUAUTOMATSKI/RUČNO with active-mode bars
  - START (running bar), STOP, POTVRDA
  - SLJEDEĆI KORAK with StepWaiting bar
  - state and mode text
  - M, T, J and predicted M/T/J, transfer progress
  - alarm lamp + newest alarm (AlarmHist[0])
  - PLC heartbeat
  - navigation bar
- **Main (305 objects):**
  - Bay 1 (yard) on the left, Bay 0 (ship) on the right, with a 2-column quay gap. Global column G = HMI_IF.CraneGX.
  - 96 cells: an appearance-animated rectangle on `CellSt*` plus a transparent ID field on `Cell*`.
  - Row and column labels.
  - Ship outline split between x1 and x2, with live L/R counts.
  - Crane X marker on the rail (horizontal movement on CraneGX; it shows the carried ID) and Y marker in the quay gap (vertical movement on CraneY).
  - Current command panel, crane state.
  - Balance bars L/R with |L−R| ≤ 5 lamp, bow/stern counts.
  - Progress panel, cell colour legend.
- **Manual (298):** same grids, plus the manual command panel:
  - ManCmd (symbolic, TL_Cmd), ManX, ManY, ManBay (TL_Bay)
  - IZVRŠI (BtnManExec)
- **Lists (304):**
  - settings: CfgOrderMode, CfgSemiPerTransfer, CfgBalMode
  - unload/load lists, 48 rows each: index, ID, state text
- **Score (46, v1.3):** objective panel: actual M/T/J by the spec rule (primary, v1.7), FB1 counter MFb1/JFb1 (MD107), predicted plan M/T/J; optimisation panel: greedy J (PredJ0), improved J (PredJ), gain %, evaluations, proven lower bound LbJ and gap %, planner progress bar; order mode actually used, winning variant, N. Nav button "REZULTAT / OPTIMIZACIJA" in the template.
- **AlarmLog (49):** AlarmHist[0..15] as alarm texts, newest alarm details (ID, x, y, bay, word, count).
- **Hand-made, never regenerated:** `Alarms` (alarm view of current alarms + alarm buffer history), `Proto`.

## Regenerate after a layout change
Edit `layout.json`, then run `.\hmi-tia\regen.ps1`. It generates, checks and previews, imports with Override, and compiles.
- Check the layout without TIA: `.\hmi-tia\regen.ps1 -DryRun`, then look at `hmi-tia\out\preview\Main.png`.

## Known limits / assumptions
- Only TextField and IOField XML is confirmed from a real V21 export (`Screen_1`). Other objects are cloned from the human's prototypes, so their schema comes from TIA itself.
  - The generator patches only geometry, texts, `Tag`/`TextList` links, the `SetBit→InvertBit` / `Screen_1→<screen>` names, and a few attributes: Mode, FormatPattern, colours, fonts, Min/Max.
  - **First real import = first real test.**
- **Movement animation endpoints:** the generator patches attributes it recognises (Start/End Left/Top/X/Y) and prints the values. If the real attribute names differ, it does not matter as long as the human typed the values from HUMAN_STEPS B. Those values match the current layout; re-type them only if the grid geometry changes.
- **SLJEDEĆI KORAK is always visible** (with a StepWaiting bar), not only in SEMI. Hiding it would need a visibility-animation prototype.
- RT Advanced alarms are on HMI_IF.AlarmWord bits. Bit n = `AlarmWord.%Xn`. Check the trigger address of one alarm after import (HUMAN_STEPS C5).
