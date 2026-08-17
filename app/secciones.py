"""Vista Secciones — panorama 360 de todo el portal: dónde está el tráfico,
no solo las secciones con periodista identificado. Igual que en Colombia.com,
usa 7 periodos acumulados (julio censo + 6 meses histórico) y NO cambia con
el selector de periodo del Dashboard — son herramientas de decisión, no una
foto de un solo mes.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import datos_reales as dr
from estilos import ecuacion_titular_box, kpi_card

COLOR_CON_PERIODISTA = "#16A34A"
COLOR_SIN_PERIODISTA = "#94A3B8"

# A diferencia de Colombia.com (playbooks validados por sección), acá no se
# inventa contexto editorial sin evidencia — LABELS_SECCION/PLAYBOOK_HINT
# quedan vacíos a propósito (ver docstring del módulo).
LABELS_SECCION: dict[str, str] = {}
PLAYBOOK_HINT: dict[str, str] = {}


def _label(seccion_raw: str) -> str:
    return LABELS_SECCION.get(seccion_raw, dr.seccion_label(seccion_raw))


@st.cache_data
def _panorama() -> pd.DataFrame:
    """Todo el tráfico real (con y sin periodista identificado), con la
    bandera de cobertura editorial — base de los KPIs y el gráfico general."""
    agg = dr.secciones_resumen_agregado()
    con_periodista = set(dr.notas_por_seccion_agregado()["seccion_raw"])
    agg = agg.copy()
    agg["con_periodista"] = agg["seccion_raw"].isin(con_periodista)
    agg["label"] = agg["seccion_raw"].apply(_label)
    return agg


def _kpis(df):
    total = df["vistas"].sum()
    con_p = df[df["con_periodista"]]["vistas"].sum()
    tarjetas = [
        kpi_card("🌐", "Tráfico total del portal (secciones con volumen real)", calc.formatear_numero(total)),
        kpi_card("👤", "Con periodista identificado", f"{100*con_p/total:.0f}%" if total else "—",
                  help_text="% del tráfico que cae en secciones/subsecciones donde ya identificamos autor por nota"),
        kpi_card("📊", "Secciones con volumen real", f"{len(df)}",
                  help_text="Tras filtrar páginas de utilidad (tags, checkout, wp-content...) y cola larga sin volumen"),
        kpi_card("🗂️", "Con subsección real detectada", f"{df['seccion_raw'].str.contains('/').sum()}",
                  help_text="Secciones donde la URL revela una subsección concreta (ej. empresas/sport-business) — "
                            "ahí es donde realmente trabajan los periodistas, no en el nombre genérico de arriba"),
    ]
    st.markdown(f'<div class="cp-kpi-row" style="grid-template-columns:repeat(4,1fr)">{"".join(tarjetas)}</div>',
                unsafe_allow_html=True)


def _grafico(df):
    st.subheader("Tráfico por sección/subsección — todo el portal")
    st.caption("🟢 Verde = con periodista identificado en el informe · Gris = tráfico real sin autor "
               "identificado todavía (muestra de mayor tráfico, no censo — ver limitación conocida del proyecto)")
    ordenado = df.sort_values("vistas", ascending=True).tail(35)
    colores = [COLOR_CON_PERIODISTA if c else COLOR_SIN_PERIODISTA for c in ordenado["con_periodista"]]
    textos = [calc.formatear_numero(v) for v in ordenado["vistas"]]
    fig = go.Figure(go.Bar(
        x=ordenado["vistas"], y=ordenado["label"], orientation="h",
        marker_color=colores, text=textos, textposition="outside",
        hovertemplate="%{y}<br>Tráfico: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(400, 24 * len(ordenado)), margin=dict(l=0, r=80, t=10, b=10),
        xaxis_title=None, yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    if len(df) > 35:
        st.caption(f"Mostrando las 35 secciones/subsecciones de mayor tráfico de {len(df)} con volumen real.")


def _tabla(df, df_notas_seccion):
    st.subheader("Detalle por sección")
    vista = df.copy().sort_values("vistas", ascending=False)
    vista["trafico_txt"] = vista["vistas"].apply(calc.formatear_numero)
    vista["cobertura"] = vista["con_periodista"].apply(lambda c: "👤 Con periodista" if c else "📦 Solo agregado")
    vista["dificultad_txt"] = vista["dificultad_categoria"].apply(
        lambda d: {"Fácil": "🟢 Fácil", "Media": "🔵 Media", "Difícil": "🔴 Difícil"}[d])
    vista["canal_txt"] = vista.apply(
        lambda r: f"{r['canal_dominante']} ({r['pct_canal_dominante']:.0f}%)"
        if pd.notna(r["pct_canal_dominante"]) else "—", axis=1)

    conteo = df_notas_seccion.set_index("seccion_raw")["notas"] if not df_notas_seccion.empty else pd.Series(dtype=int)
    vista["notas_txt"] = vista["seccion_raw"].apply(
        lambda s: f"{int(conteo[s])} notas" if s in conteo.index else "—")

    columnas = ["label", "trafico_txt", "dificultad_txt", "canal_txt", "cobertura", "notas_txt"]
    st.dataframe(
        vista[columnas], hide_index=True, width="stretch", height=420,
        column_config={
            "label": st.column_config.TextColumn("Sección", width="medium"),
            "trafico_txt": st.column_config.TextColumn("Tráfico (7 periodos)", width="small"),
            "dificultad_txt": st.column_config.TextColumn("Dificultad", width="small"),
            "canal_txt": st.column_config.TextColumn("Canal dominante", width="small"),
            "cobertura": st.column_config.TextColumn("Cobertura editorial", width="small"),
            "notas_txt": st.column_config.TextColumn("Notas identificadas", width="small"),
        },
    )
    st.caption("Ya se excluyeron páginas de utilidad (tags, checkout, wp-content, etc.) y cola larga sin "
               "volumen real (<1.000 visitas en 7 periodos) — no es tráfico editorial del sitio.")


def _seccion_mes_ligera(periodo):
    """Panorama de UN periodo puntual (no los 7 acumulados) -- para cuando el
    selector de arriba está en un mes histórico o el parcial en curso, en vez
    de julio (censo completo). Portado de calculadora-periodistas/app/secciones.py
    (Colombia.com), adaptado a la columna `seccion_raw` de Revista Mercado."""
    st.subheader(f"Panorama del portal — {dr.PERIODOS[periodo]['label']}")
    st.info(
        "📊 Tráfico y notas reales de este periodo. Las herramientas de abajo (simulador, "
        "especialización, propuesta de redistribución) usan 7 periodos acumulados y no cambian "
        "con el periodo que elijas aquí arriba — son para decidir, no una foto de un solo mes."
    )
    df_mes = dr.secciones_por_periodo(periodo)
    if df_mes.empty:
        st.warning("No hay notas identificadas para este periodo.")
        return
    df_mes = df_mes.copy()
    df_mes["label"] = df_mes["seccion"].apply(_label)

    tarjetas = [
        kpi_card("🌐", "Tráfico total del portal", calc.formatear_numero(df_mes["trafico"].sum())),
        kpi_card("📝", "Notas identificadas", f"{int(df_mes['notas'].sum())}"),
        kpi_card("📊", "Secciones con volumen", f"{len(df_mes)}"),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)
    st.write("")

    with st.container(border=True, key="card_seccion_mes_grafico"):
        st.subheader("Tráfico por sección")
        ordenado = df_mes.sort_values("trafico", ascending=True)
        fig = go.Figure(go.Bar(
            x=ordenado["trafico"], y=ordenado["label"], orientation="h", marker_color="#3457D5",
            text=[calc.formatear_numero(v) for v in ordenado["trafico"]], textposition="outside",
            hovertemplate="%{y}<br>Tráfico: %{x:,.0f}<extra></extra>",
        ))
        fig.update_layout(
            height=max(360, 26 * len(ordenado)), margin=dict(l=0, r=60, t=10, b=10),
            xaxis_title=None, yaxis_title=None, showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
            yaxis=dict(automargin=True),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.write("")
    with st.container(border=True, key="card_seccion_mes_tabla"):
        st.subheader("Detalle por sección")
        vista = df_mes.sort_values("trafico", ascending=False).copy()
        vista["trafico_txt"] = vista["trafico"].apply(calc.formatear_numero)
        st.dataframe(
            vista[["label", "notas", "trafico_txt", "eficiencia"]], hide_index=True, width="stretch",
            column_config={
                "label": st.column_config.TextColumn("Sección", width="medium"),
                "notas": st.column_config.NumberColumn("Notas", width="small"),
                "trafico_txt": st.column_config.TextColumn("Tráfico", width="small"),
                "eficiencia": st.column_config.NumberColumn("Tráfico / nota", format="%.0f", width="small"),
            },
        )


def _herramientas_7meses(tabla_periodistas, esp, df_notas_seccion):
    """Simulador, especialización, simulador de escenarios y propuesta de
    redistribución: SIEMPRE con 7 periodos acumulados, sin importar el periodo
    elegido arriba — son herramientas de decisión, no una foto de un mes."""
    st.write("")
    with st.container(border=True, key="card_eficiencia_seccion"):
        _eficiencia_por_seccion(df_notas_seccion)

    st.write("")
    with st.container(border=True, key="card_simulador"):
        _simulador(df_notas_seccion)

    if not esp.empty:
        st.write("")
        with st.container(border=True, key="card_especializacion"):
            _especializacion_periodistas(esp)

        st.write("")
        with st.container(border=True, key="card_simulador_escenarios"):
            _simulador_escenarios(esp, df_notas_seccion)

    st.write("")
    with st.container(border=True, key="card_propuesta"):
        _propuesta_redistribucion(df_notas_seccion, tabla_periodistas)

    st.write("")
    with st.container(border=True, key="card_titulares_secciones"):
        _titulares_por_seccion()


def _eficiencia_por_seccion(df_notas):
    st.subheader("Cuántas notas produce cada sección — y qué tan bien le rinden")
    st.caption(
        "Esto ya NO depende de quién firmó la nota — cuenta todo artículo real con autor identificado, "
        "acumulado en los 7 periodos (julio censo + ene-jun muestra)."
    )
    vista = df_notas.copy().sort_values("trafico_por_nota", ascending=False).head(25)
    vista["label"] = vista["seccion_raw"].apply(_label)
    vista["trafico_txt"] = vista["trafico"].apply(calc.formatear_numero)
    vista["eficiencia_txt"] = vista["trafico_por_nota"].apply(lambda v: f"{v:,.0f}".replace(",", "."))

    fig = go.Figure(go.Bar(
        x=vista["trafico_por_nota"], y=vista["label"], orientation="h",
        marker_color="#3457D5", text=vista["eficiencia_txt"], textposition="outside",
        hovertemplate="%{y}<br>Tráfico por nota: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(360, 24 * len(vista)), margin=dict(l=0, r=60, t=10, b=10),
        xaxis_title="Tráfico promedio por nota (eficiencia)", yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.dataframe(
        vista[["label", "notas", "trafico_txt", "eficiencia_txt"]], hide_index=True, width="stretch",
        column_config={
            "label": st.column_config.TextColumn("Sección", width="medium"),
            "notas": st.column_config.NumberColumn("Notas publicadas (7 periodos, con autor)", width="small"),
            "trafico_txt": st.column_config.TextColumn("Tráfico total", width="small"),
            "eficiencia_txt": st.column_config.TextColumn("Tráfico / nota", width="small",
                                                            help="A mayor número, menos notas hacen falta para el mismo tráfico"),
        },
    )
    st.caption("Top 25 por eficiencia — de las secciones/subsecciones con al menos 1 nota con autor identificado.")


def _simulador(df_notas):
    st.subheader("Simulador: ¿cuántas notas necesita cada sección?")
    st.caption(
        "Elige una sección y escribe la meta que quieres lograr en los próximos 7 periodos. Con la eficiencia "
        "real acumulada calcula cuántas notas hacen falta para llegar. Esto NO quita recursos de otras "
        "secciones automáticamente — para ver el efecto de mover a alguien específico, usa el simulador de "
        "escenarios más abajo."
    )
    base = df_notas[df_notas["notas"] >= 3].copy()
    base["label"] = base["seccion_raw"].apply(_label)
    if "meta_secciones" not in st.session_state:
        st.session_state["meta_secciones"] = {row["seccion_raw"]: int(row["trafico"]) for _, row in base.iterrows()}

    c_seccion, c_meta = st.columns(2)
    with c_seccion:
        with st.container(border=True, key="card_sim_notas_seccion"):
            seccion_sel = st.selectbox(
                "🗂️ Sección/subsección", base["seccion_raw"].tolist(), format_func=_label,
                key="sim_meta_seccion",
            )
    fila = base[base["seccion_raw"] == seccion_sel].iloc[0]
    with c_meta:
        with st.container(border=True, key="card_sim_notas_meta"):
            meta = st.number_input(
                f"🎯 Meta de tráfico (7 periodos) — {fila['label']}", min_value=0, step=5000,
                value=int(st.session_state["meta_secciones"].get(seccion_sel, fila["trafico"])),
                key=f"meta_input_{seccion_sel}",
            )
    st.session_state["meta_secciones"][seccion_sel] = meta

    notas_necesarias = meta / fila["trafico_por_nota"] if fila["trafico_por_nota"] else 0
    delta = notas_necesarias - fila["notas"]

    def _tarjeta(icono, titulo, valor, bg, fg):
        return (f'<div style="background:{bg};border-radius:12px;padding:14px 16px;height:100%">'
                f'<div style="font-size:0.95rem;color:{fg};font-weight:600;margin-bottom:6px">{icono} {titulo}</div>'
                f'<div style="font-size:1.6rem;font-weight:700;color:{fg}">{valor}</div>'
                f'</div>')

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(_tarjeta("⚡", "Eficiencia (tráfico/nota)", f"{fila['trafico_por_nota']:,.0f}".replace(",", "."),
                              "#EFF6FF", "#1E40AF"), unsafe_allow_html=True)
    with c2:
        st.markdown(_tarjeta("📝", "Notas necesarias (7 periodos)", f"{notas_necesarias:,.0f}".replace(",", "."),
                              "#EFF6FF", "#1E40AF"), unsafe_allow_html=True)
    with c3:
        signo = "+" if delta >= 0 else ""
        bg, fg = ("#FEE2E2", "#991B1B") if delta > 0 else ("#DCFCE7", "#166534")
        st.markdown(_tarjeta("⚖️", "Delta vs. producción actual", f"{signo}{delta:,.1f}".replace(",", "."), bg, fg),
                    unsafe_allow_html=True)


def _especializacion_periodistas(esp):
    st.subheader("Especialización real: dónde le rinde a cada periodista escribir")
    st.caption(
        "Cruce periodista × sección con los 7 periodos de datos reales. Confianza según volumen de muestra: "
        "🟢 alta (≥10 notas) · 🟡 media (3-9) · ⚪ baja (<3, solo indicativo)."
    )
    icono_conf = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
    for autor in sorted(esp["autor"].unique()):
        sub = esp[esp["autor"] == autor].sort_values("trafico_por_nota", ascending=False)
        mejor, peor = sub.iloc[0], sub.iloc[-1]
        with st.expander(f"{autor} — {len(sub)} sección(es) trabajada(s) en 7 periodos"):
            vista = sub.copy()
            vista["label"] = vista["seccion"].apply(_label)
            vista["icono"] = vista["confianza"].map(icono_conf)
            st.dataframe(
                vista[["label", "notas", "trafico_por_nota", "icono"]],
                hide_index=True, width="stretch",
                column_config={
                    "label": st.column_config.TextColumn("Sección", width="small"),
                    "notas": st.column_config.NumberColumn("Notas (7 periodos)", width="small"),
                    "trafico_por_nota": st.column_config.NumberColumn("Tráfico/nota", format="%.0f", width="small"),
                    "icono": st.column_config.TextColumn("Confianza", width="small"),
                },
            )
            if len(sub) > 1:
                st.markdown(f"🟢 **Mejor rendimiento: {_label(mejor['seccion'])}** "
                            f"— {mejor['trafico_por_nota']:,.0f} tráfico/nota".replace(",", "."))
                st.markdown(f"🔴 **Más débil: {_label(peor['seccion'])}** "
                            f"— {peor['trafico_por_nota']:,.0f} tráfico/nota".replace(",", "."))
            hint = PLAYBOOK_HINT.get(mejor["seccion"])
            if hint:
                st.info(f"📌 Contexto de **{_label(mejor['seccion'])}**: {hint}")


def _simulador_escenarios(esp, df_notas):
    st.subheader("Simulador: ¿qué pasa si muevo a un periodista de sección?")
    st.caption(
        "Elige un periodista y una sección destino. Si ya escribió ahí, usa su propio rendimiento (confianza "
        "alta, con hasta 7 periodos de historia); si no, la eficiencia real de esa sección con todo el "
        "contenido (confianza media); si nadie lo ha intentado, un estimado conservador (confianza baja — "
        "\"sin precedente\"). La pérdida se ve de inmediato; la ganancia tarda en madurar — tómalo como orden "
        "de magnitud, no como cifra exacta."
    )

    periodistas = sorted(esp["autor"].unique())
    c_per, c_deja, c_destino, c_notas = st.columns(4)
    with c_per:
        with st.container(border=True, key="card_sim_periodista"):
            periodista_sel = st.selectbox("👤 Periodista", periodistas, key="sim_periodista")

    secciones_periodista = esp[esp["autor"] == periodista_sel].sort_values("notas", ascending=False)
    with c_deja:
        with st.container(border=True, key="card_sim_origen"):
            seccion_origen = st.selectbox(
                "📉 Sección que reduce/deja", secciones_periodista["seccion"].tolist(),
                format_func=_label, key="sim_origen",
            )

    todas_secciones = sorted(df_notas["seccion_raw"].unique())
    opciones_destino = [s for s in todas_secciones if s != seccion_origen]
    with c_destino:
        with st.container(border=True, key="card_sim_destino"):
            seccion_destino = st.selectbox(
                "📈 Sección destino", opciones_destino, format_func=_label, key="sim_destino",
            )
    fila_origen = secciones_periodista[secciones_periodista["seccion"] == seccion_origen].iloc[0]
    notas_base = max(1, int(fila_origen["notas"]))
    with c_notas:
        with st.container(border=True, key="card_sim_notas"):
            notas_a_mover = st.number_input(
                "🔢 Notas a mover (7 periodos)", min_value=1, max_value=max(200, notas_base * 3),
                value=notas_base, key="sim_notas",
                help=f"Historial real de {periodista_sel} en esta sección: {notas_base} notas en 7 periodos.",
            )

    eficiencia_origen = float(fila_origen["trafico_por_nota"])
    trafico_perdido = notas_a_mover * eficiencia_origen

    fila_destino_propia = esp[(esp["autor"] == periodista_sel) & (esp["seccion"] == seccion_destino)]
    fila_destino_seccion = df_notas[df_notas["seccion_raw"] == seccion_destino]
    mediana_portal = df_notas["trafico_por_nota"].median()

    if not fila_destino_propia.empty:
        eficiencia_destino = float(fila_destino_propia.iloc[0]["trafico_por_nota"])
        confianza_destino = "alta"
        fuente_destino = f"rendimiento propio de {periodista_sel} en esta sección"
    elif not fila_destino_seccion.empty:
        eficiencia_destino = float(fila_destino_seccion.iloc[0]["trafico_por_nota"])
        confianza_destino = "media"
        fuente_destino = "eficiencia real de la sección (todo el contenido, no solo este periodista)"
    else:
        eficiencia_destino = mediana_portal * 0.7
        confianza_destino = "baja"
        fuente_destino = "sin datos de esa sección — estimado conservador (70% de la mediana del portal)"

    trafico_ganado = notas_a_mover * eficiencia_destino
    neto = trafico_ganado - trafico_perdido
    icono = {"alta": "🟢", "media": "🟡", "baja": "⚪"}.get(confianza_destino)

    def _resultado_card(icono_r, titulo, valor, bg, fg):
        return (f'<div style="background:{bg};border-radius:12px;padding:16px 18px;height:100%">'
                f'<div style="font-size:1.05rem;color:{fg};font-weight:600;margin-bottom:8px">{icono_r} {titulo}</div>'
                f'<div style="font-size:1.9rem;font-weight:700;color:{fg}">{valor}</div>'
                f'</div>')

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(_resultado_card(
            "🔻", f"Pierde en {_label(seccion_origen)} (inmediato)",
            f"-{calc.formatear_numero(trafico_perdido)}", "#FEE2E2", "#991B1B",
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(_resultado_card(
            icono, f"Gana en {_label(seccion_destino)} (una vez madure)",
            f"+{calc.formatear_numero(trafico_ganado)}", "#DCFCE7", "#166534",
        ), unsafe_allow_html=True)
    with c3:
        signo = "+" if neto >= 0 else ""
        bg_neto, fg_neto = ("#DCFCE7", "#166534") if neto >= 0 else ("#FEE2E2", "#991B1B")
        st.markdown(_resultado_card(
            "📊", "Neto proyectado", f"{signo}{calc.formatear_numero(neto)}", bg_neto, fg_neto,
        ), unsafe_allow_html=True)

    st.write("")
    st.caption(f"Ganancia estimada con: {fuente_destino}.")

    if eficiencia_destino < mediana_portal * 0.3:
        st.warning(
            f"⚠️ {_label(seccion_destino)} rinde muy por debajo de la mediana del portal — el techo puede ser "
            "estructural del tema, no de quién escribe. Revisar ángulo editorial antes de mover recursos aquí.")
    if neto < 0:
        st.error("Con estos supuestos el movimiento pierde tráfico neto. Prueba otra sección destino o "
                  "revisa si el volumen de notas movido es razonable.")


def _propuesta_redistribucion(df_notas, tabla_periodistas):
    st.subheader("Propuesta de redistribución editorial")
    st.caption(
        "Cruce de eficiencia por sección + cuántos periodistas están asignados hoy (por su sección dominante "
        "del periodo elegido arriba). Punto de partida con datos — la decisión final es editorial."
    )
    activos = tabla_periodistas.groupby("seccion_raw").agg(
        periodistas=("periodista", lambda s: ", ".join(s)),
        n_periodistas=("periodista", "count"),
    ).reset_index()

    df = df_notas.merge(activos, on="seccion_raw", how="left")
    df["n_periodistas"] = df["n_periodistas"].fillna(0).astype(int)
    df["periodistas"] = df["periodistas"].fillna("— ninguno asignado como principal este periodo")
    df["label"] = df["seccion_raw"].apply(_label)

    mediana_eficiencia = df["trafico_por_nota"].median()
    subrecursos = df[(df["trafico_por_nota"] > mediana_eficiencia) & (df["n_periodistas"] <= 1)].sort_values(
        "trafico_por_nota", ascending=False)
    sobrerecursos = df[(df["trafico_por_nota"] < mediana_eficiencia) & (df["n_periodistas"] >= 2)].sort_values(
        "trafico_por_nota")

    col_sub, col_sobre = st.columns(2)
    with col_sub:
        st.markdown("**🟢 Candidatas a reforzar** (alta eficiencia, poco recurso asignado)")
        if subrecursos.empty:
            st.caption("Ninguna sección cumple ambas condiciones en estos 7 periodos.")
        for _, r in subrecursos.head(4).iterrows():
            eficiencia_txt = f"{r['trafico_por_nota']:,.0f}".replace(",", ".")
            st.markdown(f"- **{r['label']}** — {eficiencia_txt} tráfico/nota, "
                        f"{r['n_periodistas']} periodista(s) principal(es)")
    with col_sobre:
        st.markdown("**🔴 Candidatas a reducir** (baja eficiencia, varios recursos asignados)")
        if sobrerecursos.empty:
            st.caption("Ninguna sección cumple ambas condiciones en estos 7 periodos.")
        for _, r in sobrerecursos.head(4).iterrows():
            eficiencia_txt = f"{r['trafico_por_nota']:,.0f}".replace(",", ".")
            st.markdown(f"- **{r['label']}** — {eficiencia_txt} tráfico/nota, "
                        f"{r['n_periodistas']} periodista(s) principal(es)")

    st.write("")
    vista = df[df["notas"] >= 3][["label", "trafico_por_nota", "n_periodistas", "periodistas"]].sort_values(
        "trafico_por_nota", ascending=False)
    st.dataframe(
        vista, hide_index=True, width="stretch",
        column_config={
            "label": st.column_config.TextColumn("Sección", width="small"),
            "trafico_por_nota": st.column_config.NumberColumn("Eficiencia (tráfico/nota)", format="%.0f", width="small"),
            "n_periodistas": st.column_config.NumberColumn("Periodistas asignados hoy", width="small"),
            "periodistas": st.column_config.TextColumn("Quiénes (sección dominante)", width="large"),
        },
    )


def _titulares_por_seccion():
    """Qué ecuación de titular le sirve a cada sección -- portado de
    calculadora-periodistas/app/secciones.py (Colombia.com). Mismo motor que la ecuación de
    portada del Dashboard y la de cada periodista, acá agrupado por sección -- todo el
    histórico real disponible (no un solo periodo), mismo criterio que el resto de esta
    pestaña para tener muestra suficiente."""
    st.subheader("🧮 Qué ecuación de titular le sirve a cada sección")
    secciones_disp = dr.secciones_con_titulares_real()
    if not secciones_disp:
        st.caption("Sin secciones con muestra suficiente (≥10 notas con título) todavía.")
        return
    opciones = [_label(s) for s in secciones_disp]
    mapa_label_a_slug = dict(zip(opciones, secciones_disp))
    seleccion = st.selectbox("🗂️ Sección", opciones, key="seccion_titulares_sel")
    seccion_sel = mapa_label_a_slug[seleccion]
    st.caption(
        "Minado en automático sobre títulos y tráfico reales, con todo el histórico disponible "
        "(no un solo periodo, para tener muestra suficiente). \"Con vs. sin\" compara el tráfico "
        "promedio de los títulos que tienen ese rasgo contra los que no."
    )

    rasgos = dr.patrones_titulares_por_seccion(seccion_sel)
    if rasgos.empty:
        st.caption(f"Sin rasgos con muestra suficiente (mínimo 3 notas con y sin cada rasgo) en {seleccion}.")
        return
    ecuacion = dr.sintetizar_ecuacion_titular(rasgos)
    if ecuacion:
        ejemplo = dr.ejemplo_titular_por_seccion(seccion_sel, rasgos)
        st.markdown(
            ecuacion_titular_box(f"Ecuación de titular -- {seleccion}", ecuacion, ejemplo),
            unsafe_allow_html=True,
        )
        st.caption(
            "Calculada en automático (mismo motor que la ecuación de portada y por periodista) "
            "tomando las piezas con más lift a favor y en contra en esta sección."
        )
        st.write("")
    else:
        st.caption(
            f"Ninguna pieza de la ecuación tiene lift suficiente todavía en {seleccion} para "
            "armar una ecuación con confianza."
        )


def render(tabla_periodistas, periodo=None):
    periodo = periodo or dr.PERIODO_DEFAULT
    df_notas_seccion = dr.notas_por_seccion_agregado()
    esp = dr.especializacion_todos()

    if not dr.es_periodo_completo(periodo):
        _seccion_mes_ligera(periodo)
        _herramientas_7meses(tabla_periodistas, esp, df_notas_seccion)
        return

    df_panorama = _panorama()
    st.subheader("Panorama del portal — 7 periodos (jul-2026 censo + histórico ene-jun)")
    st.caption("No solo lo que tiene periodista asignado: así se reparte TODO el tráfico real, incluidas las "
               "subsecciones — que es donde de verdad trabajan los periodistas de Revista Mercado, no en la "
               "categoría genérica de arriba.")
    _kpis(df_panorama)
    st.write("")
    with st.container(border=True, key="card_secciones_grafico"):
        _grafico(df_panorama)
    st.write("")
    with st.container(border=True, key="card_secciones_tabla"):
        _tabla(df_panorama, df_notas_seccion)

    _herramientas_7meses(tabla_periodistas, esp, df_notas_seccion)
