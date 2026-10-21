"""Conectores con los servicios de Google (Calendar y Sheets).

Todas las funciones son defensivas: si algo falla (red, cuota, credenciales),
se registra un warning y se devuelve False, pero NUNCA se propaga el error.
La reserva del usuario no debe perderse por una falla de un servicio externo.
"""

import logging
import traceback
from datetime import datetime, timedelta

from django.conf import settings

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Scopes mínimos necesarios para Sheets y Calendar.
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar',
]

# Ruta al archivo de credenciales de la cuenta de servicio (fuera de git).
RUTA_CREDENCIALES = settings.BASE_DIR / 'credentials' / 'google_service_account.json'


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


def _formatear_fecha(valor):
    """Devuelve la fecha como string 'YYYY-MM-DD'.

    Acepta strings (se devuelven tal cual) u objetos date/datetime, que es lo
    que entrega Django en `cleaned_data` para un `DateField`.
    """
    if hasattr(valor, 'strftime'):
        return valor.strftime('%Y-%m-%d')
    return str(valor)


def _formatear_hora(valor):
    """Devuelve la hora como string 'HH:MM' (sin segundos).

    Acepta strings u objetos time/datetime; un objeto `time` convertido con
    `str()` daría '10:00:00' y rompería el `strptime('%H:%M')` de Calendar.
    """
    if hasattr(valor, 'strftime'):
        return valor.strftime('%H:%M')
    return str(valor)


def registrar_en_google_sheets(datos, spreadsheet_id):
    """Agrega una fila con los datos de la reserva a la hoja de cálculo.

    Fila: [Fecha solicitud, Nombre, Teléfono, Correo, Fecha Cita, Hora Cita, Notas]

    Si `datos` trae `hora_etiqueta` (por ejemplo "Mañana" o "Tarde"), esa
    etiqueta se escribe en la columna Hora Cita en lugar de la hora exacta:
    así el gimnasio ve el bloque que eligió el visitante en /agendar/.

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
            _formatear_fecha(datos['fecha_visita']),
            # En /agendar/ se registra el bloque elegido ("Mañana"/"Tarde");
            # el resto de flujos sigue enviando la hora exacta.
            datos.get('hora_etiqueta') or _formatear_hora(datos['hora_visita']),
            datos.get('notas', ''),
        ]

        servicio.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='A1',
            # RAW guarda los valores como texto literal: conserva el '+' del
            # teléfono (con USER_ENTERED se interpretaba como fórmula y se perdía).
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': [fila]},
        ).execute()

        logger.info('Google Sheets: reserva de %s registrada correctamente.', datos['nombre'])
        return True

    except Exception:
        logger.warning(
            'Google Sheets: no se pudo registrar la reserva de %s.', datos['nombre']
        )
        # Traza completa en la terminal de runserver para diagnosticar el fallo.
        traceback.print_exc()
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

        # Las fechas pueden llegar como strings 'YYYY-MM-DD' y 'HH:MM' o como
        # objetos date/time (según el caller); se normalizan a datetime.
        fecha = datos['fecha_visita']
        hora = datos['hora_visita']
        if isinstance(fecha, str):
            fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
        if isinstance(hora, str):
            hora = datetime.strptime(hora, '%H:%M').time()
        inicio = datetime.combine(fecha, hora)
        fin = inicio + timedelta(hours=1)

        asistentes = [datos['email']]
        if correo_notificaciones:
            asistentes.append(correo_notificaciones)

        horario_etiqueta = datos.get('hora_etiqueta')
        detalle_horario = (
            f"{horario_etiqueta} ({hora.strftime('%H:%M')})"
            if horario_etiqueta
            else hora.strftime('%H:%M')
        )

        evento = {
            'summary': f"Día gratis - {datos['nombre']}",
            'description': (
                f"{datos.get('notas', 'Reserva de día gratis desde el sitio web.')}\n\n"
                f"Cliente: {datos['nombre']} | Teléfono: {datos['telefono']} | "
                f"Correo: {datos['email']} | Horario preferido: {detalle_horario}"
            ),
            'start': {'dateTime': inicio.isoformat(), 'timeZone': 'America/El_Salvador'},
            'end': {'dateTime': fin.isoformat(), 'timeZone': 'America/El_Salvador'},
            'attendees': [{'email': correo} for correo in asistentes],
            'reminders': {'useDefault': True},
        }

        try:
            servicio.events().insert(
                calendarId=calendar_id,
                body=evento,
                sendUpdates='all',  # Nota por correo al cliente y al gimnasio.
            ).execute()
        except HttpError as error:
            # Las cuentas de servicio NO pueden invitar asistentes (ni enviar
            # notificaciones 'all') salvo con Domain-Wide Delegation. En ese
            # caso se agenda el evento sin invitados, para que la reserva no se
            # pierda: el cliente ya recibe confirmación por WhatsApp.
            if error.resp.status == 403 and 'attendees' in (error.content or b'').decode('utf-8', 'ignore'):
                logger.warning(
                    'Google Calendar: la cuenta de servicio no puede invitar asistentes '
                    '(requiere Domain-Wide Delegation); se agenda el evento sin invitados.'
                )
                evento.pop('attendees', None)
                servicio.events().insert(
                    calendarId=calendar_id,
                    body=evento,
                    sendUpdates='none',
                ).execute()
            else:
                raise

        logger.info('Google Calendar: evento para %s creado correctamente.', datos['nombre'])
        return True

    except Exception:
        logger.warning(
            'Google Calendar: no se pudo agendar la cita de %s.', datos['nombre']
        )
        # Traza completa en la terminal de runserver para diagnosticar el fallo.
        traceback.print_exc()
        return False
