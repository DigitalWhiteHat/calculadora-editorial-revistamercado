"""Selecciona las entidades/temas prioritarias a nivel de TODO el portal, deduplicadas,
para alimentar "Temas del día" (ver data/construir_temas_del_dia.py). Reutiliza
temas_recomendados.csv (ya construido por-autor, ver construir_temas_recomendados.py)
en vez de rehacer la extracción -- solo agrega por entidad y filtra variantes obvias
(ej. "Abinader" vs "Luis Abinader") con un dedup simple por substring, sin repetir la
fusión completa de entidades_periodista.py (pensada para corpus por-periodista, no
para esta lista corta y ya curada). Adaptado de calculadora-periodistas/data/
seleccionar_entidades_prioritarias.py (colombia.com) -- misma lógica, sin cambios."""

import pandas as pd

ORDEN_CONFIANZA = {"alta": 0, "media": 1, "baja": 2}


def seleccionar(top_n: int = 10) -> pd.DataFrame:
    df = pd.read_csv("data/temas_recomendados.csv")
    sub = df[df["es_recurrente"]].copy()
    sub["_orden"] = sub["confianza"].map(ORDEN_CONFIANZA)
    agg = (
        sub.groupby("entidad")
        .agg(n_autores=("autor", "nunique"), confianza_top=("_orden", "min"), tipo=("tipo", "first"))
        .reset_index()
        .sort_values(["confianza_top", "n_autores"], ascending=[True, False])
    )

    elegidas = []
    for _, fila in agg.iterrows():
        nombre = fila["entidad"]
        nombre_norm = nombre.lower()
        es_variante = any(
            nombre_norm in e.lower() or e.lower() in nombre_norm for e in elegidas
        )
        if es_variante:
            continue
        elegidas.append(nombre)
        if len(elegidas) >= top_n:
            break

    return agg[agg["entidad"].isin(elegidas)].sort_values(["confianza_top", "n_autores"], ascending=[True, False])


if __name__ == "__main__":
    resultado = seleccionar()
    resultado.to_csv("data/entidades_prioritarias_portal.csv", index=False)
    print(resultado.to_string(index=False))
