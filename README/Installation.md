# Installation & Configuration

<h2>Installation (Production)</h2>

1. Install the package from `GitHub`.

   ```python
   pip install git+https://github.com/FilipWozniak/wagtail-contact-form.git
   ```

2. Add the application and its dependencies to the `INSTALLED_APPS` in your settings file.

   ```python
   INSTALLED_APPS = [
       "contact_form",

        "django_recaptcha",
        "widget_tweaks",
        
        "wagtail.contrib.forms",
        "wagtail.contrib.settings",
   ]
   ```

<details>
<summary><h2>Installation (Development)</h2></summary>

1. Clone the source code of application from `GitHub`.

   ```python
   mkdir wagtail-contact-form
   cd wagtail-contact-form
   git clone https://github.com/FilipWozniak/wagtail-contact-form .
   ```

2. Navigate to the application directory and execute the following command.

   ```python
   cd wagtail-contact-form
   python -m pip install -e .
   ```

3. Follow steps `2` and `3` from the section above titled `Installation (Production)`.

</details>

