"""
Inspecciona un sitio web renderizado con JavaScript (SPAs, React, Next, etc.).

Uso:
    python scripts/inspeccionar_sitio.py https://www.strengthlabcenter.com/agendar
    python scripts/inspeccionar_sitio.py <url> --mostrar        # abre el navegador visible
    python scripts/inspeccionar_sitio.py <url> --espera 5       # segundos extra de espera
    python scripts/inspeccionar_sitio.py <url> --sin-fallback   # no fuerza rutas client-side

Genera:
    static/capturas_referencia/sitio_original.png     Captura de pantalla completa
    scripts/output_renderizado.html                   HTML final ya renderizado
    scripts/estructura_sitio.json                     Clases CSS, textos y formularios
    scripts/estructura_sitio.md                       El mismo informe en Markdown legible

Decisiones de diseño (KISS):
1. La espera principal es `networkidle`; si la página nunca llega a ese estado
   (websockets, polling, animaciones infinitas) se cae a `domcontentloaded` + espera
   fija para no dejar la inspección bloqueada.
2. Fallback SPA: muchas apps (Vite + React Router, TanStack Router…) no tienen rewrites
   en el hosting y sus rutas profundas responden 404 aunque la ruta exista en el bundle.
   Si la URL directa falla, se carga el origen y se navega en el cliente con
   `history.pushState` + evento `popstate`, que es como el router pinta la vista.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as ErrorPlaywright
from playwright.sync_api import TimeoutError as TimeoutPlaywright
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_CAPTURA = BASE_DIR / "static" / "capturas_referencia" / "sitio_original.png"
RUTA_HTML = BASE_DIR / "scripts" / "output_renderizado.html"
RUTA_JSON = BASE_DIR / "scripts" / "estructura_sitio.json"
RUTA_MD = BASE_DIR / "scripts" / "estructura_sitio.md"

ESPERA_NETWORKIDLE_MS = 45_000
ESPERA_MAXIMA_CARGA_MS = 90_000


# ---------------------------------------------------------------------------
# Extracción dentro del navegador
# ---------------------------------------------------------------------------

JS_EXTRAER_ESTRUCTURA = r"""
() => {
  const limpiar = (texto) => (texto || '').replace(/\s+/g, ' ').trim();
  const clasesDe = (el) => (el && typeof el.className === 'string' ? el.className : '');

  // --- Clases CSS en uso -------------------------------------------------
  const contadorClases = {};
  document.querySelectorAll('*').forEach((el) => {
    if (!el.classList) return;
    el.classList.forEach((clase) => {
      contadorClases[clase] = (contadorClases[clase] || 0) + 1;
    });
  });

  // --- Textos visibles ---------------------------------------------------
  const texto = limpiar(document.body ? document.body.innerText : '');

  const titulos = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')]
    .map((el) => ({ etiqueta: el.tagName.toLowerCase(), texto: limpiar(el.innerText) }))
    .filter((t) => t.texto);

  const botones = [...document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"]')]
    .map((el) => ({
      etiqueta: el.tagName.toLowerCase(),
      tipo: el.getAttribute('type') || '',
      texto: limpiar(el.innerText || el.value || ''),
      id: el.id || '',
      clases: clasesDe(el),
      deshabilitado: !!el.disabled,
      datos: Object.fromEntries([...el.attributes]
        .filter((a) => a.name.startsWith('data-'))
        .map((a) => [a.name, a.value])),
    }))
    .filter((b) => b.texto || b.id);

  // Agrupa botones por contenedor: delata calendarios, toggles y grillas
  const grupos = {};
  [...document.querySelectorAll('button')].forEach((el) => {
    const padre = el.parentElement;
    if (!padre) return;
    const clave = `${padre.tagName.toLowerCase()}.${clasesDe(padre)}`;
    if (!grupos[clave]) {
      grupos[clave] = { contenedor: clave, botones: [], total: 0 };
    }
    grupos[clave].total += 1;
    if (grupos[clave].botones.length < 40) {
      grupos[clave].botones.push(limpiar(el.innerText));
    }
  });
  const gruposBotones = Object.values(grupos)
    .filter((g) => g.total >= 2)
    .sort((a, b) => b.total - a.total);

  const enlaces = [...document.querySelectorAll('a[href]')]
    .map((el) => ({ texto: limpiar(el.innerText), href: el.href }))
    .filter((a) => a.texto || a.href);

  // --- Estructura de formularios ----------------------------------------
  const etiquetaDe = (campo) => {
    if (campo.labels && campo.labels.length) {
      return limpiar([...campo.labels].map((l) => l.innerText).join(' '));
    }
    const id = campo.getAttribute('id');
    if (id) {
      const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
      if (label) return limpiar(label.innerText);
    }
    return limpiar(campo.getAttribute('aria-label') || campo.getAttribute('placeholder') || '');
  };

  // Sección a la que pertenece el campo (sube hasta encontrar un encabezado)
  const seccionDe = (campo) => {
    let nodo = campo.parentElement;
    for (let i = 0; i < 6 && nodo; i += 1) {
      const encabezado = nodo.querySelector('h1, h2, h3, h4, h5, h6, legend');
      if (encabezado) {
        const t = limpiar(encabezado.innerText);
        if (t) return t;
      }
      nodo = nodo.parentElement;
    }
    return '';
  };

  const datosDe = (campo) => {
    const datos = {};
    for (const atributo of campo.attributes) {
      if (atributo.name.startsWith('data-') ||
          ['name', 'placeholder', 'autocomplete', 'inputmode', 'pattern', 'minlength',
           'maxlength', 'min', 'max', 'step', 'aria-label', 'aria-required']
            .includes(atributo.name)) {
        datos[atributo.name] = atributo.value;
      }
    }
    return datos;
  };

  const datosCampo = (campo) => {
    const item = {
      etiqueta: campo.tagName.toLowerCase(),
      tipo: campo.getAttribute('type') || '',
      nombre: campo.getAttribute('name') || '',
      id: campo.id || '',
      etiqueta_texto: etiquetaDe(campo),
      seccion: seccionDe(campo),
      obligatorio: campo.required || campo.getAttribute('aria-required') === 'true',
      deshabilitado: !!campo.disabled,
      valor: (campo.type === 'password' || campo.type === 'hidden') ? '' : (campo.value || ''),
      clases: clasesDe(campo),
      atributos: datosDe(campo),
    };
    if (campo.tagName.toLowerCase() === 'select') {
      item.opciones = [...campo.options].map((o) => ({
        valor: o.value,
        texto: limpiar(o.text),
        seleccionado: o.selected,
      }));
    }
    return item;
  };

  const formularios = [...document.querySelectorAll('form')].map((form, indice) => ({
    indice: indice + 1,
    id: form.id || '',
    nombre: form.getAttribute('name') || '',
    accion: form.getAttribute('action') || '',
    metodo: (form.getAttribute('method') || 'get').toLowerCase(),
    clases: clasesDe(form),
    texto: limpiar(form.innerText).slice(0, 2000),
    total_campos: form.querySelectorAll('input, select, textarea').length,
    campos: [...form.querySelectorAll('input, select, textarea')].map(datosCampo),
  }));

  // SPAs sin <form>: los campos viven en divs controlados por React/Vue
  const formulariosVirtuales = [...document.querySelectorAll('[role="form"], [data-testid*="form"], .form, .formulario')]
    .filter((el) => el.tagName.toLowerCase() !== 'form' && el.querySelector('input, select, textarea'))
    .map((el, indice) => ({
      indice: indice + 1,
      id: el.id || '',
      clases: clasesDe(el),
      texto: limpiar(el.innerText).slice(0, 2000),
      total_campos: el.querySelectorAll('input, select, textarea').length,
      campos: [...el.querySelectorAll('input, select, textarea')].map(datosCampo),
    }));

  const camposSueltos = [...document.querySelectorAll('input, select, textarea')]
    .filter((campo) => !campo.closest('form'))
    .map(datosCampo);

  return {
    url_final: location.href,
    titulo: document.title,
    idioma: document.documentElement.lang || '',
    texto_visible: texto,
    titulos: titulos,
    botones: botones,
    grupos_botones: gruposBotones,
    enlaces: enlaces,
    formularios: formularios,
    formularios_virtuales: formulariosVirtuales,
    campos_sueltos: camposSueltos,
    contador_clases: contadorClases,
    totales: {
      elementos: document.querySelectorAll('*').length,
      formularios: formularios.length,
      campos: document.querySelectorAll('input, select, textarea').length,
      botones: botones.length,
      enlaces: enlaces.length,
      imagenes: document.querySelectorAll('img').length,
      iframes: document.querySelectorAll('iframe').length,
      scripts: document.querySelectorAll('script').length,
    },
  };
}
"""


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _log(mensaje: str = "") -> None:
    print(mensaje, flush=True)


def _preparar_consola() -> None:
    """Evita UnicodeEncodeError en consolas de Windows (cp1252)."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _desplazar_pagina(page) -> None:
    """Hace scroll hasta el final para disparar animaciones y carga diferida."""
    alto_previo = 0
    for _ in range(40):
        alto = page.evaluate(
            "() => { window.scrollBy(0, window.innerHeight); return document.body.scrollHeight; }"
        )
        page.wait_for_timeout(250)
        if alto == alto_previo:
            break
        alto_previo = alto
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(600)


def _navegar(page, url: str) -> int | None:
    """Navega esperando networkidle, con caída a domcontentloaded. Devuelve el status HTTP."""
    try:
        respuesta = page.goto(url, wait_until="networkidle", timeout=ESPERA_NETWORKIDLE_MS)
    except TimeoutPlaywright:
        _log(f"   · networkidle no se alcanzó en {ESPERA_NETWORKIDLE_MS // 1000}s, se continúa igual.")
        respuesta = page.goto(url, wait_until="domcontentloaded", timeout=ESPERA_MAXIMA_CARGA_MS)
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except TimeoutPlaywright:
            pass
    return respuesta.status if respuesta else None


def _fallback_spa(page, url: str, espera: float) -> bool:
    """
    Carga el origen y navega en el cliente hasta la ruta pedida.

    Necesario cuando el hosting no reescribe rutas profundas (Vercel devuelve 404)
    pero la ruta sí existe en el bundle del SPA.
    """
    partes = urlparse(url)
    if not partes.path or partes.path == "/":
        return False

    origen = f"{partes.scheme}://{partes.netloc}"
    destino = partes.path + (f"?{partes.query}" if partes.query else "")
    _log(f"   · Fallback SPA: se carga {origen} y se navega en el cliente a {destino}")

    if (_navegar(page, origen) or 0) >= 400:
        _log("   · El origen tampoco responde: no es posible el fallback.")
        return False

    page.wait_for_timeout(1200)
    page.evaluate(
        """(ruta) => {
            history.pushState({}, '', ruta);
            window.dispatchEvent(new PopStateEvent('popstate', { state: {} }));
        }""",
        destino,
    )
    page.wait_for_timeout(1500 + int(espera * 1000))
    return True


def _top_clases(contador: dict[str, int], limite: int = 40) -> list[tuple[str, int]]:
    return sorted(contador.items(), key=lambda par: (-par[1], par[0]))[:limite]


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def _campo_a_linea(campo: dict) -> str:
    partes = [f"`{campo['etiqueta']}`"]
    if campo.get("tipo"):
        partes.append(f"tipo=`{campo['tipo']}`")
    if campo.get("nombre"):
        partes.append(f"name=`{campo['nombre']}`")
    if campo.get("id"):
        partes.append(f"id=`{campo['id']}`")
    if campo.get("etiqueta_texto"):
        partes.append(f'label="{campo["etiqueta_texto"]}"')
    if campo.get("seccion"):
        partes.append(f'sección="{campo["seccion"]}"')
    if campo.get("obligatorio"):
        partes.append("**obligatorio**")
    return " · ".join(partes)


def _construir_markdown(datos: dict, modo_carga: str, url_pedida: str, aviso: str) -> str:
    totales = datos["totales"]
    lineas: list[str] = []
    a = lineas.append

    a("# Inspección del sitio renderizado")
    a("")
    a(f"- **URL solicitada**: {url_pedida}")
    a(f"- **URL final**: {datos['url_final']}")
    a(f"- **Título**: {datos['titulo']}")
    a(f"- **Idioma**: {datos['idioma'] or '(sin declarar)'}")
    a(f"- **Modo de espera**: {modo_carga}")
    a(f"- **Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if aviso:
        a(f"- **Aviso**: {aviso}")
    a("")
    a("## Totales")
    a("")
    a("| Métrica | Valor |")
    a("| --- | --- |")
    for clave, valor in totales.items():
        a(f"| {clave} | {valor} |")
    a("")
    a(f"## Clases CSS en uso ({len(datos['contador_clases'])} distintas)")
    a("")
    a("Las más frecuentes:")
    a("")
    a("| Clase | Usos |")
    a("| --- | --- |")
    for clase, usos in _top_clases(datos["contador_clases"]):
        a(f"| `{clase}` | {usos} |")
    a("")
    a("## Jerarquía de títulos")
    a("")
    if datos["titulos"]:
        for titulo in datos["titulos"]:
            a(f"- `{titulo['etiqueta']}` — {titulo['texto']}")
    else:
        a("_Sin títulos._")
    a("")

    a("## Formularios (`<form>`)")
    a("")
    if datos["formularios"]:
        for form in datos["formularios"]:
            a(f"### Formulario {form['indice']}")
            a("")
            a(f"- **action**: `{form['accion'] or '(vacío)'}`")
            a(f"- **method**: `{form['metodo']}`")
            a(f"- **id / name**: `{form['id'] or '-'}` / `{form['nombre'] or '-'}`")
            a(f"- **clases**: `{form['clases'] or '-'}`")
            a(f"- **campos**: {form['total_campos']}")
            a("")
            if form["campos"]:
                a("| Campo | Tipo | name | id | label | Obligatorio |")
                a("| --- | --- | --- | --- | --- | --- |")
                for campo in form["campos"]:
                    a(
                        f"| `{campo['etiqueta']}` | `{campo['tipo']}` | `{campo['nombre']}` | "
                        f"`{campo['id']}` | {campo['etiqueta_texto'] or '-'} | "
                        f"{'sí' if campo['obligatorio'] else 'no'} |"
                    )
                a("")
                for campo in form["campos"]:
                    if campo.get("opciones"):
                        a(f"Opciones de `{campo['nombre'] or campo['id']}`:")
                        for opcion in campo["opciones"]:
                            marca = " (por defecto)" if opcion["seleccionado"] else ""
                            a(f"- `{opcion['valor']}` → {opcion['texto']}{marca}")
                        a("")
    else:
        a("_No hay elementos `<form>` en el DOM._")
        a("")

    if datos["formularios_virtuales"]:
        a("### Contenedores tipo formulario (sin `<form>`)")
        a("")
        for form in datos["formularios_virtuales"]:
            a(f"- `#{form['id'] or '-'}` · clases `{form['clases'] or '-'}` · {form['total_campos']} campos")
            for campo in form["campos"]:
                a(f"  - {_campo_a_linea(campo)}")
        a("")

    if datos["campos_sueltos"]:
        a("### Campos fuera de un `<form>` (típico de SPAs)")
        a("")
        secciones: dict[str, list[dict]] = {}
        for campo in datos["campos_sueltos"]:
            secciones.setdefault(campo.get("seccion") or "(sin sección)", []).append(campo)
        for seccion, campos in secciones.items():
            a(f"**{seccion}**")
            a("")
            a("| Campo | Tipo | name | placeholder | Obligatorio | Clases |")
            a("| --- | --- | --- | --- | --- | --- |")
            for campo in campos:
                a(
                    f"| `{campo['etiqueta']}` | `{campo['tipo'] or '-'}` | `{campo['nombre'] or '-'}` | "
                    f"{campo['atributos'].get('placeholder', '-')} | "
                    f"{'sí' if campo['obligatorio'] else 'no'} | `{campo['clases'] or '-'}` |"
                )
            a("")

    a("## Grupos de botones (calendarios, toggles, grillas)")
    a("")
    if datos["grupos_botones"]:
        for grupo in datos["grupos_botones"]:
            a(f"- **{grupo['total']} botones** en `{grupo['contenedor'] or '(sin clase)'}`: "
              + ", ".join(b for b in grupo["botones"] if b)[:300])
    else:
        a("_Sin grupos._")
    a("")

    a("## Botones")
    a("")
    if datos["botones"]:
        a("| Texto | etiqueta | type | id | clases |")
        a("| --- | --- | --- | --- | --- |")
        for boton in datos["botones"]:
            a(
                f"| {boton['texto'] or '(sin texto)'} | `{boton['etiqueta']}` | "
                f"`{boton['tipo'] or '-'}` | `{boton['id']}` | `{boton['clases']}` |"
            )
    else:
        a("_Sin botones._")
    a("")

    a("## Texto visible (primeros 3000 caracteres)")
    a("")
    a("```text")
    a(datos["texto_visible"][:3000])
    a("```")
    a("")
    return "\n".join(lineas)


def _imprimir_formularios(datos: dict) -> None:
    """Resumen de formularios en consola."""
    _log("")
    _log("=" * 72)
    _log("ESTRUCTURA DE FORMULARIOS")
    _log("=" * 72)

    if not datos["formularios"]:
        _log("No hay elementos <form> en el DOM renderizado.")

    for form in datos["formularios"]:
        _log("")
        _log(f"Formulario {form['indice']}")
        _log(f"  action : {form['accion'] or '(vacío)'}")
        _log(f"  method : {form['metodo']}")
        _log(f"  id     : {form['id'] or '-'}")
        _log(f"  name   : {form['nombre'] or '-'}")
        _log(f"  clases : {form['clases'] or '-'}")
        _log(f"  campos : {form['total_campos']}")
        if form["campos"]:
            _log("")
            for campo in form["campos"]:
                _log(f"    - {_campo_a_linea(campo)}")
                for opcion in campo.get("opciones", []):
                    marca = " (por defecto)" if opcion["seleccionado"] else ""
                    _log(f"        · {opcion['valor']} → {opcion['texto']}{marca}")
        if form["texto"]:
            _log("")
            _log(f"  texto  : {form['texto'][:400]}")

    for form in datos["formularios_virtuales"]:
        _log("")
        _log(f"Formulario virtual #{form['id'] or '-'} · clases {form['clases'] or '-'} · {form['total_campos']} campos")
        for campo in form["campos"]:
            _log(f"    - {_campo_a_linea(campo)}")

    if datos["campos_sueltos"]:
        _log("")
        _log(f"Campos fuera de un <form>: {len(datos['campos_sueltos'])}")
        seccion_actual = None
        for campo in datos["campos_sueltos"]:
            if campo["seccion"] != seccion_actual:
                seccion_actual = campo["seccion"]
                _log(f"  [{seccion_actual or 'sin sección'}]")
            extra = campo["atributos"].get("placeholder") or campo["etiqueta_texto"] or ""
            _log(f"    - {_campo_a_linea(campo)}" + (f' · placeholder="{extra}"' if extra else ""))

    if datos["grupos_botones"]:
        _log("")
        _log("Grupos de botones (calendarios / toggles):")
        for grupo in datos["grupos_botones"]:
            textos = ", ".join(b for b in grupo["botones"] if b)
            _log(f"  - {grupo['total']} botones en {grupo['contenedor'] or '(sin clase)'}")
            if textos:
                _log(f"      {textos[:200]}")


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def inspeccionar(url: str, mostrar: bool, espera: float, usar_fallback: bool) -> int:
    RUTA_CAPTURA.parent.mkdir(parents=True, exist_ok=True)
    RUTA_HTML.parent.mkdir(parents=True, exist_ok=True)

    _log(f"→ Inspeccionando: {url}")
    if mostrar:
        _log("  (navegador visible: --mostrar)")

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=not mostrar)
        contexto = navegador.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
            locale="es-SV",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
            ),
        )
        page = contexto.new_page()
        page.set_default_timeout(ESPERA_MAXIMA_CARGA_MS)

        try:
            estado = _navegar(page, url)
            modo_carga = "networkidle"
            aviso = ""

            if estado is not None and estado >= 400:
                aviso = f"la URL respondió HTTP {estado}"
                if usar_fallback and _fallback_spa(page, url, espera):
                    modo_carga = "networkidle + fallback SPA (pushState/popstate)"
                    aviso += " y se resolvió la ruta en el cliente"
                else:
                    _log(f"   · Aviso: la URL respondió HTTP {estado}. Se inspecciona lo que haya cargado.")
            else:
                page.wait_for_timeout(int(espera * 1000))

            # Deja respirar a las animaciones de entrada y a la carga diferida
            _desplazar_pagina(page)

            _log("  · Guardando captura de pantalla completa…")
            page.screenshot(path=str(RUTA_CAPTURA), full_page=True)

            _log("  · Guardando HTML renderizado…")
            html = page.content()
            RUTA_HTML.write_text(html, encoding="utf-8")

            _log("  · Extrayendo clases, textos y formularios…")
            datos = page.evaluate(JS_EXTRAER_ESTRUCTURA)

            informe = {
                "url_pedida": url,
                "estado_http": estado,
                "modo_carga": modo_carga,
                "aviso": aviso,
                "inspeccionado_en": datetime.now().isoformat(timespec="seconds"),
                **datos,
                "clases_ordenadas": _top_clases(datos["contador_clases"], limite=200),
            }
            RUTA_JSON.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
            RUTA_MD.write_text(
                _construir_markdown(datos, modo_carga, url, aviso),
                encoding="utf-8",
            )

            _imprimir_formularios(datos)

            _log("")
            _log("-" * 72)
            _log("RESUMEN")
            _log("-" * 72)
            _log(f"  URL final     : {datos['url_final']}")
            _log(f"  Título        : {datos['titulo']}")
            _log(f"  Estado HTTP   : {estado if estado is not None else '(desconocido)'}")
            _log(f"  Modo de carga : {modo_carga}")
            if aviso:
                _log(f"  Aviso         : {aviso}")
            _log(f"  Elementos     : {datos['totales']['elementos']}")
            _log(f"  Formularios   : {datos['totales']['formularios']}")
            _log(f"  Campos        : {datos['totales']['campos']}")
            _log(f"  Botones       : {datos['totales']['botones']}")
            _log(f"  Clases CSS    : {len(datos['contador_clases'])} distintas")
            _log("")
            _log("Archivos generados:")
            _log(f"  · {RUTA_CAPTURA}")
            _log(f"  · {RUTA_HTML}")
            _log(f"  · {RUTA_JSON}")
            _log(f"  · {RUTA_MD}")
            return 0

        except ErrorPlaywright as error:
            _log("")
            _log(f"ERROR de Playwright: {error}")
            return 1
        finally:
            contexto.close()
            navegador.close()


def main() -> int:
    _preparar_consola()
    parser = argparse.ArgumentParser(
        description="Inspecciona una web renderizada con JavaScript y guarda captura, HTML y estructura.",
    )
    parser.add_argument("url", help="URL a inspeccionar (ej. https://www.strengthlabcenter.com/agendar)")
    parser.add_argument("--mostrar", action="store_true", help="Muestra el navegador en pantalla")
    parser.add_argument(
        "--espera",
        type=float,
        default=2.0,
        help="Segundos extra de espera tras la carga (por defecto 2.0)",
    )
    parser.add_argument(
        "--sin-fallback",
        action="store_true",
        help="No intenta resolver en el cliente las rutas que responden 404",
    )
    args = parser.parse_args()

    esquema = urlparse(args.url)
    if esquema.scheme not in ("http", "https"):
        _log("La URL debe comenzar con http:// o https://")
        return 2

    return inspeccionar(args.url, args.mostrar, args.espera, not args.sin_fallback)


if __name__ == "__main__":
    raise SystemExit(main())
