from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


AI_MODEL_CHOICES = (
    ("gpt-4o-mini", "GPT-4o mini"),
    ("claude-haiku-4-5", "Claude Haiku 4.5"),
)

MODEL_PROVIDER_MAP = {
    "gpt-4o-mini": "openai",
    "claude-haiku-4-5": "claude",
}


class AIProviderConfig(models.Model):
    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        CLAUDE = "claude", "Claude"

    class FailurePolicy(models.TextChoices):
        FALLBACK = "fallback", "Cambiar al siguiente proveedor"

    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        unique=True,
        verbose_name="Proveedor",
    )
    model_name = models.CharField(
        max_length=100,
        choices=AI_MODEL_CHOICES,
        verbose_name="Modelo",
        help_text="Seleccione un modelo válido para el proveedor elegido.",
    )
    priority = models.PositiveIntegerField(
        default=1,
        verbose_name="Prioridad",
        help_text="Un número menor significa mayor prioridad.",
    )
    is_enabled = models.BooleanField(default=True, verbose_name="Activo")
    timeout_seconds = models.DecimalField(
        default=Decimal("5"),
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Tiempo máximo de espera",
        help_text="Segundos de espera antes de agotar el intento (acepta decimales).",
    )
    max_retries = models.PositiveIntegerField(default=2, verbose_name="Reintentos máximos")
    failure_policy = models.CharField(
        max_length=20,
        choices=FailurePolicy.choices,
        default=FailurePolicy.FALLBACK,
        blank=True,
        verbose_name="Política de fallo",
    )
    failure_threshold = models.PositiveIntegerField(
        default=1,
        verbose_name="Umbral de fallos",
        help_text="Cantidad de fallos consecutivos antes de considerar degradado el proveedor.",
    )
    cooldown_seconds = models.DecimalField(
        default=Decimal("0"),
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Tiempo de enfriamiento",
        help_text="Segundos de espera antes de volver a intentar usar este proveedor (acepta decimales).",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    class Meta:
        ordering = ("priority",)
        verbose_name = "Configuración de proveedor de IA"
        verbose_name_plural = "Configuraciones de proveedores de IA"

    def __str__(self) -> str:
        return f"{self.get_provider_display()} - {self.get_model_name_display()} - Prioridad {self.priority}"

    def clean(self):
        super().clean()

        if not self.model_name:
            return

        expected_provider = MODEL_PROVIDER_MAP.get(self.model_name)
        if expected_provider is None:
            raise ValidationError({
                "model_name": "El modelo seleccionado no es válido.",
            })

        if expected_provider != self.provider:
            raise ValidationError({
                "model_name": "El modelo seleccionado no corresponde al proveedor elegido.",
            })


class AIPromptTemplate(models.Model):
    class UseCase(models.TextChoices):
        CHAT_EXTRACTION = "chat_extraction", "Extracción de datos del chat"
        SPAM_VALIDATION = "spam_validation", "Validación de spam"
        LEAD_ANALYSIS = "lead_analysis", "Análisis de leads"
        LEAD_PRIORITY = "lead_priority", "Priorización de leads"
        # Caso de uso para extracción guiada de leads desde el widget.
        LEAD_CAPTURE_EXTRACTION = "lead_capture_extraction", "Extracción de datos de lead"
        GENERIC = "generic", "Uso general"

    name = models.CharField(max_length=255, verbose_name="Nombre")
    use_case = models.CharField(max_length=100, choices=UseCase.choices, verbose_name="Caso de uso")
    description = models.TextField(blank=True, verbose_name="Descripción")
    system_prompt = models.TextField(verbose_name="Prompt del sistema")
    user_prompt_template = models.TextField(verbose_name="Plantilla del prompt de usuario")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    class Meta:
        ordering = ("use_case", "name")
        unique_together = ("name", "use_case")
        indexes = [
            models.Index(fields=["use_case", "is_active"]),
        ]
        verbose_name = "Plantilla de prompt de IA"
        verbose_name_plural = "Plantillas de prompts de IA"

    def __str__(self) -> str:
        return f"{self.get_use_case_display()}: {self.name}"
