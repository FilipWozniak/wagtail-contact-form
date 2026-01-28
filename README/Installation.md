# Installation & Configuration

<details>
<summary><h2>Installation (Production)</h2></summary>

1. Install the package from `GitHub`.

   ```python
   pip install git+https://github.com/FilipWozniak/wagtail-contact-form.git
   ```

2. Add the application and its dependencies to the `INSTALLED_APPS` in your settings file.

   ```python
   INSTALLED_APPS = [
       "contact_form",

        "django_recaptcha",
        "widget_tweaks"
   ]
   ```

   Most systems will already have ```wagtail.contrib.forms``` in `INSTALLED_APPS` - if not, add it, too.

</details>

<details>
<summary><h2>Installation (Development)</h2></summary>

If you want install a `Python` application in editable mode, you can use the editable mode provided by `pip`.

1. Clone the application's source code:

   ```python
   git clone https://github.com/FilipWozniak/wagtail-contact-form .
   ```

2. Navigate to the root directory of the application's source code in the terminal or command prompt.

3. Install the application in editable mode.

   Use the pip install command with the `-e` or `--editable` flag followed by a period (`.`) to specify the current
   directory (where the application's `setup.py` file is located).

   ```python
   pip install -e .
   ```

   Replace the `.` with the path to the directory if you're running the command from a different location.

4. Add the application and its dependencies to the `INSTALLED_APPS` in the `settings.py` file.

   ```python
   INSTALLED_APPS = [
       "contact_form",
        ### dependencies:
        "django_recaptcha",
        "widget_tweaks"
   ]
   ```

   Most systems will already have ```wagtail.contrib.forms``` in INSTALLED_APPS - if not, add it, too.

</details>

<details>
<summary><h2>Configuration</h2></summary>

1. Register `reCAPTCHA V3` keys in the [reCAPTCHA Admin console](https://www.google.com/recaptcha/admin/create).

    ![Register New Site](contact_form/README/Register%20New%20Site.png)

2. Add the following entries to the `settings.py` file.

    ```python
    RECAPTCHA_PUBLIC_KEY = ''
    RECAPTCHA_PRIVATE_KEY = ''
    
    RECAPTCHA_REQUIRED_SCORE = 0.85
    
    RECAPTCHA_DOMAIN = 'www.recaptcha.net'
    ```

3. Configure your email settings (`EMAIL_BACKEND`, `EMAIL_HOST` etc.), as without these settings `Django` will most likely return `ConnectionRefusedError` while attempting to submit the form.

4. Create a page of new type: "Contact Page". Add required fields to the contact form (see section "Form Fields" below.)
</details>
