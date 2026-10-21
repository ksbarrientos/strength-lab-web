"""Comando para poblar los datos iniciales del sitio.

Uso:
    python manage.py poblar_contenido

Es idempotente: puede ejecutarse varias veces sin duplicar registros.
"""

from django.core.management.base import BaseCommand

from apps.configuracion.models import ConfiguracionSitio
from apps.planes.models import PlanEntrenamiento


class Command(BaseCommand):
    help = 'Puebla los planes de entrenamiento y la configuración inicial del sitio.'

    def handle(self, *args, **options):
        self._poblar_planes()
        self._poblar_configuracion()
        self.stdout.write(self.style.SUCCESS('Datos iniciales poblados correctamente.'))

    def _poblar_planes(self):
        planes = [
            {
                'nombre': 'Plan Élite',
                'precio': '200.00',
                'sesiones_texto': '20 sesiones',
                'descripcion': 'Entrenamiento intensivo para resultados de élite.',
                'beneficios': 'Seguimiento personalizado\nPlan nutricional\nAcceso completo a instalaciones',
                'es_popular': True,
                'orden': 1,
            },
            {
                'nombre': 'Plan Progreso',
                'precio': '150.00',
                'sesiones_texto': '15 sesiones',
                'descripcion': 'Ideal para quienes buscan avance constante.',
                'beneficios': 'Asesoría de entrenador\nRutina personalizada\nAcceso a instalaciones',
                'es_popular': False,
                'orden': 2,
            },
            {
                'nombre': 'Plan Inicial',
                'precio': '100.00',
                'sesiones_texto': '10 sesiones',
                'descripcion': 'Perfecto para comenzar tu transformación.',
                'beneficios': 'Rutina inicial guiada\nAcceso a instalaciones',
                'es_popular': False,
                'orden': 3,
            },
            {
                'nombre': 'Plan Básico',
                'precio': '45.00',
                'sesiones_texto': '',
                'descripcion': 'Acceso básico para mantenerte activo.',
                'beneficios': 'Acceso a instalaciones',
                'es_popular': False,
                'orden': 4,
            },
        ]

        for datos in planes:
            plan, creado = PlanEntrenamiento.objects.update_or_create(
                nombre=datos['nombre'], defaults=datos
            )
            accion = 'creado' if creado else 'actualizado'
            self.stdout.write(f'  Plan {plan.nombre} {accion}.')

    def _poblar_configuracion(self):
        config = ConfiguracionSitio.obtener_configuracion()
        config.nombre_gimnasio = config.nombre_gimnasio or 'Strength Lab'
        config.horarios = (
            'Lunes a Viernes: 5:00am - 10:00pm\n'
            'Sábado: 7:00am - 3:00pm'
        )
        config.direccion = 'Merliot, El Salvador'
        config.numero_whatsapp = config.numero_whatsapp or '+50378538605'
        config.save()
        self.stdout.write('  Configuración del sitio actualizada.')
