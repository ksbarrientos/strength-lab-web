import logging
import re
import threading
from datetime import time
from urllib.parse import quote_plus

from django.http import HttpResponseRedirect
from django.shortcuts import render

from apps.configuracion.models import (
    MENSAJE_WHATSAPP_POR_DEFECTO,
    ConfiguracionSitio,
)
from apps.integraciones.google_services import (
    agendar_en_google_calendar,
    registrar_en_google_sheets,
)

from .forms import DIAS_MAXIMOS_RESERVA, FormularioAgendar, FormularioReserva

logger = logging.getLogger(__name__)


class _DatosPlantilla(dict):
    """Deja intactos los marcadores desconocidos en vez de romper el mensaje."""

    def __missing__(self, clave):
        return '{' + clave + '}'


def _construir_mensaje_whatsapp(config, datos):
    """Reemplaza las variables de la plantilla configurada en el admin.

    Si la plantilla está vacía o tiene llaves inválidas, se usa la plantilla
    interna. La reserva nunca debe fallar por un error de configuración.
    """
    plantilla = (config.mensaje_predeterminado_whatsapp or '').strip()
    if not plantilla:
        plantilla = MENSAJE_WHATSAPP_POR_DEFECTO

    try:
        return plantilla.format_map(_DatosPlantilla(datos))
    except (KeyError, IndexError, ValueError):
        logger.warning(
            'La plantilla de WhatsApp tiene variables o llaves inválidas; '
            'se usa la plantilla interna.'
        )
        return MENSAJE_WHATSAPP_POR_DEFECTO.format(**datos)


def _construir_url_whatsapp(config, mensaje):
    """Devuelve la URL de wa.me con el mensaje prellenado."""
    numero = re.sub(r'\D', '', config.numero_whatsapp or '')
    return f'https://wa.me/{numero}?text={quote_plus(mensaje)}'


def _sincronizar_google(datos, spreadsheet_id, calendar_id, correo_notificaciones):
    """Ejecuta Sheets y Calendar fuera del ciclo de la petición web."""
    try:
        registrar_en_google_sheets(datos, spreadsheet_id)
        agendar_en_google_calendar(datos, calendar_id, correo_notificaciones)
    except Exception:
        # google_services ya es defensivo; este except es una última barrera
        # para que un error inesperado no tumbe el hilo con un traceback suelto.
        logger.exception('Error inesperado al sincronizar la reserva con Google.')


def reserva_dia_gratis(request):
    """Procesa el formulario de día gratis y redirige a WhatsApp.

    Los leads no se guardan en la base de datos: se envían a Google Sheets y
    Calendar en un hilo en segundo plano para responder de inmediato. El
    usuario confirma la cita por WhatsApp con el mensaje prellenado.
    """
    if request.method != 'POST':
        return render(
            request,
            'reservas/formulario_reserva.html',
            {'form': FormularioReserva()},
        )

    form = FormularioReserva(request.POST)
    if not form.is_valid():
        # Ruta heredada: si los datos fallan, los errores se muestran aquí.
        return render(
            request,
            'reservas/formulario_reserva.html',
            {'form': form},
            status=400,
        )

    datos = form.cleaned_data
    config = ConfiguracionSitio.obtener_configuracion()

    # El teléfono completo incluye el código de país: '+50378538605'.
    telefono_completo = f"{datos['codigo_pais']}{datos['telefono']}"
    fecha_texto = datos['fecha_visita'].strftime('%d/%m/%Y')
    hora_texto = datos['hora_visita'].strftime('%H:%M')

    mensaje = _construir_mensaje_whatsapp(config, {
        'nombre': datos['nombre'],
        'fecha': fecha_texto,
        'hora': hora_texto,
        'correo': datos['email'],
        'telefono': telefono_completo,
    })
    url_whatsapp = _construir_url_whatsapp(config, mensaje)

    # Google necesita strings ISO ('YYYY-MM-DD' y 'HH:MM'), no objetos
    # date/time: el cliente serializa el body a JSON y Calendar usa strptime.
    datos_google = {
        'nombre': datos['nombre'],
        'telefono': telefono_completo,
        'email': datos['email'],
        'fecha_visita': datos['fecha_visita'].strftime('%Y-%m-%d'),
        'hora_visita': hora_texto,
        'notas': datos.get('notas', ''),
    }

    logger.info('[RESERVA WEB] Sheets ID: %s', config.google_sheets_spreadsheet_id)
    logger.info('[RESERVA WEB] Calendar ID: %s', config.google_calendar_id)

    try:
        threading.Thread(
            target=_sincronizar_google,
            args=(
                datos_google,
                config.google_sheets_spreadsheet_id,
                config.google_calendar_id,
                config.correo_notificaciones,
            ),
            daemon=True,
        ).start()
    except Exception:
        # Si el hilo no arranca, el usuario igual debe llegar a WhatsApp.
        logger.exception('No se pudo iniciar la sincronización con Google.')

    return HttpResponseRedirect(url_whatsapp)


def _horario_elegido(config, codigo_horario):
    """Devuelve la etiqueta visible y la hora exacta del bloque elegido.

    'manana' -> ('Mañana', hora_manana) y 'tarde' -> ('Tarde', hora_tarde).
    Las horas salen de la configuración del sitio (09:00 y 16:00 por defecto).
    """
    etiqueta = dict(FormularioAgendar.HORARIOS)[codigo_horario]
    hora = config.hora_manana if codigo_horario == 'manana' else config.hora_tarde
    if hora is None:  # defensa ante una configuración incompleta
        hora = time(9, 0) if codigo_horario == 'manana' else time(16, 0)
    return etiqueta, hora


def _contexto_agendar(form, config):
    """Contexto compartido por el GET y el POST inválido de /agendar/."""
    return {
        'form': form,
        'config': config,
        'dias_maximos': DIAS_MAXIMOS_RESERVA,
    }


def pagina_agendar(request):
    """Página dedicada `/agendar/`, con backend funcional.

    Replica el flujo del sitio de referencia (datos, calendario y bloque
    mañana/tarde), pero con lo que el original no hace: validación del lado
    del servidor, registro del lead en Google Sheets y evento real en Google
    Calendar. El formulario hace un POST normal con `target="_blank"`; la
    vista responde con un redirect a WhatsApp en la pestaña nueva.

    El evento se crea a la hora configurada para el bloque elegido
    (`ConfiguracionSitio.hora_manana` / `hora_tarde`), mientras que en Sheets
    se registra la etiqueta "Mañana" o "Tarde".
    """
    config = ConfiguracionSitio.obtener_configuracion()

    if request.method != 'POST':
        return render(
            request,
            'reservas/agendar_pagina.html',
            _contexto_agendar(FormularioAgendar(), config),
        )

    form = FormularioAgendar(request.POST)
    if not form.is_valid():
        # Se re-renderiza la página con los errores (misma pestaña nueva).
        return render(
            request,
            'reservas/agendar_pagina.html',
            _contexto_agendar(form, config),
            status=400,
        )

    datos = form.cleaned_data
    etiqueta_horario, hora = _horario_elegido(config, datos['horario'])

    telefono_completo = f"{datos['codigo_pais']}{datos['telefono']}"
    fecha_texto = datos['fecha_visita'].strftime('%d/%m/%Y')
    hora_texto = hora.strftime('%H:%M')

    mensaje = _construir_mensaje_whatsapp(config, {
        'nombre': datos['nombre'],
        'fecha': fecha_texto,
        # Ej.: "09:00 (mañana)"; la plantilla dice "a las {hora}".
        'hora': f'{hora_texto} ({etiqueta_horario.lower()})',
        'correo': datos['email'],
        'telefono': telefono_completo,
    })
    url_whatsapp = _construir_url_whatsapp(config, mensaje)

    datos_google = {
        'nombre': datos['nombre'],
        'telefono': telefono_completo,
        'email': datos['email'],
        'fecha_visita': datos['fecha_visita'].strftime('%Y-%m-%d'),
        # Calendar necesita la hora exacta ('HH:MM')…
        'hora_visita': hora_texto,
        # …y Sheets registra el bloque que eligió el visitante.
        'hora_etiqueta': etiqueta_horario,
        'notas': (
            f'Solicitud de día gratis desde /agendar/ '
            f'(horario: {etiqueta_horario}).'
        ),
    }

    logger.info(
        '[AGENDAR] %s pidió %s (%s) para el %s',
        datos['nombre'], etiqueta_horario, hora_texto, fecha_texto,
    )
    logger.info('[AGENDAR] Sheets ID: %s', config.google_sheets_spreadsheet_id)
    logger.info('[AGENDAR] Calendar ID: %s', config.google_calendar_id)

    try:
        threading.Thread(
            target=_sincronizar_google,
            args=(
                datos_google,
                config.google_sheets_spreadsheet_id,
                config.google_calendar_id,
                config.correo_notificaciones,
            ),
            daemon=True,
        ).start()
    except Exception:
        # Si el hilo no arranca, el usuario igual debe llegar a WhatsApp.
        logger.exception('No se pudo iniciar la sincronización con Google.')

    return HttpResponseRedirect(url_whatsapp)
