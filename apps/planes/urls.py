from django.urls import path

from . import views

app_name = 'planes'

urlpatterns = [
    path('', views.index, name='index'),
]
