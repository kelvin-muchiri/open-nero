# Generated by Django 4.0 on 2023-08-02 16:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0013_alter_tenant_ga_measurement_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='enable_client_login',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]