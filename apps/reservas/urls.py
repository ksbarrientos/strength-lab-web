from django.urls import path

from . import views

app_name = 'reservas'

urlpatterns = [
    path('', views.reserva_dia_gratis, name='reserva_dia_gratis'),
]
