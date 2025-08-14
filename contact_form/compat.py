import wagtail
from packaging import version

# Parse Wagtail version as a Version object for comparisons
WAGTAIL_VERSION = version.parse(getattr(wagtail, "__version__", "0"))

# Admin panels (FieldRowPanel may not be available in newer versions)
try:
    from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
    try:
        from wagtail.admin.panels import FieldRowPanel  # type: ignore
    except Exception:
        FieldRowPanel = None  # type: ignore
except Exception:  # Fallback, not expected for Wagtail 6/7
    from wagtail.admin.edit_handlers import FieldPanel, InlinePanel, MultiFieldPanel  # type: ignore
    try:
        from wagtail.admin.edit_handlers import FieldRowPanel  # type: ignore
    except Exception:
        FieldRowPanel = None  # type: ignore

# Fields
from wagtail.fields import RichTextField

# Forms (contrib)
from wagtail.contrib.forms.forms import FormBuilder
from wagtail.contrib.forms.models import (
    AbstractEmailForm,
    AbstractFormField,
    FormSubmission,
)

# Core models
from wagtail.models import Page, Site