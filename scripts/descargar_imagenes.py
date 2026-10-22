"""Descarga las imágenes de un sitio renderizado con JavaScript.

Uso:
    python scripts/descargar_imagenes.py
    python scripts/descargar_imagenes.py https://www.strengthlabcenter.com/
    python scripts/descargar_imagenes.py <url> --salida media/planes
    python scripts/descargar_imagenes.py <url> --mostrar   # navegador visible

Extrae las imágenes de los elementos `<img>` (incluido `srcset`), los
`background-image` calculados por el navegador y las metas `og:image` /
`twitter:image`. Las guarda en `media/planes/` con nombres limpios (sin el hash
de Vite) para poder asociarlas a los planes con `poblar_contenido`.

Decisiones de diseño (KISS):
1. La extracción se hace con Playwright porque el sitio de referencia es una
   SPA de React: el HTML crudo no trae las imágenes.
2. Se espera `networkidle`, pero si la página nunca llega a ese estado se cae a
   `domcontentloaded` + una espera fija, igual que `inspeccionar_sitio.py`.
3. La descarga usa el `APIRequestContext` del navegador para reutilizar cookies
   y cabeceras de la sesión.
4. Es idempotente: si el archivo ya existe con el mismo tamaño, se omite.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from playwright.sync_api import Error as ErrorPlaywright
from playwright.sync_api import TimeoutError as TimeoutPlaywright
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
SALIDA_POR_DEFECTO = BASE_DIR / "media" / "planes"
URL_POR_DEFECTO = "https://www.strengthlabcenter.com/"

ESPERA_NETWORKIDLE_MS = 45_000
ESPERA_MAXIMA_CARGA_MS = 90_000
ESPERA_FIJA_MS = 3_000

EXTENSIONES_VALIDAS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".bmp", ".ico",
}

# Extensiones que no aportan nada al catálogo de planes.
EXTENSIONES_IGNORADAS = {".ico"}

# Vite añade un hash de 8 caracteres al final del nombre: plan-elite-Cl0brlr9.jpg
PATRON_HASH = re.compile(r"-(?P<hash>[A-Za-z0-9_-]{8})$")

JS_EXTRAER_IMAGENES = r"""
() => {
  const urls = new Set();

  const agregar = (valor) => {
    if (!valor) return;
    if (valor.startsWith('data:') || valor.startsWith('blob:')) return;
    urls.add(valor);
  };

  const agregarSrcset = (srcset) => {
    if (!srcset) return;
    srcset.split(',').forEach((parte) => {
      const url = parte.trim().split(/\s+/)[0];
      agregar(url);
    });
  };

  document.querySelectorAll('img').forEach((img) => {
    // currentSrc es la variante que el navegador eligió del srcset.
    agregar(img.currentSrc || img.src);
    agregar(img.getAttribute('src'));
    agregarSrcset(img.getAttribute('srcset'));
  });

  // Backgrounds aplicados por CSS (incluye los de Tailwind con style inline).
  document.querySelectorAll('*').forEach((el) => {
    const fondo = getComputedStyle(el).backgroundImage;
    if (!fondo || fondo === 'none') return;
    const coincidencias = fondo.matchAll(/url\((['"]?)(.*?)\1\)/g);
    for (const coincidencia of coincidencias) {
      agregar(coincidencia[2]);
    }
  });

  ['og:image', 'twitter:image'].forEach((nombre) => {
    document.querySelectorAll(
      `meta[property="${nombre}"], meta[name="${nombre}"]`
    ).forEach((meta) => agregar(meta.content));
  });

  return [...urls];
}
"""


def _log(mensaje: str = "") -> None:
    print(mensaje, flush=True)


def _nombre_limpio(url: str) -> str:
    """Deriva un nombre de archivo estable y legible desde la URL."""
    ruta = unquote(urlparse(url).path)
    nombre = Path(ruta).name
    if not nombre:
        nombre = "imagen"

    tallo, extension = Path(nombre).stem, Path(nombre).suffix.lower()
    if extension not in EXTENSIONES_VALIDAS:
        extension = ".jpg"

    # Quita el hash de compilación de Vite (si queda al menos un guion antes).
    if "-" in tallo:
        tallo = PATRON_HASH.sub("", tallo)

    # Sin acentos ni caracteres problemáticos para el sistema de archivos.
    tallo = unicodedata.normalize("NFKD", tallo)
    tallo = "".join(c for c in tallo if not unicodedata.combining(c))
    tallo = re.sub(r"[^A-Za-z0-9._-]+", "-", tallo).strip("-._").lower()
    if not tallo:
        tallo = "imagen"

    return f"{tallo}{extension}"


def _ruta_disponible(carpeta: Path, nombre: str, contenido: bytes) -> Path:
    """Evita pisar archivos distintos con el mismo nombre."""
    destino = carpeta / nombre
    if not destino.exists():
        return destino
    if destino.stat().st_size == len(contenido):
        return destino

    tallo, extension = destino.stem, destino.suffix
    indice = 2
    while True:
        candidato = carpeta / f"{tallo}-{indice}{extension}"
        if not candidato.exists():
            return candidato
        if candidato.stat().st_size == len(contenido):
            return candidato
        indice += 1


def _extraer_urls(pagina, url: str, espera: float) -> tuple[list[str], str]:
    """Carga el sitio y devuelve las URLs de imagen detectadas."""
    try:
        pagina.goto(url, wait_until="networkidle", timeout=ESPERA_NETWORKIDLE_MS)
    except (TimeoutPlaywright, ErrorPlaywright):
        _log("  · networkidle no alcanzado; se usa domcontentloaded + espera fija.")
        pagina.goto(url, wait_until="domcontentloaded", timeout=ESPERA_MAXIMA_CARGA_MS)

    if espera:
        pagina.wait_for_timeout(int(espera * 1000))
    else:
        pagina.wait_for_timeout(ESPERA_FIJA_MS)

    return pagina.evaluate(JS_EXTRAER_IMAGENES), pagina.url


def descargar(url: str, salida: Path, mostrar: bool, espera: float) -> int:
    salida.mkdir(parents=True, exist_ok=True)

    _log(f"→ Abriendo: {url}")
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
        pagina = contexto.new_page()
        pagina.set_default_timeout(ESPERA_MAXIMA_CARGA_MS)

        urls, url_final = _extraer_urls(pagina, url, espera)
        urls = [urljoin(url_final, u) for u in urls]
        urls = list(dict.fromkeys(urls))
        _log(f"  · {len(urls)} URLs de imagen detectadas.")

        descargadas = 0
        omitidas = 0
        fallidas = 0

        for url_imagen in urls:
            extension = Path(urlparse(url_imagen).path).suffix.lower()
            if extension in EXTENSIONES_IGNORADAS:
                continue

            nombre = _nombre_limpio(url_imagen)
            try:
                respuesta = contexto.request.get(url_imagen, timeout=30_000)
                if not respuesta.ok:
                    _log(f"  ✗ HTTP {respuesta.status}: {url_imagen}")
                    fallidas += 1
                    continue
                contenido = respuesta.body()
            except ErrorPlaywright as error:
                _log(f"  ✗ {error}: {url_imagen}")
                fallidas += 1
                continue

            if not contenido:
                _log(f"  ✗ respuesta vacía: {url_imagen}")
                fallidas += 1
                continue

            destino = _ruta_disponible(salida, nombre, contenido)
            if destino.exists() and destino.stat().st_size == len(contenido):
                omitidas += 1
                _log(f"  = {destino.name} (ya existía)")
                continue

            destino.write_bytes(contenido)
            descargadas += 1
            _log(f"  ✓ {destino.name} ({len(contenido) // 1024} KB)")

        navegador.close()

    _log("")
    _log(
        f"Resumen: {descargadas} descargadas, {omitidas} ya existentes, "
        f"{fallidas} fallidas. Carpeta: {salida}"
    )
    return 0 if fallidas == 0 else 1


def main() -> int:
    # La consola de Windows usa cp1252 por defecto y no puede imprimir “→” ni
    # “✓”; con UTF-8 el script no se cae a mitad de la descarga.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Descarga las imágenes de un sitio renderizado con JavaScript."
    )
    parser.add_argument("url", nargs="?", default=URL_POR_DEFECTO, help="URL del sitio.")
    parser.add_argument(
        "--salida",
        type=Path,
        default=SALIDA_POR_DEFECTO,
        help="Carpeta destino (por defecto: media/planes).",
    )
    parser.add_argument("--mostrar", action="store_true", help="Abre el navegador visible.")
    parser.add_argument(
        "--espera",
        type=float,
        default=0,
        help="Segundos extra de espera antes de extraer (por defecto: 3).",
    )
    args = parser.parse_args()

    return descargar(args.url, args.salida, args.mostrar, args.espera)


if __name__ == "__main__":
    sys.exit(main())
