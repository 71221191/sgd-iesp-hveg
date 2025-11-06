# gestion/forms.py

from django import forms
# ¡IMPORTANTE! Importamos los nuevos modelos para usarlos en los formularios
from .models import Documento, PerfilUsuario

class DocumentoForm(forms.ModelForm):
    # --- MODIFICACIÓN CLAVE ---
    # Ahora el campo para seleccionar el destino será una lista desplegable
    # de todos los perfiles de usuario existentes.
    responsable_actual = forms.ModelChoiceField(
        queryset=PerfilUsuario.objects.all(),
        label="Derivar a (Responsable)",
        empty_label="-- Seleccionar un responsable --"
    )

    class Meta:
        model = Documento
        
        # --- MODIFICACIÓN ---
        # Actualizamos la lista de campos para quitar 'unidad_actual'
        # y añadir nuestro nuevo campo 'responsable_actual'.
        fields = [
            'expediente_id',
            'tipo',
            'remitente',
            'asunto',
            'responsable_actual', # <--- ¡Este es el cambio!
            'archivo_adjunto',
        ]

        labels = {
            'expediente_id': 'Número de Expediente',
            'tipo': 'Tipo de Documento',
            # Ya no necesitamos 'unidad_actual', la etiqueta la pusimos arriba.
            'archivo_adjunto': 'Adjuntar Archivo (Opcional)',
        }

# --- FORMULARIO PARA DERIVACIÓN (también necesita actualizarse) ---
class DerivacionForm(forms.Form):
    # Ahora, en lugar de un campo de texto, será una lista de usuarios/perfiles
    unidad_destino = forms.ModelChoiceField(
        queryset=PerfilUsuario.objects.all(),
        label="Derivar al Usuario/Unidad",
        widget=forms.Select(attrs={'class': 'form-select'}) # Usamos un select de Bootstrap
    )
    observaciones = forms.CharField(
        label="Observaciones o Instrucciones",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )

# --- NUEVO FORMULARIO PARA ATENDER TRÁMITES ---
class AtenderForm(forms.Form):
    proveido = forms.CharField(
        label="Proveído o Respuesta Final",
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        help_text="Escriba aquí la conclusión, resolución o respuesta para este trámite."
    )
    archivo_respuesta = forms.FileField(
        label="Adjuntar Documento de Salida (Opcional)",
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )