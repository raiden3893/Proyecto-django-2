from django.contrib import admin

from .forms import AIProviderConfigForm
from .models import AIProviderConfig, AIPromptTemplate


@admin.register(AIProviderConfig)
class AIProviderConfigAdmin(admin.ModelAdmin):
    """Administración de proveedores de IA."""

    form = AIProviderConfigForm

    list_display = (
        "provider",
        "model_name",
        "priority",
        "is_enabled",
        "failure_policy",
        "updated_at",
    )

    list_filter = (
        "provider",
        "is_enabled",
        "failure_policy",
    )

    search_fields = (
        "provider",
        "model_name",
    )

    ordering = (
        "priority",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Proveedor y modelo",
            {
                "fields": ("provider", "model_name", "priority", "is_enabled"),
            },
        ),
        (
            "Política de fallo",
            {
                "fields": ("failure_policy", "failure_threshold", "cooldown_seconds"),
            },
        ),
        (
            "Metadatos",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    class Media:
        js = ("ai_manage/js/provider_model_filter.js",)


@admin.register(AIPromptTemplate)
class AIPromptTemplateAdmin(admin.ModelAdmin):
    """Administración de prompts de IA."""

    list_display = (
        "name",
        "use_case",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "use_case",
        "is_active",
    )

    search_fields = (
        "name",
        "description",
        "system_prompt",
        "user_prompt_template",
    )

    ordering = (
        "use_case",
        "name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Identidad",
            {
                "fields": ("name", "use_case", "is_active"),
            },
        ),
        (
            "Descripción",
            {
                "fields": ("description",),
            },
        ),
        (
            "Prompts",
            {
                "fields": ("system_prompt", "user_prompt_template"),
            },
        ),
        (
            "Metadatos",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
