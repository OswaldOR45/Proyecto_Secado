# -*- coding: utf-8 -*-
"""Reporte en texto plano para consola / markdown."""
from __future__ import annotations

import datetime as dt
import pandas as pd

from . import config
from .analysis import (
    resumen_por_linea, analizar_producto_linea, ajustes_ambientales,
)


def _fmt_arranque(a: dict) -> str:
    z = lambda k: ("--" if a.get(k) is None else f"{a[k]}")
    rate = "--" if a.get("rate") is None else f"{a['rate']:,}"
    agua = "--" if a.get("agua_termo") is None else f"{a['agua_termo']}"
    return (f"Z1={z('z1')}  Z2={z('z2')}  Z3={z('z3')}  Z4={z('z4')}  "
            f"|  Rate={rate} kg/h  |  Agua Termo={agua}")


def generar_guia(df: pd.DataFrame, avisos: list[str]) -> str:
    """Devuelve la guia completa como string. No imprime ni escribe archivos."""
    L = []
    add = L.append
    hoy = dt.date.today().isoformat()

    add("=" * 78)
    add("  19 HERMANOS PET FOOD  -  GUIA DE ARRANQUE Y AJUSTE DEL SECADOR")
    add(f"  Generada automaticamente el {hoy}  |  Mejora Continua")
    add("=" * 78)
    add("")
    add(f"Registros analizados: {len(df)}   "
        f"|  Meta humedad: {config.HUMEDAD_MIN:.0f}-{config.HUMEDAD_MAX:.0f}%   "
        f"|  AW idoneo: {config.AW_MIN_IDONEO}-{config.AW_MAX_IDONEO}")
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
        r = analizar_producto_linea(g, producto, linea)
        add("")
        add(f"### {producto}  |  {linea}")
        add(f"    Corridas: {r.n_total}   En rango: {r.n_en_rango}   "
            f"Confiabilidad: {r.confiabilidad}")
        add(f"    Humedad prom: {r.humedad_prom}%   (std {r.humedad_std})   "
            f"AW prom: {r.aw_prom}")
        if r.n_en_rango >= 1:
            add(f"    ARRANQUE -> {_fmt_arranque(r.arranque)}")
        else:
            add(f"    ARRANQUE -> (orientativo, sin corridas en rango) "
                f"{_fmt_arranque(r.arranque)}")
        corr_txt = "  ".join(
            f"{config.ZONA_NOMBRE[z].split()[1]}:"
            f"{('n/d' if pd.isna(c) else f'{c:+.2f}')}"
            for z, c in r.correlaciones.items()
        )
        add(f"    Correlacion zona-humedad:  {corr_txt}")
        add(f"    ZONA CLAVE: {config.ZONA_NOMBRE[r.zona_clave]}")
        for regla in r.reglas:
            add(f"      - {regla}")

    add("")
    add("-" * 78)
    add(" AJUSTES PREVENTIVOS SEGUN CONDICION AMBIENTAL (antes de arrancar)")
    add("-" * 78)
    for linea in sorted(df["linea"].unique()):
        amb = ajustes_ambientales(df, linea)
        add("")
        add(f"### {linea}")
        if len(amb) == 0:
            add("    (sin datos ambientales suficientes)")
        else:
            add(amb.to_string(index=False))
    add("")
    add("=" * 78)
    add(" RECORDATORIO: ajustar SIEMPRE la zona clave primero, una zona a la vez,")
    add(" y medir humedad antes del siguiente cambio.")
    add("=" * 78)
    return "\n".join(L)
