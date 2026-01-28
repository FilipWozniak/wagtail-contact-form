# Form Fields Configuration

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
