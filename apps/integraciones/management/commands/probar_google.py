"""Comando de diagnóstico para las integraciones con Google (Sheets y Calendar).

Uso:
    python manage.py probar_google                     # diagnóstico completo (escribe fila y evento de prueba)
    python manage.py probar_google --sin-escribir      # solo lectura: credenciales, configuración y metadata
    python manage.py probar_google --conservar-evento  # deja el evento de prueba creado en el calendario

Cada sección imprime el error EXACTO con traceback completo si algo falla,
para poder diagnosticar en el servidor de producción (PythonAnywhere), donde
los fallos de las integraciones quedan ocultos en los logs como warnings.
"""

import traceback
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from apps.configuracion.models import ConfiguracionSitio
from apps.integraciones import google_services


class Command(BaseCommand):
    help = ('Prueba las integraciones con Google (credenciales, Sheets y Calendar) '
            'e imprime el error exacto con traceback si algo falla.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--sin-escribir',
            action='store_true',
            help='No escribe fila ni evento de prueba (solo verifica acceso de lectura).',
        )
        parser.add_argument(
            '--conservar-evento',
            action='store_true',
            help='No borra el evento de prueba creado en Google Calendar.',
        )

    def handle(self, *args, **options):
        self.errores = 0
        self.sin_escribir = options['sin_escribir']

        self.stdout.write(self.style.MIGRATE_HEADING('--- 1. CREDENCIALES ---'))
        credenciales = self._probar_credenciales()

        self.stdout.write(self.style.MIGRATE_HEADING('--- 2. CONFIGURACION DEL SITIO ---'))
        config = self._probar_configuracion()

        if credenciales is None:
            raise CommandError(
                'Sin credenciales válidas no se puede probar Sheets ni Calendar. '
                'Revisa el archivo credentials/google_service_account.json.'
            )

        self.stdout.write(self.style.MIGRATE_HEADING('--- 3. GOOGLE SHEETS ---'))
        self._probar_sheets(credenciales, config)

        self.stdout.write(self.style.MIGRATE_HEADING('--- 4. GOOGLE CALENDAR ---'))
        self._probar_calendar(credenciales, config, options['conservar_evento'])

        self.stdout.write(self.style.MIGRATE_HEADING('--- RESUMEN ---'))
        if self.errores:
            raise CommandError(
                f'Diagnóstico terminado con {self.errores} sección(es) con error. '
                'Revisa los tracebacks de arriba.'
            )
        self.stdout.write(self.style.SUCCESS('Todas las secciones pasaron correctamente.'))

    # ------------------------------------------------------------------
    # Secciones de diagnóstico
    # ------------------------------------------------------------------

    def _probar_credenciales(self):
        """Carga el archivo de la cuenta de servicio y muestra sus datos."""
        ruta = google_services.RUTA_CREDENCIALES
        self.stdout.write(f'Archivo: {ruta}')
        self.stdout.write(f'Existe: {ruta.exists()}')

        if not ruta.exists():
            self.errores += 1
            self.stdout.write(self.style.ERROR(
                'FALTA el archivo de credenciales. En el servidor de producción hay que '
                'subirlo manualmente (no via git, pues está en .gitignore).'
            ))
            return None

        try:
            from google.oauth2 import service_account

            credenciales = service_account.Credentials.from_service_account_file(
                str(ruta), scopes=google_services.SCOPES
            )
            self.stdout.write(f'Cuenta de servicio: {credenciales.service_account_email}')
            self.stdout.write(f'Proyecto: {credenciales.project_id}')
            self.stdout.write(f'Scopes: {google_services.SCOPES}')
            self.stdout.write(self.style.SUCCESS('Credenciales cargadas correctamente.'))
            return credenciales
        except Exception:
            self.errores += 1
            self.stdout.write(self.style.ERROR('No se pudieron cargar las credenciales:'))
            self.stdout.write(traceback.format_exc())
            return None

    def _probar_configuracion(self):
        """Muestra los IDs de Google guardados en ConfiguracionSitio."""
        config = ConfiguracionSitio.obtener_configuracion()
        self.stdout.write(f'Hoja de cálculo (spreadsheet_id): {config.google_sheets_spreadsheet_id!r}')
        self.stdout.write(f'Calendario (calendar_id):         {config.google_calendar_id!r}')
        self.stdout.write(f'Correo de notificaciones:         {config.correo_notificaciones!r}')

        problemas = []
        if not config.google_sheets_spreadsheet_id:
            problemas.append('falta el ID de Google Sheets')
        if not config.google_calendar_id:
            problemas.append('falta el ID de Google Calendar')

        if problemas:
            self.errores += 1
            self.stdout.write(self.style.ERROR(
                'Configuración incompleta en el admin (/admin/): ' + ', '.join(problemas) + '.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('Configuración completa.'))
        return config

    def _probar_sheets(self, credenciales, config):
        """Lista las pestañas de la hoja y escribe una fila de prueba."""
        from googleapiclient.discovery import build

        spreadsheet_id = config.google_sheets_spreadsheet_id
        if not spreadsheet_id:
            self.errores += 1
            self.stdout.write(self.style.ERROR('Se omite la prueba de Sheets: no hay spreadsheet_id.'))
            return

        servicio = build('sheets', 'v4', credentials=credenciales)

        # a) Lectura: títulos de pestañas (para verificar el rango del append).
        try:
            meta = servicio.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields='sheets(properties(title,sheetId))',
            ).execute()
            titulos = [hoja['properties']['title'] for hoja in meta.get('sheets', [])]
            self.stdout.write(f'Pestañas de la hoja: {titulos}')
            self.stdout.write(self.style.SUCCESS('Lectura de la hoja OK.'))
        except Exception:
            self.errores += 1
            self.stdout.write(self.style.ERROR(
                'No se pudo leer la hoja (revisa el ID o el compartir con la cuenta de servicio):'
            ))
            self.stdout.write(traceback.format_exc())
            return

        # b) Escritura: fila de prueba.
        if self.sin_escribir:
            self.stdout.write('Prueba de escritura omitida (--sin-escribir).')
            return

        fila = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'PRUEBA probar_google - borrar',
            '+50378538605',
            'prueba@diagnostico.local',
            (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            '10:00',
            'Fila de prueba creada por manage.py probar_google',
        ]
        try:
            rango_escrito = servicio.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range='A1',
                valueInputOption='RAW',  # RAW conserva el '+' del teléfono como texto.
                insertDataOption='INSERT_ROWS',
                body={'values': [fila]},
            ).execute()
            self.stdout.write(self.style.SUCCESS(
                f"Fila de prueba insertada en {rango_escrito.get('updates', {}).get('updatedRange')} "
                '(puedes borrarla desde la hoja).'
            ))
        except Exception:
            self.errores += 1
            self.stdout.write(self.style.ERROR('Falló el append de la fila de prueba en Sheets:'))
            self.stdout.write(traceback.format_exc())

    def _probar_calendar(self, credenciales, config, conservar_evento):
        """Verifica el calendario y crea (y borra) un evento de prueba."""
        from googleapiclient.discovery import build

        calendar_id = config.google_calendar_id
        if not calendar_id:
            self.errores += 1
            self.stdout.write(self.style.ERROR('Se omite la prueba de Calendar: no hay calendar_id.'))
            return

        servicio = build('calendar', 'v3', credentials=credenciales)

        # a) Lectura: datos del calendario.
        try:
            calendario = servicio.calendars().get(calendarId=calendar_id).execute()
            self.stdout.write(
                f"Calendario: {calendario.get('summary')} | "
                f"zona horaria: {calendario.get('timeZone')} | "
                f"acceso: {calendario.get('accessRole')}"
            )
            self.stdout.write(self.style.SUCCESS('Lectura del calendario OK.'))
        except Exception:
            self.errores += 1
            self.stdout.write(self.style.ERROR(
                'No se pudo leer el calendario (revisa el ID o el compartir con la cuenta de servicio):'
            ))
            self.stdout.write(traceback.format_exc())
            return

        # b) Escritura: evento de prueba sin asistentes y sin notificaciones.
        if self.sin_escribir:
            self.stdout.write('Prueba de escritura omitida (--sin-escribir).')
            return

        inicio = datetime.now() + timedelta(days=1)
        inicio = inicio.replace(hour=10, minute=0, second=0, microsecond=0)
        evento = {
            'summary': 'PRUEBA probar_google - borrar',
            'description': 'Evento de prueba creado por manage.py probar_google.',
            'start': {'dateTime': inicio.isoformat(), 'timeZone': 'America/El_Salvador'},
            'end': {'dateTime': (inicio + timedelta(hours=1)).isoformat(), 'timeZone': 'America/El_Salvador'},
        }
        try:
            creado = servicio.events().insert(
                calendarId=calendar_id,
                body=evento,
                sendUpdates='none',  # Sin invitaciones: es solo una prueba.
            ).execute()
            self.stdout.write(self.style.SUCCESS(
                f"Evento de prueba creado (id {creado.get('id')})."
            ))
        except Exception:
            self.errores += 1
            self.stdout.write(self.style.ERROR('Falló la creación del evento de prueba en Calendar:'))
            self.stdout.write(traceback.format_exc())
            return

        if conservar_evento:
            self.stdout.write('Evento de prueba conservado (--conservar-evento); bórralo manualmente.')
            return

        try:
            servicio.events().delete(calendarId=calendar_id, eventId=creado['id']).execute()
            self.stdout.write(self.style.SUCCESS('Evento de prueba borrado (Calendar OK en ambos sentidos).'))
        except Exception:
            self.errores += 1
            self.stdout.write(self.style.ERROR('El evento se creó pero no se pudo borrar:'))
            self.stdout.write(traceback.format_exc())
