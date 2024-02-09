import pytest
from wagtail.contrib.forms.models import FormSubmission
from wagtail.models import Site

from contact_form.models import ContactPage
from contact_form.models import FormField


@pytest.fixture
def form_submission_data():
    return {
        "full_name": "John Doe",
        "email_address": "john@example.com",
        "message": "This is a test message.",
        "wagtailcaptcha": "03AFcWeA5-DcunrWYpbA2QAv8BVc6g9t20BOtFdu39nCUrPUL4V3iINznl1wIA0dVSN2xPIlVSHRaqElcZoc4HFEPlx_Z8QEOuBNsIxGdBjjegDI4WTIRXxyThKOUYrG1RXflAIAPL3HQPaxxDoY7ro17URTBdTtImKyyTbeiZCjfaoUpCgNtPCDIx8m8CEO9amqd_leCTsS_sE0lYihTyMVrOknRxWwFDzL0w_HHKNrR3VpehRuqiRHJ6xM1FNMP8e43gF88e-JqZIKqmRT9yn3pP59WR_ZO8QqVhNlW_N-xjfSzNFBTnHUrwv1ACzG5KrOr8Rro_audAgMyXIPqZ2A6KwYL123zNg0-QJxudvBYG4Y3fx0pE6C9x3f1z0jmfh8CgpY9Xv3mZvqDsUhWGYdHy1bQZdPT94TNA5I4bTxsI308izapbAR4QGoxrLva21DJC_-sjHgKVFtrua2996_AZ6neoN7dDC7KQmIYKM8a7BK_KGLJ-hu4U1G-v769k6rs1YQNmv8lVCp0f4Tyfs5A0tQLJwemSOimQH0fikpaY0w1uo0uyY5Bpt8irNUKlGHKfoZKuTxpHH0dDzAivsVkCP5Opha_xXGYVQ2mulW0S2TWcNouPK6E",
    }


# Single Line Text: "singleline"
# Multi-Line Text: "multiline"
# Email: "email"
# Number: "number"
# URL: "url"
# Checkbox: "checkbox"
# Checkboxes: "checkboxes"
# Dropdown: "dropdown"
# Multiple Select: "multiselect"
# Radio Buttons: "radio"
# Date: "date"
# Date/Time: "datetime"
# Hidden Field: "hidden"


@pytest.mark.django_db
class TestContactPage:
    @pytest.fixture
    def contact_page(self):
        """
        Fixture to create a ContactPage instance for testing.
        """
        page = ContactPage(
            title="Contact Us",
            intro="We're here to help and answer any questions you might have. We look forward to hearing from you.",
            thank_you_text="Thank you for your submission!",
            from_address="example@example.com",
            to_address="admin@example.com",
            subject="Message from the Website (Contact Form)",
        )
        home_page = Site.objects.filter(is_default_site=True)[0].root_page
        home_page.add_child(instance=page)
        page.save()
        return page

    def test_contact_page_url(self, client, contact_page):
        """
        Test the URL of the ContactPage to ensure it returns a 200 status code.
        """
        response = client.get(contact_page.url)
        assert response.status_code == 200

    def test_create_contact_page(self, contact_page):
        """
        Test the creation of a ContactPage instance and its attributes.
        """
        assert contact_page.title == "Contact Us"
        assert (
            contact_page.intro
            == "We're here to help and answer any questions you might have. We look forward to hearing from you."
        )
        assert contact_page.landing_page_template == "contact_form/contact_page_landing.html"

    def test_create_form_fields(self, contact_page):
        """
        Test the creation of form fields for the ContactPage.
        """
        full_name_field = FormField.objects.create(
            page=contact_page,
            sort_order=1,
            label="Full Name",
            field_type="singleline",
            required=True,
        )
        email_address_field = FormField.objects.create(
            page=contact_page,
            sort_order=2,
            label="Email Address",
            field_type="email",
            required=True,
        )
        message_field = FormField.objects.create(
            page=contact_page, sort_order=3, label="Message", field_type="multiline", required=True
        )

        assert full_name_field.page == contact_page
        assert full_name_field.label == "Full Name"
        assert full_name_field.field_type == "singleline"
        assert full_name_field.required

        assert email_address_field.page == contact_page
        assert email_address_field.label == "Email Address"
        assert email_address_field.field_type == "email"
        assert email_address_field.required

        assert message_field.page == contact_page
        assert message_field.label == "Message"
        assert message_field.field_type == "multiline"
        assert message_field.required

        assert contact_page.form_fields.count() == 3

    def test_send_form_submission_successfully(self, client, contact_page, form_submission_data):
        """
        Test the successful submission of a form on the ContactPage.
        """
        response = client.post(contact_page.url, form_submission_data)
        assert response.status_code == 200

    def test_form_submission_database_save(self, contact_page, form_submission_data):
        """
        Test the saving of form submission data to the database.
        """
        FormSubmission.objects.create(
            form_data=form_submission_data,
            page=contact_page,
        )
        latest_submission = FormSubmission.objects.last()
        assert latest_submission is not None
        assert latest_submission.form_data["full_name"] == "John Doe"
        assert latest_submission.form_data["email_address"] == "john@example.com"
        assert latest_submission.form_data["message"] == "This is a test message."

    def test_custom_base_template(self, client, settings, contact_page):
        """
        Test that the default base template is used.
        """
        # settings.INSTALLED_APPS.append('cjkcms')
        response = client.get(contact_page.url)
        assert response.status_code == 200
        assert "base.html" in [template.name for template in response.templates]

    def test_form_submission_email_sent(self, client, contact_page, form_submission_data):
        """
        Test that an email is sent when the contact form is successfully submitted.
        """
        response = client.post(contact_page.url, form_submission_data)
        assert response.status_code
