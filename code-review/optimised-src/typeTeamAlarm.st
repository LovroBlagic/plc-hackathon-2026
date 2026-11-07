TYPE typeTeamAlarm :
// One alarm/message history entry, stamped with SIMULATED time (no PLC clock).
STRUCT
	k : DINT;                           // simulation step when raised
	sStamp : STRING(20);                // simulated date/time "DD.MM.YYYY HH:MM"
	iCode : INT;                        // see Team_HMI alarm code list
	sText : STRING(80);                 // human readable message
END_STRUCT
END_TYPE
