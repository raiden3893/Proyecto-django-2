from django import forms

from .models import WidgetFlowBlock


class WidgetFlowBlockForm(forms.ModelForm):
    class Meta:
        model = WidgetFlowBlock
        fields = (
            "order",
            "name",
            "message",
            "is_required",
            "is_active",
        )
        widgets = {
            "order": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
