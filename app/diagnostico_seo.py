"""Vista Diagnóstico SEO -- auditoría técnica real de revistamercado.do (robots.txt,
sitemaps, meta tags, Core Web Vitals reales vía PageSpeed Insights). Auditoría
puntual, no un pipeline recurrente -- ver app/diagnostico_seo_hallazgos.py."""

import html

import streamlit as st

import datos_reales as dr
import diagnostico_seo_hallazgos as h
from estilos import kpi_card

ESTADO_COLOR = {
    "verde": ("#DCFCE7", "#166534", "🟢"),
    "amarillo": ("#FEF3C7", "#92400E", "🟡"),
    "rojo": ("#FEE2E2", "#991B1B", "🔴"),
}
SEVERIDAD_COLOR = {
    "Alta": ("#FEE2E2", "#991B1B"),
    "Alta (condicional)": ("#FEE2E2", "#991B1B"),
    "Media": ("#FEF3C7", "#92400E"),
    "Baja": ("#F1F5F9", "#475569"),
}
CATEGORIA_CWV_COLOR = {"FAST": ("#DCFCE7", "#166534", "🟢"), "AVERAGE": ("#FEF3C7", "#92400E", "🟡"),
                        "SLOW": ("#FEE2E2", "#991B1B", "🔴")}


def _encabezado():
    bg, fg, icono = ESTADO_COLOR[h.ESTADO_GENERAL["nivel"]]
    st.subheader("🔍 Diagnóstico SEO — Revista Mercado")
    st.caption(f"Auditoría técnica real, corrida el {h.FECHA_AUDITORIA}. Puntual, no un pipeline "
               "recurrente -- si pasó mucho tiempo desde esa fecha, vale la pena volver a correrla.")
    st.markdown(
        f'<div style="background:{bg};color:{fg};border-radius:10px;padding:10px 16px;'
        f'font-weight:600;margin-bottom:14px">{icono} {html.escape(h.ESTADO_GENERAL["resumen"])}</div>',
        unsafe_allow_html=True,
    )


def _kpis():
    tarjetas = [kpi_card(k["icono"], k["label"], k["valor"], help_text=k.get("help", "")) for k in h.KPIS]
    st.markdown(f'<div class="cp-kpi-row" style="grid-template-columns:repeat(4,1fr)">{"".join(tarjetas)}</div>',
                unsafe_allow_html=True)


def _hallazgo_principal():
    st.write("")
    with st.container(border=True, key="card_hallazgo_seo"):
        st.markdown("#### 🎯 Hallazgo principal")
        st.markdown(h.HALLAZGO_PRINCIPAL)


def _matriz_acciones():
    st.write("")
    st.markdown("#### 📋 Matriz de acciones priorizadas")
    for a in h.MATRIZ_ACCIONES:
        bg, fg = SEVERIDAD_COLOR.get(a["severidad"], SEVERIDAD_COLOR["Media"])
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;gap:14px;'
            f'background:#FFFFFF;border:1px solid #E7EAF0;border-radius:10px;padding:10px 16px;margin-bottom:8px">'
            f'<div style="min-width:0">'
            f'<div style="font-weight:600;color:#232020;font-size:1rem">{html.escape(a["accion"])}</div>'
            f'<div style="font-size:0.92rem;color:#64748B;margin-top:2px">{html.escape(a["area"])} · '
            f'esfuerzo {html.escape(a["esfuerzo"]).lower()}</div></div>'
            f'<div style="flex-shrink:0;background:{bg};color:{fg};border-radius:999px;padding:4px 12px;'
            f'font-size:0.88rem;font-weight:700;white-space:nowrap">{html.escape(a["severidad"])}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _urgentes():
    st.write("")
    with st.container(border=True, key="card_urgentes_seo"):
        st.markdown("#### 🚨 Correcciones urgentes")
        if not h.URGENTES:
            st.success("Nada urgente confirmado en esta auditoría.")
            return
        for u in h.URGENTES:
            st.markdown(
                f'<div style="background:#FEE2E2;color:#991B1B;border-radius:8px;padding:8px 12px;'
                f'margin-top:6px;font-size:0.92rem">🔴 {u}</div>',
                unsafe_allow_html=True,
            )


def _cwv(df_cwv):
    st.write("")
    st.markdown("#### ⚡ Core Web Vitals (datos de campo reales, mobile)")
    st.caption("Vía PageSpeed Insights API -- percentil 75 de usuarios reales (CrUX), no estimación de laboratorio.")
    if df_cwv.empty:
        st.info("Sin datos de CWV todavía. Correr `data/medir_core_web_vitals.py` (requiere PAGESPEED_API_KEY en .env).")
        return
    cols = st.columns(len(df_cwv))
    for col, (_, r) in zip(cols, df_cwv.iterrows()):
        with col:
            if isinstance(r.get("error"), str) and r["error"]:
                st.markdown(f"**{r['pagina']}**")
                st.caption(f"⚠️ {r['error']}")
                continue
            cat = r.get("overall_category_campo", "")
            bg, fg, icono = CATEGORIA_CWV_COLOR.get(cat, ("#F1F5F9", "#475569", "⚪"))
            st.markdown(
                f'<div style="background:{bg};border-radius:12px;padding:12px 14px">'
                f'<div style="font-weight:700;color:#232020;font-size:0.98rem">{icono} {html.escape(r["pagina"])}</div>'
                f'<div style="font-size:0.88rem;color:{fg};font-weight:600;margin-top:4px">{html.escape(str(cat))}</div>'
                f'<div style="font-size:0.86rem;color:#334155;margin-top:6px">'
                f'LCP {r.get("lcp_campo_ms")}ms · CLS {r.get("cls_campo_x100")} · INP {r.get("inp_campo_ms")}ms</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _cobertura():
    st.write("")
    with st.expander("🔬 Cobertura de esta auditoría (transparencia)"):
        col_ok, col_pend = st.columns(2)
        with col_ok:
            st.markdown("**Verificado con fetch/crawling real:**")
            for item in h.COBERTURA_VERIFICADA:
                st.markdown(f"✅ {item}")
        with col_pend:
            st.markdown("**Pendiente (no confirmado ni descartado):**")
            if not h.COBERTURA_PENDIENTE:
                st.markdown("— nada pendiente")
            for item in h.COBERTURA_PENDIENTE:
                st.markdown(f"⏳ {item}")


def render():
    _encabezado()
    _kpis()
    _hallazgo_principal()
    _matriz_acciones()
    _urgentes()
    _cwv(dr.cargar_cwv_diagnostico())
    _cobertura()
