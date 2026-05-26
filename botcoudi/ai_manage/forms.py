from django import forms

from .models import AIProviderConfig, AI_MODEL_CHOICES, MODEL_PROVIDER_MAP


class AIProviderConfigForm(forms.ModelForm):
    class Meta:
        model = AIProviderConfig
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        provider_value = None
        if self.data:
            provider_value = self.data.get(self.add_prefix("provider"))
        elif self.instance and self.instance.pk:
            provider_value = self.instance.provider
        else:
            provider_value = self.initial.get("provider")

        self.fields["model_name"].choices = self._build_model_choices(provider_value)

        for field_name in ("timeout_seconds", "cooldown_seconds"):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    "step": "any",
                    "inputmode": "decimal",
                })

    @staticmethod
    def _build_model_choices(provider_value):
        provider_value = (provider_value or "").strip().lower()
        available_models = [
            (model_id, display_name)
            for model_id, display_name in AI_MODEL_CHOICES
            if MODEL_PROVIDER_MAP.get(model_id) == provider_value
        ]
        return [("", "---------")] + available_models if available_models else [("", "Seleccione un proveedor primero")]

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get("provider")
        model_name = cleaned_data.get("model_name")

        if provider and model_name:
            expected_provider = MODEL_PROVIDER_MAP.get(model_name)
            if expected_provider is None:
                self.add_error("model_name", "El modelo seleccionado no es válido.")
            elif expected_provider != provider:
                self.add_error("model_name", "El modelo seleccionado no corresponde al proveedor elegido.")

        return cleaned_data
