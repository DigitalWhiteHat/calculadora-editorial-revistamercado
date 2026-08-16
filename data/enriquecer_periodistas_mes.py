"""Une procesado_historico (ruta x mes, tráfico real) con mapa_autor_ruta
(ruta -> autor FIJO) para obtener el agregado real por (autor, mes) —
MIGRACION-DESDE-COLOMBIACOM.md §2, paso 3. Las URLs sin autor en el mapa
quedan fuera del agregado por periodista (no se inventan).

Uso: python3 data/enriquecer_periodistas_mes.py
Lee data/procesado_historico_2026-01-01_2026-06-30.csv
    data/mapa_autor_ruta.csv
Escribe data/trafico_mensual_periodista.csv (autor, mes, notas_con_trafico,
    clics, impresiones, canal_dominante, pct_canal_dominante)
"""

import pandas as pd

EXCLUIR_AUTOR = {"revistamercado", "SIN_AUTOR"}


def main():
    hist = pd.read_csv("data/procesado_historico_2026-01-01_2026-06-30.csv")
    mapa = pd.read_csv("data/mapa_autor_ruta.csv")
    mapa = mapa[~mapa["autor"].isin(EXCLUIR_AUTOR)]

    df = hist.merge(mapa[["ruta", "autor"]], on="ruta", how="inner")
    df["mes"] = df["mes"].astype(int).astype(str).str.zfill(2)

    rollup = df.groupby(["autor", "mes"], as_index=False).agg(
        notas_con_trafico=("ruta", "count"),
        vistas=("vistas", "sum"),
        clics_search=("clics_search", "sum"),
        clics_discover=("clics_discover", "sum"),
        clics_news=("clics_news", "sum"),
        impresiones_search=("impresiones_search", "sum"),
        tiempo_interaccion_seg=("tiempo_interaccion_seg", "mean"),
    )
    canales = rollup[["clics_search", "clics_discover", "clics_news"]]
    total_canal = canales.sum(axis=1)
    rollup["canal_dominante"] = canales.idxmax(axis=1).str.replace("clics_", "", regex=False)
    rollup.loc[total_canal == 0, "canal_dominante"] = "(sin datos GSC)"
    rollup["pct_canal_dominante"] = (canales.max(axis=1) / total_canal.replace(0, float("nan")) * 100).round(1)

    rollup = rollup.sort_values(["autor", "mes"])
    rollup.to_csv("data/trafico_mensual_periodista.csv", index=False)

    print(f"{len(rollup)} filas (autor x mes) -> data/trafico_mensual_periodista.csv")
    print(f"URLs del histórico SIN match de autor (quedaron fuera): "
          f"{len(hist) - len(df)} de {len(hist)} filas ruta-mes "
          f"({100*(len(hist)-len(df))/len(hist):.1f}%)")
    print()
    pivot = rollup.pivot(index="autor", columns="mes", values="vistas").fillna(0)
    pivot["total_6m"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total_6m", ascending=False)
    pd.set_option("display.width", 160)
    print(pivot.round(0).astype(int).to_string())


if __name__ == "__main__":
    main()
