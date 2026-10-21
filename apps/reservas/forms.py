import re
from datetime import timedelta

from django import forms
from django.utils import timezone

# Clases compartidas para los campos del formulario (estética oscura).
CLASES_INPUT = (
    'w-full px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-700 '
    'text-white placeholder-zinc-500 focus:outline-none focus:ring-2 '
    'focus:ring-red-500'
)
CLASES_LABEL = 'block text-sm font-semibold text-zinc-300 mb-1'
CLASES_ERROR = 'text-red-400 text-sm mt-1'

# Estética de la página /agendar/: réplica de la referencia (fondo casi negro,
# borde tenue y acento rojo al enfocar).
CLASES_INPUT_AGENDAR = (
    'w-full bg-zinc-950/60 border border-zinc-700 rounded-xl px-4 py-3 '
    'text-white placeholder-zinc-500 focus:outline-none focus:border-acento '
    'focus:ring-1 focus:ring-acento transition-colors'
)

# El select lleva menos padding horizontal para que quepa "El Salvador (+503)".
CLASES_SELECT_AGENDAR = (
    'w-full bg-zinc-950/60 border border-zinc-700 rounded-xl pl-3 pr-7 py-3 '
    'text-xs sm:text-sm text-white focus:outline-none focus:border-acento '
    'focus:ring-1 focus:ring-acento transition-colors'
)

# Selector de código de país: El Salvador es el público objetivo, por eso va
# primero y como valor inicial.
CODIGOS_PAIS = (
    ('+503', 'El Salvador +503'),
    ('+1', 'EE. UU. / Canadá +1'),
    ('+502', 'Guatemala +502'),
    ('+504', 'Honduras +504'),
    ('+506', 'Costa Rica +506'),
    ('+52', 'México +52'),
)

# Horarios preferidos de la página /agendar/. La etiqueta es la que se muestra
# y se registra en Sheets; la hora exacta (Calendar) se toma de
# ConfiguracionSitio.hora_manana / hora_tarde.
HORARIOS = (
    ('manana', 'Mañana'),
    ('tarde', 'Tarde'),
)

# Días en que el gimnasio no atiende (0 = lunes … 6 = domingo). La referencia
# deshabilita los domingos en su calendario, así que se validan igual.
DIAS_CERRADOS = (6,)

# Ventana máxima para agendar: evita fechas absurdas y mantiene el calendario
# del cliente alineado con la validación del servidor.
DIAS_MAXIMOS_RESERVA = 90


def _limpiar_nombre(valor):
    """Normaliza y valida el nombre: sin números y con al menos una letra."""
    nombre = ' '.join(valor.split())
    if len(nombre) < 3:
        raise forms.ValidationError('Escribe tu nombre completo.')
    if re.search(r'\d', nombre):
        raise forms.ValidationError('El nombre no puede contener números.')
    if not re.search(r'[^\W\d_]', nombre):
        raise forms.ValidationError('Escribe un nombre válido.')
    return nombre


def _limpiar_telefono(valor):
    """Valida que el teléfono traiga solo dígitos locales (sin código de país).

    El usuario digita únicamente el número local (ej.: 7853-8605); se
    eliminan espacios, guiones, puntos y paréntesis, y se exigen entre 7 y
    12 dígitos.
    """
    telefono = re.sub(r'[\s\-().]', '', valor)
    if not telefono.isdigit() or not 7 <= len(telefono) <= 12:
        raise forms.ValidationError(
            'Ingresa solo los dígitos de tu número local (ej.: 78538605), '
            'sin espacios, guiones ni el código de país.'
        )
    return telefono


class HiddenInputSinRequired(forms.HiddenInput):
    """Input oculto sin el atributo `required`.

    Los campos ocultos con `required` hacen que el navegador bloquee el envío
    sin mostrar ningún mensaje (no puede enfocar el campo). La obligatoriedad
    la valida Django y, del lado del cliente, el script del calendario.
    """

    def use_required_attribute(self, initial):
        return False


class FormularioReserva(forms.Form):
    """Formulario de solicitud de día gratis.

    No está ligado a un modelo: los leads se guardan 100% en Google Sheets
    para no consumir cuota de base de datos en el alojamiento gratuito.
    """

    nombre = forms.CharField(
        label='Nombre completo',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': CLASES_INPUT,
            'placeholder': 'Tu nombre',
            'autofocus': True,
        }),
    )
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={
            'class': CLASES_INPUT,
            'placeholder': 'tucorreo@ejemplo.com',
        }),
    )
    codigo_pais = forms.ChoiceField(
        label='Código de país',
        choices=CODIGOS_PAIS,
        initial='+503',
        widget=forms.Select(attrs={
            'class': CLASES_INPUT,
        }),
    )
    telefono = forms.CharField(
        label='Teléfono / WhatsApp',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': CLASES_INPUT,
            'placeholder': 'Ej.: 7853-8605',
            'inputmode': 'numeric',
        }),
    )
    fecha_visita = forms.DateField(
        label='Fecha de la cita',
        widget=forms.DateInput(attrs={
            'class': CLASES_INPUT,
            'type': 'date',
        }),
    )
    hora_visita = forms.TimeField(
        label='Hora de la cita',
        widget=forms.TimeInput(attrs={
            'class': CLASES_INPUT,
            'type': 'time',
        }),
    )
    notas = forms.CharField(
        label='Notas u objetivos',
        required=False,
        widget=forms.Textarea(attrs={
            'class': CLASES_INPUT,
            'rows': 3,
            'placeholder': 'Cuéntanos qué te gustaría lograr (opcional)',
        }),
    )

    def clean_nombre(self):
        return _limpiar_nombre(self.cleaned_data['nombre'])

    def clean_telefono(self):
        return _limpiar_telefono(self.cleaned_data['telefono'])


class FormularioAgendar(forms.Form):
    """Formulario de la página dedicada `/agendar/`.

    Réplica del flujo del sitio de referencia: datos personales, día en un
    calendario propio y horario por bloques (mañana/tarde). La fecha y el
    horario viajan en inputs ocultos que llena el calendario en JavaScript.
    """

    HORARIOS = HORARIOS

    nombre = forms.CharField(
        label='Nombre completo',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': CLASES_INPUT_AGENDAR,
            'placeholder': 'Nombre completo',
            'autocomplete': 'name',
            'autofocus': True,
        }),
    )
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={
            'class': CLASES_INPUT_AGENDAR,
            'placeholder': 'Correo electrónico',
            'autocomplete': 'email',
        }),
    )
    codigo_pais = forms.ChoiceField(
        label='Código de país',
        choices=CODIGOS_PAIS,
        initial='+503',
        widget=forms.Select(attrs={
            'class': CLASES_SELECT_AGENDAR,
            'aria-label': 'Código de país',
        }),
    )
    telefono = forms.CharField(
        label='Teléfono / WhatsApp',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': CLASES_INPUT_AGENDAR,
            'placeholder': 'Teléfono / WhatsApp',
            'inputmode': 'numeric',
            'autocomplete': 'tel-national',
        }),
    )
    fecha_visita = forms.DateField(
        label='Día de la visita',
        widget=HiddenInputSinRequired(attrs={'id': 'id_fecha_visita'}),
        error_messages={'required': 'Elige el día de tu visita.'},
    )
    horario = forms.ChoiceField(
        label='Horario preferido',
        choices=HORARIOS,
        widget=HiddenInputSinRequired(attrs={'id': 'id_horario'}),
        error_messages={
            'required': 'Elige mañana o tarde.',
            'invalid_choice': 'Elige mañana o tarde.',
        },
    )

    def clean_nombre(self):
        return _limpiar_nombre(self.cleaned_data['nombre'])

    def clean_telefono(self):
        return _limpiar_telefono(self.cleaned_data['telefono'])

    def clean_fecha_visita(self):
        fecha = self.cleaned_data['fecha_visita']
        hoy = timezone.localdate()

        if fecha < hoy:
            raise forms.ValidationError('Elige una fecha a partir de hoy.')
        if fecha > hoy + timedelta(days=DIAS_MAXIMOS_RESERVA):
            raise forms.ValidationError(
                f'Solo puedes agendar hasta {DIAS_MAXIMOS_RESERVA} días adelante.'
            )
        if fecha.weekday() in DIAS_CERRADOS:
            raise forms.ValidationError('Ese día el gimnasio está cerrado.')
        return fecha
