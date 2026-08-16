"""Extiende el mapa ruta->autor más allá de la muestra de julio (1000 URLs)
con las notas de mayor tráfico acumulado ene-jun 2026 que todavía no tienen
autor identificado. Reusa el mismo método JSON-LD de extraer_autores_muestra.py
(sección de mayor tráfico, no censo — misma limitación ya documentada: no hay
archivo de autor navegable en revistamercado.do).

Salida: un mapa ruta->autor FIJO e independiente del mes (MIGRACION-DESDE-
COLOMBIACOM.md §2) — sin columna de vistas de un periodo específico, porque el
tráfico se une aparte, por mes, desde procesado_historico_*.csv.

Uso: python3 data/extraer_autores_historico.py [top_n]
Lee data/procesado_historico_2026-01-01_2026-06-30.csv
    data/notas_con_autor_2026-07-01_2026-07-31.csv (para no repetir URLs ya conocidas)
Escribe data/autores_nuevos_historico.csv (solo las URLs nuevas scrapeadas)
        data/mapa_autor_ruta.csv (unión: julio + histórico, ruta->autor único)
"""

import sys
import time

import pandas as pd

from extraer_autores_muestra import extraer_autor, parece_articulo


def main(top_n: int):
    hist = pd.read_csv("data/procesado_historico_2026-01-01_2026-06-30.csv")
    agg = hist.groupby("ruta", as_index=False)["vistas"].sum()
    cand = agg[agg["ruta"].apply(parece_articulo)].sort_values("vistas", ascending=False)

    julio = pd.read_csv("data/notas_con_autor_2026-07-01_2026-07-31.csv")
    conocidas = set(julio["ruta"])
    nuevas_todas = cand[~cand["ruta"].isin(conocidas)]
    nuevas = nuevas_todas.head(top_n).reset_index(drop=True)
    print(f"{len(cand)} candidatas en el histórico")
    print(f"Ya conocidas (muestra julio): {len(cand) - len(nuevas_todas)}")
    print(f"Nuevas a scrapear (top {top_n} por tráfico acumulado): {len(nuevas)}")

    filas = []
    for i, row in nuevas.iterrows():
        print(f"[{i+1}/{len(nuevas)}] {row['ruta']}")
        try:
            info = extraer_autor(row["ruta"])
            info["error"] = None
        except Exception as e:
            info = {"autor": "SIN_AUTOR", "titulo": None, "seccion": None, "fecha": None,
                     "es_sindicado": False, "error": str(e)}
            print(f"  ERROR: {e}")
        info["ruta"] = row["ruta"]
        info["vistas_acumuladas_ene_jun"] = row["vistas"]
        filas.append(info)
        time.sleep(0.3)

    nuevas_df = pd.DataFrame(filas)
    nuevas_df.to_csv("data/autores_nuevos_historico.csv", index=False)
    print(f"\n{len(nuevas_df)} filas -> data/autores_nuevos_historico.csv")
    print(f"Sin autor identificado: {(nuevas_df['autor'] == 'SIN_AUTOR').sum()}")

    mapa_julio = julio[["ruta", "autor", "titulo", "seccion", "fecha", "es_sindicado"]].copy()
    mapa_nuevas = nuevas_df[["ruta", "autor", "titulo", "seccion", "fecha", "es_sindicado"]].copy()
    mapa = pd.concat([mapa_julio, mapa_nuevas], ignore_index=True).drop_duplicates(subset="ruta")
    mapa.to_csv("data/mapa_autor_ruta.csv", index=False)
    print(f"\nMapa ruta->autor combinado (julio + histórico): {len(mapa)} URLs -> data/mapa_autor_ruta.csv")
    print(f"Autores únicos en el mapa: {mapa[~mapa['autor'].isin(['SIN_AUTOR'])]['autor'].nunique()}")


if __name__ == "__main__":
    top_n_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    main(top_n_arg)
