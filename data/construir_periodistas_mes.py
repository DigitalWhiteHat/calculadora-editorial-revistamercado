"""Vista de periodo "<Mes> (parcial)" -- STANDALONE, igual que
construir_agosto_standalone.py de Colombia.com: separada a propósito de los
CSV de "7 meses acumulados" que alimentan Reemplazos/matriz de
especialización/simulador/alertas (esas herramientas siempre usan el
histórico cerrado, sin importar el periodo elegido en el Dashboard).

Uso: python3 data/construir_periodistas_mes.py <mes AAAA-MM>
Lee: data/notas_<mes>.csv (ver data/construir_notas_mes_actual.py -- ya trae
     posición real de Search Console por ruta, no hace falta releer el export crudo)
Escribe: data/periodistas_<mes>.csv, data/secciones_<mes>.csv
"""

import sys
from pathlib import Path

import pandas as pd

DIR = Path(__file__).parent
EXCLUIR_AUTOR = {"SIN_AUTOR"}


def main(mes: str):
    notas_path = DIR / f"notas_{mes}.csv"
    if not notas_path.exists():
        raise FileNotFoundError(f"No existe {notas_path} -- corre primero construir_notas_mes_actual.py {mes}")
    notas = pd.read_csv(notas_path)
    notas = notas[notas["autor"].notna() & ~notas["autor"].isin(EXCLUIR_AUTOR)].copy()

    # notas_<mes>.csv ya trae "posicion" (promedio real de Search Console,
    # calculado en construir_notas_mes_actual.py::cargar_gsc()) y
    # "clics_search" por ruta -- NO releer sc_consolidado ni volver a cruzar
    # aquí: un merge contra un segundo dataframe con su propia columna
    # "posicion" choca de nombres (pandas la renombra a posicion_x/posicion_y
    # y cruce["posicion"] revienta con KeyError, bug real encontrado corriendo
    # esto contra agosto 2026 real).
    con_pos = notas.dropna(subset=["posicion"])
    con_pos = con_pos[con_pos["clics_search"] > 0].copy()
    con_pos["top10"] = con_pos["posicion"] <= 10

    if con_pos.empty:
        pos_por_autor = pd.DataFrame(columns=["autor", "posicion_promedio", "notas_top10", "notas_con_posicion"])
    else:
        pos_por_autor = con_pos.groupby("autor").apply(
            lambda g: pd.Series({
                "posicion_promedio": (g["posicion"] * g["clics_search"]).sum() / g["clics_search"].sum(),
                "notas_top10": int(g["top10"].sum()),
                "notas_con_posicion": len(g),
            }), include_groups=False
        ).reset_index()
        pos_por_autor["posicion_promedio"] = pos_por_autor["posicion_promedio"].round(1)

    por_periodista = notas.groupby("autor").agg(
        notas=("ruta", "count"), trafico=("trafico_total", "sum")
    ).reset_index()
    por_periodista["mes"] = mes
    por_periodista["eficiencia"] = (por_periodista["trafico"] / por_periodista["notas"]).round(0)
    por_periodista = por_periodista.merge(pos_por_autor, on="autor", how="left")
    columnas = ["mes", "autor", "notas", "trafico", "eficiencia",
                "posicion_promedio", "notas_top10", "notas_con_posicion"]
    por_periodista[columnas].to_csv(DIR / f"periodistas_{mes}.csv", index=False)

    por_seccion = notas.groupby("seccion").agg(
        notas=("ruta", "count"), trafico=("trafico_total", "sum")
    ).reset_index()
    por_seccion["mes"] = mes
    por_seccion["eficiencia"] = (por_seccion["trafico"] / por_seccion["notas"]).round(0)
    por_seccion[["mes", "seccion", "notas", "trafico", "eficiencia"]].to_csv(
        DIR / f"secciones_{mes}.csv", index=False)

    print(f"periodistas_{mes}.csv: {len(por_periodista)} filas "
          f"(con posición: {por_periodista['posicion_promedio'].notna().sum()})")
    print(f"secciones_{mes}.csv: {len(por_seccion)} filas")
    print()
    print(por_periodista[columnas].sort_values("trafico", ascending=False).to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 data/construir_periodistas_mes.py <mes AAAA-MM>")
        sys.exit(1)
    main(sys.argv[1])
