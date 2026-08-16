"""Checklist EEAT (Experience, Expertise, Authoritativeness, Trust) por
periodista — MIGRACION-DESDE-COLOMBIACOM.md §4b. Verificado en vivo contra el
HTML/JSON-LD real de revistamercado.do el 2026-08-09 antes de programar (no se
asume la misma estructura de Colombia.com):

- NewsMediaOrganization SÍ está en el JSON-LD del home (name/url/foundingDate/
  logo) pero SIN sameAs — no hay perfiles sociales vinculados a nivel sitio.
- NO existe página pública de política editorial/correcciones — el footer solo
  tiene "Política de Privacidad" (y el link de "Términos y Condiciones" en
  realidad apunta a esa MISMA url — bug de UI aparte, no de este checklist).
- author.url del JSON-LD SIEMPRE apunta a /post_author/{slug}/, que SIEMPRE da
  404 (confirmado, es un bug de origen de WordPress) — "perfil verificable" y
  "bio verificable" son estructuralmente FALSE para TODOS los autores, no hace
  falta re-chequear por autor.
- author["@type"] es SIEMPRE "Person" (nunca "Organization" ni ausente) en los
  ~10 casos verificados — TRUE para todos.
- author.sameAs NUNCA está presente en los casos verificados.

Por eso el único trabajo real de scraping por-nota es: dateModified real
(vs. ruido del pipeline de publicación — un dateModified 1-2 minutos después
del datePublished es autosave, no una actualización editorial real: se exige
>10 minutos de diferencia), enlaces salientes a dominios externos reales
(no redes sociales/WhatsApp/Google News), y frases de atribución explícita.

Uso: python3 data/eeat_periodista.py
Lee data/mapa_autor_ruta.csv + tráfico acumulado (historico + jul) para elegir
    hasta 15 notas de mayor tráfico por autor
Escribe data/eeat_raw_notas.csv (señales crudas por nota)
        data/eeat_periodista.csv (checklist agregado por autor)
"""

import json
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://revistamercado.do"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
SOCIAL_O_INTERNO = ("wa.me", "news.google.com", "whatsapp.com", "javascript:", "facebook.com",
                     "twitter.com", "x.com", "instagram.com", "t.me", "linkedin.com",
                     "revistamercado.do")
FRASES_ATRIBUCION = re.compile(
    r"\b(seg[uú]n|inform[oó]|confirm[oó]|se[ñn]al[oó]|afirm[oó]|indic[oó]|asegur[oó]|"
    r"explic[oó]|declar[oó]|revel[oó]|detall[oó])\b", re.IGNORECASE)
UMBRAL_ACTUALIZACION_MIN = 10


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


def extraer_eeat_nota(ruta: str) -> dict:
    r = requests.get(BASE + ruta, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    jsonld = _jsonld_articulo(soup)

    pub = pd.to_datetime(jsonld.get("datePublished"), utc=True, errors="coerce")
    mod = pd.to_datetime(jsonld.get("dateModified"), utc=True, errors="coerce")
    actualizacion_real = bool(pd.notna(pub) and pd.notna(mod) and (mod - pub).total_seconds() > UMBRAL_ACTUALIZACION_MIN * 60)

    body = soup.find("div", class_=lambda c: c and "new-desing-content" in c.split())
    dominios_externos = set()
    texto_cuerpo = ""
    if body is not None:
        candidatos_body = soup.find_all("div", class_=lambda c: c and "new-desing-content" in c.split())
        body = max(candidatos_body, key=lambda d: len(d.find_all("p")), default=body)
        texto_cuerpo = body.get_text(" ", strip=True)
        for a in body.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/") or any(s in href for s in SOCIAL_O_INTERNO):
                continue
            m = re.search(r"https?://(?:www\.)?([^/]+)", href)
            if m:
                dominios_externos.add(m.group(1))

    cita_externas = len(dominios_externos) > 0
    atribucion = bool(FRASES_ATRIBUCION.search(texto_cuerpo))

    return {
        "actualizacion_real": actualizacion_real,
        "cita_fuentes_externas": cita_externas,
        "n_dominios_externos": len(dominios_externos),
        "atribucion_explicita": atribucion,
    }


def construir_muestra(top_n_por_autor: int = 15) -> pd.DataFrame:
    mapa = pd.read_csv("data/mapa_autor_ruta.csv")
    mapa = mapa[~mapa["autor"].isin(["revistamercado", "SIN_AUTOR"])]

    hist = pd.read_csv("data/procesado_historico_2026-01-01_2026-06-30.csv")
    jul = pd.read_csv("data/procesado_2026-07-01_2026-07-31.csv")[["ruta", "vistas"]]
    trafico = pd.concat([hist.groupby("ruta")["vistas"].sum().reset_index(), jul])
    trafico = trafico.groupby("ruta", as_index=False)["vistas"].sum()

    df = mapa.merge(trafico, on="ruta", how="left").fillna({"vistas": 0})
    return df.sort_values(["autor", "vistas"], ascending=[True, False]).groupby("autor").head(top_n_por_autor)


def main():
    muestra = construir_muestra()
    print(f"Muestra EEAT: {len(muestra)} notas ({muestra['autor'].nunique()} autores)")

    filas = []
    for i, (_, row) in enumerate(muestra.iterrows()):
        print(f"[{i+1}/{len(muestra)}] {row['autor']} -> {row['ruta']}")
        try:
            señales = extraer_eeat_nota(row["ruta"])
            señales["error"] = None
        except Exception as e:
            señales = {"actualizacion_real": None, "cita_fuentes_externas": None,
                       "n_dominios_externos": None, "atribucion_explicita": None, "error": str(e)}
            print(f"  ERROR: {e}")
        señales["autor"] = row["autor"]
        señales["ruta"] = row["ruta"]
        filas.append(señales)
        time.sleep(0.3)

    notas_df = pd.DataFrame(filas)
    notas_df.to_csv("data/eeat_raw_notas.csv", index=False)
    print(f"\n{len(notas_df)} filas -> data/eeat_raw_notas.csv")

    validas = notas_df[notas_df["error"].isna()]
    rollup = validas.groupby("autor").agg(
        notas_muestreadas=("ruta", "count"),
        pct_actualizacion_real=("actualizacion_real", "mean"),
        pct_cita_fuentes_externas=("cita_fuentes_externas", "mean"),
        pct_atribucion_explicita=("atribucion_explicita", "mean"),
    ).reset_index()
    for col in ["pct_actualizacion_real", "pct_cita_fuentes_externas", "pct_atribucion_explicita"]:
        rollup[col] = (rollup[col] * 100).round(1)

    # Estructurales, iguales para todos (verificado en vivo, ver docstring) — no
    # requieren scraping por autor.
    rollup["schema_person"] = True
    rollup["perfil_verificable"] = False  # author.url siempre 404
    rollup["bio_verificable"] = False     # misma razón

    # Consistencia temática: % del tráfico total del autor concentrado en su
    # sección más fuerte (Expertise: publicar dentro de un cluster definido).
    mapa = pd.read_csv("data/mapa_autor_ruta.csv")
    trafico_total = pd.concat([
        pd.read_csv("data/procesado_historico_2026-01-01_2026-06-30.csv").groupby("ruta")["vistas"].sum().reset_index(),
        pd.read_csv("data/procesado_2026-07-01_2026-07-31.csv")[["ruta", "vistas"]],
    ]).groupby("ruta", as_index=False)["vistas"].sum()
    con_seccion = mapa.merge(trafico_total, on="ruta", how="left").fillna({"vistas": 0})
    por_seccion = con_seccion.groupby(["autor", "seccion"])["vistas"].sum().reset_index()
    total_autor = con_seccion.groupby("autor")["vistas"].sum().rename("total")
    por_seccion = por_seccion.merge(total_autor, on="autor")
    por_seccion["pct"] = 100 * por_seccion["vistas"] / por_seccion["total"].replace(0, float("nan"))
    consistencia = por_seccion.groupby("autor")["pct"].max().round(1).rename("pct_consistencia_tematica")

    rollup = rollup.merge(consistencia, on="autor", how="left")
    rollup.to_csv("data/eeat_periodista.csv", index=False)

    print(f"\n{len(rollup)} autores -> data/eeat_periodista.csv")
    pd.set_option("display.width", 160)
    print(rollup.to_string(index=False))

    print("\n=== A NIVEL DE SITIO (contexto, no se puntúa por periodista) ===")
    print("NewsMediaOrganization schema: SÍ (sin sameAs)")
    print("Página pública de política editorial/correcciones: NO")
    print("HTTPS: SÍ")


if __name__ == "__main__":
    main()
