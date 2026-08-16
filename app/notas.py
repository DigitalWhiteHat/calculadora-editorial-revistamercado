"""Vista Notas — buscador/listado de todas las notas reales del periodo."""

import streamlit as st

import calculos as calc


def render(df_notas):
    st.subheader("Todas las notas del periodo")
    st.caption(f"{len(df_notas)} notas reales del periodo con autor identificado. "
               "Filtra por periodista, sección o canal, o busca por palabra clave del título.")

    col_buscar, col_periodista, col_seccion, col_canal = st.columns([2, 1, 1, 1])
    with col_buscar:
        buscar = st.text_input("Buscar en el título", placeholder="ej. Petro, Mundial, Espriella...")
    with col_periodista:
        periodistas = ["Todos"] + sorted(df_notas["periodista"].unique().tolist())
        f_periodista = st.selectbox("Periodista", periodistas)
    with col_seccion:
        secciones = ["Todas"] + sorted(df_notas["seccion"].unique().tolist())
        f_seccion = st.selectbox("Sección", secciones)
    with col_canal:
        canales = ["Todos"] + sorted(df_notas["canal_dominante"].dropna().unique().tolist())
        f_canal = st.selectbox("Canal", canales)

    vista = df_notas.copy()
    if buscar:
        vista = vista[vista["titulo"].str.contains(buscar, case=False, na=False)]
    if f_periodista != "Todos":
        vista = vista[vista["periodista"] == f_periodista]
    if f_seccion != "Todas":
        vista = vista[vista["seccion"] == f_seccion]
    if f_canal != "Todos":
        vista = vista[vista["canal_dominante"] == f_canal]

    vista = vista.sort_values("clics", ascending=False)
    st.caption(f"{len(vista)} notas encontradas · {calc.formatear_numero(vista['clics'].sum())} de tráfico combinado")

    tabla = vista.copy()
    tabla["trafico_txt"] = tabla["clics"].apply(calc.formatear_numero)
    tabla["posicion_txt"] = tabla["posicion_promedio"].apply(lambda p: f"{p:.0f}" if p == p else "s/d")
    tabla["seo_txt"] = tabla.apply(
        lambda r: f"{r['pct_cumplimiento']:.0f}%" if r["pct_cumplimiento"] == r["pct_cumplimiento"] else "sin evaluar",
        axis=1)

    columnas = ["titulo", "periodista", "seccion", "trafico_txt", "canal_dominante", "posicion_txt", "semaforo", "seo_txt"]
    st.dataframe(
        tabla[columnas], hide_index=True, width="stretch", height=560,
        column_config={
            "titulo": st.column_config.TextColumn("Título", width="large"),
            "periodista": st.column_config.TextColumn("Periodista", width="medium"),
            "seccion": st.column_config.TextColumn("Sección", width="small"),
            "trafico_txt": st.column_config.TextColumn("Tráfico", width="small"),
            "canal_dominante": st.column_config.TextColumn("Canal", width="small"),
            "posicion_txt": st.column_config.TextColumn("Posición Google", width="small"),
            "semaforo": st.column_config.TextColumn("SEO", width="small"),
            "seo_txt": st.column_config.TextColumn("% cumplimiento", width="small"),
        },
    )
