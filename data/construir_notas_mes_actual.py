"""Construye la tabla de notas del mes en curso (parcial) para Revista Mercado --
equivalente a lo que colombia.com resuelve con contar_notas_agosto.py +
construir_notas_agosto.py, pero adaptado: revistamercado.do NO tiene archivo de
autor navegable (/staff/{id}/{slug} devuelve 404 aquí, confirmado 2026-08-05 en
extraer_autores_muestra.py) -- el ÚNICO método de atribuir autor es scrapear el
JSON-LD de cada nota. Para no re-scrapear cientos de URLs cada corrida, este
script reusa data/mapa_autor_ruta.csv como caché acumulado (ruta -> autor ya
conocido de meses previos) y solo scrapea las rutas candidatas que todavía no
están ahí -- las nuevas se agregan de vuelta al caché al final, así la próxima
corrida las encuentra ya conocidas.

Uso: python3 data/construir_notas_mes_actual.py <mes AAAA-MM>
Ej.: python3 data/construir_notas_mes_actual.py 2026-08

Lee (ya descargados de Drive a mano o vía MCP antes de correr esto):
    data/raw_historico/ga4_pages_screens_periodos_<fecha>.csv (más reciente)
    data/raw_historico/sc_consolidado_<fecha>.csv (más reciente)
    data/mapa_autor_ruta.csv (caché de autor por ruta, se actualiza in-place)
Escribe:
    data/notas_<mes>.csv
"""

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

DIR = Path(__file__).parent
RAW = DIR / "raw_historico"
BASE = "https://revistamercado.do"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
MAX_NUEVAS_POR_CORRIDA_DEFAULT = 150  # tope para una corrida RUTINARIA (diaria) -- casi
# todo ya está en el caché de corridas previas, así que 150 nuevas de sobra en el día a
# día. Para la PRIMERA corrida real de un mes (o para ponerse al día después de un hueco)
# hace falta muchas más -- pasar un 2do argumento por línea de comandos para eso, ver
# main.py: bug real encontrado 16-ago-2026, Edwin señaló que agosto mostraba 7-29 notas
# por periodista cuando escriben 8-9 notas AL DÍA -- con el tope de 150 fijo, la primera
# corrida real solo alcanzó a identificar 150 de 12.252 rutas candidatas (1.2%).

PREFIJOS_NO_ARTICULO = ("/category/", "/tag/", "/wp-", "/author/", "/post_author/",
                        "/page/", "/feed", "/buscar", "/search", "/carrito", "/checkout",
                        "/p/", "/subscribers-login", "/suscribe", "/new-suscribe",
                        "/events/", "/event-detail/", "/form-", "/confirmar-asistencia")
MARCAS_SINDICADO = ("fortune", "exclusive-subscribers")


def normalizar(url: str) -> str:
    return (
        str(url)
        .replace("https://www.revistamercado.do", "")
        .replace("https://revistamercado.do", "")
        .rstrip("/")
        or "/"
    )


def parece_articulo(ruta: str) -> bool:
    """Misma regla que extraer_autores_muestra.py -- depth 2 o 3, slug largo."""
    if not isinstance(ruta, str) or not ruta.startswith("/"):
        return False
    if any(ruta.startswith(p) for p in PREFIJOS_NO_ARTICULO):
        return False
    segmentos = [s for s in ruta.strip("/").split("/") if s]
    if len(segmentos) not in (2, 3):
        return False
    return len(segmentos[-1]) > 12


def _jsonld_articulo(soup) -> dict:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        candidatos = data.get("@graph", [data]) if isinstance(data, dict) else data
        for item in candidatos if isinstance(candidatos, list) else [candidatos]:
            if isinstance(item, dict) and item.get("@type") in ("NewsArticle", "Article"):
                return item
    return {}


def extraer_autor(ruta: str) -> dict:
    url = BASE + ruta
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    jsonld = _jsonld_articulo(soup)
    if not jsonld:
        return {"autor": "SIN_AUTOR", "titulo": None, "seccion": None, "fecha": None, "es_sindicado": False}
    keywords = (jsonld.get("keywords") or "").lower()
    return {
        "autor": (jsonld.get("author") or {}).get("name") or "SIN_AUTOR",
        "titulo": jsonld.get("headline"),
        "seccion": (jsonld.get("articleSection") or "").lower() or None,
        "fecha": jsonld.get("datePublished"),
        "es_sindicado": any(m in keywords for m in MARCAS_SINDICADO),
    }


def _ultimo_archivo(patron: str) -> Path:
    candidatos = sorted(RAW.glob(patron), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidatos:
        raise FileNotFoundError(
            f"No hay ningún archivo '{patron}' en {RAW} -- baja los exports más "
            f"recientes de la carpeta 'Data Diaria Revista Mercado' en Drive antes de correr esto."
        )
    return candidatos[0]


def cargar_ga4() -> pd.DataFrame:
    path = _ultimo_archivo("ga4_pages_screens_periodos_*.csv")
    ga4 = pd.read_csv(path)
    actual = ga4[ga4["periodo"] == "actual"].copy()
    actual["ruta"] = actual["pagePath"].apply(normalizar)
    return actual.groupby("ruta", as_index=False)["screenPageViews"].sum().rename(
        columns={"screenPageViews": "vistas"})


def cargar_gsc() -> pd.DataFrame:
    path = _ultimo_archivo("sc_consolidado_*.csv")
    sc = pd.read_csv(path)
    sc["ruta"] = sc["pagina"].apply(normalizar)
    pivot = sc.pivot_table(index="ruta", columns="superficie", values="clics", aggfunc="sum", fill_value=0)
    pivot = pivot.reset_index()
    for col in ["Search", "Discover", "News"]:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot = pivot.rename(columns={"Search": "clics_search", "Discover": "clics_discover", "News": "clics_news"})[
        ["ruta", "clics_search", "clics_discover", "clics_news"]]

    # Posición e impresiones reales solo existen en la superficie Search de GSC.
    busq = sc[sc["superficie"] == "Search"][["ruta", "posicion", "impresiones"]].dropna(subset=["posicion"])
    busq = busq.groupby("ruta", as_index=False).agg(posicion=("posicion", "mean"), impresiones_search=("impresiones", "sum"))
    return pivot.merge(busq, on="ruta", how="left")


def main(mes: str, tope_nuevas: int = MAX_NUEVAS_POR_CORRIDA_DEFAULT):
    ga4 = cargar_ga4()
    gsc = cargar_gsc()
    trafico = ga4.merge(gsc, on="ruta", how="outer")
    for col in ["vistas", "clics_search", "clics_discover", "clics_news"]:
        trafico[col] = trafico[col].fillna(0)
    trafico["trafico_total"] = (trafico["vistas"] + trafico["clics_search"]
                                 + trafico["clics_discover"] + trafico["clics_news"])

    candidatas = trafico[trafico["ruta"].apply(parece_articulo)].sort_values(
        "trafico_total", ascending=False).reset_index(drop=True)
    print(f"{len(trafico)} rutas en el export -> {len(candidatas)} candidatas a artículo real")

    cache_path = DIR / "mapa_autor_ruta.csv"
    cache = pd.read_csv(cache_path) if cache_path.exists() else pd.DataFrame(
        columns=["ruta", "autor", "titulo", "seccion", "fecha", "es_sindicado"])
    conocidas = set(cache["ruta"])

    nuevas_candidatas = candidatas[~candidatas["ruta"].isin(conocidas)].head(tope_nuevas)
    print(f"Ya conocidas en mapa_autor_ruta.csv: {len(candidatas) - len(nuevas_candidatas)}")
    print(f"Nuevas a scrapear esta corrida (tope {tope_nuevas}): {len(nuevas_candidatas)}")

    filas_nuevas = []
    for i, row in nuevas_candidatas.iterrows():
        print(f"[{i+1}] {row['ruta']}")
        try:
            info = extraer_autor(row["ruta"])
        except Exception as e:
            info = {"autor": "SIN_AUTOR", "titulo": None, "seccion": None, "fecha": None,
                     "es_sindicado": False}
            print(f"  ERROR: {e}")
        info["ruta"] = row["ruta"]
        filas_nuevas.append(info)
        time.sleep(0.3)

    if filas_nuevas:
        cache = pd.concat([cache, pd.DataFrame(filas_nuevas)], ignore_index=True)
        cache = cache.drop_duplicates(subset="ruta", keep="last")
        cache.to_csv(cache_path, index=False)
        print(f"\nmapa_autor_ruta.csv actualizado: {len(cache)} rutas conocidas en total")

    con_autor = candidatas.merge(cache, on="ruta", how="inner")
    con_autor = con_autor[con_autor["autor"].notna() & (con_autor["autor"] != "SIN_AUTOR")]
    con_autor["fecha_real"] = pd.to_datetime(con_autor["fecha"], errors="coerce", utc=True).dt.tz_localize(None)

    inicio_mes = pd.Timestamp(f"{mes}-01")
    fin_mes = inicio_mes + pd.offsets.MonthEnd(1)
    del_mes = con_autor[(con_autor["fecha_real"] >= inicio_mes) & (con_autor["fecha_real"] <= fin_mes)].copy()
    del_mes["mes"] = mes

    salida = del_mes[["ruta", "fecha_real", "autor", "titulo", "seccion", "mes",
                       "vistas", "clics_search", "clics_discover", "clics_news", "trafico_total",
                       "posicion", "impresiones_search"]]
    salida = salida.drop_duplicates(subset="ruta")
    out_path = DIR / f"notas_{mes}.csv"
    salida.to_csv(out_path, index=False)
    print(f"\nNotas de {mes} con autor identificado: {len(salida)}")
    print(f"Guardado -> {out_path}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Uso: python3 data/construir_notas_mes_actual.py <mes AAAA-MM> [tope_nuevas]")
        sys.exit(1)
    tope = int(sys.argv[2]) if len(sys.argv) == 3 else MAX_NUEVAS_POR_CORRIDA_DEFAULT
    main(sys.argv[1], tope)
