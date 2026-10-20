# -*- coding: utf-8 -*-
"""Reporte en texto plano para consola / markdown."""
from __future__ import annotations

import datetime as dt
import pandas as pd

from . import config
from .analysis import (
    resumen_por_linea, analizar_producto_linea, ajustes_ambientales,
    sensibilidad_conjunta_global,
)


def _fmt_arranque(a: dict, rate_rango: tuple, agua_rango: tuple,
                   rate_n: int = None, rate_fuente: str = None,
                   agua_n: int = None, agua_fuente: str = None) -> str:
    z = lambda k: ("--" if a.get(k) is None else f"{a[k]}")
    r_lo, r_hi = rate_rango
    a_lo, a_hi = agua_rango
    rate_txt = "--" if r_lo is None else f"{r_lo:,}-{r_hi:,} kg/h (n={rate_n}, {rate_fuente})"
    agua_txt = "--" if a_lo is None else f"{a_lo}-{a_hi} (n={agua_n}, {agua_fuente})"
    hum_txt = "--" if a.get("humedad") is None else f"{a['humedad']}%"
    aw_txt = "--" if a.get("aw") is None else f"{a['aw']}"
    return (f"Z1={z('z1')}  Z2={z('z2')}  Z3={z('z3')}  Z4={z('z4')}  "
            f"|  Rate={rate_txt}  |  Agua Termo={agua_txt}  "
            f"|  Humedad esperada={hum_txt}  AW esperado={aw_txt}")


def generar_guia(df: pd.DataFrame, avisos: list[str],
                  quemador_df: pd.DataFrame = None, calidad_df: pd.DataFrame = None) -> str:
    """Devuelve la guia completa como string. No imprime ni escribe archivos."""
    L = []
    add = L.append
    hoy = dt.date.today().isoformat()
    sens_global = sensibilidad_conjunta_global(df)

    add("=" * 78)
    add("  19 HERMANOS PET FOOD  -  GUIA DE ARRANQUE Y AJUSTE DEL SECADOR")
    add(f"  Generada automaticamente el {hoy}  |  Mejora Continua")
    add("=" * 78)
    add("")
    add(f"Registros analizados: {len(df)}")
    add(f"OBJETIVO: la mayor humedad posible con AW seguro.")
    add(f"  Humedad: {config.texto_meta_humedad()}")
    add(f"  AW:      {config.texto_meta_aw()}   (AW esperado de la receta <= {config.AW_OBJETIVO_ESPERADO})")
    if avisos:
        add("")
        add("AVISOS DE CALIDAD DE DATOS:")
        for a in avisos:
            add(f"  - {a}")
    add("")
    add("-" * 78)
    add(" RESUMEN GENERAL POR LINEA")
    add("-" * 78)
    add(resumen_por_linea(df).to_string(index=False))
    add("")
    add("-" * 78)
    add(" GUIA POR PRODUCTO Y LINEA")
    add("-" * 78)

    for (producto, linea), g in df.groupby(["producto", "linea"]):
        r = analizar_producto_linea(g, producto, linea, quemador_df, calidad_df, sens_global=sens_global)
        add("")
        add(f"### {producto}  |  {linea}")
        add(f"    Meta humedad: {config.texto_meta_humedad(producto)}")
        add(f"    Corridas: {r.n_total}   En rango (humedad): {r.n_en_rango}   "
            f"En meta (humedad+AW): {r.n_calidad_total}   Confiabilidad: {r.confiabilidad}")
        add(f"    Humedad prom: {r.humedad_prom}%   (std {r.humedad_std})   "
            f"AW prom: {r.aw_prom}")
        add(f"    Receta calculada con: {r.base_criterio}")
        if r.n_calidad_total >= 1 or r.n_en_rango >= 1:
            add(f"    ARRANQUE -> {_fmt_arranque(r.arranque, r.rate_rango, r.agua_rango, r.rate_rango_n, r.rate_rango_fuente, r.agua_rango_n, r.agua_rango_fuente)}")
        else:
            add(f"    ARRANQUE -> (orientativo, sin corridas en meta) "
                f"{_fmt_arranque(r.arranque, r.rate_rango, r.agua_rango, r.rate_rango_n, r.rate_rango_fuente, r.agua_rango_n, r.agua_rango_fuente)}")
        if r.rate_zona_hint is not None:
            h = r.rate_zona_hint
            add(f"    NOTA: si corres cerca de {h['rate_lo']:,} kg/h, mover {config.ZONAS_AJUSTE_TXT} "
                f"{h['delta_lo']:+.1f}C cada una; cerca de {h['rate_hi']:,} kg/h, {h['delta_hi']:+.1f}C "
                f"(proyectado con el modelo de rate).")
        corr_txt = "  ".join(
            f"{config.ZONA_NOMBRE[z].split()[1]}:"
            f"{('n/d' if pd.isna(v) else f'{v:+.2f}')}"
            for z, v in r.correlaciones.items()
        )
        add(f"    Correlacion zona-humedad (informativa):  {corr_txt}")
        add(f"    Ajuste conjunto {config.ZONAS_AJUSTE_TXT}: ~{r.sens_conjunta:.1f}C por 1% de humedad "
            f"(sensibilidad {r.sens_fuente}); +1% humedad = +{r.aw_por_pct:.3f} AW")
        if r.n_calidad_grande >= config.MIN_N_RANGO_CONFIABLE:
            add(f"    Referencia Calidad (n={r.n_calidad_grande}): "
                f"Humedad prom {r.humedad_prom_calidad}%   AW prom {r.aw_prom_calidad}")
        for regla in r.reglas:
            add(f"      - {regla}")

    add("")
    add("-" * 78)
    add(" AJUSTES PREVENTIVOS SEGUN CONDICION AMBIENTAL (antes de arrancar)")
    add("-" * 78)
    for linea in sorted(df["linea"].unique()):
        amb = ajustes_ambientales(df, linea, sens_global=sens_global)
        tabla = amb["tabla"]
        add("")
        add(f"### {linea}")
        if len(tabla) == 0:
            add("    (sin datos ambientales suficientes)")
        else:
            add(tabla.to_string(index=False))
        mh, maw = amb["modelo_humedad"], amb["modelo_aw"]
        if mh is not None:
            add(f"    Sensibilidad continua humedad: por +1C ambiente "
                f"{mh['coefs']['temp_amb']:+.3f}%   por +10% HR "
                f"{mh['coefs']['hr']*10:+.3f}%   (R2={mh['r2']}, n={mh['n']})")
        if maw is not None:
            add(f"    Sensibilidad continua AW: por +1C ambiente "
                f"{maw['coefs']['temp_amb']*100:+.3f} pts   por +10% HR "
                f"{maw['coefs']['hr']*1000:+.3f} pts   (R2={maw['r2']}, n={maw['n']})")
    add("")
    add("=" * 78)
    add(f" RECORDATORIO: mover {config.ZONAS_AJUSTE_TXT} JUNTAS en pasos chicos (maximo "
        f"{config.AJUSTE_MAX_POR_ZONA}C por zona),")
    add(" medir humedad y AW antes del siguiente paso. El AW manda: 0.61 o mas es reproceso.")
    add("=" * 78)
    return "\n".join(L)
