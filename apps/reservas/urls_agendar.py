"""URLs de la página dedicada `/agendar/`.

Se separa de `urls.py` (montado en `/reserva/`) para conservar el flujo del
modal y exponer la página nueva en su propia ruta, igual que el sitio de
referencia.
"""

from django.urls import path

from . import views

app_name = 'agendar'

urlpatterns = [
    path('', views.pagina_agendar, name='pagina_agendar'),
]
