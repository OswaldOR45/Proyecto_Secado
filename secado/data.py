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

    # Filas duplicadas exactas (misma captura repetida)
    antes = len(df)
    df = df.drop_duplicates().copy()
    if len(df) < antes:
        avisos.append(f"Se eliminaron {antes - len(df)} fila(s) duplicada(s) exacta(s).")

    # Numericos: acepta decimales con punto (1.5) o con coma (1,5).
    num_cols = ["peso", "z1", "z2", "z3", "z4", "agua_termo",
                "z2_extruder", "rate", "humedad", "aw", "hr", "temp_amb"]
    for c in num_cols:
        s = df[c]
        if not pd.api.types.is_numeric_dtype(s):
            s = s.astype(str).str.strip().str.replace(",", ".", regex=False)
            s = s.replace({"": np.nan, "nan": np.nan, "None": np.nan})
        df[c] = pd.to_numeric(s, errors="coerce")

    # Fecha (dia/mes/anio). Si no se puede leer queda NaT y simplemente no se
    # usa para estimar la sensibilidad entre corridas consecutivas.
    df["fecha"] = pd.to_datetime(df["fecha_hora"], dayfirst=True, errors="coerce")

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

    # Zonas fuera de rango fisico (apagada/en 0/typo): la corrida no representa
    # una receta normal de 4 zonas y contaminaria las recetas de arranque.
    zmin, zmax = config.ZONA_MIN_VALIDA, config.ZONA_MAX_VALIDA
    zonas = df[config.ZONAS]
    fuera = ((zonas < zmin) | (zonas > zmax) | zonas.isna()).any(axis=1)
    if fuera.any():
        solo_z4 = (
            (df.loc[fuera, "z4"] < zmin)
            & df.loc[fuera, ["z1", "z2", "z3"]].apply(lambda c: (c >= zmin) & (c <= zmax)).all(axis=1)
        )
        n_z4 = int(solo_z4.sum())
        avisos.append(
            f"Se excluyeron {int(fuera.sum())} corrida(s) con alguna zona fuera de "
            f"{zmin}-{zmax}°C: {n_z4} con Zona 4 apagada/baja (operación con 3 zonas) y "
            f"{int(fuera.sum()) - n_z4} con zonas en 0 o capturas imposibles. "
            f"No entran a las recetas."
        )
        df = df[~fuera].copy()

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

    # Promedio de las zonas que se mueven juntas en un ajuste
    df["z123"] = df[config.ZONAS_AJUSTE].mean(axis=1)

    # Banderas de calidad (limites por producto: perro / gato)
    lim = df["producto"].map(config.limites)
    h_min = lim.map(lambda d: d["h_min"]); h_max = lim.map(lambda d: d["h_max"])
    aw_min = lim.map(lambda d: d["aw_min"]); aw_max = lim.map(lambda d: d["aw_max"])
    df["en_rango_h"] = (df["humedad"] >= h_min) & (df["humedad"] <= h_max)
    df["estado_h"] = np.where(
        df["humedad"] < h_min, "BAJA",
        np.where(df["humedad"] > h_max, "ALTA", "EN RANGO")
    )
    df["aw_idoneo"] = (df["aw"] >= aw_min) & (df["aw"] <= aw_max)
    df["calidad_total"] = df["en_rango_h"] & df["aw_idoneo"]

    # Condicion ambiental
    df["ambiente"] = df.apply(
        lambda r: config.clasificar_ambiente(r["temp_amb"], r["hr"]), axis=1
    )

    return df, avisos
