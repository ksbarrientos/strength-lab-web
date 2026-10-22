"""URLs de la app de reservas.

La página `/agendar/` es el flujo oficial y único de reserva: calendario con
días interactivos y bloques MAÑANA/TARDE. `/reserva/` se conserva sólo como
respaldo del formulario antiguo de hora manual (ya no se enlaza desde la
interfaz).
"""

from django.urls import path

from . import views

app_name = 'reservas'

urlpatterns = [
    # Flujo oficial: calendario + bloques mañana/tarde.
    path('agendar/', views.pagina_agendar, name='pagina_agendar'),
    # Ruta heredada del formulario con hora manual (sin enlaces en la interfaz).
    path('reserva/', views.reserva_dia_gratis, name='reserva_dia_gratis'),
]
