"""Vista general — desempeño editorial de todo el equipo."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import datos_reales as dr
from avatares import avatar_data_uri
from estilos import BG_ESTADO, TXT_ESTADO, delta_html, ecuacion_titular_box, kpi_card
from graficos import agregar_proyeccion, texto_metodologia_proyeccion
from google_updates import UPDATES_2026

COLOR_ESTADO = {"green": "#16A34A", "blue": "#3457D5", "red": "#DC2626"}
ESTADO_STYLE = {
    label: f"background-color:{BG_ESTADO[key]};color:{TXT_ESTADO[key]};font-weight:600;border-radius:6px"
    for label, key in [("SOBRE MEDIANA", "green"), ("EN RANGO", "blue"), ("EN ALERTA", "red")]
}


def _kpis(tabla, periodo):
    notas_total = tabla["notas"].sum()
    # BUG real encontrado 29-ago-2026 (Edwin, comparando contra Looker Studio/GA4
    # real: "ese número no es real"): tabla["clics"].sum() solo suma el tráfico de
    # notas con AUTOR IDENTIFICADO -- deja fuera todo lo que el sitio publica sin
    # que el scraper de autoría lo haya podido atribuir todavía (sindicado, autor
    # genérico, rutas que no calzan con el patrón de artículo). Para "tráfico
    # total" del portal (no "tráfico atribuido a periodistas conocidos") hay que
    # usar la misma fuente real ya validada en _tendencia_portal() -- suma diaria
    # directa de GA4, sin prorratear -- no la tabla de periodistas.
    por_periodo_kpi = dr.trafico_total_por_periodo()
    fila_periodo = por_periodo_kpi[por_periodo_kpi["periodo"] == periodo]
    # BUG real encontrado 29-ago-2026 (Edwin, contra el mismo Looker Studio: "el
    # tema del tráfico es Visitas, revisa ese informe"): esta tarjeta seguía
    # mostrando "trafico" (páginas vistas) mientras que _tendencia_portal(), un
    # poco más abajo en la MISMA pantalla, ya graficaba "sesiones" (visitas) para
    # el mes en curso desde el 17-ago -- dos cifras distintas de "tráfico total"
    # en la misma vista. Se unifica: la tarjeta usa sesiones (Visitas GA4 real)
    # cuando existen (mes en curso), igual que el gráfico de abajo.
    tiene_sesiones = not fila_periodo.empty and pd.notna(fila_periodo["sesiones"].iloc[0])
    if tiene_sesiones:
        trafico_total = float(fila_periodo["sesiones"].iloc[0])
        etiqueta_trafico = "Visitas"
        ayuda_trafico = (
            "Visitas reales (sesiones GA4) de TODO el portal para este periodo -- no solo lo "
            "atribuido a periodistas conocidos, mismo criterio 'Visitas' de Looker Studio/GA4. "
            "OJO: el export diario que alimenta esta cifra tiene un límite de cobertura medido "
            "entre 80% y 96% según el mes (no ve el 100% de páginas/días de baja audiencia), así "
            "que puede quedar por debajo del total exacto de Looker Studio -- para el número "
            "oficial exacto, revisar el Dashboard de Looker Studio directamente."
        )
    elif not fila_periodo.empty:
        trafico_total = float(fila_periodo["trafico"].iloc[0])
        etiqueta_trafico = "Tráfico total"
        ayuda_trafico = ("Páginas vistas reales de todo el portal (GA4) para este periodo histórico -- "
                          "no se conservaron sesiones para meses ya cerrados, solo páginas vistas.")
    else:
        trafico_total = tabla["clics"].sum()
        etiqueta_trafico = "Tráfico total"
        ayuda_trafico = "Suma de clics atribuidos a periodistas con autor identificado en este periodo."
    eficiencia_prom = tabla["eficiencia_normalizada"].mean()
    en_alerta = int(tabla["en_alerta"].sum())

    tarjetas = [
        kpi_card("👥", "Periodistas activos", f"{len(tabla)}"),
        kpi_card("⚠️", "En alerta", f"{en_alerta}", help_text="Periodistas con al menos una alerta CRÍTICA de "
                  "estado actual (SEO, canibalización, CTR o eficiencia). Ver pestaña Alertas para el detalle."),
        kpi_card("📈", "Eficiencia promedio", f"{eficiencia_prom:.0f}",
                  help_text="Índice comparativo, no un porcentaje ni un conteo: 100 = mediana del equipo. "
                  "Tráfico ajustado por dificultad de sección, relativo al resto del equipo."),
        kpi_card("📝", "Notas totales", f"{notas_total:.0f}"),
        kpi_card("🔎", etiqueta_trafico, calc.formatear_numero(trafico_total), help_text=ayuda_trafico),
        kpi_card("🚩", "Flags de revisión IA", "—", help_text="Aún no se ha corrido la auditoría de originalidad sobre este periodo"),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _tendencia_portal():
    por_periodo = dr.trafico_total_por_periodo()
    # Título dinámico -- bug real encontrado 29-ago-2026 (Edwin: "el título está
    # mal"): quedó fijo en "7 periodos (jul-2026 censo...)" desde antes de que
    # existiera el tier parcial de agosto, y nunca se actualizó al agregarlo --
    # ahora se arma solo a partir de los periodos que la serie realmente trae.
    n_periodos = len(por_periodo)
    ultimo_label = por_periodo["mes_label"].iloc[-1] if n_periodos else ""
    st.subheader(f"Tendencia del portal — {n_periodos} periodos (hasta {ultimo_label})")

    # El mes parcial grafica SESIONES (visitas GA4 reales, la cifra 1:1 contra
    # "Visitas" de Looker Studio/GA4) -- los periodos cerrados solo tienen
    # páginas vistas guardadas (no se conservó sesiones en su momento). Mezclar
    # ambas métricas en la MISMA línea sin decirlo confundió a Edwin (17-ago-
    # 2026: "me sigues diciendo que hay 387.000 visitas cuando no es cierto")
    # -- el número que se grafica y el que se cruza contra su reporte real
    # ahora son el MISMO, no dos cifras distintas en la misma pantalla.
    por_periodo["valor_grafico"] = por_periodo["trafico"]
    usa_sesiones = bool(dr.MES_PARCIAL) and pd.notna(
        por_periodo.loc[por_periodo["periodo"] == dr.MES_PARCIAL, "sesiones"]).any()
    labels_x = por_periodo["mes_label"].tolist()
    if usa_sesiones:
        por_periodo.loc[por_periodo["periodo"] == dr.MES_PARCIAL, "valor_grafico"] = \
            por_periodo.loc[por_periodo["periodo"] == dr.MES_PARCIAL, "sesiones"]
        labels_x[-1] = f"{labels_x[-1]} · visitas"  # el mes en curso es el último por construcción

    st.caption(
        "Tráfico TOTAL real reportado por GA4 cada periodo (todo el portal, sin filtrar por clasificación de "
        "artículo) — no cambia con el selector de periodo de arriba. Los periodos cerrados (líneas sólidas "
        "ene-jul) son **páginas vistas**; el mes en curso es **visitas (sesiones GA4)** — mismo criterio "
        "'Visitas' de Looker Studio/GA4, marcada '· visitas' en el eje. **OJO:** por un límite de cobertura "
        "del export diario (mide entre 80% y 96% según el mes, no ve el 100% de páginas/días de baja "
        "audiencia), esta cifra puede quedar por debajo del total exacto de Looker Studio -- es un piso "
        "real, no una cifra inventada, pero no sustituye el número oficial de Looker Studio. Los puntos "
        "rojos son periodos con un update de Google conocido."
    )

    updates_por_periodo: dict[str, list[dict]] = {}
    for u in UPDATES_2026:
        if u["inicio"].year == 2026 and 1 <= u["inicio"].month <= 7:
            mes_str = f"2026-{u['inicio'].month:02d}"
            updates_por_periodo.setdefault(mes_str, []).append(u)

    fig = go.Figure(go.Scatter(
        x=labels_x, y=por_periodo["valor_grafico"], mode="lines+markers+text",
        line=dict(color="#3457D5", width=3), marker=dict(size=9, color="#3457D5"),
        text=[calc.formatear_numero(v) for v in por_periodo["valor_grafico"]], textposition="top center",
        hovertemplate="%{x}<br>Tráfico: %{y:,.0f}<extra></extra>",
    ))

    con_update = por_periodo[por_periodo["periodo"].isin(updates_por_periodo)]
    if not con_update.empty:
        hover_txt = [" · ".join(u["nombre"] for u in updates_por_periodo[p]) for p in con_update["periodo"]]
        fig.add_trace(go.Scatter(
            x=con_update["mes_label"], y=con_update["valor_grafico"], mode="markers",
            marker=dict(size=15, color="#DC2626", symbol="diamond", line=dict(width=2, color="white")),
            hovertext=hover_txt, hovertemplate="%{x}<br>%{hovertext}<extra></extra>", showlegend=False,
        ))
        for p, r in zip(con_update["periodo"], con_update.itertuples()):
            tipos = " + ".join(sorted({u["tipo"] for u in updates_por_periodo[p]}))
            fig.add_annotation(
                x=r.mes_label, y=r.valor_grafico, text=tipos, showarrow=True, arrowhead=0, arrowcolor="#DC2626",
                ax=0, ay=-38, font=dict(size=10, color="#DC2626"),
                bgcolor="rgba(255,255,255,0.92)", bordercolor="#DC2626", borderwidth=1, borderpad=3,
            )

    proyeccion = dr.proyeccion_fin_de_mes(por_periodo, "valor_grafico", col_mes="periodo")
    if proyeccion:
        label_actual = labels_x[-1]
        label_proy = f"{label_actual} (proy.)"
        agregar_proyeccion(fig, proyeccion, x_actual=label_actual, x_proyectado=label_proy)

    fig.update_layout(
        height=380, margin=dict(l=0, r=10, t=50, b=10),
        yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(showgrid=True, gridcolor="#E2E6ED", rangemode="tozero"),
        xaxis=dict(showgrid=False),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    if proyeccion:
        st.caption(texto_metodologia_proyeccion(proyeccion))


def _aporte_trafico(tabla):
    st.subheader("Aporte de tráfico por periodista")
    ordenado = tabla.sort_values("clics", ascending=True)
    colores = [COLOR_ESTADO[calc.estado_label(r.eficiencia_normalizada, r.en_alerta)[1]] for r in ordenado.itertuples()]
    textos = [f"{calc.formatear_numero(v)} · {p:.1f}%" for v, p in zip(ordenado["clics"], ordenado["pct_trafico_total"])]

    fig = go.Figure(go.Bar(
        x=ordenado["clics"], y=ordenado["periodista"], orientation="h",
        marker_color=colores, text=textos, textposition="outside",
        hovertemplate="%{y}<br>Tráfico: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(280, 34 * len(ordenado)), margin=dict(l=0, r=60, t=10, b=10),
        xaxis_title=None, yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(f"Tráfico total del periodo: **{calc.formatear_numero(tabla['clics'].sum())}**")


def _notas_por_periodista(tabla):
    st.subheader("Notas publicadas por periodista")
    st.caption("Cuántas notas hizo cada quien en el periodo — dato bruto, sin ajustar.")
    ordenado = tabla.sort_values("notas", ascending=True)
    colores = [COLOR_ESTADO[calc.estado_label(r.eficiencia_normalizada, r.en_alerta)[1]] for r in ordenado.itertuples()]

    fig = go.Figure(go.Bar(
        x=ordenado["notas"], y=ordenado["periodista"], orientation="h",
        marker_color=colores, text=ordenado["notas"].astype(int).astype(str), textposition="outside",
        hovertemplate="%{y}<br>Notas: %{x}<extra></extra>",
    ))
    fig.update_layout(
        height=max(280, 34 * len(ordenado)), margin=dict(l=0, r=40, t=10, b=10),
        xaxis_title=None, yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(f"Notas totales del periodo: **{int(tabla['notas'].sum())}**")


def _cuadrante(tabla):
    st.subheader("Volumen de notas vs. eficiencia normalizada")
    st.caption("Cada punto representa a un periodista. Haz clic en un punto para ver su perfil.")

    x = tabla["notas"].to_numpy(dtype=float)
    y = tabla["eficiencia_normalizada"].to_numpy(dtype=float)
    x_mid = float(np.median(x))
    y_mid = 100.0

    # Equipos reales muy desiguales (2-3 de alto volumen/eficiencia vs. muchos
    # colaboradores ocasionales de 1-5 notas) hacen que el máximo bruto dispare
    # el rango del eje y aplaste a todo el resto del equipo contra el borde —
    # visualmente roto, no solo "apretado". En vez de usar el máximo real,
    # el techo del eje se calcula sobre el percentil 75 (la mayoría del
    # equipo) y los pocos puntos que superen ese techo se PINTAN ahí mismo
    # (ancla visual, no se pierden ni se inventan): su cifra real sigue en el
    # hover y en la tabla de abajo, nunca se oculta el dato.
    x_p75 = float(np.percentile(x, 75)) if len(x) else 0.0
    y_p75 = float(np.percentile(y, 75)) if len(y) else 0.0
    x_cap = max(x_p75 * 5, x_mid * 2, 20.0)
    y_cap = max(y_p75 * 5, 300.0)
    x_plot = np.clip(x, None, x_cap)
    y_plot = np.clip(y, None, y_cap)
    hay_recortados = bool((x > x_cap).any() or (y > y_cap).any())

    x_range = (0, x_cap * 1.1)
    y_range = (0, y_cap * 1.1)

    fig = go.Figure()
    zonas = [
        (x_range[0], x_mid, y_mid, y_range[1], "#FEF3C7"),
        (x_mid, x_range[1], y_mid, y_range[1], "#DCFCE7"),
        (x_range[0], x_mid, y_range[0], y_mid, "#F1F5F9"),
        (x_mid, x_range[1], y_range[0], y_mid, "#FEE2E2"),
    ]
    for x0, x1, y0, y1, color in zonas:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=color, opacity=0.5, line_width=0, layer="below")

    # Las etiquetas de zona van ancladas a las ESQUINAS del gráfico (coordenadas
    # de dominio 0-1), no a los valores de datos: con un equipo real tan
    # desigual (unos pocos periodistas de alto volumen vs. muchos de 1-5 notas),
    # x_mid/y_mid quedan muy cerca de los bordes y el texto centrado en el
    # valor de datos se sale del gráfico o choca con los ejes. Anclado a la
    # esquina, el rótulo siempre queda legible sin importar qué tan parejo o
    # desigual esté el equipo ese mes.
    # Textos cortos a propósito (no "ALTA EFICIENCIA · BAJO VOLUMEN Y ...largo"):
    # con la columna angosta del layout de 2 columnas, etiquetas largas en la
    # misma fila (arriba-izq. y arriba-der.) chocan entre sí mucho antes de
    # llegar a los bordes del gráfico. El eje X/Y y el texto explicativo de
    # arriba ya dicen qué es volumen y qué es eficiencia — la etiqueta de
    # esquina solo necesita ubicar el cuadrante, no repetirlo todo.
    etiquetas_esquina = [
        (0.02, 0.97, "left", "top", "Alta eficiencia"),
        (0.98, 0.97, "right", "top", "Zona ideal"),
        (0.02, 0.03, "left", "bottom", "Bajo rendimiento"),
        (0.98, 0.03, "right", "bottom", "Alto volumen, bajo impacto"),
    ]
    for xe, ye, xanchor, yanchor, label in etiquetas_esquina:
        fig.add_annotation(x=xe, y=ye, xref="x domain", yref="y domain", text=label, showarrow=False,
                            font=dict(size=9, color="#64748B"), xanchor=xanchor, yanchor=yanchor)

    fig.add_shape(type="line", x0=x_mid, x1=x_mid, y0=y_range[0], y1=y_range[1], line=dict(color="#94A3B8", dash="dash", width=1))
    fig.add_shape(type="line", x0=x_range[0], x1=x_range[1], y0=y_mid, y1=y_mid, line=dict(color="#94A3B8", dash="dash", width=1))

    colores = [COLOR_ESTADO[calc.estado_label(r.eficiencia_normalizada, r.en_alerta)[1]] for r in tabla.itertuples()]
    # Lista de listas (no np.stack): mezcla slug (str) con notas/eficiencia
    # (float) — un ndarray homogéneo forzaría todo a texto y rompería el
    # formato ":.0f" del hovertemplate.
    customdata = [[slug, xi, yi] for slug, xi, yi in zip(tabla["slug"], x, y)]
    fig.add_trace(go.Scatter(
        x=x_plot, y=y_plot, mode="markers", marker=dict(size=34, color=colores, line=dict(width=2, color="white")),
        customdata=customdata, text=tabla["periodista"],
        hovertemplate="%{text}<br>Notas: %{customdata[1]}<br>Eficiencia: %{customdata[2]:.0f}<extra></extra>",
    ))

    sizex = (x_range[1] - x_range[0]) * 0.055
    sizey = (y_range[1] - y_range[0]) * 0.11
    for r, xp, yp in zip(tabla.itertuples(), x_plot, y_plot):
        fig.add_layout_image(dict(
            source=avatar_data_uri(r.periodista, "#334155", 96), xref="x", yref="y",
            x=xp, y=yp, sizex=sizex, sizey=sizey,
            xanchor="center", yanchor="middle", layer="above",
        ))

    fig.update_layout(
        height=440, margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="Volumen de notas publicadas (periodo)", range=x_range, showgrid=True, gridcolor="#E2E6ED"),
        yaxis=dict(title="Eficiencia normalizada (índice)", range=y_range, showgrid=True, gridcolor="#E2E6ED"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
    )

    # Key con firma del contenido (no un string fijo): Streamlit/Plotly puede
    # persistir el zoom/rango del cliente entre reruns bajo la misma key —
    # con datos tan distintos entre periodos (un mes puede necesitar recorte
    # y julio no), un zoom viejo pegado al cambiar de periodo vuelve a romper
    # visualmente el gráfico aunque el rango recién calculado sea correcto.
    firma = f"{len(tabla)}_{int(x_cap)}_{int(y_cap)}"
    event = st.plotly_chart(fig, width="stretch", on_select="rerun", selection_mode="points",
                             key=f"cuadrante_scatter_{firma}", config={"displayModeBar": False})
    if hay_recortados:
        st.caption("📌 Uno o más periodistas con volumen o eficiencia muy por encima del resto del equipo se "
                   "muestran anclados al borde del gráfico (si no, aplastarían al resto contra el eje) — su "
                   "cifra real está en el hover y en la tabla de abajo, nunca se oculta ni se inventa.")
    puntos = event.get("selection", {}).get("points", []) if event else []
    if puntos:
        idx = puntos[0].get("point_index")
        if idx is not None and 0 <= idx < len(tabla):
            return tabla.iloc[idx]["slug"]
    return None


def _selector_perfil(tabla):
    orden = tabla.sort_values("clics", ascending=False)
    col_txt, col_sel, col_btn = st.columns([2, 2, 1])
    col_txt.subheader("Detalle por periodista")
    nombre = col_sel.selectbox("Ver perfil de periodista", orden["periodista"], label_visibility="collapsed")
    if col_btn.button("Ver perfil →", width="stretch"):
        return orden.loc[orden["periodista"] == nombre, "slug"].iloc[0]
    return None


def _tabla_principal(tabla):
    st.caption("O haz clic en una fila de la tabla / un punto del cuadrante para ver su perfil.")
    st.caption(
        "**Semáforo SEO** = % promedio de cumplimiento del checklist de 14 ítems automatizados "
        "(título, meta descripción, estructura, enlaces internos, imagen, etc.) sobre las notas evaluadas "
        "de cada periodista: 🟢 80% o más · 🟡 entre 60% y 79% · 🔴 menos de 60%. "
        "Haz clic en un periodista y baja a \"¿En qué está fallando el SEO?\" para ver el desglose ítem por ítem."
    )
    vista = tabla.copy().sort_values("clics", ascending=False).reset_index(drop=True)
    vista["foto"] = [avatar_data_uri(n, "#334155", 64) for n in vista["periodista"]]
    vista["seccion_beat"] = vista["seccion"] + " · " + vista["beat"]
    vista["eficiencia_delta"] = vista.apply(
        lambda r: calc.formatear_delta_pct(r["eficiencia_normalizada"], r["eficiencia_normalizada_anterior"]) or "—",
        axis=1)
    vista["notas_dificultad"] = vista.apply(
        lambda r: f"{int(r.notas_facil)}F · {int(r.notas_media)}M · {int(r.notas_dificil)}D", axis=1)
    vista["engagement"] = vista["tiempo_pagina_seg"].apply(calc.formatear_tiempo)
    vista["semaforo"] = vista["pct_cumplimiento_prom"].apply(
        lambda v: "⚪ s/e" if pd.isna(v) else f"{'🟢' if v >= 80 else '🟡' if v >= 60 else '🔴'} {v:.0f}%")
    vista["estado_txt"] = vista.apply(lambda r: calc.estado_label(r["eficiencia_normalizada"], r["en_alerta"])[0], axis=1)
    vista["trafico_txt"] = vista["clics"].apply(calc.formatear_numero)
    vista["pct_trafico_txt"] = vista["pct_trafico_total"].apply(lambda v: f"{v:.1f}%")

    columnas = ["foto", "periodista", "seccion_beat", "notas", "eficiencia_normalizada", "eficiencia_delta",
                "trafico_txt", "pct_trafico_txt", "canal_dominante", "notas_dificultad", "engagement",
                "semaforo", "flags_ia", "estado_txt"]
    styled = vista[columnas].style.map(lambda v: ESTADO_STYLE.get(v, ""), subset=["estado_txt"])
    event = st.dataframe(
        styled, hide_index=True, width="stretch", on_select="rerun",
        selection_mode="single-row", key="tabla_periodistas",
        column_config={
            "foto": st.column_config.ImageColumn("", width="small"),
            "periodista": st.column_config.TextColumn("Periodista", width="medium"),
            "seccion_beat": st.column_config.TextColumn("Sección / Beat", width="medium"),
            "notas": st.column_config.NumberColumn("Notas", width="small",
                                                     help="Número de notas publicadas en el periodo (dato bruto)"),
            "eficiencia_normalizada": st.column_config.NumberColumn(
                "Eficiencia", format="%.0f", width="small",
                help="Índice comparativo (100 = mediana del equipo), no un conteo de notas ni un porcentaje"),
            "eficiencia_delta": st.column_config.TextColumn("Δ vs. periodo ant.", width="small"),
            "trafico_txt": st.column_config.TextColumn("Tráfico", width="small"),
            "pct_trafico_txt": st.column_config.TextColumn("% del medio", width="small"),
            "canal_dominante": st.column_config.TextColumn("Canal", width="small"),
            "notas_dificultad": st.column_config.TextColumn("Notas por dificultad", width="small",
                                                              help="Fácil / Media / Difícil, según el tráfico mensual de la sección"),
            "engagement": st.column_config.TextColumn("Engagement", width="small"),
            "semaforo": st.column_config.TextColumn("Semáforo SEO", width="small"),
            "flags_ia": st.column_config.NumberColumn("Flags IA", width="small"),
            "estado_txt": st.column_config.TextColumn("Estado", width="medium"),
        },
    )
    filas = event.get("selection", {}).get("rows", []) if event else []
    if filas:
        return vista.iloc[filas[0]]["slug"]
    return None


def _explicacion_eficiencia(tabla):
    mediana = tabla["trafico_ajustado"].median()
    ref = tabla.iloc[(tabla["trafico_ajustado"] - mediana).abs().argsort()[:1]].iloc[0]
    top = tabla.sort_values("eficiencia_normalizada", ascending=False).iloc[0]
    with st.expander("ℹ️ ¿Qué significa \"eficiencia normalizada\"? (no es el número de notas)", expanded=True):
        st.markdown(
            "Es un **índice comparativo**, no un porcentaje ni un conteo de notas. Compara el tráfico "
            "de cada periodista (ajustado por qué tan competida es su sección) contra la **mediana del "
            "equipo del mes**.\n\n"
            "- **100** = tráfico igual a la mediana del equipo\n"
            "- **200** = el doble de la mediana\n"
            "- **50** = la mitad de la mediana\n\n"
            f"**Ejemplo con los datos reales de este mes:** la mediana de tráfico ajustado del equipo fue "
            f"**{calc.formatear_numero(mediana)}**. {ref['periodista']} tuvo prácticamente esa misma cifra, "
            f"por eso su índice es {ref['eficiencia_normalizada']:.0f} (≈100). {top['periodista']} generó "
            f"{calc.formatear_numero(top['trafico_ajustado'])} — más del doble de la mediana — por eso su "
            f"índice es {top['eficiencia_normalizada']:.0f}.\n\n"
            "El **número de notas** es una métrica totalmente aparte: se ve en la tarjeta \"Notas totales\" "
            "y en el gráfico de barras de abajo."
        )


_DIFICULTAD_ICONO = {"Fácil": "🟢", "Media": "🔵", "Difícil": "🔴"}


def _notas_mas_leidas(periodo, top_n=10):
    """Reemplaza a la tarjeta "Mejor periodista de economía" -- pedido de
    Edwin, 29-ago-2026: "elimina eso, no sabes cómo sacarlo" (la tarjeta
    anterior generó confusión dos veces seguidas sobre qué tráfico medía
    exactamente). En su lugar, lo más simple y verificable: las notas reales
    con más tráfico del portal completo en el periodo, sin recortar por
    sub-sección ni autor -- mismo dato ya usado en cargar_notas()/vista
    "Notas", ordenado por clics reales."""
    with st.container(border=True, key="card_notas_mas_leidas"):
        st.subheader(f"🔥 Notas más leídas — {dr.MES_LABEL_LARGO.get(periodo, periodo)}")
        st.caption("Tráfico real (GA4+Search Console) de todo el portal en el periodo seleccionado arriba, "
                   "sin recortar por sección ni autor.")
        notas = dr.cargar_notas(periodo)
        if notas.empty:
            st.caption("Sin notas para este periodo.")
            return
        top = notas.sort_values("clics", ascending=False).head(top_n)
        for i, n in enumerate(top.itertuples(), start=1):
            marca = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            st.markdown(f"{marca} **{n.titulo}** — {calc.formatear_numero(n.clics)} "
                        f"({n.periodista} · {n.seccion})")


def _advertencias_declive():
    """"Qué está bajando" -- secciones (mes en curso vs. julio, tráfico/día) +
    entidades/temas (ventana móvil de ~17 días, todo el portal). Pedido de
    Edwin, 17-ago-2026: "le hace falta el tema de qué está bajando... como lo
    hicimos por entidades" -- mismo patrón visual de calculadora-periodistas
    (colombia.com)."""
    declive_seccion = dr.advertencias_declive_secciones()
    declive_entidad = dr.advertencias_declive_entidades()
    if declive_seccion.empty and declive_entidad.empty:
        return
    with st.container(border=True, key="card_advertencias"):
        st.subheader("⚠️ Qué está bajando")

        st.markdown(f"**Por sección** (tráfico/día, todo el portal, "
                    f"{dr.MES_LABEL_LARGO.get(dr.MES_PARCIAL, dr.MES_PARCIAL)} vs. julio):")
        st.caption("Compara ritmo diario, no el acumulado crudo, para que un mes parcial no se vea peor solo por tener menos días.")
        if declive_seccion.empty:
            st.success("Ninguna sección con caída relevante (≥15%) este periodo.")
        else:
            for r in declive_seccion.itertuples():
                st.markdown(
                    f"🔻 **{dr.seccion_label(r.seccion_raw)}** — "
                    f"{r.trafico_dia_anterior:.0f}/día en julio vs. {r.trafico_dia_actual:.0f}/día ahora "
                    f"(**{r.pct_cambio:.0f}%**)"
                )

        st.write("")
        st.markdown("**Por entidad/tema** (ventana móvil de ~17 días vs. los ~17 días anteriores):")
        st.caption(
            "🏷️ = entidad (persona, equipo, lugar) · 📌 = tema. Solo entidades con tráfico "
            "real en ambas ventanas (no las que \"desaparecieron\" del todo — eso puede ser una nota "
            "que ya no está en portada, no una caída de interés)."
        )
        if declive_entidad.empty:
            st.success("Ninguna entidad/tema con caída relevante (≥50%) en la última ventana.")
        else:
            for r in declive_entidad.itertuples():
                icono = "🏷️" if r.tipo == "entidad" else "📌"
                st.markdown(
                    f"🔻 {icono} **{r.entidad}** — "
                    f"{calc.formatear_numero(r.trafico_anterior)} en la ventana anterior vs. "
                    f"{calc.formatear_numero(r.trafico_actual)} ahora "
                    f"(**{r.pct_cambio:.0f}%**)"
                )


def _dificultad_canal_seccion():
    with st.container(border=True, key="card_secciones_dificultad"):
        st.subheader("Dificultad y canal por sección")
        st.caption("Dato agregado de TODO lo disponible (julio completo + histórico ene-jun) — "
                   "no cambia con el periodo seleccionado arriba, es contexto del portal completo.")
        agg = dr.secciones_resumen_agregado()
        tabla_mostrar = agg.copy()
        tabla_mostrar["Sección"] = tabla_mostrar["seccion_raw"].apply(dr.seccion_label)
        tabla_mostrar["Tráfico"] = tabla_mostrar["vistas"].apply(calc.formatear_numero)
        tabla_mostrar["Dificultad"] = tabla_mostrar["dificultad_categoria"].apply(
            lambda d: f"{_DIFICULTAD_ICONO[d]} {d}")
        tabla_mostrar["Canal dominante"] = tabla_mostrar.apply(
            lambda r: f"{r['canal_dominante']} ({r['pct_canal_dominante']:.0f}%)"
            if pd.notna(r["pct_canal_dominante"]) else "—", axis=1)
        st.dataframe(
            tabla_mostrar[["Sección", "Tráfico", "Dificultad", "Canal dominante"]],
            hide_index=True, width="stretch", height=min(460, 40 + 36 * len(tabla_mostrar)),
        )


def render(tabla, periodo):
    if tabla.empty:
        st.info("No hay datos para el rango de fechas seleccionado.")
        return None

    _kpis(tabla, periodo)
    _explicacion_eficiencia(tabla)
    st.write("")

    _notas_mas_leidas(periodo)
    st.write("")

    with st.container(border=True, key="card_tendencia_portal"):
        _tendencia_portal()
    st.write("")

    _advertencias_declive()
    st.write("")

    col_izq, col_der = st.columns([1, 1.3])
    with col_izq:
        with st.container(border=True, key="card_aporte"):
            _aporte_trafico(tabla)
    with col_der:
        with st.container(border=True, key="card_cuadrante"):
            seleccion_cuadrante = _cuadrante(tabla)

    st.write("")
    with st.container(border=True, key="card_notas"):
        _notas_por_periodista(tabla)

    st.write("")
    with st.container(border=True, key="card_tabla"):
        seleccion_selector = _selector_perfil(tabla)
        seleccion_tabla = _tabla_principal(tabla)

    st.write("")
    _dificultad_canal_seccion()

    return seleccion_cuadrante or seleccion_tabla or seleccion_selector
