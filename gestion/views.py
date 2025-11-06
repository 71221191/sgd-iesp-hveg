# gestion/views.py

from django.shortcuts import render
from .models import Documento, Movimiento
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .forms import DocumentoForm, DerivacionForm, AtenderForm
from django.db.models import Count # Para hacer conteos agrupados
from django.utils import timezone  # Para obtener la fecha actual
import csv
from django.http import HttpResponse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from decouple import config


# Create your views here.
@login_required
def listar_documentos(request):
    perfil_usuario_actual = request.user.perfilusuario
    
    # --- LÓGICA DE FILTRADO BASE POR ROL ---
    if perfil_usuario_actual.rol.nombre in ["Mesa de Partes", "Dirección General"]:
        base_queryset = Documento.objects.all()
    else:
        base_queryset = Documento.objects.filter(responsable_actual=perfil_usuario_actual)

    # --- INICIO DE LA NUEVA LÓGICA DE FILTROS ---
    
    # Capturamos los valores de los filtros desde la URL (método GET)
    tipo_filter = request.GET.get('tipo', '')
    estado_filter = request.GET.get('estado', '')
    query = request.GET.get('q', '')

    # Aplicamos los filtros al queryset base si tienen algún valor
    if tipo_filter:
        base_queryset = base_queryset.filter(tipo=tipo_filter)
    
    if estado_filter:
        base_queryset = base_queryset.filter(estado=estado_filter)
        
    if query:
        base_queryset = base_queryset.filter(
            Q(expediente_id__icontains=query) |
            Q(asunto__icontains=query) |
            Q(remitente__icontains=query)
        )

    # El queryset final es el resultado de todos los filtros aplicados
    queryset_filtrado = base_queryset

    context = {
        'documentos': queryset_filtrado,
        # Devolvemos los filtros actuales a la plantilla para mantener su estado
        'query_actual': query,
        'tipo_actual': tipo_filter,
        'estado_actual': estado_filter,
        # Pasamos las opciones de los modelos para construir los <select> en el HTML
        'tipos_documento': Documento.TIPO_DOCUMENTO_CHOICES,
        'estados_documento': Documento.ESTADO_DOCUMENTO_CHOICES,
    }
    return render(request, 'gestion/listar_documentos.html', context)

@login_required
def detalle_documento(request, expediente_id):
    documento = get_object_or_404(Documento, expediente_id=expediente_id)
    
    # Obtenemos todos los movimientos relacionados con este documento.
    # 'documento.movimiento_set.all()' es como Django hace la "búsqueda inversa"
    # desde un documento hacia todos sus movimientos.
    historial_movimientos = documento.movimiento_set.all()

    context = {
        'documento': documento,
        'historial': historial_movimientos # <-- Pasamos el historial al contexto
    }
    return render(request, 'gestion/detalle_documento.html', context)

# --- NUEVA VISTA PARA CREAR ---
@login_required
def crear_documento(request):
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            nuevo_documento = form.save()
            
            # --- LÓGICA MEJORADA ---
            Movimiento.objects.create(
                documento=nuevo_documento,
                # Ahora usamos el usuario logueado. 'request.user' es el User.
                # '.perfilusuario' es como accedemos al perfil desde el User.
                usuario_origen=request.user.perfilusuario, 
                unidad_destino=nuevo_documento.responsable_actual,
                tipo='creacion',
                observaciones="Expediente creado en el sistema."
            )
            return redirect('lista_documentos')
    else:
        form = DocumentoForm()
    return render(request, 'gestion/crear_documento.html', {'form': form})

# --- NUEVA VISTA PARA EDITAR ---
@login_required
def editar_documento(request, expediente_id):
    # Primero, obtenemos el objeto que queremos editar
    documento = get_object_or_404(Documento, expediente_id=expediente_id)

    # La lógica es casi idéntica a la de 'crear_documento'
    if request.method == 'POST':
        # La diferencia clave: pasamos 'instance=documento'
        # para que el formulario sepa que estamos editando un objeto existente.
        form = DocumentoForm(request.POST, request.FILES, instance=documento)
        if form.is_valid():
            form.save()
            # Redirigimos a la página de detalle del MISMO documento editado
            return redirect('detalle_documento', expediente_id=documento.expediente_id)
    else:
        # Si es un GET, creamos el formulario y también pasamos 'instance=documento'
        # para que los campos aparezcan rellenos con los datos actuales.
        form = DocumentoForm(instance=documento)

    # Renderizamos la plantilla, que podemos reutilizar o crear una nueva.
    # Por claridad, creemos una nueva.
    return render(request, 'gestion/editar_documento.html', {'form': form, 'documento': documento})

# --- NUEVA VISTA PARA ELIMINAR ---
@login_required
def eliminar_documento(request, expediente_id):
    # Buscamos el documento que se va a eliminar
    documento = get_object_or_404(Documento, expediente_id=expediente_id)

    # Solo si la petición es POST, procederemos con la eliminación
    if request.method == 'POST':
        # El método delete() elimina el objeto de la base de datos
        documento.delete()
        # Redirigimos al usuario a la lista de documentos
        return redirect('lista_documentos')

    # Si la petición es GET, mostramos la página de confirmación
    return render(request, 'gestion/eliminar_documento.html', {'documento': documento})

# --- NUEVA VISTA PARA DERIVAR ---
@login_required
def derivar_documento(request, expediente_id):
    documento = get_object_or_404(Documento, expediente_id=expediente_id)

    if request.method == 'POST':
        form = DerivacionForm(request.POST)
        if form.is_valid():
            nuevo_responsable = form.cleaned_data['unidad_destino']
            obs = form.cleaned_data['observaciones']
            
            # --- GUARDAMOS LOS DATOS ANTES DE MODIFICARLOS ---
            remitente = request.user.perfilusuario
            
            Movimiento.objects.create(
                documento=documento,
                usuario_origen=remitente,
                unidad_destino=nuevo_responsable,
                observaciones=obs,
                tipo='derivacion'
            )
            
            documento.responsable_actual = nuevo_responsable
            documento.estado = 'derivado'
            documento.save()

            # --- INICIO DE LA LÓGICA DE ENVÍO DE CORREO ---
            try:
                subject = f"Nuevo Trámite Asignado: {documento.expediente_id}"
                contexto_email = {
                    'nombre_destinatario': nuevo_responsable.usuario.first_name or nuevo_responsable.usuario.username,
                    'documento': documento,
                    'nombre_remitente': remitente.usuario.get_full_name() or remitente.usuario.username,
                    'unidad_remitente': remitente.unidad_organizativa,
                    'fecha': timezone.now().strftime('%d/%m/%Y a las %H:%M'),
                    'observaciones': obs or "Ninguna."
                }
                
                # Renderizamos el template de texto
                cuerpo_email = render_to_string('gestion/email/notificacion_derivacion.txt', contexto_email)

                send_mail(
                    subject,
                    cuerpo_email,
                    config('EMAIL_HOST_USER'), # El remitente
                    [nuevo_responsable.usuario.email], # La lista de destinatarios
                    fail_silently=False,
                )
            except Exception as e:
                # En un proyecto real, aquí registraríamos el error en un log.
                # Por ahora, simplemente lo imprimimos en la consola.
                print(f"ERROR al enviar correo: {e}")
            # --- FIN DE LA LÓGICA DE ENVÍO DE CORREO ---

            return redirect('detalle_documento', expediente_id=documento.expediente_id)
    else:
        form = DerivacionForm()

    return render(request, 'gestion/derivar_documento.html', {
        'form': form,
        'documento': documento
    })


def consulta_expediente(request):
    documento = None
    error = None
    query = ""

    # Si el formulario ha sido enviado (método POST)
    if request.method == 'POST':
        query = request.POST.get('expediente_id', '').strip()
        
        if query:
            try:
                # Buscamos el documento por su ID exacto (insensible a mayúsculas/minúsculas)
                documento = Documento.objects.get(expediente_id__iexact=query)
            except Documento.DoesNotExist:
                # Si no se encuentra, preparamos un mensaje de error
                error = "No se encontró ningún expediente con ese ID. Verifique el número e inténtelo de nuevo."
        else:
            error = "Por favor, ingrese un número de expediente."

    context = {
        'documento': documento,
        'error': error,
        'query': query, # Para mantener el número buscado en el campo del formulario
    }
    return render(request, 'gestion/consulta_expediente.html', context)

# --- NUEVA VISTA PARA ATENDER DOCUMENTOS ---
@login_required
def atender_documento(request, expediente_id):
    documento = get_object_or_404(Documento, expediente_id=expediente_id)
    
    # Simple control de permisos: solo el responsable actual puede atenderlo.
    if documento.responsable_actual != request.user.perfilusuario:
        # Aquí podrías redirigir a un error de "no tienes permiso"
        # Por ahora, lo mandamos de vuelta a la lista.
        return redirect('lista_documentos')

    if request.method == 'POST':
        form = AtenderForm(request.POST, request.FILES)
        if form.is_valid():
            proveido = form.cleaned_data['proveido']
            archivo_respuesta = form.cleaned_data['archivo_respuesta']

            # 1. Creamos el movimiento final de atención
            Movimiento.objects.create(
                documento=documento,
                usuario_origen=request.user.perfilusuario,
                unidad_destino=None, # El destino es nulo porque el trámite termina aquí
                observaciones=proveido,
                tipo='atencion'
            )
            
            # (Opcional) Si se sube un archivo de respuesta, lo guardamos.
            # Aquí podrías guardarlo en un modelo separado o asociarlo al documento principal.
            # Por simplicidad, por ahora solo lo registramos, pero no lo guardamos en un campo.

            # 2. Actualizamos el estado del documento principal
            documento.estado = 'atendido'
            documento.responsable_actual = None # ¡Clave! Lo quitamos de las bandejas activas
            documento.save()
            
            return redirect('detalle_documento', expediente_id=documento.expediente_id)
    else:
        form = AtenderForm()
        
    context = {
        'form': form,
        'documento': documento
    }
    return render(request, 'gestion/atender_documento.html', context)

@login_required
def reportes_dashboard(request):
    if request.user.perfilusuario.rol.nombre != "Dirección General":
        return redirect('lista_documentos')

    now = timezone.now()

    # 1. Estadísticas Generales (estas se quedan igual)
    total_documentos = Documento.objects.count()
    documentos_pendientes = Documento.objects.exclude(estado__in=['atendido', 'archivado']).count()
    documentos_finalizados = Documento.objects.filter(estado__in=['atendido', 'archivado']).count()
    finalizados_mes_actual = Documento.objects.filter(
        estado__in=['atendido', 'archivado'],
        fecha_ingreso__year=now.year,
        fecha_ingreso__month=now.month
    ).count()

    # --- INICIO DE LA LÓGICA MEJORADA PARA EL GRÁFICO ---
    # 2. Datos para el Gráfico (Documentos por Estado)
    docs_por_estado = Documento.objects.values('estado')\
                                      .annotate(total=Count('id'))\
                                      .order_by('-total')

    # Para mostrar los nombres bonitos ("Recibido" en vez de "recibido") en el gráfico
    estado_display_map = dict(Documento.ESTADO_DOCUMENTO_CHOICES)
    chart_labels = [estado_display_map.get(item['estado'], item['estado']) for item in docs_por_estado]
    chart_data = [item['total'] for item in docs_por_estado]
    # --- FIN DE LA LÓGICA MEJORADA ---

    context = {
        'titulo': "Panel de Reportes y Estadísticas",
        'total_documentos': total_documentos,
        'documentos_pendientes': documentos_pendientes,
        'documentos_finalizados': documentos_finalizados,
        'finalizados_mes_actual': finalizados_mes_actual,
        'docs_por_estado': docs_por_estado, # Pasamos los nuevos datos
        'estado_display_map': estado_display_map, # Pasamos el "diccionario" de nombres
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }
    return render(request, 'gestion/reportes_dashboard.html', context)

# Añade esta vista al final
@login_required
def exportar_documentos_csv(request):
    if request.user.perfilusuario.rol.nombre != "Dirección General":
        return redirect('lista_documentos')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reporte_documentos.csv"'
    
    response.write(u'\ufeff'.encode('utf8')) # Para que Excel entienda acentos (UTF-8 BOM)
    writer = csv.writer(response)
    
    # Escribir la cabecera
    writer.writerow(['ID Expediente', 'Tipo', 'Asunto', 'Remitente', 'Fecha Ingreso', 'Estado', 'Responsable', 'Unidad'])
    
    documentos = Documento.objects.all()
    for doc in documentos:
        responsable_user = doc.responsable_actual.usuario.username if doc.responsable_actual else 'No asignado'
        responsable_unidad = doc.responsable_actual.unidad_organizativa if doc.responsable_actual else 'N/A'
        writer.writerow([
            doc.expediente_id,
            doc.get_tipo_display(),
            doc.asunto,
            doc.remitente,
            doc.fecha_ingreso.strftime('%d/%m/%Y %H:%M'),
            doc.get_estado_display(),
            responsable_user,
            responsable_unidad
        ])
    
    return response
