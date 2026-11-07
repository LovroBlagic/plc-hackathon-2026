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
7. Release the lock. **Agent:** `.\hmi-tia\regen.ps1 -Export`. With no Proto screen yet, this is round 1: it generates and imports only the tags and text lists, then compiles.
   - Result: tag table **`HMI_IF_gen`** (472 tags), 11 text lists `TL_*`.

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

**Agent:** `.\hmi-tia\regen.ps1 -Export` (lock "hmi"). It exports Proto/Tpl, generates the 4 screens and the template header, imports them, compiles and prints `HMI_RESULT errors=N`.

## C. Alarms (4 min)
1. HMI_RT_1 → **HMI alarms → Discrete alarms**. Create ONE alarm: text "x", class Errors, trigger tag `AlarmWord`, bit 0.
2. Use the **Export** button (top of the alarm editor) → save as `hmi-tia\export\alarm_sample.xlsx`.
3. **Agent:** `python hmi-tia\alarms_gen.py --sample hmi-tia\export\alarm_sample.xlsx`, which writes `hmi-tia\out\alarms\crane_alarms.xlsx`.
4. Click **Import** in the alarm editor → `crane_alarms.xlsx`. ID 1 overwrites your test alarm.
5. Check: alarm ID 4 = "ID kontejnera postoji u listi za istovar, ali ne postoji u polju Bay 0", trigger bit 3.

## D. Alarm screen (3 min), hand-made and never regenerated
1. Add screen **`Alarms`** (number 14, template `Tpl`).
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
   2. Set AUTOMATSKI, then START. The crane markers move and the cells change colour.
   3. M, T and J count up.
   4. Alarm 3 appears with the given toy data.
