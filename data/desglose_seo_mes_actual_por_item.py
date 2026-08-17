"""Igual que desglose_seo_historico_por_item.py pero para el MES EN CURSO
(parcial) -- sobre la muestra 10% real armada por
semaforo_muestra_mes_actual.py, no el tope fijo de 12/autor/mes del
histórico. Sin esto, "¿En qué está fallando el SEO?" queda vacío en
cualquier perfil mientras el mes está en curso, aunque el semáforo agregado
(pct_cumplimiento) sí exista -- bug real encontrado 2026-08-17 (Edwin,
viendo "Sin datos suficientes" en un periodista con 82 notas reales del
mes: "no estás revisando... el título, entidad... es una absurda mentira").
diagnostico_seo_por_autor_mes() en app/datos_reales.py solo leía el
histórico; hay que correr esto Y extender esa función para que también
mire este archivo cuando el periodo es "parcial".

Uso: python3 data/desglose_seo_mes_actual_por_item.py <mes AAAA-MM>
Lee: data/semaforo_raw_<mes>.csv + data/semaforo_muestra_notas_<mes>.csv
     + data/mapa_autor_ruta.csv (para la sección real de cada ruta)
Escribe: data/seo_items_por_periodista_mes_actual.csv (autor, mes, 14 items %)
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


def main(mes: str):
    raw = pd.read_csv(f"data/semaforo_raw_{mes}.csv")
    raw = raw[raw["error"].isna()].drop_duplicates(subset="ruta")

    mapa = pd.read_csv("data/mapa_autor_ruta.csv")
    raw = raw.drop(columns=["autor_jsonld", "seccion_jsonld"], errors="ignore")
    raw = raw.merge(mapa[["ruta", "seccion"]], on="ruta", how="left")
    raw["seccion"] = raw["seccion"].fillna(raw["ruta"].str.strip("/").str.split("/").str[0])

    muestra = pd.read_csv(f"data/semaforo_muestra_notas_{mes}.csv")
    combo = muestra.merge(raw, on="ruta", how="inner", suffixes=("", "_raw"))
    print(f"{len(muestra)} filas de muestra -> {len(combo)} con datos crudos disponibles")

    filas = []
    for _, row in combo.iterrows():
        items = evaluar_nota(row, row["seccion"])
        fila = {"ruta": row["ruta"], "autor": row["autor"], "mes": mes}
        fila.update({k: v for k, v in items.items() if not k.startswith("_")})
        filas.append(fila)

    df_items = pd.DataFrame(filas)
    resumen = df_items.groupby(["autor", "mes"])[LABELS_ITEM].mean().mul(100).round(1).reset_index()
    out = "data/seo_items_por_periodista_mes_actual.csv"
    resumen.to_csv(out, index=False)
    print(f"-> {out} ({len(resumen)} filas autor x mes)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 data/desglose_seo_mes_actual_por_item.py <mes AAAA-MM>")
        sys.exit(1)
    main(sys.argv[1])
