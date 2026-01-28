from django.urls import path
from wagtail.contrib.forms.views import DeleteSubmissionsView
from wagtail.contrib.forms.views import get_submissions_list_view

from contact_form.views import CustomFormPagesListView

app_name = "wagtailforms"

urlpatterns = [
    path("", CustomFormPagesListView.as_view(), name="index"),
    path(
        "results/",
        CustomFormPagesListView.as_view(results_only=True),
        name="index_results",
    ),
    path(
        "submissions/<int:page_id>/",
        get_submissions_list_view,
        name="list_submissions",
    ),
    path(
        "submissions/<int:page_id>/results/",
        get_submissions_list_view,
        {"results_only": True},
        name="list_submissions_results",
    ),
    path(
        "submissions/<int:page_id>/delete/",
        DeleteSubmissionsView.as_view(),
        name="delete_submissions",
    ),
]
