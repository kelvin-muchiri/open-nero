# Generated by Django 4.0 on 2022-10-04 04:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0004_remove_tenant_google_oauth_client_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='attachment_email',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
