"""Guarda el pass/fail de cada uno de los 15 ítems SEO automatizados, por nota
(no solo el % agregado) — para poder decir exactamente EN QUÉ está fallando
cada periodista, no solo "le fue mal".

Versión simplificada frente a la de Colombia.com: esa reconcilia varias rondas
de scraping acumuladas (semaforo_raw_completo, reScrape, etc.) porque ese
proyecto ya lleva varias corridas. Para revistamercado.do, en la primera corrida
solo hay un archivo semaforo_raw_<sufijo>.csv — si más adelante hay que sumar
rondas adicionales, replicar aquí el patrón de concat + drop_duplicates(ruta)
que usa la versión de Colombia.com.

Uso: python3 data/desglose_seo_por_item.py <sufijo_fecha>
Lee data/semaforo_raw_<sufijo>.csv + data/notas_con_autor_<sufijo>.csv
Escribe data/seo_items_por_nota.csv (una fila por nota, 15 columnas booleanas)
        data/seo_items_por_periodista.csv (% de cumplimiento por periodista y por ítem)
"""

import sys

import pandas as pd

sys.path.insert(0, "data")
from semaforo_scoring import evaluar_nota  # noqa: E402

LABELS_ITEM = {
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


def main(sufijo: str):
    raw = pd.read_csv(f"data/semaforo_raw_{sufijo}.csv")
    raw = raw[raw["error"].isna()].drop_duplicates(subset="ruta")

    notas = pd.read_csv(f"data/notas_con_autor_{sufijo}.csv")
    raw = raw.drop(columns=["autor"], errors="ignore")
    raw = raw.merge(notas[["ruta", "seccion", "autor"]], on="ruta", how="left")
    raw["seccion"] = raw["seccion"].fillna(raw["ruta"].str.strip("/").str.split("/").str[0])

    filas = []
    for _, row in raw.iterrows():
        items = evaluar_nota(row, row["seccion"])
        fila = {"ruta": row["ruta"], "autor": row["autor"]}
        fila.update({k: v for k, v in items.items() if not k.startswith("_")})
        filas.append(fila)

    df_items = pd.DataFrame(filas)
    df_items.to_csv("data/seo_items_por_nota.csv", index=False)
    print(f"{len(df_items)} notas -> data/seo_items_por_nota.csv")

    item_cols = list(LABELS_ITEM.keys())
    resumen = df_items.groupby("autor")[item_cols].mean().mul(100).round(1)
    resumen.to_csv("data/seo_items_por_periodista.csv")
    print("\n=== % de cumplimiento por ítem y periodista (columnas = ítems) ===")
    print(resumen.to_string())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 data/desglose_seo_por_item.py <sufijo_fecha>")
        sys.exit(1)
    main(sys.argv[1])
