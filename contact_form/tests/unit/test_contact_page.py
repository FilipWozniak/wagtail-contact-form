import pytest
import unittest

from django.forms import ValidationError
from django.utils.translation import gettext_lazy
from wagtail.models import Site
from contact_form.models import ContactPage, FormField


@pytest.mark.django_db
class TestContactPage:

    @pytest.fixture
    def contact_page(self):
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

    def test_create_contact_page(self, contact_page):
        assert contact_page.title == "Contact Us"
        assert contact_page.intro == "We're here to help and answer any questions you might have. We look forward to hearing from you."
        assert contact_page.landing_page_template == "contact_form/contact_page_landing.html"

