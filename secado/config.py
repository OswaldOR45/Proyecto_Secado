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


# --- Sesgo hacia humedad alta dentro de la meta (vender agua, no materia prima) ---
# Dentro de las corridas que YA cumplen humedad+AW, se prefiere la mitad con
# humedad mas alta para armar la receta de arranque (mismo AW, mas agua vendida).
# Si esa mitad se queda muy chica, se usa la base completa (no se sacrifica
# confiabilidad por sesgar el numero).
MIN_N_SESGO_HUMEDAD_ALTA = 3

# Piso de muestra para que un rango tipico (P25-P75) de rate/agua_termo sea
# estadisticamente estable. Con menos puntos, el "rango" son casi los mismos
# 2-3 numeros -- se amplia a una base mayor en vez de mostrar algo inestable.
MIN_N_RANGO_CONFIABLE = 5

# --- Modelo multivariante (zona clave + rate + agua_termo) -----------------------
# Separa el efecto de la zona del efecto del rate/agua_termo, que el operador
# suele mover a la vez (compensacion manual) y que si no se separan, sesgan la
# sensibilidad simple de una sola variable. Requiere suficientes grados de
# libertad y un ajuste minimamente razonable (R2) para reportarse; si no,
# se omite en vez de dar un numero inventado.
MIN_N_MULTIVARIANTE = 12      # ~4x los 3 predictores (zona, rate, agua_termo)
R2_MIN_MULTIVARIANTE = 0.25   # bajo esto, el modelo no explica lo suficiente
RATE_PASO_COMPENSACION = 500  # kg/h, unidad en la que se reporta la compensacion
AGUA_PASO_COMPENSACION = 50   # kg/h, unidad en la que se reporta el efecto del agua
COMP_RATE_MIN_DEG = 0.3       # tope piso: C de zona por cada 500kg/h de rate
COMP_RATE_MAX_DEG = 20.0      # tope techo: si sale fuera, no se reporta (no se recorta)

# --- Sensibilidad de AW a la zona (analoga a la de humedad, otra escala) ---------
# AW se mueve en centesimas (rango util ~0.06), no en unidades enteras como la
# humedad (rango util ~1.0). Se expresa "C por punto de AW" (punto = 0.01).
AW_SENS_MIN_POR_PUNTO = 5.0
AW_SENS_MAX_POR_PUNTO = 60.0

# --- Correccion automatica de la receta cuando el esperado sale fuera de meta ----
# Margen de seguridad: al corregir, no se apunta justo al limite sino un poco
# adentro, para no quedar al filo por variabilidad normal del proceso.
MARGEN_HUMEDAD_CORRECCION = 0.15   # puntos de %
MARGEN_AW_CORRECCION = 0.005       # unidades absolutas de AW
# Tope de sensatez: si el ajuste que pide el modelo lineal supera esto, el gap
# es demasiado grande para extrapolar con una sensibilidad local (el modelo
# es lineal solo cerca de los datos que lo alimentaron) -- se reporta como no
# confiable en vez de sugerir un salto de zona fisicamente absurdo.
CORRECCION_ZONA_MAX_DEG = 20.0

# --- Modelo ambiental continuo (temp_amb + hr) ------------------------------------
# Complementa la tabla de baldes (Dia frio / normal / caluroso...) con una
# sensibilidad continua cuando hay datos suficientes para sostenerla.
MIN_N_AMBIENTAL = 10
R2_MIN_AMBIENTAL = 0.15   # umbral mas bajo que el multivariante: solo 2 predictores


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