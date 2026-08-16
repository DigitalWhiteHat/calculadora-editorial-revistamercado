"""Aplica las 23 reglas del Semáforo SEO sobre los datos crudos extraídos por
scrape_semaforo.py. 14 ítems se automatizan con datos objetivos del HTML
(longitudes, conteos, posiciones). 8 ítems requieren una keyword objetivo
definida por el editor o juicio editorial y se marcan explícitamente como
"revisión editorial" en vez de forzar un puntaje falso.

Adaptado de calculadora-periodistas/data/semaforo_scoring.py (Colombia.com).
CORRECCIÓN 2026-08-06 (ver MIGRACION-DESDE-COLOMBIACOM.md §4): la regla de H1
que se copió al armar este proyecto era la primera versión de Colombia.com, que
Edwin marcó como injusta y corrigieron después — confundía el `<title>` SEO
(que sí debe ser corto, 50-65 car., ítem aparte) con el **H1 editorial** (el
titular dentro del contenido, que puede llevar gancho y ser más largo). Antes
tenía DOS reglas de H1 (≤78 Y 70-130) — ahora es UNA sola: 70-170 caracteres.
Eso baja el total de automatizables de 15 a 14.

Pendiente de definir con Edwin antes de correr esto en serio:
- SECCIONES_CON_LISTA_OBLIGATORIA: en Colombia.com son loterías/elecciones/cine/
  fútbol (contenido con datos enumerables). Para revistamercado.do aún no se
  sabe cuáles secciones tienen ese patrón (¿market-brief? ¿country-report? ¿
  device con comparativas de specs?) — queda vacío a propósito, no se adivina.

Uso: python3 data/semaforo_scoring.py <sufijo_fecha>
Lee data/semaforo_raw_<sufijo>.csv + data/notas_con_autor_<sufijo>.csv
Escribe data/semaforo_notas_<sufijo>.csv (pass/fail por ítem + score final por nota)
        data/semaforo_periodistas_<sufijo>.csv (rollup con semáforo por periodista)
"""

import sys

import pandas as pd

GENERICOS_H2 = {"contexto", "detalles", "más información", "otros datos", "generalidades"}
ANCLAS_PROHIBIDAS = {"clic aquí", "aquí", "leer más", "este enlace", "click aquí", "ver más"}
SECCIONES_CON_LISTA_OBLIGATORIA: set[str] = set()  # TODO: definir con Edwin cuando haya datos reales
ALT_PLACEHOLDERS_PROHIBIDOS = {"revista mercado", "revistamercado", "mercado", "imagen"}


def bajada_duplicada(row) -> bool:
    if pd.isna(row["h2_textos"]) or pd.isna(row["meta_desc"]):
        return False
    primer_h2 = row["h2_textos"].split(" | ")[0].strip()
    return primer_h2 == str(row["meta_desc"]).strip()


def h2_editoriales(row) -> list:
    if pd.isna(row["h2_textos"]):
        return []
    h2s = row["h2_textos"].split(" | ")
    if bajada_duplicada(row):
        h2s = h2s[1:]
    return [h for h in h2s if h.strip()]


def evaluar_nota(row: pd.Series, seccion: str) -> dict:
    h1 = "" if pd.isna(row["h1"]) else row["h1"]
    title_tag = "" if pd.isna(row["title_tag"]) else row["title_tag"]
    meta_desc = "" if pd.isna(row["meta_desc"]) else row["meta_desc"]
    primer_parrafo = "" if pd.isna(row["primer_parrafo"]) else row["primer_parrafo"]
    palabras = row["palabras_body"]
    h2s_reales = h2_editoriales(row)
    ancla = "" if pd.isna(row["ancla_primer_enlace"]) else row["ancla_primer_enlace"]
    alt = row["img_alt"]

    items = {}

    # 1. H1 editorial: 70-170 caracteres (el titular dentro del contenido, NO
    # el <title> SEO — puede llevar gancho y ser más largo que el title)
    items["h1_70_170"] = 70 <= len(h1) <= 170

    # 5. Title SEO 50-65 caracteres
    items["title_50_65"] = 50 <= len(title_tag) <= 65

    # 7. Meta descripción 150-170 caracteres
    items["meta_desc_150_170"] = 150 <= len(meta_desc) <= 170

    # 8. Meta descripción no repite el H1
    items["meta_desc_no_repite_h1"] = meta_desc.strip() != h1.strip() and len(meta_desc) > 0

    # 9. Primer párrafo: respuesta inmediata, mín 180 car
    items["primer_parrafo_180"] = len(primer_parrafo) >= 180

    # 13. H2 obligatorios: cantidad según extensión + calidad (no genéricos)
    rango_ok = (1 <= len(h2s_reales) <= 3) if palabras < 600 else (2 <= len(h2s_reales) <= 5)
    calidad_ok = all(h.strip().lower() not in GENERICOS_H2 and len(h.strip()) > 12 for h in h2s_reales) if h2s_reales else False
    items["h2_estructura"] = rango_ok and calidad_ok

    # 14. Listas y tablas obligatorias en secciones con datos enumerables (ver TODO arriba)
    if seccion in SECCIONES_CON_LISTA_OBLIGATORIA:
        items["listas_tablas"] = bool(row["tiene_lista_tabla"])
    else:
        items["listas_tablas"] = None  # No aplica

    # 15. Extensión mínima 400 palabras
    items["extension_400"] = palabras >= 400

    # 19. Tags 1-5
    items["tags_1_5"] = 1 <= row["num_tags"] <= 5

    # 20. Enlaces internos mínimo 2
    items["enlaces_min_2"] = row["num_enlaces_internos"] >= 2

    # 21. Posición primer enlace en párrafos 1-3
    ppe = row["parrafo_primer_enlace"]
    items["enlace_parrafo_1_3"] = (1 <= ppe <= 3) if pd.notna(ppe) else False

    # 22. Texto ancla 2-8 palabras, no genérico
    n_palabras_ancla = len(ancla.split())
    items["ancla_valida"] = (2 <= n_palabras_ancla <= 8) and (ancla.strip().lower() not in ANCLAS_PROHIBIDAS)

    # 24. Imagen mínimo 1200px de ancho
    items["imagen_1200px"] = pd.notna(row["img_ancho"]) and row["img_ancho"] >= 1200

    # 25. Imagen alt: no vacío, máx 120 car, no genérico
    if pd.isna(alt) or not str(alt).strip():
        items["imagen_alt"] = False
    else:
        alt_txt = str(alt).strip()
        items["imagen_alt"] = len(alt_txt) <= 120 and alt_txt.lower() not in ALT_PLACEHOLDERS_PROHIBIDOS

    # Ítems que requieren keyword objetivo definida por el editor o juicio editorial:
    # 6 (keyword en title), 10 (keyword en primer párrafo), 11 (núm. keywords),
    # 12 (ocurrencias keyword), 16 (intención resuelta), 17 (calidad vs. competencia),
    # 18 (verificación de fuente), 23 (destino del enlace vigente/relacionado)
    items["_no_automatizables"] = 8

    return items


def color_semaforo(pct: float) -> str:
    if pct >= 80:
        return "🟢"
    if pct >= 60:
        return "🟡"
    return "🔴"


def main(sufijo: str):
    raw = pd.read_csv(f"data/semaforo_raw_{sufijo}.csv")
    notas = pd.read_csv(f"data/notas_con_autor_{sufijo}.csv")
    raw = raw.merge(notas[["ruta", "seccion"]], on="ruta", how="left")

    filas = []
    for _, row in raw.iterrows():
        items = evaluar_nota(row, row["seccion"])
        aplicables = {k: v for k, v in items.items() if not k.startswith("_") and v is not None}
        n_pass = sum(1 for v in aplicables.values() if v)
        n_total = len(aplicables)
        pct = round(100 * n_pass / n_total, 1) if n_total else 0.0
        fila = {"ruta": row["ruta"], "autor": row["autor"], "seccion": row["seccion"],
                "items_pass": n_pass, "items_aplicables": n_total, "pct_cumplimiento": pct,
                "semaforo": color_semaforo(pct)}
        fila.update({f"item_{k}": v for k, v in items.items() if not k.startswith("_")})
        filas.append(fila)

    df_notas = pd.DataFrame(filas)
    df_notas.to_csv(f"data/semaforo_notas_{sufijo}.csv", index=False)

    rollup = df_notas.groupby("autor").agg(
        notas=("ruta", "count"),
        pct_cumplimiento_prom=("pct_cumplimiento", "mean"),
    ).reset_index()
    rollup["pct_cumplimiento_prom"] = rollup["pct_cumplimiento_prom"].round(1)
    rollup["semaforo"] = rollup["pct_cumplimiento_prom"].apply(color_semaforo)
    rollup = rollup.sort_values("pct_cumplimiento_prom", ascending=False)
    rollup.to_csv(f"data/semaforo_periodistas_{sufijo}.csv", index=False)

    print("=== Semáforo por periodista (14 ítems automatizables de 23) ===")
    print(rollup.to_string(index=False))
    print()
    print("=== Cumplimiento promedio por ítem (todas las notas) ===")
    item_cols = [c for c in df_notas.columns if c.startswith("item_")]
    for c in item_cols:
        serie = df_notas[c].dropna()
        if len(serie) == 0:
            continue
        print(f"  {c.replace('item_', ''):25s} {serie.mean()*100:5.1f}%  (n={len(serie)})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 data/semaforo_scoring.py <sufijo_fecha>")
        sys.exit(1)
    main(sys.argv[1])
