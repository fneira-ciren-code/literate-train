"""Interfaz de fuentes de datos. La ingesta real queda por definir: implementar un adaptador por
fuente y registrarlo en SOURCES. El resto del sistema solo consume el esquema horario
(ta °C, hr %, pp mm, rs W/m2, ws km/h) vía store.write_hourly()."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from . import store


class Source(Protocol):
    name: str

    def fetch(self, station_id: str, start: str, end: str) -> pd.DataFrame:
        """Devuelve DataFrame con DatetimeIndex horario y columnas ta, hr, pp, rs, ws."""
        ...


class CsvFolderSource:
    """Lee <carpeta>/<station_id>.csv exportados manualmente (ver store.parse_csv)."""
    name = "csv_folder"

    def __init__(self, folder: str | Path, mapping: dict | None = None, sep=None, decimal="."):
        self.folder, self.mapping, self.sep, self.decimal = Path(folder), mapping, sep, decimal

    def fetch(self, station_id, start, end):
        df = store.parse_csv(self.folder / f"{station_id}.csv", self.mapping, self.sep, self.decimal)
        return df.loc[start:end]


class AgrometApiSource:
    """PENDIENTE: no hay API pública documentada en agrometeorologia.cl ni en riesgosagricolas.minagri.gob.cl."""
    name = "agromet_api"

    def fetch(self, station_id, start, end):
        raise NotImplementedError("Definir acceso (convenio INIA/AGROMET) antes de implementar.")


SOURCES: dict[str, type] = {"csv_folder": CsvFolderSource, "agromet_api": AgrometApiSource}


def ingest(con, source: Source, station_ids, start: str, end: str) -> dict[str, int]:
    return {sid: store.write_hourly(con, sid, source.fetch(sid, start, end)) for sid in station_ids}
