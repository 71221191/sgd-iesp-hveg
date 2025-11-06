# gestion/admin.py

from django.contrib import admin
# IMPORTAMOS los nuevos modelos
from .models import Documento, Movimiento, Rol, PerfilUsuario

class MovimientoInline(admin.TabularInline):
    model = Movimiento
    extra = 0
    readonly_fields = ('fecha_movimiento', 'usuario_origen', 'unidad_destino') # Hacemos más campos de solo lectura

class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('expediente_id', 'asunto', 'remitente', 'responsable_actual', 'estado', 'fecha_ingreso')
    search_fields = ('expediente_id', 'asunto', 'remitente')
    list_filter = ('estado', 'tipo') # Añadimos filtros
    inlines = [MovimientoInline]

# Registramos los nuevos modelos
admin.site.register(Rol)
admin.site.register(PerfilUsuario)

# Registramos Documento y Movimiento con sus clases personalizadas
admin.site.register(Documento, DocumentoAdmin)
admin.site.register(Movimiento)