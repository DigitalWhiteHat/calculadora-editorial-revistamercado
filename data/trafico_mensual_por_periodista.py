"""Tráfico histórico REAL por mes (GA4 + GSC), SIN colapsar entre meses —
ver MIGRACION-DESDE-COLOMBIACOM.md §2: el tráfico de una nota en marzo se
cuenta en marzo, sin importar cuándo se publicó. Esto es la base Tier 1
(histórico ene-jun 2026); julio sigue siendo Tier 2 (censo completo, pipeline
separado en procesar_exports.py) y se une aparte para armar los 7 meses.

Fuente: UN solo export de GA4 con "Mes" como segunda dimensión (evita 6
exports separados) + 3 exports de GSC POR MES (Search/Discover/News — GSC no
soporta bien combinar página+fecha en un solo export sin arriesgar el límite
de filas de su UI, confirmado: el export de Search de un mes normal ya viene
con exactamente 1000 filas = tope real de la UI de Search Console, no la
cantidad real de páginas con clics — es una muestra de las de mayor tráfico
por mes, igual que ya se sabía para el export de julio).

Uso: python3 data/trafico_mensual_por_periodista.py
Lee data/raw/ga4_2026-01-01_2026-06-30.csv (con columna Mes)
    data/raw/gsc_{search,discover,news}_<rango-mes>.csv(.xlsx) por cada mes
Escribe data/procesado_historico_2026-01-01_2026-06-30.csv (ruta, mes, vistas,
    tiempo_interaccion_seg, clics/impresiones por canal, canal_dominante)
"""

import os

import pandas as pd

from procesar_exports import cargar_ga4, cargar_gsc

RAW = "data/raw"
RANGO_POR_MES = {
    "01": "2026-01-01_2026-01-31",
    "02": "2026-02-01_2026-02-28",
    "03": "2026-03-01_2026-03-31",
    "04": "2026-04-01_2026-04-30",
    "05": "2026-05-01_2026-05-31",
    "06": "2026-06-01_2026-06-30",
}


def _ruta_gsc(canal: str, rango: str) -> str | None:
    for ext in (".csv.xlsx", ".csv", ".xlsx"):
        p = f"{RAW}/gsc_{canal}_{rango}{ext}"
        if os.path.exists(p):
            return p
    return None


def procesar_historico() -> pd.DataFrame:
    ga4 = cargar_ga4(f"{RAW}/ga4_2026-01-01_2026-06-30.csv")
    if "mes" not in ga4.columns:
        raise ValueError("El GA4 histórico no trae columna 'Mes' — falta la segunda dimensión en el export.")

    bloques = []
    for mes, rango in RANGO_POR_MES.items():
        ga4_mes = ga4[ga4["mes"] == mes].drop(columns=["mes"])
        print(f"Mes {mes}: {len(ga4_mes)} URLs en GA4, {ga4_mes['vistas'].sum():,.0f} vistas")

        canales_mes = {}
        for canal, con_pos in (("search", True), ("discover", False), ("news", False)):
            ruta = _ruta_gsc(canal, rango)
            if ruta is None:
                print(f"  ⚠️  falta data/raw/gsc_{canal}_{rango}.csv(.xlsx) — {canal} queda en 0 para el mes {mes}")
                cols = ["ruta", f"clics_{canal}", f"impresiones_{canal}"] + (["posicion"] if con_pos else [])
                canales_mes[canal] = pd.DataFrame(columns=cols)
            else:
                canales_mes[canal] = cargar_gsc(ruta, canal, con_posicion=con_pos)

        df = ga4_mes.merge(canales_mes["search"], on="ruta", how="left")
        df = df.merge(canales_mes["discover"], on="ruta", how="left")
        df = df.merge(canales_mes["news"], on="ruta", how="left")
        for col in ["clics_search", "clics_discover", "clics_news",
                    "impresiones_search", "impresiones_discover", "impresiones_news"]:
            df[col] = df[col].fillna(0)

        canales = df[["clics_search", "clics_discover", "clics_news"]]
        total_gsc = canales.sum(axis=1)
        df["canal_dominante"] = canales.idxmax(axis=1).str.replace("clics_", "", regex=False)
        df.loc[total_gsc == 0, "canal_dominante"] = "(sin datos GSC)"
        df["pct_canal_dominante"] = (canales.max(axis=1) / total_gsc.replace(0, float("nan")) * 100).round(1)
        df.insert(1, "mes", mes)
        bloques.append(df)

    return pd.concat(bloques, ignore_index=True)


if __name__ == "__main__":
    resultado = procesar_historico()
    salida = "data/procesado_historico_2026-01-01_2026-06-30.csv"
    resultado.to_csv(salida, index=False)
    print(f"\n{len(resultado)} filas (ruta x mes) -> {salida}")
    print("\nVistas totales por mes:")
    print(resultado.groupby("mes")["vistas"].sum().apply(lambda v: f"{v:,.0f}"))
