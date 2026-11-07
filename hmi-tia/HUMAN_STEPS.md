# Crane HMI: remaining human / GUI steps (7 Nov 18:10)

Everything else is generated and imported by Openness (README "Method"): text lists, template `Tpl` (header, navigation, date/time footer), screens `Screen_1` (main view, also the start screen), `Manual`, `Lists`, `AlarmLog`, `Score`, and the empty screen `Alarms`.

**Done in the GUI by the orchestrator (7 Nov ~17:10–18:00):** the HMI connection `HMI_Connection_1` was checked (it already existed: PLC_1 X2 192.168.1.1 ↔ HMI_RT_1 192.168.1.2, PN/IE_1), and the resolution was checked (it stays 1024×768, layout scale 0.5333).

Openness cannot do the three steps below in V21:
- Classic HMI tags with an integrated connection lose their PLC binding on XML import and export ("'set_ControllerTag' is not supported").
- There is no API for discrete alarms.
- The alarm view is not importable.

The project is `tia-work\hmibuild\PLC_hackathon_2026_V21`. Before you start, create `tia-work\openness.lock` containing `human <time>`, and delete it when you are done.

## T. HMI tags (about 3 min)
HMI_RT_1 → HMI tags → **Import** (xlsx) → `hmi-tia\out\xlsx\HMI_IF_gen_tags.xlsx`, written by `hmi-tia\tags_xlsx_gen.py`. It contains 492 tags in table `HMI_IF_gen`, connection `HMI_Connection_1`, cycle 100 ms.
- Name rule: a scalar member keeps its name (`M`). An array element is `<member>_<idx 2 digits>`, so `Cell0_05` ↔ `HMI_IF.Cell0[5]`.
- The screens use exactly the names in `hmi-tia\out_notags\referenced_tags.txt`.

## C. Discrete alarms (about 4 min)
1. HMI_RT_1 → **HMI alarms → Discrete alarms**. Create ONE alarm: text "x", class Errors, trigger tag `AlarmWord`, bit 0. **Export** it to `hmi-tia\export\alarm_sample.xlsx`.
2. Run `python hmi-tia\alarms_gen.py --sample hmi-tia\export\alarm_sample.xlsx`. This writes `hmi-tia\out\alarms\crane_alarms.xlsx`.
3. **Import** `crane_alarms.xlsx` in the alarm editor.
4. Check that alarm ID 4 reads "ID kontejnera postoji u listi za istovar, ali ne postoji u polju Bay 0", with trigger `AlarmWord` bit 3.
5. Check that IDs 17 and 18 are on `AlarmWord2` bits 0 and 1.

Numbering: WinCC alarm ID = PLC bit + 1.

## D. Alarm views on screen `Alarms` (about 3 min; the generator never overwrites this screen)
The screen is 1024×768. The template header covers y 0–79, and the footer starts at y 546.
1. Controls → **Alarm view** at (8, 86), size 1008 × 220. Display: **current alarms**, with the acknowledge button.
2. A second **Alarm view** at (8, 316), size 1008 × 224. Display: **Alarm buffer** (history with date and time).
3. Save.

## E. Run against PLCSIM
See `tia-src/PLCSIM_RESULTS.md` (virtual memory card download).
- Then right-click HMI_RT_1 → **Start simulation**.
- Smoke test: switch on with UKLJ./ISKLJ. → press POČETNO STANJE → the SPREMAN lamp goes green → AUTOMATSKA MANIPULACIJA → START.
