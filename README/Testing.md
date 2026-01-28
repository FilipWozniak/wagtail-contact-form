# Testing

### `pytest`

```shell
(cd "../wagtail-contact-form/testproject" && DJANGO_SETTINGS_MODULE=testproject.settings.base pytest -s ../contact_form/tests/unit --disable-pytest-warnings)
```

### `pre-commit`

```shell
cd "project"
(cd "wagtail_contact_form" && pre-commit run --files contact_form/tests/unit/*)
```
