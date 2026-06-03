# -*- coding: utf-8 -*-
"""Reporte HTML con estetica editorial-industrial.
Pensado para verse bien en pantalla, en tablet y al imprimirse en papel."""
from __future__ import annotations

import datetime as dt
import html
import math
import pandas as pd

from . import config
from .analysis import (
    resumen_por_linea, analizar_producto_linea, ajustes_ambientales,
)

# =================================================================================
#  CSS  --  paleta editorial-industrial. Cremas calidos + ambar quemado + teal.
#  Tipografia: Fraunces (display serif) + IBM Plex Sans (body) + IBM Plex Mono (data)
# =================================================================================

_CSS = """
:root {
  --bg:          #121212;
  --bg-card:    #1e1e1e;
  
  --ink:         #e0e0e0;
  --ink-soft:    #a0a0a0;
  --ink-muted:   #757575;
  
  --rule:        #333333;
  --rule-soft:   #252525;
  
  --amber:       #ff9800;
  --amber-soft:  #3e2715;
  --teal:        #4fc3f7;
  --teal-soft:   #102a3a;
  --sage:        #81c784;
  --sage-soft:   #1b3320;
  --mustard:     #ffd54f;
  --mustard-soft:#332b10;
  --rust:        #e57373;
  --rust-soft:   #3a1c1c;
  
  --display: "Inter", -apple-system, "Segoe UI", sans-serif;
  --body:    "Inter", -apple-system, "Segoe UI", sans-serif;
  --mono:    "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--body);
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

.page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 56px 48px 96px;
}

/* ---- Hero ---- */
.hero {
  border-top: 4px solid var(--ink);
  padding-top: 28px;
  margin-bottom: 36px;
}
.kicker {
  font-family: var(--body);
  font-weight: 500;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--amber);
  margin-bottom: 14px;
}
.title {
  font-family: var(--display);
  font-weight: 500;
  font-size: clamp(40px, 5vw, 64px);
  line-height: 1.02;
  letter-spacing: -0.02em;
  margin: 0 0 18px;
  font-style: normal;
  font-variation-settings: "opsz" 144, "SOFT" 50;
}
.title em {
  font-style: italic;
  font-weight: 400;
  color: var(--amber);
  font-variation-settings: "opsz" 144, "SOFT" 100;
}
.subtitle {
  font-family: var(--body);
  font-size: 16px;
  color: var(--ink-soft);
  max-width: 720px;
  margin: 0 0 24px;
}
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 28px;
  padding-top: 16px;
  border-top: 1px solid var(--rule);
  font-size: 13px;
  color: var(--ink-soft);
}
.meta-row b { color: var(--ink); font-weight: 600; }

/* ---- KPI strip ---- */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  margin: 32px 0 48px;
  border-top: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
}
.kpi {
  padding: 18px 20px;
  border-right: 1px solid var(--rule);
}
.kpi:last-child { border-right: 0; }
.kpi-label {
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: 6px;
}
.kpi-value {
  font-family: var(--display);
  font-size: 32px;
  font-weight: 400;
  line-height: 1;
  color: var(--ink);
  font-variation-settings: "opsz" 48;
}
.kpi-sub {
  margin-top: 6px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-muted);
}

/* ---- Section heading ---- */
.section { margin-top: 64px; }
.section-head {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--ink);
}
.section-num {
  font-family: var(--mono);
  font-size: 13px;
  color: var(--amber);
  font-weight: 500;
}
.section-title {
  font-family: var(--display);
  font-weight: 500;
  font-size: 28px;
  letter-spacing: -0.01em;
  margin: 0;
  font-variation-settings: "opsz" 48;
}
.section-note {
  margin-left: auto;
  font-size: 12px;
  color: var(--ink-muted);
  font-family: var(--mono);
}

/* ---- Resumen por linea ---- */
.linea-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
.linea-card {
  background: var(--bg-card);
  border: 1px solid var(--rule);
  padding: 28px 28px 24px;
  position: relative;
}
.linea-card .badge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  padding: 4px 10px;
  background: var(--ink);
  color: var(--bg);
  margin-bottom: 16px;
}
.linea-card h3 {
  font-family: var(--display);
  font-size: 24px;
  margin: 0 0 18px;
  font-weight: 500;
}
.linea-progress {
  margin: 20px 0 24px;
}
.linea-progress-bar {
  height: 6px;
  background: var(--rule-soft);
  position: relative;
}
.linea-progress-fill {
  position: absolute; left: 0; top: 0; bottom: 0;
  background: var(--sage);
}
.linea-progress-fill.med  { background: var(--mustard); }
.linea-progress-fill.bad  { background: var(--rust); }
.linea-progress-label {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-soft);
}
.linea-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  border-top: 1px solid var(--rule);
  padding-top: 18px;
}
.stat-label {
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: 4px;
}
.stat-value {
  font-family: var(--mono);
  font-size: 18px;
  color: var(--ink);
}

/* ---- Tarjeta de arranque por producto ---- */
.producto-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 22px;
}
.producto-card {
  background: var(--bg-card);
  border: 1px solid var(--rule);
  position: relative;
  overflow: hidden;
}
.producto-card::before {
  content: "";
  position: absolute; top: 0; left: 0; right: 0;
  height: 4px;
  background: var(--sage);
}
.producto-card.conf-media::before    { background: var(--mustard); }
.producto-card.conf-baja::before     { background: var(--rust); }
.producto-card.conf-ninguna::before  { background: var(--ink-muted); }

.prod-head {
  padding: 22px 26px 18px;
  border-bottom: 1px solid var(--rule);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.prod-name {
  font-family: var(--display);
  font-size: 22px;
  font-weight: 500;
  margin: 0;
  line-height: 1.15;
}
.prod-linea-pill {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  background: var(--teal);
  color: white;
  padding: 4px 10px;
  white-space: nowrap;
}
.prod-meta {
  padding: 12px 26px;
  display: flex;
  gap: 20px;
  font-size: 12px;
  color: var(--ink-soft);
  border-bottom: 1px solid var(--rule);
  background: var(--rule-soft);
}
.prod-meta b { color: var(--ink); font-weight: 600; font-family: var(--mono); }
.conf-tag {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  padding: 2px 8px;
}
.conf-tag.alta    { background: var(--sage-soft);    color: var(--sage); }
.conf-tag.muy-alta{ background: var(--sage);         color: white; }
.conf-tag.media   { background: var(--mustard-soft); color: var(--mustard); }
.conf-tag.baja    { background: var(--rust-soft);    color: var(--rust); }
.conf-tag.ninguna { background: var(--rule-soft);    color: var(--ink-muted); }

/* zonas: el corazon de la tarjeta */
.zonas {
  padding: 22px 26px 18px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.zona {
  text-align: left;
  padding: 10px 0;
  position: relative;
}
.zona-label {
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: 6px;
}
.zona-value {
  font-family: var(--mono);
  font-weight: 500;
  font-size: 30px;
  line-height: 1;
  color: var(--ink);
}
.zona-value::after {
  content: "°";
  font-size: 18px;
  color: var(--ink-muted);
  margin-left: 1px;
}
.zona.clave .zona-label { color: var(--amber); }
.zona.clave .zona-value { color: var(--amber); }
.zona.clave .zona-label::after {
  content: " · CLAVE";
  font-family: var(--mono);
  font-size: 9px;
}

.prod-secondary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  padding: 0 26px 18px;
}
.prod-secondary .stat-value { font-size: 16px; }

/* reglas operativas */
.reglas {
  border-top: 1px solid var(--rule);
  padding: 18px 26px 22px;
  background: #171717;
}
.regla-line {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 14px;
  font-size: 13px;
  line-height: 1.5;
  padding: 6px 0;
  border-bottom: 1px dashed var(--rule);
}
.regla-line:last-child { border-bottom: 0; }
.regla-tag {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--ink-muted);
  padding-top: 3px;
}
.regla-tag.alta { color: var(--rust); }
.regla-tag.baja { color: var(--teal); }
.regla-tag.aviso { color: var(--mustard); }
.regla-line.aviso {
  background: var(--mustard-soft);
  border-radius: 2px;
  padding: 8px 12px;
  margin: 6px -12px;
  border-bottom: 0;
}

.corr-strip {
  padding: 12px 26px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-muted);
  border-top: 1px solid var(--rule);
}
.corr-strip b { color: var(--ink-soft); margin-right: 6px; }
.corr-val { margin-left: 4px; }
.corr-val.pos { color: var(--rust); }
.corr-val.neg { color: var(--sage); }

/* ---- Ajustes ambientales ---- */
.amb-section { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.amb-card {
  background: var(--bg-card);
  border: 1px solid var(--rule);
  padding: 22px 26px;
}
.amb-card h3 {
  font-family: var(--display);
  font-size: 22px;
  margin: 0 0 16px;
  font-weight: 500;
}
.amb-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.amb-table th {
  text-align: left;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  padding: 8px 10px 8px 0;
  border-bottom: 1px solid var(--rule);
  font-weight: 500;
}
.amb-table td {
  padding: 12px 10px 12px 0;
  border-bottom: 1px solid var(--rule-soft);
  vertical-align: top;
}
.amb-table tr:last-child td { border-bottom: 0; }
.amb-cond { font-weight: 500; }
.amb-h    { font-family: var(--mono); }
.amb-aj   { font-family: var(--mono); }
.amb-alert {
  display: inline-block;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  padding: 2px 8px;
}
.amb-alert.ok      { background: var(--sage-soft);    color: var(--sage); }
.amb-alert.monitorear { background: var(--mustard-soft); color: var(--mustard); }
.amb-alert.critico { background: var(--rust-soft);    color: var(--rust); }

/* ---- Avisos ---- */
.avisos {
  background: var(--amber-soft);
  border-left: 4px solid var(--amber);
  padding: 18px 24px;
}
.avisos h3 {
  margin: 0 0 8px;
  font-size: 13px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-family: var(--body);
  color: var(--amber);
}
.avisos ul { margin: 0; padding-left: 20px; }
.avisos li { margin: 6px 0; font-size: 13px; color: var(--ink); }

/* ---- Footer ---- */
.footer {
  margin-top: 80px;
  padding-top: 24px;
  border-top: 1px solid var(--rule);
  display: flex;
  justify-content: space-between;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-muted);
  letter-spacing: 0.05em;
}

/* ---- Print ---- */
@media print {
  body { background: white; font-size: 11pt; }
  .page { max-width: none; padding: 12mm 14mm; }
  .producto-card, .linea-card, .amb-card, .avisos { break-inside: avoid; page-break-inside: avoid; }
  .section { margin-top: 28px; }
  .producto-grid { gap: 12px; }
  .producto-card::before { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}

/* ---- Pantallas chicas (operador en tablet) ---- */
@media (max-width: 820px) {
  .page { padding: 32px 20px 60px; }
  .producto-grid, .linea-grid, .amb-section, .kpi-strip { grid-template-columns: 1fr; }
  .kpi-strip { display: grid; }
  .kpi { border-right: 0; border-bottom: 1px solid var(--rule); }
  .zonas { grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .zona-value { font-size: 24px; }
  .regla-line { grid-template-columns: 90px 1fr; }
}
"""

# =================================================================================
#  Helpers de formato HTML
# =================================================================================

def _e(s) -> str:
    return html.escape("" if s is None else str(s))


def _fmt_num(n, blanco="--"):
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return blanco
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    if isinstance(n, int):
        return f"{n:,}"
    return f"{n}"


def _clase_confiabilidad(label: str) -> str:
    L = label.upper()
    if "MUY ALTA" in L:           return "muy-alta"
    if "ALTA" in L:               return "alta"
    if "MEDIA" in L:              return "media"
    if "BAJA" in L or "MUY BAJA" in L: return "baja"
    return "ninguna"


def _clase_alerta(a: str) -> str:
    a = a.lower()
    if "crit" in a: return "critico"
    if "monit" in a: return "monitorear"
    return "ok"


# =================================================================================
#  Bloques principales
# =================================================================================

_MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

def _fecha_es(d: dt.date | None = None) -> str:
    d = d or dt.date.today()
    return f"{d.day} de {_MESES_ES[d.month - 1]}, {d.year}"


def _hero(df: pd.DataFrame) -> str:
    hoy = _fecha_es()
    total = len(df)
    en_rango = int(df["en_rango_h"].sum())
    pct = round(100 * en_rango / total, 1) if total else 0.0
    return f"""
<header class="hero">
  <div class="kicker">19 Hermanos Pet Food · Mejora Continua</div>
  <h1 class="title">Guía de arranque<br>y ajuste del <em>secador</em></h1>
  <p class="subtitle">Parámetros recomendados, reglas de ajuste y respuesta ante condición ambiental para cada producto en cada línea. Generada de forma automática a partir de la bitácora digital del proceso.</p>
  <div class="meta-row">
    <span><b>Generada:</b> {_e(hoy)}</span>
    <span><b>Registros analizados:</b> {_fmt_num(total)}</span>
    <span><b>Meta de humedad:</b> {config.HUMEDAD_MIN:.0f}–{config.HUMEDAD_MAX:.0f}%</span>
    <span><b>AW idóneo:</b> {config.AW_MIN_IDONEO}–{config.AW_MAX_IDONEO}</span>
  </div>
</header>"""


def _kpi_strip(df: pd.DataFrame) -> str:
    total = len(df)
    en_rango = int(df["en_rango_h"].sum())
    pct = round(100 * en_rango / total, 1) if total else 0.0
    n_productos = df["producto"].nunique()
    n_lineas = df["linea"].nunique()
    return f"""
<section class="kpi-strip">
  <div class="kpi">
    <div class="kpi-label">Corridas registradas</div>
    <div class="kpi-value">{_fmt_num(total)}</div>
    <div class="kpi-sub">en {_fmt_num(n_productos)} productos · {_fmt_num(n_lineas)} líneas</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">En rango de humedad</div>
    <div class="kpi-value">{_fmt_num(en_rango)}</div>
    <div class="kpi-sub">{pct}% del total</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Humedad promedio</div>
    <div class="kpi-value">{df["humedad"].mean():.2f}<span style="font-size:18px;color:var(--ink-muted)">%</span></div>
    <div class="kpi-sub">σ = {df["humedad"].std():.2f}%</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">AW promedio</div>
    <div class="kpi-value">{df["aw"].mean():.3f}</div>
    <div class="kpi-sub">idóneo {config.AW_MIN_IDONEO}–{config.AW_MAX_IDONEO}</div>
  </div>
</section>"""


def _resumen_lineas(df: pd.DataFrame) -> str:
    res = resumen_por_linea(df)
    cards = []
    for _, row in res.iterrows():
        pct = float(row["% en rango"])
        prog_class = "" if pct >= 60 else ("med" if pct >= 35 else "bad")
        cards.append(f"""
<div class="linea-card">
  <div class="badge">Línea {_e(row["Linea"].replace("L",""))}</div>
  <h3>Comportamiento general</h3>
  <div class="linea-progress">
    <div class="linea-progress-bar">
      <div class="linea-progress-fill {prog_class}" style="width:{pct}%"></div>
    </div>
    <div class="linea-progress-label">
      <span>{_e(row["En rango H"])} en rango · {pct}%</span>
      <span>meta 100%</span>
    </div>
  </div>
  <div class="linea-stats">
    <div>
      <div class="stat-label">Registros</div>
      <div class="stat-value">{_fmt_num(row["Registros"])}</div>
    </div>
    <div>
      <div class="stat-label">Humedad prom.</div>
      <div class="stat-value">{row["Humedad prom (%)"]:.2f}%</div>
    </div>
    <div>
      <div class="stat-label">σ humedad</div>
      <div class="stat-value">{row["Std humedad (%)"]:.2f}%</div>
    </div>
    <div>
      <div class="stat-label">AW prom.</div>
      <div class="stat-value">{row["AW prom"]:.3f}</div>
    </div>
    <div>
      <div class="stat-label">Z1 prom.</div>
      <div class="stat-value">{row["Z1 prom"]:.0f}°</div>
    </div>
    <div>
      <div class="stat-label">Z2 prom.</div>
      <div class="stat-value">{row["Z2 prom"]:.0f}°</div>
    </div>
    <div>
      <div class="stat-label">Z3 prom.</div>
      <div class="stat-value">{row["Z3 prom"]:.0f}°</div>
    </div>
    <div>
      <div class="stat-label">Z4 prom.</div>
      <div class="stat-value">{row["Z4 prom"]:.0f}°</div>
    </div>
  </div>
</div>""")
    return f"""
<section class="section">
  <div class="section-head">
    <span class="section-num">§ 01</span>
    <h2 class="section-title">Resumen general por línea</h2>
  </div>
  <div class="linea-grid">{"".join(cards)}</div>
</section>"""


def _producto_card(r) -> str:
    a = r.arranque
    conf_class = _clase_confiabilidad(r.confiabilidad)

    # zonas: marca la zona clave con clase especial
    zonas_html = []
    for z in config.ZONAS:
        clave = " clave" if z == r.zona_clave else ""
        val = _fmt_num(a.get(z))
        zonas_html.append(f"""
    <div class="zona{clave}">
      <div class="zona-label">{config.ZONA_NOMBRE[z]}</div>
      <div class="zona-value">{_e(val)}</div>
    </div>""")
    zonas_block = "".join(zonas_html)

    # reglas: separar los tipos para presentarlos con tag
    reglas_html = []
    for regla in r.reglas:
        cls, tag, txt = "", "", regla
        if regla.startswith("DONDE:"):
            tag, txt = "Dónde", regla[len("DONDE:"):].strip()
        elif regla.startswith("CUANTO:"):
            tag, txt = "Cuánto", regla[len("CUANTO:"):].strip()
        elif regla.startswith("CUANDO sale ALTA"):
            cls, tag, txt = "alta", "Sale alta", regla.split(":", 1)[1].strip()
        elif regla.startswith("CUANDO sale BAJA"):
            cls, tag, txt = "baja", "Sale baja", regla.split(":", 1)[1].strip()
        elif regla.startswith("AVISO:"):
            cls, tag, txt = "aviso", "Aviso", regla[len("AVISO:"):].strip()
        elif regla.startswith("APOYO:"):
            tag, txt = "Apoyo", regla[len("APOYO:"):].strip()
        elif regla.startswith("REGLA DE ORO:"):
            tag, txt = "Regla de oro", regla[len("REGLA DE ORO:"):].strip()
        line_cls = " aviso" if cls == "aviso" else ""
        reglas_html.append(
            f'<div class="regla-line{line_cls}"><span class="regla-tag {cls}">{_e(tag)}</span>'
            f'<span>{_e(txt)}</span></div>'
        )

    # correlaciones strip
    corr_items = []
    for z in config.ZONAS:
        c = r.correlaciones.get(z)
        if c is None or (isinstance(c, float) and math.isnan(c)):
            corr_items.append(f'<span><b>{config.ZONA_NOMBRE[z].split()[1]}</b>n/d</span>')
        else:
            sign_cls = "pos" if c > 0 else "neg"
            corr_items.append(
                f'<span><b>{config.ZONA_NOMBRE[z].split()[1]}</b>'
                f'<span class="corr-val {sign_cls}">{c:+.2f}</span></span>'
            )

    rate_txt = _fmt_num(a.get("rate")) + (" kg/h" if a.get("rate") else "")
    agua_txt = _fmt_num(a.get("agua_termo"))

    aviso_si_orientativo = ""
    if r.n_en_rango == 0:
        aviso_si_orientativo = (
            '<div class="regla-line aviso">'
            '<span class="regla-tag aviso">Orientativo</span>'
            '<span>Sin corridas en rango aún; estos valores son punto de partida, no recomendación firme.</span>'
            '</div>'
        )

    return f"""
<article class="producto-card conf-{conf_class}">
  <div class="prod-head">
    <h3 class="prod-name">{_e(r.producto)}</h3>
    <span class="prod-linea-pill">Línea {_e(r.linea.replace("L",""))}</span>
  </div>
  <div class="prod-meta">
    <span><b>{r.n_total}</b> corridas</span>
    <span><b>{r.n_en_rango}</b> en rango</span>
    <span>H: <b>{r.humedad_prom:.2f}%</b> · σ <b>{r.humedad_std:.2f}</b></span>
    <span class="conf-tag {conf_class}">{_e(r.confiabilidad)}</span>
  </div>
  <div class="zonas">{zonas_block}</div>
  <div class="prod-secondary">
    <div>
      <div class="stat-label">Rate</div>
      <div class="stat-value">{_e(rate_txt)}</div>
    </div>
    <div>
      <div class="stat-label">Agua Termo</div>
      <div class="stat-value">{_e(agua_txt)}</div>
    </div>
  </div>
  <div class="reglas">
    {aviso_si_orientativo}
    {"".join(reglas_html)}
  </div>
  <div class="corr-strip">
    <span><b>Corr. zona·humedad</b></span>
    <span>{" ".join(corr_items)}</span>
  </div>
</article>"""


def _productos(df: pd.DataFrame) -> str:
    cards = []
    # Ordenar: por producto, luego por linea (L1 antes que L2)
    for (producto, linea), g in sorted(df.groupby(["producto", "linea"])):
        r = analizar_producto_linea(g, producto, linea)
        cards.append(_producto_card(r))
    return f"""
<section class="section">
  <div class="section-head">
    <span class="section-num">§ 02</span>
    <h2 class="section-title">Tarjetas de arranque por producto y línea</h2>
    <span class="section-note">Mediana de corridas en rango · zona clave marcada</span>
  </div>
  <div class="producto-grid">{"".join(cards)}</div>
</section>"""


def _ambientales(df: pd.DataFrame) -> str:
    cards = []
    for linea in sorted(df["linea"].unique()):
        amb = ajustes_ambientales(df, linea)
        if len(amb) == 0:
            rows = '<tr><td colspan="4" style="color:var(--ink-muted)">Sin datos ambientales suficientes</td></tr>'
        else:
            rows_list = []
            for _, row in amb.iterrows():
                alert_cls = _clase_alerta(row["Alerta"])
                rows_list.append(f"""
    <tr>
      <td class="amb-cond">{_e(row["Condicion"])} <span style="color:var(--ink-muted)">· n={int(row["n"])}</span></td>
      <td class="amb-h">{row["Humedad prom (%)"]:.2f}%</td>
      <td class="amb-aj">{_e(row["Ajuste recomendado"])}</td>
      <td><span class="amb-alert {alert_cls}">{_e(row["Alerta"])}</span></td>
    </tr>""")
            rows = "".join(rows_list)
        cards.append(f"""
<div class="amb-card">
  <h3>Línea {_e(linea.replace("L",""))}</h3>
  <table class="amb-table">
    <thead>
      <tr><th>Condición</th><th>Humedad obs.</th><th>Ajuste preventivo</th><th>Alerta</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>""")
    return f"""
<section class="section">
  <div class="section-head">
    <span class="section-num">§ 03</span>
    <h2 class="section-title">Ajustes preventivos por condición ambiental</h2>
    <span class="section-note">Aplicar ANTES de arrancar sobre los valores base</span>
  </div>
  <div class="amb-section">{"".join(cards)}</div>
</section>"""


def _avisos(avisos: list[str]) -> str:
    if not avisos:
        return ""
    items = "".join(f"<li>{_e(a)}</li>" for a in avisos)
    return f"""
<section class="section">
  <div class="section-head">
    <span class="section-num">§ 04</span>
    <h2 class="section-title">Avisos sobre la calidad de los datos</h2>
  </div>
  <div class="avisos">
    <h3>Detectados automáticamente</h3>
    <ul>{items}</ul>
  </div>
</section>"""


def _footer() -> str:
    hoy = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""
<footer class="footer">
  <span>19 Hermanos Pet Food · Departamento de Mejora Continua</span>
  <span>Generado {hoy}</span>
</footer>"""


# =================================================================================
#  Entry point
# =================================================================================

def generar_html(df: pd.DataFrame, avisos: list[str]) -> str:
    """Devuelve el HTML completo como string. No escribe archivos."""
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Guía de arranque · Secador · 19 Hermanos Pet Food</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>{_CSS}</style>
</head>
<body>
  <main class="page">
    {_hero(df)}
    {_kpi_strip(df)}
    {_resumen_lineas(df)}
    {_productos(df)}
    {_ambientales(df)}
    {_avisos(avisos)}
    {_footer()}
  </main>
</body>
</html>"""
