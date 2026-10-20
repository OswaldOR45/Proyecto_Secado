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


# --- OBJETIVO DE NEGOCIO ----------------------------------------------------------
# Lograr la MAYOR humedad posible sin que el AW se acerque al limite.
#   * Perro: humedad minima 9.0%, SIN tope superior (mas humedad = mejor).
#   * Gato (SilverCat): humedad 7.5-8.5%; se busca lo mas cerca posible de 8.5
#     sin pasarse (al gato no le gusta la croqueta mas humeda).
#   * AW: 0.5999 es el limite seguro; 0.61 o mas es desviacion -> reproceso.
HUMEDAD_MIN   = 9.0
HUMEDAD_MAX   = float("inf")   # sin tope superior para perro
AW_MIN_IDONEO = 0.50           # piso de especificacion (LIAW real de calidad); casi nunca es el problema
AW_MAX_IDONEO = 0.5999         # limite seguro
AW_DESVIACION = 0.61           # >= esto: desviacion y reproceso

# AW esperado (mediana de la receta) que se usa como META DE DISENO al decidir
# cuanta humedad se puede ganar. Esta por debajo de 0.5999 a proposito: las
# corridas individuales se dispersan alrededor de la mediana, y con la bitacora
# (mayo-oct 2026) se midio que con humedad 9.5-10% la mediana de AW es ~0.566
# y ~4.5% de corridas pasan de 0.5999; con 10-10.5% la mediana es ~0.588 y 16% pasan.
# Apuntar a ~0.57 deja ~5% de riesgo. Subirlo gana humedad pero aumenta ese riesgo.
AW_OBJETIVO_ESPERADO = 0.57
AW_ALERTA_MONITOREAR = 0.58    # AW promedio desde el cual se marca "Monitorear" en la tabla ambiental

# --- Limites por especie -----------------------------------------------------
# Gato (SilverCat): humedad 7.5-8.5% y AW solo con tope (no exceder 0.5999, sin piso).
PRODUCTOS_GATO = {"SilverCat"}


def limites(producto: str) -> dict:
    """Limites de calidad vigentes para un producto. h_max es inf para perro."""
    if producto in PRODUCTOS_GATO:
        return {"h_min": 7.5, "h_max": 8.5, "aw_min": 0.0, "aw_max": AW_MAX_IDONEO}
    return {"h_min": HUMEDAD_MIN, "h_max": HUMEDAD_MAX,
            "aw_min": AW_MIN_IDONEO, "aw_max": AW_MAX_IDONEO}


def texto_meta_humedad(producto: str = None) -> str:
    """Meta de humedad en texto. Sin producto: perro y gato juntos."""
    gato = f"{limites('SilverCat')['h_min']:.1f}–{limites('SilverCat')['h_max']:.1f}%"
    perro = f"≥ {HUMEDAD_MIN:.1f}% (sin tope)"
    if producto is None:
        return f"{perro} perro · {gato} gato"
    return gato if producto in PRODUCTOS_GATO else perro


def texto_meta_aw() -> str:
    return f"< {AW_MAX_IDONEO} (≥ {AW_DESVIACION} es desviación)"


# --- Zonas del secador -----------------------------------------------------------
ZONAS = ["z1", "z2", "z3", "z4"]
ZONA_NOMBRE = {"z1": "Zona 1", "z2": "Zona 2", "z3": "Zona 3", "z4": "Zona 4"}

# Zonas que se mueven JUNTAS en un ajuste normal (el secador es aire caliente
# circulando: mover una sola zona exige muchos grados; mover varias, pocos).
# Zona 4 solo en casos raros (cuando Z1-Z3 ya llegaron al tope y no alcanza).
ZONAS_AJUSTE = ["z1", "z2", "z3"]
ZONAS_AJUSTE_TXT = "Z1–Z3"


# --- Validaciones de datos --------------------------------------------------------
# Rate por debajo de este umbral se considera error de captura (excluido del calculo)
RATE_MINIMO_VALIDO = 1000   # kg/h
# Una zona fuera de este rango (apagada, en 0, o typo como 275) saca la corrida
# del analisis: no representa una receta real de 4 zonas.
ZONA_MIN_VALIDA = 60        # C
ZONA_MAX_VALIDA = 140       # C


# --- Ajuste conjunto de zonas -----------------------------------------------------
# Tope de grados por zona en UN ajuste. Con ~5-6 C por zona ya se mueve ~0.5% de
# humedad; saltos mayores no son necesarios (y extrapolan el modelo).
AJUSTE_MAX_POR_ZONA = 6      # C por zona, por ajuste
AJUSTE_MIN_DEG      = 2.0    # abajo de esto la receta se considera ya en su punto

# Sensibilidad conjunta: C (promedio de Z1-Z3 movidas a la vez) por cada 1% de humedad.
# Se estima de los cambios entre corridas consecutivas (mismo producto x linea,
# menos de PAR_MAX_HORAS entre ellas), controlando por agua_termo.
# Bitacora mayo-oct 2026, 249 pares: 10.5 C por 1% (IC95 8.6-13.5).
PAR_MAX_HORAS          = 12
MIN_PARES_SENS_GLOBAL  = 30
MIN_PARES_SENS_PROPIA  = 30     # pares de ESE producto x linea para usar su propia estimacion
T_MIN_SENS_PROPIA      = 3.0    # |t| minimo del coeficiente para confiar en la propia
SENS_CONJ_MIN_DEG_POR_PCT = 6.0
SENS_CONJ_MAX_DEG_POR_PCT = 25.0
SENS_CONJ_DEFAULT_DEG_POR_PCT = 10.5   # si no hay datos/fechas para estimar
# Cuanto AW sube por cada 1% de humedad ganada (misma fuente: 0.0062 AW/C ÷ 0.095 %/C)
AW_POR_PCT_MIN     = 0.03
AW_POR_PCT_MAX     = 0.10
AW_POR_PCT_DEFAULT = 0.06

# Margen de seguridad al apuntar al tope de humedad del gato (8.5)
MARGEN_HUMEDAD_CORRECCION = 0.15   # puntos de %


# --- Sesgo hacia humedad alta dentro de la meta (vender agua, no materia prima) ---
# Dentro de las corridas que YA cumplen humedad+AW, se prefiere la mitad con
# humedad mas alta para armar la receta de arranque (mismo AW, mas agua vendida).
# Si esa mitad se queda muy chica, se usa la base completa.
MIN_N_SESGO_HUMEDAD_ALTA = 3

# Piso de muestra para que un rango tipico (P25-P75) de rate/agua_termo sea
# estadisticamente estable.
MIN_N_RANGO_CONFIABLE = 5

# --- Modelo multivariante (promedio Z1-Z3 + rate + agua_termo) -------------------
MIN_N_MULTIVARIANTE = 12
R2_MIN_MULTIVARIANTE = 0.25
RATE_PASO_COMPENSACION = 500  # kg/h, unidad en la que se reporta la compensacion
AGUA_PASO_COMPENSACION = 50   # kg/h, unidad en la que se reporta el efecto del agua
COMP_RATE_MIN_DEG = 0.3       # C de Z1-Z3 por cada 500 kg/h de rate (piso)
COMP_RATE_MAX_DEG = 20.0      # techo: si sale fuera, no se reporta

# --- Modelo ambiental continuo (temp_amb + hr) ------------------------------------
MIN_N_CONDICION = 2
MIN_N_AMBIENTAL = 10
R2_MIN_AMBIENTAL = 0.15


# --- Umbrales de confiabilidad por # de corridas EN META -------------------------
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
