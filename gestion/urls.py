# gestion/urls.py

from django.urls import path
from . import views # Importa las vistas de la aplicación actual


urlpatterns = [
    # Cuando la URL esté vacía (relativo a la app), llama a la vista 'listar_documentos'
    path('', views.listar_documentos, name='lista_documentos'),
    path('nuevo/', views.crear_documento, name='crear_documento'),
    path('<str:expediente_id>/', views.detalle_documento, name='detalle_documento'),
    path('<str:expediente_id>/editar/', views.editar_documento, name='editar_documento'),
    path('<str:expediente_id>/eliminar/', views.eliminar_documento, name='eliminar_documento'),
    path('<str:expediente_id>/derivar/', views.derivar_documento, name='derivar_documento'),
    path('<str:expediente_id>/atender/', views.atender_documento, name='atender_documento'),
]