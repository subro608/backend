# Generated by Django 4.2.16 on 2024-12-15 17:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0002_alter_properties_lessor_id"),
    ]

    operations = [
        migrations.RenameField(
            model_name="properties",
            old_name="lessor_id",
            new_name="lessor",
        ),
    ]
