"""Exporta el reporte de un periodista a PDF — para compartir fuera de la app, ya que
la app en sí corre local y no se puede distribuir al equipo. El PDF debe traer TODA la
información del perfil en pantalla (no un resumen) con el mismo criterio visual: mismos
gráficos (renderizados a imagen con kaleido), mismos colores, mismas tarjetas.

Adaptado de calculadora-periodistas/app/exportar_pdf.py (Colombia.com). Diferencias
reales del sitio, no solo de paleta: EEAT en RM es dos listas (estructural + por-nota,
ver individual.py::ITEMS_EEAT_ESTRUCTURAL/ITEMS_EEAT_POR_NOTA) en vez de una sola lista
plana, porque revistamercado.do no tiene página de autor navegable; y las entidades/temas
usan la columna "forma" (no "entidad")."""

import base64
import io

import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

import calculos as calc
import datos_reales as dr
from avatares import avatar_data_uri
from google_updates import UPDATES_2026
from individual import ACCION_ITEM_SEO, ITEMS_EEAT_ESTRUCTURAL, ITEMS_EEAT_POR_NOTA

_CACHE_TTL_PDF = 300

AZUL = (35, 32, 32)  # #232020 -- color de texto real de revistamercado.do (se mantiene el nombre por paridad con Colombia.com)
GRIS = (100, 116, 139)
VERDE = (22, 163, 74)
AMARILLO = (217, 119, 6)
ROJO = (220, 38, 38)
FONDO_VERDE = (220, 252, 231)
FONDO_AZUL = (219, 234, 254)
FONDO_ROJO = (254, 226, 226)
FONDO_AMARILLO = (254, 243, 199)
FONDO_GRIS = (241, 245, 249)

# Mapa color de texto -> su fondo tenue correspondiente, para que una tarjeta/chip
# siempre use el par correcto (nunca un fondo azul "neutral" con un valor que en
# realidad es bueno/malo).
FONDO_POR_COLOR = {VERDE: FONDO_VERDE, AZUL: FONDO_AZUL, ROJO: FONDO_ROJO, AMARILLO: FONDO_AMARILLO, GRIS: FONDO_GRIS}

ORIENTACION = "L"  # A4 horizontal -- el perfil web es ancho (gráficos + tarjetas lado a
# lado), en A4 vertical se pierde esa proporción y los gráficos quedan aplastados.
ANCHO_UTIL = 267  # mm, A4 horizontal (297) con márgenes de 15mm a cada lado
LIMITE_Y = 188  # mm, borde inferior seguro antes de forzar salto de página (A4 horiz. = 210mm alto)

# La fuente helvetica de FPDF no soporta emoji Unicode (se ven como "??" en el PDF,
# a diferencia de la web) -- se usan etiquetas de texto en su lugar.
TEXTO_TIPO_ENTIDAD = {"entidad": "[Entidad]", "tema": "[Tema]"}


def _color_estado(en_alerta: bool, eficiencia: float):
    if en_alerta:
        return ROJO, "EN ALERTA"
    if eficiencia >= 120:
        return VERDE, "SOBRE MEDIANA"
    return AZUL, "EN RANGO"


def _fmt(valor, patron="{:.0f}", vacio="sin datos"):
    if valor is None or valor != valor:
        return vacio
    return patron.format(valor)


_REEMPLAZOS_UNICODE = {
    "—": "-", "–": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...", "•": "-",
}


def _ascii(txt) -> str:
    """latin-1 (lo único que soporta la fuente helvetica de FPDF sin embeber fuentes
    Unicode) pierde caracteres típicos de textos generados como guion largo/comillas
    tipográficas -- se reemplazan primero por su equivalente ASCII para no dejar "?"
    sueltos en el PDF; el resto (emoji, etc.) sí cae en el placeholder "?"."""
    s = str(txt)
    for feo, bonito in _REEMPLAZOS_UNICODE.items():
        s = s.replace(feo, bonito)
    return s.encode("latin-1", "replace").decode("latin-1")


def _fig_png(fig, width=1300, height=320, scale=2) -> io.BytesIO:
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", font=dict(size=15))
    return io.BytesIO(fig.to_image(format="png", width=width, height=height, scale=scale))


def _grafico_trafico(historial):
    serie = historial.sort_values("mes")
    fig = go.Figure(go.Scatter(
        x=serie["mes_label"], y=serie["trafico"], mode="lines+markers+text",
        line=dict(color="#16A34A", width=3), marker=dict(size=10, color="#16A34A"),
        text=[calc.formatear_numero(v) for v in serie["trafico"]], textposition="top center",
    ))

    updates_por_mes: dict[str, list[dict]] = {}
    for u in UPDATES_2026:
        if u["inicio"].year == 2026 and 1 <= u["inicio"].month <= 7:
            mes_str = u["inicio"].strftime("%Y-%m")
            updates_por_mes.setdefault(mes_str, []).append(u)
    con_update = serie[serie["mes"].isin(updates_por_mes)]
    if not con_update.empty:
        fig.add_trace(go.Scatter(
            x=con_update["mes_label"], y=con_update["trafico"], mode="markers",
            marker=dict(size=13, color="#DC2626", symbol="diamond", line=dict(width=2, color="white")),
            showlegend=False,
        ))
        for r in con_update.itertuples():
            tipos = " + ".join(sorted({u["tipo"] for u in updates_por_mes[r.mes]}))
            fig.add_annotation(
                x=r.mes_label, y=r.trafico, text=tipos, showarrow=True, arrowhead=0, arrowcolor="#DC2626",
                ax=0, ay=-52, font=dict(size=11, color="#DC2626"),
                bgcolor="rgba(255,255,255,0.92)", bordercolor="#DC2626", borderwidth=1, borderpad=3,
            )

    fig.update_layout(margin=dict(l=45, r=15, t=62, b=10), showlegend=False,
                       yaxis=dict(showgrid=True, gridcolor="#E2E6ED", rangemode="tozero", automargin=True),
                       xaxis=dict(showgrid=False))
    return _fig_png(fig)


def _grafico_eficiencia(historial):
    serie = historial.sort_values("mes")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=serie["mes_label"], y=[100] * len(serie), mode="lines",
                              line=dict(color="#94A3B8", dash="dash", width=1), name="Mediana del equipo"))
    fig.add_trace(go.Scatter(x=serie["mes_label"], y=serie["indice"], mode="lines+markers+text",
                              line=dict(color="#3457D5", width=3), marker=dict(size=8),
                              text=[f"{v:.0f}" for v in serie["indice"]], textposition="top center",
                              name="Índice"))
    maxv = max(float(serie["indice"].max()), 100.0)
    relleno = max(35, maxv * 0.15)
    fig.update_layout(margin=dict(l=45, r=15, t=42, b=22), showlegend=True,
                       legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                       yaxis=dict(range=[0, maxv + relleno], showgrid=True, gridcolor="#E2E6ED"),
                       xaxis=dict(showgrid=False))
    return _fig_png(fig)


def _grafico_posicion(historial):
    serie = historial.sort_values("mes").dropna(subset=["posicion_promedio"])
    if serie.empty:
        return None
    fig = go.Figure(go.Scatter(x=serie["mes_label"], y=serie["posicion_promedio"], mode="lines+markers+text",
                                text=[f"{v:.1f}" for v in serie["posicion_promedio"]], textposition="top center",
                                line=dict(color="#3457D5", width=3), marker=dict(size=10)))
    minv, maxv = float(serie["posicion_promedio"].min()), float(serie["posicion_promedio"].max())
    relleno = max(0.4, (maxv - minv) * 0.25)
    fig.update_layout(margin=dict(l=45, r=15, t=20, b=10),
                       yaxis=dict(range=[maxv + relleno, minv - relleno], showgrid=True, gridcolor="#E2E6ED"),
                       xaxis=dict(showgrid=False))
    return _fig_png(fig, width=1300, height=250)


def _grafico_diagnostico_seo(diagnostico):
    if not diagnostico:
        return None
    en_pantalla = list(reversed(diagnostico))
    colores = ["#DC2626" if d["pct"] < 50 else "#F59E0B" if d["pct"] < 80 else "#16A34A" for d in en_pantalla]
    fig = go.Figure(go.Bar(
        x=[d["pct"] for d in en_pantalla], y=[d["label"] for d in en_pantalla], orientation="h",
        marker_color=colores, text=[f"{d['pct']:.0f}%" for d in en_pantalla], textposition="outside",
    ))
    fig.update_layout(margin=dict(l=0, r=40, t=15, b=28),
                       xaxis=dict(range=[0, 108], showgrid=True, gridcolor="#E2E6ED"), showlegend=False)
    return _fig_png(fig, width=850, height=max(280, 26 * len(diagnostico)))


class ReportePDF(FPDF):
    def _seccion_titulo(self, texto):
        self.ln(3)
        self.set_font("helvetica", "B", 13)
        self.set_text_color(*AZUL)
        self.cell(0, 8, _ascii(texto), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(226, 232, 240)
        self.line(15, self.get_y(), 15 + ANCHO_UTIL, self.get_y())
        self.ln(3)

    def _tarjeta_color(self, x, y, w, h, bg, titulo, valor, color_valor):
        self.set_fill_color(*bg)
        self.rect(x, y, w, h, style="F")
        self.set_xy(x + 3, y + 3)
        self.set_font("helvetica", "", 8.5)
        self.set_text_color(*GRIS)
        self.multi_cell(w - 6, 4, _ascii(titulo))
        self.set_xy(x + 3, y + h - 11)
        self.set_font("helvetica", "B", 13)
        self.set_text_color(*color_valor)
        self.cell(w - 6, 8, _ascii(valor))

    def _imagen_ajustada(self, png_bytes, alto_estimado=70):
        if self.get_y() + alto_estimado > LIMITE_Y:
            self.add_page()
        self.image(png_bytes, x=15, w=ANCHO_UTIL)
        self.ln(2)

    def _chip_linea(self, icono, texto, color=None):
        self.set_text_color(*(color or AZUL))
        self.set_font("helvetica", "", 9.5)
        self.multi_cell(0, 5.5, _ascii(f"{icono} {texto}"), new_x="LMARGIN", new_y="NEXT")


def generar_pdf_periodista(fila, notas_periodista, logo_path: str, periodo_label: str = "Sin datos cargados aún") -> bytes:
    meta = dr.periodista_por_slug(fila["slug"])
    historial = dr.historial_periodista(meta["autor_original"]) if meta else None
    ranking = dr.ranking_periodista(meta["autor_original"], "2026-07") if meta else None

    pdf = ReportePDF(orientation=ORIENTACION, format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # --- Header ---------------------------------------------------------
    pdf.image(logo_path, x=15, y=13, h=10)
    if meta:
        try:
            uri = avatar_data_uri(meta["nombre"], "#334155", 200)
            foto_bytes = base64.b64decode(uri.split(",", 1)[1])
            pdf.image(io.BytesIO(foto_bytes), x=15 + ANCHO_UTIL - 22, y=13, w=22, h=22)
        except Exception:
            pass
    pdf.set_xy(15, 26)
    pdf.set_font("helvetica", "B", 18)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 9, _ascii(fila["periodista"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(*GRIS)
    pdf.cell(0, 6, _ascii(f"{fila['seccion']} - Beat: {fila['beat']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _ascii(f"Desempeno Editorial - {periodo_label}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_draw_color(220, 224, 232)
    pdf.line(15, pdf.get_y(), 15 + ANCHO_UTIL, pdf.get_y())
    pdf.ln(6)

    # --- Resumen del periodo --------------------------------------------
    color_estado, label_estado = _color_estado(bool(fila["en_alerta"]), fila["eficiencia_normalizada"])
    dif_es_facil = fila["dificultad_categoria"] in ("Facil", "Fácil")
    dif_es_dificil = fila["dificultad_categoria"] in ("Dificil", "Difícil")
    color_dificultad = VERDE if dif_es_facil else ROJO if dif_es_dificil else AZUL

    pdf._seccion_titulo("Resumen del periodo")
    y0 = pdf.get_y()
    ancho_tarjeta = (ANCHO_UTIL - 3 * 5) / 4
    x1, x2, x3, x4 = (15 + i * (ancho_tarjeta + 5) for i in range(4))
    pdf._tarjeta_color(
        x1, y0, ancho_tarjeta, 22, FONDO_VERDE,
        f"Trafico total ({fila['pct_trafico_total']:.1f}% del medio)",
        calc.formatear_numero(fila["clics"]), VERDE,
    )
    pdf._tarjeta_color(x2, y0, ancho_tarjeta, 22, FONDO_POR_COLOR[color_estado], "Estado actual", label_estado, color_estado)
    pdf._tarjeta_color(
        x3, y0, ancho_tarjeta, 22, FONDO_POR_COLOR[color_dificultad],
        "Dificultad de seccion", _ascii(fila["dificultad_categoria"]), color_dificultad,
    )
    pdf._tarjeta_color(
        x4, y0, ancho_tarjeta, 22, FONDO_AZUL, "Ranking (julio, censo completo)",
        f"#{ranking[0]} de {ranking[1]}" if ranking else "sin dato", AZUL,
    )
    y1 = y0 + 26

    # --- Metricas clave del periodo --------------------------------------
    engagement_txt = calc.formatear_tiempo(fila["tiempo_pagina_seg"])
    metricas = [
        ("Volumen de notas publicadas", f"{fila['notas']:.0f}", AZUL),
        ("Eficiencia normalizada (100=mediana equipo)", f"{fila['eficiencia_normalizada']:.0f}", VERDE),
        ("Canal dominante", f"{fila['canal_dominante']} ({_fmt(fila['pct_canal_dominante'], '{:.0f}%')})", AZUL),
        ("CTR titulares (real vs esperado)", _fmt(fila["ctr_indice"], "{:.2f}x"), AZUL),
        ("Engagement (tiempo en pagina)", engagement_txt, AZUL),
        ("Canibalizacion interna", _fmt(fila["canibalizacion_pct"], "{:.0f}%"),
         ROJO if (fila["canibalizacion_pct"] or 0) > 8 else VERDE),
        ("Extension promedio (palabras)", _fmt(fila["palabras_promedio"], "{:.0f}"), AZUL),
        ("Notas con semaforo SEO verde", f"{fila['semaforo_verde_pct']:.0f}%", VERDE),
    ]
    ancho_m = (ANCHO_UTIL - 3 * 5) / 4
    for i, (titulo, valor, color) in enumerate(metricas):
        col, fila_grid = i % 4, i // 4
        x = 15 + col * (ancho_m + 5)
        y = y1 + fila_grid * 24
        pdf._tarjeta_color(x, y, ancho_m, 20, FONDO_POR_COLOR[color], titulo, valor, color)
    y2 = y1 + 2 * 24 + 4

    # --- Autoridad en Google + Cumplimiento SEO --------------------------
    secundarias = [
        ("Notas en Top 10 Google", f"{fila['notas_top10']:.0f}", VERDE),
        ("Posicion promedio Google", _fmt(fila["posicion_promedio"], "{:.0f}"), AZUL),
        ("Cumplimiento SEO promedio", f"{_fmt(fila['pct_cumplimiento_prom'], '{:.0f}%')} "
         f"({int(fila['notas_seo_evaluadas'])}/{fila['notas']:.0f} eval.)", AZUL),
        ("Semaforo SEO (verde/amarillo/rojo)",
         f"{int(fila['notas_verde'])} / {int(fila['notas_amarillo'])} / {int(fila['notas_rojo'])}", AZUL),
    ]
    for i, (titulo, valor, color) in enumerate(secundarias):
        x = 15 + i * (ancho_m + 5)
        pdf._tarjeta_color(x, y2, ancho_m, 20, FONDO_POR_COLOR[color], titulo, valor, color)
    pdf.set_xy(15, y2 + 24)

    dif = fila["dificultad_categoria"]
    efic = fila["eficiencia_normalizada"]
    bajo = efic == efic and efic < 70
    if not bajo:
        diag = "Rendimiento acorde o mejor a lo esperado para la dificultad de esta seccion."
    elif dif == "Fácil" or dif == "Facil":
        diag = "Seccion facil pero rendimiento bajo -- la seccion no es la limitante aqui, revisar al periodista."
    elif dif == "Difícil" or dif == "Dificil":
        diag = "Seccion dificil -- el bajo trafico se explica en parte por eso, no solo por el periodista."
    else:
        diag = "Rendimiento bajo en una seccion de dificultad media -- revisar caso a caso."
    pdf.ln(2)
    pdf.set_font("helvetica", "I", 9)
    pdf.set_text_color(*GRIS)
    pdf.multi_cell(0, 5, _ascii(diag), new_x="LMARGIN", new_y="NEXT")

    # --- Graficos historicos (7 periodos) --------------------------------
    if historial is not None and not historial.empty:
        pdf._seccion_titulo("Trafico por periodo (7 periodos, ene-jul 2026)")
        pdf._imagen_ajustada(_grafico_trafico(historial))

        pdf._seccion_titulo("Eficiencia normalizada en el tiempo")
        pdf._imagen_ajustada(_grafico_eficiencia(historial))

        png_pos = _grafico_posicion(historial)
        if png_pos:
            pdf._seccion_titulo(f"Posicion promedio en Google - {fila['beat']}")
            pdf._imagen_ajustada(png_pos, alto_estimado=70)

    # --- En que secciones le rinde escribir -------------------------------
    if meta:
        esp = dr.entidades_fuertes(meta["autor_original"])
        if not esp.empty:
            pdf._seccion_titulo("En que secciones le rinde escribir (7 periodos)")
            pdf.set_font("helvetica", "B", 8.5)
            pdf.set_fill_color(*FONDO_GRIS)
            pdf.cell(90, 6.5, "Seccion", fill=True)
            pdf.cell(40, 6.5, "Dificultad", fill=True)
            pdf.cell(50, 6.5, "Trafico/nota", fill=True, align="R")
            pdf.cell(35, 6.5, "Notas", fill=True, align="R")
            pdf.cell(40, 6.5, "Confianza", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", "", 8.5)
            for _, r in esp.iterrows():
                label = dr.seccion_label(r["seccion"]) or str(r["seccion"]).title()
                dif_cat, _ = dr.dificultad_seccion(r["seccion"])
                color_dif = VERDE if dif_cat in ("Facil", "Fácil") else ROJO if dif_cat in ("Dificil", "Difícil") else AZUL
                pdf.set_text_color(*AZUL)
                pdf.cell(90, 6, _ascii(label))
                pdf.set_fill_color(*FONDO_POR_COLOR[color_dif])
                pdf.set_text_color(*color_dif)
                pdf.cell(40, 6, _ascii(dif_cat), fill=True)
                pdf.set_text_color(*GRIS)
                pdf.cell(50, 6, _ascii(f"{r['trafico_por_nota']:,.0f}"), align="R")
                pdf.cell(35, 6, f"{int(r['notas'])}", align="R")
                pdf.cell(40, 6, _ascii(r["confianza"]), align="C", new_x="LMARGIN", new_y="NEXT")

        # --- Temas en los que le rinde / no le rinde ----------------------
        fuertes = dr.temas_fuertes(meta["autor_original"])
        debiles = dr.temas_debiles(meta["autor_original"])
        if not fuertes.empty or not debiles.empty:
            pdf._seccion_titulo("Temas en los que le rinde (y en los que no)")
            pdf.set_font("helvetica", "I", 8)
            pdf.set_text_color(*GRIS)
            pdf.multi_cell(0, 4.5, _ascii(
                "Entidad = persona/equipo/lugar/organizacion unica e identificable. Tema = frase "
                "tematica recurrente (relevancia semantica, no una entidad unica)."), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            COLOR_CONF_FUERTES = {"alta": VERDE, "media": AMARILLO, "baja": GRIS}
            COLOR_CONF_DEBILES = {"alta": ROJO, "media": ROJO, "baja": GRIS}
            if not fuertes.empty:
                pdf.set_font("helvetica", "B", 9.5)
                pdf.set_text_color(*VERDE)
                pdf.cell(0, 6, "Le rinde:", new_x="LMARGIN", new_y="NEXT")
                for _, r in fuertes.iterrows():
                    etiqueta = TEXTO_TIPO_ENTIDAD.get(r.get("tipo"), "-")
                    color = COLOR_CONF_FUERTES.get(r.get("confianza"), AZUL)
                    pdf._chip_linea(etiqueta, f"{r['forma']} - {calc.formatear_numero(r['trafico'])} "
                                              f"({int(r['notas'])} notas, confianza {r.get('confianza', '?')})", color)
            if not debiles.empty:
                pdf.ln(1)
                pdf.set_font("helvetica", "B", 9.5)
                pdf.set_text_color(*ROJO)
                pdf.cell(0, 6, "No le rinde:", new_x="LMARGIN", new_y="NEXT")
                for _, r in debiles.iterrows():
                    etiqueta = TEXTO_TIPO_ENTIDAD.get(r.get("tipo"), "-")
                    color = COLOR_CONF_DEBILES.get(r.get("confianza"), GRIS)
                    pdf._chip_linea(etiqueta, f"{r['forma']} - {calc.formatear_numero(r['trafico'])} "
                                              f"({int(r['notas'])} notas, confianza {r.get('confianza', '?')})", color)

        # --- EEAT ------------------------------------------------------
        # Dos listas (no una sola como en Colombia.com): revistamercado.do no
        # tiene página de autor navegable, así que "estructural" son 3 ítems
        # booleanos a nivel de sitio y "por-nota" son 4 porcentajes sobre una
        # muestra -- ver individual.py::_eeat_checklist.
        eeat = dr.eeat_por_autor(meta["autor_original"])
        if eeat:
            pdf._seccion_titulo("EEAT - checklist de confianza y autoridad")
            pdf.set_font("helvetica", "I", 8)
            pdf.set_text_color(*GRIS)
            pdf.multi_cell(0, 4.5, _ascii(f"Muestra de {int(eeat['notas_muestreadas'])} notas de "
                                           "todo el historico + julio 2026."), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_text_color(*AZUL)
            pdf.cell(0, 5.5, "Estructural (a nivel de sitio, igual para todos)", new_x="LMARGIN", new_y="NEXT")
            for clave, titulo, _detalle in ITEMS_EEAT_ESTRUCTURAL:
                ok = bool(eeat.get(clave))
                color = VERDE if ok else AMARILLO
                pdf.set_text_color(*color)
                pdf.set_font("helvetica", "B", 9.5)
                icono = "[OK]" if ok else "[!]"
                pdf.cell(0, 6, _ascii(f"{icono} {titulo}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_text_color(*AZUL)
            pdf.cell(0, 5.5, _ascii(f"Por-nota (muestra de {int(eeat['notas_muestreadas'])} notas)"),
                      new_x="LMARGIN", new_y="NEXT")
            for clave, titulo, _detalle in ITEMS_EEAT_POR_NOTA:
                valor = eeat.get(clave) or 0
                ok = valor >= 50
                color = VERDE if ok else AMARILLO
                pdf.set_text_color(*color)
                pdf.set_font("helvetica", "B", 9.5)
                icono = "[OK]" if ok else "[!]"
                pdf.cell(0, 6, _ascii(f"{icono} {titulo} - {valor:.0f}%"), new_x="LMARGIN", new_y="NEXT")

    # --- Cumplimiento SEO: desglose por item -------------------------------
    if meta:
        diagnostico = dr.diagnostico_seo_por_autor(meta["autor_original"])
        png_seo = _grafico_diagnostico_seo(diagnostico)
        if png_seo:
            pdf._seccion_titulo("En que esta fallando el SEO - desglose por item")
            pdf._imagen_ajustada(png_seo, alto_estimado=125)

            pendientes = [d for d in diagnostico if d["pct"] < 80]
            if pendientes:
                pdf.set_font("helvetica", "B", 10)
                pdf.set_text_color(*AZUL)
                pdf.cell(0, 7, "Que debe mejorar - instrucciones concretas", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("helvetica", "", 8.5)
                for d in pendientes:
                    pdf.set_text_color(*(ROJO if d["pct"] < 50 else AMARILLO))
                    accion = ACCION_ITEM_SEO.get(d["item"], "Revisar este punto del checklist SEO.")
                    pdf.multi_cell(0, 5, _ascii(f"({d['pct']:.0f}%) {d['label']}: {accion}"),
                                    new_x="LMARGIN", new_y="NEXT")

    # --- Alertas activas -----------------------------------------------
    if fila["alertas"]:
        pdf._seccion_titulo("Alertas activas (estado actual)")
        pdf.set_font("helvetica", "", 9.5)
        for a in fila["alertas"]:
            color = ROJO if a["severidad"] == "CRÍTICO" else AMARILLO
            pdf.set_text_color(*color)
            pdf.multi_cell(0, 5.5, _ascii(f"[{a['severidad']}] {a['tipo']}: {a['mensaje']}"),
                            new_x="LMARGIN", new_y="NEXT")

    # --- Notas mas vistas -------------------------------------------------
    pdf._seccion_titulo("Notas mas vistas del periodo")
    pdf.set_font("helvetica", "B", 8.5)
    pdf.set_fill_color(*FONDO_GRIS)
    pdf.cell(160, 6.5, "Titulo", fill=True)
    pdf.cell(45, 6.5, "Canal", fill=True)
    pdf.cell(27, 6.5, "Trafico", fill=True, align="R")
    pdf.cell(30, 6.5, "SEO", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

    top = notas_periodista.sort_values("clics", ascending=False).head(15)
    pdf.set_font("helvetica", "", 8.5)
    for _, n in top.iterrows():
        if pdf.get_y() + 6 > LIMITE_Y:
            pdf.add_page()
        pdf.set_text_color(*AZUL)
        titulo_ascii = _ascii(n["titulo"])
        if len(titulo_ascii) > 95:
            titulo_ascii = titulo_ascii[:92] + "..."
        pdf.cell(160, 6, titulo_ascii)
        pdf.set_text_color(*GRIS)
        pdf.cell(45, 6, _ascii(n["canal_dominante"]))
        pdf.cell(27, 6, _ascii(calc.formatear_numero(n["clics"])), align="R")
        seo_txt = f"{n['pct_cumplimiento']:.0f}%" if n["pct_cumplimiento"] == n["pct_cumplimiento"] else "s/e"
        pdf.cell(30, 6, seo_txt, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("helvetica", "I", 7.5)
    pdf.set_text_color(*GRIS)
    pdf.multi_cell(0, 4, _ascii(
        "Generado con datos reales de GA4 + Search Console + scraping propio. "
        "Reporte completo (no resumido) del perfil de desempeno editorial. Revista Mercado."))

    return bytes(pdf.output())


@st.cache_data(show_spinner=False, ttl=_CACHE_TTL_PDF)
def generar_pdf_periodista_cacheado(slug: str, logo_path: str, periodo_label: str) -> bytes | None:
    """Wrapper cacheado -- el PDF completo (con 4 gráficos renderizados vía kaleido)
    tarda varios segundos en generarse. Sin caché, main.py lo regeneraba en CADA rerun
    de la app (cada clic), no solo al pulsar "Exportar PDF" -- hacía toda la navegación
    del perfil individual lenta."""
    tabla = dr.cargar_periodistas()
    fila = tabla[tabla["slug"] == slug]
    if fila.empty:
        return None
    fila = fila.iloc[0]
    notas = dr.cargar_notas()
    notas = notas[notas["slug"] == slug]
    return generar_pdf_periodista(fila, notas, logo_path, periodo_label)


def generar_pdf_general(tabla, periodo_label: str = "Sin datos cargados aún") -> bytes:
    """Reporte resumen de todo el equipo (para cuando no hay un periodista puntual seleccionado)."""
    pdf = FPDF(orientation=ORIENTACION, format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 9, "Desempeno Editorial - Resumen del equipo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*GRIS)
    pdf.cell(0, 6, f"Revista Mercado - {periodo_label}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("helvetica", "B", 8.5)
    pdf.set_fill_color(*FONDO_GRIS)
    anchos = (50, 20, 22, 22, 25, 25)
    encabezados = ("Periodista", "Notas", "Trafico", "%Medio", "Eficienc.", "SEO %")
    for w, h in zip(anchos, encabezados):
        pdf.cell(w, 7, h, border=0, fill=True)
    pdf.ln()
    pdf.set_font("helvetica", "", 8.5)
    for _, r in tabla.sort_values("clics", ascending=False).iterrows():
        pdf.set_text_color(*AZUL)
        nombre = r["periodista"].encode("latin-1", "replace").decode("latin-1")
        pdf.cell(anchos[0], 6.5, nombre)
        pdf.set_text_color(*GRIS)
        pdf.cell(anchos[1], 6.5, f"{r['notas']:.0f}")
        pdf.cell(anchos[2], 6.5, _ascii(calc.formatear_numero(r["clics"])))
        pdf.cell(anchos[3], 6.5, f"{r['pct_trafico_total']:.1f}%")
        pdf.cell(anchos[4], 6.5, f"{r['eficiencia_normalizada']:.0f}")
        pdf.cell(anchos[5], 6.5, _fmt(r["pct_cumplimiento_prom"], "{:.0f}%"))
        pdf.ln()

    return bytes(pdf.output())
