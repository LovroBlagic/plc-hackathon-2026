# Crane HMI: human click list (about 25 min)

Project: `tia-work\crane\PLC_hackathon_2026_V21`, device **PC-System_1 / HMI_RT_1** (WinCC RT Advanced).
The agent generates everything else. **Never hand-edit the screens `Main`, `Manual`, `Lists`, `AlarmLog` or the template `Tpl`.** Each regeneration overwrites them (Import Override).

**Before you start:**
- Check that `tia-work\openness.lock` is absent, then create it containing `human <time>`.
- Delete the lock when you hand back to the agent.
- Agents may attach to your open TIA (HmiGen attaches to a running TIA that has this project open).
- The PLC program (tia-src incl. DB101 `HMI_IF`) must already be imported and compiled.

## A. Connection, base objects (6 min), then agent round 1
1. **Devices & networks → Network view.** Drag the PC station's IE port onto the PLC_1 PN port so they share one subnet (PN/IE_1).
2. Network view → **Connections** → type "HMI connection". Drag from HMI_RT_1 to PLC_1. Name it **`HMI_Connection_1`**.
3. HMI_RT_1 → **Runtime settings → Screen**: resolution **1920 × 1080**.
   - If only 1024×768 is possible, set `"scale": 0.5333` in `layout.json`.
4. HMI_RT_1 → HMI tags → Default tag table: add **one** tag `P_SwOn`.
   - Connection `HMI_Connection_1`, PLC tag `HMI_IF.SwOn`
   - Acquisition cycle **100 ms**. All generated tags copy this cycle.
5. HMI_RT_1 → Text and graphic lists → new **text list `TL_State`**, type *Range*. Add 2 entries: `0 → OFF`, `1 → INIT`.
6. HMI_RT_1 → Screen management → Templates: add an **empty template `Tpl`**.
   - Also add an **empty screen `Alarms`** (number **15**, template `Tpl`) now: the generated header has a nav button to it, so it must exist before round 2. You fill it in step D. (Screen 14 is the generated `Score` screen.)
7. Release the lock. **Agent:** `.\hmi-tia\regen.ps1 -Export`. With no Proto screen yet, this is round 1: it generates and imports only the tags and text lists, then compiles.
   - Result: tag table **`HMI_IF_gen`** (490 tags), 11 text lists `TL_*`.

## B. Prototype screen "Proto" (12 min), then agent round 2
Add screen **`Proto`** (number 99, template `Tpl`). Draw the objects below anywhere on it. Each object's **Name** (Properties → General/Miscellaneous → Name) must be exactly as given. Use tags from table `HMI_IF_gen`.

| Name | Object | Settings |
|---|---|---|
| `P_Text` | Text field | font Tahoma 15, transparent |
| `P_IO` | I/O field | mode **Output**, tag `M`, format decimal `99999` |
| `P_SymIO` | Symbolic I/O field | mode Output, tag `State`, text list `TL_State` |
| `P_Btn` | Button | text "BTN". Events → **Press** → `SetBit`, tag `BtnStart` |
| `P_BtnInv` | Button | Press → **`InvertBit`**, tag `SwOn` |
| `P_NavBtn` | Button | Press → **`ActivateScreen`**, screen name **`Screen_1`** |
| `P_CellRect` | Rectangle | Animations → **Appearance**, tag `CellSt0_00`, type Range. Rows 0..7, background colours: 0 `222,222,222` · 1 `165,165,165` · 2 `140,175,215` · 3 `185,160,210` · 4 `165,200,165` · 5 `70,140,230` · 6 `205,235,255` · 7 `255,215,0` |
| `P_Lamp` | Rectangle | Appearance, tag `LampReady`: 0 → `170,170,170`, 1 → `40,160,60` |
| `P_LampAlarm` | Rectangle | Appearance, tag `LampAlarm`: 0 → `170,170,170`, 1 → `220,0,0` with flashing **on** |
| `P_Bar` | Bar | process value `BalL`, min 0, max 24 |
| `P_CraneX` | I/O field 100×32 | Output, tag `Carried`, format `999`, white background, 2 px dark border. Animations → **Horizontal movement**: tag `CraneGX`, range **0..9**, start X **62**, end X **1088** (Y 188) |
| `P_CraneY` | Rectangle 120×36 | fill `70,70,70`. Animations → **Vertical movement**: tag `CraneY`, range **0..11**, start Y **237**, end Y **897** (X 566) |
| `P_DateTime` | Date/time field 346×40 | v1.5 (judge round 2 R2-J4, "date and time on every screen"): mode **Output**, **system time**, show date **and** time, font Tahoma 15. The generator places it in the footer of template `Tpl`, so every screen shows it. If missing, the generator only warns and skips it. |

**Agent:** `.\hmi-tia\regen.ps1 -Export` (lock "hmi"). It exports Proto/Tpl, generates the 4 screens and the template header, imports them, compiles and prints `HMI_RESULT errors=N`.

## C. Alarms (4 min)
1. HMI_RT_1 → **HMI alarms → Discrete alarms**. Create ONE alarm: text "x", class Errors, trigger tag `AlarmWord`, bit 0.
2. Use the **Export** button (top of the alarm editor) → save as `hmi-tia\export\alarm_sample.xlsx`.
3. **Agent:** `python hmi-tia\alarms_gen.py --sample hmi-tia\export\alarm_sample.xlsx`, which writes `hmi-tia\out\alarms\crane_alarms.xlsx`.
4. Click **Import** in the alarm editor → `crane_alarms.xlsx`. ID 1 overwrites your test alarm.
5. Check: alarm ID 4 = "ID kontejnera postoji u listi za istovar, ali ne postoji u polju Bay 0", trigger bit 3.
6. v1.4: alarm ID 17 (warning) is triggered by tag `AlarmWord2` bit 0 ("list order abandoned because of the balance rule"). v1.5: alarm ID 18 (warning) by `AlarmWord2` bit 1 ("ship loaded out of balance: relaxed balance rule keeps the list order"). If the import complains that `AlarmWord2` is unknown, run agent round 2 first (it creates the tag).
   **Numbering used everywhere (pitch, demo, this file): the WinCC alarm ID shown on screen = PLC bit + 1** (bit 0 imbalance = ID 1, bit 1 pick empty = ID 2, bit 2 drop occupied = ID 3, bit 3 unload ID not in Bay 0 = ID 4, bit 4 load ID not in Bay 1 = ID 5; `AlarmWord2` bit 0/1 = ID 17/18).
7. Optional (about 2 min, judge finding J7): in the text of alarm 4 append " ID: " and insert a **tag field** (right-click → Insert parameter field) with tag `AlarmUId`; same in alarm 5 with `AlarmLId`. The screen `AlarmLog` already shows both IDs and their counts.

## D. Alarm screen (3 min), hand-made and never regenerated
1. Open the screen **`Alarms`** created in step A6 (number **15**, template `Tpl`; number 14 belongs to the generated `Score` screen).
2. Controls → **Alarm view** at (16, 156), 1888 × 420. Display: **current alarms** (pending + acknowledge button).
3. Second **Alarm view** at (16, 590), 1888 × 420. Display: **Alarm buffer** (history with date/time).
4. HMI_RT_1 → Runtime settings → General → **Start screen = `Main`**.

## E. Run against PLCSIM
**BLOCKER:** PLCSIM is not installed on this laptop yet (tooling note). Install S7-PLCSIM V21 from the TIA ISO, or PLCSIM Advanced V8.
1. Start PLCSIM and download PLC_1 (PG/PC interface: PLCSIM). Set the CPU to RUN.
2. Windows **Set PG/PC Interface**: access point `S7ONLINE` → `PLCSIM` (PLCSIM V21) or the PLCSIM Advanced virtual adapter.
3. Right-click HMI_RT_1 → **Start simulation**. This runs WinCC RT Advanced on this PC.
4. Smoke test:
   1. UKLJ./ISKLJ. → SPREMAN lamp goes green after POČETNO STANJE.
   2. **Given toy data first:** alarm IDs 4 and 5 appear (none of 111..777 is in Bay 0; 124/125 do not exist and 123 is already on the ship). The plan has **0 transfers**: START goes straight to ZAVRŠENO and nothing moves. That is correct behaviour, not a bug (judge round 2 R2-J2).
   3. **Load a demo data set** (only in a TEST COPY of the project, never the deliverable): `python tools/json_to_db.py tools/judge_sets/r1_jury_fig1_half.json` (written to `tools/demo_db/fig1_half/`, already there: 6 unloads + 6 loads like Figure 1, about 50 commands = 1 min in AUTO). Import with `TiaRun.exe --project <copy> --headless --lock demo --src tools/demo_db/fig1_half --numbers tools/demo_db/fig1_half/numbers.txt`, download, CPU STOP → RUN, then POČETNO STANJE. Without a download (not recommended): write **every** line of `watch_values.txt` into a watch table (192 lines: all 96 cells and all 96 list entries, zeros included; writing only the non-zero values leaves the old containers and list entries behind, judge round 3 R3-J1), then press POČETNO STANJE. The import-and-download path above is the safe one.
   4. Set AUTOMATSKI, then START. The crane markers move and the cells change colour. M, T and J count up; the REZULTAT screen shows predicted vs live J.
   5. List-check demo: `tools/demo_db/listcheck_bogus_unload/` (unload list names yard container 555, which is also in the load list): alarm ID 4 with ID 555, and load entry 555 is still executed (v1.5 fix R2-E1).
   6. v1.5 checks: POČETNO STANJE is ignored while RADI / PLANIRANJE (STOP first).
   7. v1.6 data-load rules (judge round 3 R3-E1 / R3-J1). At POČETNO STANJE the PLC takes DB10/DB11 as a **new yard** only if (a) they were edited while no job was in progress (before the first command after the last POČETNO STANJE, or in ZAVRŠENO), or (b) DB20/DB21 changed **and** DB10/DB11 were edited during the job, or (c) at least 8 cells were rewritten during the job. Otherwise it **restores the loaded data set** (repeat run). An obstacle written during AUTO to provoke alarm 3 therefore never replaces the data set, also when it is removed again or a container is on the hook. New DB20/DB21 alone keep the loaded yard and take the new lists. A cell written back to its old value does not count as an edit.
