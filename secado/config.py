# -*- coding: utf-8 -*-
"""Configuracion central. Ajusta aqui rangos, columnas y umbrales.
Cualquier cambio se refleja en todo el proyecto sin tocar la logica."""

# --- Fuente de datos por defecto -------------------------------------------------
# Puede ser una URL (Google Sheets publicado como CSV) o una ruta local .csv/.xlsx.
# Se sobre-escribe pasandola como argumento del comando.
FUENTE_DATOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR-bbwqqMO53WDOPKzA-SYcEifevDMY5TpsdlcnYce5LkCofKD7fcrirem1EKvGQDhvsDXRLHUufy2p/pub?gid=0&single=true&output=csv"


# --- Mapeo de columnas (por POSICION, A=0 .. Q=16) --------------------------------
# Robusto a acentos y mayusculas en los encabezados. Solo importa el orden.
COLUMNAS = {
    "fecha_hora":   0,   # A
    "producto":     1,   # B
    "peso":         2,   # C
    "linea":        3,   # D
    "z1":           4,   # E
    "z2":           5,   # F
    "z3":           6,   # G
    "z4":           7,   # H
    "agua_termo":   8,   # I
    "z2_extruder":  9,   # J
    "rate":        10,   # K
    "humedad":     11,   # L
    "aw":          12,   # M
    "hr":          13,   # N
    "temp_amb":    14,   # O
    "realiza":     15,   # P
    "supervisor":  16,   # Q
}


# --- Metas de calidad (confirmadas por calidad) -----------------------------------
HUMEDAD_MIN   = 9.0
HUMEDAD_MAX   = 10.0
HUMEDAD_OBJ   = (HUMEDAD_MIN + HUMEDAD_MAX) / 2.0   # 9.5%, centro del rango
AW_MIN_IDONEO = 0.5200
AW_MAX_IDONEO = 0.5800


# --- Zonas del secador -----------------------------------------------------------
ZONAS = ["z1", "z2", "z3", "z4"]
ZONA_NOMBRE = {"z1": "Zona 1", "z2": "Zona 2", "z3": "Zona 3", "z4": "Zona 4"}


# --- Validaciones de datos --------------------------------------------------------
# Rate por debajo de este umbral se considera error de captura (excluido del calculo)
RATE_MINIMO_VALIDO = 1000   # kg/h


# --- Eleccion de zona clave y estimacion de ajustes ------------------------------
# Zona 3 es la variable de mayor impacto segun el reporte v2 del proceso.
# Se usa como zona clave por defecto y SOLO se sustituye si los datos muestran
# que otra zona domina con claridad.
DEFAULT_ZONA_CLAVE = "z3"
MIN_CORR_CLAVE     = 0.40    # |correlacion| minima para confiar en una zona
MARGEN_CLAVE       = 0.15    # cuanto debe superar a las demas para sustituir a Z3


# --- Topes para que las recomendaciones sean siempre realistas -------------------
SENS_MIN_DEG_POR_PCT = 2.0    # C por cada 1% de humedad (piso)
SENS_MAX_DEG_POR_PCT = 15.0   # C por cada 1% de humedad (techo)
AJUSTE_AMB_CAP       = 12.0   # tope absoluto del ajuste ambiental sugerido (C)
MIN_N_CONDICION      = 2      # registros minimos por condicion para sugerir numero


# --- Umbrales de confiabilidad por # de corridas EN RANGO ------------------------
# Estos umbrales se usan para etiquetar la fiabilidad de la tabla de arranque.
# Recomendado para validacion: 30 EN RANGO por producto y linea (suficiente para Cpk).
def etiqueta_confiabilidad(n_en_rango: int) -> str:
    if n_en_rango >= 30:
        return "MUY ALTA"
    if n_en_rango >= 10:
        return "ALTA"
    if n_en_rango >= 5:
        return "MEDIA"
    if n_en_rango >= 2:
        return "BAJA"
    if n_en_rango == 1:
        return "MUY BAJA (1 corrida)"
    return "SIN DATOS EN RANGO"


# --- Clasificacion ambiental ------------------------------------------------------
# Mismas categorias que el reporte v2. Si quieres ajustarlas, edita aqui.
import pandas as _pd

def clasificar_ambiente(temp_amb: float, hr: float) -> str:
    if _pd.isna(temp_amb):
        return "Sin dato ambiental"
    if temp_amb < 25:
        return "Dia frio (<25C)"
    if temp_amb > 30 and not _pd.isna(hr) and hr < 30:
        return "Caluroso + seco (>30C, HR<30%)"
    if temp_amb > 30 and not _pd.isna(hr) and hr >= 30:
        return "Caluroso + humedo (>30C, HR>=30%)"
    return "Dia normal (25-32C)"


# Orden en que se presentan las condiciones ambientales en los reportes
ORDEN_AMBIENTAL = [
    "Dia frio (<25C)",
    "Dia normal (25-32C)",
    "Caluroso + humedo (>30C, HR>=30%)",
    "Caluroso + seco (>30C, HR<30%)",
]