"""Exporta el reporte de un periodista a PDF — para compartir fuera de la app,
ya que la app en sí no se puede distribuir al equipo."""

import calculos as calc
from fpdf import FPDF

AZUL = (35, 32, 32)  # #232020 — color de texto real de revistamercado.do (no es "azul", se mantiene el nombre por paridad con Colombia.com)
GRIS = (100, 116, 139)
VERDE = (22, 163, 74)
AMARILLO = (217, 119, 6)
ROJO = (220, 38, 38)


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


def generar_pdf_periodista(fila, notas_periodista, logo_path: str, periodo_label: str = "Sin datos cargados aún") -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    pdf.image(logo_path, x=15, y=13, h=10)
    pdf.set_xy(15, 26)
    pdf.set_font("helvetica", "B", 18)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 9, fila["periodista"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(*GRIS)
    pdf.cell(0, 6, f"{fila['seccion']} - Beat: {fila['beat']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Desempeño Editorial - {periodo_label}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_draw_color(220, 224, 232)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)

    color_estado, label_estado = _color_estado(bool(fila["en_alerta"]), fila["eficiencia_normalizada"])
    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 7, "Resumen del periodo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)

    filas_resumen = [
        ("Tráfico total", calc.formatear_numero(fila["clics"])),
        ("Notas publicadas", f"{fila['notas']:.0f}"),
        ("% del tráfico del medio", f"{fila['pct_trafico_total']:.1f}%"),
        ("Eficiencia normalizada", f"{fila['eficiencia_normalizada']:.0f} (100 = mediana del equipo)"),
        ("Estado", label_estado),
        ("Canal dominante", f"{fila['canal_dominante']} ({_fmt(fila['pct_canal_dominante'], '{:.0f}%')})"),
        ("Cumplimiento SEO promedio", f"{_fmt(fila['pct_cumplimiento_prom'], '{:.0f}%')} "
                                       f"({int(fila['notas_seo_evaluadas'])}/{fila['notas']:.0f} notas evaluadas)"),
        ("Semaforo SEO", f"{int(fila['notas_verde'])} verde / {int(fila['notas_amarillo'])} amarillo / "
                          f"{int(fila['notas_rojo'])} rojo"),
        ("Canibalización interna", f"{_fmt(fila['canibalizacion_pct'], '{:.0f}%')}"),
        ("CTR titulares (real vs esperado)", _fmt(fila["ctr_indice"], "{:.2f}x")),
        ("Posición promedio Google", _fmt(fila["posicion_promedio"], "{:.0f}")),
        ("Engagement (tiempo en página)", calc.formatear_tiempo(fila["tiempo_pagina_seg"])),
        ("Dificultad de sección", f"{fila['dificultad_categoria']} (ajuste x{fila['dificultad_ajuste']:.1f})"),
    ]
    for etiqueta, valor in filas_resumen:
        pdf.set_text_color(*GRIS)
        pdf.cell(75, 6.5, etiqueta)
        pdf.set_text_color(*AZUL)
        pdf.cell(0, 6.5, str(valor), new_x="LMARGIN", new_y="NEXT")

    if fila["alertas"]:
        pdf.ln(4)
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(*AZUL)
        pdf.cell(0, 7, "Alertas activas", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 9.5)
        for a in fila["alertas"]:
            color = ROJO if a["severidad"] == "CRÍTICO" else AMARILLO
            pdf.set_text_color(*color)
            msg = a["mensaje"].encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 5.5, f"[{a['severidad']}] {a['tipo']}: {msg}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 7, "Notas más vistas del periodo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "B", 8.5)
    pdf.set_fill_color(241, 245, 249)
    pdf.cell(105, 6.5, "Título", border=0, fill=True)
    pdf.cell(35, 6.5, "Canal", border=0, fill=True)
    pdf.cell(20, 6.5, "Tráfico", border=0, fill=True, align="R")
    pdf.cell(20, 6.5, "SEO", border=0, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

    top = notas_periodista.sort_values("clics", ascending=False).head(10)
    pdf.set_font("helvetica", "", 8.5)
    for _, n in top.iterrows():
        pdf.set_text_color(*AZUL)
        titulo = str(n["titulo"])
        titulo_ascii = titulo.encode("latin-1", "replace").decode("latin-1")
        if len(titulo_ascii) > 62:
            titulo_ascii = titulo_ascii[:59] + "..."
        pdf.cell(105, 6, titulo_ascii)
        pdf.set_text_color(*GRIS)
        pdf.cell(35, 6, str(n["canal_dominante"]))
        pdf.cell(20, 6, calc.formatear_numero(n["clics"]), align="R")
        seo_txt = f"{n['pct_cumplimiento']:.0f}%" if n["pct_cumplimiento"] == n["pct_cumplimiento"] else "s/e"
        pdf.cell(20, 6, seo_txt, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("helvetica", "I", 7.5)
    pdf.set_text_color(*GRIS)
    pdf.multi_cell(0, 4, "Generado con datos reales de GA4 + Search Console + scraping propio. "
                          "Revista Mercado - Desempeño Editorial.")

    return bytes(pdf.output())


def generar_pdf_general(tabla, periodo_label: str = "Sin datos cargados aún") -> bytes:
    """Reporte resumen de todo el equipo (para cuando no hay un periodista puntual seleccionado)."""
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 9, "Desempeño Editorial - Resumen del equipo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*GRIS)
    pdf.cell(0, 6, f"Revista Mercado - {periodo_label}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("helvetica", "B", 8.5)
    pdf.set_fill_color(241, 245, 249)
    anchos = (50, 20, 22, 22, 25, 25)
    encabezados = ("Periodista", "Notas", "Tráfico", "%Medio", "Eficienc.", "SEO %")
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
        pdf.cell(anchos[2], 6.5, calc.formatear_numero(r["clics"]))
        pdf.cell(anchos[3], 6.5, f"{r['pct_trafico_total']:.1f}%")
        pdf.cell(anchos[4], 6.5, f"{r['eficiencia_normalizada']:.0f}")
        pdf.cell(anchos[5], 6.5, _fmt(r["pct_cumplimiento_prom"], "{:.0f}%"))
        pdf.ln()

    return bytes(pdf.output())
