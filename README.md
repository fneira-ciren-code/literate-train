# Riesgo agroclimático — Región del Maule (v0.1)

Réplica funcional, acotada al Maule, de dos fuentes:
- riesgosagricolas.minagri.gob.cl → visor heladas/golpes de calor (umbrales, simbología de probabilidad)
- agrometeorologia.cl → frío invernal, grados día (base 5/10/12.5), ETo, estrés térmico animal

## Uso
```bash
pip install fastapi uvicorn pandas numpy pytest httpx python-multipart
python -m riesgo_maule.cli init                       # carga 38 estaciones Maule -> data/maule.sqlite
python -m riesgo_maule.cli import-csv <station_id> export.csv [--map '{"ta":"Temp","ts":"Fecha"}']
uvicorn riesgo_maule.api:app --reload                 # http://127.0.0.1:8000
pytest -q
# demo con datos SINTÉTICOS:
RIESGO_DB=data/demo.sqlite python -m riesgo_maule.cli demo && RIESGO_DB=data/demo.sqlite uvicorn riesgo_maule.api:app
```

## Qué NO está resuelto (decisiones tuyas)
1. **Ingesta real**: ninguno de los dos sitios documenta API pública. La exportación CSV de agrometeorologia.cl exige verificación humana; no se automatizó. Opciones: solicitar acceso a INIA/AGROMET (info@agromet.cl), o cargar CSV manualmente. El formato del CSV no fue verificado: `parse_csv` infiere columnas por nombre.
2. **Coordenadas/elevación** de las 38 estaciones: vacías en `data/stations_maule.csv` (no inventadas). Sin ellas no hay mapa y ETo usa centroide regional.
3. **Pronóstico**: el visor de Minagri muestra *probabilidad* de evento; aquí solo hay `event_probability()` sobre un ensamble que debes proveer (DMC u otro). El sistema actual evalúa solo observado.
4. **Porciones de frío (Dinámico)**, índice **pasto** y **tizón tardío**: no implementados.
5. **Supuestos** en `config.py` (marcados `[SUPUESTO]`): Tmin ≤ 0 °C (el visor dice ">= 0", probable typo), escalones de intensidad, 0–7.2 °C para horas frío, THI NRC, unidad de radiación y altura de viento.
