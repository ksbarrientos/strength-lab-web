from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.integraciones.google_services import (
    agendar_en_google_calendar,
    registrar_en_google_sheets,
)


class GoogleSheetsTests(SimpleTestCase):
    """La columna de horario debe reflejar el bloque elegido en /agendar/."""

    def setUp(self):
        self.servicio = MagicMock()
        self.datos = {
            'nombre': 'Ana Pérez',
            'telefono': '+50378538605',
            'email': 'ana@example.com',
            'fecha_visita': '2026-11-10',
            'hora_visita': '09:00',
            'hora_etiqueta': 'Mañana',
            'notas': 'Solicitud desde /agendar/',
        }

    def _fila_enviada(self):
        cuerpo = self.servicio.spreadsheets.return_value.values.return_value \
            .append.call_args.kwargs['body']
        return cuerpo['values'][0]

    @patch('apps.integraciones.google_services._obtener_cliente_servicio')
    def test_registra_la_etiqueta_del_bloque_en_la_columna_horario(self, mock_cliente):
        mock_cliente.return_value = self.servicio

        resultado = registrar_en_google_sheets(self.datos, 'hoja-prueba')

        self.assertTrue(resultado)
        fila = self._fila_enviada()
        self.assertEqual(fila[4], '2026-11-10')
        self.assertEqual(fila[5], 'Mañana')
        # El teléfono conserva el '+' (valueInputOption='RAW').
        self.assertEqual(fila[2], '+50378538605')

    @patch('apps.integraciones.google_services._obtener_cliente_servicio')
    def test_sin_etiqueta_registra_la_hora_exacta(self, mock_cliente):
        mock_cliente.return_value = self.servicio
        datos = dict(self.datos)
        datos.pop('hora_etiqueta')

        registrar_en_google_sheets(datos, 'hoja-prueba')

        self.assertEqual(self._fila_enviada()[5], '09:00')


class GoogleCalendarTests(SimpleTestCase):
    """El evento se crea a la hora exacta y guarda el bloque en la descripción."""

    def setUp(self):
        self.servicio = MagicMock()
        self.datos = {
            'nombre': 'Ana Pérez',
            'telefono': '+50378538605',
            'email': 'ana@example.com',
            'fecha_visita': '2026-11-10',
            'hora_visita': '09:00',
            'hora_etiqueta': 'Mañana',
            'notas': 'Solicitud desde /agendar/',
        }

    @patch('apps.integraciones.google_services._obtener_cliente_servicio')
    def test_evento_a_la_hora_del_bloque(self, mock_cliente):
        mock_cliente.return_value = self.servicio

        resultado = agendar_en_google_calendar(self.datos, 'calendario-prueba', '')

        self.assertTrue(resultado)
        evento = self.servicio.events.return_value.insert.call_args.kwargs['body']
        self.assertTrue(evento['start']['dateTime'].endswith('T09:00:00'))
        self.assertIn('Mañana (09:00)', evento['description'])

    @patch('apps.integraciones.google_services._obtener_cliente_servicio')
    def test_sin_etiqueta_no_agrega_el_detalle_del_bloque(self, mock_cliente):
        mock_cliente.return_value = self.servicio
        datos = dict(self.datos)
        datos.pop('hora_etiqueta')

        agendar_en_google_calendar(datos, 'calendario-prueba', '')

        evento = self.servicio.events.return_value.insert.call_args.kwargs['body']
        self.assertIn('Horario preferido: 09:00', evento['description'])
