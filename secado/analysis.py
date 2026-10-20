# -*- coding: utf-8 -*-
"""Estadistica descriptiva, sensibilidad conjunta de zonas, ajuste de receta y
generacion de reglas operativas. Ninguna funcion aqui imprime o exporta:
todas devuelven datos. La presentacion vive en los modulos *_report.

OBJETIVO: la mayor humedad posible sin que el AW pase de 0.5999 (gato: humedad
lo mas cerca de 8.5% sin pasarse). El secador es aire caliente circulando, asi
que se ajustan varias zonas (Z1-Z3) a la vez con pocos grados cada una."""
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
    rate_rango: tuple
    rate_rango_n: int
    rate_rango_fuente: str
    agua_rango: tuple
    agua_rango_n: int
    agua_rango_fuente: str
    rate_zona_hint: dict | None   # cuanto mover Z1-Z3 si el rate esta en los extremos del rango
    zonas_ajuste: list            # zonas que se mueven juntas (Z1-Z3)
    sens_conjunta: float          # C (promedio Z1-Z3) por 1% de humedad
    sens_fuente: str              # de donde salio esa sensibilidad
    aw_por_pct: float             # AW que sube por cada 1% de humedad ganada
    correlaciones: dict           # {z1..z4: corr con humedad} (solo informativa)
    humedad_prom_calidad: float | None
    aw_prom_calidad: float | None
    n_calidad_grande: int
    modelo_rate_agua: dict | None
    reglas: list[str]


# =================================================================================
#  Helpers privados
# =================================================================================

def _correlaciones(g: pd.DataFrame, target_col: str) -> dict:
    """Correlacion de Pearson entre cada zona y una variable objetivo."""
    corr = {}
    for z in config.ZONAS:
        sub = g[[z, target_col]].dropna()
        if len(sub) >= 3 and sub[z].std() > 0:
            corr[z] = float(sub[z].corr(sub[target_col]))
        else:
            corr[z] = np.nan
    return corr


def _regresion_lineal(g: pd.DataFrame, predictores: list[str], target: str,
                       min_n: int, r2_min: float) -> dict | None:
    """OLS generico: target ~ predictores. Devuelve None (en vez de un numero
    inventado) si no hay grados de libertad suficientes, si la matriz esta mal
    condicionada o si el ajuste explica muy poco (R2 bajo el umbral)."""
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
        return None
    pred = Xd @ coef
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    if r2 < r2_min:
        return None
    return {"n": n, "r2": round(r2, 3), "intercepto": float(coef[0]),
            "coefs": dict(zip(predictores, (float(c) for c in coef[1:])))}


def _ols_con_t(X: np.ndarray, y: np.ndarray):
    """OLS con estadistico t por coeficiente. X ya incluye la constante.
    Devuelve (coef, t) o None si no se puede estimar."""
    n, k = X.shape
    if n <= k + 1:
        return None
    try:
        coef, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
        if rank < k:
            return None
        res = y - X @ coef
        s2 = float(res @ res) / (n - k)
        cov = s2 * np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return None
    se = np.sqrt(np.diag(cov))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = coef / se
    return coef, t


# =================================================================================
#  Sensibilidad CONJUNTA de Z1-Z3 (todas se mueven a la vez)
# =================================================================================

def _pares_consecutivos(g: pd.DataFrame) -> pd.DataFrame | None:
    """Cambios entre corridas consecutivas del mismo producto x linea, separadas
    por menos de PAR_MAX_HORAS. Solo pares donde el promedio Z1-Z3 si cambio."""
    if "fecha" not in g.columns or g["fecha"].notna().sum() < 3:
        return None
    x = g.dropna(subset=["fecha"]).sort_values("fecha")
    cols = ["z123", "humedad", "aw", "agua_termo"]
    d = x[cols].diff()
    horas = x["fecha"].diff().dt.total_seconds() / 3600.0
    d = d[(horas > 0) & (horas <= config.PAR_MAX_HORAS)].dropna()
    d = d[d["z123"].abs() > 0]
    return d


def _sens_desde_pares(p: pd.DataFrame | None) -> dict | None:
    """Humedad y AW vs cambio de Z1-Z3 (controlando por cambio de agua_termo)."""
    if p is None or len(p) < 8:
        return None
    X = np.column_stack([np.ones(len(p)), p["z123"].to_numpy(float), p["agua_termo"].to_numpy(float)])
    rh = _ols_con_t(X, p["humedad"].to_numpy(float))
    ra = _ols_con_t(X, p["aw"].to_numpy(float))
    if rh is None:
        return None
    b_h, t_h = rh[0][1], rh[1][1]
    if b_h >= 0:        # fisica: mas temperatura = menos humedad
        return None
    S = -1.0 / b_h
    k = None
    if ra is not None and ra[0][1] < 0:
        k = ra[0][1] / b_h            # AW por 1% de humedad
    return {"deg_por_pct": float(S), "aw_por_pct": k, "n": int(len(p)), "t": float(t_h)}


def sensibilidad_conjunta_global(df: pd.DataFrame) -> dict | None:
    """Estimacion con TODOS los productos x lineas juntos (mas pares = mas estable).
    Devuelve None si no hay datos/fechas suficientes (se usan valores por defecto)."""
    if "fecha" not in df.columns or "z123" not in df.columns:
        return None
    partes = []
    for _, g in df.groupby(["producto", "linea"]):
        p = _pares_consecutivos(g)
        if p is not None and len(p):
            partes.append(p)
    if not partes:
        return None
    res = _sens_desde_pares(pd.concat(partes, ignore_index=True))
    if res is None or res["n"] < config.MIN_PARES_SENS_GLOBAL:
        return None
    if not (config.SENS_CONJ_MIN_DEG_POR_PCT <= res["deg_por_pct"] <= config.SENS_CONJ_MAX_DEG_POR_PCT):
        return None
    return res


def _elegir_sensibilidad(g: pd.DataFrame, sens_global: dict | None) -> tuple[float, float, str]:
    """(C por 1% humedad, AW por 1% humedad, fuente). Prefiere la estimacion propia
    del producto x linea solo si es solida; si no, la global; si no, el default."""
    propia = _sens_desde_pares(_pares_consecutivos(g))
    # AW por % de humedad: global si existe (mas estable), si no la propia, si no default
    k = None
    for cand in (sens_global, propia):
        if cand and cand.get("aw_por_pct") and config.AW_POR_PCT_MIN <= cand["aw_por_pct"] <= config.AW_POR_PCT_MAX:
            k = cand["aw_por_pct"]
            break
    if k is None:
        k = config.AW_POR_PCT_DEFAULT

    lo, hi = config.SENS_CONJ_MIN_DEG_POR_PCT, config.SENS_CONJ_MAX_DEG_POR_PCT
    if (propia and propia["n"] >= config.MIN_PARES_SENS_PROPIA
            and propia["t"] <= -config.T_MIN_SENS_PROPIA and lo <= propia["deg_por_pct"] <= hi):
        return propia["deg_por_pct"], k, f"propia de este producto/línea ({propia['n']} pares de corridas)"
    if sens_global:
        return sens_global["deg_por_pct"], k, f"global de todos los productos ({sens_global['n']} pares de corridas)"
    return config.SENS_CONJ_DEFAULT_DEG_POR_PCT, k, "valor por defecto (sin datos suficientes para estimarla)"


# =================================================================================
#  Ajuste de receta: maxima humedad con AW seguro
# =================================================================================

def proponer_ajuste(hum: float | None, aw: float | None, lim: dict,
                    sens: float, aw_por_pct: float) -> dict | None:
    """Decide cuantos grados mover Z1-Z3 (todas igual) para llevar la receta a
    la MAYOR humedad que permite el AW objetivo.

    humedad objetivo = min( humedad a la que el AW llegaria a AW_OBJETIVO,
                            tope de humedad del producto - margen (solo gato) )
    Si ese objetivo queda por debajo de la humedad minima, el AW manda (se marca
    conflicto). Devuelve None si el ajuste es menor a AJUSTE_MIN_DEG."""
    if hum is None or aw is None or sens is None or aw_por_pct is None:
        return None
    h_aw = hum + (config.AW_OBJETIVO_ESPERADO - aw) / aw_por_pct
    tope_gato = lim["h_max"] - config.MARGEN_HUMEDAD_CORRECCION if np.isfinite(lim["h_max"]) else np.inf
    h_obj = min(h_aw, tope_gato)
    conflicto = h_obj < lim["h_min"]
    delta_total = -(h_obj - hum) * sens            # negativo = BAJAR temperatura
    if abs(delta_total) < config.AJUSTE_MIN_DEG:
        return None

    cap = config.AJUSTE_MAX_POR_ZONA
    limitado = abs(delta_total) > cap
    aplicado = int(round(max(-cap, min(cap, delta_total))))
    if aplicado == 0:
        return None

    hum_proy = hum - aplicado / sens
    aw_proy = aw + aw_por_pct * (hum_proy - hum)

    if aw > config.AW_OBJETIVO_ESPERADO and h_obj == h_aw:
        criterio = (f"AW esperado ({aw:.3f}) arriba del objetivo ({config.AW_OBJETIVO_ESPERADO}); "
                    f"bajar AW tiene prioridad sobre la humedad")
    elif h_obj == tope_gato and tope_gato < h_aw:
        criterio = f"humedad lo más cerca de {lim['h_max']:.1f}% sin pasarse (gato)"
    else:
        criterio = (f"hay margen de AW ({aw:.3f} vs objetivo {config.AW_OBJETIVO_ESPERADO}): "
                    f"se puede ganar humedad")
    if conflicto:
        criterio = (f"con AW seguro no se alcanza la humedad mínima de {lim['h_min']:.1f}%; "
                    f"se prioriza AW")

    return {
        "delta_c": aplicado,
        "direccion": "SUBIR" if aplicado > 0 else "BAJAR",
        "delta_total_c": round(delta_total, 1),
        "limitado_por_tope": limitado,
        "conflicto": conflicto,
        "confiable": True,
        "criterio": criterio,
        "humedad_objetivo": round(float(h_obj), 2),
        "humedad_proyectada": round(float(hum_proy), 2),
        "aw_proyectada": round(float(aw_proy), 4),
    }


def _modelo_rate_agua(g: pd.DataFrame) -> dict | None:
    """Regresion humedad ~ promedio Z1-Z3 + rate + agua_termo. Separa el efecto de
    cada variable controlando por las otras dos."""
    modelo = _regresion_lineal(
        g, ["z123", "rate_valido", "agua_termo"], "humedad",
        config.MIN_N_MULTIVARIANTE, config.R2_MIN_MULTIVARIANTE,
    )
    if modelo is None:
        return None
    b_zona = modelo["coefs"]["z123"]
    b_rate = modelo["coefs"]["rate_valido"]
    b_agua = modelo["coefs"]["agua_termo"]
    if abs(b_zona) < 1e-6:
        return None
    comp_rate = -(b_rate / b_zona) * config.RATE_PASO_COMPENSACION
    agua_efecto = b_agua * config.AGUA_PASO_COMPENSACION
    confiable = config.COMP_RATE_MIN_DEG <= abs(comp_rate) <= config.COMP_RATE_MAX_DEG
    return {
        "n": modelo["n"], "r2": modelo["r2"],
        "b_zona": b_zona,
        "comp_rate_deg": comp_rate, "comp_rate_confiable": confiable,
        "agua_efecto_pct": agua_efecto,
        "signo_rate_ok": b_rate > 0,
        "signo_agua_ok": b_agua > 0,
    }


def _construir_reglas(sens: float, aw_por_pct: float, sens_fuente: str,
                      modelo: dict | None, lim: dict, es_gato: bool) -> list[str]:
    """Traduce el analisis a instrucciones operativas. La DIRECCION se ancla en
    la fisica (mas temperatura = menos humedad y menos AW)."""
    reglas = []
    zt = config.ZONAS_AJUSTE_TXT
    cap = config.AJUSTE_MAX_POR_ZONA
    por_medio = sens / 2.0                      # C por zona para mover ~0.5% de humedad
    paso_hi = int(min(cap, round(por_medio)))
    paso_lo = int(max(2, min(paso_hi, round(sens * 0.3))))
    aw_medio = aw_por_pct / 2.0                 # AW que sube al ganar 0.5% de humedad

    if es_gato:
        reglas.append(f"OBJETIVO: humedad lo más cerca posible de {lim['h_max']:.1f}% sin pasarse "
                      f"(rango {lim['h_min']:.1f}–{lim['h_max']:.1f}%) y AW < {config.AW_MAX_IDONEO}.")
    else:
        reglas.append(f"OBJETIVO: la mayor humedad posible (mínimo {lim['h_min']:.1f}%, sin tope) "
                      f"con AW < {config.AW_MAX_IDONEO}; AW esperado de la receta ≤ {config.AW_OBJETIVO_ESPERADO}. "
                      f"AW ≥ {config.AW_DESVIACION} es desviación.")

    reglas.append(f"DONDE: mover {zt} JUNTAS, el mismo cambio en las tres. "
                  f"Zona 4 solo en casos raros, si {zt} ya llegaron al tope y no alcanza.")
    reglas.append(
        f"CUANTO: ~{por_medio:.0f}°C en cada zona ≈ 0.5% de humedad (y ≈ {aw_medio:.3f} de AW); "
        f"~{sens:.0f}°C ≈ 1.0%. Máximo {cap}°C por zona en un ajuste. "
        f"Sensibilidad: {sens_fuente}."
    )
    if es_gato:
        reglas.append(f"CUANDO sale ALTA (>{lim['h_max']:.1f}%): SUBIR {zt} ~{paso_lo} a {paso_hi}°C cada una.")
        reglas.append(f"CUANDO sale BAJA (<{lim['h_min']:.1f}%): BAJAR {zt} ~{paso_lo} a {paso_hi}°C cada una, "
                      f"solo si el AW lo permite.")
    else:
        reglas.append(f"CUANDO sale BAJA (<{lim['h_min']:.1f}%): BAJAR {zt} ~{paso_lo} a {paso_hi}°C cada una, "
                      f"solo si el AW está bajo {config.AW_OBJETIVO_ESPERADO}.")
        reglas.append(f"SI HAY MARGEN: con humedad ya sobre el mínimo y AW ≤ {config.AW_OBJETIVO_ESPERADO - 0.02:.2f}, "
                      f"BAJAR {zt} ~{paso_lo} a {paso_hi}°C cada una gana humedad "
                      f"(AW sube ~{aw_medio:.3f} por cada 0.5%).")
    reglas.append(f"SI AW SUBE: con AW ≥ {config.AW_ALERTA_MONITOREAR} SUBIR {zt} ~{paso_lo} a {paso_hi}°C cada una "
                  f"aunque la humedad baje. El AW manda: ≥ {config.AW_DESVIACION} es reproceso.")

    if modelo is not None:
        if modelo["comp_rate_confiable"] and modelo["signo_rate_ok"]:
            signo_c = "SUBIR" if modelo["comp_rate_deg"] > 0 else "BAJAR"
            reglas.append(
                f"RATE: por cada +{config.RATE_PASO_COMPENSACION} kg/h de rate, "
                f"{signo_c} {zt} ~{abs(modelo['comp_rate_deg']):.1f}°C para mantener "
                f"la misma humedad (R2={modelo['r2']:.2f}, n={modelo['n']})."
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
                f"humedad final (estimado controlando por {zt} y rate)."
            )

    reglas.append(f"REGLA DE ORO: mover {zt} juntas en pasos chicos, medir humedad y AW "
                  f"antes del siguiente paso, y ante duda guiarse por el AW.")
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
            "En meta (H+AW)": int(g["calidad_total"].sum()),
            "% en meta": round(100 * g["calidad_total"].mean(), 1),
            "AW prom": round(g["aw"].mean(), 4),
            "Z1 prom": round(g["z1"].mean(), 1),
            "Z2 prom": round(g["z2"].mean(), 1),
            "Z3 prom": round(g["z3"].mean(), 1),
            "Z4 prom": round(g["z4"].mean(), 1),
            "Rate prom": round(g["rate_valido"].mean(), 0),
        })
    return pd.DataFrame(filas).sort_values("Linea").reset_index(drop=True)


def analizar_producto_linea(g: pd.DataFrame, producto: str, linea: str,
                             quemador_df: pd.DataFrame = None,
                             calidad_df: pd.DataFrame = None,
                             sens_global: dict | None = None) -> ResultadoProducto:
    """Analisis completo para una combinacion producto x linea.
    quemador_df se ignora (se conserva solo por compatibilidad con los llamadores).
    sens_global: resultado de sensibilidad_conjunta_global(df); si es None se
    intenta estimar con las corridas de este mismo grupo."""
    en_rango = g[g["en_rango_h"]]
    n_rango = len(en_rango)
    calidad = g[g["calidad_total"]]     # humedad Y aw dentro de meta a la vez
    n_calidad = len(calidad)
    lim = config.limites(producto)
    es_gato = producto in config.PRODUCTOS_GATO

    # --- Base para la tabla de arranque -------------------------------------
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
    # Se vende agua, no materia prima: entre corridas que YA cumplen la meta se
    # prefiere la mitad con humedad mas alta. Para gato la humedad ideal es la
    # mas cercana a 8.5, asi que ahi tambien se prefiere la mitad alta.
    mediana_h_base = base["humedad"].median()
    base_alta = base[base["humedad"] >= mediana_h_base]
    base_arranque = base_alta if len(base_alta) >= config.MIN_N_SESGO_HUMEDAD_ALTA else base

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

    # --- Rango tipico de rate y agua_termo (P25-P75) ------------------------
    def _rango_tipico(candidatos: list[tuple[pd.Series, str]], redondeo: int):
        for serie, etiqueta in candidatos:
            s = serie.dropna()
            if len(s) >= config.MIN_N_RANGO_CONFIABLE:
                return (int(round(s.quantile(.25), redondeo)),
                        int(round(s.quantile(.75), redondeo)), len(s), etiqueta)
        s = candidatos[-1][0].dropna()
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

    corr = _correlaciones(g, "humedad")

    # --- Sensibilidad conjunta y ajuste de receta ---------------------------
    if sens_global is None:
        sens_global = sensibilidad_conjunta_global(g)
    sens, aw_por_pct, sens_fuente = _elegir_sensibilidad(g, sens_global)

    modelo = _modelo_rate_agua(g)
    reglas = _construir_reglas(sens, aw_por_pct, sens_fuente, modelo, lim, es_gato)

    # --- Rate: cuanto mover Z1-Z3 si el rate esta en los extremos del rango ---
    rate_zona_hint = None
    if (modelo is not None and modelo["comp_rate_confiable"] and modelo["signo_rate_ok"]
            and rate_lo is not None and arranque.get("rate") is not None):
        rate_centro = arranque["rate"]
        deg_por_kgh = modelo["comp_rate_deg"] / config.RATE_PASO_COMPENSACION
        delta_lo = (rate_lo - rate_centro) * deg_por_kgh
        delta_hi = (rate_hi - rate_centro) * deg_por_kgh
        if abs(delta_lo) <= config.AJUSTE_MAX_POR_ZONA and abs(delta_hi) <= config.AJUSTE_MAX_POR_ZONA:
            rate_zona_hint = {
                "rate_lo": rate_lo, "rate_hi": rate_hi, "rate_centro": rate_centro,
                "delta_lo": round(delta_lo, 1), "delta_hi": round(delta_hi, 1),
            }

    # --- Referencia opcional de la base grande de Calidad -------------------
    humedad_prom_calidad = aw_prom_calidad = None
    n_calidad_grande = 0
    if calidad_df is not None:
        cs = calidad_df[(calidad_df["producto"] == producto) & (calidad_df["linea"] == linea)]
        n_calidad_grande = len(cs)
        if n_calidad_grande >= config.MIN_N_RANGO_CONFIABLE:
            humedad_prom_calidad = round(cs["humedad"].mean(), 2) if cs["humedad"].notna().any() else None
            aw_prom_calidad = round(cs["aw"].mean(), 4) if cs["aw"].notna().any() else None

    return ResultadoProducto(
        producto=producto,
        linea=linea,
        n_total=len(g),
        n_en_rango=n_rango,
        n_calidad_total=n_calidad,
        base_criterio=base_criterio,
        confiabilidad=config.etiqueta_confiabilidad(len(base_arranque)),
        humedad_prom=round(g["humedad"].mean(), 2),
        humedad_std=round(g["humedad"].std(), 2) if len(g) > 1 else float("nan"),
        aw_prom=round(g["aw"].mean(), 4),
        arranque=arranque,
        rate_rango=(rate_lo, rate_hi),
        rate_rango_n=rate_n,
        rate_rango_fuente=rate_fuente,
        agua_rango=(agua_lo, agua_hi),
        agua_rango_n=agua_n,
        agua_rango_fuente=agua_fuente,
        rate_zona_hint=rate_zona_hint,
        zonas_ajuste=list(config.ZONAS_AJUSTE),
        sens_conjunta=round(sens, 1),
        sens_fuente=sens_fuente,
        aw_por_pct=round(aw_por_pct, 4),
        correlaciones=corr,
        humedad_prom_calidad=humedad_prom_calidad,
        aw_prom_calidad=aw_prom_calidad,
        n_calidad_grande=n_calidad_grande,
        modelo_rate_agua=modelo,
        reglas=reglas,
    )


def _alerta_humedad(h: float) -> str:
    """Humedad (perro): solo preocupa quedar BAJO el minimo; arriba no hay tope."""
    if h < config.HUMEDAD_MIN - 0.5:
        return "CRITICO"
    if h < config.HUMEDAD_MIN:
        return "Monitorear"
    return "OK"


def _alerta_aw(v: float) -> str:
    if v >= config.AW_MAX_IDONEO:
        return "CRITICO"
    if v >= config.AW_ALERTA_MONITOREAR:
        return "Monitorear"
    return "OK"


def ajustes_ambientales(df: pd.DataFrame, linea: str, sens_global: dict | None = None) -> dict:
    """Humedad y AW promedio por condicion ambiental y el ajuste preventivo de
    Z1-Z3 (mismo criterio que la tabla de arranque: maxima humedad con AW seguro).
    Usa solo producto de perro (SilverCat tiene otra meta y casi no tiene corridas).
    Devuelve tambien, si hay datos suficientes, una sensibilidad continua a
    temp_amb/hr a modo de nota complementaria."""
    g = df[(df["linea"] == linea) & (~df["producto"].isin(config.PRODUCTOS_GATO))]
    if sens_global is None:
        sens_global = sensibilidad_conjunta_global(df)
    sens, aw_por_pct, _ = _elegir_sensibilidad(g, sens_global)
    lim = config.limites("")
    zt = config.ZONAS_AJUSTE_TXT

    filas = []
    for cond in config.ORDEN_AMBIENTAL:
        sub = g[g["ambiente"] == cond]
        if len(sub) == 0:
            continue
        h_prom = sub["humedad"].mean()
        aw_prom = sub["aw"].mean()
        alerta_h = _alerta_humedad(h_prom)
        alerta_aw = _alerta_aw(aw_prom)

        if len(sub) < config.MIN_N_CONDICION:
            ajuste_txt = f"Datos insuficientes (n={len(sub)})"
        else:
            aj = proponer_ajuste(h_prom, aw_prom, lim, sens, aw_por_pct)
            if aj is None:
                ajuste_txt = "Sin ajuste (usar base)"
            else:
                nota = " (por etapas; medir y repetir)" if aj["limitado_por_tope"] else ""
                ajuste_txt = f"{aj['direccion']} {zt} ~{abs(aj['delta_c'])}°C cada una{nota}"

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

    modelo_h = _regresion_lineal(g, ["temp_amb", "hr"], "humedad",
                                  config.MIN_N_AMBIENTAL, config.R2_MIN_AMBIENTAL)
    modelo_aw = _regresion_lineal(g, ["temp_amb", "hr"], "aw",
                                   config.MIN_N_AMBIENTAL, config.R2_MIN_AMBIENTAL)
    return {"tabla": tabla, "modelo_humedad": modelo_h, "modelo_aw": modelo_aw,
            "zona_nombre": zt}
