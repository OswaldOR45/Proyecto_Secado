# -*- coding: utf-8 -*-
"""Reporte en texto plano para consola / markdown."""
from __future__ import annotations

import datetime as dt
import pandas as pd

from . import config
from .analysis import (
    resumen_por_linea, analizar_producto_linea, ajustes_ambientales,
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
            add(f"    NOTA: el rate puede moverse bastante dentro de la corrida; si corres "
                f"cerca de {h['rate_lo']:,} kg/h, {config.ZONA_NOMBRE[r.zona_clave]} ~{h['zona_lo']}C; "
                f"si corres cerca de {h['rate_hi']:,} kg/h, ~{h['zona_hi']}C (proyectado con el modelo de rate).")
        if r.correccion is not None:
            c = r.correccion
            if c.get("delta_c") is not None:
                conflicto_txt = "  [conflicto humedad/AW -> se priorizo AW]" if c["conflicto"] else ""
                add(f"    ** RECETA AJUSTADA (esperado fuera de meta, PROYECCION no validada) **")
                add(f"       {c['direccion']} {c['zona_nombre']} de {c['valor_original']} a "
                    f"{c['valor_corregido']} (delta {c['delta_c']:+.1f}C), criterio: {c['criterio']}"
                    f"{conflicto_txt}")
                add(f"       Con este ajuste se proyecta: Humedad ~{c['humedad_proyectada']}%   "
                    f"AW ~{c['aw_proyectada']}")
            else:
                add(f"    ** AVISO: {c['motivo']} **")
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
    add(" RECORDATORIO: ajustar SIEMPRE la zona clave primero, una zona a la vez,")
    add(" y medir humedad antes del siguiente cambio.")
    add("=" * 78)
    return "\n".join(L)