# Final crane HMI handoff

The submission version is **`deliver/TIA_HMI_flicker_fixed_v3.zap21`**. It includes the PLC and native WinCC RT Advanced HMI. Engineering uses TIA Portal V21; the HMI device/runtime version is V17.

The ME submission source remains `deliver/ME_v7_WebVisu_dashboard_v2.projectarchive`. To recreate the two submission ZIPs:

```powershell
python hmi-tia-final/package_submissions.py --out tia-work/submission-zips
```

The outputs are `strujici_rjesenje_tia.zip` and `strujici_rjesenje_codesys.zip`. Existing files are not overwritten. Archive hashes are recorded in `archive_sha256.json`.

## Verified behavior

- The exact original DB10/DB11/DB20/DB21 start values were checked against a fresh simulator download. Both PLC and Python report N=10, zero valid transfers, M=0, T=0, J=0; seven unload and three load requests have missing source IDs. Both grids remain unchanged.
- The fuller synthetic `tools/crane_data/rand_01.json` dataset completed 27 transfers: MSpec=130, T=2503.2002 seconds, J approximately 1.211793. Both final grids match Python. This demonstrates parity with the configured Python planner, not a global optimality proof.
- The blinking fix computes colours in private temporary arrays and publishes each final cell colour once per scan. Across 240 samples of all 96 stationary cells, no colours changed; 27 non-base-colour cells were included.
- AUTO and SEMI STOP/resume, SEMI stepping, manual PUT, alarm acknowledgment/history, and navigation were tested. Every manual command and every alarm combination were not exhaustively tested.
- V3 was retrieved into a fresh folder and both PLC and HMI compiled with zero errors and zero warnings. The user reviewed its runtime. Submission ZIP contents and archive integrity were verified.

Evidence is under `work/` and `validation/`. Original input DB exports are under `work/original-input-dbs/`.

## Editable sources and native controls

The PLC change is `work/plc-flicker-fix/21_FB_CraneControl.scl`; `work/flicker_fix.diff` isolates the change. The shared `tia-src` files were intentionally left unchanged during this isolated session. The final archives contain the patched block.

The local generators, layouts, Openness helper source, and native Excel templates are preserved under `work/`. For the standard V3 screen generator:

```powershell
python hmi-tia-final/work/gen_hmi_v3_backup.py screens --layout hmi-tia-final/work/layout_v3_backup.json --export hmi-tia/proto --out tia-work/rebuilt-v3
```

Start from the final project archive when editing. Native Excel imports preserve the PLC bindings for 492 generated tags. **Do not import XML tag tables over those bindings.** Generate alarms with `generate_alarms_xlsx.py --no-plc-ack`; the active native workbook is `work/alarms/crane_alarms_no_plc_ack.xlsx`.

The two native Advanced Alarm Views on `Alarms` are not preserved by Openness screen XML export. **Do not overwrite the Alarms screen with generated XML.** Retrieve the complete project archive to retain these controls. HMI acknowledgment uses `AlarmHmiAck`; the native alarm-table acknowledgment button was tested to clear the PLC alarm. Automatic PLC-to-HMI cross-acknowledgment is not claimed.

Build helper executables locally using their PowerShell build scripts. Vendor DLLs and compiled executables are not committed.

## Fullscreen V4 is a separate local demo

`deliver/TIA_HMI_fullscreen_final_v4.zap21` has the enlarged fullscreen layout reviewed on this laptop. It is **not the selected submission baseline**. Its native 1440x900 layout uses a process-local `DPIUNAWARE` launch on a 2880x1800 display with Windows 200% scaling. Normal simulation without that launch can show small geometry and clipped text.

Project-based launch instructions are in `fullscreen-local/README.txt`. The launcher accepts `-ProjectDirectory` for a retrieved project. A copied standalone-runtime experiment crashed, so no standalone runtime payload is included. Screenshots show the working project-based V4 launch. The main thread reviewed this display dependency and confirmed V3 should remain in the submission ZIP.

## Session closed

TIA, the HMI runtime, and the dedicated simulator were closed at the user's request. No physical hardware or unseen judging dataset was tested. Downloads contain the renamed submission ZIPs; no upload to organizers was performed.
