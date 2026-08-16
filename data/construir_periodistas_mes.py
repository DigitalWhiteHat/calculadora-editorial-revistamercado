"""Vista de periodo "<Mes> (parcial)" -- STANDALONE, igual que
construir_agosto_standalone.py de Colombia.com: separada a propósito de los
CSV de "7 meses acumulados" que alimentan Reemplazos/matriz de
especialización/simulador/alertas (esas herramientas siempre usan el
histórico cerrado, sin importar el periodo elegido en el Dashboard).

Uso: python3 data/construir_periodistas_mes.py <mes AAAA-MM>
Lee: data/notas_<mes>.csv (ver data/construir_notas_mes_actual.py)
     data/raw_historico/sc_consolidado_*.csv más reciente (posición real, Search)
Escribe: data/periodistas_<mes>.csv, data/secciones_<mes>.csv
"""

import sys
from pathlib import Path

import pandas as pd

DIR = Path(__file__).parent
RAW = DIR / "raw_historico"
EXCLUIR_AUTOR = {"SIN_AUTOR"}


def normalizar(url: str) -> str:
    return (
        str(url)
        .replace("https://www.revistamercado.do", "")
        .replace("https://revistamercado.do", "")
        .rstrip("/")
        or "/"
    )


def _ultimo_archivo(patron: str) -> Path:
    candidatos = sorted(RAW.glob(patron), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidatos:
        raise FileNotFoundError(f"No hay ningún archivo '{patron}' en {RAW}")
    return candidatos[0]


def _posicion_mes() -> pd.DataFrame:
    sc = pd.read_csv(_ultimo_archivo("sc_consolidado_*.csv"))
    sc = sc[sc["superficie"] == "Search"].copy()
    sc["ruta"] = sc["pagina"].apply(normalizar)
    return sc[["ruta", "clics", "posicion"]].dropna(subset=["posicion"])


def main(mes: str):
    notas_path = DIR / f"notas_{mes}.csv"
    if not notas_path.exists():
        raise FileNotFoundError(f"No existe {notas_path} -- corre primero construir_notas_mes_actual.py {mes}")
    notas = pd.read_csv(notas_path)
    notas = notas[notas["autor"].notna() & ~notas["autor"].isin(EXCLUIR_AUTOR)].copy()

    pos = _posicion_mes()
    pos = pos[pos["clics"] > 0]
    cruce = notas.merge(pos, on="ruta", how="inner")
    cruce["top10"] = cruce["posicion"] <= 10

    if cruce.empty:
        pos_por_autor = pd.DataFrame(columns=["autor", "posicion_promedio", "notas_top10", "notas_con_posicion"])
    else:
        pos_por_autor = cruce.groupby("autor").apply(
            lambda g: pd.Series({
                "posicion_promedio": (g["posicion"] * g["clics"]).sum() / g["clics"].sum(),
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
