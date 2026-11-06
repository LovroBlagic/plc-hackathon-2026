FUNCTION_BLOCK Datum_Vrijeme_Set
VAR_INPUT
	IN_Year : INT;
	IN_Month : INT;
	IN_Day : INT;
	IN_Hour : INT;
	IN_Minute : INT;
	IN_Second : INT;
END_VAR
VAR_OUTPUT
	OUT_Date_Time : DT;
END_VAR
VAR
    uidResultRtcGet: UDINT;
	dwRtcGet: DWORD;
    stGetDate: SysTimeRtc.RTS_SYSTIMEDATE;
	udiGetSysTimeDate: RTS_IEC_RESULT;
    uiGetYear: UINT;
    uiGetMonth: UINT;
    uiGetDay: UINT;
    uiGetHour: UINT;
    uiGetMinute: UINT;
    uiGetSecond: UINT;
    uiGetMSecond: UINT;
    uiGetDayOfWeek: UINT;
    uiGetYday: UINT;
    uidResultConvertToDate: UDINT;
	
	udiResultConvertToUtc: UDINT;
    stSetDate: SysTimeRtc.RTS_SYSTIMEDATE;
    dwSetTimeStamp: DWORD;
    xCommandSetRtc: BOOL;
    uidResultRtcSet: UDINT;
	  
	Sekunda: BOOL;
	R_TRIG_Sekunda: R_TRIG;
	Always_Off: BOOL;
END_VAR
