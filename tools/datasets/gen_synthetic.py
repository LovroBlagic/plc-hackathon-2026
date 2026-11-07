"""Synthetic dataset suite generator (seeded, reproducible).

Builds tools/datasets/syn_* (kind "synthetic") and tools/datasets/stress_* (kind "stress") from the practice
profiles (twin.load()) with realistic perturbations. Prices are never touched (2025 series from twin.load()).

  python tools/datasets/gen_synthetic.py            # build all
  python tools/datasets/gen_synthetic.py syn_boot1  # build selected

Building blocks:
  FEC  week rotation (keeps weekday pattern) | day bootstrap (same weekday, +-W days) | AR(1) multiplicative
       noise | extra high-load weekdays near the import limit | "peaky" (amplified intraday residual) |
       per-day start-time shift | scale (stress)
  PV   day rotation | weather transplant: target day's clear-sky envelope x donor day's clearness shape
       (donor +-W days) | Markov cloudy/clear streaks (donor chosen by clearness tercile) | scale (stress)
  EV   per charger, per day: copy the sessions of a random practice day with the same weekday (keeps each
       charger's habits), jitter arrival/departure by +-1 step, energy x lognormal(0,0.12), remove overlaps,
       rescale to the practice annual energy (~9.33 MWh), keep each session feasible.
"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import twin  # noqa: E402
from loader import write_dataset  # noqa: E402

N, D = 35040, 365
B = twin.load()
F0 = np.array(B["fec"], dtype=float).reshape(D, 96)
P0 = np.array(B["fne"], dtype=float).reshape(D, 96)
WD = np.array([((2 + d) % 7) + 1 for d in range(D)])   # 1=Mon .. 7=Sun (2025-01-01 is Wednesday)
FEC_CAP = 999.9            # practice max is 999.9 kW
EV_TOTAL = sum(e for ch in B["ev"] for (_, _, e) in ch)   # 9326.8 kWh
EV_K = 22.0 * 0.9 * 0.25   # kWh per step at max EV power


# ---------------------------------------------------------------- FEC
def fec_rotate_weeks(F, w):
    """Shift by w whole weeks; wrap modulo 364 days (52 weeks) so every day keeps its weekday."""
    return F[(np.arange(D) - 7 * w) % 364]


def fec_bootstrap(rng, F, win=28):
    """Each day replaced by a random practice day with the same weekday within +-win days."""
    out = np.empty_like(F)
    src = np.empty(D, int)
    for d in range(D):
        c = [x for x in range(max(0, d - win), min(D, d + win + 1)) if WD[x] == WD[d]]
        src[d] = rng.choice(c)
        out[d] = F[src[d]]
    return out


def fec_ar_noise(rng, F, sigma, phi=0.9):
    x = np.empty(N)
    e = rng.standard_normal(N) * sigma * np.sqrt(1 - phi * phi)
    x[0] = rng.standard_normal() * sigma
    for k in range(1, N):
        x[k] = phi * x[k - 1] + e[k]
    x = np.clip(x, -3 * sigma, 3 * sigma)
    return F * (1.0 + x.reshape(D, 96))


def fec_high_days(rng, F, n, lo=940.0, hi=990.0):
    """n random Mon-Fri days get their daytime load scaled so that the daily max hits U(lo, hi)."""
    F = F.copy()
    days = rng.choice([d for d in range(D) if WD[d] <= 5 and F[d].max() > 600], n, replace=False)
    for d in days:
        base = F[d].min()
        tgt = rng.uniform(lo, hi)
        s = max(1.0, (tgt - base) / (F[d].max() - base))
        F[d] = base + (F[d] - base) * s
    return F, sorted(int(x) for x in days)


def fec_peaky(F, gain, w=9):
    """Amplify the deviation from a +-w/2-step moving average (sharper intraday peaks, same daily shape)."""
    flat = F.reshape(-1)
    ker = np.ones(w) / w
    sm = np.convolve(np.pad(flat, w // 2, mode="edge"), ker, mode="valid")
    out = sm + gain * (flat - sm)
    return np.maximum(out, 0.6 * sm).reshape(D, 96)


def fec_day_shift(rng, F, maxs=2):
    """Each day's profile shifted by a random -maxs..+maxs steps (shift start variation)."""
    flat = F.reshape(-1).copy()
    out = flat.copy()
    for d in range(D):
        s = int(rng.integers(-maxs, maxs + 1))
        if s == 0:
            continue
        a, b = d * 96, d * 96 + 96
        idx = np.clip(np.arange(a, b) - s, 0, N - 1)
        out[a:b] = flat[idx]
    return out.reshape(D, 96)


def fec_softcap(F, knee=960.0, top=FEC_CAP):
    """Smoothly compress values above knee so that max < top (avoids flat plateaus from hard clipping)."""
    w = top - knee
    return np.where(F > knee, knee + w * np.tanh((F - knee) / w), F)


# ---------------------------------------------------------------- PV
def _envelope(P, wmax=10, wsm=5):
    """Clear-sky-like envelope per day x qh: running max over +-wmax days, then smoothed over +-wsm days."""
    E = np.empty_like(P)
    for d in range(D):
        E[d] = P[max(0, d - wmax):min(D, d + wmax + 1)].max(axis=0)
    S = np.empty_like(E)
    for d in range(D):
        S[d] = E[max(0, d - wsm):min(D, d + wsm + 1)].mean(axis=0)
    return np.maximum(S, P)


ENV = _envelope(P0)
KD = P0.sum(1) / np.maximum(ENV.sum(1), 1e-9)      # daily clearness index (0..1)


def _transplant(d, c):
    r = np.where(ENV[c] > 2.0, P0[c] / np.maximum(ENV[c], 1e-9), 0.0)
    return np.clip(ENV[d] * np.minimum(r, 1.0), 0.0, 750.0)


def pv_rotate_days(P, n):
    return np.roll(P, n, axis=0)


def pv_transplant(rng, win=10, p_stay=None, p_cloudy=None):
    """Weather transplant. Without p_stay: uniform donor within +-win days. With p_stay/p_cloudy: a 2-state
    Markov chain (clear/cloudy, persistence p_stay, stationary cloudy share p_cloudy) picks donors from the
    lower / upper half (by clearness) of the +-win window -> cloudy streaks or sunnier months."""
    out = np.empty_like(P0)
    cloudy = rng.random() < (p_cloudy or 0.5)
    for d in range(D):
        c = np.arange(max(0, d - win), min(D, d + win + 1))
        if p_stay is not None:
            # switching probs that give stationary share p_cloudy with mean persistence ~p_stay
            q_cl = (1 - p_stay) * 2 * (1 - p_cloudy)   # leave cloudy
            q_cc = (1 - p_stay) * 2 * p_cloudy         # leave clear
            if cloudy and rng.random() < q_cl:
                cloudy = False
            elif not cloudy and rng.random() < q_cc:
                cloudy = True
            med = np.median(KD[c])
            c = c[KD[c] <= med] if cloudy else c[KD[c] > med]
        out[d] = _transplant(d, int(rng.choice(c)))
    return out


# ---------------------------------------------------------------- EV
def ev_resample(rng, jit=1, esig=0.12, total=None):
    """Per charger: each target day copies the sessions of a random practice day with the same weekday."""
    total = EV_TOTAL if total is None else total
    out = []
    for j in range(4):
        byday = {}
        for (a, dp, e) in B["ev"][j]:
            byday.setdefault(a // 96, []).append((a, dp, e))
        ss = []
        for d in range(D):
            donor = int(rng.choice(np.where(WD == WD[d])[0]))
            for (a, dp, e) in byday.get(donor, []):
                a2 = a + (d - donor) * 96 + int(rng.integers(-jit, jit + 1))
                d2 = dp + (d - donor) * 96 + int(rng.integers(-jit, jit + 1))
                ss.append([a2, d2, e * float(np.exp(rng.normal(0, esig)))])
        ss.sort()
        clean = []
        last_dep = -1
        for (a, dp, e) in ss:
            a = max(a, last_dep + 1, 0)
            dp = min(dp, N)
            if dp - a < 1 or a >= N:
                continue
            clean.append([a, dp, e])
            last_dep = dp
        out.append(clean)
    # rescale to the target annual energy, respecting feasibility (<= 90 % of max deliverable)
    for _ in range(5):
        cur = sum(s[2] for ch in out for s in ch)
        f = total / cur
        for ch in out:
            for s in ch:
                s[2] = min(s[2] * f, 0.9 * EV_K * (s[1] - s[0]))
    for ch in out:
        for s in ch:
            s[2] = max(0.2, min(s[2], 0.9 * EV_K * (s[1] - s[0])))
        assert len(ch) <= 300, "Prof_EV holds max 300 sessions per charger"
    return [[tuple(s) for s in ch] for ch in out]


# ---------------------------------------------------------------- suite
def build(name, seed):
    rng = np.random.default_rng(seed)
    kind, info, stress = "synthetic", [], None
    F, P = F0, P0
    if name == "syn_rot1":
        F = fec_rotate_weeks(F0, 3); P = pv_rotate_days(P0, -9)
        info.append("FEC rotated +3 weeks, PV rotated -9 days, EV resampled")
    elif name == "syn_rot2":
        F = fec_ar_noise(rng, fec_rotate_weeks(F0, -5), 0.03); P = pv_rotate_days(P0, 12)
        info.append("FEC rotated -5 weeks + AR(1) noise 3 %, PV rotated +12 days, EV resampled")
    elif name in ("syn_boot1", "syn_boot2", "syn_boot3"):
        sig, pw = dict(syn_boot1=(0.04, 10), syn_boot2=(0.06, 10), syn_boot3=(0.03, 20))[name]
        F = fec_ar_noise(rng, fec_bootstrap(rng, F0), sig); P = pv_transplant(rng, pw)
        info.append("FEC day bootstrap (same weekday +-28 d) + AR(1) noise %d %%, PV weather transplant +-%d d, EV resampled" % (sig * 100, pw))
    elif name == "syn_highload":
        F, days = fec_high_days(rng, fec_ar_noise(rng, fec_bootstrap(rng, F0), 0.04), 8)
        P = pv_transplant(rng, 10)
        info.append("FEC bootstrap + noise 4 %% + 8 extra weekdays scaled to a 940-990 kW peak (days %s), PV transplant" % days)
    elif name == "syn_peaky":
        F = fec_ar_noise(rng, fec_peaky(fec_bootstrap(rng, F0), 1.3), 0.03); P = pv_transplant(rng, 10)
        info.append("FEC bootstrap, intraday residual vs 9-step moving average x1.3 (sharper peaks), noise 3 %, PV transplant")
    elif name == "syn_cloudy":
        F = fec_ar_noise(rng, fec_bootstrap(rng, F0), 0.04); P = pv_transplant(rng, 30, p_stay=0.8, p_cloudy=0.7)
        info.append("FEC bootstrap + noise 4 %, PV cloudy streaks: Markov chain (persistence 0.8, 70 % cloudy) picks donors from the cloudier half of +-30 d")
    elif name == "syn_sunny":
        F = fec_ar_noise(rng, fec_bootstrap(rng, F0), 0.04); P = pv_transplant(rng, 30, p_stay=0.8, p_cloudy=0.3)
        info.append("FEC bootstrap + noise 4 %, PV sunnier: Markov chain (persistence 0.8, 30 % cloudy) over +-30 d donors")
    elif name == "syn_noise8":
        F = fec_ar_noise(rng, fec_rotate_weeks(F0, 2), 0.08, phi=0.95); P = pv_transplant(rng, 10)
        info.append("FEC rotated +2 weeks + persistent AR(1) noise 8 % (phi 0.95), PV transplant")
    elif name == "syn_shift":
        F = fec_ar_noise(rng, fec_day_shift(rng, fec_bootstrap(rng, F0), 2), 0.04); P = pv_transplant(rng, 10)
        info.append("FEC bootstrap, each day shifted by -2..+2 steps (start-time variation), noise 4 %, PV transplant")
    elif name == "syn_mixed":
        F = fec_peaky(fec_bootstrap(rng, F0), 1.2)
        F, days = fec_high_days(rng, fec_ar_noise(rng, F, 0.05), 5)
        P = pv_transplant(rng, 20, p_stay=0.75, p_cloudy=0.5)
        info.append("FEC bootstrap + peaky x1.2 + noise 5 %% + 5 high-load days %s, PV Markov streaks (0.75, 50 %%)" % days)
    elif name == "stress_load105":
        kind = "stress"
        F = 1.05 * fec_ar_noise(rng, fec_bootstrap(rng, F0), 0.04); P = pv_transplant(rng, 10)
        info.append("STRESS: FEC bootstrap + noise 4 %, then x1.05, soft-capped below 999.9 kW (more time near the import limit; an uncapped x1.05 trips the baseline in winter because FEC alone exceeds 1000 kW with an empty battery), PV transplant")
        stress = "load +5 %"
    elif name == "stress_pv85":
        kind = "stress"
        F = fec_ar_noise(rng, fec_bootstrap(rng, F0), 0.04); P = 0.85 * pv_transplant(rng, 10)
        info.append("STRESS: FEC bootstrap + noise 4 %, PV transplant x0.85")
        stress = "PV -15 %"
    elif name == "stress_combo":
        kind = "stress"
        F = 1.05 * fec_ar_noise(rng, fec_bootstrap(rng, F0), 0.05)
        P = 0.85 * pv_transplant(rng, 30, p_stay=0.8, p_cloudy=0.65)
        info.append("STRESS: FEC bootstrap + noise 5 % x1.05 (soft-capped below 999.9 kW) and cloudy PV x0.85")
        stress = "load +5 % and PV -15 % with cloudy streaks"
    else:
        raise KeyError(name)
    F = np.maximum(F, 0.0)
    F = np.minimum(fec_softcap(F), FEC_CAP)   # every dataset stays below the 1000 kW import limit
    P = np.clip(P, 0.0, 750.0)
    ev = ev_resample(rng)
    meta = dict(name=name, kind=kind, description="; ".join(info) + " (seed %d, generator tools/datasets/gen_synthetic.py)" % seed,
                source_urls=[], prices="2025", seed=seed)
    if stress:
        meta["stress"] = stress
    write_dataset(name, P.reshape(-1).tolist(), F.reshape(-1).tolist(), ev, meta)
    return meta


SUITE = [("syn_rot1", 101), ("syn_rot2", 102), ("syn_boot1", 103), ("syn_boot2", 104), ("syn_boot3", 105),
         ("syn_highload", 106), ("syn_peaky", 107), ("syn_cloudy", 108), ("syn_sunny", 109), ("syn_noise8", 110),
         ("syn_shift", 111), ("syn_mixed", 112), ("stress_load105", 201), ("stress_pv85", 202), ("stress_combo", 203)]

if __name__ == "__main__":
    want = set(sys.argv[1:])
    for n, s in SUITE:
        if not want or n in want:
            m = build(n, s)
            print(n, m["kind"], m["description"][:110])
