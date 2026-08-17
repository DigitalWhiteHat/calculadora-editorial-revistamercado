"""Limpia el export crudo de YouTube Studio (Modo avanzado, filtro 'Orgánica',
periodo 'Desde el principio', desglose por Contenido) a un CSV con el mismo
esquema que ya usa app/youtube.py.

El export trae solo el Top 500 por Tiempo de reproducción -- YouTube Studio no
deja bajar más filas de una tabla desglosada por video. Se declara así en la UI,
no se presenta como "todo el canal".

Uso: python3 data/construir_youtube_lifetime.py
Lee data/youtube_lifetime_raw.csv (export crudo), escribe data/youtube_lifetime_organico.csv
"""

import pandas as pd

RUTA_CRUDA = "data/youtube_lifetime_raw.csv"
RUTA_SALIDA = "data/youtube_lifetime_organico.csv"


def main():
    df = pd.read_csv(RUTA_CRUDA)
    df = df[df["Contenido"].notna()]
    df = df[df["Contenido"] != "Total"]
    df = df[~df["Contenido"].astype(str).str.startswith("Mostrando")]

    limpio = pd.DataFrame({
        "video_id": df["Contenido"],
        "titulo": df["Título del video"],
        "fecha_publicacion": pd.to_datetime(df["Tiempo de publicación del video"], errors="coerce"),
        "duracion_seg": pd.to_numeric(df["Duración"], errors="coerce"),
        "pct_reproducido": pd.to_numeric(df["Porcentaje promedio reproducido (%)"], errors="coerce"),
        "duracion_promedio_vista": df["Duración promedio de vistas"],
        "vistas": pd.to_numeric(df["Vistas"], errors="coerce"),
        "horas_reproduccion": pd.to_numeric(df["Tiempo de reproducción (horas)"], errors="coerce"),
        "ingresos_usd": pd.to_numeric(df["Ingresos estimados (USD)"], errors="coerce"),
    })
    limpio = limpio[limpio["fecha_publicacion"].notna()]
    limpio.to_csv(RUTA_SALIDA, index=False)
    print(f"-> {RUTA_SALIDA} ({len(limpio)} filas)")
    print(f"Vistas totales: {limpio['vistas'].sum():,.0f}")
    print(f"Ingresos no nulos: {limpio['ingresos_usd'].notna().sum()}")


if __name__ == "__main__":
    main()
