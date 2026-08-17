"""Fusiona ingresos reales por video en los datasets de YouTube.

Contexto: el primer intento de sacar ingresos fue vía el export "Modo avanzado"
filtrado por AD_STATUS_ORGANIC (el mismo filtro "Orgánica" usado para vistas) --
esa combinación específica devuelve Ingresos vacío para TODO el canal, incluida
la fila Total. No es un problema de permisos ("Editor" vs "Propietario") como
se pensó al inicio -- es que YouTube Studio no cruza esas dos dimensiones
(AD_STATUS x Ingresos) en modo avanzado. Cambiando el filtro a "Videos"
(CREATOR_CONTENT_TYPE) o quitando el filtro de contenido, los ingresos SÍ
aparecen con cifras reales, confirmado también en la vista estándar de
Analytics -> pestaña "Ingresos" (sin modo avanzado), que coincide en el total.

Los exports de ingresos NO están filtrados por "Orgánica" (esa combinación
sigue rota) -- son ingresos de TODO el tráfico del video, tope de 500 filas por
export (mismo límite de YouTube Studio en modo avanzado). Por eso el cruce por
video_id es parcial: un video puede estar en el top 500 por vistas orgánicas
pero no en el top 500 por ingresos si sus ingresos reales son muy bajos -- para
esos casos se distingue "no en la muestra de 500" de "$0 real".

Uso: python3 data/fusionar_ingresos_youtube.py
Lee data/youtube_ingresos_raw.csv + data/youtube_ingresos_agosto_raw.csv,
escribe la columna ingresos_usd en data/youtube_lifetime_organico.csv y
data/youtube_agosto_organico.csv.
"""

import pandas as pd


def _limpiar_ingresos(ruta_cruda: str) -> pd.DataFrame:
    df = pd.read_csv(ruta_cruda)
    df = df[df["Contenido"].notna()]
    df = df[df["Contenido"] != "Total"]
    df = df[~df["Contenido"].astype(str).str.startswith("Mostrando")]
    return df[["Contenido", "Ingresos estimados (USD)"]].rename(
        columns={"Contenido": "video_id", "Ingresos estimados (USD)": "ingresos_real"})


def _fusionar(ruta_dataset: str, ruta_ingresos_cruda: str):
    dataset = pd.read_csv(ruta_dataset)
    ingresos = _limpiar_ingresos(ruta_ingresos_cruda)

    dataset = dataset.drop(columns=["ingresos_usd"], errors="ignore")
    dataset = dataset.merge(ingresos, on="video_id", how="left")
    dataset = dataset.rename(columns={"ingresos_real": "ingresos_usd"})
    dataset.to_csv(ruta_dataset, index=False)

    encontrados = dataset["ingresos_usd"].notna().sum()
    print(f"-> {ruta_dataset}: {encontrados}/{len(dataset)} videos con ingresos reales "
          f"(el resto no cayó en el top 500 por ingresos de YouTube Studio)")
    print(f"   Ingresos totales encontrados: US$ {dataset['ingresos_usd'].fillna(0).sum():,.2f}")


def main():
    _fusionar("data/youtube_agosto_organico.csv", "data/youtube_ingresos_agosto_raw.csv")
    _fusionar("data/youtube_lifetime_organico.csv", "data/youtube_ingresos_raw.csv")


if __name__ == "__main__":
    main()
