# Wagtail Contact Form

## Description

A very basic contact form with `CAPTCHA` module that protects you against spam based on two articles from LearnWagtail website (["Contact Forms"](https://learnwagtail.com/tutorials/contact-forms) and ["Adding Recaptcha to Your Contact Forms"](https://learnwagtail.com/tutorials/adding-recaptcha-to-your-contact-forms)).

> [!NOTE]
> `reCAPTCHA V3` is now supported, while `reCAPTCHA V2` is deprecated.

<details>
<summary><h2>Installation</h2></summary>

1. Install the package from `GitHub`.

   ```python
   pip install git+https://github.com/FilipWozniak/wagtail-contact-form.git
   ```

2. Add the application to the `INSTALLED_APPS` in the `settings.py` file.

    ```python
    INSTALLED_APPS = [
        "contact_form",
    ]
    ```

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

4. Add the application to the `INSTALLED_APPS` in the `settings.py` file.

   ```python
   INSTALLED_APPS = [
       "contact_form",
   ]
   ```

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

3. Remember to configure your email settings correctly (this refers to variables such as `EMAIL_BACKEND`, `EMAIL_HOST` etc.), as without these settings `Django` will most likely return `ConnectionRefusedError` while attempting to submit the form.

### Dependencies

```python
INSTALLED_APPS = [
    "wagtail.contrib.forms",
    "django_recaptcha",
    "wagtailcaptcha",
    "widget_tweaks"
]
```

</details>

<details>
<summary><h2>Common Issues</h2></summary>

Note that if you are using MacOS you may stumble across `URLError` while trying to submit the form.

```shell script
URLError at /contact-us/
<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] Certificate Verify Failed: Unable to Get Local Issuer Certificate (_ssl.c:1122)>
```

As regards to "[Scraping: SSL: CERTIFICATE_VERIFY_FAILED](https://stackoverflow.com/questions/50236117/scraping-ssl-certificate-verify-failed-error-for-http-en-wikipedia-org)" issue on [Stack Overflow](https://stackoverflow.com), all you need to do is go to *Macintosh HD* → *Applications* → *Python* folder and double click on **Install Certificates.command** file.

![URL Error](contact_form/README/URL%20Error.png)

</details>

<details>
<summary><h2>Screenshots</h2></summary>

#### Contact Form

![Contact Us](contact_form/README/Contact%20Us.png)

#### "Thank You" Page

!["Thank You" Page](contact_form/README/Thank%20You%20Page.png)

</details>

<details>
<summary><h2>Form Fields</h2></summary>

- `Full Name`
- `E-Mail Address`
- `Message`
- `CAPTCHA`

> [!WARNING]
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

> [!NOTE]
> Please remember that if you have saved a form with different labels than those mentioned, you must delete the form page and create it again with the correct values.

## Custom Form Fields 
- `Intro Text`
- `Thank You Text`
- `E-Mail ("From" Address)`
- `E-Mail ("To" Address)`
- `E-Mail Subject`

</details>

## Authors

[Filip Woźniak](https://github.com/FilipWozniak)