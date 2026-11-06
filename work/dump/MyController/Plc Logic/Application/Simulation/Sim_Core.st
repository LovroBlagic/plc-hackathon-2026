FUNCTION_BLOCK Sim_Core
VAR_INPUT
      phase : INT;
      simCmd : typeSimCmd;
END_VAR
VAR_OUTPUT
      simOut : typeSimOut;
      score : typeAgg;
END_VAR
VAR
      initDone : BOOL;
      closing : Bool;   // zavrsni poziv nakon zadnjeg koraka (Team_Main dobiva zadnje ostvarene vrijednosti)
      closed : Bool;   // zavrsni poziv je obavljen
      zeroAgg : typeAgg;   // nikad se ne pise -> uvijek nule
      soc : LReal;   // [%] pocetak intervala k
      evRemain : Array[0..3] of LReal;   // [kWh] jos potrebno
      evDeliv : Array[0..3] of LReal;   // [kWh] dostavljeno u sesiji
      evConn : Array[0..3] of Bool;
      evDepK : Array[0..3] of DInt;
      evNext : Array[0..3] of Int;   // idx iduce sesije u Prof_EV
      evPact : Array[0..3] of LReal;   // ostvarena snaga prosli korak
      lastFne : LReal;
      lastChg : LReal;
      lastDch : LReal;
      lastImp : LReal;
      lastExp : LReal;
      lastOvImp : Bool;
      lastOvExp : Bool;
      fneAvail : LReal;   // raspolozivo u intervalu k
      fec : LReal;
      curTime : typeSimTime;
      tot : typeAgg;   // GODISNJI TOTALI (istina za ocjenjivanje)
      day : ARRAY[0..364] OF typeAgg;
      mon : ARRAY[0..11] OF typeAgg;
      peakClosed : LReal;   // suma troska vrsne snage zatvorenih mjeseci
      N_STEPS : DINT := 35040;
      EV_MAXS : Int := 300;   // mora odgovarati generatoru profila
END_VAR
VAR_TEMP
      j : INT;
      i : Int;
      k : DInt;
      d : Int;
      m : Int;
      ts : LReal;
      cap : LReal;
      pFne : LReal;
      pc : LReal;
      pd : LReal;
      pcLim : LReal;
      pdLim : LReal;
      pe : LReal;
      sumEv : LReal;
      dE : LReal;
      pGrid : LReal;
      imp : LReal;
      gExp : LReal;
      pEn : LReal;
      fee : LReal;
      ovI : Bool;
      ovE : Bool;
      tmpT : typeSimTime;
      dep : DINT;	
END_VAR

// ---IMPL---
// FUNCTION_BLOCK "Sim_Core"
// =====================================================================
// 09_Sim_Core.scl  -  jezgra simulatora (poziva se 2x po koraku)
//   phase = 1: objavi mjerenja za interval k (prije regulatora)
//   phase = 2: primijeni naredbe, fizika, energije, trosak, k := k+1
// =====================================================================

// =================================================================
// INICIJALIZACIJA / RESET (samo u fazi 1, izmedu koraka)
// =================================================================
IF phase = 1 AND (SimCtrl.reset OR NOT initDone) THEN
	soc := REAL_TO_LREAL(SimParam.BESS_SOC_INIT);
	FOR j := 0 TO 3 DO
		evRemain[j] := 0.0;
		evDeliv[j] := 0.0;
		evConn[j] := FALSE;
		evDepK[j] := 0;
		evNext[j] := 0;
		evPact[j] := 0.0;
	END_FOR;
	lastFne := 0.0;
	lastChg := 0.0;
	lastDch := 0.0;
	lastImp := 0.0;
	lastExp := 0.0;
	lastOvImp := FALSE;
	lastOvExp := FALSE;
	closing := FALSE;
	closed := FALSE;
	tot := zeroAgg;
	FOR i := 0 TO 364 DO
		day[i] := zeroAgg;
	END_FOR;
	FOR i := 0 TO 11 DO
		mon[i] := zeroAgg;
	END_FOR;
	peakClosed := 0.0;
	SimCtrl.k := 0;
	SimCtrl.finished := FALSE;
	SimCtrl.tripped := FALSE;
	SimCtrl.reset := FALSE;
	initDone := TRUE;
	score := tot;
END_IF;

// =================================================================
// FAZA 1: OBJAVA MJERENJA ZA INTERVAL k
// =================================================================
IF phase = 1 THEN
	IF SimCtrl.k >= N_STEPS THEN
		SimCtrl.finished := TRUE;
	END_IF;
	SimCtrl.stepActive := SimCtrl.run AND (NOT SimCtrl.finished) AND (NOT SimCtrl.tripped);
	// zavrsni poziv: nakon zadnjeg koraka (k = N_STEPS) Team_Main se poziva JOS JEDNOM,
	// da dobije ostvarene vrijednosti zadnjeg intervala (31.12. 23:45); naredbe se zanemaruju
	closing := SimCtrl.run AND (SimCtrl.k >= N_STEPS) AND (NOT closed) AND (NOT SimCtrl.tripped);
	IF closing THEN
		SimCtrl.stepActive := TRUE;
	END_IF;
	simOut.sim_finished := SimCtrl.finished;
	simOut.sim_tripped := SimCtrl.tripped;
	
	IF closing THEN
		simOut.t_sim.k := N_STEPS;
		simOut.FNE_output_power := 0.0;
		simOut.FEC_P_fix := 0.0;
		simOut.FNE_P_act := LREAL_TO_REAL(lastFne);
		simOut.BESS_SoC := LREAL_TO_REAL(soc);
		simOut.BESS_P_charge_act := LREAL_TO_REAL(lastChg);
		simOut.BESS_P_discharge_act := LREAL_TO_REAL(lastDch);
		simOut.EGC_P_import := LREAL_TO_REAL(lastImp);
		simOut.EGC_P_export := LREAL_TO_REAL(lastExp);
		simOut.EGC_overload_import := lastOvImp;
		simOut.EGC_overload_export := lastOvExp;
		FOR j := 0 TO 3 DO
			simOut.EV[j].P_charge_act := LREAL_TO_REAL(evPact[j]);
			simOut.EV[j].energy_required := LREAL_TO_REAL(evRemain[j]);
			simOut.EV[j].energy_delivered := LREAL_TO_REAL(evDeliv[j]);
		END_FOR;
	END_IF;
	
	IF SimCtrl.stepActive AND (NOT closing) THEN
		k := SimCtrl.k;
		Sim_TimeFromK(k := k, t => curTime);
		curTime.tariff_high := Prof_VT.Data[k];
		d := curTime.day_of_year;
		m := curTime.month - 1;                 // indeks mjeseca 0..11
		
		// ---- EV: odlasci i dolasci ----
		FOR j := 0 TO 3 DO
			IF evConn[j] AND k >= evDepK[j] THEN
				tot.E_ev_unmet := tot.E_ev_unmet + evRemain[j];
				day[d].E_ev_unmet := day[d].E_ev_unmet + evRemain[j];
				mon[m].E_ev_unmet := mon[m].E_ev_unmet + evRemain[j];
				evConn[j] := FALSE;
				evRemain[j] := 0.0;
				evPact[j] := 0.0;
			END_IF;
			IF (NOT evConn[j]) AND (evNext[j] < Prof_EV.Count[j]) THEN
				IF Prof_EV.Arr[j * EV_MAXS + evNext[j]] <= k THEN
					evConn[j] := TRUE;
					evDepK[j] := Prof_EV.Dep[j * EV_MAXS + evNext[j]];
					evRemain[j] := REAL_TO_LREAL(Prof_EV.Energy[j * EV_MAXS + evNext[j]]);
					evDeliv[j] := 0.0;
					tot.E_ev_required := tot.E_ev_required + evRemain[j];
					day[d].E_ev_required := day[d].E_ev_required + evRemain[j];
					mon[m].E_ev_required := mon[m].E_ev_required + evRemain[j];
					evNext[j] := evNext[j] + 1;
				END_IF;
			END_IF;
		END_FOR;
		
		// ---- profili za interval k ----
		fneAvail := MAX(0.0, MIN(REAL_TO_LREAL(Prof_FNE.Data[k]), REAL_TO_LREAL(SimParam.FNE_MAX_POWER)));
		fec := MAX(0.0, REAL_TO_LREAL(Prof_FEC.Data[k]));
		
		// ---- objava ----
		simOut.t_sim := curTime;
		simOut.FNE_output_power := LREAL_TO_REAL(fneAvail);
		simOut.FNE_P_act := LREAL_TO_REAL(lastFne);
		simOut.FEC_P_fix := LREAL_TO_REAL(fec);
		simOut.BESS_SoC := LREAL_TO_REAL(soc);
		simOut.BESS_P_charge_act := LREAL_TO_REAL(lastChg);
		simOut.BESS_P_discharge_act := LREAL_TO_REAL(lastDch);
		simOut.EGC_P_import := LREAL_TO_REAL(lastImp);
		simOut.EGC_P_export := LREAL_TO_REAL(lastExp);
		simOut.EGC_overload_import := lastOvImp;
		simOut.EGC_overload_export := lastOvExp;
		FOR j := 0 TO 3 DO
			simOut.EV[j].connected := evConn[j];
			dep := MIN(evDepK[j], N_STEPS - 1);     // odlazak iza kraja godine -> zadnji korak
			Sim_TimeFromK(k := dep, t => tmpt);
			simOut.EV[j].planned_departure := tmpT.stamp;
			simOut.EV[j].energy_required := LREAL_TO_REAL(evRemain[j]);
			simOut.EV[j].energy_delivered := LREAL_TO_REAL(evDeliv[j]);
			simOut.EV[j].P_charge_act := LREAL_TO_REAL(evPact[j]);
		END_FOR;
	END_IF;
END_IF;

// =================================================================
// FAZA 2: PRIMJENA NAREDBI, FIZIKA, ENERGIJE, TROSAK
// =================================================================
IF phase = 2 AND closing THEN
	closed := TRUE;
	closing := FALSE;
END_IF;

IF phase = 2 AND SimCtrl.stepActive AND (NOT closed) THEN
	k := SimCtrl.k;
	d := curTime.day_of_year;
	m := curTime.month - 1;
	ts := REAL_TO_LREAL(SimParam.TS_H);
	cap := REAL_TO_LREAL(SimParam.BESS_CAPACITY);
	
	// ---- 1. FNE / curtailment ----
	pFne := fneAvail;
	IF simCmd.FNE_enable_curtail THEN
		pFne := MIN(fneAvail, MAX(0.0, REAL_TO_LREAL(simCmd.FNE_curtail_value)));
	END_IF;
	
	// ---- 2. BESS (obje enable istodobno -> nista) ----
	pc := 0.0;
	pd := 0.0;
	IF simCmd.BESS_enable_charge AND (NOT simCmd.BESS_enable_discharge) THEN
		pcLim := (REAL_TO_LREAL(SimParam.BESS_SOC_MAX) - soc) / 100.0 * cap / (ts * REAL_TO_LREAL(SimParam.BESS_ETA_CHG));
		pc := MAX(0.0, MIN(REAL_TO_LREAL(simCmd.BESS_P_charge), MIN(REAL_TO_LREAL(SimParam.BESS_MAX_CHG), pcLim)));
	ELSIF simCmd.BESS_enable_discharge AND (NOT simCmd.BESS_enable_charge) THEN
		pdLim := (soc - REAL_TO_LREAL(SimParam.BESS_SOC_MIN)) / 100.0 * cap * REAL_TO_LREAL(SimParam.BESS_ETA_DCH) / ts;
		pd := MAX(0.0, MIN(REAL_TO_LREAL(simCmd.BESS_P_discharge), MIN(REAL_TO_LREAL(SimParam.BESS_MAX_DCH), pdLim)));
	END_IF;
	
	// ---- 3. EV punjaci ----
	sumEv := 0.0;
	FOR j := 0 TO 3 DO
		pe := 0.0;
		IF evConn[j] THEN
			pe := MAX(0.0, MIN(REAL_TO_LREAL(simCmd.EV[j].P_charge), REAL_TO_LREAL(SimParam.EV_MAX_CHARGE)));
			// ne smije se prekoraciti trazena energija
			pe := MIN(pe, evRemain[j] / (ts * REAL_TO_LREAL(SimParam.EV_ETA)));
			dE := ts * REAL_TO_LREAL(SimParam.EV_ETA) * pe;
			evRemain[j] := MAX(0.0, evRemain[j] - dE);
			evDeliv[j] := evDeliv[j] + dE;
		END_IF;
		evPact[j] := pe;
		sumEv := sumEv + pe;
	END_FOR;
	
	// ---- 4. bilanca sabirnice: P_grid = P_fix - P_FNE - (P_dch - P_chg) + sum P_EV ----
	pGrid := fec - pFne - (pd - pc) + sumEv;
	imp := MAX(pGrid, 0.0);
	gExp := MAX(- pGrid, 0.0);
	ovI := imp > (REAL_TO_LREAL(SimParam.EGC_MAX_IMPORT) + 0.000001);
	ovE := gExp > (REAL_TO_LREAL(SimParam.EGC_MAX_EXPORT) + 0.000001);
	
	lastFne := pFne;
	lastChg := pc;
	lastDch := pd;
	lastImp := imp;
	lastExp := gExp;
	lastOvImp := ovI;
	lastOvExp := ovE;
	
	IF ovI OR ovE THEN
		// odspajanje od mreze: latch, simulacija staje (rezultat = 0 bodova)
		SimCtrl.tripped := TRUE;
	ELSE
		// ---- 5. SoC ----
		soc := soc + ts * (REAL_TO_LREAL(SimParam.BESS_ETA_CHG) * pc / cap
		- pd / (REAL_TO_LREAL(SimParam.BESS_ETA_DCH) * cap)) * 100.0;
		
		// ---- 6. cijene ----
		IF SimCtrl.price_mode = 1 THEN
			pEn := REAL_TO_LREAL(Prof_PriceDA.Data[k]);      // dan-unaprijed
		ELSE
			pEn := REAL_TO_LREAL(Prof_PriceTT.Data[k]);      // dvotarifno (Elektra)
		END_IF;
		IF curTime.tariff_high THEN
			fee := REAL_TO_LREAL(SimParam.GRID_VT);
		ELSE
			fee := REAL_TO_LREAL(SimParam.GRID_NT);
		END_IF;
		
		// ---- 7. agregacija: godina / dan / mjesec ----
		Sim_Accumulate(ts := ts,
						 pFne := pFne,
						 pFneCurt := fneAvail - pFne,
						 pFec := fec,
						 pChg := pc,
						 pDch := pd,
						 pEv := sumEv,
						 pImp := imp,
						 pExp := gExp,
						 costEnergy := imp * ts * pEn - gExp * ts * pEn * REAL_TO_LREAL(SimParam.EXPORT_FACTOR),
						 costGrid := imp * ts * fee,
						 agg := tot);
		Sim_Accumulate(ts := ts,
						 pFne := pFne,
						 pFneCurt := fneAvail - pFne,
						 pFec := fec,
						 pChg := pc,
						 pDch := pd,
						 pEv := sumEv,
						 pImp := imp,
						 pExp := gExp,
						 costEnergy := imp * ts * pEn - gExp * ts * pEn * REAL_TO_LREAL(SimParam.EXPORT_FACTOR),
						 costGrid := imp * ts * fee,
						 agg := day[d]);
		Sim_Accumulate(ts := ts,
						 pFne := pFne,
						 pFneCurt := fneAvail - pFne,
						 pFec := fec,
						 pChg := pc,
						 pDch := pd,
						 pEv := sumEv,
						 pImp := imp,
						 pExp := gExp,
						 costEnergy := imp * ts * pEn - gExp * ts * pEn * REAL_TO_LREAL(SimParam.EXPORT_FACTOR),
						 costGrid := imp * ts * fee,
						 agg := mon[m]);
		
		// ---- 8. vrsna snaga (mjesecno) ----
		mon[m].cost_peak := mon[m].P_peak * REAL_TO_LREAL(SimParam.PEAK_PRICE);
		mon[m].cost_total := mon[m].cost_energy + mon[m].cost_grid + mon[m].cost_peak;
		tot.cost_peak := peakClosed + mon[m].cost_peak;
		tot.cost_total := tot.cost_energy + tot.cost_grid + tot.cost_peak;
		IF tot.P_peak < mon[m].P_peak THEN
			tot.P_peak := mon[m].P_peak;                // informativno
		END_IF;
		// zadnji korak mjeseca -> zatvori mjesec
		IF (curTime.qh_of_day = 95) AND (curTime.day_of_year + 1 = SimCal.CumDays[curTime.month]) THEN
			peakClosed := peakClosed + mon[m].cost_peak;
		END_IF;
		
		// ---- 9. iduci korak ----
		SimCtrl.k := SimCtrl.k + 1;
		IF SimCtrl.k >= N_STEPS THEN
			SimCtrl.finished := TRUE;
		END_IF;
	END_IF;
	score := tot;
END_IF;