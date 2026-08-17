"""Vista YouTube — canal "Mercado Media Network" (Revista Mercado). Pedido de
Edwin, 17-ago-2026: "quiero que el informe de mercado tenga su propia sección
de YouTube... ingresos, visitas sin pauta (orgánico), de dónde nos visitan,
videos más vistos, qué le funciona/qué no, qué pasa con los videos de los
empresarios, temas fuertes/débiles, shorts vs. videos largos".

A diferencia del resto de esta app (GA4/GSC vía export automático diario de
Apps Script), YouTube Studio Analytics NO tiene ese pipeline -- no hay API
conectada, así que esta vista lee un SNAPSHOT manual exportado a mano desde
YouTube Studio ("Modo avanzado" -> exportar a Sheets), no se refresca sola.
Para actualizarla: en YouTube Studio, Analytics -> Modo avanzado -> filtro
"Orgánica" -> exportar -> pedirle a Claude que regenere data/youtube_*.csv
con el nuevo Sheet.

Cobertura real de esta muestra (17-ago-2026): 159 videos, 2.400.362 de
2.403.555 vistas orgánicas reales del snapshot de YouTube Studio (99.9%) --
se dejó fuera la cola larga de videos históricos con 1-3 vistas en la
ventana, no cambia ningún promedio de forma relevante.

Ingresos: la columna "Ingresos estimados" viene vacía/0 para TODO el
snapshot, incluida la fila "Total" -- no es un bug de esta vista, es lo que
devuelve YouTube Studio con el nivel de acceso actual (la cuenta conectada
aparece como "Editor", no "Propietario"/"Administrador con ingresos" -- ese
rol específico suele ser el que YouTube exige para mostrar ingresos). Se
declara así en la UI, nunca se inventa un número.
"""

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
from estilos import kpi_card

RUTA_DATOS = "data/youtube_agosto_organico.csv"
FECHA_SNAPSHOT = "17-ago-2026"
VENTANA_SNAPSHOT = "vistas orgánicas acumuladas en agosto 2026 (snapshot de YouTube Studio, mes en curso)"

COLOR_CATEGORIA = {
    "Noticias breves (geopolítica/actualidad)": "#3457D5",
    "Empresarios / Liderazgo": "#DC2626",
    "Otros / Institucional": "#94A3B8",
    "Deportes": "#16A34A",
    "Documental (Kathleen Martínez)": "#D97706",
    "Mercado Podcast": "#7C3AED",
}


@st.cache_data
def _cargar() -> pd.DataFrame:
    try:
        df = pd.read_csv(RUTA_DATOS)
    except FileNotFoundError:
        return pd.DataFrame()
    df["fecha_publicacion"] = pd.to_datetime(df["fecha_publicacion"], errors="coerce")
    return df


def _kpis(df: pd.DataFrame):
    total_vistas = df["vistas"].sum()
    total_horas = df["horas_reproduccion"].sum()
    pct_reprod_prom = (df["vistas"] * df["pct_reproducido"]).sum() / total_vistas if total_vistas else 0
    ingresos_total = df["ingresos_usd"].fillna(0).sum()

    tarjetas = [
        kpi_card("👁️", "Vistas orgánicas (snapshot)", calc.formatear_numero(total_vistas)),
        kpi_card("⏱️", "Horas de reproducción", calc.formatear_numero(total_horas)),
        kpi_card("📊", "% promedio reproducido", f"{pct_reprod_prom:.0f}%",
                  help_text="Ponderado por vistas -- >100% es normal en videos cortos con repeticiones (loop)."),
        kpi_card("🎬", "Videos con actividad", f"{len(df)}"),
        kpi_card("💰", "Ingresos estimados", "Sin acceso" if ingresos_total == 0 else calc.formatear_numero(ingresos_total),
                  help_text="YouTube Studio no devuelve ingresos con el nivel de acceso actual (cuenta conectada como "
                             "'Editor', no 'Propietario'/'Administrador con ingresos'). No es que sean $0 reales -- "
                             "es que este acceso no los puede ver. Pídele a quien administre el canal que dé acceso "
                             "de ingresos, o que exporte esa pestaña aparte."),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _aviso_snapshot():
    st.info(
        f"📸 **Esto es un snapshot manual**, no un dato que se actualiza solo como el resto de la app. "
        f"Exportado de YouTube Studio el {FECHA_SNAPSHOT}, canal 'Mercado Media Network', filtrado a "
        f"**{VENTANA_SNAPSHOT}**. Para refrescarlo: YouTube Studio → Analytics → Modo avanzado → filtro "
        f"'Orgánica' → exportar a Google Sheets → pedirle a Claude que regenere los datos con ese Sheet nuevo."
    )


def _por_categoria(df: pd.DataFrame):
    st.subheader("Qué le funciona y qué no — por tipo de contenido")
    st.caption(
        "Clasificación automática por título/duración (geopolítica y desastres = noticia breve; entrevistas a "
        "líderes/empresarios/duración larga = Empresarios; Mundial/Clásico/Juegos = Deportes). Puede tener algo "
        "de ruido puntual, pero el patrón general es claro y real."
    )
    agg = df.groupby("categoria").agg(
        videos=("video_id", "count"), vistas=("vistas", "sum"), horas=("horas_reproduccion", "sum"),
    ).reset_index()
    agg["vistas_por_video"] = (agg["vistas"] / agg["videos"]).round(0)
    agg = agg.sort_values("vistas", ascending=True)

    fig = go.Figure(go.Bar(
        x=agg["vistas"], y=agg["categoria"], orientation="h",
        marker_color=[COLOR_CATEGORIA.get(c, "#64748B") for c in agg["categoria"]],
        text=[f"{calc.formatear_numero(v)} · {n} videos · {calc.formatear_numero(vpv)}/video"
              for v, n, vpv in zip(agg["vistas"], agg["videos"], agg["vistas_por_video"])],
        textposition="outside",
        hovertemplate="%{y}<br>Vistas: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(260, 55 * len(agg)), margin=dict(l=0, r=140, t=10, b=10),
        xaxis_title=None, yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    noticias = agg[agg["categoria"] == "Noticias breves (geopolítica/actualidad)"]
    empresarios = agg[agg["categoria"] == "Empresarios / Liderazgo"]
    if not noticias.empty and not empresarios.empty:
        vpv_noticias = noticias["vistas_por_video"].iloc[0]
        vpv_empresarios = empresarios["vistas_por_video"].iloc[0]
        ratio = vpv_noticias / vpv_empresarios if vpv_empresarios else 0
        st.markdown(
            f'<div style="background:#FEF2F2;color:#991B1B;border-radius:10px;padding:12px 16px;'
            f'font-weight:600;margin-top:8px">⚠️ Los videos de "Empresarios / Liderazgo" '
            f'({int(empresarios["videos"].iloc[0])} videos publicados, casi tantos como noticias) generan en '
            f'promedio <b>{calc.formatear_numero(vpv_empresarios)} vistas/video</b> — las noticias breves generan '
            f'{ratio:,.0f}× más ({calc.formatear_numero(vpv_noticias)} vistas/video). No es una diferencia menor: '
            f'es la brecha más grande del canal entre volumen de producción e impacto real.</div>',
            unsafe_allow_html=True,
        )


def _shorts_vs_largos(df: pd.DataFrame):
    st.subheader("Shorts (≤3 min) vs. videos largos")
    agg = df.groupby("es_short").agg(
        videos=("video_id", "count"), vistas=("vistas", "sum"), horas=("horas_reproduccion", "sum"),
    ).reset_index()
    agg["label"] = agg["es_short"].map({True: "Shorts / formato corto (≤3 min)", False: "Formato largo (>3 min)"})
    agg["vistas_por_video"] = (agg["vistas"] / agg["videos"]).round(0)

    col1, col2 = st.columns(2)
    for col, corto in zip([col1, col2], [True, False]):
        fila = agg[agg["es_short"] == corto]
        if fila.empty:
            continue
        f = fila.iloc[0]
        with col:
            st.markdown(f"**{f['label']}**")
            st.markdown(
                f"{int(f['videos'])} videos · **{calc.formatear_numero(f['vistas'])}** vistas · "
                f"{calc.formatear_numero(f['vistas_por_video'])} vistas/video promedio"
            )
    st.caption(
        "El formato corto domina el canal casi por completo — la duración promedio de los videos con más "
        "tracción está entre 80 y 160 segundos, todos publicados el mismo día o el día después del hecho noticioso."
    )


def _top_videos(df: pd.DataFrame, top_n: int = 15):
    st.subheader("Videos más vistos del periodo")
    top = df.sort_values("vistas", ascending=False).head(top_n)
    for i, r in enumerate(top.itertuples(), start=1):
        fecha = r.fecha_publicacion.strftime("%d-%b-%Y") if pd.notna(r.fecha_publicacion) else "—"
        st.markdown(
            f"{i}. **{r.titulo}** — {calc.formatear_numero(r.vistas)} vistas · "
            f"{r.pct_reproducido:.0f}% reproducido · {fecha} · _{r.categoria}_"
        )


def _empresarios_detalle(df: pd.DataFrame):
    with st.expander("🔎 Ver el detalle completo de 'Empresarios / Liderazgo'"):
        st.caption(
            "Cada uno de estos videos representa una entrevista real grabada y editada — producción "
            "significativa para el alcance que logran. Ordenados de mejor a peor."
        )
        sub = df[df["categoria"] == "Empresarios / Liderazgo"].sort_values("vistas", ascending=False)
        for r in sub.itertuples():
            fecha = r.fecha_publicacion.strftime("%d-%b-%Y") if pd.notna(r.fecha_publicacion) else "—"
            dur_min = int(r.duracion_seg) // 60
            st.markdown(f"- **{r.titulo}** — {int(r.vistas)} vistas · {dur_min} min · {fecha}")


def render():
    st.subheader("📺 YouTube — Mercado Media Network")
    df = _cargar()
    if df.empty:
        st.info(f"Sin datos de YouTube todavía. Falta {RUTA_DATOS} — exporta un snapshot de YouTube Studio y "
                "pídele a Claude que lo procese.")
        return

    _aviso_snapshot()
    _kpis(df)
    st.write("")

    with st.container(border=True, key="card_yt_categoria"):
        _por_categoria(df)
    st.write("")

    with st.container(border=True, key="card_yt_shorts"):
        _shorts_vs_largos(df)
    st.write("")

    with st.container(border=True, key="card_yt_top"):
        _top_videos(df)
        _empresarios_detalle(df)

    st.write("")
    st.caption(
        "Pendiente para una próxima vuelta (no incluido en este snapshot): ingresos reales (requiere acceso de "
        "administrador con ingresos, no editor), fuentes de tráfico (búsqueda vs. sugeridos vs. externo), y datos "
        "de todo el histórico del canal por video (este corte es del mes en curso, no de siempre)."
    )
