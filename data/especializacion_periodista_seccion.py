"""Matriz periodista x sección para Revista Mercado — mismo propósito y
esquema de salida que calculadora-periodistas/data/especializacion_periodista_seccion.py
(Colombia.com), adaptado a las fuentes reales de RM: julio 2026 (censo
completo) + enero-junio 2026 (histórico), usando seccion_raw (con
subsección, ej. "empresas/sport-business") en vez del "seccion" plano de
Colombia.com — RM ya es más granular en el resto de la app, se mantiene esa
granularidad aquí también.

Confianza por celda según volumen de muestra (mismos 3 niveles que
Colombia.com): alta >=10 notas, media 3-9, baja <3.

Uso: python3 data/especializacion_periodista_seccion.py
Escribe: data/especializacion_periodista_seccion.csv
"""
import pandas as pd

SUFIJO_JULIO = "2026-07-01_2026-07-31"
EXCLUIR_AUTOR = {"revistamercado", "SIN_AUTOR"}


def confianza(n):
    if n >= 10:
        return "alta"
    if n >= 3:
        return "media"
    return "baja"


def _extraer_seccion(ruta: pd.Series) -> pd.Series:
    """Copia deliberada de app/datos_reales.py::_extraer_seccion (no se
    cruzan imports entre app/ y data/)."""
    partes = ruta.str.strip("/").str.split("/")
    seg1 = partes.str[0]
    seg2 = partes.apply(lambda p: p[1] if len(p) >= 3 else None)
    return seg1.where(seg2.isna(), seg1 + "/" + seg2)


def _julio() -> pd.DataFrame:
    notas = pd.read_csv(f"data/notas_con_autor_{SUFIJO_JULIO}.csv")
    notas = notas[~notas["autor"].isin(EXCLUIR_AUTOR)].copy()
    procesado = pd.read_csv(f"data/procesado_{SUFIJO_JULIO}.csv")
    procesado["seccion_raw"] = _extraer_seccion(procesado["ruta"])
    notas = notas.drop(columns=["vistas"], errors="ignore").merge(
        procesado[["ruta", "vistas", "seccion_raw"]], on="ruta", how="left")
    return notas[["autor", "seccion_raw", "vistas"]].rename(columns={"vistas": "trafico_total"})


def _historico() -> pd.DataFrame:
    procesado = pd.read_csv("data/procesado_historico_2026-01-01_2026-06-30.csv")
    procesado["seccion_raw"] = _extraer_seccion(procesado["ruta"])
    mapa = pd.read_csv("data/mapa_autor_ruta.csv")
    mapa = mapa[~mapa["autor"].isin(EXCLUIR_AUTOR)]
    notas = procesado.merge(mapa[["ruta", "autor"]], on="ruta", how="inner")
    return notas[["autor", "seccion_raw", "vistas"]].rename(columns={"vistas": "trafico_total"})


def main():
    julio = _julio()
    # Solo el equipo ACTUAL (activo en julio) -- quienes ya no escriben no
    # deben aparecer como candidatos de reemplazo.
    activos = set(julio["autor"].dropna().unique())

    hist = _historico()
    hist = hist[hist["autor"].isin(activos)]

    df = pd.concat([julio, hist], ignore_index=True)
    piv = df.groupby(["autor", "seccion_raw"]).agg(
        notas=("trafico_total", "count"), trafico=("trafico_total", "sum")
    ).reset_index().rename(columns={"seccion_raw": "seccion"})
    piv["trafico_por_nota"] = (piv["trafico"] / piv["notas"]).round(0)
    piv["confianza"] = piv["notas"].apply(confianza)

    mediana_seccion = piv.groupby("seccion")["trafico_por_nota"].median().rename("mediana_seccion_otros")
    piv = piv.merge(mediana_seccion, on="seccion", how="left")

    total_periodista = piv.groupby("autor")["trafico"].transform("sum")
    piv["pct_trafico_periodista"] = (piv["trafico"] / total_periodista * 100).round(1)

    piv = piv.sort_values(["autor", "trafico_por_nota"], ascending=[True, False])
    piv.to_csv("data/especializacion_periodista_seccion.csv", index=False)

    print(f"Filas periodista x sección: {len(piv)}")
    print(f"Periodistas: {piv['autor'].nunique()}, secciones: {piv['seccion'].nunique()}")
    print(piv.to_string(index=False))


if __name__ == "__main__":
    main()
