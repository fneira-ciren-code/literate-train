"""Índices agroclimáticos. Entrada: DataFrame horario con índice DatetimeIndex y columnas
ta (°C), hr (%), pp (mm), rs (W/m2), ws (km/h). Funciones puras, sin I/O."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config as C


# ---------- clasificación -----------------------------------------------------
def frost_class(tmin: float | None) -> str:
    if tmin is None or pd.isna(tmin) or tmin > C.FROST_TMIN_C:
        return "sin helada"
    for limit, label in C.FROST_SEVERITY:
        if tmin <= limit:
            return label
    return "leve"


def heat_class(tmax: float | None) -> str:
    if tmax is None or pd.isna(tmax) or tmax < C.HEAT_TMAX_C:
        return "sin golpe de calor"
    for limit, label in C.HEAT_SEVERITY:
        if tmax >= limit:
            return label
    return "leve"


def prob_class(p: float | None) -> str:
    """Simbología del visor Minagri aplicada a una probabilidad 0-1."""
    if p is None or pd.isna(p):
        return "sin datos"
    if p >= C.PROB_HIGH:
        return "alta"
    if p >= C.PROB_MID:
        return "media"
    return "baja"


def event_probability(ensemble_values, threshold: float, above: bool) -> float | None:
    """P(evento) = fracción de miembros/pronósticos que cruzan el umbral.
    Requiere un ensamble externo (no hay fuente de pronóstico integrada)."""
    v = np.asarray([x for x in ensemble_values if x is not None and not pd.isna(x)], float)
    if v.size == 0:
        return None
    return float(((v > threshold) if above else (v <= threshold)).mean())


# ---------- QC ----------------------------------------------------------------
def qc_hourly(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col, (lo, hi) in C.PHYS_LIMITS.items():
        if col in out:
            out.loc[(out[col] < lo) | (out[col] > hi), col] = np.nan
    return out


# ---------- agregación diaria -------------------------------------------------
def daily_aggregate(h: pd.DataFrame) -> pd.DataFrame:
    h = qc_hourly(h).sort_index()
    g = h.groupby(h.index.floor("D"))
    d = pd.DataFrame({
        "tmin": g["ta"].min(), "tmax": g["ta"].max(), "tmean": g["ta"].mean(),
        "n_hours": g["ta"].count(),
    })
    if "hr" in h:
        d["rhmax"], d["rhmin"], d["rhmean"] = g["hr"].max(), g["hr"].min(), g["hr"].mean()
    if "pp" in h:
        d["pp"] = g["pp"].sum(min_count=1)
    if "rs" in h:
        d["rs_mj"] = g["rs"].mean() * 0.0864  # W/m2 medio diario -> MJ/m2/día
    if "ws" in h:
        d["ws_kmh"] = g["ws"].mean()
    d.loc[d["n_hours"] < C.MIN_HOURS_PER_DAY, ["tmin", "tmax", "tmean"]] = np.nan
    return d


# ---------- frío invernal -----------------------------------------------------
def chill_hours(ta: pd.Series) -> pd.Series:
    """Horas frío por día: nº de horas con CHILL_HOURS_MIN <= T <= CHILL_HOURS_MAX."""
    ok = (ta >= C.CHILL_HOURS_MIN_C) & (ta <= C.CHILL_HOURS_MAX_C)
    return ok.groupby(ta.index.floor("D")).sum().astype(float)


def utah_unit(t: float) -> float:
    """Modelo Utah (Richardson et al. 1974), unidades por hora."""
    if pd.isna(t):
        return 0.0
    if t <= 1.4: return 0.0
    if t <= 2.4: return 0.5
    if t <= 9.1: return 1.0
    if t <= 12.4: return 0.5
    if t <= 15.9: return 0.0
    if t <= 18.0: return -0.5
    return -1.0


def chill_units(ta: pd.Series) -> pd.Series:
    return ta.map(utah_unit).groupby(ta.index.floor("D")).sum()


def chill_season(ta: pd.Series) -> pd.DataFrame:
    """Acumulado mayo-agosto (temporada que usa agrometeorologia.cl).
    Porciones de frío (modelo Dinámico, Fishman) NO implementado."""
    t = ta[ta.index.month.isin(C.CHILL_SEASON_MONTHS)]
    if t.empty:
        return pd.DataFrame(columns=["horas_frio", "unidades_utah"])
    return pd.DataFrame({"horas_frio": chill_hours(t), "unidades_utah": chill_units(t)}).cumsum()


# ---------- grados día --------------------------------------------------------
def growing_degree_days(tmin: pd.Series, tmax: pd.Series, base: float) -> pd.Series:
    """Método promedio simple: max((Tmax+Tmin)/2 - base, 0). Método exacto del sitio no documentado."""
    return (((tmax + tmin) / 2) - base).clip(lower=0)


# ---------- ETo FAO-56 --------------------------------------------------------
def eto_fao56(tmin, tmax, rhmin, rhmax, ws_kmh, rs_mj, doy, lat_deg, elev_m,
              wind_height_m=C.WIND_HEIGHT_M) -> float:
    """Penman-Monteith FAO-56 diario (mm/día). Escalares. NaN si falta algún insumo."""
    vals = [tmin, tmax, rhmin, rhmax, ws_kmh, rs_mj]
    if any(v is None or pd.isna(v) for v in vals):
        return float("nan")
    tmean = (tmin + tmax) / 2
    u = ws_kmh / 3.6
    u2 = u * 4.87 / math.log(67.8 * wind_height_m - 5.42) if wind_height_m != 2 else u
    P = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26
    gamma = 0.000665 * P
    es = lambda t: 0.6108 * math.exp(17.27 * t / (t + 237.3))
    e_s = (es(tmax) + es(tmin)) / 2
    e_a = (es(tmin) * rhmax / 100 + es(tmax) * rhmin / 100) / 2
    delta = 4098 * es(tmean) / (tmean + 237.3) ** 2
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    dec = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws_ang = math.acos(max(-1, min(1, -math.tan(phi) * math.tan(dec))))
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws_ang * math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.sin(ws_ang))
    rso = (0.75 + 2e-5 * elev_m) * ra
    rns = (1 - 0.23) * rs_mj
    ratio = min(rs_mj / rso, 1.0) if rso > 0 else 0.5
    rnl = 4.903e-9 * (((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2) * (
        0.34 - 0.14 * math.sqrt(max(e_a, 0))) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    num = 0.408 * delta * rn + gamma * 900 / (tmean + 273) * u2 * (e_s - e_a)
    return max(num / (delta + gamma * (1 + 0.34 * u2)), 0.0)


# ---------- estrés térmico animal --------------------------------------------
def thi(ta: float, rh: float) -> float:
    """THI NRC: (1.8T+32) - (0.55 - 0.0055 RH)(1.8T - 26)."""
    if pd.isna(ta) or pd.isna(rh):
        return float("nan")
    return (1.8 * ta + 32) - (0.55 - 0.0055 * rh) * (1.8 * ta - 26)


def thi_class(v: float) -> str:
    if pd.isna(v):
        return "sin datos"
    for limit, label in C.THI_CLASSES:
        if v >= limit:
            return label
    return "sin estrés"


# ---------- tabla diaria completa --------------------------------------------
def daily_indices(h: pd.DataFrame, lat: float | None = None, elev: float | None = None) -> pd.DataFrame:
    d = daily_aggregate(h)
    d["helada"] = d["tmin"].map(frost_class)
    d["golpe_calor"] = d["tmax"].map(heat_class)
    for b in C.GDD_BASES:
        d[f"gd_{b:g}"] = growing_degree_days(d["tmin"], d["tmax"], b)
    hq = qc_hourly(h)
    if "hr" in hq:
        thi_h = pd.Series([thi(t, r) for t, r in zip(hq["ta"], hq["hr"])], index=hq.index)
        d["thi_max"] = thi_h.groupby(thi_h.index.floor("D")).max()
        d["estres_animal"] = d["thi_max"].map(thi_class)
    d["horas_frio"] = chill_hours(hq["ta"]).reindex(d.index)
    d["unidades_utah"] = chill_units(hq["ta"]).reindex(d.index)
    if {"rhmin", "rhmax", "ws_kmh", "rs_mj"} <= set(d.columns):
        la = C.DEFAULT_LAT if lat is None else lat
        el = C.DEFAULT_ELEV_M if elev is None else elev
        d["eto"] = [eto_fao56(r.tmin, r.tmax, r.rhmin, r.rhmax, r.ws_kmh, r.rs_mj,
                              i.dayofyear, la, el) for i, r in d.iterrows()]
    return d
