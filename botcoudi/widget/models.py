from django.db import models

class WidgetConversation(models.Model):
    """
    Representa una sesión de conversación en el widget.
    """
    session_id = models.CharField(max_length=255, unique=True, help_text="ID único de la sesión del navegador")
    lead_state = models.JSONField(default=dict, blank=True, help_text="Estado temporal de la captura de lead")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversación {self.session_id} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

class WidgetMessage(models.Model):
    """
    Guarda cada mensaje enviado o recibido en el widget.
    """
    ROLE_CHOICES = [
        ('user', 'Usuario'),
        ('assistant', 'Asistente'),
        ('system', 'Sistema'),
    ]

    conversation = models.ForeignKey(WidgetConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    provider = models.CharField(max_length=50, null=True, blank=True, help_text="openai o claude")
    model_name = models.CharField(max_length=100, null=True, blank=True)
    metadata_json = models.JSONField(null=True, blank=True, help_text="Información extra de la respuesta")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."

class AICallLog(models.Model):
    """
    Registra cada llamada a las APIs de IA para auditoría y fallback.
    """
    STATUS_CHOICES = [
        ('success', 'Éxito'),
        ('failed', 'Fallido'),
        ('fallback', 'Fallback'),
    ]

    provider = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    request_json = models.JSONField(null=True, blank=True)
    response_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider} ({self.status}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class Lead(models.Model):
    """
    Modelo para almacenar los datos finales del lead capturado.
    """
    conversation = models.OneToOneField(
        WidgetConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead"
    )

    nombre = models.CharField(max_length=255)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    disponibilidad = models.CharField(max_length=255, blank=True)

    ESTADOS = [
        ("completed", "Completado"),
        ("incomplete", "Incompleto"),
    ]

    estado = models.CharField(max_length=20, choices=ESTADOS, default="completed")
    fuente = models.CharField(max_length=50, default="widget")

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Lead"
        verbose_name_plural = "Leads"

    def __str__(self):
        return f"Lead: {self.nombre} ({self.get_estado_display()})"


class WidgetFlowBlock(models.Model):
    """
    Bloques configurables del flujo conversacional del widget.
    """
    class ValidationType(models.TextChoices):
        TEXT = "texto", "Texto"
        PHONE = "telefono", "Teléfono"
        EMAIL = "email", "Email"
        SCHEDULE = "horario", "Horario"
        NONE = "ninguno", "Ninguno"

    class BlockType(models.TextChoices):
        GREETING = "greeting", "Saludo inicial"
        NAME = "name", "Nombre"
        PHONE = "phone", "Teléfono"
        EMAIL = "email", "E-mail"
        INSIST = "insist", "Insistir"
        AVAILABILITY = "availability", "Disponibilidad"
        CLOSING = "closing", "Cierre"
        CUSTOM = "custom", "Mensaje personalizado"
        CONTEXTUAL = "contextual", "Respuesta contextual"
        MENU = "menu", "Menú"

    name = models.CharField(max_length=255, help_text="Nombre del bloque.")
    block_type = models.CharField(max_length=50, choices=BlockType.choices)
    order = models.PositiveIntegerField(default=1, help_text="Orden del bloque en el flujo.")
    message = models.TextField(help_text="Mensaje que se mostrará al usuario.")
    required_field = models.CharField(
        max_length=50,
        blank=True,
        help_text="Campo que se espera capturar (nombre, telefono, email, disponibilidad)."
    )
    validation_type = models.CharField(
        max_length=20,
        choices=ValidationType.choices,
        default=ValidationType.NONE,
        help_text="Tipo de validación esperada para el bloque.",
    )
    is_required = models.BooleanField(default=True, help_text="Si este bloque es obligatorio.")
    is_active = models.BooleanField(default=True, help_text="Si este bloque está activo.")
    metadata_json = models.JSONField(default=dict, blank=True, help_text="Metadatos opcionales del bloque.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order",)
        verbose_name = "Bloque de flujo del widget"
        verbose_name_plural = "Bloques de flujo del widget"

    def __str__(self):
        return f"{self.order}. {self.name} ({self.block_type})"

    @property
    def field_key(self):
        return self.required_field
