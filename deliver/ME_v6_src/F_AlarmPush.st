FUNCTION F_AlarmPush : BOOL
// Push a message into the alarm history (Team_HMI.aAlarmHist, newest at index 0), stamped with simulated time.
VAR_INPUT
	k : DINT;
	sStamp : STRING(20);
	iCode : INT;
	sText : STRING(80);
END_VAR
VAR
	i : INT;
END_VAR
// ---IMPL---
FOR i := 49 TO 1 BY -1 DO
	Team_HMI.aAlarmHist[i] := Team_HMI.aAlarmHist[i - 1];
END_FOR;
Team_HMI.aAlarmHist[0].k := k;
Team_HMI.aAlarmHist[0].sStamp := sStamp;
Team_HMI.aAlarmHist[0].iCode := iCode;
Team_HMI.aAlarmHist[0].sText := sText;
Team_HMI.nAlarms := Team_HMI.nAlarms + 1;
Team_HMI.sLastAlarm := sText;
F_AlarmPush := TRUE;
