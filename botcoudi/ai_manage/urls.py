from django.urls import path
from . import views

app_name = 'ai_manage'

urlpatterns = [
    path('configuracion/', views.ai_configuracion, name='configuracion'),
    path('prompts/', views.ai_prompts, name='prompts'),
]
