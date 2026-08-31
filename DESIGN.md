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

## 6. Iconografía

Una sola librería (Lucide) en todo el proyecto, cargada una vez en el layout
base + `lucide.createIcons()` tras cada render dinámico (incluido dentro de
cualquier `fetch`/refresh periódico, o los iconos inyectados por JS no se
resuelven). Nunca un glifo Unicode crudo (`✓ ✗ ⚠ ▲ ▼`) cuando la librería ya
está cargada — usa `check`, `x`, `triangle-alert`, `chevron-up/down`.

## 7. Accesibilidad (no negociable)

- `:focus-visible` global (ver §4) — nunca `outline-none` sin sustituto.
- Contraste AA mínimo: con la base grafito (`navy-950 #121212`) y texto
  `slate-100`/`slate-400`, y el acento sobre fondo oscuro, ya cumple; si
  cambias el color de marca en otro proyecto, verifica el contraste del
  nuevo acento sobre `#121212` antes de darlo por bueno.
- `prefers-reduced-motion` respetado en cualquier animación de entrada.
- Modal de confirmación propio en vez de `confirm()` nativo del navegador
  (patrón `data-confirm="texto"` en el `<form>`, ver `base.html`) — accesible
  por teclado (Escape cierra, foco gestionado).

## 8. Qué cambia por proyecto vs. qué se mantiene

| Se mantiene igual (sistema) | Se adapta por proyecto |
|---|---|
| Escala grafito §2.A, tokens OKLCH neutros | Color de marca §2.B (+ recalcular `--p`/`--pc`/`--a`/`--ac`) |
| Tipografía (3 fuentes, roles fijos) | Nombre/wordmark, nav items del sidebar |
| `.tnum`, `.eyebrow`, `.btn-brand`, focus-visible, fade-in-up | Textos del pie institucional del sidebar |
| Macros `page_header`/`badge`/`empty_state`/`select_dropdown` | Iconos elegidos por página (siempre Lucide, pero cuáles) |
| Colores semánticos (success/warn/danger/info) | — (no cambian, son universales) |
| Tablas Notion-style, tarjetas sin sombra | Contenido de las tarjetas/tablas |

## 9. Checklist rápido al portar esto a un proyecto nuevo

1. Copia el bloque `tailwind.config` completo (§2.A–2.B) y sustituye solo
   `brand.DEFAULT/soft/dark` por el color de marca del proyecto nuevo.
2. Recalcula `--p`/`--pc`/`--a`/`--ac` en OKLCH para el nuevo color de marca
   (hex → OKLCH); copia el resto del bloque `[data-theme]` tal cual.
3. Copia las utilidades CSS del §4 tal cual, ajustando solo los hex del
   acento en `.eyebrow` y `:focus-visible`.
4. Copia las 4 macros del §5.1–5.4 sin modificar.
5. Antes de dar por cerrado el rediseño, audita: ¿hay dos sistemas de botón
   distintos? ¿un badge con el mismo significado pero dos colores en dos
   páginas? ¿algún glifo Unicode crudo? ¿algún `<p>` de estado vacío suelto
   sin componer? ¿queda algún `<select>` nativo visible (se delata por el
   popup en azul de sistema al abrirlo)? Si alguna respuesta es sí, no está
   terminado.
