"""Semáforo SEO para los 6 meses históricos (ene-jun 2026) vía MUESTREO, no
censo completo — MIGRACION-DESDE-COLOMBIACOM.md §2 (Tier 1): hasta 12 notas
por periodista por mes, las de mayor tráfico. Julio sigue siendo el único mes
con censo completo (Tier 2, pipeline separado en scrape_semaforo.py sobre las
957 notas). Esto se declara SIEMPRE como muestra en la UI, nunca como censo.

Reutiliza URLs ya scrapeadas en julio cuando coinciden (contenido evergreen
que también aparece en el top histórico) — no vuelve a pedirlas.

Uso: python3 data/semaforo_muestra_6meses.py
Lee data/procesado_historico_2026-01-01_2026-06-30.csv
    data/mapa_autor_ruta.csv
    data/semaforo_raw_2026-07-01_2026-07-31.csv (para reusar scrapes)
Escribe data/semaforo_raw_historico.csv (HTML crudo de las URLs nuevas)
        data/semaforo_muestra_autor_mes.csv (rollup: autor, mes, pct_cumplimiento,
            semaforo, notas_muestreadas)
"""

import os
import time

import pandas as pd

from scrape_semaforo import extraer_pagina
from semaforo_scoring import color_semaforo, evaluar_nota

EXCLUIR_AUTOR = {"revistamercado", "SIN_AUTOR"}
TOPE_POR_AUTOR_MES = 12


def construir_muestra() -> pd.DataFrame:
    hist = pd.read_csv("data/procesado_historico_2026-01-01_2026-06-30.csv")
    mapa = pd.read_csv("data/mapa_autor_ruta.csv")
    mapa = mapa[~mapa["autor"].isin(EXCLUIR_AUTOR)]

    df = hist.merge(mapa[["ruta", "autor", "seccion"]], on="ruta", how="inner")
    df["mes"] = df["mes"].astype(int).astype(str).str.zfill(2)

    muestra = (df.sort_values(["autor", "mes", "vistas"], ascending=[True, True, False])
                 .groupby(["autor", "mes"]).head(TOPE_POR_AUTOR_MES).reset_index(drop=True))
    return muestra


def main():
    muestra = construir_muestra()
    urls_necesarias = sorted(muestra["ruta"].unique())
    print(f"Muestra: {len(muestra)} filas (autor x mes x nota, tope {TOPE_POR_AUTOR_MES}/autor/mes), "
          f"{len(urls_necesarias)} URLs únicas")

    ya_scrapeadas = {}
    if os.path.exists("data/semaforo_raw_2026-07-01_2026-07-31.csv"):
        julio = pd.read_csv("data/semaforo_raw_2026-07-01_2026-07-31.csv")
        julio = julio[julio["error"].isna()]
        ya_scrapeadas = {row["ruta"]: row.to_dict() for _, row in julio.iterrows()}

    faltan = [u for u in urls_necesarias if u not in ya_scrapeadas]
    print(f"Ya scrapeadas (reusadas de julio): {len(urls_necesarias) - len(faltan)}")
    print(f"Nuevas por scrapear: {len(faltan)}")

    nuevas_filas = []
    for i, ruta in enumerate(faltan):
        url = "https://revistamercado.do" + ruta
        print(f"[{i+1}/{len(faltan)}] {url}")
        try:
            datos = extraer_pagina(url)
            datos["error"] = None
        except Exception as e:
            datos = {"error": str(e)}
            print(f"  ERROR: {e}")
        datos["ruta"] = ruta
        nuevas_filas.append(datos)
        time.sleep(0.3)

    nuevas_df = pd.DataFrame(nuevas_filas)
    nuevas_df.to_csv("data/semaforo_raw_historico.csv", index=False)
    print(f"\n{len(nuevas_df)} filas nuevas -> data/semaforo_raw_historico.csv")

    todas_crudas = {**ya_scrapeadas, **{row["ruta"]: row for row in nuevas_df.to_dict("records")}}

    filas_score = []
    for _, fila in muestra.iterrows():
        crudo = todas_crudas.get(fila["ruta"])
        if crudo is None or crudo.get("error") is not None:
            continue
        items = evaluar_nota(pd.Series(crudo), fila["seccion"])
        aplicables = {k: v for k, v in items.items() if not k.startswith("_") and v is not None}
        n_pass = sum(1 for v in aplicables.values() if v)
        n_total = len(aplicables)
        pct = round(100 * n_pass / n_total, 1) if n_total else None
        filas_score.append({"autor": fila["autor"], "mes": fila["mes"], "ruta": fila["ruta"],
                             "pct_cumplimiento": pct})

    notas_df = pd.DataFrame(filas_score)
    notas_df.to_csv("data/semaforo_muestra_notas.csv", index=False)

    rollup = notas_df.groupby(["autor", "mes"]).agg(
        notas_muestreadas=("ruta", "count"),
        pct_cumplimiento_prom=("pct_cumplimiento", "mean"),
    ).reset_index()
    rollup["pct_cumplimiento_prom"] = rollup["pct_cumplimiento_prom"].round(1)
    rollup["semaforo"] = rollup["pct_cumplimiento_prom"].apply(color_semaforo)
    rollup.to_csv("data/semaforo_muestra_autor_mes.csv", index=False)

    print(f"\n{len(rollup)} filas (autor x mes) -> data/semaforo_muestra_autor_mes.csv")
    pd.set_option("display.width", 160)
    pivot = rollup.pivot(index="autor", columns="mes", values="pct_cumplimiento_prom")
    print(pivot.to_string())


if __name__ == "__main__":
    main()
