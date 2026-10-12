from django import forms
from core.models import AgentSettings, Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            "name", "sector", "website", "email", "phone",
            "address", "description", "knowledge", "system_prompt", "is_active",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "knowledge": forms.Textarea(attrs={"rows": 6}),
            "system_prompt": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "is_active":
                field.widget.attrs.setdefault("class", "input")


class CompanyPromptForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["system_prompt"]
        widgets = {"system_prompt": forms.Textarea(attrs={"rows": 6, "class": "input font-mono text-xs"})}


class AgentSettingsForm(forms.ModelForm):
    prefix = "agent"

    class Meta:
        model = AgentSettings
        fields = ["system_prompt"]
        widgets = {"system_prompt": forms.Textarea(attrs={"rows": 16, "class": "input font-mono text-xs"})}
