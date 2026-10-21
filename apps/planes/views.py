from django.shortcuts import render

from apps.configuracion.models import ConfiguracionSitio
from apps.reservas.forms import FormularioReserva

from .models import PlanEntrenamiento


def index(request):
    """Landing page pública: hero, planes, ubicación y modal de reserva."""
    context = {
        'planes': PlanEntrenamiento.objects.filter(activo=True),
        'config': ConfiguracionSitio.obtener_configuracion(),
        'form_reserva': FormularioReserva(),
    }
    return render(request, 'index.html', context)
