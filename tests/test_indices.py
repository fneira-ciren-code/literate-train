import math

import numpy as np
import pandas as pd
import pytest

from riesgo_maule import indices as ix
from riesgo_maule import store


def test_frost_classes():
    assert ix.frost_class(1.0) == "sin helada"
    assert ix.frost_class(0.0) == "leve"
    assert ix.frost_class(-2.5) == "moderada"
    assert ix.frost_class(-5) == "severa"
    assert ix.frost_class(float("nan")) == "sin helada"


def test_heat_and_prob_classes():
    assert ix.heat_class(28.9) == "sin golpe de calor"
    assert ix.heat_class(29.0) == "leve"
    assert ix.heat_class(36) == "severo"
    assert ix.prob_class(0.95) == "alta" and ix.prob_class(0.7) == "media" and ix.prob_class(0.3) == "baja"
    assert ix.event_probability([-1, -2, 1, 2], 0.0, above=False) == 0.5


def test_gdd():
    g = ix.growing_degree_days(pd.Series([2.0, 10.0]), pd.Series([12.0, 24.0]), 10)
    assert g.tolist() == [0.0, 7.0]


def test_utah_and_chill_hours():
    idx = pd.date_range("2026-06-01", periods=24, freq="h")
    ta = pd.Series([5.0] * 10 + [20.0] * 14, index=idx)
    assert ix.chill_hours(ta).iloc[0] == 10
    assert ix.chill_units(ta).iloc[0] == 10 * 1.0 + 14 * -1.0
    assert ix.utah_unit(2.0) == 0.5 and ix.utah_unit(13) == 0.0


def test_eto_fao56_reference_example():
    # FAO-56 Ejemplo 18 (Uccle, Bélgica, 6 jul): ETo ≈ 3.9 mm/d con insumos diarios.
    # Con Rs medido 22.07 MJ/m2, u2 = 2.078 m/s, lat 50.8, z=100 m. wind_height=2 evita reescalado.
    v = ix.eto_fao56(12.3, 21.5, 63, 84, 2.078 * 3.6, 22.07, 187, 50.80, 100, wind_height_m=2)
    assert v == pytest.approx(3.9, abs=0.25)


def test_thi():
    assert ix.thi(30, 50) == pytest.approx(1.8 * 30 + 32 - (0.55 - 0.0055 * 50) * (1.8 * 30 - 26), rel=1e-9)
    assert ix.thi_class(85) == "peligro/emergencia" and ix.thi_class(60) == "sin estrés"


def _day(tmin, tmax, hours=24):
    idx = pd.date_range("2026-07-10", periods=hours, freq="h")
    ta = np.linspace(tmin, tmax, hours)
    return pd.DataFrame({"ta": ta, "hr": 70.0, "pp": 0.0, "rs": 100.0, "ws": 10.0}, index=idx)


def test_daily_indices_and_incomplete_day():
    d = ix.daily_indices(_day(-3, 10))
    assert d["helada"].iloc[0] == "moderada" and d["tmin"].iloc[0] == -3
    assert "eto" in d and "gd_5" in d
    inc = ix.daily_indices(_day(-3, 10, hours=10))   # < MIN_HOURS_PER_DAY
    assert math.isnan(inc["tmin"].iloc[0]) and inc["helada"].iloc[0] == "sin helada"


def test_qc_drops_impossible_values():
    h = _day(5, 15); h.iloc[3, h.columns.get_loc("ta")] = 99
    assert ix.qc_hourly(h)["ta"].isna().sum() == 1


def test_store_roundtrip_and_csv_parse(tmp_path):
    con = store.connect(tmp_path / "t.sqlite")
    st = store.load_stations(con)
    sid = st["id"].iloc[0]
    store.write_hourly(con, sid, _day(0, 10))
    assert len(store.read_hourly(con, sid)) == 24
    csv = tmp_path / "x.csv"
    csv.write_text("Fecha,Temperatura del Aire,Humedad Relativa\n10-07-2026 01:00,3.5,80\n10-07-2026 02:00,2.5,82\n")
    df = store.parse_csv(csv)
    assert df["ta"].tolist() == [3.5, 2.5] and df.index[0] == pd.Timestamp("2026-07-10 01:00")
    assert len(st) == 38 and st["id"].is_unique
