from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contact_form", "0010_harden_contact_form"),
    ]

    operations = [
        migrations.DeleteModel(name="ContactEmailDelivery"),
        migrations.DeleteModel(name="ContactFormSecurityState"),
    ]
