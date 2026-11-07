"""Line-by-line Python mirror of tia-src/11_FB_Planner.scl (FB11) + 10_FC_MoveCost.scl.
Compares against tools/crane_plan.py on every dataset x mmode x order x balmode.
Run: python tia-src/12_planner_mirror.py  (about 4 min). TiaRun ignores .py files."""
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


class FB11:
    def __init__(self, world):
        self.W = world
        self.ReqOld = False
        self.Busy = self.Done = self.Error = False
        self.ErrCode = 0
        self.calls = 0
        self.steps = 0
        self.max_ops = 0

    def call(self, Req):
        W = self.W
        edge = False
        if Req and not self.ReqOld:
            edge = True
            self.Busy = True
            self.Done = self.Error = False
            self.ErrCode = 0
            self.VarNo = 1
            self.VarActive = False
            self.VarErr = 0
            self.Err1 = 0
            self.HaveBest = False
            self.calls = 1
            self.steps = 0
            rc = 0
            self.cMMode = W["CfgMMode"]
            self.cOrder = W["CfgOrderMode"]
            self.cBalMode = W["CfgBalMode"]
            self.cLim = W["CfgBalLimit"]
            self.cVariants = W["CfgVariants"]
            self.cSteps = max(1, W["CfgStepsPerCall"])
            self.cAlpha = list(W["CfgAlpha"])
            self.sCx, self.sCy, self.sCb = W["CraneX"], W["CraneY"], W["CraneBay"]
            self.sBaseT, self.sBaseM, self.sN = W["BaseT_ds"], W["BaseM"], W["N"]
            if W["Carried"] != 0:
                rc = 4
            elif not (1 <= self.cVariants <= 4) or self.cOrder > 2 or self.cBalMode > 1 or self.cMMode > 2:
                rc = 3
            elif not (0 <= self.sCx <= 3 and 0 <= self.sCy <= 11 and 0 <= self.sCb <= 1):
                rc = 3
            if rc == 0:
                self.sG = [[col[:] for col in W["Bay0"]], [col[:] for col in W["Bay1"]]]
                self.Src = []
                for k in (1, 2):
                    for i in range(1, 49):
                        if rc:
                            continue
                        if k == 1:
                            ok, cid, b = W["UState"][i - 1] == 0, W["UList"][i - 1], 0
                        else:
                            ok, cid, b = W["LState"][i - 1] == 0, W["LList"][i - 1], 1
                        if ok:
                            if cid == 0:
                                rc = 3
                            else:
                                found = False
                                for x in range(4):
                                    for y in range(12):
                                        if not found and self.sG[b][x][y] == cid:
                                            found = True
                                            self.Src.append(dict(kind=k, idx=i, id=cid, x=x, y=y, b=b,
                                                                 g=x + 6 if b == 0 else x))
                                if not found:
                                    rc = 3
            if rc == 0:
                self.WTab = {}
                for i in range(10):
                    for j in range(12):
                        t, m = fc20(0, 0, 1, i, j, 1, self.cMMode)
                        self.WTab[(i, j, 0)] = self.WTab[(i, j, 1)] = t + 190 * m
                for j in range(12):
                    t, m = fc20(0, 0, 1, 0, j, 0, self.cMMode)
                    self.WTab[(6, j, 0)] = t + 190 * m
            if rc:
                W["PlanValid"] = False
                W["PlanLen"] = 0
                W["PlanVariant"] = 0
                self.Busy = False
                self.Error = True
                self.ErrCode = rc
        elif not Req:
            self.Busy = self.Done = self.Error = False
            self.VarActive = False
        self.ReqOld = Req
        if self.Busy and not edge:
            self.calls += 1
            budget = self.cSteps
            while self.Busy and budget > 0:
                if not self.VarActive:
                    self.VarActive = True
                    self.VarErr = 0
                    self.Alpha = self.cAlpha[self.VarNo - 1]
                    self.g = [[col[:] for col in self.sG[0]], [col[:] for col in self.sG[1]]]
                    self.Pend = [True] * len(self.Src)
                    self.nPend = len(self.Src)
                    self.cx, self.cy, self.cb = self.sCx, self.sCy, self.sCb
                    self.cG = self.cx + 6 if self.cb == 0 else self.cx
                    self.TotT, self.TotM = self.sBaseT, self.sBaseM
                    self.Cur = []
                elif self.VarErr != 0 or self.nPend == 0:
                    if self.VarErr == 0:
                        kv = (self.TotT - self.sBaseT) + 190 * (self.TotM - self.sBaseM)
                        if not self.HaveBest or kv < self.BestK:
                            self.HaveBest = True
                            self.BestV = self.VarNo
                            self.BestK = kv
                            self.BestT, self.BestM, self.Best = self.TotT, self.TotM, list(self.Cur)
                    elif self.VarNo == 1:
                        self.Err1 = self.VarErr
                    self.VarActive = False
                    self.VarNo += 1
                    if self.VarNo > self.cVariants:
                        if self.HaveBest:
                            W["Plan"] = list(self.Best)
                            W["PlanLen"] = len(self.Best)
                            W["PlanVariant"] = self.BestV
                            W["PredT_ds"] = self.BestT
                            W["PredM"] = self.BestM
                            N = self.sN
                            W["PredJ"] = (0.5 * (self.BestT / 10.0) / (76.0 * N) + 0.5 * self.BestM / (4.0 * N)) if N > 0 else 0.0
                            W["PlanValid"] = True
                            self.Done = True
                            self.ErrCode = 0
                        else:
                            W["PlanValid"] = False
                            W["PlanLen"] = 0
                            W["PlanVariant"] = 0
                            self.Error = True
                            self.ErrCode = self.Err1
                        self.Busy = False
                else:
                    budget -= 1
                    self.steps += 1
                    self.step()

    def step(self):
        g, Src, Pend = self.g, self.Src, self.Pend
        WT = self.WTab
        ops = 0
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
        fU = fU2 = fL = fL2 = 0  # 1-based source numbers, 0 = none
        Es = []
        for i in range(1, len(Src) + 1):
            if Pend[i - 1]:
                s = Src[i - 1]
                if s["kind"] == 1:
                    if s["x"] <= 1:
                        uLt += 1
                    else:
                        uRt += 1
                    if fU == 0:
                        fU = i
                    elif fU2 == 0:
                        fU2 = i
                else:
                    nLt += 1
                    if fL == 0:
                        fL = i
                    elif fL2 == 0:
                        fL2 = i
                if self.cOrder == 0:
                    Es.append(i)
        if self.cOrder == 1:
            if fU > 0:
                Es.append(fU)
            if fL > 0:
                Es.append(fL)
        elif self.cOrder == 2:
            if fU > 0:
                Es = [fU]
            elif fL > 0:
                Es = [fL]
        Free = [[], []]
        for b in (0, 1):
            for x in range(4):
                for y in range(12):
                    if g[b][x][y] == 0:
                        Free[b].append((x, y, x + 6 if b == 0 else x))
        B1 = [[None] * 48 for _ in range(2)]
        B1Own = [[0] * 48 for _ in range(2)]
        B2 = [[None] * 48 for _ in range(2)]

        def S(n):
            return Src[n - 1]

        if self.cOrder == 0 and self.Alpha != 0:
            for b in (0, 1):
                for k, (dx, dy, dg) in enumerate(Free[b]):
                    b1 = -1
                    own = 0
                    b2 = -1
                    for s2 in Es:
                        ops += 1
                        q = S(s2)
                        wv = WT[(abs(dg - q["g"]), abs(dy - q["y"]), 0 if dx == q["x"] else 1)]
                        if b1 < 0 or wv < b1:
                            b2 = b1
                            b1 = wv
                            own = s2
                        elif b2 < 0 or wv < b2:
                            b2 = wv
                    B1[b][k], B1Own[b][k], B2[b][k] = b1, own, b2
        found = False
        bestScore = 0
        bS = bK = bDb = 0
        for iPas in (0, 1):
            for s in Es:
                q = S(s)
                sx, sy, sb, sg = q["x"], q["y"], q["b"], q["g"]
                db = 1 - sb
                Ew = WT[(abs(self.cG - sg), abs(self.cy - sy), 0 if self.cx == sx else 1)]
                nx1 = nx2 = 0
                if self.cOrder != 0:
                    nxU = fU2 if fU == s else fU
                    nxL = fL2 if fL == s else fL
                    if self.cOrder == 1:
                        nx1, nx2 = nxU, nxL
                    elif nxU > 0:
                        nx1 = nxU
                    else:
                        nx1 = nxL
                if q["kind"] == 1:
                    if sx <= 1:
                        L2, R2, uL, uR = L - 1, R, uLt - 1, uRt
                    else:
                        L2, R2, uL, uR = L, R - 1, uLt, uRt - 1
                    F2, A2 = (F - 1, A) if sy <= 5 else (F, A - 1)
                    nL = nLt
                else:
                    uL, uR, nL = uLt, uRt, nLt - 1
                for k, (dx, dy, dg) in enumerate(Free[db]):
                    ops += 1
                    if q["kind"] == 2:
                        L2, R2 = (L + 1, R) if dx <= 1 else (L, R + 1)
                        F2, A2 = (F + 1, A) if dy <= 5 else (F, A + 1)
                    dAbs = abs(L2 - R2)
                    ok = dAbs <= self.cLim or dAbs <= abs(L - R)
                    if ok and self.cBalMode == 1:
                        dAbs = abs(F2 - A2)
                        ok = dAbs <= self.cLim or dAbs <= abs(F - A)
                    if ok and iPas == 0:
                        L0 = L2 - uL
                        R0 = R2 - uR
                        lo = nL - (24 - R0)
                        if lo < 0:
                            lo = 0
                        hi = 24 - L0
                        if nL < hi:
                            hi = nL
                        D0 = L0 - R0 - nL
                        ok = lo <= hi and D0 + 2 * lo <= self.cLim and D0 + 2 * hi >= -self.cLim
                    if ok:
                        Lm = WT[(abs(dg - sg), abs(dy - sy), 0 if dx == sx else 1)]
                        Nx = 0
                        if self.Alpha != 0:
                            if self.cOrder == 0:
                                if B1Own[db][k] != s:
                                    Nx = B1[db][k]
                                elif B2[db][k] >= 0:
                                    Nx = B2[db][k]
                            else:
                                first = True
                                for s2 in (nx1, nx2):
                                    if s2 > 0:
                                        q2 = S(s2)
                                        wv = WT[(abs(dg - q2["g"]), abs(dy - q2["y"]), 0 if dx == q2["x"] else 1)]
                                        if first or wv < Nx:
                                            Nx = wv
                                            first = False
                        score = 100 * (Ew + Lm) + self.Alpha * Nx
                        if not found or score < bestScore:
                            found = True
                            bestScore = score
                            bS, bK, bDb = s, k, db
            if found:
                break
        self.max_ops = max(self.max_ops, ops)
        if not found:
            self.VarErr = 1
            return
        if len(self.Cur) >= 96:
            self.VarErr = 2
            return
        q = S(bS)
        sx, sy, sb = q["x"], q["y"], q["b"]
        db = bDb
        dx, dy, dg = Free[db][bK]
        eT, eM = fc20(self.cx, self.cy, self.cb, sx, sy, sb, self.cMMode)
        lT, lM = fc20(sx, sy, sb, dx, dy, db, self.cMMode)
        g[db][dx][dy] = g[sb][sx][sy]
        g[sb][sx][sy] = 0
        self.TotT += eT + 200 + lT + 200
        self.TotM += eM + 1 + lM + 1
        self.Cur.append({"kind": q["kind"], "id": q["id"], "list_idx": q["idx"], "src": (sx, sy, sb),
                         "dst": (dx, dy, db), "cum_t": self.TotT, "cum_m": self.TotM})
        self.cx, self.cy, self.cb, self.cG = dx, dy, db, dg
        self.Pend[bS - 1] = False
        self.nPend -= 1


def run(ds_path, mmode, order, balmode, alphas=(0, 50, 100, 150), lim=5, carried=0, cfg_over=None):
    ds = cm.load_dataset(ds_path)
    st = cp.build_state(ds, lim)
    if st["init"]["blocking"]:
        return None
    cfg = {"mmode": mmode, "order": order, "balmode": balmode, "lim": lim}
    st["carried"] = carried
    ref = cp.plan(st, cfg, list(alphas))
    iv = st["init"]
    W = {"Bay0": ds["bay0"], "Bay1": ds["bay1"], "CraneX": 0, "CraneY": 0, "CraneBay": 1, "Carried": carried,
         "UList": iv["UList"], "UState": iv["UState"], "LList": iv["LList"], "LState": iv["LState"], "N": iv["N"],
         "BaseT_ds": 0, "BaseM": 0, "CfgMMode": mmode, "CfgOrderMode": order, "CfgBalMode": balmode,
         "CfgBalLimit": lim, "CfgVariants": len(alphas), "CfgAlpha": list(alphas) + [0] * (4 - len(alphas)),
         "CfgStepsPerCall": 1}
    if cfg_over:
        W.update(cfg_over)
    fb = FB11(W)
    fb.call(True)
    guard = 0
    while fb.Busy:
        fb.call(True)
        guard += 1
        assert guard < 2000
    calls = fb.calls
    if ref["err"] != 0:
        ok = fb.Error and fb.ErrCode == ref["err"]
        return ok, calls, fb.max_ops, "err ref=%d fb=%s/%d" % (ref["err"], fb.Error, fb.ErrCode), ref
    ok = fb.Done and W["PlanLen"] == len(ref["plan"]) and W["PlanVariant"] == ref["variant"] \
        and W["PredT_ds"] == ref["T"] and W["PredM"] == ref["M"] and abs(W["PredJ"] - ref["J"]) < 1e-9
    if ok:
        for a, b in zip(W["Plan"], ref["plan"]):
            if a != b:
                ok = False
                break
    return ok, calls, fb.max_ops, ("" if ok else "mismatch v=%s/%s" % (W.get("PlanVariant"), ref["variant"])), ref


if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(REPO, "tools", "crane_data", "*.json")))
    tot = fails = 0
    maxcalls = 0
    maxops = 0
    per = {}
    errs = {}
    for f in files:
        for mm, od, bm in itertools.product((0, 1, 2), (0, 1, 2), (0, 1)):
            r = run(f, mm, od, bm)
            if r is None:
                continue
            ok, calls, ops, msg, ref = r
            tot += 1
            maxcalls = max(maxcalls, calls)
            maxops = max(maxops, ops)
            key = (mm, od, bm)
            per.setdefault(key, [0, 0, 0])
            per[key][0] += 1
            if ref["err"]:
                per[key][2] += 1
            if not ok:
                fails += 1
                per[key][1] += 1
                print("FAIL", os.path.basename(f), key, msg)
    print("cfg(mmode,order,balmode) runs fails ref_errors")
    for k in sorted(per):
        print(k, per[k][0], per[k][1], per[k][2])
    # error-code checks
    f0 = files[0]
    print("carried ->", run(f0, 2, 0, 0, carried=123)[0:1], "variants=5 ->",
          run(f0, 2, 0, 0, cfg_over={"CfgVariants": 5})[3])
    print("TOTAL runs=%d fails=%d max_calls_per_job=%d max_inner_iterations_per_step=%d" % (tot, fails, maxcalls, maxops))
