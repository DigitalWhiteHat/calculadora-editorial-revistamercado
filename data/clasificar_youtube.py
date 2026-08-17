"""Clasifica los videos de un snapshot de YouTube Studio por tipo de contenido
(noticia breve, empresarios/liderazgo, deportes, documental, podcast, otros) y
marca si es formato corto (<=180s). Heurística por título/duración, no IA --
tiene algo de ruido puntual pero el patrón agregado es real (ver app/youtube.py).

Uso: python3 data/clasificar_youtube.py data/youtube_agosto_organico.csv
Sobrescribe el mismo CSV agregando las columnas "categoria" y "es_short".
"""

import re
import sys

import pandas as pd

PALABRAS_NOTICIA = (
    r"iran|irán|trump|eeuu|ee uu|estados unidos|venezuela|colombia|terremoto|sismic|sísmic|guerra|"
    r"medio oriente|ormuz|corea del norte|misiles|bombarde|pentágono|geopolític|calor global|clima|"
    r"ola de calor|ataque|tensión|conflicto|nicaragua|cuba|israel|comercio mundial|mar rojo"
)
# "mundial" a secas NO entra aquí -- captura demasiados falsos positivos fuera de
# deporte (ej. "comercio mundial"), por eso solo entidades/frases específicas.
PALABRAS_DEPORTE = (
    r"clásico mundial|copa del mundo|mundial de|mundial de fútbol|albiceleste|fifa|"
    r"juegos centroamericanos|medallero|messi|selección|fútbol|olímpic|beisbol|béisbol"
)
PALABRAS_EMPRESARIO = (
    r"entrevista|ceo|presidente|banesco|grupo ramos|meliá|marsh mclennan|copa holdings|escotet|"
    r"zonas francas|liderazgo|leadership|líder|business|sucesores|family values|vp |gerente|"
    r"fundador|director|empresari|conversations|conversatorio|summit"
)
PALABRAS_DOC = r"kathleen martínez|cleopatra|taposiris"
PALABRAS_PODCAST = r"mercado podcast|enrique rojas|isabel rojas"

# Orden de prioridad importa: noticia se evalúa ANTES que deporte para que
# frases como "comercio mundial"/"mar Rojo" no caigan en deporte por error.
# "Empresarios/Liderazgo" exige coincidencia de palabra clave -- se probó usar
# duración >=300s como respaldo y metía cualquier video largo (recetas, videos
# institucionales genéricos) en la categoría, diluyendo el hallazgo real.


def clasificar(titulo: str, duracion_seg: float) -> str:
    t = str(titulo).lower()
    if re.search(PALABRAS_DOC, t):
        return "Documental (Kathleen Martínez)"
    if re.search(PALABRAS_PODCAST, t):
        return "Mercado Podcast"
    if re.search(PALABRAS_NOTICIA, t) and duracion_seg < 200:
        return "Noticias breves (geopolítica/actualidad)"
    if re.search(PALABRAS_DEPORTE, t):
        return "Deportes"
    if re.search(PALABRAS_EMPRESARIO, t):
        return "Empresarios / Liderazgo"
    return "Otros / Institucional"


def main(ruta_csv: str):
    df = pd.read_csv(ruta_csv)
    df["categoria"] = df.apply(lambda r: clasificar(r["titulo"], r["duracion_seg"]), axis=1)
    df["es_short"] = df["duracion_seg"] <= 180
    df.to_csv(ruta_csv, index=False)
    print(df["categoria"].value_counts().to_string())
    print(f"\n-> {ruta_csv} ({len(df)} filas)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 data/clasificar_youtube.py <ruta_csv>")
        sys.exit(1)
    main(sys.argv[1])
