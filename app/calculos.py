"""
Calculadora de Periodistas — lógica de datos y fórmulas.
Fase demo: datos simulados con numpy (seed fija) siguiendo el esquema de
snapshot_semanal descrito en el traspaso. Se reemplaza por carga real
(GSC + GA4 + Contenido) en una fase posterior.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

MESES_ABREV = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

N_SEMANAS_HISTORIAL = 16
SEMANA_MAS_RECIENTE = date(2024, 5, 20)  # lunes de la última semana del histórico demo

SECCIONES_TRAFICO_MENSUAL = {
    "Economía": 180_000,
    "Deportes": 620_000,
    "Actualidad": 310_000,
    "Política": 95_000,
    "Estilo de vida": 145_000,
    "Tecnología": 15_000,
    "Opinión": 12_000,
    "Internacional": 8_500,
}

PERIODISTAS = [
    dict(slug="maria-belen-torres", nombre="María Belén Torres", seccion="Economía",
         beat="Macroeconomía y Finanzas Públicas", tema_principal="Inflación en Colombia",
         ingreso=date(2022, 3, 15), color="#3457D5", canal="Search",
         base_clics=22_000, crecimiento=1.055, calidad=0.90),
    dict(slug="carlos-velez", nombre="Carlos Vélez", seccion="Deportes",
         beat="Fútbol colombiano y selección", tema_principal="Eliminatorias Mundial 2026",
         ingreso=date(2021, 7, 1), color="#16A34A", canal="Discover",
         base_clics=26_000, crecimiento=1.020, calidad=0.80),
    dict(slug="laura-mendez", nombre="Laura Méndez", seccion="Actualidad",
         beat="Seguridad y orden público", tema_principal="Paro armado en el Catatumbo",
         ingreso=date(2020, 11, 10), color="#0EA5E9", canal="Search",
         base_clics=18_000, crecimiento=1.006, calidad=0.78),
    dict(slug="andres-gomez", nombre="Andrés Gómez", seccion="Política",
         beat="Congreso y reforma laboral", tema_principal="Reforma laboral 2024",
         ingreso=date(2023, 1, 20), color="#8B5CF6", canal="News",
         base_clics=14_000, crecimiento=1.000, calidad=0.62),
    dict(slug="sofia-ramirez", nombre="Sofía Ramírez", seccion="Estilo de vida",
         beat="Tendencias y bienestar", tema_principal="Rutinas de bienestar 2024",
         ingreso=date(2022, 9, 5), color="#F59E0B", canal="Discover",
         base_clics=12_500, crecimiento=0.990, calidad=0.66),
    dict(slug="javier-ortiz", nombre="Javier Ortiz", seccion="Tecnología",
         beat="Gadgets y apps", tema_principal="Inteligencia artificial en Colombia",
         ingreso=date(2023, 6, 1), color="#DC2626", canal="Search",
         base_clics=10_000, crecimiento=0.940, calidad=0.40),
    dict(slug="paula-herrera", nombre="Paula Herrera", seccion="Opinión",
         beat="Columnas de coyuntura", tema_principal="Coyuntura política nacional",
         ingreso=date(2021, 2, 15), color="#DC2626", canal="News",
         base_clics=7_000, crecimiento=0.960, calidad=0.35),
    dict(slug="diego-paredes", nombre="Diego Paredes", seccion="Internacional",
         beat="Latinoamérica y Estados Unidos", tema_principal="Elecciones EE.UU. 2024",
         ingreso=date(2023, 10, 1), color="#DC2626", canal="Discover",
         base_clics=4_500, crecimiento=0.950, calidad=0.34),
]

TEMAS_POR_PERIODISTA = {
    "maria-belen-torres": ["la inflación de mayo", "la decisión del BanRep", "el dólar en Colombia",
                           "el IPC de abril", "la reforma tributaria", "el salario mínimo 2025",
                           "las proyecciones del BanRep", "las perspectivas de la inflación"],
    "carlos-velez": ["las Eliminatorias", "la Selección Colombia", "el partido ante Brasil",
                     "el nuevo técnico", "la lista de convocados", "la Copa América",
                     "el estreno de James", "el sorteo del Mundial 2026"],
    "laura-mendez": ["el paro armado en el Catatumbo", "el nuevo consejo de seguridad",
                     "los desplazamientos en Norte de Santander", "la ofensiva militar",
                     "las cifras de homicidios", "el cese al fuego"],
    "andres-gomez": ["la reforma laboral", "el debate en el Congreso", "la ponencia radicada",
                     "la reacción de los gremios", "la votación en comisión séptima",
                     "el pulso entre Gobierno y oposición"],
    "sofia-ramirez": ["las rutinas de bienestar", "el nuevo hábito viral", "la tendencia wellness",
                      "el reto de 21 días", "la rutina matutina", "el minimalismo digital"],
    "javier-ortiz": ["la inteligencia artificial en Colombia", "el nuevo plegable", "ChatGPT en el trabajo",
                     "los mejores gadgets del mes", "la app que arrasa en descargas",
                     "la carrera por los chips"],
    "paula-herrera": ["la coyuntura política nacional", "el pulso electoral", "la encuesta de opinión",
                      "el debate en redes", "la polarización", "el balance del cuatrienio"],
    "diego-paredes": ["las elecciones en EE.UU.", "el debate presidencial", "la política migratoria",
                      "la relación con Colombia", "el mercado tras la elección", "la Casa Blanca"],
}

NOTA_TITULO_TEMPLATES = [
    "{tema}: lo que se sabe hasta ahora",
    "¿Qué significa {tema} para los colombianos?",
    "5 claves para entender {tema}",
    "{tema}: la reacción de los expertos",
    "Todo sobre {tema} en un solo lugar",
    "{tema}: cronología de los hechos",
    "Lo que viene después de {tema}",
    "{tema}: preguntas y respuestas",
    "{tema}, en cifras",
    "Así impacta {tema} al bolsillo de los colombianos",
]

NOTAS_EDITORIALES = [
    dict(slug="maria-belen-torres", fecha=date(2024, 5, 24), editor="Leandro Méndez",
         tipo="REVISAR", texto="Revisar uso de IA en 2 notas (sin edición humana).",
         notas=["22 may — Proyecciones del BanRep: ¿qué esperar en junio?",
                "21 may — Perspectivas de la inflación en Colombia para 2024"],
         detalle="Verificar fuentes, atribución y aporte propio. Ajustar titular si es necesario."),
    dict(slug="javier-ortiz", fecha=date(2024, 5, 22), editor="Leandro Méndez",
         tipo="ALERTA", texto="5 notas marcadas para revisión por caída sostenida de eficiencia.",
         notas=["20 may — Los mejores plegables de 2024, ¿vale la pena esperar?"],
         detalle="Agendar 1:1 con Javier para revisar enfoque de la sección Tecnología."),
]


def abreviar_fecha(d: date) -> str:
    return f"{d.day} {MESES_ABREV[d.month - 1]}"


def categoria_dificultad(trafico_mensual: float):
    if trafico_mensual > 500_000:
        return "Fácil", 0.8
    if trafico_mensual >= 20_000:
        return "Media", 1.0
    return "Difícil", 1.3


def formatear_numero(n: float) -> str:
    n = float(n)
    if np.isnan(n):
        return "— sin dato"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.0f}K"
    return f"{n:.0f}"


def formatear_tiempo(segundos: float) -> str:
    segundos = max(0, int(round(segundos)))
    return f"{segundos // 60}:{segundos % 60:02d} min"


def formatear_pct(valor: float, decimales: int = 0) -> str:
    return f"{valor:.{decimales}f}%"


def formatear_delta_pct(actual: float, anterior: float, decimales: int = 0) -> str | None:
    if anterior in (0, None) or pd.isna(anterior):
        return None
    delta = (actual - anterior) / abs(anterior) * 100
    signo = "+" if delta >= 0 else ""
    return f"{signo}{delta:.{decimales}f}%"


@st.cache_data
def generar_semanas() -> pd.DataFrame:
    inicio = SEMANA_MAS_RECIENTE - timedelta(weeks=N_SEMANAS_HISTORIAL - 1)
    fechas = [inicio + timedelta(weeks=i) for i in range(N_SEMANAS_HISTORIAL)]
    return pd.DataFrame({
        "semana_num": range(1, N_SEMANAS_HISTORIAL + 1),
        "semana_inicio": pd.to_datetime(fechas),
        "semana_fin": pd.to_datetime([f + timedelta(days=6) for f in fechas]),
        "semana_label": [abreviar_fecha(f) for f in fechas],
    })


@st.cache_data
def generar_snapshot_semanal() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    semanas = generar_semanas()
    filas = []

    for p in PERIODISTAS:
        categoria, ajuste = categoria_dificultad(SECCIONES_TRAFICO_MENSUAL[p["seccion"]])
        clics_base = p["base_clics"] / (p["crecimiento"] ** (N_SEMANAS_HISTORIAL - 10))
        calidad = p["calidad"]
        notas_totales_periodo = max(12, int(round(clics_base / 900)))

        for i, semana in semanas.iterrows():
            crecimiento_acum = p["crecimiento"] ** i
            ruido = rng.normal(1.0, 0.07)
            clics = max(200, clics_base * crecimiento_acum * ruido)
            impresiones = clics / max(0.015, rng.normal(0.045 + calidad * 0.05, 0.006))
            ctr = clics / impresiones
            notas = max(1, int(rng.poisson(max(0.5, notas_totales_periodo / N_SEMANAS_HISTORIAL))))
            posicion_promedio = max(1.0, 32 - calidad * 22 - (crecimiento_acum - 1) * 8 + rng.normal(0, 1.2))
            tiempo_pagina_seg = max(25, rng.normal(60 + calidad * 130, 12))
            scroll_pct = float(np.clip(rng.normal(40 + calidad * 45, 6), 15, 98))
            rebote_pct = float(np.clip(rng.normal(72 - calidad * 35, 5), 20, 90))
            temas_propios_pct = float(np.clip(rng.normal(35 + calidad * 45, 8), 5, 95))
            canibalizacion_pct = float(np.clip(rng.normal(10 - calidad * 8, 3), 0, 25))
            palabras_promedio = max(250, rng.normal(500 + calidad * 500, 60))
            notas_verde = int(round(notas * np.clip(rng.normal(0.35 + calidad * 0.55, 0.1), 0, 1)))
            notas_verde = min(notas, notas_verde)
            resto = notas - notas_verde
            notas_amarillo = int(round(resto * 0.6))
            notas_rojo = resto - notas_amarillo
            notas_top10 = int(round(notas * np.clip(rng.normal(0.15 + calidad * 0.45, 0.1), 0, 1)))
            flags_ia = int(rng.poisson(0.35 if calidad > 0.6 else 1.1))
            trafico_ajustado = clics * ajuste

            filas.append(dict(
                slug=p["slug"], periodista=p["nombre"], seccion=p["seccion"], beat=p["beat"],
                canal_dominante=p["canal"], tema_principal=p["tema_principal"],
                semana_num=semana["semana_num"], semana_inicio=semana["semana_inicio"],
                semana_label=semana["semana_label"],
                notas=notas, clics=clics, impresiones=impresiones, ctr=ctr,
                posicion_promedio=posicion_promedio, tiempo_pagina_seg=tiempo_pagina_seg,
                scroll_pct=scroll_pct, rebote_pct=rebote_pct,
                pct_canal_dominante=float(np.clip(rng.normal(55 + calidad * 25, 6), 40, 92)),
                temas_propios_pct=temas_propios_pct, canibalizacion_pct=canibalizacion_pct,
                palabras_promedio=palabras_promedio,
                notas_verde=notas_verde, notas_amarillo=max(0, notas_amarillo),
                notas_rojo=max(0, notas_rojo), notas_top10=min(notas, notas_top10),
                flags_ia=flags_ia, dificultad_categoria=categoria, dificultad_ajuste=ajuste,
                trafico_ajustado=trafico_ajustado,
            ))

    df = pd.DataFrame(filas)
    df["ctr_esperado"] = 1.0 / np.clip(df["posicion_promedio"], 1, None) ** 0.35
    ratio = df["ctr"] / df["ctr_esperado"]
    df["ctr_indice"] = ratio / ratio.mean()

    medianas_semanales = df.groupby("semana_num")["trafico_ajustado"].median()
    df["eficiencia_normalizada"] = df.apply(
        lambda r: 100 * r["trafico_ajustado"] / medianas_semanales.loc[r["semana_num"]], axis=1
    )
    df["notas_facil"] = np.where(df["dificultad_categoria"] == "Fácil", df["notas"], 0)
    df["notas_dificil"] = np.where(df["dificultad_categoria"] == "Difícil", df["notas"], 0)
    df["notas_media"] = np.where(df["dificultad_categoria"] == "Media", df["notas"], 0)
    return df


@st.cache_data
def generar_notas() -> pd.DataFrame:
    """Notas individuales (título, fecha, clics) simuladas a partir del snapshot semanal,
    para poder mostrar cuáles notas concretas originaron el tráfico agregado de cada periodista."""
    rng = np.random.default_rng(7)
    snapshot = generar_snapshot_semanal()
    filas = []

    for p in PERIODISTAS:
        temas = TEMAS_POR_PERIODISTA[p["slug"]]
        sub = snapshot[snapshot["slug"] == p["slug"]]
        for _, semana_row in sub.iterrows():
            n_notas = int(semana_row["notas"])
            if n_notas <= 0:
                continue
            pesos = rng.dirichlet(np.full(n_notas, 0.6))
            pesos = np.sort(pesos)[::-1]
            for i in range(n_notas):
                plantilla = rng.choice(NOTA_TITULO_TEMPLATES)
                tema = rng.choice(temas)
                titulo = plantilla.format(tema=tema).replace("de el ", "del ")
                titulo = titulo[0].upper() + titulo[1:]
                dia_offset = int(rng.integers(0, 7))
                fecha_publicacion = semana_row["semana_inicio"] + timedelta(days=dia_offset)
                filas.append(dict(
                    slug=p["slug"], periodista=p["nombre"], titulo=titulo,
                    seccion=p["seccion"], fecha_publicacion=fecha_publicacion,
                    semana_num=semana_row["semana_num"],
                    clics=max(30, semana_row["clics"] * pesos[i]),
                    posicion_promedio=max(1.0, semana_row["posicion_promedio"] + rng.normal(0, 3)),
                ))

    df = pd.DataFrame(filas)
    df["semaforo"] = rng.choice(["🟢", "🟡", "🔴"], size=len(df), p=[0.55, 0.3, 0.15])
    return df


def periodo_anterior_equivalente(fecha_ini: date, fecha_fin: date):
    duracion = (fecha_fin - fecha_ini).days + 1
    fin_anterior = fecha_ini - timedelta(days=1)
    ini_anterior = fin_anterior - timedelta(days=duracion - 1)
    return ini_anterior, fin_anterior


def filtrar_rango(df: pd.DataFrame, fecha_ini: date, fecha_fin: date) -> pd.DataFrame:
    mask = (df["semana_inicio"] >= pd.Timestamp(fecha_ini)) & (df["semana_inicio"] <= pd.Timestamp(fecha_fin))
    return df.loc[mask].copy()


def notas_destacadas(df_notas: pd.DataFrame, slug: str, fecha_ini: date, fecha_fin: date, top_n: int = 10) -> pd.DataFrame:
    mask = (
        (df_notas["slug"] == slug)
        & (df_notas["fecha_publicacion"] >= pd.Timestamp(fecha_ini))
        & (df_notas["fecha_publicacion"] <= pd.Timestamp(fecha_fin))
    )
    notas = df_notas.loc[mask].sort_values("clics", ascending=False).reset_index(drop=True)
    if notas.empty:
        return notas
    notas["pct_del_total"] = 100 * notas["clics"] / notas["clics"].sum()
    return notas.head(top_n)


def _agregar_periodista(g: pd.DataFrame) -> pd.Series:
    total_notas = g["notas"].sum()
    return pd.Series(dict(
        slug=g.name, periodista=g["periodista"].iloc[0], seccion=g["seccion"].iloc[0],
        beat=g["beat"].iloc[0], canal_dominante=g["canal_dominante"].iloc[0],
        tema_principal=g["tema_principal"].iloc[0],
        dificultad_categoria=g["dificultad_categoria"].iloc[0], dificultad_ajuste=g["dificultad_ajuste"].iloc[0],
        notas=total_notas, clics=g["clics"].sum(), impresiones=g["impresiones"].sum(),
        ctr=g["clics"].sum() / max(1, g["impresiones"].sum()),
        ctr_indice=g["ctr_indice"].mean(),
        posicion_promedio=np.average(g["posicion_promedio"], weights=g["notas"].clip(lower=1)),
        tiempo_pagina_seg=np.average(g["tiempo_pagina_seg"], weights=g["notas"].clip(lower=1)),
        rebote_pct=np.average(g["rebote_pct"], weights=g["notas"].clip(lower=1)),
        pct_canal_dominante=g["pct_canal_dominante"].mean(),
        temas_propios_pct=g["temas_propios_pct"].mean(),
        canibalizacion_pct=g["canibalizacion_pct"].mean(),
        palabras_promedio=g["palabras_promedio"].mean(),
        notas_verde=g["notas_verde"].sum(), notas_amarillo=g["notas_amarillo"].sum(),
        notas_rojo=g["notas_rojo"].sum(), notas_top10=g["notas_top10"].sum(),
        flags_ia=g["flags_ia"].sum(),
        notas_facil=g["notas_facil"].sum(), notas_media=g["notas_media"].sum(),
        notas_dificil=g["notas_dificil"].sum(),
        trafico_ajustado=g["trafico_ajustado"].sum(),
        eficiencia_normalizada=g.sort_values("semana_num")["eficiencia_normalizada"].iloc[-1],
        semanas_bajo_umbral=int((g.sort_values("semana_num")["eficiencia_normalizada"].tail(4) < 80).sum()),
    ))


def agregar_periodo(df: pd.DataFrame, fecha_ini: date, fecha_fin: date) -> pd.DataFrame:
    rango = filtrar_rango(df, fecha_ini, fecha_fin)
    if rango.empty:
        return rango
    agg = rango.groupby("slug", group_keys=False).apply(_agregar_periodista)
    agg["semaforo_verde_pct"] = 100 * agg["notas_verde"] / agg["notas"].clip(lower=1)
    agg["pct_trafico_total"] = 100 * agg["clics"] / agg["clics"].sum()
    agg["en_alerta"] = agg["semanas_bajo_umbral"] >= 4
    return agg.reset_index(drop=True)


def comparar_periodos(df: pd.DataFrame, fecha_ini: date, fecha_fin: date) -> pd.DataFrame:
    actual = agregar_periodo(df, fecha_ini, fecha_fin)
    ini_ant, fin_ant = periodo_anterior_equivalente(fecha_ini, fecha_fin)
    anterior = agregar_periodo(df, ini_ant, fin_ant)
    if anterior.empty:
        for col in ["notas", "clics", "eficiencia_normalizada", "ctr_indice", "tiempo_pagina_seg",
                    "canibalizacion_pct", "temas_propios_pct", "palabras_promedio", "semaforo_verde_pct",
                    "posicion_promedio", "notas_top10"]:
            actual[f"{col}_anterior"] = np.nan
        return actual
    anterior = anterior.set_index("slug")
    for col in ["notas", "clics", "eficiencia_normalizada", "ctr_indice", "tiempo_pagina_seg",
                "canibalizacion_pct", "temas_propios_pct", "palabras_promedio", "semaforo_verde_pct",
                "posicion_promedio", "notas_top10"]:
        actual[f"{col}_anterior"] = actual["slug"].map(anterior[col])
    return actual


def estado_label(eficiencia: float, en_alerta: bool) -> tuple[str, str]:
    if en_alerta:
        return "EN ALERTA", "red"
    if eficiencia >= 120:
        return "SOBRE MEDIANA", "green"
    return "EN RANGO", "blue"
