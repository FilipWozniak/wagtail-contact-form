from __future__ import annotations

from typing import Any

import django_filters
from django.utils.html import format_html
from wagtail.admin.filters import DateRangePickerWidget
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.ui.tables import Column
from wagtail.contrib.forms.models import FormSubmission
from wagtail.contrib.forms.views import SubmissionsListView


class SubmissionFilterSet(WagtailFilterSet):
    submit_time = django_filters.DateFromToRangeFilter(
        label="Submission Date",
        widget=DateRangePickerWidget,
    )

    class Meta:
        model = FormSubmission
        fields = ["submit_time"]


class TruncatedMessageColumn(Column):
    def __init__(
        self,
        name: str = "message",
        label: str = "Message",
        max_length: int = 100,
        **kwargs: Any,
    ):
        self.max_length = max_length
        super().__init__(name=name, label=label, **kwargs)

    def get_value(self, instance: Any) -> str:
        form_data = instance.get_data()
        message = form_data.get("message", "")
        if len(message) > self.max_length:
            return format_html("{} (...)", message[: self.max_length])
        return message


class SubmissionDateColumn(Column):
    def __init__(
        self,
        name: str = "submit_time",
        label: str = "Submission Date",
        **kwargs: Any,
    ):
        super().__init__(name=name, label=label, sort_key="submit_time", **kwargs)

    def get_value(self, instance: Any) -> str:
        submit_time = instance.submit_time
        if submit_time:
            return submit_time.strftime("%-d %B %Y at %H:%M")
        return ""


class CustomSubmissionsListView(SubmissionsListView):
    paginate_by = 10
    page_title = "Form Data"
    filterset_class = SubmissionFilterSet

    @property
    def columns(self) -> list[Column]:
        columns = []
        data_fields = self.form_page.get_data_fields()
        for name, label in data_fields:
            if name == "submit_time":
                continue
            elif name == "message":
                columns.append(TruncatedMessageColumn(name=name, label=label))
            else:
                columns.append(Column(name, label=label))
        columns.append(SubmissionDateColumn())
        return columns

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        return context
