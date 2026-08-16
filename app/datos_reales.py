"""Carga los datos reales de revistamercado.do (GA4 + Search Console + scraping
+ semáforo SEO) y los adapta al esquema de columnas que espera la UI
(general.py / individual.py / notas.py / alertas.py).

Dos tiers — MIGRACION-DESDE-COLOMBIACOM.md §2:
- **Tier 2 (julio 2026, "completo"):** censo COMPLETO — semáforo SEO de las 14
  reglas automatizadas sobre ~957 notas, autor real de cada una vía JSON-LD.
- **Tier 1 (enero-junio 2026, "histórico"):** tráfico REAL y COMPLETO por mes
  (GA4+GSC, sin colapsar entre meses), pero el semáforo SEO ahí es una MUESTRA
  de hasta 12 notas/autor/mes (autorizado explícitamente por Edwin para no
  scrapear miles de páginas históricas) — se declara SIEMPRE como muestra en
  la UI, nunca como censo.

Ambos tiers producen el MISMO esquema de columnas (`_agregar_periodistas` es
compartida) — lo que cambia es de dónde sale cada columna, no su forma.

MUESTRA en ambos tiers, no censo de autoría: revistamercado.do no tiene
archivo de autor navegable (/post_author/{slug}/ del JSON-LD da 404 real,
verificado 2026-08-05) — la cobertura es la muestra de mayor tráfico con autor
extraído en vivo del JSON-LD de cada nota, nunca una unión con un archivo de
autor como en Colombia.com. Esto subestima a quien escribe piezas modestas no
virales.

Decisiones de autoría confirmadas por Edwin (2026-08-05):
- Se cuentan como periodistas: Edwin Lozada, Agatha Thomas, Miranda Cross,
  "pferreras" y cualquier otro username de WP que aparezca como autor real.
- El contenido sindicado (Fortune, agencia EFE bajo "Miguel Vega") SÍ cuenta
  para el autor que lo firma — ellos se encargan de esa traducción/edición.
- Solo se excluyen: "revistamercado" (byline genérico de staff, no es una
  persona) y "SIN_AUTOR" (404 o página sin JSON-LD de artículo).

Métricas sin fuente real disponible en esta versión (marcadas explícitamente,
nunca inventadas): rebote_pct, temas_propios_pct, flags_ia, ctr (bruto).
"""

import glob
import re
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

DATA_DIR = "data"
SUFIJO_JULIO = "2026-07-01_2026-07-31"
EXCLUIR_AUTOR = {"revistamercado", "SIN_AUTOR"}

MESES_LABEL = {"01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril", "05": "Mayo", "06": "Junio"}
MESES_DIAS = {"01": 31, "02": 28, "03": 31, "04": 30, "05": 31, "06": 30}
MESES_TODOS = {**MESES_LABEL, "07": "Julio", "08": "Agosto", "09": "Septiembre",
                "10": "Octubre", "11": "Noviembre", "12": "Diciembre"}


def _detectar_mes_parcial() -> str | None:
    """Mes en curso, aún sin cerrar -- detectado por la presencia de
    data/periodistas_<AAAA-MM>.csv (lo produce data/construir_periodistas_mes.py,
    corrido periódicamente sobre el export más reciente de Drive). Si hay más
    de uno (no debería, pero por si acaso), se queda con el más reciente por
    orden lexicográfico AAAA-MM. Ningún cambio de código hace falta el mes que
    entra: basta con que la rutina programada deje el CSV nuevo."""
    archivos = sorted(glob.glob(f"{DATA_DIR}/periodistas_????-??.csv"))
    if not archivos:
        return None
    return archivos[-1].split("periodistas_")[-1].replace(".csv", "")


MES_PARCIAL = _detectar_mes_parcial()

PERIODOS: dict[str, dict] = {
    "2026-07": {"tipo": "completo", "label": "Julio 2026 · censo completo"},
}
for _m, _lbl in MESES_LABEL.items():
    PERIODOS[f"2026-{_m}"] = {"tipo": "historico", "mes": _m, "label": f"{_lbl} 2026 · muestra"}

if MES_PARCIAL and MES_PARCIAL not in PERIODOS:
    _anio_p, _mes_p = MES_PARCIAL.split("-")
    PERIODOS[MES_PARCIAL] = {
        "tipo": "parcial",
        "label": f"{MESES_TODOS.get(_mes_p, _mes_p)} {_anio_p} (parcial)",
    }

# El mes en curso (si ya hay datos parciales para él) es el default y el
# primero del selector -- misma UX que Colombia.com: se abre mostrando lo más
# fresco, no un censo antiguo. Si todavía no existe, julio (censo completo)
# sigue siendo el default.
PERIODO_DEFAULT = MES_PARCIAL if MES_PARCIAL else "2026-07"
ORDEN_PERIODOS = ([MES_PARCIAL] if MES_PARCIAL else []) + [
    "2026-07", "2026-06", "2026-05", "2026-04", "2026-03", "2026-02", "2026-01"]


def periodo_fechas(periodo: str = PERIODO_DEFAULT) -> tuple[date, date]:
    info = PERIODOS[periodo]
    if info["tipo"] == "completo":
        return date(2026, 7, 1), date(2026, 7, 31)
    if info["tipo"] == "parcial":
        anio, mes = periodo.split("-")
        return date(int(anio), int(mes), 1), date.today()
    mes = int(info["mes"])
    return date(2026, mes, 1), date(2026, mes, MESES_DIAS[info["mes"]])


def es_periodo_completo(periodo: str = PERIODO_DEFAULT) -> bool:
    return PERIODOS[periodo]["tipo"] == "completo"


def slugify(nombre: str) -> str:
    s = str(nombre).lower()
    s = s.translate(str.maketrans("áéíóúñ", "aeioun"))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


PREFIJOS_NO_ARTICULO = ("/category/", "/tag/", "/wp-", "/author/", "/post_author/",
                        "/page/", "/feed", "/buscar", "/search", "/carrito", "/checkout",
                        "/p/", "/subscribers-login", "/suscribe", "/new-suscribe",
                        "/events/", "/event-detail/", "/form-", "/confirmar-asistencia")


def _parece_articulo(ruta: pd.Series) -> pd.Series:
    """Mismo filtro que data/extraer_autores_muestra.py::parece_articulo(),
    duplicado a propósito (no se cruzan imports entre app/ y data/) — para que
    "tráfico real por sección" (dificultad, panorama de Secciones) no se
    contamine con páginas de utilidad (tags, checkout, wp-content, etc.) que
    aparecen en el export crudo de GA4 pero no son contenido editorial."""
    ok = ruta.str.startswith("/", na=False)
    for p in PREFIJOS_NO_ARTICULO:
        ok &= ~ruta.str.startswith(p, na=False)
    segmentos = ruta.str.strip("/").str.split("/")
    n_seg = segmentos.apply(len)
    ok &= n_seg.isin([2, 3])
    ultimo_len = segmentos.apply(lambda p: len(p[-1]) if p else 0)
    ok &= ultimo_len > 12
    return ok


def _extraer_seccion(ruta: pd.Series) -> pd.Series:
    """El primer segmento de la URL solo (ej. "empresas") es DEMASIADO
    genérico en revistamercado.do: ahí es donde de verdad trabajan los
    periodistas es en la SUBSECCIÓN — "empresas/sport-business",
    "money-invest/daily-news", "technology/devices" son beats reales y
    distintos entre sí, no la misma cosa. Se usa el segmento 2 de la URL
    cuando existe (rutas con 3+ segmentos); si la URL es plana (2 segmentos,
    sección/slug) se queda con el segmento 1 solo — no todas las secciones
    tienen subsección real."""
    partes = ruta.str.strip("/").str.split("/")
    seg1 = partes.str[0]
    seg2 = partes.apply(lambda p: p[1] if len(p) >= 3 else None)
    return seg1.where(seg2.isna(), seg1 + "/" + seg2)


def seccion_label(seccion_raw: str) -> str:
    """Etiqueta legible para una seccion_raw ("empresas/sport-business" ->
    "Sport Business · Empresas"); si no tiene subsección, solo el nombre."""
    if not seccion_raw:
        return ""
    partes = str(seccion_raw).split("/")
    if len(partes) == 2:
        return f"{partes[1].replace('-', ' ').title()} · {partes[0].replace('-', ' ').title()}"
    return partes[0].replace("-", " ").title()


def _dificultad(trafico_seccion: float):
    if trafico_seccion > 500_000:
        return "Fácil", 0.8
    if trafico_seccion >= 20_000:
        return "Media", 1.0
    return "Difícil", 1.3


def _color_semaforo(pct) -> str | None:
    if pd.isna(pct):
        return None
    if pct >= 80:
        return "🟢"
    if pct >= 60:
        return "🟡"
    return "🔴"


@st.cache_data
def _cargar_crudo_completo():
    """Tier 2 — julio 2026, censo completo. Cruza notas_con_autor (autor real
    vía JSON-LD) + procesado (GA4+GSC por URL) + semaforo_notas (14 ítems ya
    evaluados sobre TODAS las notas) + semaforo_raw (palabras_body)."""
    notas = pd.read_csv(f"{DATA_DIR}/notas_con_autor_{SUFIJO_JULIO}.csv")
    notas = notas[~notas["autor"].isin(EXCLUIR_AUTOR)].reset_index(drop=True)
    # "vistas" en este CSV es una foto vieja de cuando se armó la muestra de
    # autores (extraer_autores_muestra.py la calculó directo del export de
    # GA4 de ESE momento) — se descarta a propósito para que el tráfico real
    # SIEMPRE salga de `procesado` (la fuente única y actualizada), nunca de
    # una copia congelada. Bug real encontrado 2026-08-09: antes de este fix,
    # el merge no traía "vistas" de `procesado`, así que el censo de julio
    # quedó meses usando esta cifra vieja sin que nadie lo notara (coincidía
    # con el `procesado` de entonces por casualidad, hasta que cambió la
    # métrica de origen de Vistas a Sesiones y las dos fuentes divergieron).
    notas = notas.drop(columns=["vistas"], errors="ignore")

    procesado = pd.read_csv(f"{DATA_DIR}/procesado_{SUFIJO_JULIO}.csv")
    procesado["seccion_raw"] = _extraer_seccion(procesado["ruta"])

    semaforo = pd.read_csv(f"{DATA_DIR}/semaforo_notas_{SUFIJO_JULIO}.csv")
    raw = pd.read_csv(f"{DATA_DIR}/semaforo_raw_{SUFIJO_JULIO}.csv")

    notas = notas.merge(
        procesado[["ruta", "vistas", "tiempo_interaccion_seg", "clics_search", "impresiones_search",
                   "posicion", "clics_discover", "impresiones_discover", "clics_news",
                   "impresiones_news", "canal_dominante", "pct_canal_dominante", "seccion_raw"]],
        on="ruta", how="left",
    )
    notas = notas.merge(semaforo[["ruta", "pct_cumplimiento", "semaforo"]], on="ruta", how="left")
    notas = notas.merge(raw[["ruta", "palabras_body"]], on="ruta", how="left")
    return notas, procesado


@st.cache_data
def _cargar_crudo_historico(mes: str):
    """Tier 1 — un mes de ene-jun 2026. Tráfico REAL y completo (GA4+GSC por
    ruta, sin colapsar entre meses) unido al mapa ruta->autor FIJO; el semáforo
    SEO ahí SÍ es una muestra (hasta 12 notas/autor/mes) — la mayoría de las
    filas quedan con pct_cumplimiento/semaforo/palabras_body en NaN a
    propósito, porque esa nota concreta no fue parte de la muestra scrapeada."""
    procesado = pd.read_csv(f"{DATA_DIR}/procesado_historico_2026-01-01_2026-06-30.csv")
    procesado["mes"] = procesado["mes"].astype(int).astype(str).str.zfill(2)
    procesado_mes = procesado[procesado["mes"] == mes].drop(columns=["mes"]).copy()
    procesado_mes["seccion_raw"] = _extraer_seccion(procesado_mes["ruta"])

    mapa = pd.read_csv(f"{DATA_DIR}/mapa_autor_ruta.csv")
    mapa = mapa[~mapa["autor"].isin(EXCLUIR_AUTOR)]

    notas = procesado_mes.merge(mapa[["ruta", "autor", "titulo", "seccion", "fecha", "es_sindicado"]],
                                 on="ruta", how="inner")

    seo = pd.read_csv(f"{DATA_DIR}/semaforo_muestra_notas.csv")
    seo["mes"] = seo["mes"].astype(int).astype(str).str.zfill(2)
    seo_mes = seo[seo["mes"] == mes]
    notas = notas.merge(seo_mes[["ruta", "pct_cumplimiento"]], on="ruta", how="left")
    notas["semaforo"] = notas["pct_cumplimiento"].apply(_color_semaforo)

    raw_hist = pd.read_csv(f"{DATA_DIR}/semaforo_raw_historico.csv")[["ruta", "palabras_body"]]
    raw_jul = pd.read_csv(f"{DATA_DIR}/semaforo_raw_{SUFIJO_JULIO}.csv")[["ruta", "palabras_body"]]
    raw_todo = pd.concat([raw_hist, raw_jul]).drop_duplicates("ruta")
    notas = notas.merge(raw_todo, on="ruta", how="left")

    return notas, procesado_mes


@st.cache_data
def _cargar_crudo_parcial(mes: str):
    """Tier 'parcial' — mes en curso, todavía sin cerrar. Autor real vía
    JSON-LD (igual método que julio), pero scrapeado INCREMENTALMENTE por
    data/construir_notas_mes_actual.py (solo las notas nuevas de cada corrida,
    reusando data/mapa_autor_ruta.csv como caché) — no hay semáforo SEO ni
    EEAT para este tier todavía: eso solo se calcula en el cierre mensual
    (data/cerrar_mes.py), no en cada refresco del mes en curso. Todas esas
    columnas quedan en NaN a propósito, mismo patrón que ya usa el Tier 1
    histórico cuando una nota no fue parte de la muestra scrapeada."""
    notas = pd.read_csv(f"{DATA_DIR}/notas_{mes}.csv")
    notas = notas[~notas["autor"].isin(EXCLUIR_AUTOR)].reset_index(drop=True)
    notas["seccion_raw"] = _extraer_seccion(notas["ruta"])
    notas["fecha"] = notas["fecha_real"]
    notas["es_sindicado"] = False
    for col in ["impresiones_discover", "impresiones_news", "tiempo_interaccion_seg",
                "canal_dominante", "pct_canal_dominante", "pct_cumplimiento", "semaforo", "palabras_body"]:
        notas[col] = np.nan

    raw_path = sorted(glob.glob(f"{DATA_DIR}/raw_historico/ga4_pages_screens_periodos_*.csv"))
    if raw_path:
        procesado = pd.read_csv(sorted(raw_path)[-1])
        procesado = procesado[procesado["periodo"] == "actual"].copy()
        procesado["ruta"] = (procesado["pagePath"]
                              .str.replace("https://www.revistamercado.do", "", regex=False)
                              .str.replace("https://revistamercado.do", "", regex=False)
                              .str.rstrip("/").replace("", "/"))
        procesado = procesado.groupby("ruta", as_index=False)["screenPageViews"].sum().rename(
            columns={"screenPageViews": "vistas"})
        procesado["seccion_raw"] = _extraer_seccion(procesado["ruta"])
        procesado = procesado.merge(
            notas[["ruta", "clics_search", "clics_discover", "clics_news"]], on="ruta", how="left")
        for col in ["clics_search", "clics_discover", "clics_news"]:
            procesado[col] = procesado[col].fillna(0)
    else:
        procesado = notas

    return notas, procesado


def _crudo(periodo: str):
    info = PERIODOS[periodo]
    if info["tipo"] == "completo":
        return _cargar_crudo_completo()
    if info["tipo"] == "parcial":
        return _cargar_crudo_parcial(periodo)
    return _cargar_crudo_historico(info["mes"])


@st.cache_data
def cargar_periodistas_meta(periodo: str = PERIODO_DEFAULT) -> list[dict]:
    notas, _ = _crudo(periodo)
    metas = []
    for autor, g in notas.groupby("autor"):
        seccion_raw_dom = g["seccion_raw"].value_counts().idxmax()
        top_secciones = [str(s).title() for s in g["seccion"].value_counts().head(3).index.tolist()]
        metas.append(dict(
            slug=slugify(autor), nombre=autor, autor_original=autor,
            seccion=top_secciones[0] if top_secciones else seccion_raw_dom.title(),
            seccion_raw=seccion_raw_dom,
            beat=", ".join(top_secciones),
        ))
    return sorted(metas, key=lambda m: m["nombre"])


@st.cache_data
def trafico_total_por_periodo() -> pd.DataFrame:
    """Tráfico TOTAL real reportado por GA4 cada periodo (ene-jul 2026), sin
    filtrar por clasificación de artículo — la cifra que de verdad reporta
    Analytics para todo el portal, para "Tendencia del portal" del Dashboard."""
    filas = []
    for periodo in reversed(ORDEN_PERIODOS):  # cronológico: ene -> jul
        _, procesado = _crudo(periodo)
        filas.append(dict(periodo=periodo, mes_label=MES_LABEL_LARGO[periodo], trafico=float(procesado["vistas"].sum())))
    return pd.DataFrame(filas)


@st.cache_data
def secciones_trafico_real(periodo: str = PERIODO_DEFAULT) -> dict:
    """Tráfico real por sección/subsección sobre TODO el export del periodo
    que parece contenido editorial (no solo la muestra con autor, pero SÍ
    excluyendo tags/checkout/wp-content/etc.) — para que la dificultad de
    sección refleje el sitio completo ESE mes, no ruido de páginas de
    utilidad."""
    _, procesado = _crudo(periodo)
    articulos = procesado[_parece_articulo(procesado["ruta"])]
    return articulos.groupby("seccion_raw")["vistas"].sum().to_dict()


@st.cache_data
def secciones_resumen_agregado() -> pd.DataFrame:
    """Tabla "Dificultad y canal por sección" del Dashboard — MIGRACION-DESDE-
    COLOMBIACOM.md §8: dato agregado de TODO lo que hay (jul completo + los 6
    meses históricos), no depende del periodo seleccionado arriba, para que la
    sección se pueda comparar sin tener que ir mes por mes."""
    _, proc_jul = _cargar_crudo_completo()
    bloques = [proc_jul[["ruta", "seccion_raw", "vistas", "clics_search", "clics_discover", "clics_news"]]]
    for mes in MESES_LABEL:
        _, proc_mes = _cargar_crudo_historico(mes)
        bloques.append(proc_mes[["ruta", "seccion_raw", "vistas", "clics_search", "clics_discover", "clics_news"]])
    todo = pd.concat(bloques, ignore_index=True)
    todo = todo[_parece_articulo(todo["ruta"])]

    agg = todo.groupby("seccion_raw").agg(
        vistas=("vistas", "sum"),
        clics_search=("clics_search", "sum"),
        clics_discover=("clics_discover", "sum"),
        clics_news=("clics_news", "sum"),
    ).reset_index()
    canales = agg[["clics_search", "clics_discover", "clics_news"]]
    total_canal = canales.sum(axis=1)
    agg["canal_dominante"] = canales.idxmax(axis=1).str.replace("clics_", "", regex=False).str.capitalize()
    agg.loc[total_canal == 0, "canal_dominante"] = "—"
    agg["pct_canal_dominante"] = (canales.max(axis=1) / total_canal.replace(0, float("nan")) * 100).round(1)
    agg[["dificultad_categoria", "dificultad_ajuste"]] = agg["vistas"].apply(
        lambda v: pd.Series(_dificultad(v)))
    # Cola larga real pero irrelevante: URLs sueltas de 1-2 vistas (posts
    # archivados pre-2026 con estructura de fecha /AAAA/MM/, entradas
    # huérfanas) que pasan el filtro de "parece artículo" pero no son una
    # sección editorial activa — sin volumen mínimo, la tabla es inusable.
    agg = agg[agg["vistas"] >= 1000]
    return agg.sort_values("vistas", ascending=False).reset_index(drop=True)


@st.cache_data
def canibalizacion_por_autor() -> dict:
    """Un solo cálculo global (no por mes) — se corrió sobre la muestra de
    julio con más densidad de notas por autor; se reutiliza para todos los
    periodos porque no hay canibalización mes-a-mes calculada todavía."""
    try:
        df = pd.read_csv(f"{DATA_DIR}/canibalizacion_periodistas.csv")
        return df.set_index("autor")["pct_canibalizacion"].to_dict()
    except FileNotFoundError:
        return {}


@st.cache_data
def cargar_notas(periodo: str = PERIODO_DEFAULT) -> pd.DataFrame:
    notas, _ = _crudo(periodo)
    df = notas.copy()
    df["slug"] = df["autor"].apply(slugify)
    df["periodista"] = df["autor"]
    df["seccion"] = df["seccion"].fillna("").apply(lambda s: str(s).title())
    df["fecha_publicacion"] = pd.to_datetime(df["fecha"], utc=True, errors="coerce").dt.tz_localize(None)
    df["semana_num"] = 1
    df["clics"] = df["vistas"]
    df["posicion_promedio"] = df["posicion"]
    df["canal_dominante"] = df["canal_dominante"].fillna("—").str.capitalize()
    df["semaforo"] = df["semaforo"].fillna("⚪")
    df["fuente"] = ("Censo completo jul-2026 (JSON-LD)" if es_periodo_completo(periodo)
                     else "Tráfico real del mes; SEO solo en la muestra scrapeada")
    return df[["slug", "periodista", "titulo", "seccion", "fecha_publicacion", "semana_num",
               "clics", "posicion_promedio", "canal_dominante", "semaforo", "pct_cumplimiento", "fuente"]]


def _agregar_periodistas(notas: pd.DataFrame, sec_traf: dict, canib: dict) -> pd.DataFrame:
    """Agregación por autor — COMPARTIDA entre los dos tiers. Lo único que
    cambia entre Tier 1 y Tier 2 es qué tan completas vienen `pct_cumplimiento`
    / `palabras_body` en el `notas` de entrada (censo vs. muestra); la lógica
    de agregación es la misma."""
    df = notas

    con_pos_global = df[df["posicion"].notna() & (df["clics_search"] > 0) & (df["impresiones_search"] > 0)].copy()
    con_pos_global["ctr"] = con_pos_global["clics_search"] / con_pos_global["impresiones_search"]
    con_pos_global["ctr_esperado"] = 1.0 / con_pos_global["posicion"].clip(lower=1) ** 0.35
    ratio_global = con_pos_global["ctr"] / con_pos_global["ctr_esperado"]
    con_pos_global["ctr_indice"] = ratio_global / ratio_global.mean()

    filas = []
    for autor, g in df.groupby("autor"):
        slug = slugify(autor)
        seccion_raw_dom = g["seccion_raw"].value_counts().idxmax()
        dif_categoria, dif_ajuste = _dificultad(sec_traf.get(seccion_raw_dom, 0))
        top_secciones = [str(s).title() for s in g["seccion"].value_counts().head(3).index.tolist()]

        clics_canal = g[["clics_search", "clics_discover", "clics_news"]].fillna(0).sum()
        total_canal = clics_canal.sum()
        canal_dominante = clics_canal.idxmax().replace("clics_", "").capitalize() if total_canal > 0 else "—"
        pct_canal_dominante = (clics_canal.max() / total_canal * 100) if total_canal > 0 else np.nan

        con_pos = con_pos_global[con_pos_global["autor"] == autor]
        if len(con_pos) > 0:
            ctr_indice_val = float(con_pos["ctr_indice"].mean())
            posicion_promedio = float(np.average(con_pos["posicion"], weights=con_pos["vistas"].clip(lower=1)))
            notas_top10 = int((con_pos["posicion"] <= 10).sum())
        else:
            ctr_indice_val = np.nan
            posicion_promedio = np.nan
            notas_top10 = 0

        dif_por_nota = g["seccion_raw"].map(lambda s: _dificultad(sec_traf.get(s, 0))[0])
        notas_facil = int((dif_por_nota == "Fácil").sum())
        notas_media = int((dif_por_nota == "Media").sum())
        notas_dificil = int((dif_por_nota == "Difícil").sum())

        n_verde = int((g["semaforo"] == "🟢").sum())
        n_amarillo = int((g["semaforo"] == "🟡").sum())
        n_rojo = int((g["semaforo"] == "🔴").sum())
        notas_seo_evaluadas = int(g["pct_cumplimiento"].notna().sum())
        pct_cumplimiento_prom = float(g["pct_cumplimiento"].mean()) if notas_seo_evaluadas else np.nan

        trafico_ajustado = float(g["vistas"].sum()) * dif_ajuste

        filas.append(dict(
            slug=slug, periodista=autor,
            seccion=top_secciones[0] if top_secciones else seccion_raw_dom.title(), seccion_raw=seccion_raw_dom,
            beat=", ".join(top_secciones),
            canal_dominante=canal_dominante, tema_principal=top_secciones[0] if top_secciones else "",
            dificultad_categoria=dif_categoria, dificultad_ajuste=dif_ajuste,
            notas=len(g), clics=float(g["vistas"].sum()),
            impresiones=float(g[["impresiones_search", "impresiones_discover", "impresiones_news"]].fillna(0).sum().sum()),
            ctr=np.nan, ctr_indice=ctr_indice_val,
            posicion_promedio=posicion_promedio,
            tiempo_pagina_seg=float(g["tiempo_interaccion_seg"].mean()),
            rebote_pct=np.nan,
            pct_canal_dominante=pct_canal_dominante,
            temas_propios_pct=np.nan, canibalizacion_pct=canib.get(autor, 0.0),
            palabras_promedio=float(g["palabras_body"].mean()) if g["palabras_body"].notna().any() else np.nan,
            notas_verde=n_verde, notas_amarillo=n_amarillo, notas_rojo=n_rojo,
            notas_seo_evaluadas=notas_seo_evaluadas,
            pct_cumplimiento_prom=pct_cumplimiento_prom,
            notas_top10=notas_top10, flags_ia=np.nan,
            notas_facil=notas_facil, notas_media=notas_media, notas_dificil=notas_dificil,
            trafico_ajustado=trafico_ajustado,
            semanas_bajo_umbral=0,
        ))

    tabla = pd.DataFrame(filas)
    mediana = tabla["trafico_ajustado"].median()
    tabla["eficiencia_normalizada"] = 100 * tabla["trafico_ajustado"] / mediana if mediana else 100.0
    tabla["semaforo_verde_pct"] = 100 * tabla["notas_verde"] / tabla["notas_seo_evaluadas"].clip(lower=1)
    tabla["pct_trafico_total"] = 100 * tabla["clics"] / tabla["clics"].sum()
    tabla["pct_notas_rojas"] = 100 * tabla["notas_rojo"] / tabla["notas_seo_evaluadas"].clip(lower=1)

    for col in ["notas", "clics", "eficiencia_normalizada", "ctr_indice", "tiempo_pagina_seg",
                "canibalizacion_pct", "temas_propios_pct", "palabras_promedio", "semaforo_verde_pct",
                "posicion_promedio", "notas_top10"]:
        tabla[f"{col}_anterior"] = np.nan

    tabla["alertas"] = tabla.apply(lambda r: generar_alertas_periodista(r), axis=1)
    tabla["en_alerta"] = tabla["alertas"].apply(lambda al: any(a["severidad"] == "CRÍTICO" for a in al))

    return tabla.reset_index(drop=True)


@st.cache_data
def cargar_periodistas(periodo: str = PERIODO_DEFAULT) -> pd.DataFrame:
    notas, _ = _crudo(periodo)
    sec_traf = secciones_trafico_real(periodo)
    canib = canibalizacion_por_autor()
    return _agregar_periodistas(notas, sec_traf, canib)


# Alertas de ESTADO ACTUAL (no requieren historial de varios meses — eso sigue
# bloqueado hasta acumular periodos). Se basan en señales que ya son reales y
# medibles con un solo mes: cumplimiento SEO, canibalización, CTR vs. esperado,
# eficiencia relativa al equipo.
def generar_alertas_periodista(fila) -> list:
    alertas = []

    def _add(tipo, severidad, mensaje):
        alertas.append({"tipo": tipo, "severidad": severidad, "mensaje": mensaje})

    pct = fila["pct_cumplimiento_prom"]
    if pd.notna(pct):
        if pct < 50:
            _add("SEO", "CRÍTICO", f"Cumplimiento SEO promedio muy bajo: {pct:.0f}% (14 ítems automatizados)")
        elif pct < 60:
            _add("SEO", "ATENCIÓN", f"Cumplimiento SEO promedio por debajo del equipo: {pct:.0f}%")

    pct_rojas = fila["pct_notas_rojas"]
    if pd.notna(pct_rojas):
        if pct_rojas > 40:
            _add("SEO", "CRÍTICO", f"{pct_rojas:.0f}% de sus notas evaluadas quedaron en semáforo 🔴")
        elif pct_rojas > 20:
            _add("SEO", "ATENCIÓN", f"{pct_rojas:.0f}% de sus notas evaluadas quedaron en semáforo 🔴")

    canib = fila["canibalizacion_pct"]
    if pd.notna(canib):
        if canib > 15:
            _add("Canibalización", "CRÍTICO", f"{canib:.0f}% de sus notas compiten por el mismo tema/entidad")
        elif canib > 8:
            _add("Canibalización", "ATENCIÓN", f"{canib:.0f}% de sus notas compiten por el mismo tema/entidad")

    ctr = fila["ctr_indice"]
    if pd.notna(ctr):
        if ctr < 0.6:
            _add("CTR", "CRÍTICO", f"CTR de titulares muy por debajo del esperado para su posición: {ctr:.2f}x")
        elif ctr < 0.8:
            _add("CTR", "ATENCIÓN", f"CTR de titulares por debajo del esperado: {ctr:.2f}x")

    efic = fila["eficiencia_normalizada"]
    if pd.notna(efic):
        if efic < 40:
            _add("Eficiencia", "CRÍTICO", f"Eficiencia muy por debajo del equipo: índice {efic:.0f} (mediana=100)")
        elif efic < 70:
            _add("Eficiencia", "ATENCIÓN", f"Eficiencia por debajo del equipo: índice {efic:.0f} (mediana=100)")

    return alertas


def periodista_por_slug(slug: str, periodo: str = PERIODO_DEFAULT) -> dict | None:
    for m in cargar_periodistas_meta(periodo):
        if m["slug"] == slug:
            return m
    return None


LABELS_ITEM_SEO = {
    "h1_70_170": "H1 editorial con longitud correcta (70-170 car.)",
    "title_50_65": "Title SEO optimizado (50-65 car.)",
    "meta_desc_150_170": "Meta descripción con largo correcto (150-170 car.)",
    "meta_desc_no_repite_h1": "Meta descripción no repite el H1",
    "primer_parrafo_180": "Primer párrafo responde de inmediato (≥180 car.)",
    "h2_estructura": "Estructura de H2 correcta (cantidad y calidad)",
    "listas_tablas": "Usa listas/tablas cuando el tema lo pide",
    "extension_400": "Extensión mínima de la nota (≥400 palabras)",
    "tags_1_5": "Número de tags correcto (1-5)",
    "enlaces_min_2": "Mínimo 2 enlaces internos",
    "enlace_parrafo_1_3": "Primer enlace interno en los primeros párrafos",
    "ancla_valida": "Texto ancla descriptivo (no genérico)",
    "imagen_1200px": "Imagen principal ≥1200px de ancho",
    "imagen_alt": "Alt de la imagen bien escrito",
}


@st.cache_data
def diagnostico_seo_por_autor(autor_original: str) -> list[dict]:
    """Desglose ítem-por-ítem — solo existe a nivel de censo completo (Tier 2,
    julio). Para meses históricos (Tier 1) no hay suficientes notas evaluadas
    por autor para que un desglose de 14 ítems sea confiable — se deja vacío
    a propósito en vez de mostrar un desglose calculado sobre 1-2 notas."""
    try:
        df = pd.read_csv(f"{DATA_DIR}/seo_items_por_periodista.csv", index_col="autor")
    except FileNotFoundError:
        return []
    if autor_original not in df.index:
        return []
    fila = df.loc[autor_original]
    salida = []
    for item, label in LABELS_ITEM_SEO.items():
        if item not in fila.index or pd.isna(fila[item]):
            continue
        salida.append({"item": item, "label": label, "pct": float(fila[item])})
    return sorted(salida, key=lambda x: x["pct"])


@st.cache_data
def eeat_por_autor(autor_original: str) -> dict | None:
    """Checklist EEAT — independiente del periodo seleccionado (se calculó
    sobre una muestra de hasta 15 notas de TODO el histórico + julio, no por
    mes) — ver MIGRACION-DESDE-COLOMBIACOM.md §4b."""
    try:
        df = pd.read_csv(f"{DATA_DIR}/eeat_periodista.csv", index_col="autor")
    except FileNotFoundError:
        return None
    if autor_original not in df.index:
        return None
    return df.loc[autor_original].to_dict()


@st.cache_data
def entidades_por_autor(autor_original: str) -> pd.DataFrame:
    """Entidades/temas en los que le rinde (y no) — independiente del periodo
    seleccionado, calculado sobre TODO el histórico + julio."""
    try:
        df = pd.read_csv(f"{DATA_DIR}/entidades_periodista.csv")
    except FileNotFoundError:
        return pd.DataFrame(columns=["forma", "tipo", "notas", "pct_del_periodista", "confianza"])
    return df[df["autor"] == autor_original].copy()


MES_LABEL_LARGO = {p: info["label"].split(" · ")[0] for p, info in PERIODOS.items()}


@st.cache_data
def historial_periodista(autor_original: str) -> pd.DataFrame:
    """Serie real de los 7 periodos (ene-jul 2026) para el perfil individual.
    `indice` es una versión MÁS SIMPLE que la "Eficiencia normalizada" de la
    tarjeta del periodo (esa sí ajusta por dificultad de sección): aquí es
    tráfico/nota puro contra la mediana de tráfico/nota del equipo ESE mismo
    periodo — se sacrifica el ajuste por dificultad para poder comparar los 7
    periodos con el mismo criterio simple (igual que Colombia.com)."""
    filas = []
    for periodo in reversed(ORDEN_PERIODOS):  # cronológico: ene -> jul
        tabla = cargar_periodistas(periodo)
        if tabla.empty:
            continue
        eficiencia_equipo = tabla["clics"] / tabla["notas"].clip(lower=1)
        mediana = eficiencia_equipo.median()
        fila = tabla[tabla["periodista"] == autor_original]
        if fila.empty:
            continue
        f = fila.iloc[0]
        notas = float(f["notas"])
        eficiencia = float(f["clics"]) / notas if notas else float("nan")
        filas.append(dict(
            mes=periodo, mes_label=MES_LABEL_LARGO[periodo],
            trafico=float(f["clics"]), notas=notas,
            indice=100 * eficiencia / mediana if mediana else 100.0,
            posicion_promedio=f["posicion_promedio"],
            notas_top10=float(f["notas_top10"]),
            eficiencia=eficiencia,
        ))
    return pd.DataFrame(filas)


def ranking_periodista(autor_original: str, periodo: str = PERIODO_DEFAULT) -> tuple[int, int] | None:
    """Posición del periodista ese periodo contra el resto del equipo, por
    tráfico real — mismo dato que ya usa la tarjeta de tráfico para el % del
    medio, expresado como ranking ("#3 de 14")."""
    tabla = cargar_periodistas(periodo).sort_values("clics", ascending=False).reset_index(drop=True)
    if tabla.empty or autor_original not in set(tabla["periodista"]):
        return None
    posicion = int(tabla.index[tabla["periodista"] == autor_original][0]) + 1
    return posicion, len(tabla)


def dificultad_seccion(seccion_raw: str) -> tuple[str, float]:
    """Wrapper público de _dificultad reusando el agregado de 7 periodos (no
    solo el periodo seleccionado) — para "en qué secciones le rinde escribir",
    que tampoco depende del selector de periodo."""
    agg = secciones_resumen_agregado().set_index("seccion_raw")
    if seccion_raw in agg.index:
        fila = agg.loc[seccion_raw]
        return fila["dificultad_categoria"], float(fila["dificultad_ajuste"])
    return _dificultad(0)


@st.cache_data
def _notas_todo_periodo() -> pd.DataFrame:
    """Notas de los 7 periodos combinadas (julio censo + 6 meses histórico),
    solo columnas necesarias para especialización por sección y tráfico real
    por entidad/tema — evita repetir esta unión en cada llamada."""
    notas_jul, _ = _cargar_crudo_completo()
    bloques = [notas_jul[["autor", "ruta", "titulo", "seccion_raw", "vistas"]]]
    for mes in MESES_LABEL:
        notas_mes, _ = _cargar_crudo_historico(mes)
        bloques.append(notas_mes[["autor", "ruta", "titulo", "seccion_raw", "vistas"]])
    return pd.concat(bloques, ignore_index=True)


@st.cache_data
def notas_por_seccion_agregado() -> pd.DataFrame:
    """Cuántas notas produce cada sección/subsección y qué tan bien le rinden
    — TODO artículo real con autor identificado en los 7 periodos, ya NO
    depende de quién firmó (a diferencia de entidades_fuertes(), que es por
    periodista). Para el panorama de Secciones."""
    todo = _notas_todo_periodo()
    agg = todo.groupby("seccion_raw").agg(notas=("vistas", "count"), trafico=("vistas", "sum")).reset_index()
    agg["trafico_por_nota"] = (agg["trafico"] / agg["notas"]).round(0)
    return agg.sort_values("trafico_por_nota", ascending=False).reset_index(drop=True)


@st.cache_data
def especializacion_todos() -> pd.DataFrame:
    """entidades_fuertes() de TODOS los periodistas conocidos en una sola
    tabla — para el panel "especialización real" y el simulador de
    escenarios del panorama de Secciones."""
    todo = _notas_todo_periodo()
    bloques = []
    for autor in sorted(todo["autor"].unique()):
        esp = entidades_fuertes(autor)
        if esp.empty:
            continue
        esp = esp.copy()
        esp["autor"] = autor
        bloques.append(esp)
    if not bloques:
        return pd.DataFrame(columns=["autor", "seccion", "notas", "trafico", "trafico_por_nota", "confianza"])
    return pd.concat(bloques, ignore_index=True)


# Subsecciones reales de economía/finanzas — verificado leyendo titulares
# reales, no adivinado por el nombre del prefijo: "money-invest/daily-news"
# y "money-invest/happening-now" resultaron ser noticia general (elecciones,
# famosos, YouTube caído), NO economía, pese al nombre de la sección madre.
# "money-invest/republica-dominicana" está demasiado mezclado con resultados
# de lotería. Solo estas 3 subsecciones son consistentemente contenido
# económico/financiero real al leer sus titulares.
SECCIONES_ECONOMIA = ("market-brief/finanzas", "market-brief/bolsa-de-valores",
                      "money-invest/internacional-economia")


def _en_secciones(seccion_raw: pd.Series, prefijos: tuple[str, ...]) -> pd.Series:
    return seccion_raw.apply(lambda s: any(s == p or str(s).startswith(p + "/") for p in prefijos))


@st.cache_data
def top_periodista_tema(prefijos: tuple[str, ...] = SECCIONES_ECONOMIA, min_notas: int = 3) -> dict | None:
    """El periodista con mejor tráfico/nota REAL dentro de un grupo de
    secciones (ej. economía/finanzas), con los 7 periodos acumulados —
    respaldado en datos, no en percepción. min_notas evita premiar una sola
    nota viral aislada como si fuera especialización real."""
    todo = _notas_todo_periodo()
    sub = todo[_en_secciones(todo["seccion_raw"], prefijos)]
    if sub.empty:
        return None
    agg = sub.groupby("autor").agg(notas=("vistas", "count"), trafico=("vistas", "sum")).reset_index()
    agg = agg[agg["notas"] >= min_notas]
    if agg.empty:
        return None
    agg["trafico_por_nota"] = agg["trafico"] / agg["notas"]
    ganador = agg.sort_values("trafico_por_nota", ascending=False).iloc[0]

    notas_ganador = sub[sub["autor"] == ganador["autor"]].sort_values("vistas", ascending=False)
    top_notas = notas_ganador.drop_duplicates("ruta").head(5)[["titulo", "ruta", "seccion_raw", "vistas"]].to_dict("records")

    return dict(
        autor=ganador["autor"], notas=int(ganador["notas"]), trafico=float(ganador["trafico"]),
        trafico_por_nota=float(ganador["trafico_por_nota"]), top_notas=top_notas,
    )


@st.cache_data
def entidades_fuertes(autor_original: str) -> pd.DataFrame:
    """En qué secciones le rinde escribir a este periodista, con los 7 periodos
    reales acumulados — reemplaza el beat fijo por uno respaldado en
    tráfico/nota real. Confianza por volumen de muestra: alta (≥10 notas) ·
    media (3-9) · baja (<3, indicativo)."""
    todo = _notas_todo_periodo()
    sub = todo[todo["autor"] == autor_original]
    if sub.empty:
        return pd.DataFrame(columns=["seccion", "notas", "trafico", "trafico_por_nota", "confianza"])
    agg = sub.groupby("seccion_raw").agg(notas=("vistas", "count"), trafico=("vistas", "sum")).reset_index()
    agg["trafico_por_nota"] = (agg["trafico"] / agg["notas"]).round(0)
    agg["confianza"] = agg["notas"].apply(lambda n: "alta" if n >= 10 else "media" if n >= 3 else "baja")
    agg = agg.rename(columns={"seccion_raw": "seccion"})
    return agg.sort_values("trafico_por_nota", ascending=False).reset_index(drop=True)


@st.cache_data
def _trafico_por_entidad(autor_original: str) -> pd.DataFrame:
    """Tráfico real por entidad/tema: suma las vistas de las rutas reales que
    matchearon esa entidad (columna `rutas` de entidades_periodista.csv,
    separadas por "|") — no un promedio inventado, es trazable a notas
    concretas."""
    df = entidades_por_autor(autor_original)
    if df.empty or "rutas" not in df.columns:
        return df
    vistas = _notas_todo_periodo().drop_duplicates("ruta").set_index("ruta")["vistas"]
    df = df.copy()
    df["trafico"] = df["rutas"].apply(
        lambda rutas_str: float(vistas.reindex(str(rutas_str).split("|")).fillna(0).sum()))
    df["trafico_por_nota"] = (df["trafico"] / df["notas"]).round(0)
    return df


@st.cache_data
def temas_fuertes(autor_original: str, top_n: int = 8, excluir_patron: str | None = None) -> pd.DataFrame:
    """Espejo de entidades_fuertes pero a nivel de TEMA/entidad concreta (no
    solo la sección) — extraído de títulos reales de los 7 periodos.
    excluir_patron (opcional) filtra ANTES de truncar a top_n, para que
    excluir un tema no deje la lista más corta de lo normal — rellena con el
    siguiente mejor tema real en vez de simplemente restar uno."""
    df = _trafico_por_entidad(autor_original)
    if df.empty:
        return df
    if excluir_patron:
        df = df[~df["forma"].str.contains(excluir_patron, case=False, na=False)]
    return df.sort_values("trafico", ascending=False).head(top_n)


@st.cache_data
def temas_debiles(autor_original: str, top_n: int = 6, excluir_patron: str | None = None) -> pd.DataFrame:
    """El espejo de temas_fuertes: temas RECURRENTES (se excluye confianza
    baja, que es solo 2 notas y no alcanza a ser un patrón) donde el
    tráfico/nota es más bajo — no solo dónde rinde, también dónde insiste y
    no le funciona."""
    df = _trafico_por_entidad(autor_original)
    if df.empty or "confianza" not in df.columns:
        return df
    if excluir_patron:
        df = df[~df["forma"].str.contains(excluir_patron, case=False, na=False)]
    sub = df[~df["confianza"].astype(str).str.contains("baja", na=False)]
    return sub.sort_values("trafico_por_nota", ascending=True).head(top_n)


@st.cache_data
def diagnostico_seo_por_autor_mes(autor_original: str, periodo: str) -> list[dict]:
    """Desglose ítem-por-ítem para un periodo histórico, sobre la MUESTRA de
    ese mes (hasta 12 notas/autor) — vía seo_items_por_periodista_mes.csv
    (data/desglose_seo_historico_por_item.py), reusando el HTML crudo ya
    scrapeado para semaforo_muestra_6meses.py, sin volver a pedir nada."""
    try:
        df = pd.read_csv(f"{DATA_DIR}/seo_items_por_periodista_mes.csv", dtype={"mes": str})
    except FileNotFoundError:
        return []
    info = PERIODOS[periodo]
    if info["tipo"] != "historico":
        return []
    fila = df[(df["autor"] == autor_original) & (df["mes"] == info["mes"])]
    if fila.empty:
        return []
    fila = fila.iloc[0]
    salida = []
    for item, label in LABELS_ITEM_SEO.items():
        if item not in fila.index or pd.isna(fila[item]):
            continue
        salida.append({"item": item, "label": label, "pct": float(fila[item])})
    return sorted(salida, key=lambda x: x["pct"])
