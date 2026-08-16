"""Calculadora de Periodistas — Revista Mercado (revistamercado.do)
Entry point: streamlit run app/main.py
"""

import streamlit as st

import alertas as vista_alertas
import datos_reales as dr
import general
import individual
import notas as vista_notas
import secciones as vista_secciones
from avatares import logo_revistamercado_data_uri
from estilos import inyectar_css
from exportar_pdf import generar_pdf_general, generar_pdf_periodista

st.set_page_config(page_title="Desempeño Editorial — Revista Mercado", layout="wide", page_icon="📊")
inyectar_css()

if "vista" not in st.session_state:
    st.session_state.vista = "general"
if "periodo" not in st.session_state:
    st.session_state.periodo = dr.PERIODO_DEFAULT

periodo = st.session_state.periodo
periodistas_meta = dr.cargar_periodistas_meta(periodo)

if "periodista_slug" not in st.session_state or not any(
        p["slug"] == st.session_state.periodista_slug for p in periodistas_meta):
    st.session_state.periodista_slug = periodistas_meta[0]["slug"] if periodistas_meta else None

tabla_periodistas = dr.cargar_periodistas(periodo)
df_notas = dr.cargar_notas(periodo)

# "Configuración" sigue deshabilitada (fase posterior del proyecto).
NAV_ITEMS = [
    ("🏠", "Dashboard", "general"),
    ("🗂️", "Secciones", "secciones"),
    ("📝", "Notas", "notas"),
    ("🔔", "Alertas", "alertas"),
    ("⚙️", "Configuración", None),
]
VISTAS_PRINCIPALES = {"general", "secciones", "notas", "alertas"}

with st.sidebar:
    st.markdown(
        f'<div style="display:inline-block;margin-bottom:4px;border-radius:10px;overflow:hidden">'
        f'<img src="{logo_revistamercado_data_uri()}" style="height:44px;width:auto;display:block">'
        f'</div>', unsafe_allow_html=True,
    )
    st.caption("Desempeño Editorial")
    st.write("")

    opciones_periodo = [p for p in dr.ORDEN_PERIODOS if p in dr.PERIODOS]
    idx_actual = opciones_periodo.index(periodo) if periodo in opciones_periodo else 0
    periodo_elegido = st.selectbox(
        "Periodo", opciones_periodo, index=idx_actual,
        format_func=lambda p: dr.PERIODOS[p]["label"], key="selector_periodo",
    )
    if periodo_elegido != periodo:
        st.session_state.periodo = periodo_elegido
        st.rerun()
    if not dr.es_periodo_completo(periodo):
        st.caption("⚠️ Muestra histórica — tráfico real y completo, SEO solo sobre notas muestreadas")
    st.write("")

    vista_activa = st.session_state.vista if st.session_state.vista in VISTAS_PRINCIPALES else "general"
    for icono, etiqueta, vista_key in NAV_ITEMS:
        if vista_key is not None:
            es_actual = vista_activa == vista_key
            st.button(f"{icono}  {etiqueta}", key=f"nav_{etiqueta}", width="stretch",
                      type="primary" if es_actual else "secondary",
                      on_click=lambda v=vista_key: st.session_state.update(vista=v))
        else:
            st.button(f"{icono}  {etiqueta}", key=f"nav_{etiqueta}", width="stretch", disabled=True,
                      help="Pendiente de rediseñar con KPIs propios de Revista Mercado")
    st.write("")
    st.caption("v0.2 · jul-2026 censo completo + ene-jun muestra histórica")

st.markdown(
    f'<div class="cp-topbar"><div class="cp-brand">'
    f'<img src="{logo_revistamercado_data_uri()}" class="cp-brand-logo-img" alt="Revista Mercado">'
    f'<span class="cp-brand-sep">|</span>'
    f'<span class="cp-brand-label">DESEMPEÑO EDITORIAL</span>'
    f'</div></div>', unsafe_allow_html=True,
)

periodo_label = dr.PERIODOS[periodo]["label"]

col_espacio, col_periodo, col_export = st.columns([3, 2, 1])
with col_periodo:
    st.markdown(
        f'<div style="text-align:right;padding-top:6px;color:#64748B;font-size:0.92rem">'
        f'📅 Periodo: <b>{periodo_label}</b></div>', unsafe_allow_html=True,
    )
with col_export:
    if st.session_state.vista == "individual" and st.session_state.periodista_slug:
        fila_pdf = tabla_periodistas[tabla_periodistas["slug"] == st.session_state.periodista_slug]
        if not fila_pdf.empty:
            fila_pdf = fila_pdf.iloc[0]
            notas_pdf = df_notas[df_notas["slug"] == st.session_state.periodista_slug]
            pdf_bytes = generar_pdf_periodista(fila_pdf, notas_pdf, "assets/brand/revistamercado_logo.png", periodo_label)
            nombre_archivo = f"reporte_{fila_pdf['slug']}.pdf"
        else:
            pdf_bytes = generar_pdf_general(tabla_periodistas, periodo_label)
            nombre_archivo = "reporte_equipo.pdf"
    else:
        pdf_bytes = generar_pdf_general(tabla_periodistas, periodo_label)
        nombre_archivo = "reporte_equipo.pdf"
    st.download_button("📄 Exportar PDF", data=pdf_bytes, file_name=nombre_archivo,
                        mime="application/pdf", width="stretch", disabled=tabla_periodistas.empty)

if st.session_state.vista == "individual" and st.session_state.periodista_slug:
    col_breadcrumb, col_selector = st.columns([3, 1])
    with col_breadcrumb:
        if st.button("← Volver al dashboard", key="volver_dashboard"):
            st.session_state.vista = "general"
            st.rerun()
        st.markdown('<div class="cp-breadcrumb">Desempeño Editorial &nbsp;›&nbsp; <b>Perfil del Periodista</b></div>',
                    unsafe_allow_html=True)
    nombres = [p["nombre"] for p in periodistas_meta]
    slug_actual = st.session_state.periodista_slug
    nombre_actual = next(p["nombre"] for p in periodistas_meta if p["slug"] == slug_actual)
    with col_selector:
        elegido = st.selectbox("Cambiar periodista", nombres, index=nombres.index(nombre_actual),
                                key="selector_periodista_top")
    slug_elegido = next(p["slug"] for p in periodistas_meta if p["nombre"] == elegido)
    if slug_elegido != slug_actual:
        st.session_state.periodista_slug = slug_elegido
        st.rerun()

    individual.render(tabla_periodistas, df_notas, st.session_state.periodista_slug, periodo)
elif st.session_state.vista == "secciones":
    vista_secciones.render(tabla_periodistas, periodo)
elif st.session_state.vista == "notas":
    vista_notas.render(df_notas)
elif st.session_state.vista == "alertas":
    vista_alertas.render(tabla_periodistas)
else:
    slug_seleccionado = general.render(tabla_periodistas)
    if slug_seleccionado:
        st.session_state.periodista_slug = slug_seleccionado
        st.session_state.vista = "individual"
        st.rerun()
