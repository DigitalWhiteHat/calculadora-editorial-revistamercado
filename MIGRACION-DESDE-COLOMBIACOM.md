# Prompt de migración: llevar esta calculadora al nivel de la de Colombia.com

Pega este documento completo como primer mensaje en una sesión de Claude Code **dentro de este
proyecto** (`calculadora-periodistas-revistamercado`). Describe todo lo que se construyó, aprendió
y corrigió en el proyecto hermano `calculadora-periodistas` (Colombia.com) a lo largo de varias
semanas de trabajo con Edwin. El objetivo es que esta calculadora de Revista Mercado quede al
mismo nivel: mismos conceptos, mismas reglas, mismos patrones de diseño, misma disciplina de
verificación — adaptados a los datos reales de Revista Mercado (autores, secciones, escala de
tráfico propias, que NO son las de Colombia.com).

No copies literalmente los nombres de periodistas, secciones ni los números de umbral de
Colombia.com — este documento te da el MÉTODO. Los valores concretos (lista de autores,
secciones, umbrales de dificultad) hay que recalcularlos con los datos reales de Revista Mercado.

---

## 0. Contexto del proyecto

Edwin Lozada es consultor SEO/analítica. Esta calculadora mide desempeño editorial por periodista
para un medio digital, cruzando GA4 + Google Search Console (Search/Discover/News) + scraping de
HTML real de cada nota. Ya existe una versión base en este proyecto con datos de julio 2026 (14
periodistas, semáforo SEO corriendo). Falta todo lo que se construyó DESPUÉS en el proyecto de
Colombia.com. Edwin va a cargar 6 meses adicionales de exports (mismo formato que ya usa este
proyecto: `ga4_<rango>.csv`, `gsc_search_<rango>.csv`, `gsc_discover_<rango>.csv`,
`gsc_news_<rango>.csv`) — con eso, todo lo de abajo debe poder construirse.

---

## 0b. Aislamiento de entornos y puertos (OBLIGATORIO)

En este computador conviven **dos proyectos Streamlit independientes** que pueden estar corriendo
al mismo tiempo. Esta separación es una regla dura, no una sugerencia, y aplica durante todo el
ciclo de trabajo en este documento: desarrollo, pruebas, auditorías, reinicios de Streamlit y
verificación visual en navegador.

- **Colombia.com** (`calculadora-periodistas`) — el proyecto de referencia metodológica de todo
  este documento (ver sección 0). Ya está desarrollado y corre en `http://localhost:8504/`. **El
  puerto 8504 está RESERVADO exclusivamente para Colombia.com.**
- **Revista Mercado** (`calculadora-periodistas-revistamercado`, este proyecto) — su puerto local
  por defecto es `http://localhost:8505/`.

**Reglas obligatorias:**
1. Nunca uses el puerto 8504 para Revista Mercado.
2. Nunca detengas, mates, reinicies, modifiques ni interfieras de ninguna forma con un proceso que
   esté usando el puerto 8504 — puede ser la calculadora de Colombia.com corriendo en ese momento.
3. Antes de levantar Revista Mercado, verifica si el 8505 está libre (ej. `lsof -i :8505`). Si
   está libre, úsalo. Si está ocupado, prueba el siguiente puerto disponible (8506, 8507, ...).
   **Nunca mates otro proceso solo para liberar un puerto.**
4. Nunca reutilices el 8504 para Revista Mercado, aunque en algún momento parezca estar libre.
5. Elegir un puerto distinto de 8505 (por estar ocupado) **no debe implicar ningún cambio en el
   proyecto de Colombia.com** — la elección de puerto es local a la sesión de Revista Mercado, por
   ejemplo: `streamlit run app/main.py --server.port 8505` (o el puerto siguiente que corresponda
   según la regla 3).

**Sobre las instrucciones de este documento:** en cualquier parte de este `.md` (incluida la
sección 9, "Disciplina de verificación") donde se diga "reinicia el servidor", "mata el proceso",
"levanta el servidor" o una instrucción equivalente, se refiere **EXCLUSIVAMENTE al proceso de
Streamlit de Revista Mercado** (puerto 8505 o el que se haya elegido siguiendo la regla 3). Nunca
es autorización para tocar el proceso de Colombia.com en el 8504, incluso si ese puerto aparece en
pantalla, en logs o en la lista de procesos mientras trabajas en este proyecto.

Colombia.com sigue siendo el proyecto de referencia metodológica de todo este documento (código,
patrones, reglas, bugs ya resueltos) — pero eso es solo sobre lo que se **replica**, no autoriza
tocar su proceso, su puerto ni sus archivos mientras se desarrolla Revista Mercado. Las dos
aplicaciones deben poder correr simultáneamente sin interferencia.

---

## 1. Inventario de módulos (arquitectura a replicar)

```
app/
├── main.py            # routing, sidebar, selector de periodo (mes actual + histórico)
├── datos_reales.py     # TODA la lógica de carga/transformación — el corazón del proyecto
├── general.py          # Dashboard: KPIs, cuadrante, tabla principal, tendencia del portal
├── individual.py        # Perfil por periodista — la vista más rica, ver sección 6
├── secciones.py         # Vista 360 del portal: tráfico por sección, simuladores
├── notas.py             # Buscador/listado de notas reales
├── alertas.py           # Alertas de estado actual + alertas de TENDENCIA (7 meses)
├── estilos.py           # CSS global + helpers de tarjetas de color (reutilizar, no reinventar)
├── avatares.py          # Foto real si existe en assets/fotos_periodistas/<slug>.(jpg|jpeg|png)
├── calculos.py          # Formateo de números, utilidades puras
└── exportar_pdf.py       # Export a PDF del informe

data/
├── procesar_exports.py               # GA4+GSC crudo -> tabla unificada del mes actual
├── scrape_semaforo.py                # scraping HTML real -> 23 señales SEO crudas
├── semaforo_scoring.py               # las 23 reglas del semáforo (ver sección 4)
├── desglose_seo_por_item.py          # pass/fail por ítem y por nota (no solo el % agregado)
├── aplicar_semaforo_completo.py      # aplica semaforo_scoring sobre TODO el censo del mes actual
├── trafico_mensual_por_periodista.py # el fix más importante — ver sección 2
├── enriquecer_periodistas_mes.py     # agrega posición Google / top10 al agregado mensual
├── semaforo_muestra_6meses.py        # semáforo SEO vía MUESTREO para meses históricos (ver 2)
├── reaplicar_regla_h1.py             # re-puntúa sin re-scrapear cuando cambia una regla
├── entidades_periodista.py           # extracción de temas/entidades — ver sección 5
└── eeat_periodista.py                # checklist EEAT — ver sección 4b
```

---

## 2. El concepto más importante: tráfico REAL por mes vs. tráfico atribuido al mes de publicación

Este fue el bug más serio que Edwin encontró y hay que evitarlo desde el principio.

**Mal:** sumar todo el tráfico histórico de una nota y atribuirlo al mes en que se PUBLICÓ.
**Bien:** el tráfico de una nota en marzo debe contarse en marzo, sin importar si se publicó en
enero. Eso significa leer el GA4/GSC de CADA mes con su columna de fecha/mes, sin colapsar antes
de unir con el autor.

Patrón correcto (`data/trafico_mensual_por_periodista.py` en Colombia.com):
1. Cargar el histórico de GA4/GSC **sin agregar entre meses** (una fila por ruta+mes).
2. Cargar un mapa `ruta -> autor` FIJO (independiente del mes — un artículo tiene un solo autor).
3. Unir por ruta, agrupar por (autor, mes) — ahí sí se suma vistas+clics.
4. "Notas publicadas" es un concepto DISTINTO: se basa en el mes en que se publicó, no se toca.

### Canonicalización de autor (el segundo bug serio)

El campo de autor crudo (byline scrapeado) tiene decenas/cientos de variantes: acentos distintos,
sufijos ("- Revista Mercado"), créditos de agencia, "Redacción", ex-empleados, etc. Sin
normalizar, terminas con 100+ "periodistas" en vez de los ~14 reales.

Patrón de canonicalización (reutilizable tal cual, es genérico):
```python
def _normalizar_nombre(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.lower().split())

def _resolver_autor(raw, CANONICOS, ALIAS_EXTRA={}):
    norm = _normalizar_nombre(raw)
    # match exacto, luego startswith con chequeo de límite de palabra
    # (evita que "Juan Pérez" haga match parcial de "Juan Pérez Gómez" a menos
    # que el resto después del canónico no sea alfabético — o sea, corte de palabra real)
    ...
```
Construye la lista `CANONICOS` a partir de lo que YA hay en este proyecto (los 14 periodistas
reales de julio) y agrega alias a mano según lo que vayas encontrando al auditar el crudo (igual
que se hizo para Colombia.com: se encontraron ~300 variantes para 11 periodistas reales).
**Verifica con `df['autor'].nunique()` después del fix — si el número no coincide con la nómina
real, sigue habiendo variantes sin capturar.**

### Tier 1 vs Tier 2 — la distinción que sostiene todo el proyecto

- **Tier 2 (mes completo actual, julio en este caso):** censo COMPLETO. Semáforo SEO de las 23
  reglas sobre el 100% de las notas, alertas, canibalización, EEAT sobre muestra de 15 notas.
- **Tier 1 (meses históricos):** tráfico/notas/eficiencia REAL y COMPLETO (no es aproximado —
  viene de GA4+GSC reales), pero el semáforo SEO ahí es una MUESTRA (Edwin autorizó explícitamente
  esto para no tener que scrapear miles de páginas históricas): hasta 12 notas por periodista por
  mes, vía `semaforo_muestra_6meses.py`. Esto se declara SIEMPRE en la UI con un `st.info()`, nunca
  se presenta como si fuera el censo completo.

Cada vista tiene un patrón "lite" para los meses históricos y un patrón "full" para el mes actual
— ver sección 7.

---

## 3. Dificultad de sección

```python
def _dificultad(trafico_seccion_mensual):
    if trafico_seccion_mensual > UMBRAL_FACIL:      return "Fácil", 0.8
    if trafico_seccion_mensual >= UMBRAL_MEDIA:      return "Media", 1.0
    return "Difícil", 1.3
```
En Colombia.com los umbrales fueron >500K Fácil / 20K-500K Media / <20K Difícil — **esos números
son específicos de la escala de tráfico de Colombia.com, NO los copies**. Para Revista Mercado hay
que recalcularlos mirando la distribución real de tráfico por sección (revisa
`secciones_trafico_real()` o equivalente y decide los cortes con base en los cuartiles/gaps
naturales de los datos reales, no a ciegas).

**El diagnóstico que más le importó a Edwin** (agrégalo al header del perfil individual, en una
tarjeta "Dificultad de la sección"):
- Eficiencia normalizada **saludable** → ✅ "Rendimiento acorde o mejor a lo esperado".
- Eficiencia baja (<70) en sección **Fácil** → ⚠️ "Revisar al periodista" — la sección no es la
  limitante.
- Eficiencia baja en sección **Difícil** → ℹ️ "Puede ser la sección" — el bajo tráfico se explica
  en parte por la dificultad, no solo por el periodista.
- Eficiencia baja en sección **Media** → 🟡 "Revisar caso a caso".

Esta misma lógica de dificultad se reutiliza en TRES lugares: (a) tarjeta de dificultad en el
header del perfil, (b) badge de dificultad junto a cada sección en "en qué secciones le rinde
escribir", (c) módulo general "Dificultad y canal por sección" en el Dashboard (ver sección 8).

---

## 4. Semáforo SEO — 23 ítems, 14 automatizables

Revisa si Revista Mercado ya tiene su propio documento de referencia tipo "Semáforo SEO Final"
(Colombia.com lo tenía). Si no existe, pregúntale a Edwin antes de inventar las reglas — así se
hizo en Colombia.com. La checklist final, tras corregir un error real que Edwin encontró:

**Automatizables (14), extraídos del HTML real de cada nota:**
1. **H1 editorial 70-170 caracteres** — ¡OJO CON ESTE! La primera versión exigía H1 ≤78
   caracteres, y Edwin la marcó como injusta: confundía el `<title>` SEO (que sí debe ser corto,
   ver ítem siguiente) con el **H1 editorial** (el titular que aparece en el contenido, que puede
   llevar gancho y ser más largo). La regla correcta es **70-170 caracteres**, no ≤78. No repitas
   ese error de diseño.
2. Title SEO 50-65 caracteres (este sí es el `<title>`, es el que Google recorta en SERP)
3. Meta descripción 150-170 caracteres
4. Meta descripción no repite el H1
5. Primer párrafo responde de inmediato (≥180 caracteres)
6. Estructura de H2 correcta (cantidad según extensión + no genéricos)
7. Listas/tablas cuando el tema lo requiere (definir qué secciones lo requieren, ej. rankings,
   comparativas — en Colombia.com fue fútbol/loterías/elecciones/cine)
8. Extensión mínima 400 palabras
9. Tags 1-5
10. Mínimo 2 enlaces internos
11. Primer enlace interno en los primeros 3 párrafos
12. Texto ancla descriptivo (2-8 palabras, no genérico tipo "aquí"/"clic aquí")
13. Imagen principal ≥1200px de ancho
14. Alt de imagen no vacío, no genérico, ≤120 caracteres

**No automatizables (8), requieren juicio editorial** — se marcan explícitamente como "revisión
editorial" en vez de forzar un puntaje falso: keyword en el title, keyword en el primer párrafo,
número de keywords, ocurrencias de keyword, intención de búsqueda resuelta, calidad vs.
competencia, verificación de la fuente citada, destino del enlace interno vigente/relacionado.

Semáforo: 🟢 ≥80% · 🟡 60-79% · 🔴 <60%.

Guarda SIEMPRE las señales crudas del HTML (h1, title_tag, meta_desc, num_enlaces_internos, etc.)
en un CSV separado del puntaje calculado — así, si una regla cambia (como pasó con el H1), se
puede re-puntuar sin volver a scrapear (`reaplicar_regla_h1.py` es el patrón: lee el crudo ya
guardado, vuelve a aplicar `evaluar_nota()`, listo en segundos).

## 4b. EEAT — ítem complementario (Experience, Expertise, Authoritativeness, Trust)

Edwin pidió esto como checklist adicional al semáforo SEO, basado en la mejor práctica real de
Google para medios de noticias (investigar si hace falta, no inventar sin fundamento). Lo que
funcionó en Colombia.com, verificado contra el HTML real del sitio antes de programarlo a ciegas:

**Automatizable por nota (scraping ligero, muestra de ~15 notas/periodista):**
- `datePublished`/`dateModified` del JSON-LD `NewsArticle` → **actualización real** (modified >
  published, no solo idénticos)
- Enlaces salientes a dominios externos reales (no redes sociales/WhatsApp/Google News) →
  **cita fuentes externas**
- Frases de atribución ("según", "informó", "confirmó", "señaló"...) cerca de una afirmación →
  **atribución explícita**

**Automatizable por autor (una sola revisión, no por nota):**
- El JSON-LD `NewsArticle.author` trae `url` (perfil del autor) y `sameAs` (red social real,
  LinkedIn/X) → **perfil verificable**
- La página de perfil del autor tiene una bio real (buscar el texto en el HTML, NO en el meta
  description — el meta description casi siempre es un boilerplate genérico tipo "Noticias y
  artículos de X en [medio]" que NUNCA cambia) → **bio verificable**

- El JSON-LD `NewsArticle.author` trae `"@type":"Person"` (no "Organization" ni ausente) →
  **schema de autor tipo Person** — identidad formalmente reconocible por Google
- % del tráfico del periodista concentrado en su sección más fuerte (ver
  `especializacion_periodista_seccion.csv`, tomar el máximo de `pct_trafico_periodista` por autor)
  → **consistencia temática** (Expertise: publicar dentro de un cluster temático definido, no
  disperso en todo, es señal real según las Search Quality Rater Guidelines)

**A nivel de sitio (contexto, no se puntúa por periodista):** ¿tiene el sitio schema
`NewsMediaOrganization`? ¿Hay una página pública de política editorial/correcciones? ¿HTTPS?
(Colombia.com sí tenía NewsMediaOrganization + HTTPS, pero NO tenía política de
correcciones/editorial visible en el footer — es un hallazgo legítimo, no un fallo del scraper).

**No automatizable con este pipeline (requiere juicio editorial o herramienta paga):** precisión
factual verificable, evidencia de reporteo de primera mano (fotos/video originales vs. agregación
de agencia), diversidad y calidad de fuentes citadas (no solo que exista un enlace, sino si son
varias fuentes independientes), objetividad/balance editorial, **backlinks y menciones en medios
externos** (requiere Ahrefs/Moz/Semrush — este pipeline no lo tiene), transparencia de conflictos
de interés o contenido patrocinado marcado.

**Esta lista NO es exhaustiva.** Edwin explícitamente pidió investigar más a fondo qué otros
criterios de EEAT existen para medios de noticias específicamente (Search Quality Rater
Guidelines de Google + checklist de inclusión en Google News) antes de darla por cerrada — antes
de implementar, busca la versión más reciente de esos documentos y evalúa si hay más señales
automatizables desde el HTML/schema que no están en esta lista (ej. AI-disclosure, sitemap de
noticias, timestamps no escalonados, RSS).

**Antes de programar esto a ciegas:** baja el HTML de 2-3 notas reales de Revista Mercado y mira
el JSON-LD real (`<script type="application/ld+json">`) y el HTML de la página de autor — la
estructura exacta (nombres de clases CSS, si trae `sameAs`, dónde vive la bio) puede ser distinta
a la de Colombia.com. No asumas la misma estructura sin verificarla primero.

---

## 5. Extracción de temas/entidades por periodista ("en qué temas le rinde y en cuáles no")

Edwin pidió esto explícitamente: no solo la sección (ej. "Actualidad"), sino los temas/entidades
concretas (ej. "Petro", "Mhoni Vidente", "números de la suerte"). Se construye desde los TÍTULOS
reales de las notas (7 meses), con un extractor heurístico (no hay NER real, es regex + estadística
de corpus) — la calidad depende de varios ajustes finos que costó encontrar.

**Qué es una ENTIDAD en SEO de verdad (Edwin pidió investigar esto explícitamente porque sentía
que el resultado tenía ruido, y tenía razón):** una entidad es una cosa única e identificable
—persona, lugar, organización, producto, evento— que Google puede mapear a un solo perfil sin
ambigüedad en su Knowledge Graph, vía Named Entity Recognition + "entity salience" (qué tan
central es esa entidad en el contenido). Un TEMA (ej. "números de la suerte") es relevancia
semántica/temática, NO una entidad única identificable — es una categoría distinta, igual de real
y útil, pero no lo mismo. **Por eso cada fila debe llevar una columna "tipo": "entidad" o "tema"**,
y la interfaz debe distinguirlas visualmente (ej. 🏷️ entidad vs. 📌 tema) — mostrarlas sin
distinguir fue exactamente la causa del ruido que Edwin reportó.

**Extractor 1 — nombres propios = "entidad" (personas, equipos, lugares, organizaciones):**
No uses "¿esta palabra está en mayúscula AQUÍ?" — eso falla porque los titulares reinician
mayúscula después de dos puntos/guion, y arrastra basura como "Qué"/"No"/"Fe" sueltos. En su lugar,
construye un clasificador de corpus: para cada palabra (excluyendo la posición 0 de cada titular,
que siempre es mayúscula por estilo editorial y no por ser nombre propio), calcula qué % de sus
apariciones en el CORPUS ENTERO son con mayúscula inicial. Si ≥70% → esa palabra "es" nombre
propio en este medio. Con eso, arma rachas de palabras consecutivas reconocidas como propias.

Al armar la racha, **permite VARIOS conectores seguidos en minúscula** ("de la", "de los"), no
solo uno — bug real encontrado: con la lógica de "un solo conector", el título "Abelardo de la
Espriella" se cortaba en solo "Abelardo" porque tras consumir "de" la siguiente palabra ("la")
tampoco era nombre propio, y el código no seguía buscando más allá. Hay que escanear hacia
adelante TODOS los conectores consecutivos y solo entonces revisar si lo que sigue es nombre
propio.

**Extractor 2 — temas recurrentes = "tema" (n-gramas de 2-4 palabras en minúscula):**
Filtra agresivamente con una lista de stopwords que incluya: conectores, preposiciones (a, ante,
bajo, desde, según, sobre, tras...), días de la semana, meses, y verbos genéricos de titular
clickbait ("gracias", "pueden", "revelan", "rompe", "confirma", "elegir"...). Sin esto, salen
frases basura tipo "jueves de junio" o "gracias a" mezcladas con temas reales. Descarta el
n-grama si la primera O la última palabra es stopword.

**Deduplicar por forma NORMALIZADA, no por texto exacto, antes de agregar:** el extractor de temas
puede "redescubrir" en minúscula la misma frase que el extractor de nombres propios ya capturó
correctamente (ej. "gustavo petro" cuando el título ya dio "Gustavo Petro") — si no filtras esto
por texto normalizado (sin acentos, minúsculas) en el momento de generar candidatos por título,
la versión en minúscula compite por ser el texto final mostrado y a veces gana, mostrando la
entidad con la capitalización incorrecta de forma inconsistente entre corridas.

**Fusión de variantes (ej. "Petro" y "Gustavo Petro" son la misma entidad):**
Solo fusiona dos formas si (a) una es subcadena de palabra completa de la otra Y (b) sus conjuntos
de notas (por ruta) se solapan ≥80%. El paso (b) es crítico — fusionar solo por coincidencia de
texto (sin verificar solape real de notas) produce fusiones fantasma entre entidades sin ninguna
relación real (bug encontrado y corregido: dos personas totalmente distintas terminaron fusionadas
por una palabra puente casual).

**Si un grupo fusionado mezcla candidatos "entidad" y "tema", que gane "entidad":** no uses voto
mayoritario para decidir el tipo final del grupo. Si el extractor de nombres propios reconoció la
frase como entidad aunque sea en una sola nota, ES una entidad real — que otras variantes del
mismo título no hayan completado la racha (puntuación distinta, orden distinto) no cambia qué es
la cosa.

**Filtro de boilerplate:** descarta cualquier "entidad"/"tema" que aparezca en más de la mitad de
TODAS las notas de ese periodista — eso no es un tema, es una atribución de rutina (ej. una fuente
oficial citada en casi todo reporte de cierto beat).

**Temas débiles ("no le rinde"):** mismo extractor, pero ordenado ascendente por tráfico/nota,
excluyendo confianza "baja" (2 notas es una sola coincidencia, no un patrón).

Confianza: 🟢 alta (≥10 notas) · 🟡 media (3-9) · ⚪ baja (2, solo se muestra en "le rinde").

Después de programarlo, **inspecciona manualmente el top 6-8 de cada periodista, tanto "entidad"
como "tema" por separado** antes de darlo por bueno — así se encontraron y corrigieron varias
rondas de bugs de ruido reales en Colombia.com (no es opcional, la primera versión SIEMPRE tuvo
problemas que solo se ven mirando los datos reales, no leyendo el código).

---

## 6. Perfil individual — todo lo que debe tener

- Header: foto (círculo, usar `ImageOps.fit(img, (size,size), centering=(0.5,0.22))` — centrado
  hacia arriba para no cortar caras), nombre, beat, **ranking del mes dentro de la misma tarjeta**
  ("🏆 #5 de 11 este mes" — como badge de color aparte, NO como texto perdido dentro de otra
  línea; Edwin lo pidió dos veces hasta que quedó como elemento visual propio).
- Tarjeta de tráfico del período, con delta real vs. mes anterior (no "sin dato previo" si ya hay
  historial).
- Tarjeta de estado actual (SOBRE MEDIANA / EN RANGO / EN ALERTA).
- Tarjeta de dificultad de sección (ver sección 3).
- Gráfica "Tráfico por mes" — SIEMPRE los 7 meses completos, sin importar qué mes esté
  seleccionado en el dropdown de arriba (es la única pieza que Edwin pidió que NO cambie con el
  selector). Incluye selector "Comparar con" para superponer la línea de otro periodista.
- Gráfica de eficiencia normalizada en el tiempo.
- Métricas clave del período/mes.
- Posición promedio en Google en el tiempo.
- "En qué secciones le rinde escribir" — TODAS las secciones (no cortar a un top 5), con badge de
  dificultad junto a cada una.
- "Temas en los que le rinde (y en los que no)" — ver sección 5, dos bloques de chips.
- Autoridad en Google (Top10 + posición) — tarjetas de color, no texto plano.
- Checklist EEAT (ver 4b).
- Cumplimiento SEO + desglose "¿en qué está fallando?" con instrucciones concretas por ítem.
- Notas más vistas del período.

### El fix más importante de esta vista: que responda al selector de periodo

La primera versión dejaba el perfil completo congelado en el mes actual sin importar qué mes
eligiera Edwin en el dropdown — excepto la gráfica "Tráfico por mes", que sí debe quedarse fija
(ver arriba). Patrón: `render(..., periodo=None)` con branch `if periodo == PERIODO_COMPLETO:` (la
vista rica de Tier 2) / `else:` (una vista "ligera" Tier 1, con un `st.info()` aclarando qué es
real-completo ese mes vs. qué sigue siendo solo-mes-actual). Aplica esto a CADA vista del proyecto
(Dashboard, Secciones, Notas, Alertas, perfil individual) — no solo al perfil.

---

## 6b. Exportar PDF — debe tener TODA la información, no un resumen

Motivo de negocio (no es un capricho de diseño): la app corre local, Edwin no la puede compartir
todavía con nadie. El PDF es la única forma de que otras personas entiendan de qué está hablando
cuando comparte un análisis — por eso tiene que traer **exactamente la misma información que la
vista web del perfil, con el mismo criterio visual**, no un resumen recortado. La primera versión
del PDF en Colombia.com solo traía un cuarto del contenido real (una tabla de resumen y una lista
de notas) y hubo que reconstruirla completa. Al migrar, construye el PDF completo desde el
principio, no como una idea de último momento.

**Contenido mínimo que debe traer** (mismo orden que el perfil web, ver sección 6): header con
foto/ranking, tarjetas de resumen con color, LOS TRES GRÁFICOS históricos (tráfico por mes,
eficiencia normalizada, posición en Google), tabla de secciones con dificultad, temas
fuertes/débiles (con la distinción entidad/tema, ver sección 5), checklist EEAT completo,
desglose SEO con gráfico + instrucciones concretas de qué mejorar, alertas activas, alertas de
tendencia, notas más vistas (12-15, no solo 10).

**Cómo embeber los gráficos reales (no solo tablas):** instala `kaleido` (`pip install kaleido`)
para exportar las figuras de Plotly a PNG y embeberlas con `fpdf.image()`:
```python
img_bytes = fig.to_image(format="png", width=900, height=380, scale=2)
pdf.image(io.BytesIO(img_bytes), x=15, w=180)  # ancho útil en A4 con márgenes de 15mm
```
Reutiliza la MISMA lógica de construcción de cada figura que ya usa el perfil web (colores, ejes),
no inventes una versión distinta para el PDF.

**Dos bugs de codificación que vas a encontrarte seguro (fpdf2 con fuente "helvetica" estándar
solo soporta latin-1, no Unicode completo):**
1. Los emoji (🏷️ 📌 ✅ ⚠️ etc.) se ven como "??" en el PDF. No los uses ahí — reemplázalos por
   etiquetas de texto ASCII-seguras como `[Entidad]`/`[Tema]`/`[OK]`/`[!]` en la versión PDF
   específicamente (la web sí puede seguir usando los emoji reales).
2. El guion largo "—" (y comillas tipográficas '' "" …) tampoco están en latin-1 y se convierten
   en "?" sueltos en medio del texto. Reemplázalos por sus equivalentes ASCII (`-`, `'`, `"`,
   `...`) ANTES de codificar a latin-1, no después — construye una función `_ascii(txt)` que haga
   ese reemplazo primero y solo al final haga
   `texto.encode("latin-1", "replace").decode("latin-1")`.

**Rendimiento — cachear, y no bloquear el render de la página:** con 3-4 gráficos vía kaleido, un
PDF completo tarda ~10 segundos en generarse. Si el código que arma el PDF se ejecuta sin más en
cada rerun del script (Streamlit reejecuta el script completo en cada interacción), CADA clic en
la app —no solo pulsar "Exportar"— se siente congelado 10 segundos. Dos fixes obligatorios:
1. Envuelve la función que arma el PDF en `@st.cache_data`, cacheada por el slug del periodista
   (no por el DataFrame completo) — así solo se recalcula si cambia el periodista o los datos
   subyacentes, no en cada clic sobre el mismo perfil.
2. Usa un placeholder (`st.empty()`) para el botón de descarga, colocado donde va visualmente
   (arriba), pero RELLENADO al final del script — después de que ya se renderizó todo el
   contenido principal de la página. Así el perfil aparece de inmediato y el botón de PDF llega
   un instante después, en vez de bloquear toda la pantalla.

---

## 7. Patrón "lite vs. full" por vista

Cada módulo (`general.py`, `secciones.py`, `notas.py`, `alertas.py`, `individual.py`) sigue el
mismo esqueleto:
```python
def render(datos, periodo=None):
    periodo = periodo or PERIODO_COMPLETO
    if periodo != PERIODO_COMPLETO:
        _render_mes_ligero(periodo)   # Tier 1: dato real de ese mes, sin lo que es solo-Tier2
        return
    # cuerpo completo existente (Tier 2, censo del mes actual)
```
Las herramientas de DECISIÓN (simulador de notas necesarias, especialización periodista×sección,
simulador de "qué pasa si muevo a alguien de sección", propuesta de redistribución) usan SIEMPRE
el agregado de 7 meses, independientemente del selector de periodo — no tiene sentido que cambien
con el dropdown, son herramientas de planeación, no una foto de un mes.

---

## 8. Módulos nuevos a nivel de Dashboard (no del perfil)

- **"Dificultad y canal por sección"** — listado de TODAS las secciones con: badge de dificultad
  (mismo criterio de la sección 3) + canal dominante (Search/Discover/News, con % de sus clics) +
  tráfico total. Va en el **Dashboard/panel principal**, visible sin importar el mes seleccionado
  (es dato agregado, no depende del periodo). Usa tarjetas de color (`seccion_dificultad_row()` en
  Colombia.com, en `estilos.py`) — nunca texto plano con `:color-background[...]` suelto, se ve
  pobre.
- **Alertas de tendencia (7 meses)** — ahora que hay varios meses de historial, sí se puede medir
  tendencia real (antes estaba bloqueada por falta de datos). Regla usada en Colombia.com: racha
  de meses SEGUIDOS (terminando en el más reciente con dato) con índice de eficiencia <80 →
  3-4 meses = 🟡 ATENCIÓN, 5+ meses = 🔴 CRÍTICO. Van en su propia tarjeta, SIEMPRE visibles (no
  dependen del mes seleccionado), separadas de las alertas de estado-actual (que sí son solo del
  mes actual/Tier2). **Cuidado con las `key=` de Streamlit**: si el mismo periodista puede
  aparecer en la lista de alertas de estado actual Y en la de tendencia, dales prefijos de key
  distintos (`alerta_<slug>` vs `alerta_tendencia_<slug>`) — con la misma key duplicada Streamlit
  tira `StreamlitDuplicateElementKey` (bug real que apareció en Colombia.com, lo detectó la
  auditoría automatizada, ver sección 9).

---

## 9. Disciplina de verificación (no te la saltes)

Cada cambio no trivial se verificó con DOS pasos antes de reportarlo como terminado:

**1. Auditoría headless con `streamlit.testing.v1.AppTest`** — recorre TODAS las combinaciones de
periodista × mes (y de vista × mes para las demás pestañas) sin necesidad de navegador, revienta
rápido cualquier `KeyError`/excepción no manejada:
```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app/main.py", default_timeout=60)
at.session_state["vista"] = "individual"
at.session_state["periodista_slug"] = slug
at.session_state["periodo"] = periodo
at.run()
if at.exception: ...  # reporta
```
Esto encontró bugs reales (`StreamlitDuplicateElementKey`, columnas faltantes tras un rebuild) que
hubieran sido tediosos de encontrar clickeando manualmente cada combinación.

**2. Verificación visual en navegador** — reinicia el server de Streamlit **de Revista Mercado
únicamente** (puerto 8505, o el siguiente disponible si aplicó la regla de la sección 0b — nunca
el proceso de Colombia.com en el 8504, ver sección 0b) — los cambios de código en módulos ya
importados NO se recargan solos entre reruns del mismo proceso, hay que matar y levantar el
proceso de Revista Mercado de nuevo — y confirma con capturas reales que el dato mostrado es el
esperado, no solo que no truena.

No reportes "listo" sin haber hecho ambos pasos.

---

## 10. Patrones de diseño (reutilizables de `estilos.py`)

- Tarjetas con `st.container(border=True, key="card_...")` + CSS que targetea
  `div[class*="st-key-card_"]` — nunca inventes contenedores sueltos sin esta convención, rompe la
  consistencia visual del resto del proyecto.
- `pill()`, `metrica_card()`, `trafico_card()`, `delta_html()`, `seccion_dificultad_row()` —
  helpers ya armados, reutilízalos en vez de escribir HTML inline cada vez.
- Colores semánticos consistentes: verde `#16A34A`/`#DCFCE7`, azul `#3457D5`/`#DBEAFE`, rojo
  `#DC2626`/`#FEE2E2` — se usan para lo mismo en todos lados (bien/neutral/mal), no mezcles
  significados.
- **`translate="no"` a nivel de página** (inyectado una vez en `inyectar_css()`): el navegador
  (Chrome) puede auto-traducir términos técnicos en inglés que deben quedarse así (Search,
  Discover, News son nombres de producto de Google, no se traducen). Sin este fix, Edwin vio
  "Descubrir"/"Búsqueda"/"Noticias" en pantalla y pensó que era un bug del código — inclúyelo desde
  el principio.
- Miles/decimales: usa siempre un formateador consistente tipo `calc.formatear_numero()` (K/M) —
  nunca muestres un `st.number_input` crudo sin un `st.caption()` de apoyo con el número
  formateado, porque los inputs nativos de Streamlit no muestran separador de miles mientras se
  escribe.
- Simuladores/calculadoras interactivas: envuelve cada input en su propia tarjeta con emoji +
  label, y los resultados en tarjetas de color (verde/rojo según si es bueno o malo), nunca en
  `st.metric()` plano — Edwin fue explícito con esto dos veces.

---

## 11. Cómo trabaja Edwin — patrones de feedback a respetar

- Prefiere que audites y reportes **números exactos verificados**, no que le des seguridad sin
  comprobar ("¿solucionaste esto?" es una pregunta real, no retórica — vuelve a verificar en vivo
  antes de responder que sí).
- Visualización comparativa: escala compartida entre elementos + orden por magnitud + semáforo de
  color — no auto-scale individual por tarjeta.
- Cuando pide algo metodológicamente nuevo (EEAT, umbral de dificultad, reglas del semáforo) y no
  da la fuente exacta, prefiere que investigues la mejor práctica real (documentada, no inventada)
  antes de programar — así se hizo con el checklist EEAT.
- Si hay ambigüedad real sobre alcance (ej. "temas" = ¿nivel sección o nivel entidad específica?),
  pregúntale con una opción recomendada en vez de asumir — pero si ya te dio ejemplos concretos
  úsalos como especificación (dio "millonarios, Petro, de la Espriella, números de la suerte,
  comida en Tunja" como ejemplos exactos de lo que esperaba de la extracción de temas).
- Le gusta ver los cambios in situ: verifica en navegador y muéstrale con capturas o descripción
  precisa de lo que ve, no solo "ya quedó".

---

## 12. Qué necesita cargar Edwin para que esto funcione

Mismo formato que ya usa este proyecto para julio, por cada uno de los 6 meses adicionales:
- `data/raw/ga4_<rango-mes>.csv`
- `data/raw/gsc_search_<rango-mes>.csv`
- `data/raw/gsc_discover_<rango-mes>.csv`
- `data/raw/gsc_news_<rango-mes>.csv`

Con eso, el pipeline (adaptado siguiendo las secciones 2-5 de este documento) debe poder:
1. Construir el tráfico mensual real por periodista (sección 2).
2. Construir el histórico de 7 meses para el perfil individual y el Dashboard.
3. Muestrear y scrapear el semáforo SEO de los 6 meses históricos (12 notas/periodista/mes, igual
   que Colombia.com — confirma con Edwin si quiere el mismo tamaño de muestra).
4. Construir la extracción de temas/entidades sobre los títulos de los 7 meses.
5. Habilitar las alertas de tendencia.

---

## 13. Orden de trabajo sugerido

1. Audita primero qué hay YA en este proyecto (`app/`, `data/`) contra este documento — no
   reconstruyas lo que ya funciona bien.
2. Pide/confirma con Edwin los 6 meses de exports si no están ya en `data/raw/`.
3. Construye el pipeline de tráfico mensual real + canonicalización de autor (sección 2) —
   TODO lo demás depende de esto.
4. Recalcula umbrales de dificultad de sección con los datos reales de Revista Mercado.
5. Aplica el patrón lite/full a cada vista (sección 7).
6. Semáforo SEO histórico vía muestreo (sección 4) — confirma con Edwin el tamaño de muestra y si
   ya existe un documento de referencia de reglas para Revista Mercado antes de asumir las mismas
   23 reglas de Colombia.com.
7. Extracción de temas/entidades (sección 5) — inspecciona manualmente antes de dar por bueno,
   revisando "entidad" y "tema" por separado.
8. EEAT (sección 4b) — verifica la estructura real del HTML de Revista Mercado antes de programar,
   e investiga si hay más criterios automatizables antes de darla por una lista cerrada.
9. Módulos de Dashboard nuevos (sección 8).
10. PDF completo (sección 6b) — no lo dejes para el final como un detalle menor, es la forma en
    que Edwin va a compartir esto mientras la app siga siendo local.
11. Verifica todo con auditoría headless + navegador (sección 9) antes de reportar terminado.
