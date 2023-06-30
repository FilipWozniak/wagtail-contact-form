import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.core import mail
from wagtail.models import Page, Site
from contact_form.models import ContactPage, FormField

@pytest.fixture
def contact_page():
    """
    Fixture that sets up a ContactPage instance for testing.

    Returns:
        ContactPage: Instance of the ContactPage model.
    """
    contact_page = ContactPage(
        title="Contact Us",
        slug="contact-us",
        from_address="contact@example.com",
        to_address="admin@example.com",
        subject="Message from the Website (Contact Form)",
        intro="We’re here to help and answer any questions you might have. We look forward to hearing from you.",
        thank_you_text="Thank You for Your Submission",
    )
    site = Site.objects.get(is_default_site=True)
    site.root_page.add_child(instance=contact_page)
    return contact_page

@pytest.mark.django_db
def test_contact_page_render(client, contact_page):
    """
    Test the rendering of the ContactPage.

    Args:
        client (django.test.Client): The Django test client.
        contact_page (ContactPage): The ContactPage object.

    Asserts:
        - The response status code is 200.
        - The intro text is present in the response content.
    """
    response = client.get(contact_page.url)
    assert response.status_code == 200
    assert contact_page.intro in response.content.decode()

@pytest.mark.django_db
def test_contact_page_context(contact_page):
    """
    Test the context of the ContactPage.

    Args:
        contact_page (ContactPage): The ContactPage object.

    Asserts:
        - The 'seo_pagetitle' and 'seo_description' attributes exist in the ContactPage object.
    """
    request = None
    context = contact_page.get_context(request)
    assert 'seo_pagetitle' in contact_page.__dict__
    assert 'seo_description' in contact_page.__dict__
    assert contact_page.title == 'Contact Us'
    assert contact_page.subject == 'Message from the Website (Contact Form)'
    assert contact_page.intro == 'We’re here to help and answer any questions you might have. We look forward to hearing from you.'
    assert contact_page.thank_you_text == 'Thank You for Your Submission'

@pytest.fixture
@pytest.mark.django_db
def form_field(contact_page):
    """
    Fixture that sets up a FormField instance for testing.

    Args:
        contact_page (ContactPage): Instance of the ContactPage model.

    Returns:
        FormField: Instance of the FormField model.
    """
    return FormField.objects.create(page=contact_page, label='Name', field_type='singleline')

@pytest.mark.django_db
def test_form_field_created(form_field):
    """
    Test that a form field is created with the expected properties.

    Args:
        form_field (FormField): The FormField object.

    Asserts:
        - The label of the form field is 'Name'.
        - The field type of the form field is 'singleline'.
    """
    assert form_field.label == 'Name'
    assert form_field.field_type == 'singleline'
