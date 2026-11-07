"""Build the REAL-WORLD datasets tools/datasets/real_*/ from public data downloaded to research/data_raw/.

Raw inputs (gitignored, re-download with the URLs in each meta.json):
  research/data_raw/pvgis/pv_zg_all.csv        PVGIS v5.3 seriescalc, SARAH3, 45.8N 15.97E, 800 kWp, 14 % loss,
                                                30 deg, south, hourly 2005-2023 (UTC, value at HH:10 = hour HH)
  research/data_raw/load/LoadProfile_20IPs_2016.csv   Zenodo 3899018 (CC-BY 4.0), 15-min loads of German SMEs
  research/data_raw/acn_jpl_sessions.csv       sessions parsed from ACN-Data static snapshot (JPL Arroyo garage)

KEY FINDING: the practice FNE profile is EXACTLY PVGIS-SARAH3 2023 for this site/plant (hour h -> steps 4h..4h+3),
disaggregated to 15 min by differentiating a PCHIP interpolant of the cumulative hourly energy, then clipped to
750 kW (residual 0.01 kW rms). pv_year() reproduces that method for any year 2005-2023, so the real_pvgisYYYY
datasets are very likely built the same way the organisers built (and will build) their FNE profiles.

Run (reads untrusted downloads -> isolated mode):  python -I tools/datasets/build_real.py
"""
import csv, json, math, os, sys, datetime as dt
import numpy as np
from scipy.interpolate import PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
RAW = os.path.join(ROOT, "research", "data_raw")
sys.path.insert(0, TOOLS)
import twin  # noqa: E402  (our own code: practice profiles)

N = 35040
EV_TARGET = 9326.755          # practice total EV energy, kWh/yr
EV_PMAX = 22.0 * 0.9 * 0.25   # kWh deliverable per step

PVGIS_URL = ("https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?lat=45.8&lon=15.97&peakpower=800&loss=14&angle=30"
             "&aspect=0&startyear=2005&endyear=2023&pvcalculation=1&outputformat=csv")
PVGIS_LIC = ("PVGIS (c) European Union 2001-2026, JRC; free reuse with attribution (Commission Decision 2011/833/EU). "
             "Radiation database PVGIS-SARAH3.")
LOAD_URL = "https://zenodo.org/records/3899018"
LOAD_LIC = ("Braeuer, F. (2020) 'Load profile data of 50 industrial plants in Germany for one year', Zenodo, "
            "doi:10.5281/zenodo.3899018, CC-BY 4.0. Only a rescaled derived 15-min series is stored here.")
ACN_URLS = ["https://ev.caltech.edu/dataset", "https://github.com/tongxin-li/ACN-Data-Static"]
ACN_LIC = ("ACN-Data (Caltech/JPL), Lee, Li & Low, 'ACN-Data: Analysis and Applications of an Open EV Charging "
           "Dataset', ACM e-Energy 2019 - free for research with citation (official API needs a free token; "
           "the static GitHub snapshot states no separate licence). Only derived, rescaled session tuples stored.")


# ---------------------------------------------------------------- PV (PVGIS, organiser method)
_pv_cache = {}


def _pvgis_hourly():
    if not _pv_cache:
        with open(os.path.join(RAW, "pvgis", "pv_zg_all.csv")) as f:
            for line in f:
                if line[:2] == "20" and len(line) > 9 and line[8] == ":":
                    p = line.split(",")
                    _pv_cache.setdefault(int(line[:4]), []).append((line[4:8], float(p[1]) / 1000.0))
    return _pv_cache


def pv_year(year):
    """FNE (kW, 35040) from PVGIS year: drop Feb 29, PCHIP on cumulative energy, clip 0..750."""
    h = [v for (md, v) in _pvgis_hourly()[year] if md[:4] != "0229"]
    h = np.array(h)
    assert len(h) == 8760, (year, len(h))
    C = np.concatenate([[0.0], np.cumsum(h)])
    q = np.diff(PchipInterpolator(np.arange(8761), C)(np.arange(N + 1) / 4.0)) * 4.0
    return np.clip(q, 0.0, 750.0)


# ---------------------------------------------------------------- FEC (German industrial plants 2016)
def load_plant_2016(col):
    """15-min load of plant LG<col> (2016, local time). Drops the 4 duplicated DST rows ('... b'), giving a
    constant-offset series of 35136 values kept on the plant's wall clock (the practice FEC/EV are wall-clock-like:
    shift starts ~06 h, EVs arrive 08-09 h, no DST) and aligns weekdays to 2025 (2025-01-01 Wed <- 2016-01-06 Wed;
    days past the end wrap back 52 weeks)."""
    vals = []
    with open(os.path.join(RAW, "load", "LoadProfile_20IPs_2016.csv")) as f:
        rows = f.read().splitlines()[2:]
    for r in rows:
        p = r.split(";")
        if not p[0] or p[0].strip().endswith("b"):
            continue
        vals.append(float(p[col].replace(",", ".")))
    a = np.array(vals)
    assert len(a) == 35136, len(a)
    ndays = 366
    D = a.reshape(ndays, 96)
    out = np.empty((365, 96))
    for d in range(365):
        s = d + 5
        if s >= ndays:
            s -= 364
        out[d] = D[s]
    return out.reshape(-1)


def scale_fec(raw, peak=990.0, night=35.0):
    """Affine map of a real load shape to the practice level: weekday-night median -> `night` kW,
    annual maximum -> `peak` kW (keeps the real temporal shape, spikes and weekly pattern)."""
    D = raw.reshape(365, 96)
    wd = np.array([(2 + d) % 7 + 1 for d in range(365)])
    base = np.median(D[wd <= 5][:, 0:16])
    s = (peak - night) / (raw.max() - base)
    return np.clip(night + s * (raw - base), 5.0, None)


# ---------------------------------------------------------------- EV (ACN-Data JPL sessions)
US_DST = {2018: (dt.datetime(2018, 3, 11, 10), dt.datetime(2018, 11, 4, 9)),
          2019: (dt.datetime(2019, 3, 10, 10), dt.datetime(2019, 11, 3, 9)),
          2020: (dt.datetime(2020, 3, 8, 10), dt.datetime(2020, 11, 1, 9))}   # UTC instants


def _la_local(t_utc):
    t = t_utc.replace(tzinfo=None)
    a, b = US_DST[t.year]
    return t - dt.timedelta(hours=7 if a <= t < b else 8)


def jpl_sessions(stations):
    """Map 4 real JPL EVSEs (one per charger) of calendar 2019 to 2025 step indices.
    Local LA wall-clock time (DST-corrected from UTC) is used as sim time, like the wall-clock-like practice
    EV/FEC profiles; 2025 day d <- 2019 day d+1 (both Wednesdays)."""
    origin = dt.datetime(2019, 1, 2)    # sim k=0 == local clock 2019-01-02 00:00
    per = {s: [] for s in stations}
    with open(os.path.join(RAW, "acn_jpl_sessions.csv")) as f:
        for r in csv.DictReader(f):
            if r["station"] not in per:
                continue
            a = _la_local(dt.datetime.fromisoformat(r["start_utc"]))
            d = _la_local(dt.datetime.fromisoformat(r["end_utc"]))
            ka = math.ceil((a - origin).total_seconds() / 900.0)
            kd = math.floor((d - origin).total_seconds() / 900.0)
            e = float(r["kwh_integrated_208V"])
            if ka < 0 or ka >= N or e <= 0.05:
                continue
            per[r["station"]].append([ka, min(kd, N), e])
    ev = []
    for s in stations:
        ss = sorted(per[s])
        out = []
        last = 0
        for a, d, e in ss:
            a = max(a, last)
            if d - a < 1:
                continue
            out.append([a, d, e])
            last = d
        ev.append(out)
    return rescale_ev(ev)


def rescale_ev(ev, target=EV_TARGET, margin=0.98):
    """Scale energies so the total equals `target` while every session stays feasible
    (energy <= margin * 22*0.9*0.25 * steps); capped energy is redistributed to the other sessions."""
    raw = [[s[2] for s in ch] for ch in ev]
    cap = [[margin * EV_PMAX * (s[1] - s[0]) for s in ch] for ch in ev]
    k = target / sum(map(sum, raw))
    for _ in range(50):
        tot = sum(min(k * e, c) for ch_e, ch_c in zip(raw, cap) for e, c in zip(ch_e, ch_c))
        if abs(tot - target) < 1e-6:
            break
        k *= target / tot
    return [[[s[0], s[1], round(min(k * e, c), 3)] for s, e, c in zip(ch, ch_e, ch_c)]
            for ch, ch_e, ch_c in zip(ev, raw, cap)]


# ---------------------------------------------------------------- writer
def write(name, fne, fec, ev, description, urls, licence, extra=None):
    folder = os.path.join(HERE, name)
    os.makedirs(folder, exist_ok=True)
    fne = np.clip(np.asarray(fne, float), 0.0, 750.0)
    fec = np.maximum(np.asarray(fec, float), 0.0)
    assert len(fne) == N and len(fec) == N
    with open(os.path.join(folder, "fne.csv"), "w") as f:
        f.write("\n".join("%.3f" % x for x in fne) + "\n")
    with open(os.path.join(folder, "fec.csv"), "w") as f:
        f.write("\n".join("%.3f" % x for x in fec) + "\n")
    with open(os.path.join(folder, "ev.json"), "w") as f:
        json.dump([[list(s) for s in ch] for ch in ev], f)
    m = dict(name=name, kind="real", description=description, source_urls=urls, licence=licence, prices="2025")
    if extra:
        m.update(extra)
    m["stats"] = dict(fne_MWh=round(float(fne.sum()) * 0.25 / 1000, 1), fne_max=round(float(fne.max()), 1),
                      fec_MWh=round(float(fec.sum()) * 0.25 / 1000, 1), fec_max=round(float(fec.max()), 1),
                      ev_MWh=round(sum(s[2] for ch in ev for s in ch) / 1000, 3),
                      ev_sessions=[len(ch) for ch in ev])
    with open(os.path.join(folder, "meta.json"), "w") as f:
        json.dump(m, f, indent=1)
    print("%-28s FNE %6.1f MWh  FEC %6.1f MWh max %6.1f  EV %.3f MWh %s" % (
        name, m["stats"]["fne_MWh"], m["stats"]["fec_MWh"], m["stats"]["fec_max"], m["stats"]["ev_MWh"],
        m["stats"]["ev_sessions"]))


JPL_A = ["1-1-179-800", "1-1-179-799", "1-1-179-810", "1-1-179-815"]   # ~300 sessions/yr each, workplace
JPL_B = ["1-1-193-819", "1-1-178-828", "1-1-194-821", "1-1-193-827"]   # high turnover, ~450-650 sessions/yr

if __name__ == "__main__":
    base = twin.load()
    p_fne, p_fec, p_ev = np.array(base["fne"]), np.array(base["fec"]), base["ev"]
    chk = pv_year(2023)
    print("check: PVGIS-2023 rebuild vs practice FNE  rms %.3f kW" % float(np.sqrt(((chk - p_fne) ** 2).mean())))

    # A) real PV years (organiser method) + practice FEC/EV: isolates the weather-year effect
    for y in [2010, 2012, 2017, 2018, 2019, 2020, 2021, 2022]:
        write("real_pvgis%d" % y, pv_year(y), p_fec, p_ev,
              "PVGIS-SARAH3 %d hourly PV for the exact plant (45.8N 15.97E, 800 kWp, 30 deg S, 14 %% loss) turned "
              "into 15-min exactly like the practice FNE (= PVGIS 2023, PCHIP of cumulative energy, clip 750); "
              "practice FEC and EV sessions." % y,
              [PVGIS_URL.replace("2005", str(y)).replace("2023", str(y))], PVGIS_LIC, dict(pv_year=y))

    jA = jpl_sessions(JPL_A)
    jB = jpl_sessions(JPL_B)
    # B) practice PV/FEC + real EV sessions
    write("real_jplev", p_fne, p_fec, jA,
          "Practice FNE/FEC + real workplace EV sessions: 4 JPL (Caltech ACN-Data) EVSEs %s, calendar 2019, one "
          "EVSE per charger, weekday-aligned (2025 day d <- 2019 day d+1), local wall-clock time, energies rescaled to "
          "the practice total 9.33 MWh/yr (energy from integrated current at 208 V), all sessions feasible."
          % JPL_A, ACN_URLS, ACN_LIC, dict(ev_stations=JPL_A))
    write("real_jplev_hiturn", p_fne, p_fec, jB,
          "Practice FNE/FEC + high-turnover JPL EVSEs %s (2019; several sessions per day incl. evening/overnight "
          "ones), rescaled to 9.33 MWh/yr." % JPL_B, ACN_URLS, ACN_LIC, dict(ev_stations=JPL_B))

    # C) real industrial load shapes (German SMEs 2016) + real PV years (+ real EV)
    combos = [("real_ind13_pv2021_jpl", 13, 2021, jA, JPL_A,
               "plant LG13 (night ~2 % of peak, Sat ~30 %, Sun ~3 % of weekday: closest to practice)"),
              ("real_ind9_pv2019", 9, 2019, None, None,
               "plant LG9 (night ~10 % of peak, weekend ~20 %, smooth peaks)"),
              ("real_ind1_pv2010_jplhi", 1, 2010, jB, JPL_B,
               "plant LG1 (spiky: annual max = 1.7x mean weekday daily max; weekends ~1/3)"),
              ("real_ind7_pv2022", 7, 2022, None, None,
               "plant LG7 (office-like: short weekday peaks, almost nothing at night/weekends)")]
    for name, col, y, ev, st, desc in combos:
        fec = scale_fec(load_plant_2016(col))
        write(name, pv_year(y), fec, ev if ev is not None else p_ev,
              "All-real-shape scenario: FEC = German industrial %s from Zenodo 3899018 (2016, 15-min), DST rows "
              "removed, wall-clock time, weekday-aligned to 2025, affinely rescaled (weekday-night median -> 35 kW, annual "
              "max -> 990 kW); FNE = PVGIS-SARAH3 %d (organiser method); EV = %s." % (
                  desc, y, "JPL sessions %s rescaled to 9.33 MWh" % st if st else "practice sessions"),
              [LOAD_URL, PVGIS_URL.replace("2005", str(y)).replace("2023", str(y))] + (ACN_URLS if st else []),
              LOAD_LIC + " | " + PVGIS_LIC + (" | " + ACN_LIC if st else ""),
              dict(plant="LG%d (2016)" % col, pv_year=y, ev_stations=st))
