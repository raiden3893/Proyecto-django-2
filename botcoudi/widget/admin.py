"""
Administración Django para los modelos del módulo widget.
Registra WidgetConversation, WidgetMessage, AICallLog y Lead.
"""

from django.contrib import admin
from .models import WidgetConversation, WidgetMessage, AICallLog, Lead, WidgetFlowBlock


@admin.register(WidgetConversation)
class WidgetConversationAdmin(admin.ModelAdmin):
    """Administración de conversaciones del widget."""
    list_display = ("id", "session_id", "created_at", "updated_at")
    search_fields = ("session_id",)
    ordering = ("-updated_at",)
    readonly_fields = ("lead_state",)


@admin.register(WidgetMessage)
class WidgetMessageAdmin(admin.ModelAdmin):
    """Administración de mensajes del widget."""
    list_display = ("id", "conversation", "role", "content_preview", "provider", "created_at")
    list_filter = ("role", "provider")
    search_fields = ("content", "conversation__session_id")
    ordering = ("-created_at",)

    def content_preview(self, obj):
        """Muestra una vista previa corta del contenido del mensaje."""
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content
    content_preview.short_description = "Contenido"


@admin.register(AICallLog)
class AICallLogAdmin(admin.ModelAdmin):
    """Administración de logs de llamadas a IA."""
    list_display = ("id", "provider", "model_name", "status", "latency_ms", "created_at")
    list_filter = ("provider", "status")
    ordering = ("-created_at",)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """Administración de leads finales capturados."""
    list_display = (
        "nombre",
        "telefono",
        "email",
        "disponibilidad",
        "estado",
        "fuente",
        "created_at",
    )
    list_filter = ("estado", "fuente", "created_at")
    search_fields = ("nombre", "telefono", "email")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "metadata", "conversation")


@admin.register(WidgetFlowBlock)
class WidgetFlowBlockAdmin(admin.ModelAdmin):
    """Administración de bloques del flujo conversacional."""
    list_display = ("order", "name", "block_type", "required_field", "validation_type", "is_required", "is_active")
    list_filter = ("block_type", "validation_type", "is_required", "is_active")
    search_fields = ("name", "message", "required_field", "validation_type")
    ordering = ("order",)
