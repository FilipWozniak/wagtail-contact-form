# Configuration

## Configuration

1. Generate keys for `Google reCAPTCHA` or `Turnstile` and add them to the `CAPTCHA` settings in the `Wagtail` panel.

   ![2.png](README/images/2.png)

2. Configure your email settings (`EMAIL_BACKEND`, `EMAIL_HOST` etc.), because without these settings `Django` will most likely return `ConnectionRefusedError` while attempting to submit the form.

   ```python
   EMAIL_HOST = ""
   EMAIL_PORT = 
   EMAIL_HOST_USER = ""
   EMAIL_HOST_PASSWORD = ""
   EMAIL_USE_TLS = 
   DEFAULT_FROM_EMAIL = ""
   EMAIL_BACKEND = ""
   ```

3. Add `SILENCED_SYSTEM_CHECKS` variable to `settings.py` file.

   ```python
   SILENCED_SYSTEM_CHECKS = ["django_recaptcha.recaptcha_test_key_error"]
   ```

4. Create a page of type `Contact Pag` and add all the required fields listed below.

   - `Full Name`
   - `E-Mail Address`
   - `Message`
   - `Provider`

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
> Please remember that if you have saved a form with different labels than those mentioned, you must delete the form page instance completely and create it again with the correct values.

## Custom Form Fields 

- `Intro Text`
- `Thank You Text`
- `E-Mail ("From" Address)`
- `E-Mail ("To" Address)`
- `E-Mail Subject`
