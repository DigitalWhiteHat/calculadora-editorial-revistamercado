"""Descarga el HTML real de cada nota de revistamercado.do y extrae las señales
on-page necesarias para las 23 reglas del Semáforo SEO. Usa parsing de HTML (bs4)
+ el JSON-LD NewsArticle que el sitio ya expone, no un modelo de lenguaje, para
tener conteos de caracteres/enlaces exactos.

Adaptado de calculadora-periodistas/data/scrape_semaforo.py (Colombia.com).
Diferencias reales del sitio, verificadas en vivo el 2026-08-05:
- JSON-LD <script type="application/ld+json"> con @type NewsArticle ya trae
  author.name, articleSection, datePublished, keywords e image{width,height} —
  se usa directo, así que NO hace falta descargar la imagen para medir su ancho
  (a diferencia de Colombia.com).
- El H1 real del artículo es el PRIMER <h1> del documento (tiene class="mt-3").
  Las notas traducidas/sindicadas de Fortune (sección Business, keywords con
  "fortune"/"exclusive-subscribers") a veces traen sub-subtítulos marcados como
  <h1> DENTRO del cuerpo — es un bug de origen del importador, no del artículo.
  Se detectan y se cuentan como subtítulo (para el chequeo de estructura),
  nunca como el H1 de la página.
- Cuerpo del artículo: <div class="content new-desing-content">.
- No todas las notas traen <meta name="description"> — hay que usar
  <meta property="og:description"> como respaldo (falta real en varias notas,
  vale la pena reportarlo aparte como hallazgo técnico, no solo rellenar).
- Tags: mismo patrón que Colombia.com, <a href="/tag/...">.

Uso: python3 data/scrape_semaforo.py <sufijo_fecha>
Lee data/notas_con_autor_<sufijo>.csv (columnas: ruta, autor — mismo formato que
Colombia.com, generado en el paso de cruce GA4+GSC+autor)
Escribe data/semaforo_raw_<sufijo>.csv (una fila por nota con todas las señales crudas)
"""

import json
import re
import sys
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://revistamercado.do"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
SOCIAL_HOST_SNIPPETS = ("wa.me", "news.google.com", "whatsapp.com", "javascript:", "facebook.com",
                        "twitter.com", "x.com", "instagram.com", "t.me")
MARCAS_SINDICADO = ("fortune", "exclusive-subscribers")


def texto_o_none(tag):
    return tag.get_text(strip=True) if tag else None


def _extraer_jsonld_articulo(soup) -> dict:
    """Busca el bloque JSON-LD @type NewsArticle. Devuelve {} si no aparece
    (no debería pasar en revistamercado.do, pero no se asume)."""
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


def extraer_pagina(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    jsonld = _extraer_jsonld_articulo(soup)
    keywords = jsonld.get("keywords", "") or ""
    es_sindicado = any(marca in keywords.lower() for marca in MARCAS_SINDICADO)

    h1 = texto_o_none(soup.find("h1"))  # el primer <h1> del documento es siempre el título real
    title_tag = texto_o_none(soup.find("title"))
    if title_tag:
        title_tag = re.sub(r"\s*-\s*Revista Mercado\s*$", "", title_tag).strip()

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    if meta_desc_tag:
        meta_desc = meta_desc_tag.get("content", "").strip()
    else:
        og_desc_tag = soup.find("meta", property="og:description")
        meta_desc = og_desc_tag.get("content", "").strip() if og_desc_tag else None

    # OJO: hay 2 divs con "new-desing-content" en el DOM — un teaser/resumen
    # corto (class="content new-desing-content mt-4", 1 párrafo) que aparece
    # ANTES en el HTML, y el cuerpo real del artículo (más abajo, sin "mt-4").
    # Verificado en vivo: tomar el primer match por error deja el body casi
    # vacío. Nos quedamos con el que tiene más párrafos, no el primero.
    candidatos_body = soup.find_all("div", class_=lambda c: c and "new-desing-content" in c.split())
    body = max(candidatos_body, key=lambda d: len(d.find_all("p")), default=None)
    parrafos, h2s, tags = [], [], []
    enlaces_internos = []  # (indice_parrafo, texto_ancla, href)
    tiene_lista_tabla = False

    if body:
        idx_parrafo = 0
        for el in body.find_all(["p", "h1", "h2", "ul", "ol", "table"], recursive=True):
            if el.name == "p":
                txt = el.get_text(strip=True)
                if not txt:
                    continue
                idx_parrafo += 1
                parrafos.append(txt)
                for a in el.find_all("a", href=True):
                    href = a["href"]
                    if any(s in href for s in SOCIAL_HOST_SNIPPETS):
                        continue
                    if href.startswith("/tag/"):
                        continue
                    if href.startswith("/") or "revistamercado.do" in href:
                        enlaces_internos.append((idx_parrafo, a.get_text(strip=True), href))
            elif el.name in ("h1", "h2"):
                # h1 DENTRO del cuerpo = subtítulo mal marcado (bug de origen en
                # notas sindicadas de Fortune) — se cuenta como subtítulo real,
                # nunca como el H1 de la página (ese ya se tomó arriba).
                txt = el.get_text(strip=True)
                if txt:
                    h2s.append(txt)
            elif el.name in ("ul", "ol", "table"):
                if "Comparte" not in el.get_text():
                    tiene_lista_tabla = True

        for a in body.find_all("a", href=True):
            if a["href"].startswith("/tag/") or "/tag/" in a["href"]:
                tags.append(a.get_text(strip=True))

    palabras = sum(len(p.split()) for p in parrafos)
    primer_parrafo = parrafos[0] if parrafos else None

    img_info = jsonld.get("image") or {}
    img_ancho = img_info.get("width")
    img_url = img_info.get("url")
    img_alt = None
    if img_url:
        nombre_archivo = img_url.rsplit("/", 1)[-1]
        for im_tag in soup.find_all("img"):
            src_cand = im_tag.get("data-src") or im_tag.get("src") or ""
            if nombre_archivo.split(".")[0][:40] in src_cand:
                img_alt = im_tag.get("alt")
                break

    return {
        "h1": h1,
        "title_tag": title_tag,
        "meta_desc": meta_desc,
        "primer_parrafo": primer_parrafo,
        "num_parrafos": len(parrafos),
        "num_h2": len(h2s),
        "h2_textos": " | ".join(h2s),
        "tiene_lista_tabla": tiene_lista_tabla,
        "num_tags": len(tags),
        "tags_textos": ", ".join(tags),
        "num_enlaces_internos": len(enlaces_internos),
        "parrafo_primer_enlace": enlaces_internos[0][0] if enlaces_internos else None,
        "ancla_primer_enlace": enlaces_internos[0][1] if enlaces_internos else None,
        "anclas_todas": " | ".join(a[1] for a in enlaces_internos),
        "palabras_body": palabras,
        "img_url": img_url,
        "img_ancho": img_ancho,
        "img_alt": img_alt,
        "autor_jsonld": (jsonld.get("author") or {}).get("name"),
        "seccion_jsonld": jsonld.get("articleSection"),
        "fecha_publicacion": jsonld.get("datePublished"),
        "keywords_jsonld": keywords,
        "es_sindicado": es_sindicado,
    }


def main(sufijo: str):
    notas = pd.read_csv(f"data/notas_con_autor_{sufijo}.csv")
    notas = notas[notas["autor"] != "SIN_AUTOR"].reset_index(drop=True)

    filas = []
    for i, row in notas.iterrows():
        url = BASE + row["ruta"]
        print(f"[{i+1}/{len(notas)}] {row['autor']} -> {url}")
        try:
            datos = extraer_pagina(url)
            datos["error"] = None
        except Exception as e:
            datos = {"error": str(e)}
            print(f"  ERROR: {e}")
        datos["ruta"] = row["ruta"]
        datos["autor"] = row["autor"]
        filas.append(datos)
        time.sleep(0.3)

    df = pd.DataFrame(filas)
    salida = f"data/semaforo_raw_{sufijo}.csv"
    df.to_csv(salida, index=False)
    print(f"\n{len(df)} filas -> {salida}")
    print(f"Errores: {df['error'].notna().sum()}")
    if "es_sindicado" in df.columns:
        print(f"Sindicadas (Fortune): {int(df['es_sindicado'].sum())}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 data/scrape_semaforo.py <sufijo_fecha>")
        sys.exit(1)
    main(sys.argv[1])
