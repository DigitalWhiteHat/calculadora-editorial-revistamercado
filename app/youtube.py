"""Vista YouTube — canal "Mercado Media Network" (Revista Mercado). Pedido de
Edwin, 17-ago-2026: sección propia de YouTube con ingresos, visitas orgánicas,
fuentes de tráfico, videos más vistos, qué le funciona/qué no, temas fuertes/
débiles, shorts vs. largos. Ajustado el mismo día tras su feedback: la lista
de videos debe ser tabla filtrable (vistas/reproducción/ingresos/categoría),
shorts pasa a ser un filtro más de esa tabla (no una sección aparte), y hace
falta cubrir todo agosto + periodos del resto del año, no solo un mes suelto.

A diferencia del resto de esta app (GA4/GSC vía export automático diario de
Apps Script), YouTube Studio Analytics NO tiene esa API conectada -- esta
vista lee SNAPSHOTS manuales exportados a mano desde YouTube Studio ("Modo
avanzado" -> exportar a Sheets), no se refrescan solos. Para actualizarlos:
en YouTube Studio, Analytics -> Modo avanzado -> filtro "Orgánica" -> exportar
-> pedirle a Claude que regenere data/youtube_*.csv con el nuevo Sheet.

Dos periodos disponibles:
- "Agosto 2026": snapshot mes en curso, 159 videos, 99.9% de las vistas reales
  de agosto (se dejó fuera una cola larga de videos con 1-3 vistas).
- "Histórico": snapshot "Desde el principio" filtrado a orgánica, ordenado por
  tiempo de reproducción -- YouTube Studio tope a 500 filas por video en modo
  avanzado, así que es el Top 500 histórico, no el canal completo. Confirmado
  cruzando el total (10.59M vistas) contra el Sheet de KPIs que Edwin ya
  mantiene a mano -- coincide.

Ingresos: la columna "Ingresos estimados" viene vacía/0 en AMBOS snapshots,
agosto y el histórico completo, incluida la fila "Total" -- se confirmó que no
es un recorte de agosto, es el nivel de acceso de la cuenta conectada (aparece
como "Editor", no "Propietario"/"Administrador con ingresos", el rol que
YouTube exige para mostrar ingresos). Se declara así en la UI, nunca se
inventa un número.

Tendencia mensual: data/youtube_tendencia_mensual.csv son vistas orgánicas a
nivel de CANAL (no por video), tomadas del Sheet de KPIs 2026 que Edwin ya
mantiene ("Youtube Vistas Sin pauta", filas 218-234) -- dato oficial, sirve
para ver el año completo aunque el detalle por video solo cubra agosto/top 500.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
from estilos import kpi_card

RUTA_AGOSTO = "data/youtube_agosto_organico.csv"
RUTA_LIFETIME = "data/youtube_lifetime_organico.csv"
RUTA_TENDENCIA = "data/youtube_tendencia_mensual.csv"
FECHA_SNAPSHOT = "17-ago-2026"

PERIODOS_YT = {
    "agosto": {
        "ruta": RUTA_AGOSTO,
        "label": "Agosto 2026 (mes en curso)",
        "desc": "vistas orgánicas acumuladas en agosto 2026 -- 99.9% de las vistas reales del mes",
    },
    "historico": {
        "ruta": RUTA_LIFETIME,
        "label": "Histórico -- Top 500 por tiempo de reproducción",
        "desc": "vistas orgánicas acumuladas desde el inicio del canal, Top 500 videos por tiempo de "
                "reproducción (YouTube Studio no deja exportar más de 500 filas por video en modo avanzado)",
    },
}

COLOR_CATEGORIA = {
    "Noticias breves (geopolítica/actualidad)": "#3457D5",
    "Empresarios / Liderazgo": "#DC2626",
    "Otros / Institucional": "#94A3B8",
    "Deportes": "#16A34A",
    "Documental (Kathleen Martínez)": "#D97706",
    "Mercado Podcast": "#7C3AED",
}

ORDEN_MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
               "Septiembre", "Octubre", "Noviembre", "Diciembre"]


@st.cache_data
def _cargar(ruta: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(ruta)
    except FileNotFoundError:
        return pd.DataFrame()
    df["fecha_publicacion"] = pd.to_datetime(df["fecha_publicacion"], errors="coerce")
    return df


@st.cache_data
def _cargar_tendencia() -> pd.DataFrame:
    try:
        return pd.read_csv(RUTA_TENDENCIA)
    except FileNotFoundError:
        return pd.DataFrame()


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
        kpi_card("🎬", "Videos en esta vista", f"{len(df)}"),
        kpi_card("💰", "Ingresos estimados", "Sin acceso" if ingresos_total == 0 else calc.formatear_numero(ingresos_total),
                  help_text="YouTube Studio no devuelve ingresos con el nivel de acceso actual (cuenta conectada como "
                             "'Editor', no 'Propietario'/'Administrador con ingresos') -- confirmado tanto en agosto "
                             "como en el histórico completo. No es que sean $0 reales -- es que este acceso no los "
                             "puede ver. Pídele a quien administre el canal que dé acceso de ingresos, o que exporte "
                             "esa pestaña aparte."),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _aviso_snapshot(periodo_key: str):
    info = PERIODOS_YT[periodo_key]
    st.info(
        f"📸 **Esto es un snapshot manual**, no un dato que se actualiza solo como el resto de la app. "
        f"Exportado de YouTube Studio el {FECHA_SNAPSHOT}, canal 'Mercado Media Network', filtrado a "
        f"**{info['desc']}**. Para refrescarlo: YouTube Studio → Analytics → Modo avanzado → filtro "
        f"'Orgánica' → exportar a Google Sheets → pedirle a Claude que regenere los datos con ese Sheet nuevo."
    )


def _tendencia_mensual():
    st.subheader("Vistas orgánicas por mes -- todo 2025 y 2026")
    st.caption(
        "Dato oficial a nivel de canal (no por video), tomado del Sheet de KPIs de Revista Mercado que Edwin ya "
        "mantiene al día cada mes. Cubre todo el año, más allá del periodo elegido arriba."
    )
    df = _cargar_tendencia()
    if df.empty:
        return
    df = df.copy()
    df["orden"] = df.apply(lambda r: (int(r["anio"]), ORDEN_MESES.index(r["mes"])), axis=1)
    df = df.sort_values("orden")
    df["periodo"] = df["mes"].str[:3] + " " + df["anio"].astype(str)

    fig = go.Figure(go.Bar(
        x=df["periodo"], y=df["vistas_sin_pauta"], marker_color="#3457D5",
        text=[calc.formatear_numero(v) for v in df["vistas_sin_pauta"]], textposition="outside",
        hovertemplate="%{x}<br>Vistas: %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=280, margin=dict(l=0, r=0, t=20, b=10),
        xaxis_title=None, yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _por_categoria(df: pd.DataFrame):
    st.subheader("Qué le funciona y qué no -- por tipo de contenido")
    st.caption(
        "Clasificación automática por título/duración (geopolítica y desastres = noticia breve; entrevistas a "
        "líderes/empresarios/liderazgo = Empresarios; Mundial/Clásico/Juegos = Deportes). Puede tener algo "
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
            f'({int(empresarios["videos"].iloc[0])} videos) generan en promedio '
            f'<b>{calc.formatear_numero(vpv_empresarios)} vistas/video</b> — las noticias breves generan '
            f'{ratio:,.0f}× más ({calc.formatear_numero(vpv_noticias)} vistas/video). No es una diferencia menor: '
            f'es la brecha más grande del canal entre volumen de producción e impacto real.</div>',
            unsafe_allow_html=True,
        )


def _tabla_videos(df: pd.DataFrame):
    st.subheader("Catálogo de videos")
    st.caption(
        "Filtra por categoría, formato o palabra clave del título. Los ingresos vienen vacíos para todo el "
        "canal (ver aviso arriba) -- no es que sean $0 reales, es que esta cuenta no puede verlos."
    )

    col_cat, col_formato, col_buscar = st.columns([2, 1, 2])
    with col_cat:
        categorias = sorted(df["categoria"].unique().tolist())
        f_categorias = st.multiselect("Categoría", categorias, default=categorias, key="yt_filtro_categoria")
    with col_formato:
        f_formato = st.selectbox("Formato", ["Todos", "Shorts (≤3 min)", "Largo (>3 min)"], key="yt_filtro_formato")
    with col_buscar:
        buscar = st.text_input("Buscar en el título", placeholder="ej. Irán, Escotet, Barceló...", key="yt_buscar")

    vista = df[df["categoria"].isin(f_categorias)] if f_categorias else df.iloc[0:0]
    if f_formato == "Shorts (≤3 min)":
        vista = vista[vista["es_short"]]
    elif f_formato == "Largo (>3 min)":
        vista = vista[~vista["es_short"]]
    if buscar:
        vista = vista[vista["titulo"].str.contains(buscar, case=False, na=False)]

    vista = vista.sort_values("vistas", ascending=False)
    st.caption(f"{len(vista)} videos · {calc.formatear_numero(vista['vistas'].sum())} vistas combinadas")

    tabla = vista.copy()
    tabla["fecha_txt"] = tabla["fecha_publicacion"].apply(lambda f: f.strftime("%d-%b-%Y") if pd.notna(f) else "—")
    tabla["formato"] = tabla["es_short"].map({True: "Short", False: "Largo"})
    tabla["reproducido_txt"] = tabla["pct_reproducido"].apply(lambda p: f"{p:.0f}%")
    tabla["ingresos_txt"] = tabla["ingresos_usd"].apply(
        lambda v: calc.formatear_numero(v) if pd.notna(v) and v else "Sin acceso")

    columnas = ["titulo", "fecha_txt", "vistas", "reproducido_txt", "ingresos_txt", "categoria", "formato"]
    st.dataframe(
        tabla[columnas], hide_index=True, width="stretch", height=480,
        column_config={
            "titulo": st.column_config.TextColumn("Título", width="large"),
            "fecha_txt": st.column_config.TextColumn("Publicado", width="small"),
            "vistas": st.column_config.NumberColumn("Vistas", width="small", format="%d"),
            "reproducido_txt": st.column_config.TextColumn("% reproducido", width="small"),
            "ingresos_txt": st.column_config.TextColumn("Ingresos", width="small"),
            "categoria": st.column_config.TextColumn("Categoría", width="medium"),
            "formato": st.column_config.TextColumn("Formato", width="small"),
        },
    )


def _empresarios_detalle(df: pd.DataFrame):
    with st.expander("🔎 Ver el detalle completo de 'Empresarios / Liderazgo'"):
        st.caption(
            "Cada uno de estos videos coincide con una palabra clave real de entrevista/liderazgo ejecutivo "
            "(entrevista, CEO, presidente, liderazgo, nombre de la empresa, etc.) -- no se clasifican aquí solo "
            "por ser videos largos. Ordenados de mejor a peor."
        )
        sub = df[df["categoria"] == "Empresarios / Liderazgo"].sort_values("vistas", ascending=False)
        for r in sub.itertuples():
            fecha = r.fecha_publicacion.strftime("%d-%b-%Y") if pd.notna(r.fecha_publicacion) else "—"
            dur_min = int(r.duracion_seg) // 60
            st.markdown(f"- **{r.titulo}** — {int(r.vistas)} vistas · {dur_min} min · {fecha}")


def render():
    st.subheader("📺 YouTube — Mercado Media Network")

    periodo_key = st.radio(
        "Periodo", list(PERIODOS_YT.keys()), format_func=lambda k: PERIODOS_YT[k]["label"],
        horizontal=True, key="yt_periodo",
    )
    df = _cargar(PERIODOS_YT[periodo_key]["ruta"])
    if df.empty:
        st.info(f"Sin datos de YouTube todavía para este periodo. Falta {PERIODOS_YT[periodo_key]['ruta']} -- "
                "exporta un snapshot de YouTube Studio y pídele a Claude que lo procese.")
        return

    _aviso_snapshot(periodo_key)
    _kpis(df)
    st.write("")

    with st.container(border=True, key="card_yt_tendencia"):
        _tendencia_mensual()
    st.write("")

    with st.container(border=True, key="card_yt_categoria"):
        _por_categoria(df)
    st.write("")

    with st.container(border=True, key="card_yt_tabla"):
        _tabla_videos(df)
        _empresarios_detalle(df)

    st.write("")
    st.caption(
        "Pendiente para una próxima vuelta: ingresos reales (requiere acceso de administrador con ingresos, no "
        "editor -- confirmado sin acceso tanto en agosto como en el histórico completo) y fuentes de tráfico "
        "(búsqueda vs. sugeridos vs. externo). El histórico está limitado al Top 500 por tiempo de reproducción "
        "-- tope de exportación de YouTube Studio en modo avanzado, no una elección nuestra."
    )
