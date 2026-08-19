# Runbook: corregir la detección de "entidad/tema concluido" en la calculadora de periodistas

Este runbook viene de un bug real encontrado y corregido en `calculadora-periodistas-revistamercado`
(17-ago-2026). Es muy probable que este mismo proyecto (colombia.com / Bloomberg Línea) tenga el
mismo problema, porque comparten el mismo patrón de "calculadora de periodistas" y probablemente el
mismo tipo de lógica de "en qué entidad/tema le rinde escribir a este periodista" o "temas
recomendados/temas del día".

## El problema real (verificado con capturas de Search Console)

Cualquier vista que decida si un periodista "debería seguir escribiendo" sobre una entidad/tema
(ej. "le rinde escribir sobre X", "temas recomendados", "temas del día") necesita saber si esa
entidad ya CONCLUYÓ como evento — si ya no genera tráfico nuevo, no debe seguir apareciendo como
recomendación para el mes en curso, aunque haya generado mucho tráfico hace 2-3 semanas.

Edwin lo describió así: *"Si tengo una entidad que me queda cero, no me sirve. Si tengo una entidad
que tuvo mucho tráfico antes y ya no tiene ni la cuarta parte de ese tráfico, no me sirve. Tienes que
mirar las impresiones, la evolución de las impresiones en los últimos 30 o 60 días."*

### Enfoques que NO funcionan (ya se probaron y fallaron)

1. **Lista curada a mano de eventos conocidos** (ej. `{"mundial": "2026-07-19", ...}`) — funciona
   solo para los eventos que ya conocías cuando escribiste el código. Un evento nuevo (o una variante
   de texto que no coincide con las palabras de la lista) se cuela igual que antes. Edwin lo rechazó
   explícitamente: *"hay forma de inferirlo... miras la entidad en Search Console en los últimos
   meses y miras altas y bajas."*

2. **Ratio mensual simple** (tráfico del último mes / pico histórico, con un bucket = un mes
   calendario o una ventana móvil) — funciona para eventos que concluyeron HACE VARIOS MESES, pero
   NO detecta un evento que arrancó Y se desplomó DENTRO del mismo bucket/mes en curso: el promedio
   del mes mezcla los días de pico con los días ya caídos, y el ratio sale ~1.0 (parece que sigue en
   su pico) aunque en la realidad ya esté muerto.

3. **Comparar el TOTAL de dos ventanas móviles consecutivas** (ej. snapshot de ayer vs. snapshot de
   hoy de un export con ventana rodante tipo "últimos 30-35 días") — tampoco alcanza: el total
   acumulado de una ventana rodante casi SIEMPRE sigue subiendo aunque el tema ya esté muerto, porque
   el día que sale de la ventana rara vez tiene cero tráfico (así que restar totales no aísla nada
   limpiamente).

### El enfoque que SÍ funciona (validado con datos reales)

**Requisito de datos**: un export diario a Drive con ventana móvil (Apps Script) que se guarde como
un archivo NUEVO cada día (no que sobrescriba el mismo archivo) — ej.
`sc_consolidado_<fecha_inicio>_<fecha_fin>.csv`, uno por día, cada uno con el rango de fechas real
(`periodo_inicio`, `periodo_fin`) y columnas `pagina`/`impresiones` (Search Console) por página.
Colombia.com y Bloomberg Línea YA tienen exportadores diarios de GA4+GSC a Drive (ver memoria
`colombiacom-exports-drive-automatizados` / `revistamercado-exportador-ga4-gsc`) — **primero
verificar si ese Apps Script guarda un archivo por día (con el rango en el nombre) o si sobrescribe
uno solo**; si sobrescribe uno solo, hay que cambiarlo para que no lo haga, o empezar a bajar y
conservar el archivo de cada día desde ahora (no hace falta reconstruir el pasado, la serie se
arma sola hacia adelante).

**La técnica**: en vez de mirar el TOTAL de cada snapshot, mirar el **aporte marginal diario** — la
diferencia entre snapshots consecutivos (`snapshot_de_hoy - snapshot_de_ayer`). Como el día que sale
de la ventana casi nunca es cero, esta diferencia se aproxima muy bien al tráfico real del día que
ENTRÓ a la ventana. Con esa serie de diferencias:

- Si son **todas positivas y decrecen de forma sostenida** (con algo de tolerancia a ruido, ej. no
  romper la racha si un punto sube hasta un 5% sobre el anterior) → el tema está en declive real, ya
  no genera tráfico nuevo al ritmo de antes.
- Si **oscilan entre positivo y negativo** (sube y baja sin una dirección clara) → es un tema
  evergreen/estable, sigue construyendo, NO se marca.

Umbral de decisión: `último_aporte_diario / primer_aporte_diario < 0.30` (Edwin lo describió como
"menos de la cuarta parte" — 0.30 deja algo de margen sobre el 0.25 literal). Piso mínimo en el
primer aporte diario para no evaluar la señal sobre ruido de un grupo chico (ajustar según el volumen
real de impresiones del proyecto — en revistamercado.do se usó 300 impresiones/día; en colombia.com o
Bloomberg Línea, con volúmenes más altos, probablemente haga falta un piso mayor). Mínimo 3-4
snapshots disponibles antes de evaluar la señal (con menos puntos no se puede distinguir monotonía
real de ruido).

**Verificado con datos reales de revistamercado.do (6 snapshots diarios, 09 al 14-ago-2026):**
- "Juegos Centroamericanos" (evento que ya había concluido, según capturas reales de Search Console
  de Edwin): aporte diario +3,923 → +2,175 → +1,639 → +1,223 → +962. Ratio 0.245 → declive real.
- "Precio del dólar" (evergreen confirmado por Edwin): aporte diario oscila entre -23,421 y +12,696,
  sin dirección sostenida → NO se marca, correcto.

### El gotcha de la fragmentación (no lo pases por alto)

El mismo evento real puede fragmentarse en VARIOS grupos de entidad/tema distintos si tu extractor
fusiona variantes de texto por solape de rutas (patrón común: exigir ≥80% de solape de URLs para
fusionar, para evitar fusiones falsas). Un fragmento chico (ej. 2-3 notas) de un evento grande puede
no cruzar los umbrales de volumen de las señales más viejas (mínimo de notas, % reciente, etc.) y
seguir apareciendo como "vigente" aunque el fragmento GRANDE del mismo evento ya se haya marcado
correctamente como concluido. La señal de tendencia reciente (arriba) hay que aplicarla A CADA
FRAGMENTO por separado, con su propio conjunto de rutas — no asumas que basta con arreglar el grupo
principal.

## Tarea

1. **Localizar TODAS las vistas/scripts del proyecto que deciden "esta entidad/tema sigue
   vigente/recomendada"** — no solo el perfil individual. En revistamercado.do había DOS pipelines
   independientes con este problema: el perfil del periodista ("le rinde escribir sobre X") Y un
   pipeline separado de "temas recomendados/temas del día" con su propia lógica duplicada. Buscar por
   nombres tipo `es_evento_concluido`, `es_coyuntural`, `es_recurrente`, `demanda_reciente`,
   `entidades_fuertes`, `temas_recomendados`, `temas_del_dia` en `app/*.py` y `data/*.py`.
2. **Para cada uno, confirmar si ya filtra por una señal de tendencia real** (ratio mensual, lista
   curada, etc.) o si no filtra nada. Si usa solo una lista curada de palabras/eventos, ESE es el
   síntoma del mismo bug.
3. **Implementar la señal de aporte-diario-marginal** descrita arriba, usando los snapshots diarios
   reales ya disponibles en Drive (bajarlos y conservarlos en el repo, un archivo por día, igual que
   se hizo aquí en `data/raw_historico/sc_consolidado_*.csv`).
4. **Combinar con lo que ya exista, no reemplazar a ciegas**: si ya hay una lista curada o un ratio
   mensual, dejarlos como señales ADICIONALES (con lógica OR: se excluye si CUALQUIERA dispara) en
   vez de borrarlos — mientras el historial de snapshots diarios todavía es corto, las señales viejas
   siguen aportando cobertura.
5. **Verificar con al menos 2 casos reales conocidos** antes de dar por cerrado: un caso que SÍ debe
   quedar marcado como concluido (con capturas de Search Console si es posible, como hizo Edwin) y un
   caso evergreen conocido (ej. "precio del dólar" o el equivalente del proyecto) que NO debe quedar
   marcado — si el evergreen se marca por error, el umbral o la tolerancia de ruido están mal
   calibrados para el volumen real de ese proyecto.
6. **Redesplegar y verificar en producción** (no solo localmente) antes de reportar terminado.

## Verificación

- [ ] Corriste el script de generación de entidades y confirmaste con números reales (no solo
      lectura de código) que el caso concluido conocido queda `True` y el evergreen conocido queda
      `False`.
- [ ] Revisaste TODAS las vistas que muestran entidades/temas como "recomendado"/"le rinde"/"tema del
      día", no solo la primera que encontraste.
- [ ] El fix está desplegado en producción y lo verificaste ahí (no solo en local).
