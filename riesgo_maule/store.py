"""Persistencia SQLite + carga de estaciones + importador CSV con mapeo de columnas configurable."""
from __future__ import annotations

import re
import sqlite3
import unicodedata

import numpy as np
import pandas as pd

from . import config as C

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations(id TEXT PRIMARY KEY, name TEXT, comuna TEXT, provider TEXT,
  lat REAL, lon REAL, elev_m REAL);
CREATE TABLE IF NOT EXISTS obs_hourly(station_id TEXT, ts TEXT, ta REAL, hr REAL, pp REAL, rs REAL, ws REAL,
  PRIMARY KEY(station_id, ts));
"""


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def connect(path=C.DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def load_stations(con=None) -> pd.DataFrame:
    st = pd.read_csv(C.STATIONS_CSV)
    st["id"] = [slug(f"{n}-{p}") for n, p in zip(st["name"], st["provider"])]
    if con is not None:
        st.to_sql("stations", con, if_exists="replace", index=False)
    return st


def write_hourly(con, station_id: str, df: pd.DataFrame) -> int:
    d = df.copy()
    d.index = pd.to_datetime(d.index)
    d = d[~d.index.duplicated(keep="last")]
    rows = [(station_id, ts.strftime("%Y-%m-%d %H:%M:%S"),
             *[None if pd.isna(r.get(c, np.nan)) else float(r[c]) for c in ("ta", "hr", "pp", "rs", "ws")])
            for ts, r in d.iterrows()]
    con.executemany("INSERT OR REPLACE INTO obs_hourly VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def read_hourly(con, station_id: str, start=None, end=None) -> pd.DataFrame:
    q, p = "SELECT ts, ta, hr, pp, rs, ws FROM obs_hourly WHERE station_id=?", [station_id]
    if start:
        q += " AND ts>=?"; p.append(str(start))
    if end:
        q += " AND ts<?"; p.append(str(end))
    df = pd.read_sql_query(q + " ORDER BY ts", con, params=p)
    df["ts"] = pd.to_datetime(df["ts"])
    return df.set_index("ts")


# ---- importador CSV (exportación de agrometeorologia.cl: formato NO verificado) --------
# El sitio permite exportar CSV tras una pregunta de verificación humana; no se automatiza.
# Se aceptan nombres de columna por coincidencia de subcadena; ajustar con --map si difiere.
DEFAULT_MAP = {
    "ts": ["fecha", "date", "hora", "timestamp", "datetime"],
    "ta": ["temperatura del aire", "temp_aire", "ta", "temperatura"],
    "hr": ["humedad relativa", "humedad", "hr"],
    "pp": ["precipitación", "precipitacion", "pp", "lluvia"],
    "rs": ["radiación", "radiacion", "rs"],
    "ws": ["velocidad de viento", "velocidad", "viento", "ws"],
}


def _pick(cols, candidates):
    low = {c: c.lower().strip() for c in cols}
    for cand in candidates:                       # exacto primero, luego subcadena
        for c, l in low.items():
            if l == cand:
                return c
    for cand in candidates:
        for c, l in low.items():
            if cand in l:
                return c
    return None


def parse_csv(path, mapping: dict | None = None, sep=None, decimal=".") -> pd.DataFrame:
    raw = pd.read_csv(path, sep=sep, engine="python", decimal=decimal)
    m = {k: (mapping or {}).get(k) or _pick(raw.columns, v) for k, v in DEFAULT_MAP.items()}
    if m["ts"] is None or m["ta"] is None:
        raise ValueError(f"No se identificaron columnas de fecha/temperatura. Columnas: {list(raw.columns)}")
    out = pd.DataFrame({k: raw[c] for k, c in m.items() if c is not None and k != "ts"})
    out.index = pd.to_datetime(raw[m["ts"]], errors="coerce", dayfirst=True)
    out = out[out.index.notna()]
    for c in out.columns:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out
