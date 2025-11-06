# gestion/models.py

from django.db import models
# ¡IMPORTANTE! Importamos el modelo User de Django
from django.contrib.auth.models import User 


# --- NUEVOS MODELOS PARA USUARIOS Y ROLES ---

class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class PerfilUsuario(models.Model):
    # Relación uno-a-uno con el modelo User de Django
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True)
    unidad_organizativa = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.usuario.username} - {self.rol.nombre if self.rol else 'Sin rol'}"

class Documento(models.Model):
    # ... (tus campos existentes como TIPO_DOCUMENTO_CHOICES, etc., no cambian) ...
    TIPO_DOCUMENTO_CHOICES = [
        ('solicitud', 'Solicitud'),
        ('oficio', 'Oficio'),
        ('informe', 'Informe'),
        ('constancia', 'Constancia'),
    ]
    ESTADO_DOCUMENTO_CHOICES = [
        ('recibido', 'Recibido'),
        ('en_revision', 'En revisión'),
        ('derivado', 'Derivado'),
        ('en_proceso', 'En proceso'),
        ('atendido', 'Atendido'),
        ('archivado', 'Archivado'),
    ]

    expediente_id = models.CharField(max_length=20, unique=True, verbose_name="ID del Expediente")
    tipo = models.CharField(max_length=20, choices=TIPO_DOCUMENTO_CHOICES, verbose_name="Tipo de Documento")
    remitente = models.CharField(max_length=200, verbose_name="Remitente")
    asunto = models.TextField(verbose_name="Asunto")
    estado = models.CharField(max_length=20, choices=ESTADO_DOCUMENTO_CHOICES, default='recibido', verbose_name="Estado")
    fecha_ingreso = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Ingreso")
    
    # MODIFICACIÓN 1: Enlazamos la unidad actual a un usuario responsable
    # Permitimos que sea nulo por si un documento no está asignado a nadie específico.
    responsable_actual = models.ForeignKey(PerfilUsuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="documentos_a_cargo")
    
    archivo_adjunto = models.FileField(upload_to='documentos/', blank=True, null=True, verbose_name="Archivo Adjunto")

    # Eliminamos 'unidad_actual' porque ahora la obtendremos del 'responsable_actual'
    # def __str__ ... y class Meta ... se mantienen igual

    def __str__(self):
        return f"{self.expediente_id} - {self.asunto}"

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ['-fecha_ingreso']


# --- NUEVO MODELO MOVIMIENTO ---
class Movimiento(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE)
    fecha_movimiento = models.DateTimeField(auto_now_add=True, verbose_name="Fecha del Movimiento")
    
    # MODIFICACIÓN 2: Reemplazamos los CharField por ForeignKey a PerfilUsuario
    usuario_origen = models.ForeignKey(PerfilUsuario, on_delete=models.SET_NULL, null=True, related_name="movimientos_enviados")
    unidad_destino = models.ForeignKey(PerfilUsuario, on_delete=models.SET_NULL, null=True, related_name="movimientos_recibidos")
    
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    
    TIPO_MOVIMIENTO_CHOICES = [
        ('creacion', 'Creación de Expediente'),
        ('derivacion', 'Derivación'),
        ('atencion', 'Atención'),
        ('archivo', 'Archivado'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES)

    def __str__(self):
        origen = self.usuario_origen.unidad_organizativa if self.usuario_origen else "Sistema"
        destino = self.unidad_destino.unidad_organizativa if self.unidad_destino else "N/A"
        return f"Movimiento de {self.documento.expediente_id} de {origen} a {destino}"

    class Meta:
        verbose_name = "Movimiento"
        verbose_name_plural = "Movimientos"
        ordering = ['-fecha_movimiento']