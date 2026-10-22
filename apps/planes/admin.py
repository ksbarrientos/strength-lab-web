from django.contrib import admin
from django.utils.html import format_html

from .models import PlanEntrenamiento


@admin.register(PlanEntrenamiento)
class PlanEntrenamientoAdmin(admin.ModelAdmin):
    """Panel para gestionar los planes de entrenamiento del sitio."""

    list_display = ('portada', 'nombre', 'precio', 'sesiones_texto', 'es_popular', 'orden', 'activo')
    list_display_links = ('nombre',)
    list_editable = ('orden', 'activo')
    list_filter = ('activo', 'es_popular')
    search_fields = ('nombre', 'descripcion')
    ordering = ('orden',)

    @admin.display(description='portada')
    def portada(self, plan):
        """Miniatura de la imagen de portada en el listado del admin."""
        if not plan.imagen:
            return '—'
        return format_html(
            '<img src="{}" alt="{}" '
            'style="height:48px;width:36px;object-fit:cover;border-radius:4px;">',
            plan.imagen.url,
            plan.nombre,
        )
