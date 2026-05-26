from django.urls import path
from . import views

app_name = 'widget'

urlpatterns = [
    path('prueba/', views.prueba_widget, name='prueba'),
    path('configuracion-conversacion/', views.configuracion_conversacion, name='configuracion_conversacion'),
    path('api/mensaje/', views.api_mensaje, name='api_mensaje'),
]
