from django.contrib import admin

from .models import ConfiguracionSitio


@admin.register(ConfiguracionSitio)
class ConfiguracionSitioAdmin(admin.ModelAdmin):
    """Panel para editar la configuración global del sitio (singleton)."""

    fieldsets = (
        ('Gimnasio', {
            'fields': ('nombre_gimnasio', 'slogan', 'direccion', 'horarios'),
        }),
        ('Contacto', {
            'fields': (
                'numero_whatsapp',
                'correo_notificaciones',
                'mensaje_predeterminado_whatsapp',
            ),
        }),
        ('Integraciones con Google', {
            'fields': (
                'google_calendar_id',
                'google_sheets_spreadsheet_id',
            ),
            'description': (
                'IDs obtenidos desde Google Cloud Console. Deben coincidir '
                'con la cuenta de servicio autorizada.'
            ),
        }),
        ('Horarios de la página /agendar/', {
            'fields': ('hora_manana', 'hora_tarde'),
            'description': (
                'Hora exacta que se crea en Google Calendar según el bloque '
                'elegido. En Google Sheets se registra la etiqueta '
                '"Mañana" o "Tarde".'
            ),
        }),
    )

    def has_add_permission(self, request):
        # Singleton: no se permite crear más de una instancia.
        return not ConfiguracionSitio.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Singleton: nunca se debe borrar la configuración.
        return False
