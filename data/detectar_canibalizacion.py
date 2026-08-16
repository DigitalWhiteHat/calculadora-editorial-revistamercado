"""Detecta canibalización interna: un mismo periodista publicando varias notas
sobre el mismo tema/entidad, compitiendo por la misma intención de búsqueda.

Usa título + sección + autor de cada nota. Compara títulos por similitud de
palabras significativas (Jaccard sobre tokens, quitando stopwords) dentro del
mismo periodista y sección — si dos notas comparten >=45% de sus palabras
clave, se marcan como posible canibalización.

Adaptado de calculadora-periodistas/data/detectar_canibalizacion.py (Colombia.com).
PATRONES_RECURRENTES cambia por medio a propósito: son los formatos de servicio
que CADA sitio republica a diario/semanalmente sin que sea canibalización real
(apuntan a una búsqueda de un día distinto). Para revistamercado.do, según los
beats de apertura fija documentados por Edwin (MAESTRO §11): Elba abre con
dólar+clima, Giovanni con loterías+tabla de posiciones — ver
revistamercado-overview en memoria. Revisar y ampliar esta lista con Edwin en
cuanto se vea el primer lote real de títulos (puede haber otros formatos
recurrentes que no están documentados todavía).

Uso: python3 data/detectar_canibalizacion.py <sufijo_fecha>
Lee data/notas_con_autor_<sufijo>.csv (columnas: ruta, titulo, seccion, autor, vistas)
Escribe data/canibalizacion_notas.csv (pares detectados)
        data/canibalizacion_periodistas.csv (rollup: % de notas en canibalización)
"""

import re
import sys
from itertools import combinations

import pandas as pd

STOPWORDS = {
    "el", "la", "los", "las", "de", "del", "en", "y", "a", "que", "con", "por",
    "para", "su", "sus", "un", "una", "unos", "unas", "es", "se", "lo", "al",
    "como", "más", "sobre", "tras", "ya", "no", "si", "qué", "así", "esto",
    "esta", "este", "estos", "estas", "hoy", "cómo", "dónde", "donde", "cuándo",
    "cuando", "quién", "quien", "vs", "mercado", "rd",
}

UMBRAL_SIMILITUD = 0.45

# Formatos de servicio de revistamercado.do que se republican a propósito con
# apertura fija por periodista (MAESTRO §11) — cada versión apunta a una
# búsqueda de un día distinto, no es canibalización real.
PATRONES_RECURRENTES = [r"d[óo]lar hoy", r"tipo de cambio", r"clima (hoy|en)",
                        r"resultados? de la[s]? loter[íi]as?", r"resultados? de leidsa",
                        r"resultados? de loteka", r"tabla de posiciones",
                        r"pron[óo]stico del tiempo"]


def es_recurrente(titulo: str) -> bool:
    t = str(titulo).lower()
    return any(re.search(p, t) for p in PATRONES_RECURRENTES)


def tokens(titulo: str) -> set:
    palabras = re.findall(r"[a-záéíóúñ0-9]+", str(titulo).lower())
    # Los números SIEMPRE se conservan aunque sean cortos (ej. "1", "22" de una
    # fecha) — si no, dos notas de servicio de días distintos quedan como falsos
    # duplicados idénticos cuando en realidad apuntan a búsquedas de días distintos.
    return {p for p in palabras if p.isdigit() or (p not in STOPWORDS and len(p) > 2)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def main(sufijo: str):
    df = pd.read_csv(f"data/notas_con_autor_{sufijo}.csv")
    df = df.dropna(subset=["titulo"]).reset_index(drop=True)
    df["tokens"] = df["titulo"].apply(tokens)

    pares = []
    for (autor, seccion), g in df.groupby(["autor", "seccion"]):
        if len(g) < 2:
            continue
        for i, j in combinations(g.index, 2):
            if es_recurrente(df.loc[i, "titulo"]) and es_recurrente(df.loc[j, "titulo"]):
                continue
            sim = jaccard(df.loc[i, "tokens"], df.loc[j, "tokens"])
            if sim >= UMBRAL_SIMILITUD:
                pares.append({
                    "autor": autor, "seccion": seccion, "similitud": round(sim, 2),
                    "titulo_1": df.loc[i, "titulo"], "ruta_1": df.loc[i, "ruta"], "vistas_1": df.loc[i, "vistas"],
                    "titulo_2": df.loc[j, "titulo"], "ruta_2": df.loc[j, "ruta"], "vistas_2": df.loc[j, "vistas"],
                })

    pares_df = pd.DataFrame(pares).sort_values("similitud", ascending=False)
    pares_df.to_csv("data/canibalizacion_notas.csv", index=False)
    print(f"Pares de posible canibalización detectados: {len(pares_df)}")

    notas_afectadas = set(pares_df["ruta_1"]) | set(pares_df["ruta_2"])
    rollup = df.groupby("autor").agg(notas_totales=("ruta", "count")).reset_index()
    afectadas_por_autor = df[df["ruta"].isin(notas_afectadas)].groupby("autor").size()
    rollup["notas_en_canibalizacion"] = rollup["autor"].map(afectadas_por_autor).fillna(0).astype(int)
    rollup["pct_canibalizacion"] = (100 * rollup["notas_en_canibalizacion"] / rollup["notas_totales"]).round(1)
    rollup = rollup.sort_values("pct_canibalizacion", ascending=False)
    rollup.to_csv("data/canibalizacion_periodistas.csv", index=False)

    print()
    print(rollup.to_string(index=False))
    if not pares_df.empty:
        print()
        print("=== Top 10 pares más similares (para revisión editorial) ===")
        print(pares_df.head(10)[["autor", "similitud", "titulo_1", "titulo_2"]].to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 data/detectar_canibalizacion.py <sufijo_fecha>")
        sys.exit(1)
    main(sys.argv[1])
