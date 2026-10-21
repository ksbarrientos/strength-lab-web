import logging
from urllib.parse import quote_plus

from django.http import JsonResponse
from django.shortcuts import redirect, render

from apps.configuracion.models import ConfiguracionSitio
from apps.integraciones.google_services import (
    agendar_en_google_calendar,
    registrar_en_google_sheets,
)

from .forms import FormularioReserva

logger = logging.getLogger(__name__)


def _es_peticion_ajax(request):
    """Detecta si la petición viene de fetch/AJAX por el header custom."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def reserva_dia_gratis(request):
    """Muestra el formulario de reserva de día gratis y procesa el envío.

    La reserva NO se guarda en la base de datos (alojamiento gratuito con
    cuota limitada); se envía a Google Sheets y Calendar, y se devuelve la
    URL de WhatsApp para que el usuario confirme con el gimnasio.

    Si la petición es AJAX (header `X-Requested-With`), responde JSON con
    la URL de WhatsApp; si no, redirige directamente (fallback POST clásico).
    """
    if request.method == 'POST':
        form = FormularioReserva(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            config = ConfiguracionSitio.obtener_configuracion()

            registrar_en_google_sheets(datos, config.google_sheets_spreadsheet_id)
            agendar_en_google_calendar(
                datos, config.google_calendar_id, config.correo_notificaciones
            )

            # Mensaje prellenado para abrir el chat de WhatsApp del gimnasio.
            mensaje = (
                f"Hola {config.nombre_gimnasio}, soy {datos['nombre']}. "
                f"Agendé mi día gratis para el {datos['fecha_visita']} a las "
                f"{datos['hora_visita']}. Mi correo es {datos['email']}."
            )
            numero = config.numero_whatsapp.replace('+', '').replace(' ', '')
            url_whatsapp = f"https://wa.me/{numero}?text={quote_plus(mensaje)}"

            if _es_peticion_ajax(request):
                return JsonResponse({'ok': True, 'url_whatsapp': url_whatsapp})

            return redirect(url_whatsapp)

        # Formulario inválido.
        if _es_peticion_ajax(request):
            return JsonResponse({'ok': False, 'errores': form.errors}, status=400)
    else:
        form = FormularioReserva()

    return render(request, 'reservas/formulario_reserva.html', {'form': form})
