from __future__ import annotations

from typing import Any

from django import forms


class MaskedInputWidget(forms.TextInput):
    template_name = "django/forms/widgets/text.html"
    PLACEHOLDER_HAS_VALUE = "••••••••••••••••"
    PLACEHOLDER_NO_VALUE = ""

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        default_attrs = {"autocomplete": "off"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def format_value(self, value: str | None) -> str:
        return ""

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        if value:
            context["widget"]["attrs"]["placeholder"] = self.PLACEHOLDER_HAS_VALUE
        else:
            context["widget"]["attrs"]["placeholder"] = self.PLACEHOLDER_NO_VALUE
        return context

    def value_from_datadict(self, data: dict[str, Any], files: dict[str, Any], name: str) -> str | None:
        return super().value_from_datadict(data, files, name)
