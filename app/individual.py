"""Vista individual — perfil de desempeño de un periodista."""

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import datos_reales as dr
import secciones
from avatares import avatar_data_uri
from estilos import avatar_badge, card_value, delta_html, ecuacion_titular_box, metrica_card, nota_row, pill, trafico_card
from google_updates import UPDATES_2026
from graficos import agregar_proyeccion, marcar_mes_parcial, texto_metodologia_proyeccion

COLOR_ESTADO = {"green": "#16A34A", "blue": "#3457D5", "red": "#DC2626"}
ICONO_ESTADO = {"green": "📈", "blue": "➡️", "red": "🔻"}

ACCION_ITEM_SEO = {
    "h1_70_170": "Ajusta el H1 editorial a 70-170 caracteres — se está saliendo de ese rango.",
    "title_50_65": "Ajusta el title SEO a 50-65 caracteres (fuera de ese rango, Google lo corta o lo reescribe).",
    "meta_desc_150_170": "Escribe la meta descripción con 150-170 caracteres — si no, Google la reescribe por su cuenta.",
    "meta_desc_no_repite_h1": "No copies el H1 en la meta descripción — debe sumar información nueva, no repetir.",
    "primer_parrafo_180": "El primer párrafo debe responder la pregunta del titular en los primeros 180 caracteres, sin rodeos.",
    "h2_estructura": "Organiza el cuerpo con subtítulos H2 (cantidad y jerarquía correctas) — no lo dejes en bloque corrido.",
    "listas_tablas": "Cuando el tema lo permite (pasos, comparaciones, cifras), usa listas o tablas en vez de solo párrafos.",
    "extension_400": "La nota debe tener mínimo 400 palabras — se está quedando corta.",
    "tags_1_5": "Agrega entre 1 y 5 tags a la nota — sin tags, el sitio no la clasifica bien.",
    "enlaces_min_2": "Incluye mínimo 2 enlaces internos a otras notas del sitio.",
    "enlace_parrafo_1_3": "Pon el primer enlace interno en los primeros 3 párrafos, no hasta el final.",
    "ancla_valida": "Usa texto ancla descriptivo en los enlaces — nada de \"aquí\" o \"clic aquí\".",
    "imagen_1200px": "Sube la imagen principal en al menos 1200px de ancho — se está subiendo muy pequeña.",
    "imagen_alt": "Escribe el alt de la imagen describiendo lo que se ve — no lo dejes vacío o genérico.",
}


def _fmt(valor, patron="{:.0f}", vacio="— sin datos de Search"):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return vacio
    return patron.format(valor)


def _header(meta, ranking=None):
    with st.container(border=True, key="card_header"):
        col_foto, col_info = st.columns([1, 3], vertical_alignment="center")
        with col_foto:
            st.markdown(
                f'<img class="cp-avatar-perfil" src="{avatar_data_uri(meta["nombre"], "#334155", 320)}">',
                unsafe_allow_html=True,
            )
        with col_info:
            st.markdown(f"### {meta['nombre']}")
            st.markdown(f'<div class="cp-header-beat">{meta["seccion"]} · Beat principal: {meta["beat"]}</div>',
                        unsafe_allow_html=True)
            if ranking:
                st.write("")
                _ranking_pill(ranking)


def _ranking_pill(ranking):
    """Posición del periodista ese periodo contra el resto del equipo, como
    badge de color aparte — comparado con los demás de un vistazo."""
    if not ranking:
        return
    pos, total = ranking
    tercio = max(1, round(total / 3))
    color_key = "green" if pos <= tercio else "red" if pos > total - tercio else "blue"
    st.markdown(pill(f"🏆 #{pos} de {total} este periodo", color_key), unsafe_allow_html=True)


def _trafico(fila, historial, periodo):
    # OJO: tiene que ser el tráfico del PERIODO SELECCIONADO, no siempre el
    # más reciente del historial — bug real encontrado 2026-08-09: al ver un
    # mes histórico de alguien que TAMBIÉN tiene datos más nuevos (ej. julio),
    # tomar historial.iloc[-1] a ciegas mostraba el tráfico de julio con la
    # etiqueta de abril. Se busca la fila exacta de `periodo` en el historial
    # y se usa la anterior CRONOLÓGICAMENTE (no la última) para el delta.
    serie = historial.sort_values("mes").reset_index(drop=True)
    fila_periodo = serie[serie["mes"] == periodo]
    if not fila_periodo.empty:
        pos = fila_periodo.index[0]
        trafico_actual = float(fila_periodo.iloc[0]["trafico"])
        trafico_anterior = float(serie.iloc[pos - 1]["trafico"]) if pos > 0 else None
    else:
        trafico_actual = float(fila["clics"])
        trafico_anterior = None
    secundario = f"{fila['notas']:.0f} notas · {fila['pct_trafico_total']:.1f}% del tráfico del medio"
    html_card = trafico_card(calc.formatear_numero(trafico_actual),
                              delta_html(trafico_actual, trafico_anterior), secundario)
    st.markdown(html_card, unsafe_allow_html=True)


def _estado_actual(fila):
    label, color_key = calc.estado_label(fila["eficiencia_normalizada"], fila["en_alerta"])
    n_criticas = sum(1 for a in fila["alertas"] if a["severidad"] == "CRÍTICO")
    texto_alerta = (f"{n_criticas} alerta(s) crítica(s) de estado actual — ver pestaña Alertas para el detalle."
                     if n_criticas else "Rendimiento dentro del rango esperado del equipo.")
    descripciones = {
        "SOBRE MEDIANA": "Rendimiento por encima de la mediana del equipo en el periodo seleccionado.",
        "EN RANGO": "Rendimiento dentro del rango esperado del equipo.",
        "EN ALERTA": texto_alerta,
    }
    with st.container(border=True, key="card_estado"):
        # Flexbox en un solo bloque de markdown, no st.columns(): con la
        # tarjeta angosta (esta es 1 de 4 en la fila del header), un ratio
        # fijo de columnas deja muy poco ancho real para el círculo de 48px y
        # el texto lo atropella — flexbox reparte el espacio según el
        # contenido, no una proporción rígida.
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">'
            f'<div style="width:44px;height:44px;min-width:44px;border-radius:50%;'
            f'display:flex;align-items:center;justify-content:center;'
            f'background:{"#DCFCE7" if color_key=="green" else "#FEE2E2" if color_key=="red" else "#DBEAFE"};'
            f'font-size:1.3rem;flex-shrink:0">{ICONO_ESTADO[color_key]}</div>'
            f'<div style="min-width:0"><div class="cp-card-title" style="margin-bottom:2px">ESTADO ACTUAL</div>'
            f'<div style="font-weight:700;font-size:1.15rem;color:{COLOR_ESTADO[color_key]}">{label}</div></div>'
            f'</div>'
            f'<div class="cp-card-desc">{descripciones[label]}</div>',
            unsafe_allow_html=True,
        )


def _diagnostico_dificultad(fila):
    """De quién es "el problema" cuando el tráfico es bajo: si la sección es
    fácil, es del periodista; si es difícil, es (al menos en parte) de la
    sección — mismo criterio que Colombia.com para leer estos números."""
    dificultad = fila["dificultad_categoria"]
    eficiencia = fila["eficiencia_normalizada"]
    bajo = pd.notna(eficiencia) and eficiencia < 70
    if not bajo:
        return "✅", "Rendimiento saludable", "Tráfico acorde o mejor a lo esperado para la dificultad de esta sección."
    if dificultad == "Fácil":
        return "⚠️", "Revisar al periodista", "Sección fácil pero rendimiento bajo — la sección no es la limitante aquí."
    if dificultad == "Difícil":
        return "ℹ️", "Puede ser la sección", "Sección difícil — el bajo tráfico se explica en parte por eso, no solo por el periodista."
    return "🟡", "Revisar caso a caso", "Rendimiento bajo en una sección de dificultad media."


def _dificultad_seccion(fila, periodo):
    with st.container(border=True, key="card_dificultad"):
        st.markdown('<div class="cp-card-title">Dificultad de la sección</div>', unsafe_allow_html=True)
        badge_color = {"Fácil": "green", "Media": "blue", "Difícil": "red"}[fila["dificultad_categoria"]]
        st.markdown(f":{badge_color}-background[**{fila['dificultad_categoria'].upper()}**] — "
                    f"{dr.seccion_label(fila['seccion_raw'])}")
        icono, titulo, detalle = _diagnostico_dificultad(fila)
        st.markdown(f"{icono} **{titulo}**")
        st.caption(detalle)
        trafico_mensual = dr.secciones_trafico_real(periodo).get(fila["seccion_raw"], 0)
        st.caption(f"Tráfico real de la sección en el periodo: **{calc.formatear_numero(trafico_mensual)}** visitas "
                   f"· ajuste de eficiencia ×{fila['dificultad_ajuste']:.1f}")


def _trafico_historico(historial, nombre_display, meta, periodistas_meta):
    with st.container(border=True, key="card_trafico_historico"):
        col_titulo, col_comparar = st.columns([2, 1])
        with col_titulo:
            st.subheader("Tráfico por mes")
            st.caption(
                "Tráfico real generado cada mes (ene-jul 2026, GA4+Search Console) — el número bruto, sin "
                "ajustar por dificultad de sección ni normalizar contra el equipo (eso está en \"Eficiencia "
                "normalizada\" más abajo). No cambia con el selector de periodo de arriba. Los puntos rojos "
                "son meses con un update de Google conocido — si una caída coincide con uno, es una señal de "
                "algoritmo/sección, no necesariamente del periodista."
            )
        otros = [p for p in periodistas_meta if p["slug"] != meta["slug"]]
        with col_comparar:
            comparar_con = st.selectbox(
                "Comparar con", ["Ninguno"] + [p["nombre"] for p in otros], key="comparar_periodista",
            )

        serie = historial.sort_values("mes")
        if serie.empty:
            st.caption("Sin notas identificadas de este periodista en ningún periodo.")
            return
        fig = go.Figure(go.Scatter(
            x=serie["mes_label"], y=serie["trafico"], mode="lines+markers+text",
            line=dict(color="#16A34A", width=3), marker=dict(size=9, color="#16A34A"),
            text=[calc.formatear_numero(v) for v in serie["trafico"]], textposition="top center",
            hovertemplate="%{x}<br>Tráfico: %{y:,.0f}<extra></extra>", name=nombre_display,
        ))

        mostrar_leyenda = comparar_con != "Ninguno"
        if mostrar_leyenda:
            otro_meta = next(p for p in otros if p["nombre"] == comparar_con)
            otro_historial = dr.historial_periodista(otro_meta["autor_original"]).sort_values("mes")
            fig.add_trace(go.Scatter(
                x=otro_historial["mes_label"], y=otro_historial["trafico"], mode="lines+markers+text",
                line=dict(color="#F59E0B", width=3, dash="dash"), marker=dict(size=9, color="#F59E0B"),
                text=[calc.formatear_numero(v) for v in otro_historial["trafico"]], textposition="bottom center",
                hovertemplate="%{x}<br>Tráfico: %{y:,.0f}<extra></extra>", name=comparar_con,
            ))

        # Updates de Google conocidos superpuestos sobre la línea de tráfico:
        # si una caída coincide con un update, no es (solo) culpa del periodista.
        updates_por_mes: dict[str, list[dict]] = {}
        for u in UPDATES_2026:
            if u["inicio"].year == 2026 and 1 <= u["inicio"].month <= 7:
                mes_str = f"2026-{u['inicio'].month:02d}"
                updates_por_mes.setdefault(mes_str, []).append(u)

        con_update = serie[serie["mes"].isin(updates_por_mes)]
        if not con_update.empty:
            hover_txt = [" · ".join(u["nombre"] for u in updates_por_mes[m]) for m in con_update["mes"]]
            fig.add_trace(go.Scatter(
                x=con_update["mes_label"], y=con_update["trafico"], mode="markers",
                marker=dict(size=15, color="#DC2626", symbol="diamond", line=dict(width=2, color="white")),
                hovertext=hover_txt, hovertemplate="%{x}<br>%{hovertext}<extra></extra>", showlegend=False,
            ))
            for r in con_update.itertuples():
                tipos = " + ".join(sorted({u["tipo"] for u in updates_por_mes[r.mes]}))
                fig.add_annotation(
                    x=r.mes_label, y=r.trafico, text=tipos, showarrow=True, arrowhead=0, arrowcolor="#DC2626",
                    ax=0, ay=-38, font=dict(size=10, color="#DC2626"),
                    bgcolor="rgba(255,255,255,0.92)", bordercolor="#DC2626", borderwidth=1, borderpad=3,
                )

        proyeccion = dr.proyeccion_fin_de_mes(serie, "trafico", col_mes="mes")
        if proyeccion:
            label_actual = serie["mes_label"].iloc[-1]
            label_proy = f"{label_actual} (proy.)"
            agregar_proyeccion(fig, proyeccion, x_actual=label_actual, x_proyectado=label_proy)

        # Orden cronológico EXPLÍCITO del eje X: con dos trazas de meses
        # distintos (ej. Ana Sosa arranca en abril, Andrea Mercedes tiene
        # desde marzo), Plotly por defecto ordena las categorías por el
        # orden en que las va viendo TRAZA POR TRAZA, no por su valor real —
        # "Marzo" de la segunda traza terminaba después de "Julio" porque la
        # primera traza nunca lo mencionó. Con categoryarray fijo, el eje
        # siempre sale enero->julio sin importar qué periodista tenga huecos.
        orden_meses = [dr.MES_LABEL_LARGO[p] for p in reversed(dr.ORDEN_PERIODOS)]
        fig.update_layout(
            height=340, margin=dict(l=10, r=10, t=50, b=10), showlegend=mostrar_leyenda,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#E2E6ED", rangemode="tozero"),
            xaxis=dict(showgrid=False, categoryorder="array", categoryarray=orden_meses),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        if proyeccion:
            st.caption(texto_metodologia_proyeccion(proyeccion))


def _eficiencia_historica(historial, nombre_display):
    with st.container(border=True, key="card_eficiencia"):
        st.subheader("Eficiencia normalizada (índice) en el tiempo")
        st.caption(
            "7 periodos reales (ene-jul 2026): tráfico/nota de cada mes contra la mediana del equipo ese mes "
            "= 100. Versión más simple que la tarjeta \"Eficiencia normalizada\" del periodo seleccionado "
            "arriba (esa sí ajusta por dificultad de sección) — aquí se sacrifica ese ajuste para poder "
            "comparar los 7 periodos con el mismo criterio."
        )
        serie = historial.sort_values("mes")
        if serie.empty:
            st.caption("Sin notas identificadas de este periodista en ningún periodo.")
            return
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=serie["mes_label"], y=[100] * len(serie), mode="lines",
                                  line=dict(color="#94A3B8", dash="dash", width=1), name="Mediana del equipo (100)"))
        fig.add_trace(go.Scatter(x=serie["mes_label"], y=serie["indice"], mode="lines+markers+text",
                                  line=dict(color="#3457D5", width=3), marker=dict(size=7),
                                  text=[f"{v:.0f}" for v in serie["indice"]], textposition="top center",
                                  name=nombre_display))
        if dr.mes_es_parcial(serie["mes"].iloc[-1]):
            marcar_mes_parcial(fig, serie["mes_label"].iloc[-1], serie["indice"].iloc[-1])
        fig.update_layout(
            height=420, margin=dict(l=10, r=10, t=10, b=10), showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#E2E6ED", rangemode="tozero"),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _metricas_clave(fila):
    engagement = calc.formatear_tiempo(fila["tiempo_pagina_seg"])
    tarjetas = [
        metrica_card("Volumen de notas publicadas", f"{fila['notas']:.0f}",
                     "<span class='cp-delta' style='color:#64748B'>notas del periodo, conteo directo</span>", "📝", "purple"),
        metrica_card("Eficiencia normalizada", f"{fila['eficiencia_normalizada']:.0f}",
                     "<span class='cp-delta' style='color:#64748B'>índice · 100 = mediana del equipo</span>", "📈", "teal"),
        metrica_card("Canal dominante", f"{fila['canal_dominante']}",
                     f"<span class='cp-delta' style='color:#64748B'>{_fmt(fila['pct_canal_dominante'], '{:.0f}% del tráfico', '—')}</span>",
                     "🔍", "blue"),
        metrica_card("CTR de titulares (real vs. esperado)", _fmt(fila["ctr_indice"], "{:.2f}x"),
                     "", "🎯", "blue"),
        metrica_card("Engagement (tiempo en página)", engagement, "", "👥", "purple"),
        metrica_card("Canibalización interna", f"{fila['canibalizacion_pct']:.0f}%",
                     "<span class='cp-delta' style='color:#64748B'>% de notas con título muy similar a otra "
                     "propia en la misma sección</span>", "🧭", "teal"),
        metrica_card("Extensión promedio (palabras)", _fmt(fila["palabras_promedio"], "{:.0f}", "— sin dato"), "", "📄", "blue"),
        metrica_card("Notas con semáforo SEO verde", f"{fila['semaforo_verde_pct']:.0f}%",
                     f"<span class='cp-delta' style='color:#64748B'>{int(fila['notas_verde'])}🟢 "
                     f"{int(fila['notas_amarillo'])}🟡 {int(fila['notas_rojo'])}🔴</span>", "✅", "green"),
    ]
    with st.container(border=True, key="card_metricas"):
        st.subheader("Métricas clave del periodo")
        st.markdown(f'<div class="cp-metric-grid">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _posicion_google(historial, meta):
    with st.container(border=True, key="card_posicion"):
        st.subheader(f"Posición promedio en Google — {meta['beat']}")
        serie = historial.sort_values("mes").dropna(subset=["posicion_promedio"])
        if serie.empty:
            st.caption("Sin notas con datos de posición de Search Console en ningún periodo "
                       "(el tráfico de este periodista viene sobre todo de Discover/News, "
                       "que no reportan posición).")
            return
        fig = go.Figure(go.Scatter(x=serie["mes_label"], y=serie["posicion_promedio"], mode="lines+markers+text",
                                    text=[f"{v:.1f}" for v in serie["posicion_promedio"]], textposition="top center",
                                    line=dict(color="#3457D5", width=3), marker=dict(size=10)))
        if dr.mes_es_parcial(serie["mes"].iloc[-1]):
            marcar_mes_parcial(fig, serie["mes_label"].iloc[-1], serie["posicion_promedio"].iloc[-1])
        fig.update_layout(
            height=280, margin=dict(l=10, r=10, t=10, b=10),
            yaxis=dict(autorange="reversed", title="Posición", showgrid=True, gridcolor="#E2E6ED"),
            xaxis=dict(showgrid=False), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption("↓ Descendente = mejora (menor posición es mejor). Ponderada por tráfico de cada nota. "
                    "Periodos sin punto = sin notas con datos de Search ese mes.")


def _eeat(fila):
    with st.container(border=True, key="card_eeat"):
        st.subheader("Autoridad en Google")
        st.caption("Top 10 y posición en Search Console, de las notas con dato de posición.")
        tarjetas = [
            metrica_card("Notas en Top 10 Google", f"{fila['notas_top10']:.0f}", "", "🏆", "green"),
            metrica_card("Posición promedio", _fmt(fila["posicion_promedio"]), "", "🔍", "blue"),
        ]
        st.markdown(f'<div class="cp-metric-grid" style="grid-template-columns:repeat(2,1fr)">'
                    f'{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _cumplimiento_seo(fila):
    with st.container(border=True, key="card_seo"):
        st.caption("Cumplimiento SEO promedio (14 de 23 ítems automatizados)")
        st.markdown(card_value("", _fmt(fila["pct_cumplimiento_prom"], "{:.0f}%", "— sin notas evaluadas")),
                    unsafe_allow_html=True)
        st.caption("Notas por semáforo (umbral 80% / 60%):")
        st.markdown(f"🟢 **{fila['notas_verde']:.0f}**&nbsp;&nbsp;"
                    f"🟡 **{fila['notas_amarillo']:.0f}**&nbsp;&nbsp;"
                    f"🔴 **{fila['notas_rojo']:.0f}**", unsafe_allow_html=True)
        evaluadas, total = int(fila["notas_seo_evaluadas"]), int(fila["notas"])
        if evaluadas >= total:
            st.caption(f"Las {total} notas del periodo fueron evaluadas a fondo con el checklist SEO completo.")
        else:
            st.caption(f"{evaluadas} de {total} notas del periodo evaluadas a fondo "
                       "(el resto no tiene datos suficientes para scrapear el checklist)")


def _diagnostico_seo(meta, periodo):
    with st.container(border=True, key="card_diagnostico_seo"):
        st.subheader("¿En qué está fallando el SEO? — desglose por ítem")
        if dr.es_periodo_completo(periodo):
            diagnostico = dr.diagnostico_seo_por_autor(meta["autor_original"])
            st.caption("% de sus notas que cumplen cada regla del checklist, de peor a mejor. "
                       "Esto es lo accionable: no basta con saber el promedio, hay que saber dónde corregir.")
        else:
            diagnostico = dr.diagnostico_seo_por_autor_mes(meta["autor_original"], periodo)
            st.caption(f"% sobre la muestra de {dr.PERIODOS[periodo]['label'].split(' · ')[0]} "
                       "(hasta 12 notas), de peor a mejor. Muestra chica — indicativo, no censo.")
        if not diagnostico:
            st.caption("Sin datos suficientes para el desglose.")
            return

        # Plotly dibuja barras horizontales de abajo hacia arriba, así que se invierte
        # el orden para que el peor ítem (el más importante de corregir) quede arriba.
        en_pantalla = list(reversed(diagnostico))
        colores = ["#DC2626" if d["pct"] < 50 else "#F59E0B" if d["pct"] < 80 else "#16A34A" for d in en_pantalla]
        textos = [f"{d['pct']:.0f}%" for d in en_pantalla]
        fig = go.Figure(go.Bar(
            x=[d["pct"] for d in en_pantalla], y=[d["label"] for d in en_pantalla], orientation="h",
            marker_color=colores, text=textos, textposition="outside",
            hovertemplate="%{y}<br>Cumplimiento: %{x:.0f}%<extra></extra>",
        ))
        fig.update_layout(
            height=max(320, 26 * len(diagnostico)), margin=dict(l=0, r=40, t=10, b=10),
            xaxis=dict(title=None, range=[0, 108], showgrid=True, gridcolor="#E2E6ED"),
            yaxis_title=None, showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        peores = [d["label"] for d in diagnostico[:3]]
        st.caption(f"🔴 Sus 3 puntos más débiles: {'; '.join(peores)}.")

        _que_mejorar(diagnostico)


def _que_mejorar(diagnostico):
    pendientes = [d for d in diagnostico if d["pct"] < 80]
    st.write("")
    st.markdown("**Qué debe mejorar — instrucciones concretas**")
    if not pendientes:
        st.success("Cumple con 80%+ del checklist en todos los ítems evaluados. Nada urgente que corregir.")
        return
    st.caption(
        "Un ítem en 0% significa que nunca lo hace, no que le está yendo mal a veces — la diferencia importa "
        "para saber si es un hábito por corregir o un caso puntual."
    )
    filas = []
    for d in pendientes:
        if d["pct"] == 0:
            severidad = "🔴 Nunca lo hace"
        elif d["pct"] < 50:
            severidad = "🔴 Rara vez"
        else:
            severidad = "🟡 A veces"
        filas.append({
            "Ítem": d["label"],
            "Cumplimiento": f"{d['pct']:.0f}%",
            "Frecuencia": severidad,
            "Qué hacer": ACCION_ITEM_SEO.get(d["item"], "Revisar este punto del checklist SEO."),
        })
    st.dataframe(
        pd.DataFrame(filas), hide_index=True, width="stretch",
        column_config={
            "Ítem": st.column_config.TextColumn(width="medium"),
            "Cumplimiento": st.column_config.TextColumn(width="small"),
            "Frecuencia": st.column_config.TextColumn(width="small"),
            "Qué hacer": st.column_config.TextColumn(width="large"),
        },
    )


def _semaforo_pct(pct: float) -> str:
    if pct >= 60:
        return "🟢"
    if pct >= 30:
        return "🟡"
    return "🔴"


ITEMS_EEAT_ESTRUCTURAL = [
    ("schema_person", "Autor con schema Person",
     "El JSON-LD del artículo tipa al autor como \"Person\" (no \"Organization\" ni ausente) — "
     "identidad formalmente reconocible por Google."),
    ("perfil_verificable", "Perfil de autor verificable",
     "La URL de autor del JSON-LD (/post_author/{slug}/) siempre da 404 en revistamercado.do — "
     "bug de origen del sitio, igual para todos los periodistas, no algo que este autor controle."),
    ("bio_verificable", "Bio de autor real",
     "Consecuencia directa del punto anterior: sin una página de autor que cargue, no hay biografía "
     "pública verificable en ningún perfil del sitio."),
]

ITEMS_EEAT_POR_NOTA = [
    ("pct_actualizacion_real", "Actualiza notas publicadas",
     "% de notas con fecha de actualización real posterior a la de publicación (>10 min de diferencia, "
     "para descartar ruido del autosave) — evidencia de mantenimiento, no solo publicar y olvidar."),
    ("pct_cita_fuentes_externas", "Cita fuentes externas",
     "% de notas con al menos un enlace saliente a un sitio externo real (no redes sociales) — "
     "evidencia de fuentes primarias."),
    ("pct_atribucion_explicita", "Atribución explícita de la información",
     "% de notas con frases como \"según\", \"informó\", \"confirmó\" cerca de una afirmación — "
     "trazabilidad de la fuente."),
    ("pct_consistencia_tematica", "Consistencia temática (Expertise)",
     "% del tráfico del periodista concentrado en su sección más fuerte — publicar dentro de un "
     "cluster temático definido es señal real de expertise, no dispersarse en todo."),
]


def _titulares_periodista(meta):
    """Qué ecuación de titular (rasgo estructural) le rinde a ESTE periodista -- portado de
    calculadora-periodistas/app/individual.py (Colombia.com). Mismo motor que la ecuación de
    portada (Dashboard) y por sección, acá agrupado por autor."""
    autor = meta["autor_original"]
    with st.container(border=True, key="card_titulares_real"):
        st.subheader("🧮 Qué ecuación de titular le rinde")
        st.caption(
            "Minado en automático sobre sus títulos y tráfico real, con todo su histórico "
            "disponible (no un solo periodo, para tener muestra suficiente). \"Con vs. sin\" "
            "compara el tráfico promedio de sus títulos que tienen ese rasgo contra los que no."
        )

        secciones_propias = dr.secciones_con_titulares_por_autor(autor)
        seccion_sel = None
        if secciones_propias:
            opciones = ["Todas sus secciones (agregado)"] + [
                secciones.LABELS_SECCION.get(s, dr.seccion_label(s)) for s in secciones_propias]
            mapa_label_a_slug = dict(zip(
                [secciones.LABELS_SECCION.get(s, dr.seccion_label(s)) for s in secciones_propias], secciones_propias))
            seleccion = st.selectbox(
                "🗂️ Ver la ecuación de una sección puntual de este periodista",
                opciones, key="titulares_autor_seccion_sel",
            )
            if seleccion != opciones[0]:
                seccion_sel = mapa_label_a_slug[seleccion]
        else:
            st.caption(
                "Ninguna sección propia con muestra suficiente (mínimo 10 notas) todavía -- "
                "mostrando el agregado de todas sus notas."
            )

        if seccion_sel:
            rasgos = dr.patrones_titulares_por_autor_y_seccion(autor, seccion_sel)
            etiqueta_seccion = secciones.LABELS_SECCION.get(seccion_sel, dr.seccion_label(seccion_sel))
            etiqueta_ecuacion = f"Ecuación de titular -- {meta['nombre']} en {etiqueta_seccion}"
        else:
            rasgos = dr.patrones_titulares_por_autor(autor)
            etiqueta_ecuacion = f"Ecuación de titular -- {meta['nombre']} -- todas sus secciones"

        if rasgos.empty:
            st.caption("Sin muestra suficiente (mínimo 10 notas con título, 3 con y 3 sin cada "
                       "rasgo) para medir esto con confianza en este corte todavía.")
            return

        ecuacion = dr.sintetizar_ecuacion_titular(rasgos)
        if ecuacion:
            if seccion_sel:
                ejemplo = dr.ejemplo_titular_por_autor_y_seccion(autor, seccion_sel, rasgos)
            else:
                ejemplo = dr.ejemplo_titular_por_autor(autor, rasgos)
            st.markdown(ecuacion_titular_box(etiqueta_ecuacion, ecuacion, ejemplo), unsafe_allow_html=True)
            st.caption(
                "Calculada en automático (mismo motor que la ecuación de portada y por sección) "
                "tomando las piezas con más lift a favor y en contra -- no es juicio editorial "
                "hecho a mano, es una aproximación mecánica sobre datos reales."
            )
        else:
            st.caption(
                "Ninguna pieza de la ecuación (ancla, fuente, verbo de consulta, año...) tiene "
                "lift suficiente todavía para armar una ecuación con confianza -- ver el detalle "
                "de rasgos abajo si quieres revisarlo de todas formas."
            )


def _eeat_checklist(meta):
    eeat = dr.eeat_por_autor(meta["autor_original"])
    with st.container(border=True, key="card_eeat_checklist"):
        st.subheader("Checklist EEAT — confianza y autoridad")
        st.caption(
            "Mejor práctica de Google para medios de noticias (Search Quality Rater Guidelines + checklist "
            "de Google News), sobre una muestra de hasta 15 notas de TODO el histórico + julio (no cambia con "
            "el periodo seleccionado de arriba). Complementa el semáforo SEO — no reemplaza la revisión "
            "editorial de precisión factual, diversidad de fuentes ni backlinks/menciones externas."
        )
        if not eeat:
            st.caption("Sin datos suficientes para este autor.")
            return

        st.markdown("**Estructural (a nivel de sitio, igual para todos)**")
        for clave, titulo, detalle in ITEMS_EEAT_ESTRUCTURAL:
            ok = bool(eeat[clave])
            st.markdown(f"{'✅' if ok else '❌'} **{titulo}**" + ("" if ok else " — no"))
            st.caption(detalle)

        st.write("")
        st.markdown(f"**Por-nota (muestra de {int(eeat['notas_muestreadas'])} notas)**")
        for clave, titulo, detalle in ITEMS_EEAT_POR_NOTA:
            valor = eeat[clave]
            st.markdown(f"{_semaforo_pct(valor)} **{valor:.0f}%** {titulo}")
            st.caption(detalle)

        st.write("")
        st.caption(
            "No automatizable, requiere revisión editorial o una herramienta paga que este pipeline no "
            "tiene: precisión factual verificable, evidencia de reporteo propio (fotos/video originales, "
            "no solo agregación de agencia), diversidad y calidad de fuentes citadas, objetividad/balance, "
            "backlinks y menciones en medios externos (Ahrefs/Moz/Semrush), transparencia de conflictos "
            "de interés o contenido patrocinado marcado."
        )


def _entidades_fuertes(meta):
    with st.container(border=True, key="card_entidades_fuertes"):
        st.subheader("En qué secciones le rinde escribir")
        st.caption(
            "Tráfico/nota real por sección, con los 7 periodos de historia (ene-jul 2026) — reemplaza el beat "
            "fijo asignado por instinto. Confianza: 🟢 alta (≥10 notas) · 🟡 media (3-9) · ⚪ baja (<3, "
            "indicativo). Dificultad = qué tan fácil es generar tráfico en esa sección (por su volumen real "
            "acumulado) — si el tráfico/nota es bajo en una sección FÁCIL, es más señal del periodista; si es "
            "en una DIFÍCIL, la sección también pesa."
        )
        esp = dr.entidades_fuertes(meta["autor_original"])
        if esp.empty:
            st.caption("Sin datos suficientes para calcular especialización.")
            return
        # Tabla compacta, no una línea de markdown por sección: con secciones
        # tan granulares (subsección real, ej. "empresas/sport-business") un
        # periodista activo en varias fácilmente pasa de 15-18 filas — como
        # texto libre eso es un listado eterno; como tabla con scroll interno
        # cabe la MISMA información sin perder nada, solo más compacta.
        icono_conf = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
        vista = esp.copy()
        vista["Sección"] = vista["seccion"].apply(
            lambda s: secciones.LABELS_SECCION.get(s, dr.seccion_label(s)))
        vista["Dificultad"] = vista["seccion"].apply(lambda s: dr.dificultad_seccion(s)[0])
        vista["Confianza"] = vista["confianza"].map(icono_conf)
        st.dataframe(
            vista[["Sección", "trafico_por_nota", "notas", "Dificultad", "Confianza"]],
            hide_index=True, width="stretch", height=min(380, 40 + 36 * len(vista)),
            column_config={
                "Sección": st.column_config.TextColumn("Sección", width="medium"),
                "trafico_por_nota": st.column_config.NumberColumn("Tráfico/nota", format="%.0f", width="small"),
                "notas": st.column_config.NumberColumn("Notas (7 periodos)", width="small"),
                "Dificultad": st.column_config.TextColumn("Dificultad", width="small"),
                "Confianza": st.column_config.TextColumn("Confianza", width="small"),
            },
        )
        hints = [secciones.PLAYBOOK_HINT[r["seccion"]] for _, r in esp.iterrows() if r["seccion"] in secciones.PLAYBOOK_HINT]
        for hint in hints[:2]:
            st.caption(f"📌 {hint}")


ICONO_TIPO_ENTIDAD = {"entidad": "🏷️", "tema": "📌"}


def _chips_temas(df, color_conf):
    chips = []
    for _, r in df.iterrows():
        confianza_txt = str(r.get("confianza", ""))
        color = "gray"
        for clave, c in color_conf.items():
            if clave in confianza_txt:
                color = c
                break
        icono = ICONO_TIPO_ENTIDAD.get(r.get("tipo"), "📌")
        trafico_txt = f"{calc.formatear_numero(r['trafico'])} · " if "trafico" in df.columns else ""
        chips.append(f":{color}-background[{icono} **{r['forma']}** · {trafico_txt}{int(r['notas'])} notas]")
    st.markdown("  ".join(chips))


# Pedido explícito de Edwin (2026-08-09), SOLO para este periodista: los
# resultados de lotería son contenido de servicio recurrente y diario (se
# publica todos los días, no es una elección editorial) — su volumen de
# tráfico domina y distorsiona el análisis de "en qué le rinde escribir" de
# Jhojhanni Fiorini específicamente, tapando el resto de sus temas reales.
# No es un cambio global: para el resto del equipo la lotería sí cuenta.
AUTORES_EXCLUIR_LOTERIA = {"Jhojhanni Fiorini"}


def _temas_fuertes(meta):
    with st.container(border=True, key="card_temas_fuertes"):
        st.subheader("Temas en los que le rinde (y en los que no)")
        st.caption(
            "🏷️ Entidad = persona, equipo, lugar u organización única e identificable. 📌 Tema = frase "
            "temática recurrente, relevancia semántica pero no una entidad única. Extraído de títulos reales "
            "de los 7 periodos (ene-jul 2026); el tráfico es la suma real de vistas de las notas donde aparece "
            "cada uno, no un promedio inventado. Detección automática por patrones de texto, no verificación "
            "editorial manual: puede tener algo de ruido puntual."
        )
        excluir_loteria = meta["autor_original"] in AUTORES_EXCLUIR_LOTERIA
        patron_excluir = "loter" if excluir_loteria else None
        if excluir_loteria:
            st.caption("ℹ️ Se excluyeron los temas de resultados de lotería de este análisis — es contenido "
                       "de servicio diario recurrente cuyo volumen tapaba el resto de sus temas reales.")
        fuertes = dr.temas_fuertes(meta["autor_original"], excluir_patron=patron_excluir)
        st.markdown("**🟢 Le rinde — más tráfico total**")
        if fuertes.empty:
            st.caption("Sin temas recurrentes detectados todavía para este periodista.")
        else:
            _chips_temas(fuertes, {"alta": "green", "media": "orange", "baja": "gray"})

        st.write("")
        debiles = dr.temas_debiles(meta["autor_original"], excluir_patron=patron_excluir)
        st.markdown("**🔴 No le rinde — temas en los que insiste pero no genera tráfico/nota**")
        if debiles.empty:
            st.caption("Sin temas recurrentes de bajo rendimiento detectados (muestra insuficiente).")
        else:
            _chips_temas(debiles, {"alta": "red", "media": "red", "baja": "gray"})

        st.caption("🟢 alta confianza (≥10 notas) · 🟠 media (3-9) · ⚪ baja (2, solo se muestra en \"le rinde\", "
                   "indicativo). \"No le rinde\" excluye baja confianza para no señalar por un caso aislado.")


def _nota_editorial(slug):
    with st.container(border=True, key="card_nota"):
        col_titulo, col_boton = st.columns([2, 1])
        col_titulo.caption("Nota / Flag editorial")
        if col_boton.button("+ Nota", key=f"agregar_nota_{slug}", width="stretch"):
            st.info("El registro manual de flags editoriales se implementa en una fase posterior del proyecto.")
        st.caption("Sin notas editoriales registradas en el periodo.")


def _lista_notas_html(propias):
    if propias.empty:
        st.caption("Sin notas en esta vista.")
        return
    propias = propias.copy()
    propias["pct_del_total"] = 100 * propias["clics"] / propias["clics"].sum()
    top = propias.head(10)

    pct_max = top["pct_del_total"].max()
    filas_html = []
    for i, n in enumerate(top.itertuples(), start=1):
        pos_txt = f"{n.posicion_promedio:.0f}" if n.posicion_promedio == n.posicion_promedio else "s/d"
        meta = f"{n.canal_dominante} · Posición Google {pos_txt}"
        filas_html.append(nota_row(
            rank=i, titulo=n.titulo, meta=meta,
            clics_txt=calc.formatear_numero(n.clics), pct_txt=f"{n.pct_del_total:.1f}%",
            barra_pct=100 * n.pct_del_total / pct_max if pct_max else 0,
            semaforo=n.semaforo,
        ))
    st.markdown(f'<div class="cp-nota-list">{"".join(filas_html)}</div>', unsafe_allow_html=True)


def _notas_destacadas(df_notas, slug, autor_original=None):
    with st.container(border=True, key="card_notas_destacadas"):
        st.subheader("Notas más vistas del periodo")
        st.caption("De dónde salió el tráfico: ranking de las notas individuales con más clics. "
                   "🟢🟡🔴 = semáforo SEO evaluado · ⚪ = nota real pero sin evaluar a fondo todavía.")
        propias = df_notas[df_notas["slug"] == slug].sort_values("clics", ascending=False).reset_index(drop=True)
        if propias.empty:
            st.caption("No hay notas registradas para este periodista en el periodo.")
            return

        # Pedido explícito de Edwin (2026-08-16), mismo criterio que
        # AUTORES_EXCLUIR_LOTERIA en _temas_fuertes(): para Jhojhanni Fiorini
        # los resultados de lotería (contenido de servicio diario recurrente,
        # no elección editorial) dominan el ranking crudo y tapan sus notas
        # reales -- acá se separan en dos módulos en vez de excluirse en
        # silencio, para no perder la evidencia de cuánto pesa la lotería.
        if autor_original in AUTORES_EXCLUIR_LOTERIA:
            es_loteria = propias["titulo"].str.contains("loter", case=False, na=False)
            tab_todas, tab_sin = st.tabs(
                [f"Todas ({len(propias)})", f"Sin loterías ({int((~es_loteria).sum())})"])
            with tab_todas:
                _lista_notas_html(propias)
            with tab_sin:
                st.caption("ℹ️ Se excluyeron los resultados de lotería de este ranking — contenido de "
                           "servicio diario recurrente cuyo volumen tapa el resto de sus notas reales.")
                _lista_notas_html(propias[~es_loteria].reset_index(drop=True))
        else:
            _lista_notas_html(propias)


def render(tabla, df_notas, slug, periodo=dr.PERIODO_DEFAULT):
    periodistas_meta = dr.cargar_periodistas_meta(periodo)
    meta_por_slug = {p["slug"]: p for p in periodistas_meta}
    if slug not in meta_por_slug:
        if not periodistas_meta:
            st.info("No hay datos para este periodo.")
            return
        slug = periodistas_meta[0]["slug"]
    meta = meta_por_slug[slug]

    if tabla.empty or slug not in set(tabla["slug"]):
        st.info("No hay datos para este periodista en el periodo.")
        return

    if not dr.es_periodo_completo(periodo):
        st.info(f"📊 **{dr.PERIODOS[periodo]['label']}** — tráfico real y completo del mes (GA4+Search Console). "
                "El semáforo SEO de este periodo es una MUESTRA (hasta 12 notas), no un censo — algunas tarjetas "
                "de abajo pueden mostrar menos notas evaluadas de las que realmente publicó.", icon="ℹ️")
    fila = tabla[tabla["slug"] == slug].iloc[0]
    historial = dr.historial_periodista(meta["autor_original"])
    ranking = dr.ranking_periodista(meta["autor_original"], periodo)

    col_header, col_trafico, col_estado, col_dificultad = st.columns([1.5, 0.9, 1.05, 1.1], vertical_alignment="top")
    with col_header:
        _header(meta, ranking)
    with col_trafico:
        _trafico(fila, historial, periodo)
    with col_estado:
        _estado_actual(fila)
    with col_dificultad:
        _dificultad_seccion(fila, periodo)
    st.write("")

    _trafico_historico(historial, fila["periodista"], meta, periodistas_meta)
    st.write("")

    col_izq, col_der = st.columns([1.3, 1])
    with col_izq:
        _eficiencia_historica(historial, fila["periodista"])
    with col_der:
        _metricas_clave(fila)

    st.write("")
    col_pos, col_nota = st.columns([1.4, 1])
    with col_pos:
        _posicion_google(historial, meta)
    with col_nota:
        _nota_editorial(slug)

    st.write("")
    _entidades_fuertes(meta)

    st.write("")
    _temas_fuertes(meta)

    st.write("")
    col_eeat, col_seo = st.columns(2)
    with col_eeat:
        _eeat(fila)
    with col_seo:
        _cumplimiento_seo(fila)

    st.write("")
    _titulares_periodista(meta)

    st.write("")
    _eeat_checklist(meta)

    st.write("")
    _diagnostico_seo(meta, periodo)

    st.write("")
    _notas_destacadas(df_notas, slug, meta["autor_original"])
