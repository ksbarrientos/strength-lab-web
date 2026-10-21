"""Conectores con los servicios de Google (Calendar y Sheets).

Todas las funciones son defensivas: si algo falla (red, cuota, credenciales),
se registra un warning y se devuelve False, pero NUNCA se propaga el error.
La reserva del usuario no debe perderse por una falla de un servicio externo.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# Scopes mínimos necesarios para Sheets y Calendar.
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar',
]

# Ruta al archivo de credenciales de la cuenta de servicio (fuera de git).
RUTA_CREDENCIALES = Path(settings.BASE_DIR) / 'credentials' / 'google_service_account.json'


def _obtener_cliente_servicio(nombre_api, version):
    """Crea y devuelve un cliente autenticado con la cuenta de servicio.

    Devuelve None si las credenciales no existen o hay algún error; el
    caller debe manejar ese caso sin lanzar excepciones.
    """
    if not RUTA_CREDENCIALES.exists():
        logger.warning(
            'Google Services: no existe el archivo de credenciales %s. '
            'La integración con %s quedará deshabilitada.',
            RUTA_CREDENCIALES, nombre_api,
        )
        return None

    credenciales = service_account.Credentials.from_service_account_file(
        str(RUTA_CREDENCIALES), scopes=SCOPES
    )
    return build(nombre_api, version, credentials=credenciales)


def registrar_en_google_sheets(datos, spreadsheet_id):
    """Agrega una fila con los datos de la reserva a la hoja de cálculo.

    Fila: [Fecha solicitud, Nombre, Teléfono, Correo, Fecha Cita, Hora Cita, Notas]

    Retorna True si se registró correctamente, False en caso contrario.
    """
    if not spreadsheet_id:
        logger.warning('Google Sheets: no hay spreadsheet_id configurado; se omite el registro.')
        return False

    try:
        servicio = _obtener_cliente_servicio('sheets', 'v4')
        if servicio is None:
            return False

        fila = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            datos['nombre'],
            datos['telefono'],
            datos['email'],
            datos['fecha_visita'],
            datos['hora_visita'],
            datos.get('notas', ''),
        ]

        servicio.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='A1',
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body={'values': [fila]},
        ).execute()

        logger.info('Google Sheets: reserva de %s registrada correctamente.', datos['nombre'])
        return True

    except Exception:
        logger.warning(
            'Google Sheets: no se pudo registrar la reserva de %s.', datos['nombre'], exc_info=True
        )
        return False


def agendar_en_google_calendar(datos, calendar_id, correo_notificaciones):
    """Crea el evento de la cita en Google Calendar e invita al cliente.

    Retorna True si el evento se creó correctamente, False en caso contrario.
    """
    if not calendar_id:
        logger.warning('Google Calendar: no hay calendar_id configurado; se omite el evento.')
        return False

    try:
        servicio = _obtener_cliente_servicio('calendar', 'v3')
        if servicio is None:
            return False

        # Las fechas llegan como strings 'YYYY-MM-DD' y 'HH:MM'.
        inicio = datetime.strptime(f"{datos['fecha_visita']} {datos['hora_visita']}", '%Y-%m-%d %H:%M')
        fin = inicio + timedelta(hours=1)

        asistentes = [datos['email']]
        if correo_notificaciones:
            asistentes.append(correo_notificaciones)

        evento = {
            'summary': f"Día gratis - {datos['nombre']}",
            'description': datos.get('notas', 'Reserva de día gratis desde el sitio web.'),
            'start': {'dateTime': inicio.isoformat(), 'timeZone': 'America/El_Salvador'},
            'end': {'dateTime': fin.isoformat(), 'timeZone': 'America/El_Salvador'},
            'attendees': [{'email': correo} for correo in asistentes],
            'reminders': {'useDefault': True},
        }

        servicio.events().insert(
            calendarId=calendar_id,
            body=evento,
            sendUpdates='all',  # Nota por correo al cliente y al gimnasio.
        ).execute()

        logger.info('Google Calendar: evento para %s creado correctamente.', datos['nombre'])
        return True

    except Exception:
        logger.warning(
            'Google Calendar: no se pudo agendar la cita de %s.', datos['nombre'], exc_info=True
        )
        return False
