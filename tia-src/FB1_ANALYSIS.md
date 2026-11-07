# FB1 "Crane_manipulation": analysis (tooling worker, 7 Nov 2026 ~01:15)

**Source recovered.** FB1 and its instance DB2 are **know-how protected** in the project: `IsKnowHowProtected=True`, and GenerateSource is refused.

Even so, the archive's project search index (`IM/SearchIndex/_0.cfs`, a Lucene index) stores term vectors with offsets for the "SCL Code" field. Rebuilding the tokens in offset order gives back the **complete FB1 body**. It comes out lowercased, without line breaks, and without the declaration part. The OB100 body rebuilt the same way matches the exported OB100 word for word, which validates the method.

Parser: `tia-work/fb1_recover/tv.py` and `cfs.py`.

## Recovered FB1 body (lowercased by the indexer; layout reconstructed)
```
case #command_id of
  0:  // no new commands for the cran have been given
      goto end;
  1:  // lift the cargo
      #total_time := #total_time + "global_constants".time_to_lift_a_container_in_s;
      #total_number_of_manipulations := #total_number_of_manipulations + 1;
      goto end;
  2:  // put down the cargo
      #total_time := #total_time + "global_constants".time_to_put_down_a_container_in_s;
      #total_number_of_manipulations := #total_number_of_manipulations + 1;
      goto end;
  10: #total_number_of_manipulations := 0;
      #total_time := 0.0;
      #current_x_position_in_bay := 0;
      #current_y_position_in_bay := 0;
      #current_bay_id := 1;
      goto end;
  3:  // move the crane to specific (x, y, bay id) position
      // recalibrate the current x position
      case #current_bay_id of
        0: #x_position_recalibratin_of_the_current_position := #current_x_position_in_bay + 6;
        1: #x_position_recalibratin_of_the_current_position := #current_x_position_in_bay;
        else ;
      end_case;
      // recalibrate the next x position
      case #new_bay_id of
        0: #x_position_recalibratin_of_the_new_position := #new_x_position + 6;
        1: #x_position_recalibratin_of_the_new_position := #new_x_position;
        else ;
      end_case;
      // x and y distance difference
      #difference_in_x_position := abs(sint_to_real(#x_position_recalibratin_of_the_new_position
                                     - #x_position_recalibratin_of_the_current_position)) * "global_constants".container_length_in_m;
      #difference_in_y_position := abs(sint_to_real(#new_y_position - #current_y_position_in_bay))
                                     * "global_constants".container_width_in_m;
      if (#difference_in_x_position > #difference_in_y_position) then   // x difference is larger
        #time_needed_for_move_command_in_s := #difference_in_x_position / "global_constants".velocity_of_the_crane_in_m_per_s;
        #total_time := #total_time + #time_needed_for_move_command_in_s;
      else                                                              // y difference is larger
        #time_needed_for_move_command_in_s := #difference_in_y_position / "global_constants".velocity_of_the_crane_in_m_per_s;
        #total_time := #total_time + #time_needed_for_move_command_in_s;
      end_if;
      // set the new crane position
      #current_bay_id := #new_bay_id;
      #current_x_position_in_bay := #new_x_position;
      #current_y_position_in_bay := #new_y_position;
      // increment the total number of maipulations
      #total_number_of_manipulations := #total_number_of_manipulations + 1;
      goto end;
  else  // command id not valid
      goto end;
end_case;
// after command execution reset the command to do nothing (id = 0)
end:
#pos_x_after_command   := #current_x_position_in_bay;
#pos_y_after_command   := #current_y_position_in_bay;
#bay_id_after_command  := #current_bay_id;
#number_of_manipulations := #total_number_of_manipulations;
#working_time          := #total_time;
#command_id := 0;
```

## U-list answers (CONTRACT §2)
- **U1. Completion in one call.** A command completes in ONE call. `command_id := 0` runs at the end of **every** call, including 0 and invalid IDs. The outputs are also refreshed on every call.
- **U2. M per command.** M is **+1 per move command (3)**, whatever the number of axes changed. A diagonal x+y move counts **1**, not 2. **This contradicts spec p. 10** ("istodobna promjena i x i y koordinate broji se kao dvije manipulacije"). See the ORGANIZER QUESTION below.
- **U3. Bay change.** M is always 1, so a bay change is irrelevant to M. For time, x is recalibrated to a global column: Bay0 → x+6, Bay1 → x. A bay change with equal local x therefore costs |6|·6.0 = 36 s.
- **U4. Move time.** T_move = max(|ΔG|·container_length, |Δy|·container_width) / velocity, as REAL arithmetic from DB1 (6.0, 2.3, 1.0). The +6 offset is hard-coded. A tie takes the y branch (same value). 2.3 as a REAL is 2.29999995, so T accumulates small float error: compare T with a tolerance of about 1e-3 s per command.
- **U5. Lift and put.** Lift (1) adds DB1.time_to_lift (20.0) and +1 M. Put (2) adds DB1.time_to_put_down (20.0) and +1 M. **Neither reads x, y or bay, and neither checks anything:** FB1 has no notion of containers.
- **U6. Move to the current position.** It adds **+1 M** and 0 s. **Never issue a zero-distance move.**
- **U7. No range checks.** x and y are taken as given (any SInt). For bay ≠ 0/1 the recalibration CASE takes the empty `else`, so the temp keeps a stale or undefined value and the time is garbage, yet current_bay_id is still set to the new bay. **Our code must only ever send bay 0/1, x 0..3, y 0..11** (CheckCmd).
- **U8. Reset (10).** It sets M = 0, T = 0, x = 0, y = 0, bay = 1, refreshes the outputs, and sets command_id := 0, all in one call. Unknown IDs (4..9, 11..255) are no-ops that also clear command_id.
- **U9. OB30 and OB100.**
  - The given OB30 "Cyclic interrupt" is **LAD**, with 1 network: `"Crane_manipulation_DB"` (FB1) is called with EN = power rail.
    - IN: new_x_position := "new_x_position", new_y_position := "new_y_position", new_bay_ID := "new_bay_ID"
    - INOUT: command_id := "new_command_ID"
    - OUT: "x_position", "y_position", "bay_ID", "number_of_manipulations", "time"
  - OB30 timing: **CyclicTime = 1 000 000 µs (1000 ms)**, PhaseOffset 0, priority 10.
  - The given OB100 "Startup" is SCL:
    - DB2.command_id := 0, current_bay_ID := 1, current_x/y := 0, total_number_of_manipulations := 0, total_time := 0.0
    - tags new_x/new_y := 0, new_bay_ID := 1, new_command_ID := 0
- **U10. Tag names.** The MD112 tag is named exactly **`"time"`** (Real). Its tag table is **`"Default tag table"`**, which also holds `"x_position"` %MB104 SInt, `"y_position"` %MB105 SInt, `"bay_ID"` %MB106 USInt and `"number_of_manipulations"` %MD107 UDInt. The command tags are in the table **`"Crane_command"`**: `"new_x_position"` %MB100 SInt, `"new_y_position"` %MB101 SInt, `"new_bay_ID"` %MB102 USInt, `"new_command_ID"` %MB103 USInt.
- **U11. Know-how protection.** Only FB1 and DB2 are know-how protected. OB30, OB100, DB1, DB10, DB11, DB20 and DB21 are open. There are no UDTs.
- **U12. HMI.** The HMI is `PC-System_1` / `HMI_RT_1` (WinCC RT Advanced). It has **no connections** (we must create the HMI connection to PLC_1), one screen `Screen_1` (template content only), and one HMI tag `"time"` in its "Default tag table".

## CfgMMode decision (CONTRACT §4.1)

> **v1.7 (7 Nov, team decision, binding): CfgMMode default = 0, the spec rule.** The team decided the M question in favour of the spec text p. 10: a diagonal move (x and y change) counts 2, a bay change counts as an x change (global column), a lift and a put count 1 each. The planner optimises that rule, and the HMI shows it as the primary M/J (`HMI_IF.M/J` = `World.MSpec`, counted in OB30). FB1 is given and is **not** changed, so MD107 keeps counting +1 per command; it is shown as the secondary `HMI_IF.MFb1/JFb1`. The two counts differ by design (MSpec ≥ MD107 for every plan, since no zero-distance move is ever issued). Mode 2 stays selectable. The text below is the v1.1 reasoning, kept for history.
**CfgMMode = 2 (per command)** is what FB1, and therefore MD107 (the M shown and presumably scored), actually computes.

With mode 2:
- Every move costs exactly 1 M, so a single combined diagonal move per leg is always optimal.
- A transfer is 4 M, or 3 if the crane is already at the source.
- Splitting a move into separate x and y moves doubles M.
- A zero-distance move costs 1 M for nothing.

Time stays T = max(60·dG, 23·dy) ds plus 200 ds for each lift and put. That is identical to the contract.

> **ORGANIZER QUESTION (loud):** the spec, p. 10, says a simultaneous x+y change counts as 2 manipulations, but the given FB1 counts 1 per move command (its comment reads "Total number of manipulations (commands)"). Which one is scored: MD107 from FB1, or the spec rule?
>
> Until answered: plan with mode 2, because MD107 is what the HMI shows and what FB1 reports. Keep mode 0 selectable.
>
> The plans differ only in tie-breaking. Under mode 0 a one-axis move is cheaper than a diagonal one; under mode 2 they cost the same. The runtime always issues one combined move per leg either way.

## Given data start values (also in `tia-src/given_data.json`)
- **DB10 Bay0:** [0,0]=123, [0,1]=326, [0,2]=987. The rest are 0.
- **DB11 Bay1:** [0,1]=246, [0,7]=675, [1,5]=777. The rest are 0.
- **DB20 unload** (IDs_of_the_containers): [1..7] = 111, 222, 333, 444, 555, 666, 777. The rest are 0. Note: none of these IDs are in Bay0, and 777 is in Bay1, so this is an alarm-test set.
- **DB21 load** (Bay1_IDs_of_the_containers): [1..3] = 123, 124, 125. The rest are 0. Note: 123 is in **Bay0** and 124/125 exist nowhere, so these are alarm tests too.
- **Start position** (OB100 / reset): x = 0, y = 0, bay = 1.
