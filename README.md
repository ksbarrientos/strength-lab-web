# Strength Lab Web & Admin

Sitio web y panel de administración para el gimnasio **Strength Lab**, construido con **Python 3.12+** y **Django**.

## Características del proyecto

- **Landing page pública** con estética deportiva oscura (Tailwind vía CDN): hero, grid de planes dinámico, sección de ubicación/horarios con mapa embebido y **modal de reserva** con **POST normal** (`target="_blank"`), sin `fetch`, sin `window.open` y sin pestañas en blanco. El sitio muestra una confirmación inmediata en la pestaña actual y el formulario se procesa en la pestaña nueva.
- Configuración global editable desde el admin (WhatsApp, correo de notificaciones, mensaje de WhatsApp e IDs de Google).
- CMS ligero para planes de entrenamiento e información del sitio.
- **Reserva de día gratis**: Django procesa el formulario, responde con un `HttpResponseRedirect` a WhatsApp y envía la cita a Google Sheets y Calendar **en un hilo en segundo plano**, para que la respuesta web sea instantánea.
- **Mensaje de WhatsApp configurable** desde el admin con las variables `{nombre}`, `{fecha}`, `{hora}`, `{correo}` y `{telefono}`. Si el campo se deja vacío, se usa una plantilla interna con esas mismas variables.
- **Selector de código de país** en el formulario y el modal (El Salvador +503 por defecto, +1, +502, +504, +506, +52); el teléfono se concatena como `+50378538605` antes de enviarlo a Sheets, Calendar y WhatsApp.
- **Página dedicada `/agendar/`**: réplica funcional del formulario del sitio de referencia (título "AGENDA TU DÍA DE PRUEBA", sección de datos, calendario mensual, toggle **MAÑANA/TARDE** y botón "CONFIRMAR POR WHATSAPP"), con validación, registro en Google Sheets y evento en Google Calendar a la hora configurada para cada bloque. Convive con el modal rápido de la landing.
- **Script de inspección de sitios con JavaScript** (`scripts/inspeccionar_sitio.py`, Playwright + Chromium): captura la pantalla completa, el HTML ya renderizado y la estructura de clases, textos y formularios de cualquier SPA, incluida la del sitio de referencia.

### Arquitectura de leads (importante)

Los leads de pruebas gratis **NO se guardan en la base de datos**. El sitio se aloja en la capa gratuita de PythonAnywhere, cuya BD tiene cuota limitada; por eso el almacenamiento de leads es **100% Google Sheets**. La app `reservas` usa un `forms.Form` simple (sin modelo, sin migraciones) y solo dispara las integraciones de Google.

## Requisitos

- Python 3.12 o superior.
- `pip` actualizado.

## Instalación

```powershell
# 1. Crear y activar el entorno virtual (Windows)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -r requirements.txt
# 2b. Descargar el navegador Chromium que usa Playwright (solo la primera vez)
playwright install chromium

# 3. Configurar variables de entorno
Copy-Item .env.example .env
# Editar .env con valores reales (SECRET_KEY, DEBUG, ALLOWED_HOSTS)

# 4. Aplicar migraciones
python manage.py migrate

# 5. Poblar datos iniciales (4 planes + configuración del sitio)
python manage.py poblar_contenido

# 6. Crear usuario administrador
python manage.py createsuperuser

# 7. Arrancar el servidor de desarrollo
python manage.py runserver
```

El sitio quedará disponible en `http://127.0.0.1:8000/` y el panel admin en `http://127.0.0.1:8000/admin/`.

## Variables de entorno (`.env`)

| Variable | Descripción |
| --- | --- |
| `SECRET_KEY` | Clave secreta de Django (obligatoria en producción). |
| `DEBUG` | `True` en desarrollo, `False` en producción. |
| `ALLOWED_HOSTS` | Hosts permitidos separados por coma. |

El archivo `.env` está ignorado por git; usar `.env.example` como plantilla.

## Estructura

```text
strengthlab/
├── manage.py
├── core/                        # settings.py, urls.py, wsgi.py, asgi.py
├── apps/
│   ├── configuracion/           # ConfiguracionSitio (singleton, admin)
│   ├── planes/                  # PlanEntrenamiento + vista index (landing)
│   ├── reservas/                # formulario de reserva (sin modelo) + vista de redirección
│   └── integraciones/           # google_services.py (Sheets y Calendar) + comando probar_google
├── templates/                   # base.html, index.html + reservas/ (modal)
├── static/                      # CSS, JS e imágenes globales
│   └── capturas_referencia/     # capturas de referencia (sitio_original.png)
├── scripts/                     # utilidades de desarrollo (inspeccionar_sitio.py)
├── media/                       # Archivos multimedia subidos (admin)
├── credentials/                 # google_service_account.json (ignorado en git)
├── requirements.txt
├── .env.example
└── README.md
```

### URLs

| Ruta | Descripción |
| --- | --- |
| `/` | Landing pública (hero, planes, ubicación y modal de reserva). |
| `/agendar/` | Página dedicada de reserva: datos, calendario mensual y bloque mañana/tarde. |
| `/reserva/` | POST del formulario de reserva (redirige a WhatsApp) y formulario clásico para visitas directas sin JS. |
| `/admin/` | Panel de administración. |

## Configurar las integraciones con Google

1. En Google Cloud Console crear un proyecto, habilitar **Google Sheets API** y **Google Calendar API**.
2. Crear una **cuenta de servicio** y descargar la clave JSON.
3. Guardarla como `credentials/google_service_account.json` (nunca se commitea).
4. Compartir la hoja de cálculo y el calendario con el correo de la cuenta de servicio (permiso editor).
5. En el admin (`/admin/`), sección **Configuración del sitio**, completar: número de WhatsApp, correo de notificaciones, mensaje predeterminado de WhatsApp, ID del calendario, ID de la hoja y las **horas de los bloques** (`hora_manana` / `hora_tarde`, 09:00 y 16:00 por defecto). El mensaje admite las variables `{nombre}`, `{fecha}`, `{hora}`, `{correo}` y `{telefono}`; si se deja vacío se usa la plantilla interna.

Si falta algo, el sitio **sigue funcionando**: las integraciones fallan de forma defensiva (solo registran un warning) y el usuario igual es redirigido a WhatsApp.

> ⚠️ **Importante en producción (PythonAnywhere)**: el archivo `credentials/google_service_account.json` está en `.gitignore`, así que **no viaja con el código**. Hay que subirlo manualmente a la carpeta `credentials/` del servidor; si no existe allí, las integraciones quedan deshabilitadas en silencio (solo un warning en los logs) y el formulario seguirá redirigiendo a WhatsApp sin registrar nada. Para diagnosticarlo en el servidor:

```powershell
# En la consola de PythonAnywhere (con el virtualenv activado y en la carpeta del proyecto):
python manage.py probar_google --sin-escribir   # solo lectura: credenciales, config y metadata
python manage.py probar_google                  # completo: escribe fila y evento de prueba
```

Las filas y eventos de prueba quedan marcados con `PRUEBA`; el evento de prueba se borra solo al terminar (usar `--conservar-evento` para dejarlo).

**Nota sobre el formato del teléfono en Sheets**: el append usa `valueInputOption='RAW'` para que el teléfono `+50378538605` se guarde como texto literal. Con `USER_ENTERED`, Google Sheets interpretaba el `+` inicial como fórmula y perdía el signo (quedaba `50378538605`).

### Solución de problemas (diagnóstico)

La vista `reserva_dia_gratis` **lee los IDs directo de la base** con `ConfiguracionSitio.obtener_configuracion()`, nunca de `.env` ni de variables de entorno, y los imprime en la terminal de `runserver`:

```
[INFO] apps.reservas.views: [RESERVA WEB] Sheets ID: 1bhbQ...
[INFO] apps.reservas.views: [RESERVA WEB] Calendar ID: f6a89f...
```

Si una integración falla, `google_services.py` imprime el **traceback completo** en la terminal (además del warning). Errores frecuentes:

| Error | Causa y solución |
| --- | --- |
| `TypeError: Object of type date is not JSON serializable` | La vista no convirtió `fecha_visita`/`hora_visita` a string. Ya se normalizan con `strftime` en la vista y con `_formatear_fecha`/`_formatear_hora` en `google_services.py`. |
| `ValueError: unconverted data remains: :00` | La hora venía como objeto `time` (cuyo `str()` es `10:00:00`) y Calendar esperaba `HH:MM`. Solucionado con `datetime.combine`. |
| `403 forbiddenForServiceAccounts: "Service accounts cannot invite attendees..."` | **Limitación de Google**: una cuenta de servicio no puede invitar asistentes ni enviar notificaciones `sendUpdates='all'` salvo con *Domain-Wide Delegation*. El código lo maneja: reintenta el evento **sin invitados** (el cliente ya confirma por WhatsApp). |
| `404 notFound` en Sheets/Calendar | El ID no corresponde, o la hoja/calendario **no están compartidos** con el correo de la cuenta de servicio. |
| No ocurre nada en la terminal | Falta el archivo de credenciales (las funciones devuelven `False` tras un warning). Verificar con `python manage.py probar_google --sin-escribir`. |

Los logs de las apps (`apps.*`) se muestran en la consola gracias a la sección `LOGGING` de `core/settings.py`; sin ella, Django solo imprime el logger `django`.

### Limitación de Google Calendar (cuenta de servicio)

Los eventos se crean en el calendario del gimnasio con el nombre `Día gratis - <nombre>` y una descripción que incluye teléfono y correo del cliente. **No envían invitación por correo** al cliente, porque una cuenta de servicio no puede invitar asistentes (requiere *Domain-Wide Delegation* de Google Workspace). Si en el futuro se quiere que el cliente reciba la invitación de calendario, hay que migrar a OAuth de usuario (consentimiento propio) o habilitar la delegación de dominio.

## Cómo probar la reserva de día gratis

1. Arrancar el servidor: `python manage.py runserver`.
2. Abrir `http://127.0.0.1:8000/` y hacer clic en **"Día Gratis"** (o "Reserva tu día gratis" en el hero).
3. Llenar el modal (nombre, correo, código de país + teléfono local, fecha y hora) y enviar. El formulario hace un **POST normal** a `/reserva/` en una **pestaña nueva** (`target="_blank"`), sin `fetch` ni `window.open`. En la pestaña del sitio, el modal oculta el formulario y muestra **"¡Solicitud enviada!"**.
4. La pestaña nueva recibe la redirección de Django (`HttpResponseRedirect`) y abre WhatsApp con el mensaje prellenado. Si los datos no son válidos, esa pestaña muestra el formulario con los errores.
5. El script del modal solo abre/cierra, reinicia el formulario y **deshabilita el botón en el `submit`** para evitar envíos dobles.
6. El formulario clásico sin modal está en `http://127.0.0.1:8000/reserva/`.
7. Si las integraciones están configuradas, verificar la fila nueva en Sheets (el teléfono debe aparecer con `+`, ej. `+50378538605`) y el evento en Calendar. La sincronización corre en un hilo en segundo plano, así que la redirección a WhatsApp no espera a Google; en la terminal de `runserver` se ven los `[RESERVA WEB]` con los IDs usados y cualquier warning de las integraciones.

## Inspeccionar un sitio con JavaScript (Playwright)

`scripts/inspeccionar_sitio.py` abre una URL en Chromium, espera a que la red quede en reposo (`networkidle`), hace scroll para disparar animaciones y carga diferida, y guarda:

| Archivo | Contenido |
| --- | --- |
| `static/capturas_referencia/sitio_original.png` | Captura de pantalla completa. |
| `scripts/output_renderizado.html` | HTML final ya renderizado (no el HTML crudo del servidor). |
| `scripts/estructura_sitio.json` | Clases CSS, textos, botones, enlaces y estructura de formularios. |
| `scripts/estructura_sitio.md` | El mismo informe en Markdown, legible. |

```powershell
# Uso básico
python scripts/inspeccionar_sitio.py https://www.strengthlabcenter.com/agendar

# Con el navegador visible (útil para depurar paso a paso)
python scripts/inspeccionar_sitio.py https://www.strengthlabcenter.com/agendar --mostrar

# Más espera para SPAs lentas, o sin fallback de rutas client-side
python scripts/inspeccionar_sitio.py <url> --espera 5
python scripts/inspeccionar_sitio.py <url> --sin-fallback
```

**Fallback SPA (importante)**: el sitio de referencia está desplegado en Vercel como SPA de Vite sin rewrites, así que `https://www.strengthlabcenter.com/agendar` responde **HTTP 404** aunque la ruta exista en el bundle. Cuando la URL directa falla, el script carga el origen y navega en el cliente con `history.pushState` + evento `popstate`; así la vista se renderiza igual y la inspección funciona. El informe lo deja anotado en el campo `aviso`.

**Qué encontró en `/agendar`**: no hay `<form>`; son tres `input` controlados por React (`nombre`, `correo` de tipo `email`, `telefono`) dentro de una grilla, un calendario propio (31 `button` en `div.grid.grid-cols-7`, días pasados con `cursor-not-allowed`), un toggle `MAÑANA`/`TARDE` y un `button` **CONFIRMAR POR WHATSAPP** que **no valida ni envía nada al backend**: abre en una pestaña nueva `https://api.whatsapp.com/send/?phone=...&text=...` con el mensaje prellenado. Tampoco guarda el lead en ningún lado. Esa estructura es la que replica nuestra página propia `/agendar/` (ver más arriba), pero con validación, Sheets y Calendar.

### Página `/agendar/` (calendario + mañana/tarde)

1. Arrancar el servidor y abrir `http://127.0.0.1:8000/agendar/` (también se llega desde **"Agendar cita"** en la barra de navegación).
2. Elegir el día en el calendario: los días pasados, los domingos y los que superan los **90 días** de ventana aparecen deshabilitados.
3. Alternar **MAÑANA** / **TARDE**; el valor se guarda en el input oculto `horario` (`manana`/`tarde`).
4. Enviar: el formulario hace un **POST normal** a `/agendar/` con `target="_blank"`. La vista valida, agenda en Calendar a la hora configurada y escribe en Sheets.
5. La pestaña original muestra "¡Solicitud enviada!" y deshabilita el botón; la nueva abre WhatsApp con el mensaje prellenado.

Diferencias con el modal de la landing:

| Aspecto | Modal (`/reserva/`) | Página `/agendar/` |
| --- | --- | --- |
| Fecha y hora | `input type="date"` + `input type="time"` | calendario propio + bloque mañana/tarde |
| Hora en Calendar | la que elige el usuario | `ConfiguracionSitio.hora_manana` (09:00) o `hora_tarde` (16:00) |
| Hora en Sheets | `HH:MM` | etiqueta `Mañana` / `Tarde` |
| Validación extra | — | no domingos, máximo 90 días, nombre sin dígitos |

Las reglas viven en `apps/reservas/forms.py`: `DIAS_CERRADOS = (6,)` (domingo) y `DIAS_MAXIMOS_RESERVA = 90`. El calendario recibe `DIAS_MAXIMOS` desde la vista; si cambias la constante, el límite del JS se actualiza solo. Los días cerrados también deben ajustarse en `DIA_CERRADO` del script de la plantilla.

Para probar el flujo completo con el backend (sin escribir en Google, porque el hilo se mockea):

```powershell
python manage.py test apps.reservas apps.integraciones
```

## Comandos útiles

| Comando | Descripción |
| --- | --- |
| `python manage.py runserver` | Servidor de desarrollo. |
| `python manage.py migrate` | Aplicar migraciones. |
| `python manage.py makemigrations` | Generar migraciones de cambios en modelos. |
| `python manage.py poblar_contenido` | Poblar/actualizar planes y configuración (idempotente). |
| `python manage.py test` | Ejecutar las pruebas (incluye `apps.reservas.tests` para el flujo de reserva). |
| `python manage.py probar_google` | Diagnosticar credenciales, Google Sheets y Calendar (con `--sin-escribir` y `--conservar-evento`). |
| `python scripts/inspeccionar_sitio.py <url>` | Inspeccionar una web con JavaScript: captura, HTML renderizado y estructura (requiere `playwright install chromium`). |
| `python manage.py createsuperuser` | Crear usuario del admin. |
| `python manage.py check` | Verificar la configuración del proyecto. |

## Próximos pasos

- Implementar el modelo `InformacionSitio` (redes sociales, galería de instalaciones) en `apps/planes`.
- Mejorar la landing: sección de servicios/galería, testimonials y SEO (meta tags, sitemap).
- En producción (PythonAnywhere): configurar `DEBUG=False`, `SECRET_KEY` real y `ALLOWED_HOSTS` en el `.env`.
