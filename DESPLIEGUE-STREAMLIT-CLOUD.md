# Prompt de despliegue: subir esta calculadora a la web (privada, sin index)

Pega este documento completo como primer mensaje en una sesión de Claude Code **dentro de la
carpeta del proyecto que quieras desplegar** (ej. `calculadora-periodistas-revistamercado` o
`calculadora-periodistas-bloomberglinea`). Describe el objetivo: sacar la calculadora de
`localhost` y ponerla en una URL real, privada (solo Edwin puede verla, nadie más sin invitación
explícita) y con `noindex` para que Google nunca la indexe — exactamente lo que ya se hizo para
la calculadora de Colombia.com, ahora en `https://desempeno-editorial-colombiacom.streamlit.app/`.

**No ejecutes nada de esto sobre otro proyecto.** Cada calculadora (Colombia.com, Revista
Mercado, Bloomberg Línea) tiene su PROPIO repositorio de GitHub y su PROPIA app en Streamlit
Cloud — nunca reutilices ni toques el repo o el despliegue de otro proyecto al hacer esto.

---

## 0. Antes de empezar

- Confirma con Edwin el nombre del repositorio que se va a crear (sugerido:
  `calculadora-editorial-<medio>`, ej. `calculadora-editorial-revistamercado`).
- Revisa `requirements.txt` del proyecto: debe tener **todo** lo que la app necesita en
  producción, no solo lo que ya estaba. En Colombia.com faltaba `kaleido` (necesario para que
  `exportar_pdf.py` pueda convertir los gráficos de Plotly a imagen) — revisa si este proyecto
  también exporta gráficos a PDF y agrégalo si falta.
- Este proceso usa el navegador REAL de Edwin (`Claude in Chrome`, no el navegador aislado) — sus
  sesiones de GitHub/Streamlit ya están o van a quedar ahí. Si el navegador tiene MÁS de una
  cuenta de GitHub logueada (de otro trabajo, por ejemplo), nunca selecciones la que no sea la
  suya — confírmalo con Edwin si hay ambigüedad.

---

## 1. Preparar el repo localmente

**`.gitignore`** — créalo si no existe, con esto como mínimo:
```
.venv/
__pycache__/
*.pyc
.DS_Store
*.png
!assets/**/*.png
!assets/**/*.jpg
!assets/**/*.jpeg
```
El `.venv` puede pesar 100+ MB y nunca debe subirse (Streamlit Cloud instala las dependencias
solo desde `requirements.txt`). El patrón `*.png` + negaciones excluye capturas de pantalla
sueltas en la raíz del proyecto pero mantiene el logo y las fotos de periodistas que sí carga la
app en tiempo real.

**`noindex` en el código** — agrégalo en el mismo lugar donde ya se inyecta el CSS global
(`estilos.py` o el módulo equivalente), junto al script que ya existe para evitar que Chrome
traduzca "Search/Discover/News":
```python
SCRIPT_NOINDEX = """
<script>
(function() {
    if (!document.querySelector('meta[name="robots"]')) {
        const meta = document.createElement('meta');
        meta.name = 'robots';
        meta.content = 'noindex, nofollow';
        document.head.appendChild(meta);
    }
})();
</script>
"""

def inyectar_css():
    st.html(CSS_GLOBAL)
    st.html(SCRIPT_NO_TRANSLATE)
    # Datos por periodista con nombre propio -- nunca debe indexarse, sin importar el hosting.
    st.html(SCRIPT_NOINDEX)
```

**Inicializar git** (solo si el proyecto no es ya un repo):
```bash
git init
```

---

## 2. Crear el repositorio en GitHub (nuevo, privado, separado)

En el navegador real de Edwin, ve a `github.com`. Si no hay sesión iniciada, es su cuenta
(`DigitalWhiteHat` / `edwin@digitalwhitehat.com`) — no la de ningún trabajo anterior que pueda
aparecer en el selector de cuentas.

1. `github.com/new`.
2. Owner: su cuenta personal (`DigitalWhiteHat`), nunca una organización ajena.
3. Nombre: `calculadora-editorial-<medio>`.
4. **Visibilidad: Private** — obligatorio, estos proyectos tienen datos por periodista con
   nombre propio.
5. No agregues README/.gitignore/licencia desde la interfaz de GitHub (para no chocar con lo que
   ya vas a subir tú).
6. "Create repository".

---

## 3. Autenticar git sin tocar contraseñas

Nunca escribas ni pidas la contraseña de Edwin. El flujo correcto usa `gh` (GitHub CLI) con
código de un solo uso — nunca pide password:

```bash
which gh || brew install gh
gh auth login --hostname github.com --git-protocol https --web
```

Esto imprime algo como:
```
! First copy your one-time code: XXXX-XXXX
Open this URL to continue in your web browser: https://github.com/login/device
```

Abre esa URL en el navegador real de Edwin, escribe el código en los 8 casilleros, y en la
pantalla "Autoriza tu dispositivo" selecciona la cuenta correcta de Edwin (si aparece más de una
cuenta en el selector, como una de un trabajo anterior, **nunca la selecciones** — usa la de
Edwin).

**Gotcha real encontrado en producción:** el botón final ("Authorize github" / "Autorizar
streamlit" en los pasos siguientes) a veces **no responde a los clics automatizados** del
navegador — parece protección anti-bot de GitHub en pasos sensibles. Si después de un par de
intentos el botón sigue sin reaccionar (la página no cambia), pídele a Edwin que le dé clic él
mismo directamente y que te avise ("ya") cuando lo haga — no insistas más de 2-3 veces con clics
automatizados.

Una vez autenticado, revisa que fue exitoso:
```bash
gh auth status
```
Debe decir "Logged in to github.com account DigitalWhiteHat". Luego conecta ese login con git:
```bash
gh auth setup-git
```

---

## 4. Commit y push

```bash
cd "<carpeta del proyecto>"
git config user.name "Edwin Lozada"
git config user.email "edwin@digitalwhitehat.com"
git add -A
git status --short | wc -l     # revisa cuántos archivos entran — confirma que NO aparece .venv
git commit -m "Primera versión: calculadora de desempeño editorial <medio>"
git branch -M main
git remote add origin https://github.com/DigitalWhiteHat/calculadora-editorial-<medio>.git
git push -u origin main
```

Verifica en el navegador que el push llegó (`github.com/DigitalWhiteHat/calculadora-editorial-<medio>`,
badge "Private" visible, carpetas `app/`, `data/`, `assets/` presentes).

---

## 5. Desplegar en Streamlit Community Cloud

1. Navega a `share.streamlit.io`. Si pide "Continue to sign-in", es aceptar los Términos de
   Servicio de Streamlit — dile a Edwin qué botón es antes de darle clic (o pídele que lo haga él).
2. Si es la primera vez que se usa Streamlit Cloud desde esta cuenta, va a pedir "Connect to
   GitHub" — es otra autorización OAuth, mismo criterio que en el paso 3 (puede necesitar que
   Edwin le dé clic él mismo al botón final "Authorize streamlit").

### Gotcha real: el primer "Connect to GitHub" NO alcanza para repos privados

La primera conexión con GitHub solo pide el scope `public_repo` (repos públicos). Si intentas
llenar el formulario de despliegue con el nombre del repo privado, va a decir **"Este repositorio
no existe"** — no es un error real, es que Streamlit todavía no tiene permiso de ver repos
privados. Arreglo:

1. Click en el nombre del workspace (arriba a la izquierda) → **Ajustes**.
2. Pestaña **Cuentas vinculadas**.
3. Busca el bloque azul "**Acceso privado**: Streamlit no tiene acceso a los repositorios
   privados de esta cuenta de GitHub." → click en "**Conéctate aquí →**".
4. Esto abre de nuevo la pantalla de autorización de GitHub, esta vez pidiendo "Repositorios:
   Public and **private**" — autorízala (mismo cuidado del paso 3 si el botón no responde a
   clics automatizados).
5. Vuelve a `share.streamlit.io/deploy` — ahora, al escribir el nombre del repo, sí debe
   aparecer en el autocompletado.

### Llenar el formulario de despliegue

- **Repositorio**: `DigitalWhiteHat/calculadora-editorial-<medio>` (elígelo del autocompletado,
  no lo escribas a mano completo si el dropdown ya lo ofrece).
- **Rama**: `main` (el campo trae "master" por defecto — cámbialo).
- **Ruta del archivo principal**: `app/main.py` (o el entry point real del proyecto, verifícalo).
- **URL de la aplicación (opcional)**: pon algo legible, ej. `desempeno-editorial-<medio>` — si
  el campo trae un valor aleatorio pre-rellenado, selecciona todo el texto primero
  (`triple_click` o `cmd+a`) antes de escribir, para no dejar el texto viejo pegado al nuevo.
- Click "Desplegar" (mismo cuidado: si no responde a clics automatizados, que lo haga Edwin).

Espera 1-2 minutos a que compile. Verifica con una captura que carga bien y que los datos reales
se ven — no lo des por bueno solo porque no marcó error.

---

## 6. Confirmar que quedó privada (no pública)

1. Click en "**Compartir**" arriba a la derecha de la app ya desplegada.
2. Confirma que el toggle "**Haz pública esta aplicación**" está **apagado**. Por defecto, una
   app desplegada desde un repo privado YA nace así — no actives ese toggle.
3. Esto significa: nadie puede entrar, ni con el link, a menos que Edwin invite explícitamente un
   correo desde ese mismo panel ("Invitar"). No es una contraseña compartida — es una lista de
   acceso por correo, más segura pero requiere invitar a cada persona nueva individualmente.

---

## 7. Reportar a Edwin

Al terminar, dile:
1. La URL final (`https://<slug-elegido>.streamlit.app/`).
2. Que quedó privada (nadie tiene acceso salvo que él invite un correo puntual).
3. Que quedó con `noindex` (nunca la va a indexar Google, así la haga pública en el futuro).
4. Cómo actualizarla después: cualquier cambio de código o de datos que se suba con `git push` a
   `main` hace que Streamlit Cloud la redespliegue sola en 1-2 minutos — no hay paso manual
   adicional en la web.

---

## Nota de aislamiento

Todo este proceso — repo de GitHub, autorización, despliegue — es específico de ESTE proyecto.
Nunca toques el repositorio, la autorización de GitHub App, ni la app de Streamlit Cloud de
Colombia.com (`calculadora-editorial-colombiacom` / `desempeno-editorial-colombiacom.streamlit.app`)
ni de ningún otro proyecto de Edwin mientras trabajas en este. Si al revisar `gh auth status` o
la lista de apps de Streamlit Cloud aparecen apps/repos de otros proyectos, no los edites ni los
elimines — son de otro trabajo, no se tocan.
