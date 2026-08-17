"""Vista Temas del día -- lote de entidades prioritarias del portal cruzadas con
keywords relacionadas en tendencia + SERP actual, vía Semrush. No es un pipeline
automático (ver datos_reales.cargar_temas_del_dia); se regenera bajo pedido a Claude."""

import html

import pandas as pd
import streamlit as st

import datos_reales as dr

UMBRAL_TENDENCIA_ALTA = 0.6


def _formatear_volumen(v: float) -> str:
    v = int(v)
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M/mes".replace(".0M", "M")
    if v >= 1_000:
        return f"{v / 1_000:.0f}K/mes"
    return f"{v}/mes"


def _tarjeta(row) -> None:
    delta = float(row["tendencia_delta"])
    icono = "🔥" if delta >= UMBRAL_TENDENCIA_ALTA else ("📈" if delta > 0 else "➖")
    en_top5 = bool(row["revistamercado_en_top5"])
    if en_top5:
        chip = '<span style="background:#DCFCE7;color:#166534;border-radius:999px;padding:3px 12px;font-size:0.85rem;font-weight:700">✅ Ya en el top 5</span>'
    else:
        chip = '<span style="background:#FEF3C7;color:#92400E;border-radius:999px;padding:3px 12px;font-size:0.85rem;font-weight:700">🔓 Oportunidad -- no aparece</span>'
    with st.container(border=True, key=f"card_tema_{row.name}"):
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;gap:10px">'
            f'<div style="font-weight:700;color:#232020;font-size:1.05rem">{icono} {html.escape(row["entidad"])}</div>'
            f'{chip}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="margin-top:6px;font-size:0.95rem;color:#334155">'
            f'Keyword con más tendencia: <b>"{html.escape(row["keyword_ganadora"])}"</b> '
            f'-- {_formatear_volumen(row["volumen"])} de búsquedas, tendencia {delta:+.0%} vs. hace 6 meses</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="margin-top:4px;font-size:0.88rem;color:#64748B">'
            f'Hoy rankea #1: <a href="{html.escape(row["top1_url"])}" target="_blank">{html.escape(row["top1_dominio"])}</a></div>',
            unsafe_allow_html=True,
        )


def render():
    st.subheader("🗓️ Temas del día")
    df = dr.cargar_temas_del_dia()
    if df.empty:
        st.info("Sin lote generado todavía. Pídele a Claude: \"genera el lote de temas del día\".")
        return

    fecha = df["fecha_generado"].iloc[0] if "fecha_generado" in df.columns else "?"
    st.caption(
        f"Lote generado el {fecha}. Entidades prioritarias del portal (de 'Temas recomendados') "
        "cruzadas con keywords relacionadas en tendencia y quién rankea hoy en el top 5, vía "
        "Semrush -- no es una búsqueda de noticias en vivo, es una pista de demanda de búsqueda "
        "real. No se actualiza solo: pídele a Claude que genere un lote nuevo cuando lo necesites."
    )

    n_oportunidad = int((~df["revistamercado_en_top5"]).sum())
    st.markdown(
        f'<div style="background:#FEF3C7;color:#92400E;border-radius:10px;padding:10px 16px;'
        f'font-weight:600;margin-bottom:14px">🔓 {n_oportunidad} de {len(df)} entidades del lote de hoy: '
        f'revistamercado.do no aparece en el top 5 de Google para su keyword en tendencia.</div>',
        unsafe_allow_html=True,
    )

    ordenado = df.sort_values("tendencia_delta", ascending=False).reset_index(drop=True)
    for _, row in ordenado.iterrows():
        _tarjeta(row)
