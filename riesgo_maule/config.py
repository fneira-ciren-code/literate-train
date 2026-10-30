"""Parámetros del sistema. Todo umbral marcado [SUPUESTO] no está documentado en las
fuentes consultadas (riesgosagricolas.minagri.gob.cl, agrometeorologia.cl) y debe validarse."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "maule.sqlite"
STATIONS_CSV = ROOT / "data" / "stations_maule.csv"

REGION = "Maule"

# --- Heladas -----------------------------------------------------------------
# El visor de Minagri declara "heladas (T°C >= 0°C)": casi seguro es typo de <= 0 (>= 0 sería
# casi siempre verdadero). Se usa Tmin <= 0 °C. [SUPUESTO]
FROST_TMIN_C = 0.0
# Intensidad (clasificación agronómica habitual) [SUPUESTO]
FROST_SEVERITY = [(-4.0, "severa"), (-2.0, "moderada"), (0.0, "leve")]  # Tmin <= límite

# --- Golpe de calor ----------------------------------------------------------
HEAT_TMAX_C = 29.0  # visor Minagri: "golpes de calor (T°C > 29°C)"
HEAT_SEVERITY = [(35.0, "severo"), (32.0, "moderado"), (29.0, "leve")]  # Tmax >= límite [SUPUESTO escalones]

# --- Probabilidad (simbología del visor Minagri) ------------------------------
PROB_HIGH = 0.90   # alta  >= 90 %
PROB_MID = 0.66    # media >= 66 % y < 90 %; baja < 66 % (el visor dice "<= 66", solapa en 66)

# --- Frío invernal -----------------------------------------------------------
CHILL_SEASON_MONTHS = (5, 6, 7, 8)  # agrometeorologia.cl: "Temporada (may. - ago.)"
CHILL_HOURS_MAX_C = 7.2             # horas frío: 0 <= T <= 7.2 °C [SUPUESTO, convención clásica]
CHILL_HOURS_MIN_C = 0.0

# --- Grados día --------------------------------------------------------------
GDD_BASES = (5.0, 10.0, 12.5)       # agrometeorologia.cl: "Base 5, 10 y 12.5"

# --- ETo (FAO-56 Penman-Monteith diario) ---------------------------------------
# Sin lat/elev por estación se usa el centroide regional. [SUPUESTO — reemplazar con coordenadas reales]
DEFAULT_LAT = -35.4
DEFAULT_ELEV_M = 150.0
WIND_HEIGHT_M = 10.0                # [SUPUESTO] altura del anemómetro; ajustar a 2 m con perfil log
RS_UNITS_TO_MJ = 0.0036             # W/m2 promedio horario -> MJ/m2/h [SUPUESTO unidad de RD]

# --- Estrés térmico animal (THI) --------------------------------------------
# Fórmula NRC (1971). El índice exacto de agrometeorologia.cl no está documentado. [SUPUESTO]
THI_CLASSES = [(84.0, "peligro/emergencia"), (79.0, "alerta"), (72.0, "estrés leve")]  # THI >= límite

# --- Calidad de datos --------------------------------------------------------
MIN_HOURS_PER_DAY = 18              # días con menos horas válidas -> sin índice diario
PHYS_LIMITS = {"ta": (-25, 50), "hr": (0, 100), "pp": (0, 150), "rs": (0, 1400), "ws": (0, 200)}
