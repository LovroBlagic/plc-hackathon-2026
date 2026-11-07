# GUI import of generated HMI files (TIA V21, PC-System_1 / HMI_RT_1)

Why: Openness XML import of HMI tags cannot set the PLC tag link (`set_ControllerTag` not supported). The TIA GUI
xlsx import of the HMI tag editor does set it.

## 1. HMI tags (492 tags, table HMI_IF_gen)
File: `hmi-tia\out\xlsx\HMI_IF_gen_tags.xlsx` (regenerate: `python hmi-tia\tags_xlsx_gen.py`, must print `CHECK OK`).

Format is a copy of the GUI export `hmi-tia\export\HMITags_sample.xlsx`:
- sheet `Hmi Tags`, 33 columns, plus an empty sheet `Multiplexing`
- Path = `HMI_IF_gen`, Connection = `HMI_Connection_1`
- PLC tag = `HMI_IF.SwOn` (no quotes); array elements are `HMI_IF.Cell0[5]` with the HMI name `Cell0_05`
- Access Method = `Symbolic access`
- Acquisition mode = `Cyclic in operation`, cycle = `100 ms`
- Length and Coding come from the type:
  - Bool, SInt, USInt: 1, `Binary`
  - Int, UInt, Word: 2, `Binary`
  - DInt, UDInt: 4, `Binary`
  - Real: 4, `IEEE754`
- Every other column keeps the sample's defaults (`<No Value>`, `None`, `False`, the scaling values 10/0/100/0).

Steps:
1. Project tree → PC-System_1 → HMI_RT_1 → HMI tags. Create the tag table **HMI_IF_gen** first: Add new tag table, then rename it. The Path column names the target table. Import should create a missing table, but creating it first is safe.
2. Open **Show all tags** or the HMI_IF_gen table. In the editor toolbar, click **Import** (the icon with the arrow into the table, next to Export).
3. In the dialog, choose the file `...\hmi-tia\out\xlsx\HMI_IF_gen_tags.xlsx` → Import. Wait: 492 rows take some seconds to a minute.
4. Check:
   - The Inspector / import log shows no errors (the log is in the Info tab).
   - The tag `Cell0_05` shows PLC tag `HMI_IF.Cell0[5]` and connection HMI_Connection_1.
   - The PLC tag column has no red entries.

Gotchas:
- The DB must be compiled in the PLC with this exact interface (v1.7 HMI_IF, MFb1/JFb1 included), or the PLC tag links stay unresolved (red).
- If tags with the same name already exist (from the Openness XML import without links), **delete them first**. TIA may overwrite them or report duplicates, depending on the version. The safest way is to delete the old HMI_IF_gen table, recreate it empty, then import.
- The `P_SwOn` tag that was made by hand is in Default tag table. It does not collide with `SwOn`.
- The screens were generated against these exact names (`out_notags\referenced_tags.txt`, 485 names, all present). Import the tags **before** importing or regenerating the screens, so the screen tag references resolve.

## 2. Discrete alarms (18 alarms, AlarmWord + AlarmWord2)
File: `hmi-tia\out\alarms\crane_alarms.xlsx` (regenerate: `python hmi-tia\alarms_gen.py`).

Steps:
1. HMI_RT_1 → **HMI alarms** → tab **Discrete alarms** → toolbar **Import** → choose crane_alarms.xlsx.
2. The trigger tags `AlarmWord` and `AlarmWord2` and the ack tags `AlarmHmiAck` and `AlarmAckWord` must already exist as HMI tags. They are in HMI_IF_gen, so import the tags first.
3. Check alarm 4: trigger tag AlarmWord, bit 3, class Errors.

Gotchas:
- The headers are a best guess (sheet `DiscreteAlarms`, 14 columns). The GUI tag export uses `<No Value>` with a capital V, but alarms_gen.py writes `<No value>` for empty ack tags and group. Before the real import, **export one hand-made discrete alarm** to `hmi-tia\export\Alarms_sample.xlsx`, then run `python hmi-tia\alarms_gen.py --sample hmi-tia\export\Alarms_sample.xlsx`. That reuses the real sheet name and headers. Also make the placeholder match what the sample shows, and leave blank whatever the sample leaves blank.
- The alarm text column header contains the culture (`[en-US]`). The texts are Croatian, but they go into the en-US column, which is the project's editing language. That is fine.
- Class names `Errors` / `Warnings` must exist as alarm classes. These are the RT Advanced defaults.

## 3. Text lists
- WinCC Advanced has **no xlsx Import button for text lists**.
- Options:
  - (a) Openness XML import of `hmi-tia\out\textlists\TL_*.xml`. Text lists contain no PLC links, so the `set_ControllerTag` problem does not apply.
  - (b) Enter them by hand: HMI_RT_1 → Text and graphic lists → Text lists.
  - (c) For texts only, use Tools → **Export project texts / Import project texts** (xlsx). This only translates texts that already exist; it cannot create lists.

## 4. Screens
- There is no GUI file import for screens.
- Options: Openness XML import (`out\screens\*.xml`), or library copy and paste.
- Import the screens after the tags exist with their PLC links, so the tag references resolve.
