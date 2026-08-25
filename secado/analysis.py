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
    n_calidad_total: int    # cumple humedad Y aw a la vez
    base_criterio: str       # que subconjunto respaldo la tabla de arranque
    confiabilidad: str
    humedad_prom: float
    humedad_std: float
    aw_prom: float
    arranque: dict          # {z1..z4: int, rate: int, agua_termo: int, humedad, aw}
    rate_rango: tuple        # (p25, p75) del rate tipico observado
    rate_rango_n: int
    rate_rango_fuente: str
    agua_rango: tuple        # (p25, p75) del agua_termo tipico observado
    agua_rango_n: int
    agua_rango_fuente: str
    rate_zona_hint: dict | None  # zona sugerida en los extremos del rango de rate
    zona_clave: str         # "z3" por defecto
    correlaciones: dict     # {z1..z4: corr con humedad}
    sensibilidad: dict      # {z1..z4: C por 1% de humedad (con signo)}
    sens_clave: float | None  # sensibilidad robusta de la zona clave (None si insuficiente)
    modelo_rate_agua: dict | None  # regresion multivariante (None si no hay datos suficientes)
    correccion: dict | None  # ajuste de zona_clave si humedad/aw esperados quedan fuera de meta
    reglas: list[str]


# =================================================================================
#  Helpers privados (no se exportan)
# =================================================================================

def _correlaciones(g: pd.DataFrame, target_col: str) -> dict:
    """Correlacion de Pearson entre cada zona y una variable objetivo
    (humedad o aw). Generico: la correlacion no depende de la escala."""
    corr = {}
    for z in config.ZONAS:
        sub = g[[z, target_col]].dropna()
        if len(sub) >= 3 and sub[z].std() > 0:
            corr[z] = float(sub[z].corr(sub[target_col]))
        else:
            corr[z] = np.nan
    return corr


def _sensibilidad(g: pd.DataFrame, target_col: str, escala: float = 1.0) -> dict:
    """C de cada zona por cada 1 'punto' de cambio en el target (1/pendiente).
    escala permite reexpresar el target en unidades mas naturales antes de
    ajustar la recta: humedad ya esta en % (escala=1.0); AW se multiplica por
    100 (escala=100.0) para hablar de 'C por punto de AW' en vez de 'C por
    1.0 de AW' (que seria un salto absurdo, ya que el AW se mueve en centesimas)."""
    sens = {}
    for z in config.ZONAS:
        sub = g[[z, target_col]].dropna()
        if len(sub) >= 4 and sub[z].std() > 0 and sub[target_col].std() > 0:
            b = np.polyfit(sub[z], sub[target_col] * escala, 1)[0]
            sens[z] = float(1.0 / b) if abs(b) > 1e-6 else np.nan
        else:
            sens[z] = np.nan
    return sens


# Alias retrocompatibles (humedad es el caso mas usado en el modulo)
def _correlaciones_zona(g: pd.DataFrame) -> dict:
    return _correlaciones(g, "humedad")


def _sensibilidad_zona(g: pd.DataFrame) -> dict:
    return _sensibilidad(g, "humedad")


def _regresion_lineal(g: pd.DataFrame, predictores: list[str], target: str,
                       min_n: int, r2_min: float) -> dict | None:
    """OLS generico: target ~ predictores. Devuelve None (en vez de un numero
    inventado) si no hay grados de libertad suficientes, si la matriz esta mal
    condicionada (colinealidad fuerte / varianza nula) o si el ajuste explica
    muy poco (R2 bajo el umbral)."""
    cols = predictores + [target]
    sub = g[cols].dropna()
    n = len(sub)
    if n < min_n:
        return None
    X = sub[predictores].to_numpy(dtype=float)
    y = sub[target].to_numpy(dtype=float)
    if np.any(X.std(axis=0) < 1e-9):
        return None
    Xd = np.column_stack([np.ones(n), X])
    try:
        coef, _, rank, _ = np.linalg.lstsq(Xd, y, rcond=None)
    except np.linalg.LinAlgError:
        return None
    if rank < Xd.shape[1]:
        return None  # colinealidad perfecta / matriz singular
    pred = Xd @ coef
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    if r2 < r2_min:
        return None
    return {"n": n, "r2": round(r2, 3), "intercepto": float(coef[0]),
            "coefs": dict(zip(predictores, (float(c) for c in coef[1:])))}


def _modelo_rate_agua(g: pd.DataFrame, zona_clave: str) -> dict | None:
    """Regresion humedad ~ zona_clave + rate + agua_termo. Separa el efecto de
    cada variable controlando por las otras dos: el rate y el agua_termo se
    mueven junto con la zona (el operador compensa a mano), y eso puede sesgar
    una correlacion simple de una sola variable."""
    modelo = _regresion_lineal(
        g, [zona_clave, "rate_valido", "agua_termo"], "humedad",
        config.MIN_N_MULTIVARIANTE, config.R2_MIN_MULTIVARIANTE,
    )
    if modelo is None:
        return None
    b_zona = modelo["coefs"][zona_clave]
    b_rate = modelo["coefs"]["rate_valido"]
    b_agua = modelo["coefs"]["agua_termo"]
    if abs(b_zona) < 1e-6:
        return None
    # Fisica esperada: b_zona<0 (mas temp = menos humedad), b_rate>0 (mas
    # rate = mas humeda a igual temp, por el tiempo de residencia fijo).
    comp_rate = -(b_rate / b_zona) * config.RATE_PASO_COMPENSACION
    agua_efecto = b_agua * config.AGUA_PASO_COMPENSACION
    confiable = config.COMP_RATE_MIN_DEG <= abs(comp_rate) <= config.COMP_RATE_MAX_DEG
    return {
        "n": modelo["n"], "r2": modelo["r2"],
        "comp_rate_deg": comp_rate, "comp_rate_confiable": confiable,
        "agua_efecto_pct": agua_efecto,
        "signo_rate_ok": b_rate > 0,
        "signo_agua_ok": b_agua > 0,
    }


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


def sensibilidad_robusta(zona: str, corr: dict, sens: dict,
                          sens_min: float = None, sens_max: float = None) -> float | None:
    """C por cada 1 punto del target, SOLO si es confiable.
    Requiere correlacion fuerte y valor dentro de un rango fisicamente razonable.
    sens_min/sens_max por defecto son los de humedad; se pasan otros para AW."""
    sens_min = config.SENS_MIN_DEG_POR_PCT if sens_min is None else sens_min
    sens_max = config.SENS_MAX_DEG_POR_PCT if sens_max is None else sens_max
    c = corr.get(zona)
    s = sens.get(zona)
    if c is None or pd.isna(c) or abs(c) < config.MIN_CORR_CLAVE:
        return None
    if s is None or pd.isna(s):
        return None
    val = abs(s)
    if val < sens_min or val > sens_max:
        val = min(max(val, sens_min), sens_max)
    return val


def resolver_correccion_zona(hum_actual: float | None, aw_actual: float | None,
                              sens_hum: float | None, sens_aw: float | None) -> dict | None:
    """Calcula cuanto y en que sentido mover la MISMA zona clave para que
    humedad Y aw esperados queden dentro de meta (con un margen chico, no al
    filo del limite). Fisica: mas temperatura en la zona clave = menos
    humedad Y menos AW (misma direccion para las dos).

    Si humedad y AW piden sentidos opuestos -- tension real entre vender mas
    agua y mantener el AW controlado -- se prioriza AW (calidad/inocuidad)
    sobre humedad (negocio), y el conflicto se marca explicitamente para que
    el operador lo sepa; nunca se resuelve en silencio.

    Devuelve None si ninguna de las dos variables necesita correccion, o si
    ninguna tiene sensibilidad confiable con la que calcular un numero."""
    def _gap_humedad(h):
        if h is None:
            return None
        if h < config.HUMEDAD_MIN:
            return h - (config.HUMEDAD_MIN + config.MARGEN_HUMEDAD_CORRECCION)
        if h > config.HUMEDAD_MAX:
            return h - (config.HUMEDAD_MAX - config.MARGEN_HUMEDAD_CORRECCION)
        return 0.0

    def _gap_aw(v):
        if v is None:
            return None
        if v < config.AW_MIN_IDONEO:
            return v - (config.AW_MIN_IDONEO + config.MARGEN_AW_CORRECCION)
        if v > config.AW_MAX_IDONEO:
            return v - (config.AW_MAX_IDONEO - config.MARGEN_AW_CORRECCION)
        return 0.0

    gap_h = _gap_humedad(hum_actual)          # puntos de % (positivo = sobra humedad)
    gap_aw_pts = _gap_aw(aw_actual)
    if gap_aw_pts is not None:
        gap_aw_pts *= 100.0                    # a "puntos" (0.01 AW), misma escala que sens_aw

    necesita_h = gap_h is not None and gap_h != 0.0
    necesita_aw = gap_aw_pts is not None and gap_aw_pts != 0.0
    if not necesita_h and not necesita_aw:
        return None  # ya esta todo en meta, no hay nada que corregir

    delta_h = gap_h * sens_hum if (necesita_h and sens_hum is not None) else None
    delta_aw = gap_aw_pts * sens_aw if (necesita_aw and sens_aw is not None) else None

    if delta_h is None and delta_aw is None:
        return {
            "delta_c": None, "conflicto": False, "confiable": False,
            "motivo": "fuera de meta pero sin sensibilidad de zona confiable; "
                      "ajustar en pasos de 3-5C y volver a medir.",
        }

    conflicto = (delta_h is not None and delta_aw is not None and
                 delta_h * delta_aw < 0)
    if conflicto:
        delta_c = delta_aw          # AW manda: calidad/inocuidad sobre negocio
        criterio = "AW (se prioriza sobre humedad por conflicto de sentido)"
    elif delta_h is not None and delta_aw is not None:
        delta_c = delta_h if abs(delta_h) >= abs(delta_aw) else delta_aw
        criterio = "humedad y AW" if abs(delta_h) >= abs(delta_aw) else "AW (pedia mas ajuste)"
    else:
        delta_c = delta_h if delta_h is not None else delta_aw
        criterio = "humedad" if delta_h is not None else "AW"

    if abs(delta_c) > config.CORRECCION_ZONA_MAX_DEG:
        return {
            "delta_c": None, "conflicto": conflicto, "confiable": False,
            "motivo": f"el ajuste necesario supera {config.CORRECCION_ZONA_MAX_DEG:.0f}C "
                      f"en una sola zona -- el desvio es demasiado grande para extrapolar "
                      f"con confianza; revisar receta completa (zonas, rate, agua_termo) "
                      f"en vez de un solo ajuste puntual.",
        }

    hum_proy = (hum_actual - delta_c / sens_hum) if (hum_actual is not None and sens_hum) else hum_actual
    aw_proy = (aw_actual - (delta_c / sens_aw) / 100.0) if (aw_actual is not None and sens_aw) else aw_actual

    return {
        "delta_c": round(delta_c, 1),
        "direccion": "SUBIR" if delta_c > 0 else "BAJAR",
        "conflicto": conflicto,
        "confiable": True,
        "criterio": criterio,
        "humedad_proyectada": round(hum_proy, 2) if hum_proy is not None else None,
        "aw_proyectada": round(aw_proy, 4) if aw_proy is not None else None,
    }


def _construir_reglas(zona_clave: str, corr: dict, sens: dict, modelo: dict | None) -> list[str]:
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

    if modelo is not None:
        if modelo["comp_rate_confiable"] and modelo["signo_rate_ok"]:
            signo_c = "SUBIR" if modelo["comp_rate_deg"] > 0 else "BAJAR"
            reglas.append(
                f"RATE: por cada +{config.RATE_PASO_COMPENSACION} kg/h de rate, "
                f"{signo_c} {zc} ~{abs(modelo['comp_rate_deg']):.1f}C para mantener "
                f"la misma humedad (modelo controlado por agua_termo, "
                f"R2={modelo['r2']:.2f}, n={modelo['n']})."
            )
        elif not modelo["signo_rate_ok"]:
            reglas.append(
                "AVISO: en estos datos el rate no se comporta como se espera "
                "fisicamente (mas rate deberia dar mas humeda a igual temp); "
                "no se reporta compensacion de rate hasta revisar la causa."
            )
        if modelo["signo_agua_ok"]:
            reglas.append(
                f"AGUA TERMO: cada +{config.AGUA_PASO_COMPENSACION} kg/h en el "
                f"acondicionador sube ~{abs(modelo['agua_efecto_pct']):.2f}% la "
                f"humedad final (estimado controlando por {zc} y rate)."
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
    calidad = g[g["calidad_total"]]     # humedad Y aw dentro de meta a la vez
    n_calidad = len(calidad)

    # --- Base para la tabla de arranque -------------------------------------
    # Preferencia: corridas que cumplen humedad Y aw (calidad_total). Si no hay
    # ninguna, corridas que al menos cumplen humedad (en_rango_h, como antes).
    # Si tampoco hay, toda la muestra. Asi la receta que se sugiere es siempre
    # la mas exigente que el volumen de datos permita sostener.
    if n_calidad >= 1:
        base = calidad
        base_criterio = "humedad + AW"
    elif n_rango >= 1:
        base = en_rango
        base_criterio = "solo humedad (sin corridas con AW tambien en meta)"
    else:
        base = g
        base_criterio = "ninguna corrida en meta (se uso todo el historico)"

    # --- Sesgo hacia humedad alta dentro de la base -------------------------
    # Se vende agua, no materia prima: entre corridas que YA cumplen la meta,
    # se prefiere la mitad con humedad mas alta (mismo AW controlado, mas agua).
    # Se usan combinaciones reales de zonas/rate/agua que de verdad ocurrieron
    # juntas (no medianas independientes de columnas distintas), y solo se
    # aplica si queda suficiente muestra; si no, se usa la base completa.
    mediana_h_base = base["humedad"].median()
    base_alta = base[base["humedad"] >= mediana_h_base]
    if len(base_alta) >= config.MIN_N_SESGO_HUMEDAD_ALTA:
        base_arranque = base_alta
    else:
        base_arranque = base

    arranque = {}
    for z in config.ZONAS:
        val = base_arranque[z].median()
        arranque[z] = None if pd.isna(val) else round(val)
    rate_med = base_arranque["rate_valido"].median()
    arranque["rate"] = None if pd.isna(rate_med) else int(round(rate_med, -1))
    agua_med = base_arranque["agua_termo"].median()
    arranque["agua_termo"] = None if pd.isna(agua_med) else round(agua_med)
    hum_med = base_arranque["humedad"].median()
    arranque["humedad"] = None if pd.isna(hum_med) else round(hum_med, 2)
    aw_med = base_arranque["aw"].median()
    arranque["aw"] = None if pd.isna(aw_med) else round(aw_med, 4)

    # --- Rango tipico de rate y agua_termo, sobre la MISMA base que respalda la receta ---
    # Antes se calculaba sobre TODO el historico, incluidas corridas que fallaron
    # la meta -- eso podia mezclar un regimen de operacion completamente distinto
    # (ej. un rate mucho mas bajo de un dia con arranque atipico) con el rango
    # "normal", dando un ancho enganoso. Ahora usa la misma base que arma zonas/
    # humedad/aw (calidad -> en_rango_h -> todo), con un piso de muestra minima
    # para que el P25-P75 no sea solo 2-3 numeros inestables; si no alcanza, se
    # amplia a una base mayor y se marca la degradacion.
    def _rango_tipico(candidatos: list[tuple[pd.Series, str]], redondeo: int):
        for serie, etiqueta in candidatos:
            s = serie.dropna()
            if len(s) >= config.MIN_N_RANGO_CONFIABLE:
                return (int(round(s.quantile(.25), redondeo)),
                        int(round(s.quantile(.75), redondeo)), len(s), etiqueta)
        s = candidatos[-1][0].dropna()  # ultimo recurso: la base mas grande, igual
        if len(s) < 2:
            return (None, None, len(s), "insuficiente")
        return (int(round(s.quantile(.25), redondeo)),
                int(round(s.quantile(.75), redondeo)), len(s), "todo el historico (muestra chica)")

    candidatos_rate = [
        (base["rate_valido"], "corridas en meta"),
        (en_rango["rate_valido"], "corridas en rango de humedad"),
        (g["rate_valido"], "todo el historico"),
    ]
    candidatos_agua = [
        (base["agua_termo"], "corridas en meta"),
        (en_rango["agua_termo"], "corridas en rango de humedad"),
        (g["agua_termo"], "todo el historico"),
    ]
    rate_lo, rate_hi, rate_n, rate_fuente = _rango_tipico(candidatos_rate, -1)
    agua_lo, agua_hi, agua_n, agua_fuente = _rango_tipico(candidatos_agua, 0)
    rate_rango = (rate_lo, rate_hi)
    agua_rango = (agua_lo, agua_hi)

    corr = _correlaciones(g, "humedad")
    sens = _sensibilidad(g, "humedad")
    zona_clave, _ = elegir_zona_clave(corr)
    sens_clave = sensibilidad_robusta(zona_clave, corr, sens)
    modelo = _modelo_rate_agua(g, zona_clave)
    reglas = _construir_reglas(zona_clave, corr, sens, modelo)

    # --- Correccion automatica si el esperado (humedad y/o AW) sale de meta -----
    corr_aw = _correlaciones(g, "aw")
    sens_aw = _sensibilidad(g, "aw", escala=100.0)   # C por punto de AW (0.01)
    sens_clave_aw = sensibilidad_robusta(
        zona_clave, corr_aw, sens_aw,
        sens_min=config.AW_SENS_MIN_POR_PUNTO, sens_max=config.AW_SENS_MAX_POR_PUNTO,
    )
    correccion = resolver_correccion_zona(
        arranque.get("humedad"), arranque.get("aw"), sens_clave, sens_clave_aw,
    )
    if correccion is not None and correccion.get("delta_c") is not None:
        zona_actual = arranque.get(zona_clave)
        if zona_actual is not None:
            correccion["zona"] = zona_clave
            correccion["zona_nombre"] = config.ZONA_NOMBRE[zona_clave]
            correccion["valor_original"] = zona_actual
            correccion["valor_corregido"] = round(zona_actual + correccion["delta_c"])

    # --- Traducir el rango de rate a un rango de zona (mismo modelo de RATE:) ---
    # Si el rate va a variar dentro del rango tipico observado, mostrar un solo
    # valor de zona fijo puede quedar mal calibrado en los extremos. Se usa la
    # compensacion ya estimada (comp_rate_deg) para proyectar la zona en el
    # extremo bajo y alto del rango, anclada al rate/zona de la receta.
    rate_zona_hint = None
    if (modelo is not None and modelo["comp_rate_confiable"] and modelo["signo_rate_ok"]
            and rate_lo is not None and arranque.get(zona_clave) is not None
            and arranque.get("rate") is not None):
        rate_centro = arranque["rate"]
        zona_centro = arranque[zona_clave]
        deg_por_kgh = modelo["comp_rate_deg"] / config.RATE_PASO_COMPENSACION
        delta_lo = (rate_lo - rate_centro) * deg_por_kgh
        delta_hi = (rate_hi - rate_centro) * deg_por_kgh
        if abs(delta_lo) <= config.CORRECCION_ZONA_MAX_DEG and abs(delta_hi) <= config.CORRECCION_ZONA_MAX_DEG:
            rate_zona_hint = {
                "rate_lo": rate_lo, "rate_hi": rate_hi,
                "zona_lo": round(zona_centro + delta_lo),
                "zona_hi": round(zona_centro + delta_hi),
                "rate_centro": rate_centro, "zona_centro": zona_centro,
            }

    n_para_confiabilidad = len(base_arranque)

    return ResultadoProducto(
        producto=producto,
        linea=linea,
        n_total=len(g),
        n_en_rango=n_rango,
        n_calidad_total=n_calidad,
        base_criterio=base_criterio,
        confiabilidad=config.etiqueta_confiabilidad(n_para_confiabilidad),
        humedad_prom=round(g["humedad"].mean(), 2),
        humedad_std=round(g["humedad"].std(), 2) if len(g) > 1 else float("nan"),
        aw_prom=round(g["aw"].mean(), 4),
        arranque=arranque,
        rate_rango=rate_rango,
        rate_rango_n=rate_n,
        rate_rango_fuente=rate_fuente,
        agua_rango=agua_rango,
        agua_rango_n=agua_n,
        agua_rango_fuente=agua_fuente,
        rate_zona_hint=rate_zona_hint,
        zona_clave=zona_clave,
        correlaciones=corr,
        sensibilidad=sens,
        sens_clave=sens_clave,
        modelo_rate_agua=modelo,
        correccion=correccion,
        reglas=reglas,
    )


def ajustes_ambientales(df: pd.DataFrame, linea: str) -> dict:
    """Calcula humedad y AW promedio por condicion ambiental y recomienda el
    ajuste preventivo en la zona clave antes de arrancar. La direccion se
    ancla en la fisica (humedo->subir zona, seco->bajar); la magnitud usa la
    misma logica de correccion que la tabla de arranque (prioriza AW sobre
    humedad si piden sentidos opuestos). Devuelve tambien, si hay datos
    suficientes, una sensibilidad continua a temp_amb/hr (mas precisa que
    comparar baldes) a modo de nota complementaria."""
    g = df[df["linea"] == linea]
    corr_h = _correlaciones(g, "humedad")
    sens_h = _sensibilidad(g, "humedad")
    corr_aw = _correlaciones(g, "aw")
    sens_aw = _sensibilidad(g, "aw", escala=100.0)
    zona_clave, _ = elegir_zona_clave(corr_h)
    sens_zc_h = sensibilidad_robusta(zona_clave, corr_h, sens_h)
    sens_zc_aw = sensibilidad_robusta(
        zona_clave, corr_aw, sens_aw,
        sens_min=config.AW_SENS_MIN_POR_PUNTO, sens_max=config.AW_SENS_MAX_POR_PUNTO,
    )
    zc_nombre = config.ZONA_NOMBRE[zona_clave]

    filas = []
    for cond in config.ORDEN_AMBIENTAL:
        sub = g[g["ambiente"] == cond]
        if len(sub) == 0:
            continue
        h_prom = sub["humedad"].mean()
        aw_prom = sub["aw"].mean()
        gap_h = h_prom - config.HUMEDAD_OBJ
        aw_centro = (config.AW_MIN_IDONEO + config.AW_MAX_IDONEO) / 2
        gap_aw = aw_prom - aw_centro
        alerta_h = "CRITICO" if abs(gap_h) >= 0.6 else ("Monitorear" if abs(gap_h) >= 0.3 else "OK")
        alerta_aw = ("CRITICO" if abs(gap_aw) >= 0.02
                     else ("Monitorear" if abs(gap_aw) >= 0.01 else "OK"))

        if len(sub) < config.MIN_N_CONDICION:
            ajuste_txt = f"Datos insuficientes (n={len(sub)})"
        else:
            correccion = resolver_correccion_zona(h_prom, aw_prom, sens_zc_h, sens_zc_aw)
            if correccion is None:
                # Dentro de la meta estricta (9.0-10.0 / 0.52-0.58): no hay nada
                # que corregir. Si aun asi la alerta esta encendida es porque el
                # promedio esta cerca del limite (banda de vigilancia), no fuera.
                ajuste_txt = ("Sin ajuste (usar base)" if (alerta_h == "OK" and alerta_aw == "OK")
                              else "Dentro de meta, pero cerca del límite — vigilar en piso")
            elif correccion.get("delta_c") is not None:
                delta = correccion["delta_c"]
                signo = "SUBIR" if delta > 0 else "BAJAR"
                nota_conf = " [conflicto humedad/AW, se priorizo AW]" if correccion["conflicto"] else ""
                ajuste_txt = f"{signo} {zc_nombre} ~{abs(delta):.1f}C{nota_conf}"
            else:
                ajuste_txt = correccion.get("motivo", f"Ajustar {zc_nombre} 3-5C (estimar con mas datos)")

        filas.append({
            "Condicion": cond,
            "n": len(sub),
            "Humedad prom (%)": round(h_prom, 2),
            "AW prom": round(aw_prom, 4),
            "Ajuste recomendado": ajuste_txt,
            "Alerta Humedad": alerta_h,
            "Alerta AW": alerta_aw,
        })
    tabla = pd.DataFrame(filas)

    # --- Sensibilidad continua (complementa la tabla de baldes) -----------------
    modelo_h = _regresion_lineal(g, ["temp_amb", "hr"], "humedad",
                                  config.MIN_N_AMBIENTAL, config.R2_MIN_AMBIENTAL)
    modelo_aw = _regresion_lineal(g, ["temp_amb", "hr"], "aw",
                                   config.MIN_N_AMBIENTAL, config.R2_MIN_AMBIENTAL)
    return {"tabla": tabla, "modelo_humedad": modelo_h, "modelo_aw": modelo_aw,
            "zona_clave": zona_clave, "zona_nombre": zc_nombre}