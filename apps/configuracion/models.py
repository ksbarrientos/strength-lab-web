from datetime import time

from django.db import models

# Plantilla interna del mensaje de WhatsApp. Se usa cuando el admin deja
# vacío `mensaje_predeterminado_whatsapp` (o cuando su plantilla es inválida).
MENSAJE_WHATSAPP_POR_DEFECTO = (
    'Hola Strength Lab, soy {nombre}. Agendé mi día gratis para el {fecha} '
    'a las {hora}. Mi correo es {correo} y mi teléfono es {telefono}.'
)


class ConfiguracionSitio(models.Model):
    """Configuración global del sitio, editable desde el admin.

    Implementa el patrón singleton: solo puede existir un registro (pk=1),
    accesible mediante `ConfiguracionSitio.obtener_configuracion()`.
    """

    nombre_gimnasio = models.CharField(
        'nombre del gimnasio', max_length=100, default='Strength Lab'
    )
    slogan = models.CharField('slogan', max_length=200, blank=True)
    direccion = models.CharField('dirección', max_length=200, blank=True)
    horarios = models.TextField('horarios de atención', blank=True)

    numero_whatsapp = models.CharField(
        'número de WhatsApp',
        max_length=20,
        help_text='Formato internacional sin signos, ej.: +50312345678.',
    )
    correo_notificaciones = models.EmailField(
        'correo de notificaciones',
        blank=True,
        help_text='Recibe alertas y copias de las reservas de prueba gratis.',
    )
    mensaje_predeterminado_whatsapp = models.TextField(
        'mensaje predeterminado de WhatsApp',
        blank=True,
        default='',
        help_text=(
            'Mensaje que se prellena al confirmar la reserva por WhatsApp. '
            'Variables disponibles: {nombre}, {fecha}, {hora}, {correo}, '
            '{telefono}. Si se deja vacío, se usa la plantilla interna.'
        ),
    )

    google_calendar_id = models.CharField(
        'ID de Google Calendar',
        max_length=255,
        blank=True,
        help_text='ID del calendario donde se agendarán las citas.',
    )
    google_sheets_spreadsheet_id = models.CharField(
        'ID de Google Sheets',
        max_length=255,
        blank=True,
        help_text='ID de la hoja de cálculo donde se registran los leads.',
    )

    hora_manana = models.TimeField(
        'hora de la cita (mañana)',
        default=time(9, 0),
        help_text=(
            'Hora que se agenda en Google Calendar cuando el visitante elige '
            '"Mañana" en la página /agendar/.'
        ),
    )
    hora_tarde = models.TimeField(
        'hora de la cita (tarde)',
        default=time(16, 0),
        help_text=(
            'Hora que se agenda en Google Calendar cuando el visitante elige '
            '"Tarde" en la página /agendar/.'
        ),
    )

    class Meta:
        verbose_name = 'configuración del sitio'
        verbose_name_plural = 'configuración del sitio'

    def __str__(self):
        return f'Configuración de {self.nombre_gimnasio}'

    def save(self, *args, **kwargs):
        """Fuerza el patrón singleton: siempre se guarda como la fila pk=1."""
        self.pk = 1
        super().save(*args, **kwargs)
        # Limpia cualquier fila duplicada que pudiera existir por carreras.
        ConfiguracionSitio.objects.exclude(pk=1).delete()

    @classmethod
    def obtener_configuracion(cls):
        """Devuelve la configuración existente o la crea con valores por defecto."""
        configuracion, _ = cls.objects.get_or_create(pk=1)
        return configuracion
