# gestion/views.py

from django.shortcuts import render
from .models import Documento, Movimiento
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .forms import DocumentoForm, DerivacionForm, AtenderForm


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
            
            # --- LÓGICA MEJORADA ---
            Movimiento.objects.create(
                documento=documento,
                # El origen es el usuario que está realizando la acción (el logueado)
                usuario_origen=request.user.perfilusuario,
                unidad_destino=nuevo_responsable,
                observaciones=obs,
                tipo='derivacion'
            )
            
            documento.responsable_actual = nuevo_responsable
            documento.estado = 'derivado'
            documento.save()
            return redirect('detalle_documento', expediente_id=documento.expediente_id)
    else:
        form = DerivacionForm()
    return render(request, 'gestion/derivar_documento.html', {'form': form, 'documento': documento})


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