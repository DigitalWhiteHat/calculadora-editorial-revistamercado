"""Serie mensual REAL de impresiones (Search+Discover+News) por ruta -- pedido
de Edwin, 17-ago-2026, rechazando el registro curado a mano de eventos
concluidos: "hay forma de inferirlo... miras la entidad en Search Console en
los últimos meses y miras altas y bajas. Si se mantiene con picos altos y
constante, es una entidad que construye. Si sube de la nada y cae abrupto,
ya no sirve."

Junta 3 fuentes reales que YA existen en el proyecto (nada se descarga de
nuevo):
- data/procesado_historico_2026-01-01_2026-06-30.csv -- ene-jun 2026, ya
  trae una columna "mes" (1-6) por ruta.
- data/procesado_2026-07-01_2026-07-31.csv -- julio 2026 completo, un solo
  mes implícito.
- data/raw_historico/sc_consolidado_2026-08-16.csv -- ventana móvil actual
  (~10-jul a 13-ago), la misma fuente que ya usa datos_reales.py para
  "mes en curso". Se etiqueta como "2026-08" aunque no sea un mes calendario
  limpio -- mismo criterio ya aceptado en el resto de la app para agosto.

Uso: python3 data/construir_impresiones_mensuales.py
Escribe data/impresiones_mensuales_por_ruta.csv (ruta, mes, impresiones)
"""

import pandas as pd

COLS_IMPRESIONES = ["impresiones_search", "impresiones_discover", "impresiones_news"]


def _desde_historico() -> pd.DataFrame:
    df = pd.read_csv("data/procesado_historico_2026-01-01_2026-06-30.csv")
    df["mes"] = "2026-0" + df["mes"].astype(str)
    df["impresiones"] = df[COLS_IMPRESIONES].fillna(0).sum(axis=1)
    return df.groupby(["ruta", "mes"], as_index=False)["impresiones"].sum()


def _desde_julio() -> pd.DataFrame:
    df = pd.read_csv("data/procesado_2026-07-01_2026-07-31.csv")
    df["mes"] = "2026-07"
    df["impresiones"] = df[COLS_IMPRESIONES].fillna(0).sum(axis=1)
    return df.groupby(["ruta", "mes"], as_index=False)["impresiones"].sum()


def _desde_ventana_actual() -> pd.DataFrame:
    df = pd.read_csv("data/raw_historico/sc_consolidado_2026-08-16.csv")
    df["ruta"] = (df["pagina"]
                  .str.replace("https://www.revistamercado.do", "", regex=False)
                  .str.replace("https://revistamercado.do", "", regex=False))
    df["mes"] = "2026-08"
    return df.groupby(["ruta", "mes"], as_index=False)["impresiones"].sum()


def main():
    partes = [_desde_historico(), _desde_julio(), _desde_ventana_actual()]
    todo = pd.concat(partes, ignore_index=True)
    todo = todo.groupby(["ruta", "mes"], as_index=False)["impresiones"].sum()
    todo.to_csv("data/impresiones_mensuales_por_ruta.csv", index=False)
    print(f"-> data/impresiones_mensuales_por_ruta.csv ({len(todo)} filas)")
    print(todo.groupby("mes")["impresiones"].sum())


if __name__ == "__main__":
    main()
