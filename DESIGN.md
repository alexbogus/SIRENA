# DESIGN.md — Sistema de diseño SIRENA

Guía para replicar el lenguaje visual de SIRENA en otros proyectos (paneles de
control, dashboards internos, herramientas operativas). No es una librería de
componentes instalable: es un conjunto de decisiones + fragmentos de código
para copiar y adaptar. Todo lo que aparece como bloque de código está sacado
literalmente de `templates/base.html` y las macros de `templates/_*.html`.

## 0. Filosofía

- **Minimalismo utilitario, no marketing.** Bordes finos casi invisibles,
  tarjetas planas sin sombra pesada, jerarquía por tipografía y espaciado, no
  por decoración. Referencia: Notion / Linear, adaptado a modo oscuro.
- **Un único acento de color.** El color de marca es el único protagonista de
  color en toda la app. Todo lo demás es una escala neutra (gris/grafito).
  Los colores semánticos (éxito/aviso/error/info) son la única excepción, y
  están fijados a un significado, nunca a "lo que quede bien" en cada pantalla.
- **Un solo punto de verdad por decisión.** La paleta vive en un objeto de
  `tailwind.config` + un bloque de variables OKLCH, no en clases repetidas por
  plantilla. Los patrones que se repiten (cabecera de página, badge, estado
  vacío) son macros de Jinja, no HTML copiado y pegado.
- **Nada de "AI slop":** sin gradientes morados, sin iconos mezclados de dos
  librerías, sin `⚠`/`✓` en texto plano cuando hay una librería de iconos ya
  cargada, sin frases de placeholder ("No hay datos.") sin componer.

## 1. Stack

- **Tailwind CSS** vía CDN (`cdn.tailwindcss.com`) + configuración inline en
  `<script>tailwind.config = {...}</script>`. No hay build step.
- **daisyUI v4** (`cdn.jsdelivr.net/npm/daisyui@4.12.14`) para primitivas de
  formulario/modal/menu (`input`, `select`, `modal`, `menu`, `drawer`), con un
  tema custom por CSS variables (ver §2).
- **Lucide** (`unpkg.com/lucide@latest`) como única librería de iconos. Nunca
  mezclar con otra (Feather, Heroicons, emoji) en el mismo proyecto.
- **Jinja2** (o el motor de plantillas equivalente) con macros para los
  patrones repetidos — ver §5.
- Fuentes vía Google Fonts `<link>` (aceptable aquí porque no hay build step
  ni requisitos de rendimiento agresivos; en un proyecto con bundler, usar
  `next/font` o self-host en su lugar).

## 2. Paleta

### 2.A Base neutra — "grafito" (croma 0, sin tinte de color)

Nunca uses un gris con tinte (azulado tipo `slate` de Tailwind por defecto,
o marrón tipo `stone`) junto a un fondo neutro puro: es la fuente nº1 de
inconsistencia de "dos familias de gris" en un mismo proyecto.

```js
// tailwind.config.theme.extend.colors
navy: {              // nombre libre — es la escala de fondo/superficie
    950: '#121212',  // fondo de página
    900: '#1a1a1a',  // superficies (tarjetas, sidebar, cabeceras de tabla)
    850: '#202020',  // hover / superficie elevada
    800: '#262626',  // bordes sólidos legacy, fondos de badge neutro
    700: '#333333',  // secondary de daisyUI
    600: '#4d4d4d',  // estados "apagados" (dots offline, barras inactivas)
},
// Sobrescribe el slate por defecto de Tailwind (que es azulado) para que
// TODO el texto secundario (text-slate-*) use la misma familia neutra que
// el fondo, sin tener que tocar una sola clase en las plantillas.
slate: {
    100: '#f2f2f1', 200: '#e2e2e0', 300: '#c7c7c4', 400: '#a3a3a0',
    500: '#8a8a87', 600: '#6b6b68', 700: '#525250', 800: '#3a3a38', 900: '#232322',
},
```

### 2.B Acento de marca

Un solo color, tres pasos (base/soft/dark). En SIRENA es el naranja
institucional de Protección Civil — **en otro proyecto, sustituye este bloque
por el color de marca de ese proyecto y nada más**; el resto del sistema no
cambia.

```js
brand: {
    DEFAULT: '#f2711c',
    soft: '#ffb27a',
    dark: '#c65613',
},
```

### 2.C Colores semánticos (estado, no marca)

Fijos por significado, en cualquier proyecto: `success` = emerald,
`warn`/`pending` = amber, `danger` = red, `info` = sky, `neutral` = la escala
gris del §2.A. Nunca reasignes un color semántico distinto para el mismo
concepto en dos pantallas (ver macro `badge()`, §5.2).

### 2.D Tema daisyUI (variables OKLCH)

daisyUI v4 espera `L% C H` en OKLCH, no HSL/hex — si defines los tokens con
otro formato, los componentes de daisyUI renderizan sin color. Para grises
puros (`navy-*`), croma y matiz son `0`; solo la marca tiene croma real.

```css
[data-theme="tuproyecto"] {
    color-scheme: dark;
    --p: 69.56% 0.1737 48.69;   /* primary = color de marca */
    --pc: 19.35% 0.0211 47.60;  /* texto sobre primary */
    --s: 32.11% 0 0;            /* secondary = navy-700 */
    --sc: 95% 0 0;
    --a: 83.32% 0.1069 54.40;   /* accent = marca-soft */
    --ac: 19.35% 0.0211 47.60;
    --n: 24.35% 0 0;            /* neutral = navy-850 */
    --nc: 95% 0 0;
    --b1: 18.22% 0 0;           /* base-100 = navy-950 (fondo) */
    --b2: 21.78% 0 0;           /* base-200 = navy-900 */
    --b3: 26.86% 0 0;           /* base-300 = navy-800 */
    --bc: 95% 0 0;
    --rounded-box: 1rem;
    --rounded-btn: 0.6rem;
}
```
Convierte hex → OKLCH con cualquier conversor sRGB→Oklab estándar al adaptar
esto a un nuevo color de marca (ver script de referencia en el historial del
proyecto si hace falta recalcular).

## 3. Tipografía

Tres familias, cada una con un rol fijo — no se mezclan fuera de su rol:

| Rol | Fuente | Uso |
|---|---|---|
| Display (`font-display`) | Barlow Condensed | `h1`, `h2`, `h3`, wordmark |
| Cuerpo (`font-sans`, por defecto) | Public Sans | Todo el texto de UI |
| Editorial (`font-editorial`) | Newsreader (itálica) | Solo hero/landing (login), nunca en el panel interno |

```js
fontFamily: {
    sans: ['"Public Sans"', 'system-ui', 'sans-serif'],
    display: ['"Barlow Condensed"', 'system-ui', 'sans-serif'],
    editorial: ['"Newsreader"', 'serif'],
},
```
```css
h1, h2, h3, .font-display { font-family: 'Barlow Condensed', system-ui, sans-serif; }
```

Escala fija para `<h1>` de página interna: `text-2xl font-semibold
tracking-tight` — nunca `text-xl` en unas páginas y `text-2xl` en otras.

## 4. Utilidades CSS globales (una sola vez, en el layout base)

```css
/* Cifras que cambian (contadores, %, dBm): sin esto "bailan" de anchura
   cada vez que se refrescan. */
.tnum { font-variant-numeric: tabular-nums; }

/* Etiqueta editorial sobre un <h1> interno — ver macro page_header. */
.eyebrow {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(255, 178, 122, .8); /* brand-soft/80 — ajustar al color de marca */
    margin-bottom: 0.375rem;
}

/* Botón primario único — sustituye cualquier variante "bg-brand ... px-4
   py-2" hecha a mano y repetida por plantilla. */
.btn-brand {
    background-color: #f2711c; /* = brand DEFAULT */
    color: #fff;
    border-radius: 0.5rem;
    font-weight: 600;
    transition: background-color 150ms, transform 150ms;
}
.btn-brand:hover { background-color: #c65613; } /* = brand dark */
.btn-brand:active { transform: scale(0.98); }

/* Foco de teclado visible en TODA la app, sin tocar cada input/botón. */
:focus-visible {
    outline: 2px solid rgba(242, 113, 28, .6); /* = brand/60 */
    outline-offset: 2px;
}

/* Entrada suave para pantallas de acceso (login/setup), respetando
   prefers-reduced-motion. */
.fade-in-up {
    opacity: 0;
    transform: translateY(12px);
    animation: fade-in-up 600ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
    animation-delay: var(--fade-delay, 0ms);
}
@keyframes fade-in-up { to { opacity: 1; transform: translateY(0); } }
@media (prefers-reduced-motion: reduce) {
    .fade-in-up { animation: none; opacity: 1; transform: none; }
}
```

## 5. Componentes reutilizables (macros Jinja)

No repitas markup por página — cada patrón que aparece más de dos veces se
extrae a una macro. En SIRENA viven en `templates/_*.html`:

### 5.1 `_page_header.html` — cabecera de página interna
```jinja
{% macro page_header(eyebrow, title, subtitle=none) %}
<div class="mb-6">
    <div class="eyebrow">{{ eyebrow }}</div>
    <h1 class="text-2xl font-semibold tracking-tight">{{ title }}</h1>
    {% if subtitle %}<p class="text-sm text-slate-400 mt-0.5">{{ subtitle }}</p>{% endif %}
</div>
{% endmacro %}
```
Uso: `{{ page_header("PANEL DE CONTROL", "Panel") }}`. Para cabeceras con
elementos extra al lado (badge de contador, botón de acción), no envuelvas
todo el flex row en la macro — usa solo la clase `.eyebrow` + el `<h1>` a
mano dentro de tu propio layout, para no forzar la macro a cubrir casos que
no encajan en su forma.

### 5.2 `_badge.html` — badge de estado semántico
```jinja
{% macro badge(text, tone="neutral") %}
{% set tones = {
    "success": "bg-emerald-900/60 text-emerald-300 border-emerald-700/60",
    "warn": "bg-amber-900/60 text-amber-300 border-amber-700/60",
    "danger": "bg-red-900/60 text-red-300 border-red-700/60",
    "info": "bg-sky-900/60 text-sky-300 border-sky-700/60",
    "neutral": "bg-navy-800 text-slate-400 border-white/10",
} %}
<span class="text-xs px-2 py-0.5 rounded-full border font-medium {{ tones[tone] }}">{{ text }}</span>
{% endmacro %}
```
Regla de oro: el mismo concepto usa siempre el mismo tono en todas las
pantallas ("activo" es `success` en todas partes, nunca `sky` en una página
y `emerald` en otra).

### 5.3 `_empty_state.html` — estado vacío compuesto
```jinja
{% macro empty_state(icon, text, cta_href=none, cta_label=none, colspan=none) %}
{% set inner %}
<div class="flex flex-col items-center justify-center gap-2 py-10 text-center">
    <i data-lucide="{{ icon }}" class="w-8 h-8 text-slate-700"></i>
    <p class="text-slate-500 text-sm">{{ text }}</p>
    {% if cta_href %}<a href="{{ cta_href }}" class="text-brand-soft text-xs font-semibold hover:underline mt-1">{{ cta_label }}</a>{% endif %}
</div>
{% endset %}
{% if colspan %}<tr><td colspan="{{ colspan }}">{{ inner }}</td></tr>{% else %}{{ inner }}{% endif %}
{% endmacro %}
```
Nunca dejes un `<p class="text-slate-500">Sin datos.</p>` suelto — es la
señal más rápida de "panel a medio terminar" para una auditoría.

### 5.4 `_select.html` — selección única con estilo propio (nunca `<select>` nativo)

`<select>` nativo **no se puede colorear cuando está abierto**: el popup de
opciones lo renderiza el sistema operativo/navegador, no la página — en
Chrome/macOS la opción resaltada sale siempre en azul de acento del sistema,
sin importar el CSS. Es la razón nº1 por la que un desplegable "rompe" la
paleta de un proyecto que por lo demás es 100% coherente.

Regla del sistema: **nunca uses `<select>` nativo visible.** Usa siempre este
patrón, que ya existía para multiselección (`_multiselect.html`) y aquí se
adapta a selección única:

```jinja
{% macro select_dropdown(name, options, selected_value=none, id=none, size="md") %}
{% set sel = selected_value|string %}
{% set pad = "px-2 py-1.5 text-xs" if size == "sm" else "px-3 py-2 text-sm" %}
<div class="relative" data-select-dropdown>
    <select name="{{ name }}" {% if id %}id="{{ id }}"{% endif %} class="sr-only" tabindex="-1" aria-hidden="true">
        {% for opt in options %}
        <option value="{{ opt.value }}" {{ 'selected' if opt.value|string == sel else '' }}>{{ opt.label }}</option>
        {% endfor %}
    </select>
    <button type="button" data-dropdown-toggle-btn
            class="w-full flex items-center justify-between gap-2 bg-navy-800 border border-white/10 rounded-lg {{ pad }} text-left hover:border-navy-600">
        <span data-dropdown-label class="truncate"></span>
        <i data-lucide="chevron-down" class="w-4 h-4 text-slate-400 shrink-0"></i>
    </button>
    <div data-dropdown-panel
         class="hidden absolute z-20 mt-1 w-full max-h-56 overflow-y-auto bg-navy-900 border border-white/10 rounded-lg shadow-lg p-1 space-y-0.5">
        {% for opt in options %}
        <button type="button" data-dropdown-option data-value="{{ opt.value }}"
                class="w-full text-left flex items-center justify-between gap-2 px-2 py-1.5 rounded-md hover:bg-navy-800 text-sm">
            <span class="truncate">{{ opt.label }}</span>
            <i data-lucide="check" class="w-3.5 h-3.5 text-brand shrink-0 {{ '' if opt.value|string == sel else 'invisible' }}"></i>
        </button>
        {% endfor %}
    </div>
</div>
{% endmacro %}
```

Detalle clave: dentro del `<select>` real, ahora oculto con `sr-only` (no
`display:none`, para que siga siendo enfocable/legible por lectores de
pantalla y participe en el envío del formulario). El botón+panel visibles
solo lo pilotan; al elegir una opción se hace `select.value = ...` y se
dispara un evento `change` sintético (`select.dispatchEvent(new
Event("change", {bubbles: true}))`), así que **cualquier JS existente que ya
leyera `.value` o escuchara `"change"` sobre ese `<select>` sigue funcionando
sin tocarlo** — es la razón por la que este patrón se puede meter encima de
un `<select>` ya usado por otro script sin reescribir ese script.

La inicialización (`initSelectDropdown`, delegada sobre
`[data-select-dropdown]`) vive una sola vez en el layout base y reutiliza el
mismo cierre-al-hacer-click-fuera que ya tenía el desplegable de
multiselección (ambos comparten el atributo `data-dropdown-panel`).

### 5.5 Tablas tipo Notion
Sin rejilla completa (`border` en cada celda). Contenedor con borde único +
cabecera translúcida + separadores solo horizontales + resalte de fila al
pasar el ratón:
```html
<table class="w-full text-sm bg-navy-900 border border-white/10 rounded-xl overflow-hidden">
    <thead class="bg-navy-900/60 text-slate-400 text-left border-b border-white/10">...</thead>
    <tbody class="divide-y divide-white/5">
        <tr class="hover:bg-navy-850/40">...</tr>
    </tbody>
</table>
```

### 5.6 Tarjetas
`bg-navy-900 border border-white/10 rounded-xl` — sin `shadow-*`. La
elevación se comunica con el borde y el contraste de fondo, no con sombra.

### 5.7 Botones — tres variantes fijas, nunca una cuarta

| Variante | Cuándo | Clases |
|---|---|---|
| **Primario de marca** | Una sola acción principal por formulario/página (guardar, crear, enviar) | `.btn-brand` (§4) — `px-4 py-2 text-sm`, o `class="btn bg-brand hover:bg-brand-dark text-white border-0"` cuando necesitas las utilidades de tamaño/gap de daisyUI (`btn-sm`, `gap-2`) sobre el mismo color. Las dos formas pintan el mismo naranja; usa `.btn-brand` por defecto y la variante `btn`+`bg-brand` solo cuando ya estás dentro de un `btn` de daisyUI con `btn-sm`/icono. |
| **Ghost neutro** | Acciones secundarias: cancelar, iconos de acción en tablas, botón de logout | `btn btn-ghost` (+ `btn-sm`, `btn-square` para icon-only) con `text-slate-400`, aclarando en hover al color que corresponda: `hover:text-white` (edición genérica), `hover:text-amber-400` (activar/desactivar), `hover:text-red-400` (eliminar/salir), `hover:text-emerald-300` (variante de icon+label en vez de icon-only, ver `rules.html`). El color de hover **siempre** comunica la naturaleza de la acción, nunca es decorativo. |
| **Semántico de daisyUI** (`btn-primary` / `btn-error`) | Solo dentro del modal de confirmación genérico (§5.9) | `btn-primary` para confirmar una acción neutra, `btn-error` cuando `data-confirm-variant="danger"` (borrados). No se usan sueltos en el resto de la UI — son el único sitio donde se apoya en el color `primary`/`error` de daisyUI en vez de `.btn-brand`/semánticos manuales. |

Icon-only siempre `btn btn-sm btn-square btn-ghost` con `title="..."` para
accesibilidad (no hay texto visible que lo sustituya). Nunca mezclar
`btn-brand` a mano (bg-color inline) con las utilidades `btn-*` de daisyUI en
el mismo botón — o son clases custom (`.btn-brand`) o son `btn` + utilidades
Tailwind, nunca ambos sistemas fundidos.

### 5.8 Formularios e inputs

Todo `<input>`/`<textarea>` de texto lleva foco de marca explícito
(`focus:border-brand focus:outline-none`) porque el `:focus-visible` global
(§4/§7) ya cubre accesibilidad por teclado, pero un input de texto necesita
además feedback visual claro con el ratón. Dos variantes según contexto —
**elige una sola por proyecto nuevo**, no mezcles ambas como ocurre hoy entre
plantillas de SIRENA (deuda a limpiar, no a copiar):

- **Dentro de modal** (login, setup, altas rápidas): patrón `form-control` de
  daisyUI, con `label-text` en vez de `<label>` a mano:
  ```html
  <div class="form-control w-full">
      <label class="label py-0 mb-2">
          <span class="label-text text-xs font-semibold text-slate-400 uppercase tracking-wide">Nombre</span>
      </label>
      <input class="input w-full bg-navy-950 border-white/10 focus:border-brand focus:outline-none">
  </div>
  ```
- **Inline en tarjeta de página** (ajustes, formularios de alta de
  reglas/zonas): `<label>` simple + input con borde manual, sin la clase
  `input` de daisyUI:
  ```html
  <div>
      <label class="block text-xs text-slate-400 mb-1">Nombre</label>
      <input class="w-full bg-navy-800 border border-white/10 rounded-lg px-3 py-2">
  </div>
  ```
  Recomendado como **variante única** al portar el sistema a un proyecto
  nuevo: es la que no depende de las clases de formulario de daisyUI y por
  tanto sigue funcionando igual si en el futuro se retira daisyUI del stack.

Checkbox suelto (p. ej. "Regla activa"): `<label class="flex items-center
gap-2 text-sm"><input type="checkbox" ...> Texto</label>` — nunca un
checkbox sin su label envolvente (área de click pequeña, mala accesibilidad).

Nunca `<select>` nativo visible — usa siempre `select_dropdown` (§5.4) o
`multiselect` (`_multiselect.html`, mismo patrón de checkbox+panel que
`select_dropdown` pero con `<input type="checkbox">` en vez de radio-como-botón).

### 5.9 Modales

`<dialog>` nativo de daisyUI (`showModal()`/`close()` desde `onclick` inline
del botón que lo abre — sin librería de modales aparte):
```html
<dialog id="add_speaker_modal" class="modal">
    <div class="modal-box bg-navy-900 border border-white/10">
        ...
        <div class="modal-action">
            <button type="button" onclick="add_speaker_modal.close()" class="btn btn-sm btn-ghost">Cancelar</button>
            <button class="btn btn-sm bg-brand hover:bg-brand-dark text-white border-0">Añadir altavoz</button>
        </div>
    </div>
</dialog>
```
`modal-box` siempre lleva `bg-navy-900 border border-white/10` explícito
(el tema daisyUI ya define `--b2`/`--b3` pero se fija a mano para que el
modal use el mismo tono de superficie que tarjetas y sidebar sin depender de
qué variable de daisyUI resuelva). Acciones siempre alineadas a la derecha
(`modal-action` o `flex justify-end gap-2`), cancelar (ghost) a la izquierda
del botón primario.

**Modal de confirmación genérico** — sustituye a `confirm()` nativo del
navegador en cualquier formulario destructivo o no trivial, vive una sola
vez en `base.html` y se dispara declarativamente:
```html
<form method="post" action="..." data-confirm="¿Eliminar este altavoz?" data-confirm-variant="danger">
```
El listener global en `base.html` intercepta el `submit` de cualquier
`form[data-confirm]`, rellena el texto del modal (`#confirm-modal-text`),
colorea el botón de aceptar (`btn-primary` por defecto, `btn-error` si
`data-confirm-variant="danger"`) y solo hace `form.submit()` real tras
click en aceptar — cierre también por click fuera o `Escape`. Al portar el
sistema, copia este modal + su script tal cual (§8): es lo que garantiza que
ningún formulario nuevo caiga en `confirm()` nativo, que no se puede
colorear ni testear.

### 5.10 Alertas / flash messages
Mensajes flash del backend (`get_flashed_messages`), siempre vía las clases
semánticas de daisyUI, nunca un `<div>` de color hecho a mano:
```html
<div class="alert {{ 'alert-error' if category == 'error' else 'alert-success' }} text-sm py-2">
    {{ message }}
</div>
```
Solo dos categorías en uso (`error`/`success`); si se necesita `warning`/
`info` como flash, usar `alert-warning`/`alert-info` de daisyUI, no una
combinación manual `bg-*-900/60 text-*-300` (eso queda reservado para el
badge de estado, §5.2, que sí necesita tonos más sutiles que el `alert`
de daisyUI).

### 5.11 Fila de KPIs y estados de carga

Resumen numérico en la parte superior de una página de listado: tarjeta
única dividida en columnas iguales, sin fondo ni borde por celda — solo
separadores:
```html
<div class="bg-navy-900 border border-white/10 rounded-xl mb-6 divide-y divide-white/5">
    <div class="grid grid-cols-2 sm:grid-cols-4 divide-x divide-white/5">
        <div class="px-4 py-3">
            <div class="text-xs text-slate-500 mb-1">Etiqueta</div>
            <div class="text-xl font-semibold tnum">{{ valor }}</div>
        </div>
        <!-- ... -->
    </div>
</div>
```
El número siempre lleva `.tnum` (§4) porque estas cifras se refrescan por
polling — sin tabular-nums el ancho de columna "baila" en cada refresco.

**Estado de carga (skeleton)**, para listados que se rellenan por `fetch` al
cargar la página en vez de venir ya renderizados por el servidor: tarjetas
placeholder con la misma geometría que la tarjeta real, `animate-pulse` de
Tailwind, bloques internos en `bg-navy-800 rounded`/`rounded-lg` en vez de
texto — nunca un spinner genérico centrado, para que el layout no salte
cuando llegan los datos reales:
```html
<div class="bg-navy-900 border border-white/10 rounded-xl p-4 space-y-3 animate-pulse">
    <div class="h-4 w-2/3 bg-navy-800 rounded"></div>
    <div class="h-16 bg-navy-800 rounded-lg"></div>
</div>
```

## 6. Layout de aplicación (sidebar + contenido)

Estructura basada en el `drawer` de daisyUI, no en un sidebar posicionado a
mano con `fixed`/`absolute`: en desktop queda siempre abierto (`lg:drawer-open`)
y en móvil colapsa a un drawer deslizante controlado por un `<input
type="checkbox">` oculto — sin JS propio para abrir/cerrar.

```html
<div class="drawer lg:drawer-open">
    <input id="sidebar-drawer" type="checkbox" class="drawer-toggle" />
    <div class="drawer-content flex flex-col">
        <!-- barra superior SOLO visible en móvil (lg:hidden): logo + botón hamburguesa -->
        <div class="lg:hidden flex items-center justify-between px-4 py-3 border-b border-white/10 bg-navy-900">
            <a href="..." class="flex items-center">
                <img src="..." class="h-5 w-auto" alt="...">
            </a>
            <label for="sidebar-drawer" class="btn btn-sm btn-square btn-ghost">
                <i data-lucide="menu" class="w-5 h-5"></i>
            </label>
        </div>
        <!-- contenido de página: ancho máximo centrado, nunca full-bleed -->
        <main class="max-w-6xl w-full mx-auto px-6 py-8">
            {{ contenido de la página }}
        </main>
    </div>
    <div class="drawer-side z-20">
        <label for="sidebar-drawer" aria-label="close sidebar" class="drawer-overlay"></label>
        <aside class="w-60 min-h-full bg-navy-900 border-r border-white/10 flex flex-col">
            <!-- ... ver detalle abajo ... -->
        </aside>
    </div>
</div>
```

**Reglas fijas del sidebar:**

- **Ancho**: `w-60` (240px), fijo — no `w-64`/`w-56` en unas plantillas y
  otro valor en otras. `min-h-full` para cubrir todo el alto de viewport.
- **Posición**: izquierda, vía `drawer-side` de daisyUI (en desktop es
  estáticamente parte del flujo por `lg:drawer-open`; en móvil es un overlay
  con `z-20` sobre el contenido, cerrado por click fuera gracias a
  `drawer-overlay`). Nunca `position: fixed` hecho a mano.
- **Fondo/borde**: `bg-navy-900` (mismo tono que las tarjetas) +
  `border-r border-white/10` — nunca un tono de fondo distinto al de las
  superficies del resto de la app, ni sombra (`shadow-*`) para separarlo del
  contenido; el borde de 1px es toda la separación visual necesaria.
- **Logo/wordmark**: arriba del todo, `px-5 py-5`, imagen a `h-6 w-auto`
  (en la topbar móvil equivalente, `h-5`) — nunca el nombre de la app como
  texto plano si existe un wordmark en imagen.
- **Lista de navegación**: `<ul class="menu flex-1 px-3 gap-1 text-sm
  flex-nowrap">` — `flex-1` para empujar el pie (info institucional + logout)
  al fondo del sidebar aunque haya pocos items.
- **Item de navegación — estados**:
  - Contenedor: `rounded-lg` en todos los estados.
  - Inactivo: `text-slate-400`, hover a `hover:text-slate-100
    hover:bg-navy-850/60` (fondo hover con 60% de opacidad, no sólido).
  - Activo (`request.endpoint == endpoint`): clase `active` de daisyUI +
    `bg-navy-850 text-white` (fondo sólido, no `/60`, y texto blanco puro en
    vez de `slate-100`, para que el item activo destaque claramente sobre el
    hover).
  - **Coloreado de iconos**: el icono (`w-4 h-4`, Lucide) hereda el color del
    texto del link salvo en el estado activo, donde se le añade
    explícitamente `text-brand` — es el único icono de todo el sidebar que
    lleva el color de marca; en inactivo/hover el icono es neutro (mismo gris
    que el texto). Nunca colorear iconos de nav en más de un tono a la vez.
- **Pie del sidebar** (fuera de la lista, después del `flex-1`):
  - Bloque de texto institucional: `px-5 py-3 border-t border-white/10
    text-[11px] text-slate-500 leading-tight` — separado de la nav por un
    borde superior, tamaño de fuente por debajo de la escala normal (11px
    explícito, no una utility `text-xs` de Tailwind que sería 12px).
  - Botón de salir/logout: `btn btn-ghost btn-block justify-start gap-3
    text-slate-400 hover:text-red-400` — es el único lugar del sidebar donde
    el hover usa un color semántico (`red-400`, peligro) en vez de
    aclarar a blanco; comunica que la acción es distinta a navegar.
- **Contenido principal**: `max-w-6xl w-full mx-auto px-6 py-8` — ancho
  máximo fijo y centrado dentro del espacio restante, nunca ocupa el 100%
  del viewport aunque la pantalla sea muy ancha.
- **Breakpoint móvil**: `lg` (1024px) es el corte fijo entre sidebar
  estático (desktop) y drawer deslizante con topbar (móvil) — no uses `md`
  ni `xl` para esta transición en otro proyecto, para que el comportamiento
  responsive sea idéntico entre proyectos que comparten este sistema.

## 7. Uso del logotipo

Cada proyecto tiene su propio logo y nombre — eso cambia siempre. Lo que se
mantiene es **dónde aparece, en qué tamaño, en qué formato y con qué
compañero visual** en cada punto de la app. Copia esta estructura de assets
y de colocación tal cual; sustituye solo los ficheros de imagen.

### 7.1 Assets necesarios (dos piezas, nunca una sola imagen combinada)

| Asset | Forma | Uso |
|---|---|---|
| **Icono/marca** (`logo_{proyecto}_icon.png`) | Cuadrado, recortado al glifo, fondo transparente | Favicon, marco de icono en login/setup |
| **Wordmark** (`logo_{proyecto}_wordmark.png`) | Horizontal, nombre de marca ya tipografiado como imagen, fondo transparente, recortado sin aire sobrante arriba/abajo | Sidebar, topbar móvil, caja de login |
| **Favicon** (`favicon.png`) | Derivado del icono/marca, cuadrado | `<link rel="icon">` en `<head>` |

Regla de oro: si existe wordmark en imagen, **nunca** se sustituye por el
nombre en texto plano (`<span>SIRENA</span>`) en sidebar o login — la única
excepción admitida es la navbar mínima de login (§8.1), que por estar sobre
una foto con poco espacio vertical usa un icono SVG inline (ligero, sin
petición de imagen aparte) + el nombre como texto en `font-display` en vez
del wordmark completo, y `setup.html` cuando el proyecto aún no tiene
icono de marca definitivo (usa una imagen de contexto + `<h1
class="font-display">` como fallback de texto — ver §8.3).

### 7.2 Dónde aparece y a qué tamaño (todos los usos actuales de SIRENA)

| Ubicación | Asset | Clases | Nota |
|---|---|---|---|
| `<head>` | favicon | `<link rel="icon" type="image/png" href="...">` | Una sola vez, en `base.html` |
| Sidebar desktop, arriba (§6) | wordmark | `h-6 w-auto`, contenedor `px-5 py-5` | Enlaza al home (`dashboard.index`) |
| Topbar móvil (`lg:hidden`, §6) | wordmark | `h-5 w-auto` | Un paso más pequeño que en desktop porque comparte fila con el botón hamburguesa |
| Navbar de login (§8.1) | icono SVG inline + texto | SVG `28×28`, `stroke="{brand.DEFAULT}"`, + `<span class="font-display font-bold text-lg leading-none">` | Único sitio con marca como SVG inline en vez de `<img>` |
| Caja de login (§8.3) | icono + wordmark | icono `80×80` dentro de marco `w-24 h-24`; wordmark `h-6 w-auto mb-5` debajo | Las dos piezas, apiladas, nunca combinadas en una sola imagen |
| Caja de setup (§8.3) | imagen de contexto (fallback) | `70×70` dentro del mismo marco `w-24 h-24`; `<h1 class="card-title font-display text-2xl">` en vez de wordmark | Válido mientras el proyecto no tenga icono de marca todavía |

- El **marco** `w-24 h-24 rounded-2xl bg-navy-950 border border-white/10
  flex items-center justify-center overflow-hidden` es siempre el mismo,
  esté lo que esté dentro (icono de marca real o imagen de contexto
  provisional) — es una pieza del sistema, no del logo en sí.
- La imagen dentro del marco siempre lleva `object-contain` (nunca `cover`,
  para no recortar el icono) y dos tallas fijas según qué contiene: `80px`
  si es el icono/marca real, `70px` si es una imagen de producto/contexto
  más "llena" visualmente (deja más aire al marco).
- El wordmark nunca lleva `border`/fondo propio — flota directamente sobre
  el fondo de su contenedor (sidebar `bg-navy-900`, caja de login
  `bg-navy-900/95`).

### 7.3 Al portar a un proyecto nuevo

1. Genera las dos piezas (icono cuadrado + wordmark horizontal) en PNG con
   transparencia, y el favicon derivado del icono.
2. Sustituye únicamente los `src` de los `<img>` en los puntos de la tabla
   §7.2 — no cambies ninguna clase de tamaño/posición.
3. Si el proyecto nuevo aún no tiene wordmark en imagen (fase temprana),
   usa el fallback de texto `<h1 class="font-display ...">` del patrón de
   `setup.html`, nunca un `<span>` de texto plano sustituyendo al wordmark
   en sidebar o en la caja de login — esas dos ubicaciones exigen imagen.
4. El SVG inline de la navbar de login es opcional: si el nuevo proyecto no
   tiene un glifo simple que se preste a trazo SVG, usa directamente el
   wordmark en imagen ahí también (`h-5`), en vez de forzar un SVG.

## 8. Pantallas de acceso (login / setup inicial)

Dos variantes de una misma plantilla-caja, ambas fuera del layout con
sidebar (usan `{% block content %}` sin `session.get('authenticated')`, así
que `base.html` no monta el `drawer` — ver §6). Solo la de **login** lleva
imagen de fondo + panel editorial; **setup** (alta de contraseña la primera
vez) es la caja sola, centrada en pantalla completa sin fondo ni columna de
texto — es la variante a copiar para cualquier pantalla de acceso simple
(recuperar contraseña, invitación, etc.) en un proyecto nuevo.

### 7.1 Login — fondo + panel editorial + caja

Tres capas apiladas con `-z-20`/`-z-10` sobre `position: relative` +
`isolate` en el contenedor raíz, para que el `z-index` de la caja de login
no tenga que competir con nada del resto de la página:

```html
<div class="relative min-h-screen flex flex-col overflow-hidden isolate">

    <!-- capa 1 (-z-20): foto de fondo, oscurecida con filter, no con un overlay a parte -->
    <div class="pointer-events-none absolute inset-0 -z-20 bg-cover bg-center"
         style="background-image:url('...'); filter:brightness(.5) saturate(.9) contrast(1.02);"></div>

    <!-- capa 2 (-z-10): degradado de marca muy sutil + vignette de legibilidad -->
    <div class="pointer-events-none absolute inset-0 -z-10"
         style="background:
            radial-gradient(ellipse 900px 700px at 78% 58%, rgba(242,113,28,.04), transparent 70%),
            linear-gradient(180deg, rgba(5,13,28,.85) 0%, rgba(5,13,28,.48) 42%, rgba(5,13,28,.62) 68%, rgba(5,13,28,.95) 100%);"></div>

    <!-- navbar mínima: solo wordmark, sin nav (no hay sesión todavía) -->
    <div class="navbar max-w-6xl mx-auto w-full px-4">
        <div class="flex-1 flex items-center gap-2">
            <svg ...><!-- icono de marca inline, mismo trazo que el favicon --></svg>
            <span class="font-display font-bold text-lg leading-none">SIRENA</span>
        </div>
    </div>

    <div class="flex-1 flex items-center">
        <div class="max-w-6xl mx-auto w-full px-4 grid lg:grid-cols-2 gap-16 items-center py-20">
            <!-- columna izquierda: texto editorial, ver 7.2 -->
            <!-- columna derecha: caja de login, ver 7.3 -->
        </div>
    </div>
</div>
```

Reglas de la capa de fondo:
- **Nunca** un `<div>` de overlay de color sólido encima de la imagen para
  oscurecerla — se hace con `filter: brightness()/saturate()/contrast()` en
  la propia capa de imagen, y el degradado de la capa 2 es lo único que
  añade color/legibilidad (radial muy tenue del color de marca al 4% de
  opacidad + lineal oscuro de arriba a abajo para que el texto del panel
  editorial tenga contraste garantizado sin depender de qué zona de la foto
  quede detrás).
- El radial de marca (`rgba(marca, .04)`) se posiciona `at 78% 58%` —
  hacia donde cae la caja de login (columna derecha en desktop) — para que
  el acento de color, aunque casi imperceptible, converja visualmente con la
  tarjeta y no con el texto.

### 7.2 Panel editorial (columna izquierda, solo login)

Único lugar de toda la app donde se usa `font-editorial` (Newsreader
itálica, §3) — nunca en el panel interno:
```html
<div class="fade-in-up" style="--fade-delay: 0ms;">
    <div class="inline-flex items-center gap-1.5 rounded-full bg-brand/10 border border-brand/20 text-brand-soft text-[11px] font-semibold uppercase tracking-wider px-3 py-1.5 mb-6">
        <i data-lucide="plus" class="w-3 h-3"></i>
        Sistema de megafonía IP · ALVPC Godella
    </div>
    <h1 class="font-editorial italic font-medium text-4xl sm:text-5xl leading-[1.1] tracking-tight mb-5 pb-1 [text-shadow:0_4px_24px_rgba(0,0,0,.65)]">
        SIRENA, <span class="text-brand">sistema IP de reconocimiento y envío de nuevas alertas</span>.
    </h1>
    <p class="text-slate-300 text-lg max-w-md [text-shadow:0_2px_12px_rgba(0,0,0,.7)]">
        Descripción breve del producto para quien todavía no ha entrado.
    </p>
</div>
```
- **Eyebrow-píldora** (no confundir con `.eyebrow`, §4, que es solo texto):
  fondo `bg-brand/10` + borde `border-brand/20` + texto `text-brand-soft`,
  siempre con un icono Lucide de 12px delante, nunca solo texto.
  `text-shadow` inline en `<h1>`/`<p>` — es la única sección de la app donde
  se usa, porque va sobre foto y necesita legibilidad garantizada
  independientemente del contenido de la imagen de fondo.
- Se anima con `.fade-in-up` (§4) y `--fade-delay: 0ms`; la caja de login
  (§8.3) entra 120ms después (`--fade-delay: 120ms`) para que el ojo lea
  primero el mensaje y luego el formulario.
- En `lg:grid-cols-2`, esta columna va primero (izquierda); en móvil ambas
  columnas apilan y esta pasa a ir arriba, sobre la caja.

### 7.3 Caja de login / setup

```html
<div class="card w-full max-w-sm mx-auto bg-navy-900/95 border border-white/10 rounded-xl shadow-[0_1px_2px_rgba(0,0,0,.3)] fade-in-up" style="--fade-delay: 120ms;">
    <div class="card-body items-center text-center">
        <div class="w-24 h-24 rounded-2xl bg-navy-950 border border-white/10 flex items-center justify-center overflow-hidden mb-3">
            <img src="..." class="w-[80px] h-[80px] object-contain" alt="">
        </div>
        <img src="..." class="h-6 w-auto mb-5" alt="SIRENA"> <!-- wordmark -->
        <form method="post" class="w-full space-y-4 text-left">
            <!-- inputs: patrón form-control de §5.8 -->
            <button type="submit" class="btn btn-primary btn-block shadow-none active:scale-[0.98]">Entrar</button>
        </form>
        <p class="text-center text-xs text-slate-500 mt-4">Acceso restringido · Nombre de la organización</p>
    </div>
</div>
```

- **Ancho/posición**: `max-w-sm` (384px), centrada con `mx-auto`. En login
  ocupa la columna derecha del grid de dos columnas (§8.1); en setup, al no
  haber panel editorial ni fondo, va sola en `min-h-screen flex items-center
  justify-center` — es decir, centrada en toda la pantalla, ambas ejes.
- **Fondo de la caja**: `bg-navy-900/95` — el único sitio del sistema donde
  una superficie lleva opacidad (`/95`) en vez de color sólido, porque en
  login flota sobre la foto de fondo y necesita dejar traslucir un mínimo de
  esa imagen para no verse como un recorte pegado encima.
- **Única excepción de sombra del sistema**: `shadow-[0_1px_2px_rgba(0,0,0,.3)]`
  — una sombra casi imperceptible, deliberadamente mínima (el resto de la
  app usa borde en vez de sombra, §5.6, pero aquí la caja flota sobre una
  foto en vez de sobre el fondo grafito plano, y sin ninguna sombra se
  fundiría visualmente con la imagen).
- **Logo — dos piezas apiladas, no una sola imagen combinada**:
  1. Icono de marca dentro de un cuadrado `w-24 h-24 rounded-2xl bg-navy-950
     border border-white/10`, con la imagen a `80×80px` (`object-contain`,
     nunca recortada) centrada dentro — actúa de "marco" para el icono,
     mismo lenguaje visual que las tarjetas (fondo + borde, sin sombra).
  2. Wordmark (nombre de marca en imagen) justo debajo, `h-6 w-auto mb-5`,
     sin marco — mismo alto que el wordmark del sidebar (§6).
  En `setup.html` (sin icono de marca de producto en este caso concreto) se
  sustituye por una imagen de producto en el mismo marco `w-24 h-24`, y el
  wordmark por un `<h1 class="card-title font-display text-2xl">` de texto
  — usa la variante con imagen siempre que exista un icono de marca real.
- **Formulario**: siempre el patrón `form-control` de daisyUI (§5.8,
  variante "dentro de modal") — nunca el patrón de borde manual de página
  aquí, porque la caja de login/setup se comporta como un modal flotante,
  no como contenido inline de una página.
- **Botón de envío**: único sitio (junto al confirm-modal, §5.9) donde se
  usa `btn-primary` de daisyUI en vez de `.btn-brand` — siempre `btn-block`
  (ancho completo de la caja) + `active:scale-[0.98]` para feedback táctil
  al pulsar, sin `shadow-none` explícito porque daisyUI añade sombra por
  defecto a `btn-primary` y aquí se quiere plano como el resto del sistema.
- **Pie**: una línea `text-xs text-slate-500` con el nombre de la
  organización/contexto de despliegue — mismo tono que el pie del sidebar
  (§6), refuerza que es texto institucional secundario, no parte del
  formulario.

## 9. Iconografía

Una sola librería (Lucide) en todo el proyecto, cargada una vez en el layout
base + `lucide.createIcons()` tras cada render dinámico (incluido dentro de
cualquier `fetch`/refresh periódico, o los iconos inyectados por JS no se
resuelven). Nunca un glifo Unicode crudo (`✓ ✗ ⚠ ▲ ▼`) cuando la librería ya
está cargada — usa `check`, `x`, `triangle-alert`, `chevron-up/down`.

## 10. Accesibilidad (no negociable)

- `:focus-visible` global (ver §4) — nunca `outline-none` sin sustituto.
- Contraste AA mínimo: con la base grafito (`navy-950 #121212`) y texto
  `slate-100`/`slate-400`, y el acento sobre fondo oscuro, ya cumple; si
  cambias el color de marca en otro proyecto, verifica el contraste del
  nuevo acento sobre `#121212` antes de darlo por bueno.
- `prefers-reduced-motion` respetado en cualquier animación de entrada.
- Modal de confirmación propio en vez de `confirm()` nativo del navegador
  (patrón `data-confirm="texto"` en el `<form>`, ver `base.html`) — accesible
  por teclado (Escape cierra, foco gestionado).

## 11. Qué cambia por proyecto vs. qué se mantiene

| Se mantiene igual (sistema) | Se adapta por proyecto |
|---|---|
| Escala grafito §2.A, tokens OKLCH neutros | Color de marca §2.B (+ recalcular `--p`/`--pc`/`--a`/`--ac`) |
| Tipografía (3 fuentes, roles fijos) | Nombre/wordmark, nav items del sidebar |
| `.tnum`, `.eyebrow`, `.btn-brand`, focus-visible, fade-in-up | Textos del pie institucional del sidebar |
| Macros `page_header`/`badge`/`empty_state`/`select_dropdown` | Iconos elegidos por página (siempre Lucide, pero cuáles) |
| Colores semánticos (success/warn/danger/info) | — (no cambian, son universales) |
| Tablas Notion-style, tarjetas sin sombra | Contenido de las tarjetas/tablas |
| Estructura de layout §6: `drawer` de daisyUI, ancho `w-60`, breakpoint `lg`, estados de nav (inactivo/hover/activo), regla de un solo icono con `text-brand` | Nombre/wordmark del logo, items de navegación (endpoint/icono/label), texto del pie institucional |
| Tres variantes de botón §5.7 (primario marca / ghost neutro con hover semántico / semántico daisyUI solo en confirm-modal) | Textos y acciones concretas de cada botón |
| Variante única de input elegida (§5.8 — recomendado el patrón "inline en tarjeta") | Campos concretos de cada formulario |
| Modal `<dialog>` de daisyUI + modal de confirmación genérico `data-confirm` (§5.9) | Contenido de cada modal |
| Alertas flash con clases semánticas de daisyUI (§5.10) | Textos de los mensajes |
| Fila de KPIs + patrón skeleton de carga (§5.11) | Qué KPIs mostrar, qué listado tiene loading async |
| Estructura de login §8: 3 capas de fondo, grid de 2 columnas, caja `max-w-sm`, orden/animación `fade-in-up` con delay escalonado, doble logo (marco + wordmark), única sombra del sistema | Foto de fondo, copy del panel editorial, campos concretos del formulario, texto del pie |
| Uso del logo §7: dos assets (icono cuadrado + wordmark horizontal), tamaños/ubicaciones exactos (sidebar `h-6`, topbar móvil `h-5`, marco de login `w-24 h-24`), marco común, jerarquía icono+wordmark siempre apilados | Los ficheros de imagen del logo/wordmark en sí, nombre de la app |

## 12. Checklist rápido al portar esto a un proyecto nuevo

1. Copia el bloque `tailwind.config` completo (§2.A–2.B) y sustituye solo
   `brand.DEFAULT/soft/dark` por el color de marca del proyecto nuevo.
2. Recalcula `--p`/`--pc`/`--a`/`--ac` en OKLCH para el nuevo color de marca
   (hex → OKLCH); copia el resto del bloque `[data-theme]` tal cual.
3. Copia las utilidades CSS del §4 tal cual, ajustando solo los hex del
   acento en `.eyebrow` y `:focus-visible`.
4. Copia las 4 macros del §5.1–5.4 sin modificar.
5. Copia la estructura de layout completa del §6 (`drawer`/`drawer-side` de
   daisyUI, `aside` a `w-60`, topbar móvil `lg:hidden`) y sustituye solo el
   logo, la lista `nav_items` y el texto del pie institucional — no cambies
   el ancho del sidebar, el breakpoint `lg`, ni la regla de un único icono
   con `text-brand` en el item activo.
6. Copia las tres variantes de botón del §5.7 tal cual (`.btn-brand`, ghost
   con hover semántico según acción, `btn-primary`/`btn-error` reservado al
   confirm-modal) — no inventes una cuarta variante ad-hoc para un caso
   nuevo.
7. Elige **una sola** variante de input del §5.8 (recomendado: el patrón
   "inline en tarjeta" del bloque final de esa sección, por no depender de
   las clases de formulario de daisyUI) y úsala en todos los formularios del
   proyecto nuevo — no arrastres la mezcla de dos patrones que hoy conviven
   en SIRENA.
8. Copia el `<dialog>` de daisyUI para modales puntuales y el modal de
   confirmación genérico + su script del §5.9 tal cual — es lo que evita que
   aparezca un `confirm()` nativo del navegador en un formulario nuevo.
9. Copia el bloque de alertas flash del §5.10 y, si la página lo necesita,
   el patrón de fila de KPIs + skeleton de carga del §5.11.
10. Genera los dos assets de logo del §7.1 (icono cuadrado + wordmark
    horizontal + favicon derivado) y colócalos exactamente en los puntos y
    tamaños de la tabla §7.2 (sidebar `h-6`, topbar móvil `h-5`, navbar de
    login, marco `w-24 h-24` + wordmark de la caja de login/setup) — no
    inventes un tamaño ni una ubicación nueva para el logo.
11. Copia la pantalla de login del §8 tal cual (3 capas de fondo, panel
    editorial, caja `max-w-sm`) sustituyendo solo la foto de fondo, el copy
    editorial y el texto del pie (el logo ya lo pusiste en el paso 10); para
    cualquier pantalla de acceso sin foto (setup, recuperar contraseña) usa
    la variante simplificada del §8.3 (caja sola centrada en pantalla, sin
    capas de fondo ni panel editorial).
12. Antes de dar por cerrado el rediseño, audita: ¿hay dos sistemas de botón
    distintos, o una variante de botón fuera de las tres del §5.7? ¿un badge
    con el mismo significado pero dos colores en dos páginas? ¿algún glifo
    Unicode crudo? ¿algún `<p>` de estado vacío suelto sin componer? ¿queda
    algún `<select>` nativo visible (se delata por el popup en azul de
    sistema al abrirlo)? ¿el sidebar tiene un ancho distinto de `w-60` en
    alguna plantilla, o más de un icono coloreado con el acento de marca a
    la vez? ¿conviven las dos variantes de input del §5.8 en el mismo
    proyecto nuevo? ¿algún formulario destructivo usa `confirm()` nativo en
    vez del modal genérico? ¿hay más de una sombra distinta en la app fuera
    de la caja de login (§8.3), o `font-editorial` usado fuera del panel de
    login? ¿aparece el nombre de la app como texto plano en el sidebar o en
    la caja de login habiendo ya un wordmark en imagen? ¿el logo tiene un
    tamaño distinto al de la tabla §7.2 en alguna plantilla? Si alguna
    respuesta es sí, no está terminado.
