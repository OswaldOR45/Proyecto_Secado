# -*- coding: utf-8 -*-
"""Entry point del CLI. Se invoca con:  python -m secado [fuente]"""
from __future__ import annotations
import sys

from . import config
from .data import cargar_datos, limpiar
from .text_report import generar_guia
from .html_report import generar_html
from .csv_export import exportar_tablas


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    fuente = argv[0] if argv else config.FUENTE_DATOS
    print(f"[info] Leyendo datos de: {fuente}")

    try:
        df_raw = cargar_datos(fuente)
    except Exception as e:
        print(f"[ERROR] No se pudo leer la fuente de datos: {e}")
        print("        Revisa la ruta/URL o publica la hoja como CSV.")
        return 1

    df, avisos = limpiar(df_raw)
    if len(df) == 0:
        print("[ERROR] No quedaron registros validos despues de la limpieza.")
        return 1

    # 1) Consola en texto plano
    guia_txt = generar_guia(df, avisos)
    print("\n" + guia_txt + "\n")

    # 2) Archivos: HTML (principal), Markdown (referencia), CSVs
    with open("guia_operador.html", "w", encoding="utf-8") as f:
        f.write(generar_html(df, avisos))
    with open("guia_operador.md", "w", encoding="utf-8") as f:
        f.write("```\n" + guia_txt + "\n```\n")
    rutas_csv = exportar_tablas(df)

    print(f"[ok] HTML  -> guia_operador.html")
    print(f"[ok] Texto -> guia_operador.md")
    for r in rutas_csv:
        print(f"[ok] CSV   -> {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())