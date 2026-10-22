from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings

from .models import PlanEntrenamiento


class ImagenesPlanesTests(TestCase):
    """Pruebas del campo de portada y de su asociación con los planes."""

    def _poblar(self):
        """Ejecuta el comando sin ensuciar la salida de los tests."""
        call_command('poblar_contenido', stdout=StringIO())

    def test_asocia_la_portada_si_existe(self):
        with TemporaryDirectory() as temporal:
            carpeta = Path(temporal) / 'planes'
            carpeta.mkdir()
            (carpeta / 'plan-elite.jpg').write_bytes(b'portada')

            with override_settings(MEDIA_ROOT=temporal):
                self._poblar()

            plan = PlanEntrenamiento.objects.get(nombre='Plan Élite')
            self.assertEqual(plan.imagen.name, 'planes/plan-elite.jpg')

    def test_no_asocia_portada_si_falta(self):
        with TemporaryDirectory() as temporal:
            with override_settings(MEDIA_ROOT=temporal):
                self._poblar()

            plan = PlanEntrenamiento.objects.get(nombre='Plan Élite')
            self.assertFalse(plan.imagen)

    def test_la_landing_muestra_la_portada(self):
        with TemporaryDirectory() as temporal:
            carpeta = Path(temporal) / 'planes'
            carpeta.mkdir()
            (carpeta / 'plan-elite.jpg').write_bytes(b'portada')

            with override_settings(MEDIA_ROOT=temporal):
                self._poblar()
                respuesta = self.client.get('/')

        self.assertContains(respuesta, '/media/planes/plan-elite.jpg')
