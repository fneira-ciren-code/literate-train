"""API REST + dashboard estático.  uvicorn riesgo_maule.api:app --reload"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from . import config as C
from . import indices as ix
from . import store

DB = os.environ.get("RIESGO_DB", str(C.DB_PATH))
STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Riesgo agroclimático — Región del Maule", version="0.1.0")


def _con():
    return store.connect(DB)


def _stations() -> pd.DataFrame:
    return store.load_stations()


def _num(v):
    return None if v is None or pd.isna(v) else round(float(v), 2)


@app.get("/api/meta")
def meta():
    con = _con()
    r = con.execute("SELECT COUNT(DISTINCT station_id), MIN(ts), MAX(ts) FROM obs_hourly").fetchone()
    return {"region": C.REGION, "stations_with_data": r[0], "first_ts": r[1], "last_ts": r[2],
            "db": Path(DB).name,
            "thresholds": {"helada_tmin_c": C.FROST_TMIN_C, "golpe_calor_tmax_c": C.HEAT_TMAX_C,
                           "frio_horas_rango_c": [C.CHILL_HOURS_MIN_C, C.CHILL_HOURS_MAX_C],
                           "gdd_bases": list(C.GDD_BASES)},
            "caveats": ["umbrales de intensidad, THI y horas frío son SUPUESTOS; ver config.py",
                        "ETo usa lat/elev por defecto si la estación no los tiene"]}


@app.get("/api/stations")
def stations():
    st = _stations()
    return [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in st.to_dict("records")]


@app.get("/api/risk/summary")
def risk_summary(date: str | None = Query(None, description="YYYY-MM-DD; por defecto último día con datos")):
    con, st = _con(), _stations()
    last = con.execute("SELECT MAX(ts) FROM obs_hourly").fetchone()[0]
    if last is None:
        raise HTTPException(404, "Sin datos. Ejecutar import-csv o demo.")
    day = pd.Timestamp(date or last).floor("D")
    out = []
    for r in st.itertuples():
        h = store.read_hourly(con, r.id, day, day + pd.Timedelta(days=1))
        if h.empty:
            out.append({"id": r.id, "name": r.name, "comuna": r.comuna, "provider": r.provider,
                        "date": str(day.date()), "status": "sin datos"})
            continue
        d = ix.daily_indices(h).iloc[0]
        out.append({"id": r.id, "name": r.name, "comuna": r.comuna, "provider": r.provider,
                    "lat": None if pd.isna(r.lat) else r.lat, "lon": None if pd.isna(r.lon) else r.lon,
                    "date": str(day.date()), "status": "ok" if d["n_hours"] >= C.MIN_HOURS_PER_DAY else "incompleto",
                    "n_hours": int(d["n_hours"]), "tmin": _num(d["tmin"]), "tmax": _num(d["tmax"]),
                    "helada": d["helada"], "golpe_calor": d["golpe_calor"],
                    "estres_animal": d.get("estres_animal"), "thi_max": _num(d.get("thi_max")),
                    "pp": _num(d.get("pp"))})
    return out


@app.get("/api/station/{sid}/daily")
def station_daily(sid: str, start: str | None = None, end: str | None = None):
    st = _stations().set_index("id")
    if sid not in st.index:
        raise HTTPException(404, "estación desconocida")
    s = st.loc[sid]
    lat = None if pd.isna(s["lat"]) else s["lat"]
    elev = None if pd.isna(s["elev_m"]) else s["elev_m"]
    h = store.read_hourly(_con(), sid, start, end)
    if h.empty:
        raise HTTPException(404, "sin datos en el rango")
    d = ix.daily_indices(h, lat, elev)
    d.index = d.index.strftime("%Y-%m-%d")
    rec = d.reset_index(names="date").astype(object).where(d.reset_index(names="date").notna(), None)
    return {"station": sid, "eto_params": "estación" if lat is not None and elev is not None else "DEFAULT_REGIONAL (supuesto)",
            "rows": rec.to_dict("records")}


@app.get("/api/chill/season")
def chill_season(year: int):
    con, st = _con(), _stations()
    out = []
    for r in st.itertuples():
        h = store.read_hourly(con, r.id, f"{year}-05-01", f"{year}-09-01")
        if h.empty:
            continue
        c = ix.chill_season(ix.qc_hourly(h)["ta"])
        if not c.empty:
            out.append({"id": r.id, "name": r.name, "comuna": r.comuna,
                        "horas_frio": _num(c["horas_frio"].iloc[-1]), "unidades_utah": _num(c["unidades_utah"].iloc[-1]),
                        "hasta": str(c.index[-1].date())})
    return out


@app.get("/api/frost/events")
def frost_events(start: str, end: str, kind: str = Query("helada", pattern="^(helada|golpe_calor)$")):
    """Conteo de días con evento por estación (equivalente al visor de eventos de Minagri, pero observado)."""
    con, st = _con(), _stations()
    out = []
    for r in st.itertuples():
        h = store.read_hourly(con, r.id, start, pd.Timestamp(end) + pd.Timedelta(days=1))
        if h.empty:
            continue
        d = ix.daily_indices(h)
        ev = d[~d[kind].str.startswith("sin")]
        out.append({"id": r.id, "name": r.name, "comuna": r.comuna, "dias_evento": int(len(ev)),
                    "dias_validos": int(d["tmin"].notna().sum()),
                    "peor": _num(d["tmin"].min() if kind == "helada" else d["tmax"].max())})
    return sorted(out, key=lambda x: -x["dias_evento"])


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
