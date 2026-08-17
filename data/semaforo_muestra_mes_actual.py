"""Semáforo SEO del mes en curso (parcial) vía MUESTREO -- mismo espíritu que
semaforo_muestra_6meses.py (histórico ene-jun), pero con la regla de tamaño
corregida (16-ago-2026, Edwin, tras encontrar que agosto mostraba 7-29 notas
por periodista cuando escriben 8-9/día -- root cause real: el tope de
scraping de autoría estaba pensado para corridas diarias, no la primera
corrida de un mes; corregido en construir_notas_mes_actual.py):

"sí puede sacar una muestra... pero tiene que ser más representativa de aquí
en adelante... la muestra debería ser mínimo el diez por ciento de las notas
que hace el periodista." -- a diferencia del histórico (tope FIJO de 12/autor/
mes, que para un periodista de 200 notas/mes es apenas 6% pero para uno de 15
notas/mes es 80%), acá el tamaño es proporcional: ceil(10% de sus notas reales
del mes), nunca menos de 1 si escribió algo.

Caso especial Jhojhanni Fiorini (mismo criterio ya usado en "Temas en los que
le rinde" y "Notas más vistas del periodo", ver AUTORES_EXCLUIR_LOTERIA en
app/individual.py): los resultados de lotería son contenido de servicio DIARIO
recurrente con la misma plantilla -- 2-3 notas ya dicen cómo publica esa parte.
El 10% se calcula solo sobre sus notas NO-lotería, para no gastar la muestra
en 15 copias casi idénticas del mismo formato.

Uso: python3 data/semaforo_muestra_mes_actual.py <mes AAAA-MM>
Lee: data/notas_<mes>.csv (ver construir_notas_mes_actual.py)
     data/semaforo_raw_2026-07-01_2026-07-31.csv + data/semaforo_raw_historico.csv
     (para reusar scrapes de notas evergreen que ya se scrapearon antes)
Escribe: data/semaforo_raw_<mes>.csv (HTML crudo de las URLs nuevas)
         data/semaforo_muestra_notas_<mes>.csv (ruta, autor, pct_cumplimiento)
         data/semaforo_muestra_autor_<mes>.csv (rollup autor -> pct_cumplimiento_prom, semaforo)
"""

import math
import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from scrape_semaforo import extraer_pagina
from semaforo_scoring import color_semaforo, evaluar_nota

DIR = Path(__file__).parent
MIN_PCT_MUESTRA = 0.10
AUTORES_EXCLUIR_LOTERIA = {"Jhojhanni Fiorini"}
TOPE_LOTERIA = 3


def construir_muestra(mes: str) -> pd.DataFrame:
    notas = pd.read_csv(DIR / f"notas_{mes}.csv")
    notas = notas[notas["titulo"].notna()].copy()

    filas = []
    for autor, grupo in notas.groupby("autor"):
        grupo = grupo.sort_values("vistas", ascending=False)
        if autor in AUTORES_EXCLUIR_LOTERIA:
            es_loteria = grupo["titulo"].str.contains("loter", case=False, na=False)
            loteria = grupo[es_loteria].head(TOPE_LOTERIA)
            resto = grupo[~es_loteria]
            n_resto = max(1, math.ceil(MIN_PCT_MUESTRA * len(resto))) if len(resto) else 0
            filas.append(loteria)
            filas.append(resto.head(n_resto))
        else:
            n = max(1, math.ceil(MIN_PCT_MUESTRA * len(grupo))) if len(grupo) else 0
            filas.append(grupo.head(n))

    return pd.concat(filas, ignore_index=True) if filas else notas.head(0)


def main(mes: str):
    muestra = construir_muestra(mes)
    urls_necesarias = sorted(muestra["ruta"].unique())
    print(f"Muestra: {len(muestra)} notas de {muestra['autor'].nunique()} periodistas "
          f"(mínimo {MIN_PCT_MUESTRA:.0%} de las notas reales de cada uno), "
          f"{len(urls_necesarias)} URLs únicas")
    print(muestra.groupby("autor").size().to_string())

    ya_scrapeadas = {}
    for archivo in ["semaforo_raw_2026-07-01_2026-07-31.csv", "semaforo_raw_historico.csv"]:
        ruta_archivo = DIR / archivo
        if ruta_archivo.exists():
            df = pd.read_csv(ruta_archivo)
            df = df[df["error"].isna()]
            ya_scrapeadas.update({row["ruta"]: row.to_dict() for _, row in df.iterrows()})

    faltan = [u for u in urls_necesarias if u not in ya_scrapeadas]
    print(f"\nYa scrapeadas (reusadas de julio/histórico): {len(urls_necesarias) - len(faltan)}")
    print(f"Nuevas por scrapear: {len(faltan)}")

    nuevas_filas = []
    for i, ruta in enumerate(faltan):
        url = "https://revistamercado.do" + ruta
        print(f"[{i + 1}/{len(faltan)}] {url}")
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
    out_raw = DIR / f"semaforo_raw_{mes}.csv"
    nuevas_df.to_csv(out_raw, index=False)
    print(f"\n{len(nuevas_df)} filas nuevas -> {out_raw}")

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
        filas_score.append({"autor": fila["autor"], "ruta": fila["ruta"], "pct_cumplimiento": pct})

    notas_df = pd.DataFrame(filas_score)
    out_notas = DIR / f"semaforo_muestra_notas_{mes}.csv"
    notas_df.to_csv(out_notas, index=False)

    rollup = notas_df.groupby("autor").agg(
        notas_muestreadas=("ruta", "count"),
        pct_cumplimiento_prom=("pct_cumplimiento", "mean"),
    ).reset_index()
    rollup["pct_cumplimiento_prom"] = rollup["pct_cumplimiento_prom"].round(1)
    rollup["semaforo"] = rollup["pct_cumplimiento_prom"].apply(color_semaforo)
    out_autor = DIR / f"semaforo_muestra_autor_{mes}.csv"
    rollup.to_csv(out_autor, index=False)

    print(f"\n{len(rollup)} periodistas -> {out_autor}")
    print(rollup.to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 data/semaforo_muestra_mes_actual.py <mes AAAA-MM>")
        sys.exit(1)
    main(sys.argv[1])
