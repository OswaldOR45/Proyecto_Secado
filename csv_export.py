# -*- coding: utf-8 -*-
"""Exporta las tablas principales a CSV para consumo externo (Excel, BI, etc.)."""
from __future__ import annotations

import os
import pandas as pd

from . import config
from .analysis import (
    resumen_por_linea, analizar_producto_linea, ajustes_ambientales,
)


def exportar_tablas(df: pd.DataFrame, carpeta: str = "salida") -> list[str]:
    os.makedirs(carpeta, exist_ok=True)
    rutas = []

    res = resumen_por_linea(df)
    p = os.path.join(carpeta, "resumen_por_linea.csv")
    res.to_csv(p, index=False, encoding="utf-8-sig")
    rutas.append(p)

    filas = []
    for (producto, linea), g in df.groupby(["producto", "linea"]):
        r = analizar_producto_linea(g, producto, linea)
        a = r.arranque
        filas.append({
            "Producto": producto, "Linea": linea,
            "Z1": a["z1"], "Z2": a["z2"], "Z3": a["z3"], "Z4": a["z4"],
            "Rate(kg/h)": a["rate"], "AguaTermo": a["agua_termo"],
            "Corridas": r.n_total, "EnRango": r.n_en_rango,
            "ZonaClave": config.ZONA_NOMBRE[r.zona_clave],
            "Confiabilidad": r.confiabilidad,
        })
    arranque_df = pd.DataFrame(filas).sort_values(["Producto", "Linea"])
    p = os.path.join(carpeta, "tabla_arranque.csv")
    arranque_df.to_csv(p, index=False, encoding="utf-8-sig")
    rutas.append(p)

    amb_all = []
    for linea in sorted(df["linea"].unique()):
        amb = ajustes_ambientales(df, linea)
        if len(amb) > 0:
            amb.insert(0, "Linea", linea)
            amb_all.append(amb)
    if amb_all:
        amb_df = pd.concat(amb_all, ignore_index=True)
        p = os.path.join(carpeta, "ajustes_ambientales.csv")
        amb_df.to_csv(p, index=False, encoding="utf-8-sig")
        rutas.append(p)

    return rutas
