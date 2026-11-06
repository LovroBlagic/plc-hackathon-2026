FUNCTION_BLOCK Datum_Vrijeme_Get
VAR_OUTPUT
	OUT_Date_Time : DT;
	OUT_Year : INT;
	OUT_Month : INT;
	OUT_Day : INT;
	OUT_Hour : INT;
	OUT_Minute : INT;
	OUT_Second : INT;
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
