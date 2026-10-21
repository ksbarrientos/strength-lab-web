from django.db import models


class PlanEntrenamiento(models.Model):
    """Plan de entrenamiento ofrecido en el sitio."""

    nombre = models.CharField('nombre', max_length=100)
    precio = models.DecimalField('precio', max_digits=8, decimal_places=2)
    sesiones_texto = models.CharField(
        'sesiones',
        max_length=100,
        help_text='Ej.: "8 sesiones al mes".',
    )
    descripcion = models.TextField('descripción', blank=True)
    beneficios = models.TextField(
        'beneficios',
        blank=True,
        help_text='Un beneficio por línea.',
    )
    es_popular = models.BooleanField('es el más popular', default=False)
    orden = models.PositiveIntegerField('orden de despliegue', default=0)
    activo = models.BooleanField('activo', default=True)

    class Meta:
        verbose_name = 'plan de entrenamiento'
        verbose_name_plural = 'planes de entrenamiento'
        ordering = ['orden']

    def __str__(self):
        return self.nombre
