from __future__ import annotations

from typing import Any

import django_filters
from django.utils.functional import cached_property
from django.utils.functional import classproperty
from wagtail.admin.filters import DateRangePickerWidget
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.paginator import WagtailPaginator
from wagtail.admin.ui.tables import DateColumn
from wagtail.admin.views.pages.listing import PageListingMixin
from wagtail.contrib.forms.models import FormSubmission
from wagtail.contrib.forms.views import FormPagesListView
from wagtail.contrib.forms.views import SubmissionsListView
from wagtail.contrib.forms.views import TitleColumn
from wagtail.models import Page


class SubmissionFilterSet(WagtailFilterSet):
    submit_time = django_filters.DateFromToRangeFilter(
        label="Submission Date",
        widget=DateRangePickerWidget,
    )

    class Meta:
        model = FormSubmission
        fields = ["submit_time"]


class FormSubmissionPaginator(WagtailPaginator):
    @cached_property
    def verbose_name(self) -> str:
        return "Form Submission"

    @cached_property
    def verbose_name_plural(self) -> str:
        return "Form Submissions"


class FormPagePaginator(WagtailPaginator):
    @cached_property
    def verbose_name(self) -> str:
        return "Page"

    @cached_property
    def verbose_name_plural(self) -> str:
        return "Pages"


class CustomSubmissionsListView(SubmissionsListView):
    paginate_by = 10
    page_title = "Form Data"
    filterset_class = SubmissionFilterSet
    paginator_class = FormSubmissionPaginator

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        if self.is_export:
            return context

        data_fields = self.form_page.get_data_fields()
        submissions = context.get("submissions", [])

        non_date_fields = [
            (field_name, field_label)
            for field_name, field_label in data_fields
            if field_name != "submit_time"
        ]
        reordered_fields = non_date_fields + [("submit_time", "Submission Date")]

        ordering_by_field = self.get_validated_ordering()
        orderable_fields = self.orderable_fields
        data_headings = []
        for name, label in reordered_fields:
            order_label = None
            if name in orderable_fields:
                order = ordering_by_field.get(name)
                if order:
                    order_label = order[1]
                else:
                    order_label = "orderable"
            data_headings.append(
                {
                    "name": name,
                    "label": label,
                    "order": order_label,
                }
            )

        data_rows = []
        for submission in submissions:
            form_data = submission.get_data()
            data_row = []
            for name, label in reordered_fields:
                if name == "submit_time":
                    submit_time = submission.submit_time
                    if submit_time:
                        val = submit_time.strftime("%-d %B %Y at %H:%M")
                    else:
                        val = ""
                elif name == "message":
                    val = form_data.get(name, "")
                    if isinstance(val, list):
                        val = ", ".join(val)
                    if len(val) > 100:
                        val = val[:100] + " (...)"
                else:
                    val = form_data.get(name)
                    if isinstance(val, list):
                        val = ", ".join(val)
                data_row.append(val)
            data_rows.append({"model_id": submission.id, "fields": data_row})

        context.update(
            {
                "data_headings": data_headings,
                "data_rows": data_rows,
            }
        )

        return context


class CustomDateColumn(DateColumn):
    cell_template_name = "wagtailadmin/tables/custom_date_cell.html"


class FormPagesFilterSet(WagtailFilterSet):
    latest_revision_created_at = django_filters.DateFromToRangeFilter(
        label="Updated",
        widget=DateRangePickerWidget,
    )

    class Meta:
        model = Page
        fields = ["latest_revision_created_at"]


class CustomFormPagesListView(FormPagesListView):
    filterset_class = FormPagesFilterSet
    paginator_class = FormPagePaginator

    @classproperty
    def columns(cls) -> list:
        base_columns = [
            col for col in PageListingMixin.columns if col.name not in {"title", "type", "status"}
        ]

        columns = []
        for col in base_columns:
            if col.name == "latest_revision_created_at":
                columns.append(
                    CustomDateColumn(
                        "latest_revision_created_at",
                        label="Updated",
                        sort_key="latest_revision_created_at",
                        width="20%",
                    )
                )
            else:
                columns.append(col)

        columns.insert(
            1,
            TitleColumn(
                "title",
                classname="title",
                label="Title",
                url_name="wagtailforms:list_submissions",
                sort_key="title",
                width="30%",
            ),
        )

        return columns
