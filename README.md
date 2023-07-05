# Contact Form

## Description

A very basic contact form with CAPTCHA module that protects you against spam based on two articles from LearnWagtail website (["Contact Forms"](https://learnwagtail.com/tutorials/contact-forms) and ["Adding Recaptcha to Your Contact Forms"](https://learnwagtail.com/tutorials/adding-recaptcha-to-your-contact-forms)).

> **Note**
> As of version `1.0.0` of [`dj-apps-contact_form`](https://github.com/FilipWozniak/dj-apps-contact_form), reCAPTCHA V3 is now supported, while reCAPTCHA V2 is deprecated.

### Configuration

1. Register reCAPTCHA V3 keys on the [reCAPTCHA Admin console](https://www.google.com/recaptcha/admin/create).

![img.png](README/Register%20New%20Site.png)

2. Add the following entries to the `settings.py` file.

```python
RECAPTCHA_PUBLIC_KEY = ''
RECAPTCHA_PRIVATE_KEY = ''

RECAPTCHA_REQUIRED_SCORE = 0.85

RECAPTCHA_DOMAIN = 'www.recaptcha.net'
```

3. Remember to configure your email settings correctly (this refers to variables such as `EMAIL_BACKEND`, `EMAIL_HOST` etc.), as without these settings `Django` will most likely return `ConnectionRefusedError` while attempting to submit the form.

### Installing

Installation process is exactly the same as for regular [Django application](https://docs.djangoproject.com/en/3.2/intro/tutorial01/).

If you follow the convention of storing reusable applications in the `apps` folder, please remember to add these three lines to the `manage.py` file.

```python
from os.path import abspath, dirname, join
PROJECT_ROOT = abspath(dirname(__file__))
sys.path.append(join(PROJECT_ROOT, "apps"))
```

```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "landing_page.settings.dev")

    from os.path import abspath, dirname, join
    PROJECT_ROOT = abspath(dirname(__file__))
    sys.path.append(join(PROJECT_ROOT, "apps"))

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
```

### Dependencies

- django-widget-tweaks (https://github.com/jazzband/django-widget-tweaks)
- wagtail-django-recaptcha (https://github.com/springload/wagtail-django-recaptcha)
```python
INSTALLED_APPS = [
    "captcha",
    "wagtailcaptcha",
    "widget_tweaks"
]
```

- `wagtail.contrib.forms`
```python
INSTALLED_APPS = [
    'wagtail.contrib.forms'
]
```

### Common Issues

Note that if you are using MacOS you may stumble across `URLError` while trying to submit the form.

```shell script
URLError at /contact-us/
<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] Certificate Verify Failed: Unable to Get Local Issuer Certificate (_ssl.c:1122)>
```

As regards to "[Scraping: SSL: CERTIFICATE_VERIFY_FAILED](https://stackoverflow.com/questions/50236117/scraping-ssl-certificate-verify-failed-error-for-http-en-wikipedia-org)" issue on [Stack Overflow](https://stackoverflow.com), all you need to do is go to *Macintosh HD* → *Applications* → *Python* folder and double click on **Install Certificates.command** file.

![URL Error](./contact_form/README/URL%20Error.png)

## Screenshots

#### Contact Form

![Contact Us](./contact_form/README/Contact%20Us.png)

#### "Thank You" Page

!["Thank You" Page](./contact_form/README/Thank%20You%20Page.png)

## Form Fields 

- Full Name
- E-Mail Address
- Message
- CAPTCHA

> **Warning**
> As you can see from the code snippet below, form fields are not rendered dynamically, which means you need to name labels identically as mentioned above — `Full Name`, `E-Mail Address`, `Message` (the `CAPTCHA` field is generated automatically, you do not need to define it in the backend).

```python
<div class="col-12 col-sm-6">
    <div class="form-group mb-3">
        <label for="full_name">Full Name</label>
        {% render_field form.full_name placeholder=form.full_name.label class="form-control" %}
        <small class="form-text text-muted">{{ form.full_name.field.help_text }}</small>
    </div>
</div>
```

> **Note**
> Please remember that if you have saved a form with different labels than those mentioned, you must delete the form page and create it again with the correct values.

## Custom Form Fields 
- *Intro* Text
- *Thank You* Text
- E-Mail ("From" Address)
- E-Mail ("To" Address)
- E-Mail Subject

## Authors

[Filip Woźniak](https://github.com/FilipWozniak)