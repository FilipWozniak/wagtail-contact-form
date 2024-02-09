import pytest
import unittest

from django.forms import ValidationError
from django.utils.translation import gettext_lazy
from wagtail.models import Site
from wagtail.tests.utils import WagtailPageTests
from contact_form.models import ContactPage, FormField
from wagtail.contrib.forms.models import FormSubmission, AbstractFormSubmission


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
            subject="Message from the Website (Contact Form)"
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
        assert contact_page.intro == "We're here to help and answer any questions you might have. We look forward to hearing from you."
        assert contact_page.landing_page_template == "contact_form/contact_page_landing.html"

    def test_create_form_fields(self, contact_page):
        """
        Test the creation of form fields for the ContactPage.
        """
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

        full_name_field = FormField.objects.create(
            page=contact_page, sort_order=1, label="Full Name", field_type="singleline", required=True
        )
        email_address_field = FormField.objects.create(
            page=contact_page, sort_order=2, label="Email Address", field_type="email", required=True
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

    def test_send_form_submission_successfully(self, client, contact_page):
        """
        Test the successful submission of a form on the ContactPage.
        """
        data = {
            'full_name': 'John Doe',
            'email_address': 'john@example.com',
            'message': 'This is a test message.',
        }
        response = client.post(contact_page.url, data)
        assert response.status_code == 200

    def test_form_submission_database_save(self, contact_page):
        """
        Test the saving of form submission data to the database.
        """
        form_submission = FormSubmission.objects.create(
            form_data={
                'full_name': 'John Doe',
                'email_address': 'john@example.com',
                'message': 'This is a test message.',
            },
            page=contact_page,
        )
        latest_submission = FormSubmission.objects.last()
        assert latest_submission is not None
        assert latest_submission.form_data['full_name'] == 'John Doe'
        assert latest_submission.form_data['email_address'] == 'john@example.com'
        assert latest_submission.form_data['message'] == 'This is a test message.'
