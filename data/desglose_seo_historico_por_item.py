"""Igual que desglose_seo_por_item.py pero por (autor, mes) sobre la MUESTRA
histórica (hasta 12 notas/autor/mes) — para que "¿En qué está fallando el
SEO?" también funcione en los 6 meses históricos, no solo en julio (censo).

No hace falta scrapear nada nuevo: semaforo_raw_historico.csv (293 URLs) +
semaforo_raw_2026-07-01_2026-07-31.csv (para las notas evergreen reusadas de
julio) ya tienen todos los campos crudos que semaforo_scoring.evaluar_nota()
necesita. Una misma ruta puede aparecer en varios meses (nota evergreen que
sigue estando en el top-12 de más de un mes) — se evalúa una vez por cada
(autor, mes, ruta) real de la muestra, no una vez por ruta.

Uso: python3 data/desglose_seo_historico_por_item.py
Lee data/semaforo_raw_historico.csv + data/semaforo_raw_2026-07-01_2026-07-31.csv
    + data/semaforo_muestra_notas.csv + data/mapa_autor_ruta.csv
Escribe data/seo_items_por_periodista_mes.csv (autor, mes, 14 columnas % cumplimiento)
"""

import sys

import pandas as pd

sys.path.insert(0, "data")
from semaforo_scoring import evaluar_nota  # noqa: E402

LABELS_ITEM = [
    "h1_70_170", "title_50_65", "meta_desc_150_170", "meta_desc_no_repite_h1",
    "primer_parrafo_180", "h2_estructura", "listas_tablas", "extension_400",
    "tags_1_5", "enlaces_min_2", "enlace_parrafo_1_3", "ancla_valida",
    "imagen_1200px", "imagen_alt",
]


def main():
    raw_hist = pd.read_csv("data/semaforo_raw_historico.csv")
    raw_jul = pd.read_csv("data/semaforo_raw_2026-07-01_2026-07-31.csv")
    raw = pd.concat([raw_hist, raw_jul], ignore_index=True)
    raw = raw[raw["error"].isna()].drop_duplicates(subset="ruta")

    mapa = pd.read_csv("data/mapa_autor_ruta.csv")
    raw = raw.drop(columns=["autor_jsonld", "seccion_jsonld"], errors="ignore")
    raw = raw.merge(mapa[["ruta", "seccion"]], on="ruta", how="left")
    raw["seccion"] = raw["seccion"].fillna(raw["ruta"].str.strip("/").str.split("/").str[0])

    muestra = pd.read_csv("data/semaforo_muestra_notas.csv")
    muestra["mes"] = muestra["mes"].astype(int).astype(str).str.zfill(2)

    combo = muestra.merge(raw, on="ruta", how="inner", suffixes=("", "_raw"))
    print(f"{len(muestra)} filas de muestra -> {len(combo)} con datos crudos disponibles")

    filas = []
    for _, row in combo.iterrows():
        items = evaluar_nota(row, row["seccion"])
        fila = {"ruta": row["ruta"], "autor": row["autor"], "mes": row["mes"]}
        fila.update({k: v for k, v in items.items() if not k.startswith("_")})
        filas.append(fila)

    df_items = pd.DataFrame(filas)
    resumen = df_items.groupby(["autor", "mes"])[LABELS_ITEM].mean().mul(100).round(1).reset_index()
    resumen.to_csv("data/seo_items_por_periodista_mes.csv", index=False)
    print(f"-> data/seo_items_por_periodista_mes.csv ({len(resumen)} filas autor x mes)")


if __name__ == "__main__":
    main()
