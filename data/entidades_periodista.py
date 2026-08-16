"""Extracción de entidades/temas por periodista desde los TÍTULOS reales
(julio + histórico ene-jun, ~2500 notas) — MIGRACION-DESDE-COLOMBIACOM.md §5.

Una ENTIDAD es una cosa única e identificable (persona/lugar/organización/
evento) que Google puede mapear a un perfil sin ambigüedad — se detecta por
nombres propios. Un TEMA es relevancia semántica/temática (ej. "números de la
suerte"), NO una entidad única — es una categoría distinta, igual de real. Se
distinguen con una columna "tipo" explícita en toda la salida (nunca mezclar
sin marcar, esa fue la causa del ruido que Colombia.com reportó).

Reglas ya conocidas por los bugs reales que costó encontrarlas en Colombia.com
(ver comentarios en el código en cada punto):
- nombre propio = ≥70% de sus apariciones en el CORPUS ENTERO (excluyendo la
  posición 0 de cada título) llevan mayúscula inicial.
- las rachas de nombre propio permiten VARIOS conectores seguidos en minúscula
  ("de la Espriella"), no solo uno.
- deduplicar por forma normalizada ANTES de agregar (si el extractor de temas
  redescubre en minúscula lo que el de entidades ya sacó bien, gana entidad).
- fusionar variantes solo si además de solapar como texto, sus notas (por
  ruta) se solapan ≥80% — si no, se generan fusiones fantasma.
- si un grupo fusionado mezcla candidatos entidad y tema, gana entidad.
- filtrar boilerplate: descartar lo que aparece en >50% de TODAS las notas de
  ese periodista (no es un tema, es una atribución de rutina).

Uso: python3 data/entidades_periodista.py
Lee data/mapa_autor_ruta.csv (título + autor + ruta, julio + histórico)
Escribe data/entidades_periodista.csv (autor, forma, tipo, notas, confianza,
    pct_del_periodista, rutas)
"""

import re
import unicodedata
from collections import defaultdict

import pandas as pd

CONECTORES = {"de", "del", "la", "los", "las", "y", "e", "a", "al", "en"}

# Días/meses SOLO para el filtro de temas (n-gramas en minúscula) — a
# propósito NO se incluyen en EXCLUIR_PROPIO: capitalizados, "Domingo"/"Enero"
# suelen ser parte de un nombre propio real (Santo Domingo, Enero como
# apellido) — bug real encontrado: bloquear "domingo" para ambos casos rompía
# la racha de "Santo Domingo" como entidad.
DIAS_MESES = {
    "lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado",
    "sabado", "domingo", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
}

# Verbos/palabras genéricas de titular Title Case ("Todo lo que Debes Saber")
# que a veces llevan mayúscula por estilo editorial, no por ser nombre propio
# — estas SÍ hay que bloquear en ambos casos (entidad y tema).
GENERICOS_TITULAR = {
    "gracias", "pueden", "puede", "podría", "podrían", "revelan", "revela",
    "rompe", "confirma", "confirman", "elegir", "muestra", "dice", "dicen",
    "hace", "hizo", "hará", "logra", "logran", "presenta", "anuncia", "lanza",
    "debes", "debe", "saber", "puedes", "hacer", "tener", "ser", "estar",
    "todo", "toda", "todos", "todas", "nuevo", "nueva", "mejor", "peor",
    "mayor", "menor", "gran", "grande", "cada", "otro", "otra", "otros", "otras",
    "esto", "eso", "esa", "ese", "esas", "esos", "aquello",
}

STOPWORDS_TEMA = CONECTORES | GENERICOS_TITULAR | DIAS_MESES | {
    "el", "un", "una", "unos", "unas", "que", "su", "sus", "lo", "se", "es", "son",
    "fue", "ha", "han", "hay", "no", "si", "sí", "más", "menos", "cómo", "qué",
    "cuál", "cuáles", "cuándo", "dónde", "por", "para", "con", "sin", "sobre",
    "tras", "ante", "bajo", "desde", "según", "hasta", "entre", "hacia", "este",
    "esta", "estos", "estas", "ese", "esa", "esos", "esas", "así", "también",
    "muy", "ya", "vs", "hoy", "aquí",
}

EXCLUIR_PROPIO = CONECTORES | GENERICOS_TITULAR

# Entidades boilerplate a NIVEL DE SITIO (no del periodista): revistamercado.do
# es un medio dominicano, así que "República Dominicana"/"RD" salen mencionadas
# en casi cualquier nota de casi cualquier autor — no distinguen tema ni beat,
# es la misma situación que "Colombia"/"Colombiacom" en el proyecto hermano.
EXCLUIR_ENTIDADES_SITIO = {"republica dominicana", "rd"}

MIN_RATIO_PROPIO = 0.70
MIN_NOTAS_FUSION_OVERLAP = 0.80
MIN_NOTAS_CANDIDATO = 2  # 1 sola nota no es un patrón, se descarta directo
MAX_PCT_BOILERPLATE = 0.50


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return s.lower().strip()


def tokenizar(titulo: str) -> list[str]:
    # conserva may/min original; separa por espacios y puntuación, quita signos sueltos
    crudo = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñÜü]+(?:['’][A-Za-zÁÉÍÓÚÑáéíóúñ]+)?", str(titulo))
    return crudo


def construir_estadisticas_propios(titulos: list[str]) -> dict[str, float]:
    total = defaultdict(int)
    mayuscula = defaultdict(int)
    for t in titulos:
        palabras = tokenizar(t)
        for i, w in enumerate(palabras):
            if i == 0:
                continue  # posición 0 siempre mayúscula por estilo editorial, no cuenta
            clave = w.lower()
            total[clave] += 1
            if w[:1].isupper():
                mayuscula[clave] += 1
    return {w: mayuscula[w] / total[w] for w in total if total[w] > 0}


def es_propio(palabra: str, stats: dict[str, float]) -> bool:
    clave = palabra.lower()
    if clave in EXCLUIR_PROPIO:
        return False
    ratio = stats.get(clave)
    return ratio is not None and ratio >= MIN_RATIO_PROPIO


def extraer_entidades_titulo(titulo: str, stats: dict[str, float]) -> list[str]:
    palabras = tokenizar(titulo)
    entidades, i, n = [], 0, len(palabras)
    while i < n:
        if not es_propio(palabras[i], stats):
            i += 1
            continue
        racha = [palabras[i]]
        j = i + 1
        while j < n:
            # escanea TODOS los conectores consecutivos, no solo uno
            k = j
            while k < n and palabras[k].lower() in CONECTORES:
                k += 1
            if k < n and k > j and es_propio(palabras[k], stats):
                racha.extend(palabras[j:k + 1])
                j = k + 1
                continue
            if k == j and es_propio(palabras[j], stats):  # sin conector de por medio
                racha.append(palabras[j])
                j += 1
                continue
            break
        if len(racha) >= 1:
            entidades.append(" ".join(racha))
        i = j if j > i + 1 else i + 1
    return entidades


def extraer_temas_titulo(titulo: str) -> list[str]:
    palabras = [w.lower() for w in tokenizar(titulo)]
    temas = []
    for n in (2, 3, 4):
        for i in range(len(palabras) - n + 1):
            gram = palabras[i:i + n]
            if gram[0] in STOPWORDS_TEMA or gram[-1] in STOPWORDS_TEMA:
                continue
            if any(len(w) <= 2 and w not in CONECTORES for w in gram):
                continue
            temas.append(" ".join(gram))
    return temas


def procesar_autor(df_autor: pd.DataFrame, stats_globales: dict[str, float]) -> pd.DataFrame:
    total_notas = len(df_autor)
    candidatos = []  # (forma_original, tipo, ruta)
    normalizadas_por_ruta = {}

    for _, row in df_autor.iterrows():
        titulo = row["titulo"]
        if pd.isna(titulo):
            continue
        ents = extraer_entidades_titulo(titulo, stats_globales)
        temas = extraer_temas_titulo(titulo)

        normas_ya_en_esta_nota = set()
        for e in ents:
            norma = normalizar(e)
            if norma in EXCLUIR_ENTIDADES_SITIO:
                # se filtra ANTES de agrupar/fusionar — si se dejara pasar y
                # se filtrara solo al final por el "raiz" del grupo fusionado,
                # una fusión con una frase más larga que la contiene (ej. un
                # tema de 4 palabras que incluye "república") cambia cuál es
                # el raiz final y el filtro exacto deja de aplicar.
                continue
            candidatos.append((e, "entidad", row["ruta"]))
            normas_ya_en_esta_nota.add(norma)
        for t in temas:
            norma = normalizar(t)
            if norma in EXCLUIR_ENTIDADES_SITIO:
                continue
            if norma in normas_ya_en_esta_nota:
                continue  # ya lo capturó el extractor de entidades en esta misma nota
            candidatos.append((t, "tema", row["ruta"]))
            normas_ya_en_esta_nota.add(norma)

    if not candidatos:
        return pd.DataFrame(columns=["forma", "tipo", "notas", "rutas"])

    grupos = defaultdict(lambda: {"formas": defaultdict(int), "tipo": defaultdict(int), "rutas": set()})
    for forma, tipo, ruta in candidatos:
        norma = normalizar(forma)
        g = grupos[norma]
        g["formas"][forma] += 1
        g["tipo"][tipo] += 1
        g["rutas"].add(ruta)

    claves = list(grupos.keys())
    padre = {k: k for k in claves}

    def find(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            padre[ra] = rb

    claves_ordenadas = sorted(claves, key=len)
    for idx, a in enumerate(claves_ordenadas):
        palabras_a = set(a.split())
        for b in claves_ordenadas[idx + 1:]:
            if a == b or len(a) >= len(b):
                continue
            palabras_b = b.split()
            if not all(pa in palabras_b for pa in palabras_a):
                continue  # a no es subcadena de PALABRAS completas de b
            rutas_a, rutas_b = grupos[a]["rutas"], grupos[b]["rutas"]
            solape = len(rutas_a & rutas_b) / max(1, min(len(rutas_a), len(rutas_b)))
            if solape >= MIN_NOTAS_FUSION_OVERLAP:
                union(a, b)

    fusionados = defaultdict(lambda: {"formas": defaultdict(int), "tipo": defaultdict(int), "rutas": set()})
    for k in claves:
        raiz = find(k)
        fusionados[raiz]["rutas"] |= grupos[k]["rutas"]
        for f, c in grupos[k]["formas"].items():
            fusionados[raiz]["formas"][f] += c
        for t, c in grupos[k]["tipo"].items():
            fusionados[raiz]["tipo"][t] += c

    filas = []
    for raiz, g in fusionados.items():
        if raiz in EXCLUIR_ENTIDADES_SITIO:
            continue
        n_notas = len(g["rutas"])
        if n_notas < MIN_NOTAS_CANDIDATO:
            continue
        if n_notas / total_notas > MAX_PCT_BOILERPLATE:
            continue
        tipo_final = "entidad" if g["tipo"].get("entidad", 0) > 0 else "tema"
        forma_final = max(g["formas"].items(), key=lambda kv: (kv[1], len(kv[0])))[0]
        filas.append({"forma": forma_final, "tipo": tipo_final, "notas": n_notas,
                      "pct_del_periodista": round(100 * n_notas / total_notas, 1),
                      "rutas": "|".join(sorted(g["rutas"]))})

    if not filas:
        return pd.DataFrame(columns=["forma", "tipo", "notas", "pct_del_periodista", "rutas"])
    return pd.DataFrame(filas).sort_values("notas", ascending=False)


def confianza(n_notas: int) -> str:
    if n_notas >= 10:
        return "🟢 alta"
    if n_notas >= 3:
        return "🟡 media"
    return "⚪ baja"


def main():
    mapa = pd.read_csv("data/mapa_autor_ruta.csv")
    mapa = mapa[~mapa["autor"].isin(["revistamercado", "SIN_AUTOR"])]

    stats = construir_estadisticas_propios(mapa["titulo"].dropna().tolist())
    print(f"Palabras con estadística de mayúscula calculada: {len(stats)}")

    resultados = []
    for autor, df_autor in mapa.groupby("autor"):
        r = procesar_autor(df_autor, stats)
        if r.empty:
            continue
        r.insert(0, "autor", autor)
        r["confianza"] = r["notas"].apply(confianza)
        resultados.append(r)

    salida = pd.concat(resultados, ignore_index=True)
    salida.to_csv("data/entidades_periodista.csv", index=False)
    print(f"{len(salida)} entidades/temas -> data/entidades_periodista.csv")
    print(f"  de tipo entidad: {(salida['tipo']=='entidad').sum()}")
    print(f"  de tipo tema:    {(salida['tipo']=='tema').sum()}")


if __name__ == "__main__":
    main()
