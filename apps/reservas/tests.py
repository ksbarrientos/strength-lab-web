from datetime import time, timedelta
from urllib.parse import unquote_plus
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.configuracion.models import ConfiguracionSitio

from .forms import DIAS_MAXIMOS_RESERVA
class ReservaDiaGratisTests(TestCase):
    """Pruebas del flujo local: POST normal, mensaje y redirección."""

    def setUp(self):
        self.config = ConfiguracionSitio.obtener_configuracion()
        self.config.nombre_gimnasio = 'Strength Lab'
        self.config.numero_whatsapp = '+50378538605'
        self.config.google_sheets_spreadsheet_id = 'hoja-prueba'
        self.config.google_calendar_id = 'calendario-prueba'
        self.config.correo_notificaciones = 'gimnasio@example.com'
        self.config.mensaje_predeterminado_whatsapp = ''
        self.config.save()

        self.url = reverse('reservas:reserva_dia_gratis')
        self.datos = {
            'nombre': 'Ana Pérez',
            'email': 'ana@example.com',
            'codigo_pais': '+503',
            'telefono': '7853-8605',
            'fecha_visita': '2026-11-10',
            'hora_visita': '10:30',
            'notas': 'Quiero ganar fuerza',
        }

    def test_get_muestra_formulario(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Reserva tu día de entrenamiento gratis')

    @patch('apps.reservas.views.threading.Thread')
    def test_post_valido_redirige_a_whatsapp_y_lanza_hilo(self, mock_thread):
        respuesta = self.client.post(self.url, self.datos)

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            respuesta['Location'].startswith('https://wa.me/50378538605?text=')
        )

        # El hilo se crea en modo daemon y arranca una sola vez.
        mock_thread.assert_called_once()
        self.assertTrue(mock_thread.call_args.kwargs['daemon'])
        mock_thread.return_value.start.assert_called_once()

        # Los datos enviados a Google ya son strings serializables.
        args = mock_thread.call_args.kwargs['args']
        self.assertEqual(args[0]['fecha_visita'], '2026-11-10')
        self.assertEqual(args[0]['hora_visita'], '10:30')
        self.assertEqual(args[0]['telefono'], '+50378538605')
        self.assertEqual(args[1], 'hoja-prueba')
        self.assertEqual(args[2], 'calendario-prueba')
        self.assertEqual(args[3], 'gimnasio@example.com')

    @patch('apps.reservas.views.threading.Thread')
    def test_usa_plantilla_configurada(self, mock_thread):
        self.config.mensaje_predeterminado_whatsapp = (
            'Hola, soy {nombre}. Cita: {fecha} {hora}. '
            'Correo: {correo}. Tel: {telefono}.'
        )
        self.config.save()

        respuesta = self.client.post(self.url, self.datos)
        mensaje = unquote_plus(respuesta['Location'])

        self.assertIn('Hola, soy Ana Pérez.', mensaje)
        self.assertIn('Cita: 10/11/2026 10:30.', mensaje)
        self.assertIn('Correo: ana@example.com.', mensaje)
        self.assertIn('Tel: +50378538605.', mensaje)

    @patch('apps.reservas.views.threading.Thread')
    def test_plantilla_vacia_usa_la_interna(self, mock_thread):
        respuesta = self.client.post(self.url, self.datos)
        mensaje = unquote_plus(respuesta['Location'])

        self.assertIn('Hola Strength Lab, soy Ana Pérez.', mensaje)
        self.assertIn('10/11/2026', mensaje)
        self.assertIn('10:30', mensaje)
        self.assertIn('ana@example.com', mensaje)
        self.assertIn('+50378538605', mensaje)

    @patch('apps.reservas.views.threading.Thread')
    def test_marcador_desconocido_se_conserva(self, mock_thread):
        self.config.mensaje_predeterminado_whatsapp = 'Hola {nombre}, plan {plan}.'
        self.config.save()

        respuesta = self.client.post(self.url, self.datos)
        mensaje = unquote_plus(respuesta['Location'])

        self.assertIn('Hola Ana Pérez, plan {plan}.', mensaje)

    @patch('apps.reservas.views.threading.Thread')
    def test_plantilla_invalida_no_rompe_la_reserva(self, mock_thread):
        self.config.mensaje_predeterminado_whatsapp = 'Hola {nombre'
        self.config.save()

        respuesta = self.client.post(self.url, self.datos)
        mensaje = unquote_plus(respuesta['Location'])

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('Hola Strength Lab, soy Ana Pérez.', mensaje)

    @patch('apps.reservas.views.threading.Thread')
    def test_formulario_invalido_no_redirige_ni_lanza_google(self, mock_thread):
        datos = dict(self.datos, telefono='abc')

        respuesta = self.client.post(self.url, datos)

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, 'Ingresa solo los dígitos', status_code=400)
        mock_thread.assert_not_called()


def _dia_habil(dias_adelante=1):
    """Devuelve una fecha futura que no caiga en domingo (el gimnasio cierra)."""
    fecha = timezone.localdate() + timedelta(days=dias_adelante)
    while fecha.weekday() == 6:
        fecha += timedelta(days=1)
    return fecha


def _proximo_domingo():
    """Devuelve el próximo domingo futuro."""
    fecha = timezone.localdate() + timedelta(days=1)
    while fecha.weekday() != 6:
        fecha += timedelta(days=1)
    return fecha


class PaginaAgendarTests(TestCase):
    """Pruebas de la página dedicada /agendar/ (calendario + bloques)."""

    def setUp(self):
        self.config = ConfiguracionSitio.obtener_configuracion()
        self.config.nombre_gimnasio = 'Strength Lab'
        self.config.numero_whatsapp = '+50378538605'
        self.config.google_sheets_spreadsheet_id = 'hoja-prueba'
        self.config.google_calendar_id = 'calendario-prueba'
        self.config.correo_notificaciones = 'gimnasio@example.com'
        self.config.mensaje_predeterminado_whatsapp = ''
        self.config.hora_manana = time(9, 0)
        self.config.hora_tarde = time(16, 0)
        self.config.save()

        self.url = reverse('agendar:pagina_agendar')
        self.fecha = _dia_habil()
        self.datos = {
            'nombre': 'Ana Pérez',
            'email': 'ana@example.com',
            'codigo_pais': '+503',
            'telefono': '7853-8605',
            'fecha_visita': self.fecha.isoformat(),
            'horario': 'manana',
        }

    def test_get_muestra_la_pagina(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Agenda tu')
        self.assertContains(respuesta, 'Tus datos')
        self.assertContains(respuesta, 'Elige tu día')
        self.assertContains(respuesta, 'Horario preferido')
        self.assertContains(respuesta, 'Confirmar por WhatsApp')
        self.assertContains(respuesta, 'id="calendario-dias"')

    def test_la_navegacion_enlaza_la_pagina(self):
        respuesta = self.client.get(reverse('planes:index'))
        self.assertContains(respuesta, 'href="/agendar/"')

    @patch('apps.reservas.views.threading.Thread')
    def test_post_manana_agenda_a_las_09_y_redirige(self, mock_thread):
        respuesta = self.client.post(self.url, self.datos)

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta['Location'].startswith('https://wa.me/50378538605?text='))

        mock_thread.assert_called_once()
        self.assertTrue(mock_thread.call_args.kwargs['daemon'])
        mock_thread.return_value.start.assert_called_once()

        datos_google = mock_thread.call_args.kwargs['args'][0]
        self.assertEqual(datos_google['hora_visita'], '09:00')
        self.assertEqual(datos_google['hora_etiqueta'], 'Mañana')
        self.assertEqual(datos_google['fecha_visita'], self.fecha.isoformat())
        self.assertEqual(datos_google['telefono'], '+50378538605')

        mensaje = unquote_plus(respuesta['Location'])
        self.assertIn(self.fecha.strftime('%d/%m/%Y'), mensaje)
        self.assertIn('09:00 (mañana)', mensaje)

    @patch('apps.reservas.views.threading.Thread')
    def test_post_tarde_agenda_a_las_16(self, mock_thread):
        respuesta = self.client.post(self.url, dict(self.datos, horario='tarde'))

        self.assertEqual(respuesta.status_code, 302)
        datos_google = mock_thread.call_args.kwargs['args'][0]
        self.assertEqual(datos_google['hora_visita'], '16:00')
        self.assertEqual(datos_google['hora_etiqueta'], 'Tarde')
        self.assertIn('16:00 (tarde)', unquote_plus(respuesta['Location']))

    @patch('apps.reservas.views.threading.Thread')
    def test_horas_configurables(self, mock_thread):
        self.config.hora_manana = time(8, 30)
        self.config.hora_tarde = time(17, 45)
        self.config.save()

        self.client.post(self.url, self.datos)
        self.client.post(self.url, dict(self.datos, horario='tarde'))

        primera = mock_thread.call_args_list[0].kwargs['args'][0]
        segunda = mock_thread.call_args_list[1].kwargs['args'][0]
        self.assertEqual(primera['hora_visita'], '08:30')
        self.assertEqual(segunda['hora_visita'], '17:45')

    @patch('apps.reservas.views.threading.Thread')
    def test_domingo_no_permitido(self, mock_thread):
        respuesta = self.client.post(
            self.url, dict(self.datos, fecha_visita=_proximo_domingo().isoformat())
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, 'cerrado', status_code=400)
        mock_thread.assert_not_called()

    @patch('apps.reservas.views.threading.Thread')
    def test_fecha_pasada_no_permitida(self, mock_thread):
        ayer = timezone.localdate() - timedelta(days=1)

        respuesta = self.client.post(self.url, dict(self.datos, fecha_visita=ayer.isoformat()))

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, 'a partir de hoy', status_code=400)
        mock_thread.assert_not_called()

    @patch('apps.reservas.views.threading.Thread')
    def test_fecha_muy_lejana_no_permitida(self, mock_thread):
        lejana = timezone.localdate() + timedelta(days=DIAS_MAXIMOS_RESERVA + 1)

        respuesta = self.client.post(self.url, dict(self.datos, fecha_visita=lejana.isoformat()))

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, 'días adelante', status_code=400)
        mock_thread.assert_not_called()

    @patch('apps.reservas.views.threading.Thread')
    def test_sin_fecha_no_envia(self, mock_thread):
        respuesta = self.client.post(self.url, dict(self.datos, fecha_visita=''))

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, 'Elige el día de tu visita', status_code=400)
        mock_thread.assert_not_called()

    @patch('apps.reservas.views.threading.Thread')
    def test_horario_invalido_no_envia(self, mock_thread):
        respuesta = self.client.post(self.url, dict(self.datos, horario='noche'))

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, 'Elige mañana o tarde', status_code=400)
        mock_thread.assert_not_called()

    @patch('apps.reservas.views.threading.Thread')
    def test_telefono_invalido_no_envia(self, mock_thread):
        respuesta = self.client.post(self.url, dict(self.datos, telefono='abc'))

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, 'Ingresa solo los dígitos', status_code=400)
        mock_thread.assert_not_called()

    @patch('apps.reservas.views.threading.Thread')
    def test_correo_invalido_no_envia(self, mock_thread):
        respuesta = self.client.post(self.url, dict(self.datos, email='no-es-correo'))

        self.assertEqual(respuesta.status_code, 400)
        mock_thread.assert_not_called()

    @patch('apps.reservas.views.threading.Thread')
    def test_codigo_pais_invalido_no_envia(self, mock_thread):
        respuesta = self.client.post(self.url, dict(self.datos, codigo_pais='+999'))

        self.assertEqual(respuesta.status_code, 400)
        mock_thread.assert_not_called()

    @patch('apps.reservas.views.threading.Thread')
    def test_nombre_con_numeros_no_envia(self, mock_thread):
        respuesta = self.client.post(self.url, dict(self.datos, nombre='Ana 123'))

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, 'no puede contener números', status_code=400)
        mock_thread.assert_not_called()

    @patch('apps.reservas.views.threading.Thread')
    def test_telefono_con_parentesis_y_puntos_se_normaliza(self, mock_thread):
        self.client.post(self.url, dict(self.datos, telefono='(785) 386.05'))

        datos_google = mock_thread.call_args.kwargs['args'][0]
        self.assertEqual(datos_google['telefono'], '+50378538605')

    @patch('apps.reservas.views.threading.Thread')
    def test_usa_plantilla_configurada(self, mock_thread):
        self.config.mensaje_predeterminado_whatsapp = 'Hola {nombre}, {fecha} a las {hora}.'
        self.config.save()

        respuesta = self.client.post(self.url, self.datos)
        mensaje = unquote_plus(respuesta['Location'])

        self.assertIn('Hola Ana Pérez, ' + self.fecha.strftime('%d/%m/%Y'), mensaje)
        self.assertIn('09:00 (mañana)', mensaje)

    def test_el_formulario_expone_las_reglas_del_calendario(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, f'const DIAS_MAXIMOS = {DIAS_MAXIMOS_RESERVA};')
