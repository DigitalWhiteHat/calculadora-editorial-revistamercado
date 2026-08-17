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

# Términos que el detector de propios siempre agarra (mayúscula consistente
# por estilo editorial) pero que son COYUNTURALES -- ligados a un evento/fecha
# puntual, no una entidad estable que Google mapea a un perfil único (persona/
# lugar/organización). Pedido de Edwin, 16-ago-2026: "las entidades no pueden
# ser elementos coyunturales. Mundial es un elemento coyuntural, así que no
# puede ser una entidad" -- confirmado en los datos: "Mundial" salía como
# entidad de 7 de los 8 periodistas del portal (hasta 151 notas en un caso),
# la más dominante de todo el dataset, precisamente por ser un evento de
# actualidad y no un beat real de nadie. Se DEGRADA a tema en vez de
# descartarse del todo (a diferencia de EXCLUIR_ENTIDADES_SITIO, que sí es
# ruido puro sin señal): sigue siendo una pista real de en qué escribe el
# periodista, solo que no es una entidad en el sentido estricto de E-E-A-T.
DEGRADAR_A_TEMA_COYUNTURAL = {"mundial"}

# EVENTO CONCLUIDO -- pedido de Edwin, 17-ago-2026, viendo "clásico mundial"
# en "le rinde" de Elba con 39K de tráfico total: "como le pones a Elba
# clásico mundial si fue a inicio de año, ya no hay clásico mundial" -- el
# guard de arriba (DEGRADAR_A_TEMA_COYUNTURAL) solo degrada el TIPO
# (entidad->tema) por nombre exacto ("mundial"), no detecta que un evento
# YA TERMINÓ y no vale como señal de "beat" a seguir asignando. La palabra
# "mundial" tampoco cubre "Clásico Mundial de Béisbol" (evento DISTINTO).
#
# Señal real y verificada (no una lista de palabras, que nunca cubre todos
# los casos): "Clásico Mundial de Béisbol" tuvo 24 de sus 26 notas
# publicadas en una ventana de 10 días en marzo, y solo 1.6% de su tráfico
# TOTAL cayó en jul+ago -- comparado con "precio del dólar" (evergreen real,
# republicado con URL nueva cada día): 36% de sus notas se publicaron en
# jul+ago, aunque su tráfico reciente también se ve bajo en proporción
# (natural: un artículo de dólar de enero ya no genera clics, pero eso NO
# significa que el TEMA murió, solo que ESA nota puntual sí). La señal que
# sí distingue ambos casos es "¿siguen publicando notas NUEVAS sobre esto?"
# -- eso es lo que mide pct_notas_recientes, no el tráfico.
VENTANA_RECIENTE_DIAS = 60
UMBRAL_NOTAS_RECIENTES_EVENTO_CONCLUIDO = 0.15
MIN_NOTAS_PARA_EVALUAR_EVENTO_CONCLUIDO = 5

# Segunda señal, independiente del % -- pedido de Edwin, 17-ago-2026: en el
# perfil de Andrea (coyuntura pura) "elecciones en Perú" seguía sin marcarse
# concluida aunque la elección ya pasó ("es un hecho coyuntural que no se va
# a repetir"). Causa real, verificada con las fechas: el extractor parte el
# mismo evento en variantes de texto ("elecciones perú", "elecciones en
# perú", "quién ganó las elecciones", "keiko fujimori", "Perú Fujimori"...)
# que NO fusionan entre sí (su solape de RUTAS es <80%, cada una sale de
# titulares distintos) -- cada variante fragmentada cae por debajo del
# volumen mínimo o queda justo en el límite del umbral de %, aunque TODAS
# comparten el mismo último dato real: nadie escribió sobre esto en más de
# 50 días. El % es sensible a cuántas notas totales tiene el grupo (una
# fragmentación de 11 notas cruza el 15% con solo 2 notas recientes; una de
# 15 notas no); días-desde-la-última-nota no depende del tamaño del grupo,
# así que no le importa la fragmentación -- si nadie volvió a escribir sobre
# esto en más de 45 días, está concluido, sin importar cuántas notas tenga
# el grupo (el mínimo sigue siendo MIN_NOTAS_CANDIDATO=2, no 5: la fecha de
# la última nota es una señal válida aunque el grupo sea chico).
UMBRAL_DIAS_SIN_NOTA_NUEVA = 45

# Tercera señal -- pedido de Edwin, 17-ago-2026, viendo "Ganar la Copa del
# Mundo" seguir como "le rinde". Primer intento (fallido): un registro curado
# a mano con la fecha real del evento (el Mundial 2026 cerró 19-jul-2026, y
# se revisó -- correcto -- que las impresiones de UNA nota puntual ("quién
# ganará la copa del mundo", 613K en la ventana móvil) no sirven de señal
# porque el tráfico residual de un evento grande se queda alto semanas
# después). Edwin lo rechazó con razón: "hay forma de inferirlo... miras la
# entidad en Search Console en los últimos meses y miras altas y bajas". La
# curva mensual completa (no una sola ventana) SÍ distingue los dos casos:
# - "elecciones en perú" (Andrea): pico 1.45M impresiones en junio -> 3.7K en
#   agosto (0.3% del pico) -- sube de la nada y cae a pique, coyuntura pura.
# - "copa del mundo" (Elba) mezclaba notas del Mundial 2026 (concluido) CON
#   "cuándo empieza el próximo mundial 2030" (evergreen real, sigue subiendo)
#   -- por eso el registro curado de abajo por sí solo SE EQUIVOCABA con este
#   grupo (lo marcaba concluido aunque su impresiones seguían creciendo,
#   100% del pico en agosto). La curva mensual real evita ese falso positivo.
# Fuente: data/impresiones_mensuales_por_ruta.csv (construido por
# data/construir_impresiones_mensuales.py desde los exports de GA4/GSC que
# YA existen en el proyecto -- ene-jun de procesado_historico, jul de
# procesado_2026-07, agosto parcial de sc_consolidado).
UMBRAL_RATIO_DECLIVE_GENERAL = 0.15   # cualquier entidad: <15% del pico en el último mes = concluida
MIN_PICO_IMPRESIONES_EVALUABLE = 3000  # pico mínimo para que la señal sea confiable, no ruido de una entidad chica

# El registro curado de eventos mayores conocidos NO se descarta -- sigue
# sirviendo para casos donde la fragmentación de texto diluye la caída real
# (ej. "Mundial" a secas de Elba: 54% del pico en agosto, no cruza el umbral
# general de 15% porque el bucket mezcla el uso genérico "a nivel mundial"
# con el torneo real). Pero ya NO fuerza concluido solo por coincidir con la
# palabra -- ahora exige ADEMÁS que la curva de impresiones esté en declive
# real (umbral más laxo, 60%, no 15%: ya sabemos que es un evento puntual,
# solo hace falta confirmar que no está en una racha de crecimiento genuino
# como el caso de "próximo mundial 2030" de arriba).
UMBRAL_RATIO_DECLIVE_EVENTO_CONOCIDO = 0.60
EVENTOS_CONCLUIDOS_CONOCIDOS = {
    "mundial": "2026-07-19",           # Mundial 2026 (fútbol) -- final 19-jul-2026
    "copa del mundo": "2026-07-19",
    "copa del mundial": "2026-07-19",  # variante de extracción, mismo evento
    "mundial de futbol": "2026-07-19",
    "mundial de clubes": "2026-07-19",
}
GRACIA_POST_EVENTO_DIAS = 21  # cobertura real de cierre/resumen post-evento, no señal de que sigue vigente

MIN_RATIO_PROPIO = 0.70
MIN_NOTAS_FUSION_OVERLAP = 0.80
MIN_NOTAS_CANDIDATO = 2  # 1 sola nota no es un patrón, se descarta directo
MAX_PCT_BOILERPLATE = 0.50


def _fin_evento_conocido(raiz_normalizada: str) -> str | None:
    """Devuelve la fecha de fin (str) si `raiz_normalizada` coincide con un
    evento de EVENTOS_CONCLUIDOS_CONOCIDOS. Las entradas de UNA sola palabra
    ("mundial") exigen coincidencia EXACTA de toda la raíz -- si fuera por
    palabra suelta, "Banco Mundial"/"récord mundial"/"a nivel mundial"
    (usos genéricos del adjetivo, nada que ver con el torneo) también
    calificarían. Las entradas de VARIAS palabras ("copa del mundo") sí
    matchean por subconjunto de palabras, para atrapar variantes como
    "segunda copa del mundo" o "inglaterra copa del mundo"."""
    palabras_raiz = set(raiz_normalizada.split())
    mejor = None
    for evento, fecha_fin in EVENTOS_CONCLUIDOS_CONOCIDOS.items():
        palabras_evento = evento.split()
        if len(palabras_evento) == 1:
            coincide = raiz_normalizada == evento
        else:
            coincide = all(p in palabras_raiz for p in palabras_evento)
        if coincide and (mejor is None or len(palabras_evento) > len(mejor[1].split())):
            mejor = (fecha_fin, evento)
    return mejor[0] if mejor else None


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


def construir_mapa_fusion(grupos: dict) -> dict:
    """Extraído de procesar_autor() (16-ago-2026) para poder reutilizarlo también en
    construir_temas_recomendados.py, que necesita la MISMA fusión de variantes pero
    con su propia agregación por mes -- sin duplicar el algoritmo de unión (con su
    guard de coyunturales, ya corregido y probado). Recibe `grupos` (norma ->
    {"rutas": set(...), ...}, como ya lo arma procesar_autor) y devuelve
    {norma: raiz_fusionada} para TODAS las claves de `grupos`."""
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
        if a in DEGRADAR_A_TEMA_COYUNTURAL:
            # NO se deja fusionar hacia arriba: si "mundial" se fusionara con
            # una racha más larga y genuinamente propia que la contiene (ej.
            # "Clásico Mundial de Béisbol") y esa racha SÍ califica como
            # entidad, el voto por mayoría de tipo_final la reclasificaría de
            # vuelta a "entidad" -- justo lo que este término debía evitar.
            continue
        palabras_a = set(a.split())
        for b in claves_ordenadas[idx + 1:]:
            if a == b or len(a) >= len(b):
                continue
            palabras_b = b.split()
            if not all(pa in palabras_b for pa in palabras_a):
                continue  # a no es subcadena de PALABRAS completas de b
            rutas_a, rutas_b = grupos[a]["rutas"], grupos[b]["rutas"]
            # BUG real encontrado 2026-08-17 (Edwin, viendo "terremoto de
            # Venezuela" mezclado dentro de "clásico mundial" de Elba):
            # dividir por el MÍNIMO de los dos grupos es casi siempre 100%
            # cuando `a` es una sub-frase de `b` -- toda nota que menciona
            # "terremoto de Venezuela" también extrae "Venezuela" suelto, así
            # que "Venezuela" (hub genérico, 12 notas de temas distintos:
            # béisbol Y terremoto) fusionaba con CUALQUIER frase más larga
            # que la contuviera, sin importar que fueran temas no
            # relacionados. Jaccard (intersección / unión) exige que AMBOS
            # grupos se solapen casi por completo, no solo que uno sea
            # subconjunto del otro -- así "Venezuela" (12 notas de varios
            # temas) no fusiona con "terremoto de Venezuela" (5 notas, un
            # tema) aunque las 5 estén incluidas en las 12.
            solape = len(rutas_a & rutas_b) / max(1, len(rutas_a | rutas_b))
            if solape >= MIN_NOTAS_FUSION_OVERLAP:
                union(a, b)

    return {k: find(k) for k in claves}


def cargar_impresiones_mensuales() -> dict[str, dict[str, float]]:
    """{ruta: {mes: impresiones}} desde data/impresiones_mensuales_por_ruta.csv
    (data/construir_impresiones_mensuales.py). Vacío si el archivo no existe
    todavía -- la señal de tendencia simplemente no se evalúa, no rompe nada."""
    try:
        df = pd.read_csv("data/impresiones_mensuales_por_ruta.csv")
    except FileNotFoundError:
        return {}
    lookup: dict[str, dict[str, float]] = defaultdict(dict)
    for ruta, mes, impresiones in df[["ruta", "mes", "impresiones"]].itertuples(index=False):
        lookup[ruta][mes] = lookup[ruta].get(mes, 0.0) + impresiones
    return lookup


def _ratio_declive_impresiones(rutas, impresiones_por_ruta_mes: dict) -> float | None:
    """último_mes / pico de la serie mensual REAL de impresiones del grupo
    (suma de todas sus rutas por mes) -- None si no hay dato suficiente para
    confiar en la señal (pico por debajo de MIN_PICO_IMPRESIONES_EVALUABLE)."""
    if not impresiones_por_ruta_mes:
        return None
    por_mes: dict[str, float] = defaultdict(float)
    for ruta in rutas:
        for mes, imp in impresiones_por_ruta_mes.get(ruta, {}).items():
            por_mes[mes] += imp
    if not por_mes:
        return None
    pico = max(por_mes.values())
    if pico < MIN_PICO_IMPRESIONES_EVALUABLE:
        return None
    ultimo_mes = max(por_mes.keys())
    return por_mes[ultimo_mes] / pico


def procesar_autor(df_autor: pd.DataFrame, stats_globales: dict[str, float],
                    fecha_corte_reciente=None, impresiones_por_ruta_mes: dict | None = None) -> pd.DataFrame:
    total_notas = len(df_autor)
    candidatos = []  # (forma_original, tipo, ruta)
    normalizadas_por_ruta = {}
    fecha_por_ruta = pd.to_datetime(df_autor.set_index("ruta")["fecha"], errors="coerce", utc=True).dt.tz_localize(None)

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
            tipo_e = "tema" if norma in DEGRADAR_A_TEMA_COYUNTURAL else "entidad"
            candidatos.append((e, tipo_e, row["ruta"]))
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

    mapa_fusion = construir_mapa_fusion(grupos)
    fusionados = defaultdict(lambda: {"formas": defaultdict(int), "tipo": defaultdict(int), "rutas": set()})
    for k, g in grupos.items():
        raiz = mapa_fusion[k]
        fusionados[raiz]["rutas"] |= g["rutas"]
        for f, c in g["formas"].items():
            fusionados[raiz]["formas"][f] += c
        for t, c in g["tipo"].items():
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

        fechas_grupo = fecha_por_ruta.reindex(g["rutas"]).dropna()
        if len(fechas_grupo) and fecha_corte_reciente is not None:
            pct_recientes = (fechas_grupo >= fecha_corte_reciente).mean()
        else:
            pct_recientes = None
        concluido_por_volumen = bool(
            n_notas >= MIN_NOTAS_PARA_EVALUAR_EVENTO_CONCLUIDO
            and pct_recientes is not None
            and pct_recientes < UMBRAL_NOTAS_RECIENTES_EVENTO_CONCLUIDO
        )
        hoy = (fecha_corte_reciente + pd.Timedelta(days=VENTANA_RECIENTE_DIAS)
               if fecha_corte_reciente is not None else None)
        if len(fechas_grupo) and hoy is not None:
            dias_desde_ultima = (hoy - fechas_grupo.max()).days
        else:
            dias_desde_ultima = None
        concluido_por_silencio = bool(dias_desde_ultima is not None and dias_desde_ultima > UMBRAL_DIAS_SIN_NOTA_NUEVA)

        ratio_declive = _ratio_declive_impresiones(g["rutas"], impresiones_por_ruta_mes or {})
        concluido_por_tendencia = bool(ratio_declive is not None and ratio_declive < UMBRAL_RATIO_DECLIVE_GENERAL)

        fin_conocido = _fin_evento_conocido(raiz)
        vencio_gracia = bool(
            fin_conocido is not None and hoy is not None
            and hoy > pd.Timestamp(fin_conocido) + pd.Timedelta(days=GRACIA_POST_EVENTO_DIAS)
        )
        # El registro curado ya NO fuerza concluido solo por coincidir con la
        # palabra -- exige además que la curva de impresiones muestre declive
        # real (umbral más laxo que el general: ya sabemos que es un evento
        # puntual, solo falta confirmar que no es un caso como "próximo
        # mundial 2030" que sigue creciendo genuinamente).
        concluido_por_evento_conocido = bool(
            vencio_gracia and ratio_declive is not None and ratio_declive < UMBRAL_RATIO_DECLIVE_EVENTO_CONOCIDO
        )
        es_evento_concluido = (concluido_por_volumen or concluido_por_silencio
                                or concluido_por_tendencia or concluido_por_evento_conocido)

        filas.append({"forma": forma_final, "tipo": tipo_final, "notas": n_notas,
                      "pct_del_periodista": round(100 * n_notas / total_notas, 1),
                      "rutas": "|".join(sorted(g["rutas"])),
                      "es_evento_concluido": es_evento_concluido,
                      "ratio_declive_impresiones": round(ratio_declive, 3) if ratio_declive is not None else None})

    if not filas:
        return pd.DataFrame(columns=["forma", "tipo", "notas", "pct_del_periodista", "rutas",
                                      "es_evento_concluido", "ratio_declive_impresiones"])
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

    # Corte real (hoy - 60 días) para detectar entidades/temas de un evento ya
    # CONCLUIDO -- ver VENTANA_RECIENTE_DIAS arriba.
    fecha_corte_reciente = pd.Timestamp.now().normalize() - pd.Timedelta(days=VENTANA_RECIENTE_DIAS)

    impresiones_por_ruta_mes = cargar_impresiones_mensuales()
    print(f"Impresiones mensuales cargadas para {len(impresiones_por_ruta_mes)} rutas "
          f"(correr data/construir_impresiones_mensuales.py si está vacío/desactualizado)")

    resultados = []
    for autor, df_autor in mapa.groupby("autor"):
        r = procesar_autor(df_autor, stats, fecha_corte_reciente, impresiones_por_ruta_mes)
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
