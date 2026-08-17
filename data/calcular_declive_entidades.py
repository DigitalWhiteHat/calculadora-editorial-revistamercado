"""Qué ENTIDAD/TEMA está bajando -- a nivel de TODO EL PORTAL, ventana móvil de
~17 días vs. los ~17 días anteriores (no mes calendario). Pedido de Edwin,
16-ago-2026 (mismo pedido ya resuelto en calculadora-periodistas/colombia.com):
"no podemos tomar el último mes como referencia... corre, de la fecha de
actualización, treinta días hacia atrás".

BUG REAL encontrado y descartado en colombia.com antes de publicar ese script
(mismo riesgo aquí, documentado para no repetirlo): comparar tráfico ACUMULADO
por fecha de publicación entre dos ventanas sesga todo hacia "cayendo", porque
el contenido más nuevo simplemente no ha tenido tiempo de acumular vistas. Este
script usa el export crudo de GA4 con columnas periodo=actual/anterior, donde
screenPageViews SÍ está genuinamente delimitado por fecha (no acumulado) --
así lo garantiza GA4 al hacer un query de rango de fechas.

Reutiliza el extractor de entidades/temas de entidades_periodista.py TAL CUAL
(mismas funciones, mismo guard de EXCLUIR_ENTIDADES_SITIO/DEGRADAR_A_TEMA_
COYUNTURAL ya corregido 16-ago-2026 -- "las entidades no pueden ser elementos
coyunturales") aplicado a TODO el portal a la vez en vez de por periodista.

Uso: python3 data/calcular_declive_entidades.py
Lee data/raw_historico/ga4_pages_screens_periodos_2026-08-16.csv
Escribe data/entidades_declive_portal.csv
"""
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, "data")
from entidades_periodista import (  # noqa: E402
    DEGRADAR_A_TEMA_COYUNTURAL,
    EXCLUIR_ENTIDADES_SITIO,
    construir_estadisticas_propios,
    construir_mapa_fusion,
    extraer_entidades_titulo,
    extraer_temas_titulo,
    normalizar,
)

DIR = Path(__file__).parent
RAW_GA4 = DIR / "raw_historico" / "ga4_pages_screens_periodos_2026-08-16.csv"
UMBRAL_VOLUMEN = 300  # piso de tráfico en la ventana "anterior" para no reportar ruido
MAX_PCT_BOILERPLATE_PORTAL = 0.15  # a nivel portal, no 0.50 (ese umbral es por-periodista)
MIN_NOTAS_CANDIDATO = 2
MIN_NOTAS_FUSION_OVERLAP = 0.80


def _extraer_por_periodo(df: pd.DataFrame) -> pd.DataFrame:
    """Mismo núcleo de extracción+fusión que entidades_periodista.py::procesar_autor(),
    aplicado a UN periodo (actual/anterior) de todo el portal a la vez en vez de a
    un solo autor."""
    titulos = df["pageTitle"].dropna().tolist()
    stats = construir_estadisticas_propios(titulos)

    candidatos = []  # (forma, tipo, pagePath)
    for row in df.itertuples():
        titulo = row.pageTitle
        if not isinstance(titulo, str) or not titulo.strip():
            continue
        ents = extraer_entidades_titulo(titulo, stats)
        temas = extraer_temas_titulo(titulo)

        normas_ya_en_esta_nota = set()
        for e in ents:
            norma = normalizar(e)
            if norma in EXCLUIR_ENTIDADES_SITIO:
                continue
            tipo_e = "tema" if norma in DEGRADAR_A_TEMA_COYUNTURAL else "entidad"
            candidatos.append((e, tipo_e, row.pagePath))
            normas_ya_en_esta_nota.add(norma)
        for t in temas:
            norma = normalizar(t)
            if norma in EXCLUIR_ENTIDADES_SITIO or norma in normas_ya_en_esta_nota:
                continue
            candidatos.append((t, "tema", row.pagePath))
            normas_ya_en_esta_nota.add(norma)

    grupos = defaultdict(lambda: {"formas": defaultdict(int), "tipo": defaultdict(int),
                                   "rutas": set(), "trafico": 0})
    trafico_por_ruta = df.set_index("pagePath")["screenPageViews"].to_dict()
    for forma, tipo, ruta in candidatos:
        norma = normalizar(forma)
        g = grupos[norma]
        g["formas"][forma] += 1
        g["tipo"][tipo] += 1
        g["rutas"].add(ruta)

    mapa_fusion = construir_mapa_fusion(grupos)
    fusionados = defaultdict(lambda: {"formas": defaultdict(int), "tipo": defaultdict(int), "rutas": set()})
    for k, g in grupos.items():
        raiz = mapa_fusion[k]
        fusionados[raiz]["rutas"] |= g["rutas"]
        for f, c in g["formas"].items():
            fusionados[raiz]["formas"][f] += c
        for t, c in g["tipo"].items():
            fusionados[raiz]["tipo"][t] += c

    total_paginas = df["pagePath"].nunique()
    filas = []
    for raiz, g in fusionados.items():
        if raiz in EXCLUIR_ENTIDADES_SITIO:
            continue
        n_paginas = len(g["rutas"])
        if n_paginas < MIN_NOTAS_CANDIDATO:
            continue
        if n_paginas / total_paginas > MAX_PCT_BOILERPLATE_PORTAL:
            continue
        tipo_final = "entidad" if g["tipo"].get("entidad", 0) > 0 else "tema"
        forma_final = max(g["formas"].items(), key=lambda kv: (kv[1], len(kv[0])))[0]
        trafico = sum(trafico_por_ruta.get(r, 0) for r in g["rutas"])
        filas.append({"entidad": forma_final, "entidad_norm": raiz, "tipo": tipo_final,
                      "paginas": n_paginas, "trafico": trafico})

    return pd.DataFrame(filas)


def main():
    df = pd.read_csv(RAW_GA4)
    print(f"Filas totales: {len(df)} -- periodos: {df['periodo'].unique().tolist()}")
    for p in df["periodo"].unique():
        sub = df[df["periodo"] == p]
        print(f"  {p}: {sub['periodo_inicio'].iloc[0]} a {sub['periodo_fin'].iloc[0]}, "
              f"{sub['pagePath'].nunique()} páginas, {sub['screenPageViews'].sum():,.0f} vistas")

    actual = _extraer_por_periodo(df[df["periodo"] == "actual"])
    anterior = _extraer_por_periodo(df[df["periodo"] == "anterior"])
    print(f"\nEntidades/temas detectados -- actual: {len(actual)}, anterior: {len(anterior)}")

    comparado = actual.merge(anterior, on=["entidad_norm", "tipo"], how="outer",
                              suffixes=("_actual", "_anterior"))
    comparado["entidad"] = comparado["entidad_actual"].fillna(comparado["entidad_anterior"])
    comparado["trafico_actual"] = comparado["trafico_actual"].fillna(0)
    comparado["trafico_anterior"] = comparado["trafico_anterior"].fillna(0)
    comparado["paginas_actual"] = comparado["paginas_actual"].fillna(0)
    comparado["paginas_anterior"] = comparado["paginas_anterior"].fillna(0)

    comparado = comparado[(comparado["trafico_anterior"] >= UMBRAL_VOLUMEN)
                           & (comparado["trafico_actual"] > 0) & (comparado["trafico_anterior"] > 0)]
    comparado["pct_cambio"] = 100 * (comparado["trafico_actual"] - comparado["trafico_anterior"]) / comparado["trafico_anterior"]
    comparado = comparado.sort_values("pct_cambio")

    columnas = ["entidad", "tipo", "trafico_actual", "trafico_anterior", "pct_cambio",
                "paginas_actual", "paginas_anterior"]
    out = DIR / "entidades_declive_portal.csv"
    comparado[columnas].to_csv(out, index=False)
    print(f"\nGuardado -> {out} ({len(comparado)} filas, entidades con tráfico en ambos periodos)")

    print("\n=== Top 15 en mayor declive ===")
    for r in comparado.head(15).itertuples():
        print(f"  {r.entidad:<35} ({r.tipo}) {r.trafico_anterior:>10,.0f} -> {r.trafico_actual:>8,.0f}  ({r.pct_cambio:.0f}%)")

    print("\n=== Top 10 en mayor subida ===")
    for r in comparado.sort_values('pct_cambio', ascending=False).head(10).itertuples():
        print(f"  {r.entidad:<35} ({r.tipo}) {r.trafico_anterior:>10,.0f} -> {r.trafico_actual:>8,.0f}  (+{r.pct_cambio:.0f}%)")


if __name__ == "__main__":
    main()
