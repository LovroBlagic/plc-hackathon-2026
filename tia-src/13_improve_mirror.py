"""Line-by-line Python mirror of the v1.3/v1.4 additions to tia-src/11_FB_Planner.scl:
the IMPROVE phase (REGION 2, branch `IF #ImpActive`, v1.4: exact FaMask side feasibility in Pass A),
the v1.4 SLOT phase (branches SlStart / SlActive / FinStart, FC21 "Crane_DropCost") and the
closed-form lower bound (REGION 1).
It starts from the oracle's greedy winner (the greedy part is mirrored by 12_planner_mirror.py),
runs the SCL state machine call by call (cImpPerCall evaluations / 3000 iterator positions per
call) and compares plan, T, M, evaluations, accepts and the bound with tools/crane_plan.py
(improve(), lower_bound()).  Run: python tia-src/13_improve_mirror.py [budget] [percall]
TiaRun ignores .py files."""
import sys, os, glob, itertools
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import crane_model as cm
import crane_plan as cp


def fc20(X0, Y0, B0, X1, Y1, B1, MMode):
    if X0 == X1 and Y0 == Y1 and B0 == B1:
        return 0, 0
    g0 = X0 + (6 if B0 == 0 else 0)
    g1 = X1 + (6 if B1 == 0 else 0)
    dG = abs(g1 - g0)
    dY = abs(Y1 - Y0)
    t = max(60 * dG, 23 * dY)
    if MMode == 1:
        m = (X1 != X0) + (dY != 0)
    elif MMode == 2:
        m = 1
    else:
        m = (dG != 0) + (dY != 0)
    return t, m


class Mirror:
    def __init__(self, st, cfg, res, evals, dist, percall):
        self.cMMode, self.cOrder, self.cBalMode, self.cLim = cfg["mmode"], cfg["order"], cfg["balmode"], cfg["lim"]
        self.cCeil = cfg.get("ceil", 0) if cfg.get("ceil", 0) > cfg["lim"] else 0   # v1.5 (R2-J1)
        self.cImpEvals, self.cImpDist, self.cImpPerCall = max(0, evals), dist, max(1, percall)
        self.cSlotSweeps = cp.SLOT_SWEEPS
        self.sG = [[c[:] for c in st["bay0"]], [c[:] for c in st["bay1"]]]
        self.sCx, self.sCy, self.sCb = st["crane"]
        self.sBaseT, self.sBaseM = st["base_t"], st["base_m"]
        # Src arrays, 1-based (FB11 REGION 1 order: unloads, then loads; first match x outer / y inner)
        self.SrcKind, self.SrcIdx, self.SrcId = [0], [0], [0]
        self.SrcX, self.SrcY, self.SrcB, self.SrcG = [0], [0], [0], [0]
        for k, lst, b in ((1, st["PU"], 0), (2, st["PL"], 1)):
            for (idx, cid) in lst:
                found = False
                for x in range(4):
                    for y in range(12):
                        if not found and self.sG[b][x][y] == cid:
                            found = True
                            self.SrcKind.append(k); self.SrcIdx.append(idx); self.SrcId.append(cid)
                            self.SrcX.append(x); self.SrcY.append(y); self.SrcB.append(b)
                            self.SrcG.append(x + 6 if b == 0 else x)
        self.nSrc = len(self.SrcKind) - 1
        self.WTab = {}
        for i in range(10):
            for j in range(12):
                t, m = fc20(0, 0, 1, i, j, 1, self.cMMode)
                self.WTab[(i, j, 0)] = self.WTab[(i, j, 1)] = t + 190 * m
        for j in range(12):
            t, m = fc20(0, 0, 1, 0, j, 0, self.cMMode)
            self.WTab[(6, j, 0)] = t + 190 * m
        # BestPlan / BestSrc from the greedy winner
        key = {(self.SrcKind[i], self.SrcIdx[i]): i for i in range(1, self.nSrc + 1)}
        self.BestPlan = [None] + [dict(tr) for tr in res["plan"]]
        self.BestSrc = [0] + [key[(tr["kind"], tr["list_idx"])] for tr in res["plan"]]
        self.BestLen = len(res["plan"])
        self.BestT, self.BestM = res["T"], res["M"]
        self.BestK = (res["T"] - self.sBaseT) + 190 * (res["M"] - self.sBaseM)
        self.ImpEvals = self.ImpAcc = 0
        self.calls = 0
        self.maxops = 0
        self.lb()

    # ---------------- REGION 1: lower bound ----------------
    def lb(self):
        self.LbT = self.LbM = 0
        if self.nSrc > 0:
            qNu = qNl = 0
            qXs = 3 * self.nSrc
            qAtSrc = False
            for i in range(1, self.nSrc + 1):
                if self.SrcKind[i] == 1:
                    qNu += 1
                    qXs += 2 * self.SrcX[i]
                else:
                    qNl += 1
                    qXs += 2 * (3 - self.SrcX[i])
                if self.SrcX[i] == self.sCx and self.SrcY[i] == self.sCy and self.SrcB[i] == self.sCb:
                    qAtSrc = True
            cG = self.sCx + 6 if self.sCb == 0 else self.sCx
            qXb = -1
            for qKind in (1, 2):
                qHaveF = False
                qFm = 0
                for i in range(1, self.nSrc + 1):
                    if self.SrcKind[i] == qKind:
                        qVal = self.SrcX[i] + 3 if qKind == 1 else 6 - self.SrcX[i]
                        qFv = 3 + abs(cG - self.SrcG[i]) - qVal
                        if not qHaveF or qFv < qFm:
                            qFm = qFv
                            qHaveF = True
                if qHaveF:
                    if qKind == 2:
                        qSf = qNu - qNl if qNu > qNl else max(0, qNl - qNu - 1)
                    else:
                        qSf = max(0, qNu - qNl - 1) if qNu >= qNl else qNl - qNu
                    qXt = qXs + 3 * qSf + qFm
                    if qXb < 0 or qXt < qXb:
                        qXb = qXt
            self.LbT = 400 * self.nSrc + 60 * qXb
            self.LbM = 4 * self.nSrc - (1 if qAtSrc else 0)

    # ---------------- close of the last variant: start ----------------
    def start(self):
        self.SlAcc = 0
        self.SlSweeps = 0
        self.LsN = self.BestLen
        self.LsT = [self.sBaseT] + [0] * 96
        self.LsM = [self.sBaseM] + [0] * 96
        self.LsSeq, self.LsDX, self.LsDY, self.LsDB = [0] * 97, [0] * 97, [0] * 97, [0] * 97
        for i in range(1, self.BestLen + 1):
            self.LsSeq[i] = self.BestSrc[i]
            self.LsDX[i], self.LsDY[i], self.LsDB[i] = self.BestPlan[i]["dst"]
            self.LsT[i] = self.BestPlan[i]["cum_t"]
            self.LsM[i] = self.BestPlan[i]["cum_m"]
        self.LsK = self.BestK
        self.CdSeq, self.CdDX, self.CdDY, self.CdDB = [0] * 97, [0] * 97, [0] * 97, [0] * 97
        self.CdT, self.CdM = [0] * 97, [0] * 97
        self.FaTot, self.FaYc, self.FaMask = [0] * 97, [0] * 97, [0] * 97
        if self.cImpEvals > 0 and self.cOrder != 2 and self.BestLen >= 2:
            self.ItMv, self.ItI, self.ItJ = 0, 1, 1
            self.ItSweepImp = False
            self.ImpActive = True
        else:
            self.ImpActive = False
            self.slot()

    # ---------------- REGION 2: one call of the improve branch ----------------
    def call(self):
        self.calls += 1
        qEv = qScan = 0
        WT = self.WTab
        SK, SX, SY, SB, SG, SI = self.SrcKind, self.SrcX, self.SrcY, self.SrcB, self.SrcG, self.SrcId
        while self.ImpActive and qEv < self.cImpPerCall and qScan < 3000:
            qScan += 1
            qMv, qI, qJ = self.ItMv, self.ItI, self.ItJ
            qEnd = False
            if self.ItMv == 0:
                qHave = True
                self.ItMv, self.ItI, self.ItJ = 1, 1, 1
            else:
                qImax = self.LsN - 1 if self.ItMv == 3 else self.LsN
                qHave = self.ItJ != self.ItI and (self.ItMv != 2 or self.ItJ > self.ItI) \
                    and (self.cImpDist <= 0 or abs(self.ItI - self.ItJ) <= self.cImpDist)
                self.ItJ += 1
                if self.ItJ > qImax:
                    self.ItJ = 1
                    self.ItI += 1
                    if self.ItI > qImax:
                        self.ItI = 1
                        self.ItMv += 1
                        if self.ItMv > 3:
                            self.ItMv = 1
                            qEnd = True
            Ls = self.LsSeq
            qValid = qHave
            if qHave and self.cOrder == 1 and qMv != 0:
                if qMv == 1:
                    # v1.5: pattern-token relocate, valid iff an element of the other kind lies between
                    qKa = SK[Ls[qI]]
                    qLow, qHigh = (qI + 1, qJ) if qI < qJ else (qJ, qI - 1)
                    qValid = False
                    for qQ in range(qLow, qHigh + 1):
                        if SK[Ls[qQ]] != qKa:
                            qValid = True
                            break
                elif qMv == 2:
                    qValid = qJ == qI + 1 and SK[Ls[qI]] != SK[Ls[qJ]]
                else:
                    qKa, qKb = SK[Ls[qI]], SK[Ls[qI + 1]]
                    qLow, qHigh = (qJ, qI - 1) if qJ < qI else (qI + 2, qJ + 1)
                    for qQ in range(qLow, qHigh + 1):
                        if SK[Ls[qQ]] == qKa or SK[Ls[qQ]] == qKb:
                            qValid = False
                            break
            if qValid:
                Cd = self.CdSeq
                if qMv == 0 or qMv == 2:
                    for qQ in range(1, self.LsN + 1):
                        Cd[qQ] = Ls[qQ]
                    if qMv == 2:
                        Cd[qI] = Ls[qJ]
                        Cd[qJ] = Ls[qI]
                elif qMv == 1 and self.cOrder == 1:
                    # v1.5: kind pattern with token i moved to j; k-th U / L = k-th unload / load
                    qRd = qU = qL = 1
                    for qQ in range(1, self.LsN + 1):
                        if qQ == qJ:
                            qKb = SK[Ls[qI]]
                        else:
                            if qRd == qI:
                                qRd += 1
                            qKb = SK[Ls[qRd]]
                            qRd += 1
                        if qKb == SK[Ls[qI]]:
                            while SK[Ls[qU]] != qKb:
                                qU += 1
                            Cd[qQ] = Ls[qU]
                            qU += 1
                        else:
                            while SK[Ls[qL]] == SK[Ls[qI]]:
                                qL += 1
                            Cd[qQ] = Ls[qL]
                            qL += 1
                else:
                    qRd = 1
                    for qQ in range(1, self.LsN + 1):
                        if qQ == qJ:
                            Cd[qQ] = Ls[qI]
                        elif qMv == 3 and qQ == qJ + 1:
                            Cd[qQ] = Ls[qI + 1]
                        else:
                            if qRd == qI:
                                qRd += 2 if qMv == 3 else 1
                            Cd[qQ] = Ls[qRd]
                            qRd += 1
                if qMv == 0:
                    qPos = 1
                elif qMv == 1 and self.cOrder == 1:
                    qPos = 1
                    while Cd[qPos] == Ls[qPos]:
                        qPos += 1
                elif qI < qJ:
                    qPos = qI
                else:
                    qPos = qJ
                qStart = max(1, qPos - 1)
                g = [[c[:] for c in self.sG[0]], [c[:] for c in self.sG[1]]]
                for qQ in range(1, qStart):
                    si = Ls[qQ]
                    g[self.LsDB[qQ]][self.LsDX[qQ]][self.LsDY[qQ]] = SI[si]
                    g[SB[si]][SX[si]][SY[si]] = 0
                if qStart > 1:
                    cx, cy, cb = self.LsDX[qStart - 1], self.LsDY[qStart - 1], self.LsDB[qStart - 1]
                else:
                    cx, cy, cb = self.sCx, self.sCy, self.sCb
                TotT, TotM = self.LsT[qStart - 1], self.LsM[qStart - 1]
                L = R = F = A = 0
                for x in range(4):
                    for y in range(12):
                        if g[0][x][y] != 0:
                            if x <= 1:
                                L += 1
                            else:
                                R += 1
                            if y <= 5:
                                F += 1
                            else:
                                A += 1
                uLt = uRt = nLt = 0
                for qQ in range(qStart, self.LsN + 1):
                    si = Cd[qQ]
                    if SK[si] == 1:
                        if SX[si] <= 1:
                            uLt += 1
                        else:
                            uRt += 1
                    else:
                        nLt += 1
                # v1.4 FaMask (exact side feasibility of the remaining fixed sequence)
                wYc = sum(1 for x in range(4) for y in range(12) if g[1][x][y] != 0)
                FT, FY, FM = self.FaTot, self.FaYc, self.FaMask
                FT[qStart - 1] = L + R
                FY[qStart - 1] = wYc
                for qQ in range(qStart, self.LsN + 1):
                    if SK[Cd[qQ]] == 1:
                        FT[qQ] = FT[qQ - 1] - 1
                        FY[qQ] = FY[qQ - 1] + 1
                    else:
                        FT[qQ] = FT[qQ - 1] + 1
                        FY[qQ] = FY[qQ - 1] - 1
                wMsk = 0
                for wLv in range(25):
                    wRv = FT[self.LsN] - wLv
                    if 0 <= wRv <= 24 and (self.cCeil == 0 or abs(wLv - wRv) <= self.cLim):
                        wMsk |= 1 << wLv
                FM[self.LsN] = wMsk
                for qQ in range(self.LsN, qStart - 1, -1):
                    si = Cd[qQ]
                    wTot = FT[qQ - 1]
                    wMsk = 0
                    for wLv in range(25):
                        wRv = wTot - wLv
                        if 0 <= wRv <= 24:
                            wOk = False
                            if SK[si] == 1:
                                if FY[qQ - 1] < 48:
                                    L2, R2 = (wLv - 1, wRv) if SX[si] <= 1 else (wLv, wRv - 1)
                                    if L2 >= 0 and R2 >= 0:
                                        dAbs = abs(L2 - R2)
                                        if dAbs <= self.cLim or dAbs <= abs(wLv - wRv) or (abs(wLv - wRv) > self.cLim and dAbs <= self.cCeil):
                                            wOk = (FM[qQ] >> L2) & 1 != 0
                            else:
                                for wSd in (0, 1):
                                    L2, R2 = (wLv + 1, wRv) if wSd == 0 else (wLv, wRv + 1)
                                    if not wOk and L2 <= 24 and R2 <= 24:
                                        dAbs = abs(L2 - R2)
                                        if dAbs <= self.cLim or dAbs <= abs(wLv - wRv) or (abs(wLv - wRv) > self.cLim and dAbs <= self.cCeil):
                                            wOk = (FM[qQ] >> L2) & 1 != 0
                            if wOk:
                                wMsk |= 1 << wLv
                    FM[qQ - 1] = wMsk
                qFail = (FM[qStart - 1] >> L) & 1 == 0
                ops = 0
                kv = 0
                for qStep in (range(qStart, self.LsN + 1) if not qFail else ()):
                    si = Cd[qStep]
                    sCol, sRow, sBay, srcCol = SX[si], SY[si], SB[si], SG[si]
                    dBay = 1 - sBay
                    qNx = Cd[qStep + 1] if qStep < self.LsN else 0
                    if cx != sCol or cy != sRow or cb != sBay:
                        eT, eMan = fc20(cx, cy, cb, sCol, sRow, sBay, self.cMMode)
                        TotT += eT
                        TotM += eMan
                    if SK[si] == 1:
                        if sCol <= 1:
                            uLt -= 1
                        else:
                            uRt -= 1
                        L2, R2 = (L - 1, R) if sCol <= 1 else (L, R - 1)
                        F2, A2 = (F - 1, A) if sRow <= 5 else (F, A - 1)
                    else:
                        nLt -= 1
                    found = False
                    bestScore = 0
                    bK = 0
                    for iPas in (0, 1):
                        for x in range(4):
                            for y in range(12):
                                ops += 1
                                if g[dBay][x][y] == 0:
                                    if SK[si] == 2:
                                        L2, R2 = (L + 1, R) if x <= 1 else (L, R + 1)
                                        F2, A2 = (F + 1, A) if y <= 5 else (F, A + 1)
                                    dAbs = abs(L2 - R2)
                                    okB = dAbs <= self.cLim or dAbs <= abs(L - R) or (abs(L - R) > self.cLim and dAbs <= self.cCeil)
                                    if okB and self.cBalMode == 1:
                                        dAbs = abs(F2 - A2)
                                        okB = dAbs <= self.cLim or dAbs <= abs(F - A)
                                    if okB and iPas == 0:
                                        okB = 0 <= L2 <= 24
                                        if okB:
                                            okB = (self.FaMask[qStep] >> L2) & 1 != 0
                                    if okB:
                                        dGc = x + 6 if dBay == 0 else x
                                        xd = 0 if x == sCol else 1
                                        qW = WT[(abs(dGc - srcCol), abs(y - sRow), xd)]
                                        if qNx > 0:
                                            xd = 0 if x == SX[qNx] else 1
                                            qW += WT[(abs(dGc - SG[qNx]), abs(y - SY[qNx]), xd)]
                                        if not found or qW < bestScore:
                                            found = True
                                            bestScore = qW
                                            bK = x * 12 + y
                        if found:
                            break
                    if not found:
                        qFail = True
                        break
                    dCol, dRow = bK // 12, bK % 12
                    lT, lMan = fc20(sCol, sRow, sBay, dCol, dRow, dBay, self.cMMode)
                    g[dBay][dCol][dRow] = SI[si]
                    g[sBay][sCol][sRow] = 0
                    if SK[si] == 1:
                        if sCol <= 1:
                            L -= 1
                        else:
                            R -= 1
                        if sRow <= 5:
                            F -= 1
                        else:
                            A -= 1
                    else:
                        if dCol <= 1:
                            L += 1
                        else:
                            R += 1
                        if dRow <= 5:
                            F += 1
                        else:
                            A += 1
                    TotT += 400 + lT
                    TotM += 2 + lMan
                    self.CdDX[qStep], self.CdDY[qStep], self.CdDB[qStep] = dCol, dRow, dBay
                    self.CdT[qStep], self.CdM[qStep] = TotT, TotM
                    cx, cy, cb = dCol, dRow, dBay
                    kv = (TotT - self.sBaseT) + 190 * (TotM - self.sBaseM)
                    if kv + 960 * (self.LsN - qStep) >= self.LsK:
                        qFail = True
                        break
                self.maxops = max(self.maxops, ops)
                self.ImpEvals += 1
                qEv += 1
                if not qFail:
                    self.ImpAcc += 1
                    self.ItSweepImp = True
                    for qQ in range(qStart, self.LsN + 1):
                        self.LsDX[qQ], self.LsDY[qQ], self.LsDB[qQ] = self.CdDX[qQ], self.CdDY[qQ], self.CdDB[qQ]
                        self.LsT[qQ], self.LsM[qQ] = self.CdT[qQ], self.CdM[qQ]
                    for qQ in range(1, self.LsN + 1):
                        self.LsSeq[qQ] = Cd[qQ]
                    self.LsK = kv
            qFin = self.ImpEvals >= self.cImpEvals
            if qEnd and not qFin:
                if self.ItSweepImp:
                    self.ItSweepImp = False
                else:
                    qFin = True
            if qFin:
                self.ImpActive = False
                self.slot()

    # ---------------- v1.4: SlStart / SlActive (one k per call) / FinStart ----------------
    def dropcost(self, s, x, y, b, nq, has):
        t, m = fc20(self.SrcX[s], self.SrcY[s], self.SrcB[s], x, y, b, self.cMMode)
        w = t + 190 * m
        if has:
            t, m = fc20(x, y, b, self.SrcX[nq], self.SrcY[nq], self.SrcB[nq], self.cMMode)
            w += t + 190 * m
        return w

    def slot(self):
        SK, SX, SY, SB, SI = self.SrcKind, self.SrcX, self.SrcY, self.SrcB, self.SrcId
        Ls, DX, DY, DB = self.LsSeq, self.LsDX, self.LsDY, self.LsDB
        N = self.LsN
        if self.cSlotSweeps > 0 and N >= 1:
            Av = [[[1 if self.sG[b][x][y] == 0 else 999 for y in range(12)] for x in range(4)] for b in range(2)]
            Us = [[[0] * 12 for x in range(4)] for b in range(2)]
            for k in range(1, N + 1):
                si = Ls[k]
                Av[SB[si]][SX[si]][SY[si]] = k + 1
                Us[DB[k]][DX[k]][DY[k]] = k
            bl = br = bf = ba = 0
            for x in range(4):
                for y in range(12):
                    if self.sG[0][x][y] != 0:
                        if x <= 1:
                            bl += 1
                        else:
                            br += 1
                        if y <= 5:
                            bf += 1
                        else:
                            ba += 1
            SlK, SlSweep, SlImp, active = 1, 1, False, True
            while active:                                   # one iteration = one OB1 call
                self.calls += 1
                k = SlK
                si = Ls[k]
                b = DB[k]
                qNx = Ls[k + 1] if k < N else 1
                wCur = self.dropcost(si, DX[k], DY[k], b, qNx, k < N)
                for wC in range(0, 48 + N):
                    wGo = False
                    wQ = 0
                    if wC <= 47:
                        x, y = wC // 12, wC % 12
                        if Us[b][x][y] == 0 and Av[b][x][y] <= k:
                            wC1 = self.dropcost(si, x, y, b, qNx, k < N)
                            wGo = wC1 < wCur
                    else:
                        wQ = wC - 47 + k
                        if wQ <= N:
                            if DB[wQ] == b and Av[b][DX[wQ]][DY[wQ]] <= k:
                                sj = Ls[wQ]
                                wNq = Ls[wQ + 1] if wQ < N else 1
                                wC2 = self.dropcost(sj, DX[wQ], DY[wQ], b, wNq, wQ < N)
                                wC1 = (self.dropcost(si, DX[wQ], DY[wQ], b, qNx, k < N)
                                       + self.dropcost(sj, DX[k], DY[k], b, wNq, wQ < N))
                                if wC1 < wCur + wC2:
                                    wGo = True
                                    x, y = DX[wQ], DY[wQ]
                        else:
                            wQ = 0
                    if wGo:
                        wOx, wOy = DX[k], DY[k]
                        wChk = False
                        if SK[si] == 2:
                            wChk = ((x <= 1) != (wOx <= 1)) or (self.cBalMode == 1 and ((y <= 5) != (wOy <= 5)))
                        if wQ > 0 and SK[Ls[wQ]] == 2:
                            wChk = wChk or ((wOx <= 1) != (x <= 1)) or (self.cBalMode == 1 and ((wOy <= 5) != (y <= 5)))
                        DX[k], DY[k] = x, y
                        if wQ > 0:
                            DX[wQ], DY[wQ] = wOx, wOy
                        wTrj = True
                        if wChk:
                            wLa, wRa, wFa, wAa = bl, br, bf, ba
                            for qQ in range(1, N + 1):
                                sj = Ls[qQ]
                                if SK[sj] == 1:
                                    L2, R2 = (wLa - 1, wRa) if SX[sj] <= 1 else (wLa, wRa - 1)
                                    F2, A2 = (wFa - 1, wAa) if SY[sj] <= 5 else (wFa, wAa - 1)
                                else:
                                    L2, R2 = (wLa + 1, wRa) if DX[qQ] <= 1 else (wLa, wRa + 1)
                                    F2, A2 = (wFa + 1, wAa) if DY[qQ] <= 5 else (wFa, wAa + 1)
                                dAbs = abs(L2 - R2)
                                okB = dAbs <= self.cLim or dAbs <= abs(wLa - wRa) or (abs(wLa - wRa) > self.cLim and dAbs <= self.cCeil)
                                if okB and self.cBalMode == 1:
                                    dAbs = abs(F2 - A2)
                                    okB = dAbs <= self.cLim or dAbs <= abs(wFa - wAa)
                                if not okB:
                                    wTrj = False
                                    break
                                wLa, wRa, wFa, wAa = L2, R2, F2, A2
                            if wTrj and self.cCeil > 0 and abs(wLa - wRa) > self.cLim:
                                wTrj = False             # v1.5: a relaxed plan must end balanced
                        if not wTrj:
                            DX[k], DY[k] = wOx, wOy
                            if wQ > 0:
                                DX[wQ], DY[wQ] = x, y
                        else:
                            if wQ > 0:
                                Us[b][x][y] = k
                                Us[b][wOx][wOy] = wQ
                                wCur = self.dropcost(si, x, y, b, qNx, k < N)
                            else:
                                Us[b][wOx][wOy] = 0
                                Us[b][x][y] = k
                                wCur = wC1
                            SlImp = True
                            self.SlAcc += 1
                SlK += 1
                if SlK > N:
                    if SlImp and SlSweep < self.cSlotSweeps:
                        SlSweep += 1
                        SlK = 1
                        SlImp = False
                    else:
                        active = False
            self.SlSweeps = SlSweep
        # FinStart
        if self.SlAcc > 0:
            cx, cy, cb = self.sCx, self.sCy, self.sCb
            TotT, TotM = self.sBaseT, self.sBaseM
            for k in range(1, N + 1):
                si = Ls[k]
                if cx != SX[si] or cy != SY[si] or cb != SB[si]:
                    eT, eMan = fc20(cx, cy, cb, SX[si], SY[si], SB[si], self.cMMode)
                    TotT += eT
                    TotM += eMan
                lT, lMan = fc20(SX[si], SY[si], SB[si], DX[k], DY[k], DB[k], self.cMMode)
                TotT += 400 + lT
                TotM += 2 + lMan
                self.LsT[k], self.LsM[k] = TotT, TotM
                cx, cy, cb = DX[k], DY[k], DB[k]
            self.LsK = (TotT - self.sBaseT) + 190 * (TotM - self.sBaseM)
        if self.ImpAcc > 0 or self.SlAcc > 0:
            for qQ in range(1, N + 1):
                si = Ls[qQ]
                self.BestPlan[qQ] = {"kind": SK[si], "id": SI[si], "list_idx": self.SrcIdx[si],
                                     "src": (SX[si], SY[si], SB[si]),
                                     "dst": (DX[qQ], DY[qQ], DB[qQ]),
                                     "cum_t": self.LsT[qQ], "cum_m": self.LsM[qQ]}
            self.BestT, self.BestM, self.BestK = self.LsT[N], self.LsM[N], self.LsK


def check(path, cfg, evals, dist, percall, alphas, sweeps=cp.SLOT_SWEEPS):
    ds = cm.load_dataset(path)
    st = cp.build_state(ds)
    if st["init"]["blocking"]:
        return None
    res = cp.plan_fb(st, cfg, alphas, slot_sweeps=0)          # greedy winner only
    if res["err"] != 0:
        return None
    c2 = res["cfg"]
    ref = cp.slot_search(st, c2, cp.improve(st, c2, res, evals, dist), sweeps)
    lbT, lbM, _ = cp.lower_bound(st)
    mi = Mirror(st, c2, res, evals, dist, percall)
    mi.cSlotSweeps = sweeps
    mi.start()
    guard = 0
    while mi.ImpActive:
        mi.call()
        guard += 1
        assert guard < 200000
    plan = [mi.BestPlan[i] for i in range(1, mi.BestLen + 1)]
    ok = (plan == ref["plan"] and mi.BestT == ref["T"] and mi.BestM == ref["M"]
          and mi.ImpEvals == ref.get("imp_evals", 0) and mi.ImpAcc == ref.get("imp_accepts", 0)
          and mi.SlAcc == ref.get("slot_accepts", 0) and mi.SlSweeps == ref.get("slot_sweeps", 0)
          and mi.LbT == lbT and mi.LbM == lbM)
    return ok, mi.calls, mi.maxops, mi.ImpEvals, mi.ImpAcc


if __name__ == "__main__":
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    percall = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    files = sorted(glob.glob(os.path.join(REPO, "tools", "crane_data", "*.json")))
    files += sorted(glob.glob(os.path.join(REPO, "tools", "crane_data_stress", "*.json")))[::4]
    files += sorted(glob.glob(os.path.join(REPO, "tools", "judge_sets", "r2_jury_imb*.json")))   # v1.5 relaxed rule
    tot = fails = 0
    maxops = maxcalls = 0
    for f in files:
        for mm, od, bm, dist in itertools.product((2, 0), (0, 1), (0, 1), (0, 6)):
            if mm == 0 and (bm == 1 or dist == 6):
                continue
            r = check(f, {"mmode": mm, "order": od, "balmode": bm, "lim": 5}, budget, dist, percall,
                      [0, 100, 200, 300])
            if r is None:
                continue
            tot += 1
            ok, calls, ops, ev, acc = r
            maxops, maxcalls = max(maxops, ops), max(maxcalls, calls)
            if not ok:
                fails += 1
                print("FAIL", os.path.basename(f), (mm, od, bm, dist), ev, acc)
    print("IMPROVE_MIRROR runs=%d fails=%d max_calls=%d max_inner_iterations_per_eval=%d (budget %d, %d/call)" % (
        tot, fails, maxcalls, maxops, budget, percall))
