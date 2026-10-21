# Strength Lab Web & Admin

Sitio web y panel de administración para el gimnasio **Strength Lab**, construido con **Python 3.12+** y **Django**.

## Características del proyecto

- **Landing page pública** con estética deportiva oscura (Tailwind vía CDN): hero, grid de planes dinámico, sección de ubicación/horarios con mapa embebido y **modal de reserva** que consume el formulario vía Fetch/JSON.
- Configuración global editable desde el admin (WhatsApp, correos, IDs de Google).
- CMS ligero para planes de entrenamiento e información del sitio.
- **Reserva de día gratis**: al enviarla, la cita se registra en Google Sheets y Calendar, y el usuario es redirigido a WhatsApp para confirmar.

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
│   ├── reservas/                # formulario de reserva (sin modelo) + vista JSON
│   └── integraciones/           # google_services.py (Sheets y Calendar)
├── templates/                   # base.html, index.html + reservas/ (modal)
├── static/                      # CSS, JS e imágenes globales
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
| `/reserva/` | Formulario clásico (fallback POST tradicional, sin modal). |
| `/admin/` | Panel de administración. |

## Configurar las integraciones con Google

1. En Google Cloud Console crear un proyecto, habilitar **Google Sheets API** y **Google Calendar API**.
2. Crear una **cuenta de servicio** y descargar la clave JSON.
3. Guardarla como `credentials/google_service_account.json` (nunca se commitea).
4. Compartir la hoja de cálculo y el calendario con el correo de la cuenta de servicio (permiso editor).
5. En el admin (`/admin/`), sección **Configuración del sitio**, completar: número de WhatsApp, correo de notificaciones, ID del calendario y ID de la hoja.

Si falta algo, el sitio **sigue funcionando**: las integraciones fallan de forma defensiva (solo registran un warning) y el usuario igual es redirigido a WhatsApp.

## Cómo probar la reserva de día gratis

1. Arrancar el servidor: `python manage.py runserver`.
2. Abrir `http://127.0.0.1:8000/` y hacer clic en **"Día Gratis"** (o "Reserva tu día gratis" en el hero).
3. Llenar el modal y enviar: muestra una confirmación y ~2 s después abre WhatsApp con el mensaje prellenado.
4. El fallback sin modal está en `http://127.0.0.1:8000/reserva/`.
5. Si las integraciones están configuradas, verificar la fila nueva en Sheets y el evento en Calendar.

## Comandos útiles

| Comando | Descripción |
| --- | --- |
| `python manage.py runserver` | Servidor de desarrollo. |
| `python manage.py migrate` | Aplicar migraciones. |
| `python manage.py makemigrations` | Generar migraciones de cambios en modelos. |
| `python manage.py poblar_contenido` | Poblar/actualizar planes y configuración (idempotente). |
| `python manage.py createsuperuser` | Crear usuario del admin. |
| `python manage.py check` | Verificar la configuración del proyecto. |

## Próximos pasos

- Implementar el modelo `InformacionSitio` (redes sociales, galería de instalaciones) en `apps/planes`.
- Mejorar la landing: sección de servicios/galería, testimonials y SEO (meta tags, sitemap).
- En producción (PythonAnywhere): configurar `DEBUG=False`, `SECRET_KEY` real y `ALLOWED_HOSTS` en el `.env`.
