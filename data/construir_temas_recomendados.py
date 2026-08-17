"""Temas recomendados por periodista -- en qué entidad/tema seguir escribiendo,
excluyendo coyunturas ya cerradas. Adaptado de calculadora-periodistas/data/
construir_temas_recomendados.py (colombia.com), simplificado a las fuentes y al
extractor reales de este proyecto -- revistamercado.do no tiene la capa de
resolución de variantes de nombre de autor ni de sinónimos de entidad que sí
tiene colombia.com (roster mucho más chico, el autor ya viene canónico por
nota en todas las fuentes), así que reutiliza directamente
construir_estadisticas_propios/extraer_entidades_titulo/extraer_temas_titulo/
construir_mapa_fusion de data/entidades_periodista.py en vez de duplicar esa
lógica -- pero implementa su PROPIA agregación con la dimensión "mes" (la
fusión de variantes ya corregida se comparte; el rollup con recurrencia es
propio, porque procesar_autor() de ese módulo no rastrea mes por candidato).

Regla final "es_recurrente" (dos condiciones, las dos necesarias, igual que
colombia.com/Bloomberg Línea):
1) meses_activos >= 3 Y span (mes_reciente - mes_primero) >= 3 meses -- el
   periodista ya demostró un patrón real de volver sobre el tema.
2) demanda_reciente_ratio >= 0.10 -- share de impresiones_search (normalizado
   contra el portal ese mes) del último mes COMPARABLE con datos, sobre el
   share PICO histórico de esa entidad.

A diferencia de colombia.com (que tuvo que limitarse a ene-jun por un bug real
de metodología incomparable entre exports de Search Console con límite de
1.000 filas de la UI), revistamercado.do SÍ tiene impresiones_search reales y
SIN límite de filas en julio y en el histórico ene-jun (verificado: 859 y
5.140 valores >0 respectivamente, distribución continua, no un tope redondo)
-- se usan los 7 periodos completos (ene-jul) como base comparable, no solo 6.

Agosto (parcial, en curso) SÍ entra para contar meses_activos/span de las
notas (mismo criterio que colombia.com, que también incluye su mes parcial) --
pero NO entra en el share de impresiones del portal: notas_<mes>.csv del mes
parcial solo cubre las rutas con autor ya identificado (69 de un portal mucho
más grande), no todas las rutas como sí hacen procesado_2026-07*.csv y
procesado_historico_*.csv -- usarlo ahí inflaría artificialmente el ratio de
cualquier entidad con actividad en agosto. Limitación residual documentada,
no resuelta: se resolvería con un export de impresiones portal-completo de
agosto (ej. sc_consolidado ya sirve, ver data/raw_historico/), no con más
lógica -- pendiente para cuando agosto cierre.

Uso: python3 data/construir_temas_recomendados.py
Escribe: data/temas_recomendados.csv
"""
import glob
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import entidades_periodista as ep

DIR = Path(__file__).parent
EXCLUIR_AUTOR = {"revistamercado", "SIN_AUTOR"}
SUFIJO_JULIO = "2026-07-01_2026-07-31"

# Julio (censo completo) es el último mes con impresiones PORTAL-COMPLETAS
# comparables -- ver limitación de agosto documentada arriba.
MESES_IMPRESIONES_COMPARABLES = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]
ULTIMO_MES_COMPARABLE = MESES_IMPRESIONES_COMPARABLES[-1]


def _cargar_notas_con_mes() -> pd.DataFrame:
    """ruta, autor, titulo, mes -- de las 3 fuentes reales de este proyecto
    (julio censo, histórico ene-jun, parcial en curso)."""
    julio = pd.read_csv(DIR / f"notas_con_autor_{SUFIJO_JULIO}.csv")
    julio = julio[~julio["autor"].isin(EXCLUIR_AUTOR) & julio["titulo"].notna()].copy()
    julio["mes"] = "2026-07"
    julio = julio[["ruta", "autor", "titulo", "mes"]]

    procesado_hist = pd.read_csv(DIR / "procesado_historico_2026-01-01_2026-06-30.csv")
    procesado_hist["mes"] = "2026-" + procesado_hist["mes"].astype(int).astype(str).str.zfill(2)
    mapa = pd.read_csv(DIR / "mapa_autor_ruta.csv")
    mapa = mapa[~mapa["autor"].isin(EXCLUIR_AUTOR) & mapa["titulo"].notna()][["ruta", "autor", "titulo"]]
    historico = procesado_hist[["ruta", "mes"]].merge(mapa, on="ruta", how="inner")
    historico = historico[["ruta", "autor", "titulo", "mes"]]

    bloques = [julio, historico]
    for path in sorted(glob.glob(str(DIR / "notas_????-??.csv"))):
        parcial = pd.read_csv(path)
        parcial = parcial[~parcial["autor"].isin(EXCLUIR_AUTOR) & parcial["titulo"].notna()].copy()
        bloques.append(parcial[["ruta", "autor", "titulo", "mes"]])

    todas = pd.concat(bloques, ignore_index=True)
    return todas.drop_duplicates(subset="ruta")


def _cargar_impresiones_portal_por_ruta_mes() -> pd.DataFrame:
    """ruta, mes, impresiones -- PORTAL COMPLETO (no solo rutas con autor),
    solo julio + histórico (ver limitación de agosto en el docstring del
    módulo)."""
    julio = pd.read_csv(DIR / f"procesado_{SUFIJO_JULIO}.csv")
    julio = julio[["ruta", "impresiones_search"]].copy()
    julio["mes"] = "2026-07"

    hist = pd.read_csv(DIR / "procesado_historico_2026-01-01_2026-06-30.csv")
    hist = hist[["ruta", "mes", "impresiones_search"]].copy()
    hist["mes"] = "2026-" + hist["mes"].astype(int).astype(str).str.zfill(2)

    todas = pd.concat([julio, hist], ignore_index=True)
    todas = todas.rename(columns={"impresiones_search": "impresiones"})
    return todas[todas["mes"].isin(MESES_IMPRESIONES_COMPARABLES)]


def main():
    notas = _cargar_notas_con_mes()
    print(f"Notas con autor, título y mes real: {len(notas)}")

    impresiones = _cargar_impresiones_portal_por_ruta_mes()
    portal_impresiones_mes = impresiones.groupby("mes")["impresiones"].sum()
    print(f"Meses con impresiones portal-completas comparables: {MESES_IMPRESIONES_COMPARABLES}")

    def _demanda_reciente_ratio(rutas_entidad: set) -> float:
        sub = impresiones[impresiones["ruta"].isin(rutas_entidad)]
        serie = sub.groupby("mes")["impresiones"].sum()
        if serie.empty:
            return 0.0
        share = (serie / portal_impresiones_mes.reindex(serie.index)).fillna(0)
        pico = share.max()
        if pico <= 0:
            return 0.0
        reciente = share.reindex([ULTIMO_MES_COMPARABLE]).fillna(0).mean()
        return float(reciente / pico)

    stats = ep.construir_estadisticas_propios(notas["titulo"].dropna().tolist())
    print(f"Palabras con estadística de mayúscula calculada: {len(stats)}")

    filas = []
    for row in notas.itertuples():
        ents = ep.extraer_entidades_titulo(row.titulo, stats)
        temas = ep.extraer_temas_titulo(row.titulo)
        normas_ya = set()
        for e in ents:
            norma = ep.normalizar(e)
            if norma in ep.EXCLUIR_ENTIDADES_SITIO:
                continue
            tipo = "tema" if norma in ep.DEGRADAR_A_TEMA_COYUNTURAL else "entidad"
            filas.append({"ruta": row.ruta, "autor": row.autor, "mes": row.mes,
                          "entidad_norm": norma, "entidad_display": e, "tipo": tipo})
            normas_ya.add(norma)
        for t in temas:
            norma = ep.normalizar(t)
            if norma in ep.EXCLUIR_ENTIDADES_SITIO or norma in normas_ya:
                continue
            filas.append({"ruta": row.ruta, "autor": row.autor, "mes": row.mes,
                          "entidad_norm": norma, "entidad_display": t, "tipo": "tema"})
            normas_ya.add(norma)

    df = pd.DataFrame(filas)

    resultado = []
    for autor, grupo in df.groupby("autor"):
        rutas_por_norma = grupo.groupby("entidad_norm")["ruta"].apply(set)
        rutas_por_norma = rutas_por_norma[rutas_por_norma.apply(len) >= ep.MIN_NOTAS_CANDIDATO].to_dict()
        if not rutas_por_norma:
            continue
        grupos_para_fusion = {k: {"rutas": v} for k, v in rutas_por_norma.items()}
        mapa_fusion = ep.construir_mapa_fusion(grupos_para_fusion)

        grupo = grupo[grupo["entidad_norm"].isin(mapa_fusion)].copy()
        grupo["entidad_canon"] = grupo["entidad_norm"].map(mapa_fusion)
        grupo = grupo.drop_duplicates(subset=["entidad_canon", "ruta"])

        display_propio = (
            grupo[grupo["entidad_norm"] == grupo["entidad_canon"]]
            .groupby("entidad_canon")["entidad_display"].agg(lambda s: s.value_counts().idxmax())
        )
        display_fallback = grupo.groupby("entidad_canon")["entidad_display"].agg(lambda s: min(s, key=len))
        tipo_mayoritario = grupo.groupby("entidad_canon")["tipo"].agg(
            lambda s: "entidad" if "entidad" in set(s) else "tema")

        agg = grupo.groupby("entidad_canon").agg(notas=("ruta", "nunique")).reset_index()
        agg["autor"] = autor
        agg["entidad"] = agg["entidad_canon"].map(display_propio)
        agg["entidad"] = agg["entidad"].fillna(agg["entidad_canon"].map(display_fallback))
        agg["tipo"] = agg["entidad_canon"].map(tipo_mayoritario)

        meses_por_entidad = grupo.groupby("entidad_canon")["mes"]
        agg["meses_activos"] = agg["entidad_canon"].map(meses_por_entidad.nunique())
        agg["mes_reciente"] = agg["entidad_canon"].map(meses_por_entidad.apply(lambda s: s.dropna().max()))
        agg["mes_primero"] = agg["entidad_canon"].map(meses_por_entidad.apply(lambda s: s.dropna().min()))

        rutas_por_entidad_canon = grupo.groupby("entidad_canon")["ruta"].apply(set)
        agg["demanda_reciente_ratio"] = agg["entidad_canon"].map(rutas_por_entidad_canon).apply(_demanda_reciente_ratio)
        resultado.append(agg)

    rollup = pd.concat(resultado, ignore_index=True)

    notas_totales_autor = notas.groupby("autor").size()
    rollup["notas_totales_autor"] = rollup["autor"].map(notas_totales_autor)
    rollup = rollup[rollup["notas"] <= 0.5 * rollup["notas_totales_autor"]]

    rollup["confianza"] = rollup["notas"].apply(lambda n: "alta" if n >= 10 else "media" if n >= 3 else "baja")

    def _span(r):
        if pd.isna(r["mes_reciente"]) or pd.isna(r["mes_primero"]):
            return -1
        return (pd.Period(r["mes_reciente"], freq="M") - pd.Period(r["mes_primero"], freq="M")).n

    span_meses = rollup.apply(_span, axis=1)
    _UMBRAL_DEMANDA_RECIENTE = 0.10
    rollup["es_recurrente"] = (
        (rollup["meses_activos"] >= 3)
        & (span_meses >= 3)
        & (rollup["demanda_reciente_ratio"] >= _UMBRAL_DEMANDA_RECIENTE)
    )

    columnas = ["autor", "entidad", "tipo", "notas", "confianza", "meses_activos",
                "mes_primero", "mes_reciente", "demanda_reciente_ratio", "es_recurrente"]
    salida = rollup[columnas].sort_values(["autor", "es_recurrente", "meses_activos"], ascending=[True, False, False])
    salida.to_csv(DIR / "temas_recomendados.csv", index=False)
    print(f"\n-> temas_recomendados.csv ({len(salida)} filas, {int(salida['es_recurrente'].sum())} marcadas recurrentes)")

    print("\n=== Muestra: temas recomendados por periodista ===")
    for autor, grupo in salida[salida["es_recurrente"]].groupby("autor"):
        print(f"\n{autor}:")
        for r in grupo.head(5).itertuples():
            print(f"  🎯 {r.entidad:35s} ({r.tipo}) {r.meses_activos} meses, demanda={r.demanda_reciente_ratio:.0%}")


if __name__ == "__main__":
    main()
