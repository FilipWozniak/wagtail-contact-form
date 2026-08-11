from __future__ import annotations

import uuid

import django.core.validators
import django.db.models.deletion
import wagtail.contrib.forms.models
from django.db import migrations
from django.db import models


def assign_form_field_locales_and_translation_keys(apps, schema_editor) -> None:
    form_field_model = apps.get_model("contact_form", "FormField")
    page_model = apps.get_model("wagtailcore", "Page")

    form_fields = list(
        form_field_model.objects.order_by("page_id", "sort_order", "id").values(
            "id",
            "page_id",
            "clean_name",
        )
    )
    page_ids = {form_field["page_id"] for form_field in form_fields}
    page_details = {
        page["id"]: page
        for page in page_model.objects.filter(id__in=page_ids).values(
            "id",
            "locale_id",
            "translation_key",
        )
    }

    occurrence_by_page_and_name: dict[tuple[int, str], int] = {}
    for form_field in form_fields:
        page = page_details.get(form_field["page_id"])
        if page is None or page["locale_id"] is None:
            continue

        clean_name = form_field["clean_name"] or f"field-{form_field['id']}"
        occurrence_key = (form_field["page_id"], clean_name)
        occurrence = occurrence_by_page_and_name.get(occurrence_key, 0)
        occurrence_by_page_and_name[occurrence_key] = occurrence + 1
        shared_key = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"wagtail-contact-form:{page['translation_key']}:{clean_name}:{occurrence}",
        )

        form_field_model.objects.filter(pk=form_field["id"]).update(
            locale_id=page["locale_id"],
            translation_key=shared_key,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("contact_form", "0009_update_field_labels"),
        ("wagtailforms", "0005_alter_formsubmission_form_data"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="contactpage",
            options={
                "verbose_name": "Contact Page",
                "verbose_name_plural": "Contact Pages",
            },
        ),
        migrations.AddField(
            model_name="contactpage",
            name="error_message_throttling",
            field=models.PositiveIntegerField(
                default=60,
                help_text=(
                    "The error messages of the same type will not be sent more "
                    "frequently than the value specified below."
                ),
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Error Message Throttling (in Minutes)",
            ),
        ),
        migrations.AddField(
            model_name="contactpage",
            name="technical_to_address",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "The error messages will be emailed to these addresses. "
                    "Please separate multiple recipients by comma."
                ),
                max_length=255,
                validators=[wagtail.contrib.forms.models.validate_to_address],
                verbose_name="Address to (Technical)",
            ),
        ),
        migrations.AlterField(
            model_name="contactpage",
            name="to_address",
            field=models.CharField(
                blank=True,
                help_text=(
                    "The form submissions will be emailed to these addresses. "
                    "Please separate multiple recipients by comma."
                ),
                max_length=255,
                validators=[wagtail.contrib.forms.models.validate_to_address],
                verbose_name="Address to",
            ),
        ),
        migrations.AddField(
            model_name="formfield",
            name="locale",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="wagtailcore.locale",
                verbose_name="locale",
            ),
        ),
        migrations.AddField(
            model_name="formfield",
            name="translation_key",
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        migrations.RunPython(
            assign_form_field_locales_and_translation_keys,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="formfield",
            name="locale",
            field=models.ForeignKey(
                editable=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="wagtailcore.locale",
                verbose_name="locale",
            ),
        ),
        migrations.AddConstraint(
            model_name="formfield",
            constraint=models.UniqueConstraint(
                fields=("translation_key", "locale"),
                name="contact_form_unique_field_translation",
            ),
        ),
        migrations.CreateModel(
            name="ContactFormSecurityState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("captcha_notification", "CAPTCHA notification"),
                            ("post_rate_limit", "POST rate limit"),
                            ("duplicate_content", "Duplicate content"),
                            ("submission_nonce", "Submission nonce"),
                        ],
                        max_length=32,
                    ),
                ),
                ("scope_hash", models.CharField(max_length=64)),
                ("fingerprint", models.CharField(max_length=64)),
                ("window_started_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("count", models.PositiveIntegerField(default=0)),
                ("last_event_at", models.DateTimeField()),
            ],
        ),
        migrations.AddConstraint(
            model_name="contactformsecuritystate",
            constraint=models.UniqueConstraint(
                fields=("kind", "scope_hash", "fingerprint"),
                name="contact_form_unique_security_state",
            ),
        ),
        migrations.AddIndex(
            model_name="contactformsecuritystate",
            index=models.Index(
                fields=["kind", "expires_at"],
                name="contact_sec_kind_exp_idx",
            ),
        ),
        migrations.CreateModel(
            name="ContactEmailDelivery",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sending", "Sending"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                            ("unknown", "Delivery unknown"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("recipients", models.JSONField(default=list)),
                ("subject", models.CharField(blank=True, max_length=255)),
                ("body", models.TextField(blank=True)),
                ("from_address", models.EmailField(blank=True, max_length=254)),
                ("message_id", models.CharField(max_length=255, unique=True)),
                ("submission_nonce_hash", models.CharField(max_length=64, unique=True)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("last_error_type", models.CharField(blank=True, max_length=255)),
                ("last_error_message", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "submission",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contact_email_delivery",
                        to="wagtailforms.formsubmission",
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
