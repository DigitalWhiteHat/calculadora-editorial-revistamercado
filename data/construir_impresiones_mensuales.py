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
- data/raw_historico/sc_consolidado_*.csv (el más reciente) -- ventana móvil
  actual, la misma fuente que ya usa datos_reales.py para "mes en curso". Se
  etiqueta como "2026-08" aunque no sea un mes calendario limpio -- mismo
  criterio ya aceptado en el resto de la app para agosto. Toma el archivo
  con el periodo_fin REAL más reciente (leído del contenido, no adivinado
  por el nombre) -- bug real encontrado 21-ago-2026, dos veces seguidas:
  primero el nombre estaba fijo en sc_consolidado_2026-08-16.csv e ignoraba
  exports más nuevos; el primer intento de arreglo (ordenar por nombre de
  archivo) volvió a fallar porque conviven dos convenciones de nombre en
  raw_historico/ (sc_consolidado_2026-08-16.csv de un solo día vs.
  sc_consolidado_<inicio>_<fin>.csv con rango) -- "2026-08-16" ordena
  alfabéticamente DESPUÉS que "2026-07-14_2026-08-17" aunque el segundo sea
  el más fresco. Comparar la fecha real (periodo_fin) evita todo esto.

Uso: python3 data/construir_impresiones_mensuales.py
Escribe data/impresiones_mensuales_por_ruta.csv (ruta, mes, impresiones)
"""

import glob

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


def _archivo_sc_consolidado_mas_reciente() -> str:
    candidatos = glob.glob("data/raw_historico/sc_consolidado_*.csv")
    mejor_archivo, mejor_fecha = None, None
    for archivo in candidatos:
        fin = pd.read_csv(archivo, usecols=["periodo_fin"], nrows=1)["periodo_fin"].iloc[0]
        fin = pd.Timestamp(fin)
        if mejor_fecha is None or fin > mejor_fecha:
            mejor_archivo, mejor_fecha = archivo, fin
    return mejor_archivo


def _desde_ventana_actual() -> pd.DataFrame:
    archivo = _archivo_sc_consolidado_mas_reciente()
    df = pd.read_csv(archivo)
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
