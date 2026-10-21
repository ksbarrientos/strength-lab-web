from django import forms

# Clases compartidas para los campos del formulario (estética oscura).
CLASES_INPUT = (
    'w-full px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-700 '
    'text-white placeholder-zinc-500 focus:outline-none focus:ring-2 '
    'focus:ring-red-500'
)
CLASES_LABEL = 'block text-sm font-semibold text-zinc-300 mb-1'
CLASES_ERROR = 'text-red-400 text-sm mt-1'


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
    telefono = forms.CharField(
        label='Teléfono / WhatsApp',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': CLASES_INPUT,
            'placeholder': 'Ej.: +503 1234-5678',
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
