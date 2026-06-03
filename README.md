Análisis del Proceso de Secado · 19 Hermanos Pet Food
Genera una guía de arranque y ajuste para el secador, a partir de la bitácora
digital del proceso. Cada vez que se corre, lee los datos más recientes y produce:
`guia_operador.html` — reporte visual (lo que se imprime y pega en la línea).
`guia_operador.md` — versión texto para terminal/documentación.
`salida/*.csv` — tablas reutilizables (arranque, ajustes ambientales, resumen).
Estructura del proyecto
```
proyecto/
├── secado/                  # paquete
│   ├── __init__.py         # API pública
│   ├── __main__.py         # CLI entry: `python -m secado`
│   ├── config.py           # constantes (rangos, umbrales, columnas)
│   ├── data.py             # carga + limpieza
│   ├── analysis.py         # estadística, correlaciones, reglas
│   ├── text_report.py      # salida en texto plano
│   ├── html_report.py      # salida HTML (editorial-industrial)
│   └── csv_export.py       # exportación a CSV
├── secado_analisis.py      # wrapper retrocompatible
└── README.md
```
Cada módulo tiene una responsabilidad clara:
Cambiar el rango de humedad o agregar una nueva condición ambiental → `config.py`.
Cambiar el formato del CSV de entrada → `data.py`.
Cambiar cómo se eligen las zonas clave o se construyen las reglas → `analysis.py`.
Rediseñar el HTML → `html_report.py` (sin tocar la lógica).
Cómo correrlo
```bash
# Lo más común: con la URL del Google Sheet publicado (definida en config.py)
python -m secado

# O pasando un archivo o URL específica:
python -m secado bitacora.csv
python -m secado bitacora.xlsx
python -m secado "https://docs.google.com/.../pub?output=csv"
```
Equivalente para retrocompatibilidad:
```bash
python secado_analisis.py [fuente]
```
Cómo usarlo desde otro script
```python
from secado import cargar_datos, limpiar, generar_html

df_raw = cargar_datos("bitacora.csv")
df, avisos = limpiar(df_raw)
html = generar_html(df, avisos)
```
Dependencias
```bash
pip install pandas numpy openpyxl
```
(Las tipografías Fraunces e IBM Plex se cargan automáticamente desde Google Fonts.)
Criterio para considerar la guía "validada"
Recomendado: 30 corridas EN RANGO por producto y línea (alcanza para calcular Cpk).
Con eso, el script te marca el producto como `MUY ALTA` confiabilidad y la guía es
estadísticamente defendible. Hasta entonces, sigue siendo orientativa.