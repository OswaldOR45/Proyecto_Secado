# 🔥 Análisis del Proceso de Secado — 19 Hermanos Pet Food

Herramienta de análisis de datos que convierte la bitácora del secador de croqueta en una **guía de arranque y ajuste para el operador**. Cada vez que se ejecuta, lee los datos más recientes, los limpia, corre estadística de proceso y genera una guía lista para imprimir y pegar en la línea.

No es un dashboard: es un **motor de decisión operativa** que responde tres preguntas para cada producto y línea — *¿con qué temperaturas arranco?*, *¿qué zona muevo si la humedad se sale de rango y cuántos grados?*, y *¿qué ajusto antes de arrancar según el clima de hoy?*

![Status](https://img.shields.io/badge/status-en%20uso-success)
![Python](https://img.shields.io/badge/Python-3-3776AB)
![Pandas](https://img.shields.io/badge/Pandas-data-150458)
![NumPy](https://img.shields.io/badge/NumPy-stats-013243)
![Output](https://img.shields.io/badge/salida-HTML%20%C2%B7%20MD%20%C2%B7%20CSV-FF9800)

---

## 📌 El problema

La calidad de la croqueta depende de mantener la **humedad final entre 9% y 10%** (y el *water activity* en rango). Lograrlo dependía de la experiencia de cada operador con las temperaturas de las 4 zonas del secador, sin una referencia común ni un criterio claro de cuánto ajustar ante un fuera de rango o un cambio de clima.

Este proyecto destila el histórico de corridas en una guía objetiva: una **tabla de arranque** por producto/línea, **reglas de ajuste** (dónde, cuándo y cuánto), y **ajustes preventivos según la condición ambiental** — todo etiquetado por nivel de confiabilidad estadística.

---

## ✨ Características principales

- **Pipeline reproducible**: una sola ejecución lee la fuente, limpia, analiza y publica los reportes; pensado para re-correrse conforme crecen los datos.
- **Tabla de arranque** por producto y línea: temperaturas de Z1–Z4, rate y agua termo, calculadas con la **mediana de las corridas en rango** (robusta a outliers).
- **Análisis estadístico de proceso**:
  - Correlación de Pearson entre cada zona y la humedad final.
  - **Sensibilidad** (°C por cada 1% de humedad) vía ajuste lineal.
  - **Selección de zona clave** con guarda anti-colinealidad: usa Zona 3 por conocimiento del proceso y solo la sustituye si otra zona domina con claridad.
- **Reglas operativas ancladas en física**: la *dirección* del ajuste (más temperatura → menos humedad) se fija por física, no por la correlación observada — que en muestras chicas puede invertirse y dar instrucciones peligrosas. La *magnitud* se acota a un rango realista.
- **Ajustes preventivos por condición ambiental** (día frío / normal / caluroso-húmedo / caluroso-seco) con nivel de alerta.
- **Etiqueta de confiabilidad** por número de corridas en rango (lista para Cpk a partir de 30), para que la guía diga qué tan defendible es cada recomendación.
- **Ingesta robusta**: acepta CSV, XLSX o una URL de Google Sheets publicado; mapeo de columnas por posición (inmune a acentos/mayúsculas), decimales con punto o coma, y detección de errores de captura (p. ej. rate imposible).
- **Salida multiformato**: HTML editorial-industrial (apto para impresión), Markdown para terminal/documentación y CSVs para Excel/BI.

---

## 🧱 Stack tecnológico

| Componente | Tecnología |
|-----------|-----------|
| Lenguaje | Python 3 |
| Datos y estadística | pandas, numpy (correlación, `polyfit`, mediana) |
| Lectura de Excel | openpyxl |
| Reporte HTML | plantilla propia (Fraunces + IBM Plex desde Google Fonts) |
| Fuente de datos | CSV / XLSX / Google Sheets publicado como CSV |

---

## 🏗️ Arquitectura

Paquete modular donde **cada módulo tiene una sola responsabilidad** y la lógica de análisis está separada de la presentación: las funciones de `analysis.py` **devuelven datos, nunca imprimen ni exportan**; los módulos `*_report` solo presentan.

```
secado/                  # paquete
├── __init__.py          # API pública (uso programático)
├── __main__.py          # CLI:  python -m secado [fuente]
├── config.py            # rangos, umbrales, mapeo de columnas, reglas ambientales
├── data.py              # carga + limpieza (aísla el formato del CSV)
├── analysis.py          # estadística, correlaciones, sensibilidad, reglas
├── text_report.py       # salida en texto plano / Markdown
├── html_report.py       # salida HTML (editorial-industrial, imprimible)
└── csv_export.py        # exportación a CSV
secado_analisis.py       # wrapper retrocompatible (= python -m secado)
```

**Dónde tocar para cada cambio:**
- Cambiar el rango de humedad o una condición ambiental → `config.py`.
- Cambiar el formato del CSV de entrada → `data.py`.
- Cambiar cómo se elige la zona clave o se construyen las reglas → `analysis.py`.
- Rediseñar el reporte → `html_report.py` (sin tocar la lógica).

**Flujo:** `cargar_datos` → `limpiar` (devuelve datos + avisos de calidad) → `analizar_producto_linea` / `ajustes_ambientales` → generadores de reporte (texto, HTML, CSV).

---

## 🗃️ Datos de entrada

La bitácora trae, por columna y posición: fecha/hora, producto, peso, línea, temperaturas de zonas 1–4, agua termo, Z2 extruder, rate, humedad final, AW, HR ambiental, temperatura ambiental, y quién registra/supervisa. Metas de calidad: humedad 9–10% (objetivo 9.5%) y AW idóneo 0.52–0.58.

---

## 🚀 Uso

```bash
pip install pandas numpy openpyxl

# Lo más común: usa la URL del Google Sheet publicado (definida en config.py)
python -m secado

# O pasando una fuente específica:
python -m secado bitacora.csv
python -m secado bitacora.xlsx
python -m secado "https://docs.google.com/.../pub?output=csv"
```

Genera en el directorio de trabajo: `guia_operador.html` (reporte visual para imprimir), `guia_operador.md` (versión texto) y `salida/*.csv` (tabla de arranque, ajustes ambientales y resumen).

### Uso como librería
```python
from secado import cargar_datos, limpiar, generar_html

df_raw = cargar_datos("bitacora.csv")
df, avisos = limpiar(df_raw)
html = generar_html(df, avisos)
```

---

## 📐 Criterio de validación

La guía se considera estadísticamente defendible con **30 corridas en rango** por producto y línea (suficiente para calcular Cpk); en ese punto el script marca el producto como confiabilidad `MUY ALTA`. Por debajo de eso, la guía es orientativa y el reporte lo indica explícitamente.

---

## 🛣️ Roadmap / mejoras

- [ ] **Unificar el paquete**: mover los módulos a `secado/` (hoy el código vive en la raíz y la carpeta `secado/` quedó con archivos vacíos — ver nota).
- [ ] Agregar `requirements.txt` y empaquetado (`pyproject.toml`) para instalación con `pip`.
- [ ] Cálculo y reporte automático de **Cpk** al alcanzar el umbral de corridas.
- [ ] Pruebas automatizadas de `data.limpiar` y de las reglas de `analysis`.
- [ ] Integrar la temperatura/HR ambiental en vivo para sugerir el arranque del día.

---

## 🧹 Nota de estructura y seguridad

- **Estructura**: el código fuente con contenido está en la raíz, pero usa imports relativos (`from . import config`) y el README describe el paquete `secado/`. Para que `python -m secado` funcione tal cual, los módulos deben vivir dentro de `secado/` (hoy esos archivos están vacíos). Es un arreglo de mover archivos, no de lógica.
- **Repo**: conviene agregar un `.gitignore` (para `.idea/`, `__pycache__/`, `salida/` y los reportes generados) y quitar `.idea/` del control de versiones.
- **Datos**: `config.py` incluye una URL de Google Sheet publicado; si la fuente no debe ser pública, parametrízala por variable de entorno o archivo de configuración local.

---

## 👤 Autor

**Oswaldo Reynoso Robles** — Departamento de Mejora Continua. Diseño del pipeline, la estadística de proceso y los reportes para convertir la bitácora del secador en una guía operativa basada en datos.