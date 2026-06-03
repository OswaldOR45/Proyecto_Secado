# -*- coding: utf-8 -*-
"""Estadistica descriptiva, correlaciones, sensibilidad, eleccion de zona clave
y generacion de reglas operativas. Ninguna funcion aqui imprime o exporta:
todas devuelven datos. La presentacion vive en los modulos *_report."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from . import config


# =================================================================================
#  Resultado por (producto, linea)  --  estructura de datos que consumen los reportes
# =================================================================================

@dataclass
class ResultadoProducto:
    producto: str
    linea: str
    n_total: int
    n_en_rango: int
    confiabilidad: str
    humedad_prom: float
    humedad_std: float
    aw_prom: float
    arranque: dict          # {z1..z4: int, rate: int, agua_termo: int}
    zona_clave: str         # "z3" por defecto
    correlaciones: dict     # {z1..z4: corr con humedad}
    sensibilidad: dict      # {z1..z4: C por 1% de humedad (con signo)}
    sens_clave: float | None  # sensibilidad robusta de la zona clave (None si insuficiente)
    reglas: list[str]


# =================================================================================
#  Helpers privados (no se exportan)
# =================================================================================

def _correlaciones_zona(g: pd.DataFrame) -> dict:
    """Correlacion de Pearson entre cada zona y la humedad final."""
    corr = {}
    for z in config.ZONAS:
        sub = g[[z, "humedad"]].dropna()
        if len(sub) >= 3 and sub[z].std() > 0:
            corr[z] = float(sub[z].corr(sub["humedad"]))
        else:
            corr[z] = np.nan
    return corr


def _sensibilidad_zona(g: pd.DataFrame) -> dict:
    """C de cada zona por cada 1% de cambio en humedad (1/pendiente)."""
    sens = {}
    for z in config.ZONAS:
        sub = g[[z, "humedad"]].dropna()
        if len(sub) >= 4 and sub[z].std() > 0 and sub["humedad"].std() > 0:
            b = np.polyfit(sub[z], sub["humedad"], 1)[0]
            sens[z] = float(1.0 / b) if abs(b) > 1e-6 else np.nan
        else:
            sens[z] = np.nan
    return sens


def elegir_zona_clave(corr: dict) -> tuple[str, bool]:
    """Devuelve (zona_clave, fue_determinada_por_datos).
    Por defecto usa Zona 3 (conocimiento del proceso). Solo la sustituye si OTRA
    zona domina con claridad: |corr| >= MIN_CORR_CLAVE y supera a las demas por
    al menos MARGEN_CLAVE. Esto evita que la colinealidad (zonas que se mueven
    juntas) elija una zona casi al azar."""
    validas = {z: abs(c) for z, c in corr.items() if not pd.isna(c)}
    if not validas:
        return config.DEFAULT_ZONA_CLAVE, False
    mejor = max(validas, key=validas.get)
    mejor_val = validas[mejor]
    segundo_val = max([v for z, v in validas.items() if z != mejor], default=0.0)
    domina = (mejor_val >= config.MIN_CORR_CLAVE) and \
             (mejor_val - segundo_val >= config.MARGEN_CLAVE)
    if domina and mejor != config.DEFAULT_ZONA_CLAVE:
        return mejor, True
    if pd.isna(corr.get(config.DEFAULT_ZONA_CLAVE, np.nan)):
        return mejor, True
    return config.DEFAULT_ZONA_CLAVE, domina and mejor == config.DEFAULT_ZONA_CLAVE


def sensibilidad_robusta(zona: str, corr: dict, sens: dict) -> float | None:
    """C por cada 1% de humedad, SOLO si es confiable.
    Requiere correlacion fuerte y valor dentro de un rango fisicamente razonable."""
    c = corr.get(zona)
    s = sens.get(zona)
    if c is None or pd.isna(c) or abs(c) < config.MIN_CORR_CLAVE:
        return None
    if s is None or pd.isna(s):
        return None
    val = abs(s)
    if val < config.SENS_MIN_DEG_POR_PCT or val > config.SENS_MAX_DEG_POR_PCT:
        val = min(max(val, config.SENS_MIN_DEG_POR_PCT), config.SENS_MAX_DEG_POR_PCT)
    return val


def _construir_reglas(zona_clave: str, corr: dict, sens: dict) -> list[str]:
    """Traduce el analisis a instrucciones operativas: donde, cuando y cuanto.
    La DIRECCION se ancla en la fisica del secador (mas temperatura = menos
    humedad), no en la correlacion observada (que en muestras chicas puede
    salir invertida y dar instrucciones peligrosas)."""
    reglas = []
    zc = config.ZONA_NOMBRE[zona_clave]
    zc_sens = sensibilidad_robusta(zona_clave, corr, sens)

    orden = sorted(
        [(z, c) for z, c in corr.items() if not pd.isna(c)],
        key=lambda x: abs(x[1]), reverse=True
    )
    zona_sec = next((z for z, _ in orden if z != zona_clave), None)

    reglas.append(f"DONDE: ajustar primero {zc} (variable de mayor impacto).")

    if zc_sens is not None:
        paso_lo = max(config.SENS_MIN_DEG_POR_PCT, zc_sens * 0.5)
        paso_hi = zc_sens * 1.0
        reglas.append(
            f"CUANTO: ~{paso_lo:.0f}C en {zc} corrigen ~0.5% de humedad; "
            f"~{paso_hi:.0f}C corrigen ~1.0% (estimado de los datos)."
        )
        reglas.append(f"CUANDO sale ALTA (>10%): SUBIR {zc} ~{paso_lo:.0f} a {paso_hi:.0f}C.")
        reglas.append(f"CUANDO sale BAJA (<9%): BAJAR {zc} ~{paso_lo:.0f} a {paso_hi:.0f}C.")
    else:
        reglas.append(
            f"CUANTO: datos aun insuficientes para estimar grados exactos; "
            f"ajustar {zc} en pasos de 3-5C y volver a medir."
        )
        reglas.append(f"CUANDO sale ALTA (>10%): SUBIR {zc} 3-5C.")
        reglas.append(f"CUANDO sale BAJA (<9%): BAJAR {zc} 3-5C.")

    c_zc = corr.get(zona_clave)
    if c_zc is not None and not pd.isna(c_zc) and c_zc > 0.2:
        reglas.append(
            f"AVISO: en estos datos, mas temperatura coincidio con MAS humedad "
            f"(corr {c_zc:+.2f}); puede ser efecto de otra variable o calibracion. "
            f"Revisar; mantener la regla fisica de arriba."
        )

    if zona_sec:
        reglas.append(
            f"APOYO: si {zc} no corrige, mover {config.ZONA_NOMBRE[zona_sec]} en el mismo sentido."
        )
    reglas.append("REGLA DE ORO: cambiar UNA zona a la vez y medir antes del siguiente ajuste.")
    return reglas


# =================================================================================
#  API publica del modulo
# =================================================================================

def resumen_por_linea(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla general por linea."""
    filas = []
    for linea, g in df.groupby("linea"):
        filas.append({
            "Linea": linea,
            "Registros": len(g),
            "Humedad prom (%)": round(g["humedad"].mean(), 2),
            "Std humedad (%)": round(g["humedad"].std(), 2),
            "En rango H": int(g["en_rango_h"].sum()),
            "% en rango": round(100 * g["en_rango_h"].mean(), 1),
            "AW prom": round(g["aw"].mean(), 4),
            "Z1 prom": round(g["z1"].mean(), 1),
            "Z2 prom": round(g["z2"].mean(), 1),
            "Z3 prom": round(g["z3"].mean(), 1),
            "Z4 prom": round(g["z4"].mean(), 1),
            "Rate prom": round(g["rate_valido"].mean(), 0),
        })
    return pd.DataFrame(filas).sort_values("Linea").reset_index(drop=True)


def analizar_producto_linea(g: pd.DataFrame, producto: str, linea: str) -> ResultadoProducto:
    """Analisis completo para una combinacion producto x linea."""
    en_rango = g[g["en_rango_h"]]
    n_rango = len(en_rango)

    # Tabla de arranque: mediana de las corridas EN RANGO (o todo si no hay ninguna)
    base = en_rango if n_rango >= 1 else g
    arranque = {}
    for z in config.ZONAS:
        val = base[z].median()
        arranque[z] = None if pd.isna(val) else round(val)
    rate_med = base["rate_valido"].median()
    arranque["rate"] = None if pd.isna(rate_med) else int(round(rate_med, -1))
    agua_med = base["agua_termo"].median()
    arranque["agua_termo"] = None if pd.isna(agua_med) else round(agua_med)

    corr = _correlaciones_zona(g)
    sens = _sensibilidad_zona(g)
    zona_clave, _ = elegir_zona_clave(corr)
    sens_clave = sensibilidad_robusta(zona_clave, corr, sens)
    reglas = _construir_reglas(zona_clave, corr, sens)

    return ResultadoProducto(
        producto=producto,
        linea=linea,
        n_total=len(g),
        n_en_rango=n_rango,
        confiabilidad=config.etiqueta_confiabilidad(n_rango),
        humedad_prom=round(g["humedad"].mean(), 2),
        humedad_std=round(g["humedad"].std(), 2) if len(g) > 1 else float("nan"),
        aw_prom=round(g["aw"].mean(), 4),
        arranque=arranque,
        zona_clave=zona_clave,
        correlaciones=corr,
        sensibilidad=sens,
        sens_clave=sens_clave,
        reglas=reglas,
    )


def ajustes_ambientales(df: pd.DataFrame, linea: str) -> pd.DataFrame:
    """Calcula humedad promedio por condicion ambiental y recomienda el ajuste
    preventivo en la zona clave antes de arrancar. La direccion se ancla en la
    fisica (humedo->subir, seco->bajar). La magnitud va acotada."""
    g = df[df["linea"] == linea]
    corr_global = _correlaciones_zona(g)
    sens_global = _sensibilidad_zona(g)
    zona_clave, _ = elegir_zona_clave(corr_global)
    sens_zc = sensibilidad_robusta(zona_clave, corr_global, sens_global)
    zc_nombre = config.ZONA_NOMBRE[zona_clave]

    filas = []
    for cond in config.ORDEN_AMBIENTAL:
        sub = g[g["ambiente"] == cond]
        if len(sub) == 0:
            continue
        h_prom = sub["humedad"].mean()
        gap = h_prom - config.HUMEDAD_OBJ
        alerta = "CRITICO" if abs(gap) >= 0.6 else ("Monitorear" if abs(gap) >= 0.3 else "OK")

        if alerta == "OK":
            ajuste_txt = "Sin ajuste (usar base)"
        elif len(sub) < config.MIN_N_CONDICION:
            ajuste_txt = f"Datos insuficientes (n={len(sub)})"
        elif sens_zc is not None:
            delta = min(abs(gap) * sens_zc, config.AJUSTE_AMB_CAP)
            lo, hi = max(2, round(delta * 0.7)), max(3, round(delta))
            signo = "+" if gap > 0 else "-"
            ajuste_txt = f"{signo}{lo} a {signo}{hi}C en {zc_nombre}"
        else:
            signo_txt = "SUBIR" if gap > 0 else "BAJAR"
            ajuste_txt = f"{signo_txt} {zc_nombre} 3-5C (estimar con mas datos)"

        filas.append({
            "Condicion": cond,
            "n": len(sub),
            "Humedad prom (%)": round(h_prom, 2),
            "Ajuste recomendado": ajuste_txt,
            "Alerta": alerta,
        })
    return pd.DataFrame(filas)
