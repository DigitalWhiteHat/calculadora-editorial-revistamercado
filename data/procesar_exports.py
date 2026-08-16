"""Cruza los exports de GA4 + Search Console (Search/Discover/News) por URL.
Uso: python3 data/procesar_exports.py <sufijo_fecha>
Ej.: python3 data/procesar_exports.py 2026-08-01_2026-08-31
Lee de data/raw/{ga4,gsc_search,gsc_discover,gsc_news}_<sufijo>.csv
Escribe data/procesado_<sufijo>.csv
"""

import sys

import pandas as pd

DOMINIOS = ["https://www.revistamercado.do", "https://revistamercado.do", "http://www.revistamercado.do"]


def cargar_ga4(path: str) -> pd.DataFrame:
    """Soporta el export de un solo mes (3 columnas: ruta, métrica, tiempo) y
    el histórico multi-mes (4 columnas, con "Mes" como segunda dimensión de
    la exploración de GA4, valores "01".."07"). Las columnas se mapean por el
    TEXTO del encabezado, no por posición fija: el orden y hasta la métrica
    en sí (Vistas vs. Sesiones) han cambiado entre exports reales de este
    proyecto (2026-08-09: se pasó de "Vistas" a "Sesiones" en toda la fuente,
    y el orden tiempo/métrica se invirtió) — mapear por posición fija
    corrompería los datos en silencio (cruzaría tiempo con la métrica) si
    vuelve a cambiar el orden. La columna interna se sigue llamando "vistas"
    por compatibilidad con el resto del pipeline, aunque desde 2026-08-09
    contiene SESIONES reales de GA4, no vistas de página — ver
    MIGRACION-DESDE-COLOMBIACOM.md / memoria del proyecto para el porqué."""
    with open(path, encoding="utf-8") as f:
        lineas = f.readlines()
    inicio = next(i for i, l in enumerate(lineas) if l.startswith("Ruta de página"))
    encabezados = [h.strip() for h in lineas[inicio].strip().split(",")]
    mapa: dict[int, str] = {}
    for i, h in enumerate(encabezados):
        low = h.lower()
        if "ruta" in low:
            mapa[i] = "ruta"
        elif low == "mes":
            mapa[i] = "mes"
        elif "tiempo" in low:
            mapa[i] = "tiempo_interaccion_seg"
        elif "vistas" in low or "sesion" in low:
            mapa[i] = "vistas"
    if len(mapa) != len(encabezados):
        faltantes = set(range(len(encabezados))) - set(mapa)
        raise ValueError(f"Encabezado de GA4 no reconocido en columnas {faltantes}: {encabezados}")
    nombres = [mapa[i] for i in sorted(mapa)]
    df = pd.read_csv(path, skiprows=inicio + 2, header=None, names=nombres, index_col=False)
    df = df.dropna(subset=["ruta"])
    if "mes" in df.columns:
        # "Mes" viene como "01".."07" en el CSV crudo, pero pandas lo infiere
        # como entero (pierde el cero a la izquierda) si no se fuerza a texto.
        df["mes"] = df["mes"].astype(int).astype(str).str.zfill(2)
    return df


def limpiar_ruta(serie: pd.Series) -> pd.Series:
    out = serie
    for dominio in DOMINIOS:
        out = out.str.replace(dominio, "", regex=False)
    return out


def cargar_gsc(path: str, canal: str, con_posicion: bool = False) -> pd.DataFrame:
    """Acepta tanto el .csv plano (como julio) como el .xlsx real que exporta
    Search Console (como el histórico ene-jun) — ese último trae varias hojas
    (Gráfico, Consultas, Páginas, Países...); la que importa es "Páginas",
    NUNCA la primera hoja (la primera es "Gráfico", con series diarias del
    sitio completo — mismas columnas Clics/Impresiones que confunden si se
    lee por posición de hoja en vez de por nombre)."""
    if path.endswith(".xlsx"):
        df = pd.read_excel(path, sheet_name="Páginas")
    else:
        df = pd.read_csv(path)
    df = df.rename(columns={"Páginas principales": "url", "Clics": f"clics_{canal}",
                             "Impresiones": f"impresiones_{canal}", "Posición": "posicion"})
    df["ruta"] = limpiar_ruta(df["url"])
    cols = ["ruta", f"clics_{canal}", f"impresiones_{canal}"]
    if con_posicion:
        cols.append("posicion")
    return df[cols]


def procesar(sufijo: str) -> pd.DataFrame:
    raw = "data/raw"
    ga4 = cargar_ga4(f"{raw}/ga4_{sufijo}.csv")
    search = cargar_gsc(f"{raw}/gsc_search_{sufijo}.csv", "search", con_posicion=True)
    discover = cargar_gsc(f"{raw}/gsc_discover_{sufijo}.csv", "discover")
    news = cargar_gsc(f"{raw}/gsc_news_{sufijo}.csv", "news")

    df = ga4.merge(search, on="ruta", how="left")
    df = df.merge(discover, on="ruta", how="left")
    df = df.merge(news, on="ruta", how="left")

    for col in ["clics_search", "clics_discover", "clics_news",
                "impresiones_search", "impresiones_discover", "impresiones_news"]:
        df[col] = df[col].fillna(0)

    canales = df[["clics_search", "clics_discover", "clics_news"]]
    total_gsc = canales.sum(axis=1)
    df["canal_dominante"] = canales.idxmax(axis=1).str.replace("clics_", "", regex=False)
    df.loc[total_gsc == 0, "canal_dominante"] = "(sin datos GSC)"
    df["pct_canal_dominante"] = (canales.max(axis=1) / total_gsc.replace(0, float("nan")) * 100).round(1)

    df = df.sort_values("vistas", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 data/procesar_exports.py <sufijo_fecha>")
        sys.exit(1)
    sufijo = sys.argv[1]
    resultado = procesar(sufijo)
    salida = f"data/procesado_{sufijo}.csv"
    resultado.to_csv(salida, index=False)
    print(f"{len(resultado)} filas -> {salida}")
    print(resultado.head(25).to_string())
