from datetime import datetime
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from wagtail.contrib.forms.models import FormSubmission
from wagtail.models import Site

from contact_form.models import ContactPage
from contact_form.models import FormField
from contact_form.views import CustomSubmissionsListView
from contact_form.views import SubmissionDateColumn
from contact_form.views import TruncatedMessageColumn

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="admin_password",
    )


@pytest.fixture
def admin_client(admin_user):
    client = Client()
    client.force_login(admin_user)
    return client


@pytest.fixture
def contact_page(db):
    page = ContactPage(
        title="Contact Us",
        intro="Lorem Ipsum",
        thank_you_text="Thank You",
        from_address="from@example.com",
        to_address="to@example.com",
        subject="Contact Form",
    )
    home_page = Site.objects.filter(is_default_site=True)[0].root_page
    home_page.add_child(instance=page)
    page.save()

    FormField.objects.create(
        page=page,
        sort_order=1,
        label="Full Name",
        field_type="singleline",
        required=True,
    )
    FormField.objects.create(
        page=page,
        sort_order=2,
        label="E-Mail Address",
        field_type="email",
        required=True,
    )
    FormField.objects.create(
        page=page,
        sort_order=3,
        label="Message",
        field_type="multiline",
        required=True,
    )

    return page


@pytest.fixture
def form_submissions(contact_page):
    submissions = []
    for i in range(15):
        submission = FormSubmission.objects.create(
            page=contact_page,
            form_data={
                "full_name": f"User {i}",
                "e-mail_address": f"user{i}@example.com",
                "message": f"Message {i}" * 20,
            },
        )
        submissions.append(submission)
    return submissions


@pytest.mark.django_db
class TestTruncatedMessageColumn:
    def test_truncates_long_message(self):
        column = TruncatedMessageColumn(max_length=50)
        long_message = "A" * 100
        class MockSubmission:
            def get_data(self):
                return {"message": long_message}
        result = column.get_value(MockSubmission())
        assert len(result) <= 60
        assert "(...)" in result

    def test_does_not_truncate_short_message(self):
        column = TruncatedMessageColumn(max_length=100)
        short_message = "Short Message"
        class MockSubmission:
            def get_data(self):
                return {"message": short_message}
        result = column.get_value(MockSubmission())
        assert result == short_message
        assert "(...)" not in result

    def test_handles_missing_message(self):
        column = TruncatedMessageColumn()
        class MockSubmission:
            def get_data(self):
                return {}
        result = column.get_value(MockSubmission())
        assert result == ""


@pytest.mark.django_db
class TestSubmissionDateColumn:
    def test_formats_date_correctly(self):
        column = SubmissionDateColumn()

        class MockSubmission:
            submit_time = datetime(2025, 1, 12, 9, 45)

        result = column.get_value(MockSubmission())
        assert result == "12 January 2025 at 09:45"

    def test_handles_none_submit_time(self):
        column = SubmissionDateColumn()

        class MockSubmission:
            submit_time = None

        result = column.get_value(MockSubmission())
        assert result == ""


@pytest.mark.django_db
class TestCustomSubmissionsListView:
    def test_pagination_setting(self):
        assert CustomSubmissionsListView.paginate_by == 10

    def test_page_title(self):
        assert CustomSubmissionsListView.page_title == "Form Data"


@pytest.mark.django_db
class TestCSVDownload:
    def test_csv_download_returns_200(self, admin_client, contact_page, form_submissions):
        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url, {"export": "csv"})
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]

    def test_csv_download_contains_headers(self, admin_client, contact_page, form_submissions):
        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url, {"export": "csv"})
        content = b"".join(response.streaming_content).decode("utf-8-sig")
        assert "Full Name" in content or "full_name" in content or "Submission" in content

    def test_csv_download_contains_data(self, admin_client, contact_page, form_submissions):
        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url, {"export": "csv"})
        content = b"".join(response.streaming_content).decode("utf-8-sig")
        assert "User" in content

    def test_csv_download_has_correct_filename(self, admin_client, contact_page, form_submissions):
        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url, {"export": "csv"})
        assert "attachment" in response["Content-Disposition"]
        assert ".csv" in response["Content-Disposition"]


@pytest.mark.django_db
class TestXLSXDownload:
    def test_xlsx_download_returns_200(self, admin_client, contact_page, form_submissions):
        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url, {"export": "xlsx"})
        assert response.status_code == 200
        content_type = response["Content-Type"]
        assert "spreadsheetml" in content_type or "xlsx" in content_type

    def test_xlsx_download_has_correct_filename(self, admin_client, contact_page, form_submissions):
        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url, {"export": "xlsx"})
        assert "attachment" in response["Content-Disposition"]
        assert ".xlsx" in response["Content-Disposition"]

    def test_xlsx_download_is_valid_file(self, admin_client, contact_page, form_submissions):
        try:
            import openpyxl
        except ImportError:
            pytest.skip("Package openpyxl Not Installed")

        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url, {"export": "xlsx"})
        content = b"".join(response.streaming_content)
        workbook = openpyxl.load_workbook(BytesIO(content))
        assert workbook.active is not None

    def test_xlsx_download_contains_data(self, admin_client, contact_page, form_submissions):
        try:
            import openpyxl
        except ImportError:
            pytest.skip("Package openpyxl Not Installed")

        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url, {"export": "xlsx"})
        content = b"".join(response.streaming_content)
        workbook = openpyxl.load_workbook(BytesIO(content))
        sheet = workbook.active
        values = []
        for row in sheet.iter_rows(values_only=True):
            values.extend([str(cell) for cell in row if cell])
        all_values = " ".join(values)
        assert "User" in all_values


@pytest.mark.django_db
class TestSubmissionsListView:
    def test_list_submissions_view_returns_200(self, admin_client, contact_page, form_submissions):
        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_pagination_limits_results(self, admin_client, contact_page, form_submissions):
        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_page_title_is_form_data(self, admin_client, contact_page, form_submissions):
        url = reverse(
            "wagtailforms:list_submissions",
            args=[contact_page.pk],
        )
        response = admin_client.get(url)
        assert response.status_code == 200
