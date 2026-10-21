from django.contrib import admin

from .models import PlanEntrenamiento


@admin.register(PlanEntrenamiento)
class PlanEntrenamientoAdmin(admin.ModelAdmin):
    """Panel para gestionar los planes de entrenamiento del sitio."""

    list_display = ('nombre', 'precio', 'sesiones_texto', 'es_popular', 'orden', 'activo')
    list_editable = ('orden', 'activo')
    list_filter = ('activo', 'es_popular')
    search_fields = ('nombre', 'descripcion')
    ordering = ('orden',)
