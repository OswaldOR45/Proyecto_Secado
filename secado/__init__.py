# -*- coding: utf-8 -*-
"""Paquete `secado` -- Analisis del proceso de secado de croqueta.
19 Hermanos Pet Food · Departamento de Mejora Continua.

Uso programatico:
    from secado import cargar_datos, limpiar, generar_guia, generar_html

Uso por linea de comandos:
    python -m secado bitacora.csv
    python -m secado https://docs.google.com/.../pub?output=csv
"""
from .data import cargar_datos, limpiar
from .analysis import (
    ResultadoProducto,
    resumen_por_linea,
    analizar_producto_linea,
    ajustes_ambientales,
)
from .text_report import generar_guia
from .html_report import generar_html
from .csv_export import exportar_tablas

__version__ = "3.0.0"
__all__ = [
    "cargar_datos", "limpiar",
    "ResultadoProducto",
    "resumen_por_linea", "analizar_producto_linea", "ajustes_ambientales",
    "generar_guia", "generar_html", "exportar_tablas",
]
