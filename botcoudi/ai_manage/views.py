from django.shortcuts import render
from .models import AIProviderConfig, AIPromptTemplate

def dashboard(request):
    """
    Vista general del proyecto.
    """
    return render(request, 'dashboard.html', {
        'title': 'Dashboard de IA',
    })

def ai_configuracion(request):
    """
    Vista para configurar proveedores de IA.
    Carga datos reales si existen en la base de datos.
    """
    configuraciones = AIProviderConfig.objects.all()
    return render(request, 'ai_manage/configuracion.html', {
        'title': 'Configuración de IA',
        'configuraciones': configuraciones,
    })

def ai_prompts(request):
    """
    Vista para administrar plantillas de prompts.
    Carga datos reales si existen en la base de datos.
    """
    prompts = AIPromptTemplate.objects.all()
    return render(request, 'ai_manage/prompts.html', {
        'title': 'Plantillas de Prompts',
        'prompts': prompts,
    })
