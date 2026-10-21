# Directivas del Agente - Strength Lab Web & Admin

## 1. Estado actual

- **Landing pública implementada** (raíz `/`): estética oscura con Tailwind vía CDN, hero, grid de planes dinámico, sección Ubicación/Horarios con mapa embebido y **modal de reserva** con **POST normal** a `/reserva/` usando `target="_blank"`. No hay `fetch`, ni JSON, ni `window.open('about:blank')`, ni tarjeta de éxito intermedia: Django responde con `HttpResponseRedirect` a WhatsApp en la pestaña nueva, mientras la pestaña del sitio muestra la confirmación **"¡Solicitud enviada!"**.
- **Datos iniciales**: comando `python manage.py poblar_contenido` (idempotente) puebla los 4 planes reales (Élite $200/20 ses. popular, Progreso $150/15, Inicial $100/10, Básico $45) y la configuración del sitio (horarios L-V 5am-10pm, Sáb 7am-3pm, Merliot, WhatsApp +50378538605).
- **Modelos y reservas**: `ConfiguracionSitio` (singleton, incluye `mensaje_predeterminado_whatsapp`, `hora_manana` y `hora_tarde`), `PlanEntrenamiento`, `FormularioReserva`/`FormularioAgendar` y `google_services.py` (Sheets + Calendar). Migraciones `0002` y `0003` aplicadas y `manage.py check` en verde.
- **Página dedicada `/agendar/`** (`apps/reservas/urls_agendar.py` + `views.pagina_agendar` + `templates/reservas/agendar_pagina.html`): réplica de la estructura del sitio de referencia (título "AGENDA TU DÍA DE PRUEBA", sección TUS DATOS, calendario mensual propio, toggle MAÑANA/TARDE y botón "CONFIRMAR POR WHATSAPP") pero **con backend real**: POST normal con `target="_blank"` a `/agendar/`, validación completa, lead a Google Sheets y evento en Calendar. Es una ruta **independiente** del modal y de `/reserva/`; ambas conviven en la navegación (enlace "Agendar cita" y botón "Día Gratis").
  - `FormularioAgendar` valida nombre (sin dígitos), correo, `codigo_pais` (choices), teléfono local (7–12 dígitos, quita espacios/guiones/puntos/paréntesis), fecha (no pasada, no domingo, máximo 90 días) y horario (`manana`/`tarde`).
  - `pagina_agendar` traduce el bloque a hora exacta: `manana` → `ConfiguracionSitio.hora_manana` (09:00 por defecto) y `tarde` → `hora_tarde` (16:00). En Sheets se escribe la etiqueta "Mañana"/"Tarde" (`hora_etiqueta`); en Calendar, la hora exacta.
  - La fecha y el horario viajan en **inputs ocultos** que llena JavaScript; por eso usan `HiddenInputSinRequired` (un `required` en un campo oculto bloquea el submit sin mensaje). El cliente valida antes de enviar y el servidor vuelve a validar siempre.
  - Días cerrados y ventana de reserva se definen en `forms.py` (`DIAS_CERRADOS = (6,)` = domingo, `DIAS_MAXIMOS_RESERVA = 90`) y el calendario JS recibe `DIAS_MAXIMOS` desde el contexto: si cambia uno, cambiar el otro.
- **Arquitectura de leads**: los leads de pruebas gratis **NO se guardan en la base de datos** (alojamiento gratuito en PythonAnywhere con cuota de BD limitada); se envían 100% a Google Sheets y se redirige al usuario a WhatsApp.
- **Selector de código de país**: `FormularioReserva` tiene `codigo_pais` (`ChoiceField`, constantes `CODIGOS_PAIS` en `forms.py`, +503 El Salvador por defecto) y `telefono` (solo dígitos locales, validado en `clean_telefono`); la vista `reserva_dia_gratis` concatena `f"{codigo_pais}{telefono}"` (ej. `+50378538605`) antes de pasarlo a Sheets, Calendar y WhatsApp (incluido en el mensaje prellenado).
- **Integraciones verificadas de punta a punta en local**: un POST real a `/reserva/` (cliente de pruebas de Django) escribe la fila en Google Sheets y crea el evento en Calendar. Causas del fallo original corregidas: (1) `fecha_visita`/`hora_visita` llegaban como objetos `date`/`time` y no como strings, (2) la cuenta de servicio no puede invitar asistentes en Calendar (se reintenta sin invitados). Ver sección 4.
- **Diagnóstico de Google**: comando `python manage.py probar_google` (`apps/integraciones/management/commands/`), con flags `--sin-escribir` (solo lectura) y `--conservar-evento`; imprime traceback completo por sección (credenciales → config → Sheets → Calendar). **Hallazgo**: en local todo funciona (credenciales, hoja `Hoja 1`, calendario "Strength Lab Citas"); si en producción no se registran leads, la causa es ambiental: falta `credentials/google_service_account.json` en el servidor (va en `.gitignore`, no viaja con el código) o la `ConfiguracionSitio` de la BD de producción no tiene los IDs.
- **Script de inspección con Playwright** (`scripts/inspeccionar_sitio.py`): recibe una URL, abre Chromium, espera `networkidle`, guarda la captura completa en `static/capturas_referencia/sitio_original.png`, el HTML renderizado en `scripts/output_renderizado.html` y la estructura (clases CSS, textos, botones, grupos de botones y formularios) en `scripts/estructura_sitio.json` + `.md`. Dependencia `playwright==1.64.0` fijada en `requirements.txt`; requiere `playwright install chromium` una sola vez.
- **Hallazgo sobre el sitio de referencia**: `https://www.strengthlabcenter.com/agendar` responde **HTTP 404** (SPA de Vite en Vercel sin rewrites de rutas profundas). La ruta sí existe en el bundle, así que el script hace **fallback SPA**: carga el origen y navega en el cliente con `history.pushState` + `popstate`. La página `/agendar` **no usa `<form>`**: tres `input` controlados por React (`nombre`, `correo`, `telefono`), calendario propio de `button`, toggle `MAÑANA`/`TARDE` y un botón **CONFIRMAR POR WHATSAPP** que solo abre `api.whatsapp.com` con el mensaje prellenado (sin validación, sin backend y sin guardar el lead). El número que usa producción es `50375093445`, distinto del `numero_whatsapp` configurado en nuestra BD.
- Dependencias instaladas y fijadas en `requirements.txt`; entorno virtual en `.venv`.
- Otras decisiones: `python-dotenv` para cargar `.env`, `LANGUAGE_CODE='es'`, `TIME_ZONE='America/El_Salvador'`, apps registradas como `apps.<nombre>` (requiere `name='apps.<nombre>'` en cada `AppConfig`).

## 2. Rol, Principios y Flujo de Trabajo

- Actúa como desarrollador backend/fullstack senior con **Python 3.12+ y Django 5+**.
- **Todo en español**: código, comentarios, nombres de variables, commits y documentación técnica.
- **KISS**: prefiere la solución nativa de Django antes de instalar paquetes externos; evita sobreingeniería.

### ⚠️ Regla Obligatoria de Sincronización Continua

Tras completar cualquier implementación, refactorización o cambio estructural:

1. **Actualizar `README.md`**: estado actual del proyecto, dependencias nuevas en `requirements.txt`, variables de entorno requeridas en `.env`, comandos para migrar/correr el servidor y cómo probar la funcionalidad agregada.
2. **Actualizar `AGENTS.md`**: nuevas decisiones de diseño, módulos añadidos al mapa de arquitectura y tareas pendientes o completadas.
3. No des por finalizada una tarea sin verificar que ambos documentos estén al día.

---

## 3. Estructura del Proyecto

```text
strengthlab/
├── manage.py
├── core/                        # settings.py, urls.py, wsgi.py, asgi.py
├── apps/
│   ├── __init__.py              # obligatorio: hace de apps un paquete
│   ├── configuracion/           # singleton ConfiguracionSitio (admin)
│   ├── planes/                  # PlanEntrenamiento + vista index (landing)
│   ├── reservas/                # FormularioReserva (forms.Form, SIN modelo) + vista
│   └── integraciones/           # google_services.py (Sheets y Calendar)
├── templates/                   # base.html, index.html + reservas/ (modal y agendar_pagina)
├── static/                      # estáticos globales (STATICFILES_DIRS)
│   └── capturas_referencia/     # sitio_original.png (captura de referencia)
├── scripts/                     # utilidades de desarrollo (inspeccionar_sitio.py)
├── media/                       # subidas del admin (fotos, banners)
├── credentials/                 # google_service_account.json (ignorado en git)
├── .env / .env.example
├── README.md
└── requirements.txt
```

- Las apps viven bajo el paquete `apps/`, así que cada `AppConfig` debe declarar `name = 'apps.<nombre>'` (no `'<nombre>'`), o Django falla al arrancar.

---

## 4. Restricciones del dominio que un agente no debe violar

- **`ConfiguracionSitio` es un singleton** (forzado en `save()` con pk=1, acceso vía `obtener_configuracion()`): nombre/slogan/dirección/horarios del gimnasio, `numero_whatsapp`, `correo_notificaciones`, `mensaje_predeterminado_whatsapp`, `google_calendar_id`, `google_sheets_spreadsheet_id`, `hora_manana` y `hora_tarde`.
  - `google_calendar_id` y `google_sheets_spreadsheet_id` usan `max_length=255` **a propósito**: los IDs de Google miden mucho más de 100 caracteres; no reducir ese tamaño.
  - `hora_manana`/`hora_tarde` (TimeField, 09:00 y 16:00 por defecto) definen la **hora exacta** del evento de Calendar para los bloques de `/agendar/`; se editan en el admin, nunca se hardcodean en la vista.
- **`apps.reservas` NO tiene modelo ni migraciones**: los leads de pruebas gratis se guardan **100% en Google Sheets** (decisión de arquitectura por la cuota de BD de PythonAnywhere). Usar `FormularioReserva`/`FormularioAgendar` (`forms.Form`, nunca `ModelForm`) y **no agregar** un modelo de reservas sin consultar antes al usuario.
- **Flujo de reserva (sin AJAX)**: el modal hace un **POST normal** a `/reserva/` con `target="_blank"`. La vista procesa el formulario, construye la URL de WhatsApp, lanza Google en un hilo y responde `HttpResponseRedirect(url_whatsapp)`. La pestaña nueva abre WhatsApp; la pestaña del sitio solo muestra la confirmación de envío. No volver a introducir `fetch`, `JsonResponse`, `X-Requested-With` ni `window.open`.
  - La página `/agendar/` sigue el **mismo patrón** (POST normal con `target="_blank"` a `/agendar/`, sin AJAX) pero con su propio formulario y su propio redirect. Es la versión "completa" del flujo; el modal sigue siendo el acceso rápido de la landing. La navegación de `base.html` expone las dos opciones: el enlace **"Agendar cita"** va a la página y el botón **"Día Gratis"** abre el modal (`data-abrir-reserva`; el modal hace `preventDefault()` y, sin JS, el enlace navega a `/agendar/`).
  - **El mensaje de WhatsApp es configurable** en `ConfiguracionSitio.mensaje_predeterminado_whatsapp` con las variables `{nombre}`, `{fecha}` (`dd/mm/aaaa`), `{hora}` (`HH:MM`), `{correo}` y `{telefono}` (con código de país). Si el campo está vacío o la plantilla es inválida, se usa `MENSAJE_WHATSAPP_POR_DEFECTO` de `apps/configuracion/models.py`.
    - En `/agendar/` la variable `{hora}` llega como `09:00 (mañana)` para que el mensaje conserve el bloque elegido.
  - **Anti double-submit**: el script mínimo del modal deshabilita el botón en el evento `submit` y muestra la confirmación en la pestaña del sitio. No hay bandera `enviando` ni restauración tras error porque la navegación ocurre en otra pestaña.
  - En `/agendar/`, si el POST falla la validación, la página con los errores se muestra en la **pestaña nueva** (status 400) mientras la original conserva la confirmación; es la misma concesión del modal y está documentada en el texto de la confirmación.
- **Frontend**: Tailwind vía **Play CDN** en `base.html` (decisión KISS, sin paso de build) + Google Fonts (Anton/Montserrat). Colores: `antracita #0d0d0f`, `acento #ef4444`, `acento_naranja #f97316`. El modal está en `templates/reservas/modal_reserva.html` y usa `data-abrir-reserva` / `data-cerrar-reserva`.
- **Comando `poblar_contenido`** (`apps/planes/management/commands/`): idempotente, usa `update_or_create`; puebla los 4 planes y la configuración inicial. Ejecutar tras `migrate` en entornos nuevos.
- **Integraciones Google en `apps/integraciones/google_services.py`**:
  1. `registrar_en_google_sheets(datos, spreadsheet_id)`: fila `[Fecha solicitud, Nombre, Teléfono, Correo, Fecha Cita, Hora Cita, Notas]`. El append usa **`valueInputOption='RAW'`** a propósito: con `USER_ENTERED` el `+` inicial del teléfono (`+50378538605`) se interpretaba como fórmula y Sheets guardaba `50378538605` sin el signo. No cambiar a `USER_ENTERED` sin contemplar eso.
     - Si `datos` trae `hora_etiqueta`, esa etiqueta (`Mañana`/`Tarde`) se escribe en la columna **Hora Cita** en lugar de la hora exacta. Solo la usa `/agendar/`; el modal y `/reserva/` siguen enviando `HH:MM`.
  2. `agendar_en_google_calendar(datos, calendar_id, correo_notificaciones)`: evento de 1 hora. Intenta invitar al cliente y al correo del gimnasio con `sendUpdates='all'`, pero **las cuentas de servicio no pueden invitar asistentes sin Domain-Wide Delegation** (error `403 forbiddenForServiceAccounts`); por eso, ante ese 403 se reintenta el evento **sin invitados** (`sendUpdates='none'`) en vez de fallar. El cliente confirma igual por WhatsApp.
  - **Las fechas deben llegar como strings** `YYYY-MM-DD` y `HH:MM`: el cliente de Google serializa el body a JSON (los objetos `date`/`time` de `cleaned_data` lanzan `TypeError: Object of type date is not JSON serializable`) y Calendar parsea con `strptime` (un objeto `time` daría `10:00:00`). La vista las normaliza con `strftime` y `google_services` usa los helpers `_formatear_fecha`/`_formatear_hora` y `datetime.combine` como defensa.
  - **Los IDs de Google se leen de la BD**, nunca de `.env`: la vista usa `ConfiguracionSitio.obtener_configuracion()` y loguea `[RESERVA WEB] Sheets ID/Calendar ID`.
  - **La sincronización corre en un hilo en segundo plano** (`threading.Thread(..., daemon=True)` en `apps/reservas/views.py`) para que el `HttpResponseRedirect` a WhatsApp no espere a Google. Al hilo se le pasan solo strings (`datos_google`), nunca la instancia del modelo ni la conexión a BD. `_sincronizar_google` envuelve ambas llamadas en un `try/except` con `logger.exception`.
  - `RUTA_CREDENCIALES = settings.BASE_DIR / 'credentials' / 'google_service_account.json'`; los `except` imprimen `traceback.print_exc()` para ver el error en la terminal de `runserver`.
  - El comando `manage.py probar_google` (en `apps/integraciones/management/commands/`) replica estas dos operaciones con datos de prueba para diagnosticar el entorno de producción.
  - Autenticación por cuenta de servicio (`credentials/google_service_account.json`); la acción de exportar reservas a `.xlsx` desde el admin **quedó fuera del alcance** (sin registros locales no hay nada que exportar).
- **Logging visible en runserver**: `core/settings.py` define un `LOGGING` con handler de consola para el logger `apps` (nivel INFO). Sin esa sección, Django solo muestra el logger `django` y los `logger.info`/`logger.warning` de nuestras apps (incluidos los `[RESERVA WEB]` y los tracebacks defensivos) no aparecen en la terminal.
- **Manejo defensivo obligatorio**: si Google falla (cuotas, red, sin credenciales), cada función registra un `logger.warning` y devuelve `False` sin lanzar excepciones; la redirección a WhatsApp **siempre** debe ocurrir.
- `credentials/google_service_account.json` jamás se commitea (ya está en `.gitignore`).
- **`scripts/inspeccionar_sitio.py` es solo de diagnóstico**: no forma parte del sitio, no se importa desde las apps y no debe tocar el flujo de reserva. Sus artefactos (`scripts/output_renderizado.html`, `scripts/estructura_sitio.json`, `scripts/estructura_sitio.md`) están en `.gitignore`; **sí** se conserva `static/capturas_referencia/sitio_original.png` como referencia visual.
  - Fallback SPA: si la URL responde `>= 400`, el script carga el origen y navega en el cliente (`history.pushState` + `popstate`). Es necesario porque el hosting del sitio de referencia no reescribe rutas profundas; no eliminar ese fallback sin verificar que la URL directa devuelve 200.
  - `playwright install chromium` descarga el navegador en `%LOCALAPPDATA%\ms-playwright` (no es una dependencia de `pip`); hay que ejecutarlo una vez por máquina.

## Regla de Comunicación Obligatoria

- **Idioma de interacción**: Responde, explica, reporta y comunica SIEMPRE y ÚNICAMENTE en **español**, sin excepciones.
- Nunca generes resúmenes, mensajes de estado ni respuestas en inglés en la terminal.
