"""Diagnóstico SEO técnico de revistamercado.do -- auditoría real, 16-ago-2026.

Hallazgos verificados con fetch/crawling real contra el sitio en vivo (robots.txt,
sitemaps, headers HTTP, HTML de 5 artículos reales) más Core Web Vitals reales vía
PageSpeed Insights API (datos de campo/CrUX, no solo laboratorio) -- ver
data/medir_core_web_vitals.py para la medición de CWV y data/cwv_diagnostico.csv
para el resultado.

Adaptado de calculadora-periodistas/app/diagnostico_seo_hallazgos.py (colombia.com)
-- mismo esquema de datos, pero los hallazgos NO se asumieron repetidos: se
volvió a auditar todo desde cero contra revistamercado.do, y el resultado real es
bastante distinto (sitemap sano acá, cabeceras de seguridad peor, CWV parejo en
amarillo en vez de todo verde).

Esto es una auditoría puntual (no un pipeline recurrente): los hallazgos quedan
fijados a la fecha en que se corrió. Antes de confiar en algo de aquí para una
decisión nueva, vale la pena volver a correr la auditoría si ya pasó mucho tiempo.
"""

FECHA_AUDITORIA = "2026-08-16"

ESTADO_GENERAL = {
    "nivel": "amarillo",
    "resumen": (
        "Sin bloqueos de indexación confirmados -- el sitemap está sano (a diferencia de "
        "colombia.com, no hay corte sin continuación). El gap real es otro: cero cabeceras "
        "de seguridad recomendadas y Core Web Vitals reales parejos en \"necesita mejora\" "
        "en las 4 páginas medidas, ninguna en verde."
    ),
}

KPIS = [
    {"icono": "🗺️", "label": "Sub-sitemaps de notas (post-sitemap) sin continuación pese a tocar el techo de fila",
     "valor": "0 de 18", "help": "A diferencia de colombia.com: acá SÍ hay paginación automática de Yoast SEO (~1.000 URLs por archivo) y el archivo 18 (el más reciente) sigue con espacio (853 de 1.000) -- sin riesgo de contenido sin descubrir."},
    {"icono": "🚫", "label": "Artículos muestreados con noindex accidental", "valor": "0 de 5"},
    {"icono": "🔗", "label": "Artículos con canonical mal formado", "valor": "0 de 5"},
    {"icono": "🧩", "label": "Artículos con JSON-LD válido (NewsArticle)", "valor": "5 de 5"},
    {"icono": "🍞", "label": "Artículos con BreadcrumbList", "valor": "5 de 5"},
    {"icono": "📏", "label": "Titles muestreados dentro del límite recomendado (~60 car.)",
     "valor": "4 de 5", "help": "Rango real observado: 48-83 caracteres -- el único fuera de rango arrastra el sufijo \" - Revista Mercado\" en el title."},
    {"icono": "🛡️", "label": "Cabeceras de seguridad recomendadas presentes en home", "valor": "0 de 5",
     "help": "Ninguna de HSTS, X-Frame-Options, X-Content-Type-Options, CSP o Referrer-Policy está presente."},
    {"icono": "⚡", "label": "Páginas con Core Web Vitals en verde (datos de campo reales, mobile)",
     "valor": "0 de 4", "help": "Home, Actualidad, Money Invest, Lifestyle -- las 4 en \"Necesita mejora\" (AVERAGE), ninguna en \"Rápido\" ni en \"Lento\". Home está apenas 22ms sobre el umbral bueno de LCP (2.522ms vs. 2.500ms)."},
]

HALLAZGO_PRINCIPAL = (
    "El armado técnico base del sitio es sólido donde se pudo verificar: **el sitemap no tiene "
    "el problema que sí tiene colombia.com** -- Yoast SEO pagina el post-sitemap automáticamente "
    "cada ~1.000 URLs (18 archivos hoy, el más reciente con espacio de sobra), así que no hay "
    "riesgo de contenido nuevo sin ruta de descubrimiento. Los 5 artículos muestreados (empresas, "
    "actualidad, tecnología, money-invest, lifestyle) tienen canonical correcto, cero noindex "
    "accidental, JSON-LD NewsArticle válido y BreadcrumbList presente -- mejor cobertura que "
    "colombia.com, que tenía un hueco de BreadcrumbList en Loterías. El problema real, y sí "
    "confirmado, es otro: **cero de las 5 cabeceras de seguridad recomendadas está presente** en "
    "la home (HSTS, X-Frame-Options, X-Content-Type-Options, CSP, Referrer-Policy -- colombia.com "
    "tenía al menos 3 de 5). Y **Core Web Vitals reales (datos de campo, tráfico real de usuarios) "
    "están en \"Necesita mejora\" en las 4 páginas medidas, ninguna en verde** -- home está apenas "
    "22ms sobre el umbral bueno de LCP (2.522ms vs. 2.500ms), y las 3 secciones de contenido "
    "(Actualidad, Money Invest, Lifestyle) reportan exactamente el mismo LCP/CLS/INP de campo "
    "(2.919ms / 0.11 / 202ms) -- comparten la misma plantilla de WordPress y probablemente caen "
    "en el mismo bucket de CrUX, no es un error de medición. Hallazgo aparte, aislado (no "
    "sistemático -- se revisaron 2 notas de lotería más y ambas estaban bien): la nota "
    "\"Resultados de las loterías del 14 de julio\" tiene **\"2025\" en el title** pese a que la "
    "URL y el JSON-LD (fecha real de publicación) dicen 2026."
)

MATRIZ_ACCIONES = [
    {"accion": "Agregar cabeceras Strict-Transport-Security, X-Frame-Options y X-Content-Type-Options (impacto alto, riesgo bajo de romper algo)",
     "severidad": "Media", "esfuerzo": "Bajo", "area": "Global"},
    {"accion": "Agregar Content-Security-Policy y Referrer-Policy (probar que no rompa ads/analytics antes de publicar)",
     "severidad": "Media", "esfuerzo": "Medio", "area": "Global"},
    {"accion": "Investigar qué recurso empuja el LCP de Home a 2.522ms (22ms sobre el umbral bueno) -- candidato típico: imagen hero sin preload/sin formato moderno",
     "severidad": "Media", "esfuerzo": "Bajo-Medio", "area": "Home"},
    {"accion": "Investigar el LCP de laboratorio de Home (82,8s y 84,9s en dos mediciones independientes, con throttling simulado) -- confirmado que se repite, no es un artefacto puntual; muy por encima del dato de campo real (2,5s), señal de un recurso que solo se vuelve lento en conexión fría/simulada (ej. script de terceros o fuente web bloqueante que no afecta tanto a usuarios reales con caché tibia)",
     "severidad": "Media", "esfuerzo": "Bajo-Medio", "area": "Home"},
    {"accion": "Corregir el año en el title de \"Resultados de las loterías del 14 de julio\" (dice 2025, la nota es de 2026)",
     "severidad": "Baja", "esfuerzo": "Muy bajo", "area": "Actualidad / Loterías"},
    {"accion": "Acortar el title de \"Las 20 mejores películas de la historia...\" (83 caracteres, el sufijo \" - Revista Mercado\" lo saca del rango recomendado)",
     "severidad": "Baja", "esfuerzo": "Muy bajo", "area": "Lifestyle"},
]

URGENTES = [
    "Nada bloqueante confirmado (a diferencia de colombia.com, que sí tenía un riesgo real de "
    "indexación por el sitemap). El ítem más cercano a \"urgente\" es de esfuerzo casi nulo: "
    "**agregar las cabeceras de seguridad básicas** (HSTS, X-Frame-Options, X-Content-Type-Options) "
    "-- no hay ninguna hoy, y no depende de investigar nada más primero.",
]

COBERTURA_VERIFICADA = [
    "robots.txt (contenido completo)",
    "Índice de sitemaps (58 sub-sitemaps de todos los post types) + conteo real de URLs y "
    "continuación del sitemap principal de notas (post-sitemap, 18 archivos)",
    "Headers HTTP y cabeceras de seguridad de la home",
    "Redirect www → no-www (confirmado: 301, un solo salto, sin cadena)",
    "Meta tags, canonical, robots meta y JSON-LD en 5 artículos reales (empresas/deportes, "
    "actualidad/loterías, tecnología, money-invest, lifestyle)",
    "Muestra de URLs para 404s y rutas de utilidad (permalink antiguo, wp-admin, feed)",
    "Core Web Vitals reales (datos de campo/CrUX vía PageSpeed Insights) en 4 páginas, mobile",
]

COBERTURA_PENDIENTE = [
    "Conteo/paginación de los demás sub-sitemaps más allá del principal de notas (page, category, "
    "post_tag, rankings, who-is-who, etc.)",
    "Auditoría exhaustiva de 404s/redirects más allá de la muestra puntual",
    "Renderizado JS de plantillas de artículo (solo se confirmó fetch estático, no ejecución de JS)",
    "Por qué el LCP de laboratorio de Home difiere tanto del dato de campo -- no se investigó a fondo",
]
