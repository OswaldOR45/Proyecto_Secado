# -*- coding: utf-8 -*-
"""Carga y limpieza de la bitacora. Aisla todo el conocimiento sobre el formato
del CSV (decimales con coma, errores de captura, etc.) en un solo lugar."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def cargar_datos(fuente: str) -> pd.DataFrame:
    """Lee CSV/XLSX/URL y devuelve un DataFrame con columnas mapeadas por posicion.
    El mapeo por posicion (no por nombre) lo hace robusto a acentos y mayusculas
    en los encabezados de la hoja."""
    if fuente.lower().endswith((".xlsx", ".xlsm", ".xls")):
        raw = pd.read_excel(fuente, header=0)
    else:
        raw = pd.read_csv(fuente, header=0)

    n_cols = raw.shape[1]
    datos = {}
    for nombre, pos in config.COLUMNAS.items():
        if pos < n_cols:
            datos[nombre] = raw.iloc[:, pos]
        else:
            datos[nombre] = pd.Series([np.nan] * len(raw))
    return pd.DataFrame(datos)


def limpiar(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Convierte tipos, normaliza texto y marca/filtra datos sospechosos.
    Devuelve (df_limpio, lista_de_avisos)."""
    avisos: list[str] = []
    df = df.copy()

    # Numericos: acepta decimales con punto (1.5) o con coma (1,5).
    # Aplicamos el reemplazo de coma a CUALQUIER columna que no sea ya numerica
    # (cubre 'object' en pandas <3 y el nuevo 'str' de pandas >=3).
    num_cols = ["peso", "z1", "z2", "z3", "z4", "agua_termo",
                "z2_extruder", "rate", "humedad", "aw", "hr", "temp_amb"]
    for c in num_cols:
        s = df[c]
        if not pd.api.types.is_numeric_dtype(s):
            s = s.astype(str).str.strip().str.replace(",", ".", regex=False)
            s = s.replace({"": np.nan, "nan": np.nan, "None": np.nan})
        df[c] = pd.to_numeric(s, errors="coerce")

    # Texto normalizado
    df["producto"] = df["producto"].astype(str).str.strip()
    df["linea"] = df["linea"].astype(str).str.strip().str.upper()
    df["linea"] = df["linea"].str.replace(r"(?i)l[ií]nea\s*", "L", regex=True)
    df["linea"] = df["linea"].str.replace(r"^\s*1\s*$", "L1", regex=True)
    df["linea"] = df["linea"].str.replace(r"^\s*2\s*$", "L2", regex=True)

    # Filas sin humedad: no sirven para nada del analisis
    antes = len(df)
    df = df[df["humedad"].notna()].copy()
    if len(df) < antes:
        avisos.append(f"Se ignoraron {antes - len(df)} fila(s) sin lectura de humedad.")

    # Rates sospechosos: aislamos sin borrar la fila (las demas variables sirven)
    sospechosos = df["rate"].notna() & (df["rate"] < config.RATE_MINIMO_VALIDO)
    if sospechosos.any():
        ejemplos = df.loc[sospechosos, ["producto", "linea", "rate"]].head(5).to_dict("records")
        avisos.append(
            f"{int(sospechosos.sum())} registro(s) con RATE < {config.RATE_MINIMO_VALIDO} "
            f"kg/h (posible error de captura). Se excluyen del calculo de rate. "
            f"Ej.: {ejemplos}"
        )
    df["rate_valido"] = df["rate"].where(~sospechosos, np.nan)

    # Banderas de calidad
    df["en_rango_h"] = df["humedad"].between(config.HUMEDAD_MIN, config.HUMEDAD_MAX)
    df["estado_h"] = np.where(
        df["humedad"] < config.HUMEDAD_MIN, "BAJA (<9%)",
        np.where(df["humedad"] > config.HUMEDAD_MAX, "ALTA (>10%)", "EN RANGO")
    )
    df["aw_idoneo"] = df["aw"].between(config.AW_MIN_IDONEO, config.AW_MAX_IDONEO)
    df["calidad_total"] = df["en_rango_h"] & df["aw_idoneo"]

    # Condicion ambiental
    df["ambiente"] = df.apply(
        lambda r: config.clasificar_ambiente(r["temp_amb"], r["hr"]), axis=1
    )

    return df, avisos
