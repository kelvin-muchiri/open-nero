# Generated by Django 4.0 on 2022-12-16 09:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0007_remove_tenant_default_from_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='facebook_profile',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tenant',
            name='instagram_profile',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tenant',
            name='twitter_profile',
            field=models.URLField(blank=True, null=True),
        ),
    ]
