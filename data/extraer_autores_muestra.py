"""Identifica el autor real de cada URL candidata a "artículo real" en la
muestra de mayor tráfico, vía el JSON-LD NewsArticle que cada nota de
revistamercado.do ya expone (author.name, articleSection, datePublished,
headline, keywords).

Este paso reemplaza al de Colombia.com que cruzaba "muestra de tráfico" +
"archivo de autor" (/staff/{id}/{slug}, paginado) y se quedaba con la unión.
revistamercado.do NO tiene esa segunda fuente: el JSON-LD de cada nota declara
author.url = /post_author/{slug}/, pero esa URL devuelve 404 en vivo (verificado
2026-08-05) — no hay archivo de autor navegable. Por eso este es el ÚNICO método
disponible: la muestra de mayor tráfico es la cobertura real, no una unión con
una segunda fuente. Hay que ser explícito con Edwin en cada entrega: esto
subestima a quien escribe piezas modestas no virales, igual que ya se advirtió
en la muestra previa de 53 URLs (ver memoria calculadora-trafico-muestra-periodistas).

Filtra "artículo real" vs. página de utilidad por profundidad de ruta (2 o 3
segmentos: /seccion/slug/ o /seccion/subseccion/slug/ — verificado en el
export real de jul-2026: depth=3 es el 56% del tráfico total, ej.
empresas/sport-business/... y money-invest/daily-news/..., así que exigir
depth==2 a secas (primera versión de este filtro) dejaba fuera más de la
mitad del tráfico real) + una lista explícita de prefijos de NO-artículo
(listados, tags, paginación, checkout, páginas programáticas /p/, el archivo
de autor roto /post_author/). depth==1 se descarta entero: son landing
pages/eventos/rankings especiales, no notas individuales de un periodista.

Uso: python3 data/extraer_autores_muestra.py <sufijo_fecha> [top_n]
Lee data/procesado_<sufijo>.csv (salida de procesar_exports.py)
Escribe data/notas_con_autor_<sufijo>.csv (ruta, titulo, autor, seccion, fecha,
        vistas, es_sindicado, error)
"""

import json
import sys
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://revistamercado.do"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
PREFIJOS_NO_ARTICULO = ("/category/", "/tag/", "/wp-", "/author/", "/post_author/",
                        "/page/", "/feed", "/buscar", "/search", "/carrito", "/checkout",
                        "/p/", "/subscribers-login", "/suscribe", "/new-suscribe",
                        "/events/", "/event-detail/", "/form-", "/confirmar-asistencia")
MARCAS_SINDICADO = ("fortune", "exclusive-subscribers")


def parece_articulo(ruta: str) -> bool:
    """depth=1 (landing pages, eventos, rankings especiales, /suscribe/, etc.)
    se descarta entero. depth=2 y depth=3 son ambos patrones reales de nota
    en revistamercado.do (con y sin subsección, ej. /actualidad/slug/ vs.
    /empresas/sport-business/slug/) — confirmado con el export real de
    jul-2026, ver docstring del módulo."""
    if not isinstance(ruta, str) or not ruta.startswith("/"):
        return False
    if any(ruta.startswith(p) for p in PREFIJOS_NO_ARTICULO):
        return False
    segmentos = [s for s in ruta.strip("/").split("/") if s]
    if len(segmentos) not in (2, 3):
        return False
    return len(segmentos[-1]) > 12  # slugs de artículo son largos y descriptivos


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


def main(sufijo: str, top_n: int):
    procesado = pd.read_csv(f"data/procesado_{sufijo}.csv")
    candidatos = procesado[procesado["ruta"].apply(parece_articulo)].sort_values("vistas", ascending=False)
    candidatos = candidatos.head(top_n).reset_index(drop=True)
    print(f"{len(procesado)} URLs en el export -> {len(candidatos)} candidatas a artículo real "
          f"(top {top_n} por tráfico)")

    filas = []
    for i, row in candidatos.iterrows():
        print(f"[{i+1}/{len(candidatos)}] {row['ruta']}")
        try:
            info = extraer_autor(row["ruta"])
            info["error"] = None
        except Exception as e:
            info = {"autor": "SIN_AUTOR", "titulo": None, "seccion": None, "fecha": None,
                     "es_sindicado": False, "error": str(e)}
            print(f"  ERROR: {e}")
        info["ruta"] = row["ruta"]
        info["vistas"] = row["vistas"]
        filas.append(info)
        time.sleep(0.3)

    df = pd.DataFrame(filas)
    salida = f"data/notas_con_autor_{sufijo}.csv"
    df.to_csv(salida, index=False)
    print(f"\n{len(df)} filas -> {salida}")
    print(f"Sin autor identificado: {(df['autor'] == 'SIN_AUTOR').sum()}")
    print(f"Sindicadas (Fortune): {int(df['es_sindicado'].sum())}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 data/extraer_autores_muestra.py <sufijo_fecha> [top_n]")
        sys.exit(1)
    sufijo_arg = sys.argv[1]
    top_n_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    main(sufijo_arg, top_n_arg)
