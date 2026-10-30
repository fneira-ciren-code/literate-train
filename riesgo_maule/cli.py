"""CLI:  python -m riesgo_maule.cli init | import-csv | demo"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

from . import config as C
from . import store


def cmd_init(a):
    con = store.connect(a.db)
    st = store.load_stations(con)
    print(f"{len(st)} estaciones Maule cargadas en {a.db}")


def cmd_import(a):
    con = store.connect(a.db)
    st = store.load_stations(con)
    if a.station not in set(st["id"]):
        raise SystemExit(f"station_id inválido. Ejemplos: {st['id'].head(5).tolist()}")
    df = store.parse_csv(a.csv, json.loads(a.map) if a.map else None, sep=a.sep, decimal=a.decimal)
    print(f"{store.write_hourly(con, a.station, df)} filas -> {a.station}")


def synth_station(seed: int, start, end) -> pd.DataFrame:
    """Serie horaria SINTÉTICA (ciclo anual+diario + ruido). Solo para demo/test; sin valor climatológico."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="h")
    doy = idx.dayofyear.values
    hour = idx.hour.values
    base = 14 - 7 * np.cos(2 * np.pi * (doy - 15) / 365)             # mín. en julio (hemisferio sur)
    amp = 5 + 3 * (1 - np.cos(2 * np.pi * (doy - 15) / 365)) / 2 * -1 + 6
    daily_noise = np.repeat(rng.normal(0, 2.5, len(idx) // 24 + 2), 24)[: len(idx)]
    ta = base + amp * np.sin(2 * np.pi * (hour - 9) / 24) + daily_noise + rng.normal(0, .4, len(idx))
    hr = np.clip(75 - 2.2 * (ta - base) + rng.normal(0, 4, len(idx)), 15, 100)
    sun = np.clip(np.sin(np.pi * (hour - 6) / 12), 0, None)
    rs = 900 * sun * (0.6 + 0.4 * (1 - np.cos(2 * np.pi * (doy - 355) / 365)) / 2) * rng.uniform(.5, 1, len(idx))
    ws = np.clip(8 + 6 * sun + rng.normal(0, 3, len(idx)), 0, None)
    pp = np.where(rng.random(len(idx)) < (0.02 + 0.03 * (base < 12)), rng.exponential(1.2, len(idx)), 0.0)
    return pd.DataFrame({"ta": ta, "hr": hr, "pp": pp, "rs": rs, "ws": ws}, index=idx)


def cmd_demo(a):
    con = store.connect(a.db)
    st = store.load_stations(con)
    for i, sid in enumerate(st["id"]):
        df = synth_station(i, a.start, a.end)
        df["ta"] += np.random.default_rng(1000 + i).normal(0, 1.2)  # sesgo por estación
        store.write_hourly(con, sid, df)
    print(f"DEMO SINTÉTICO: {len(st)} estaciones, {a.start}..{a.end} -> {a.db}")


def main():
    p = argparse.ArgumentParser(prog="riesgo_maule")
    p.add_argument("--db", default=os.environ.get("RIESGO_DB", str(C.DB_PATH)))
    sp = p.add_subparsers(required=True)
    sp.add_parser("init").set_defaults(f=cmd_init)
    i = sp.add_parser("import-csv")
    i.add_argument("station"); i.add_argument("csv")
    i.add_argument("--map", help='JSON {"ta":"Columna temp","ts":"Fecha"...}')
    i.add_argument("--sep", default=None); i.add_argument("--decimal", default=".")
    i.set_defaults(f=cmd_import)
    d = sp.add_parser("demo")
    d.add_argument("--start", default="2026-04-01"); d.add_argument("--end", default="2026-10-30 23:00")
    d.set_defaults(f=cmd_demo)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
