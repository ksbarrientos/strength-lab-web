# Directivas del Agente - Strength Lab Web & Admin

## 1. Estado actual

- **Landing pública implementada** (raíz `/`): estética oscura con Tailwind vía CDN, hero, grid de planes dinámico, sección Ubicación/Horarios con mapa embebido y **modal de reserva** que envía el formulario por Fetch/JSON y redirige a WhatsApp.
- **Datos iniciales**: comando `python manage.py poblar_contenido` (idempotente) puebla los 4 planes reales (Élite $200/20 ses. popular, Progreso $150/15, Inicial $100/10, Básico $45) y la configuración del sitio (horarios L-V 5am-10pm, Sáb 7am-3pm, Merliot, WhatsApp +50378538605).
- **Modelos y reservas**: `ConfiguracionSitio` (singleton), `PlanEntrenamiento`, `FormularioReserva` y `google_services.py` (Sheets + Calendar). Migraciones aplicadas y `manage.py check` en verde.
- **Arquitectura de leads**: los leads de pruebas gratis **NO se guardan en la base de datos** (alojamiento gratuito en PythonAnywhere con cuota de BD limitada); se envían 100% a Google Sheets y se redirige al usuario a WhatsApp.
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
├── templates/                   # base.html, index.html + reservas/ (modal)
├── static/                      # estáticos globales (STATICFILES_DIRS)
├── media/                       # subidas del admin (fotos, banners)
├── credentials/                 # google_service_account.json (ignorado en git)
├── .env / .env.example
├── README.md
└── requirements.txt
```

- Las apps viven bajo el paquete `apps/`, así que cada `AppConfig` debe declarar `name = 'apps.<nombre>'` (no `'<nombre>'`), o Django falla al arrancar.

---

## 4. Restricciones del dominio que un agente no debe violar

- **`ConfiguracionSitio` es un singleton** (forzado en `save()` con pk=1, acceso vía `obtener_configuracion()`): nombre/slogan/dirección/horarios del gimnasio, `numero_whatsapp`, `correo_notificaciones`, `google_calendar_id` y `google_sheets_spreadsheet_id`.
- **`apps.reservas` NO tiene modelo ni migraciones**: los leads de pruebas gratis se guardan **100% en Google Sheets** (decisión de arquitectura por la cuota de BD de PythonAnywhere). Usar `FormularioReserva` (`forms.Form`, nunca `ModelForm`) y **no agregar** un modelo de reservas sin consultar antes al usuario.
- La landing (`/`, vista `index` en `apps/planes/views.py`) y el modal: si el POST a `/reserva/` trae el header `X-Requested-With: XMLHttpRequest`, la vista responde `JsonResponse({'ok': True, 'url_whatsapp': ...})`; si no, redirige directamente (fallback clásico). **No duplicar la lógica de reserva** entre modal y fallback.
- **Frontend**: Tailwind vía **Play CDN** en `base.html` (decisión KISS, sin paso de build) + Google Fonts (Anton/Montserrat). Colores: `antracita #0d0d0f`, `acento #ef4444`, `acento_naranja #f97316`. El modal está en `templates/reservas/modal_reserva.html` y usa `data-abrir-reserva` / `data-cerrar-reserva`.
- **Comando `poblar_contenido`** (`apps/planes/management/commands/`): idempotente, usa `update_or_create`; puebla los 4 planes y la configuración inicial. Ejecutar tras `migrate` en entornos nuevos.
- **Integraciones Google en `apps/integraciones/google_services.py`**:
  1. `registrar_en_google_sheets(datos, spreadsheet_id)`: fila `[Fecha solicitud, Nombre, Teléfono, Correo, Fecha Cita, Hora Cita, Notas]`.
  2. `agendar_en_google_calendar(datos, calendar_id, correo_notificaciones)`: evento de 1 hora con el cliente y el correo del gimnasio como asistentes (`sendUpdates='all'`).
  - Autenticación por cuenta de servicio (`credentials/google_service_account.json`); la acción de exportar reservas a `.xlsx` desde el admin **quedó fuera del alcance** (sin registros locales no hay nada que exportar).
- **Manejo defensivo obligatorio**: si Google falla (cuotas, red, sin credenciales), cada función registra un `logger.warning` y devuelve `False` sin lanzar excepciones; la redirección a WhatsApp **siempre** debe ocurrir.
- `credentials/google_service_account.json` jamás se commitea (ya está en `.gitignore`).

## Regla de Comunicación Obligatoria

- **Idioma de interacción**: Responde, explica, reporta y comunica SIEMPRE y ÚNICAMENTE en **español**, sin excepciones.
- Nunca generes resúmenes, mensajes de estado ni respuestas en inglés en la terminal.
