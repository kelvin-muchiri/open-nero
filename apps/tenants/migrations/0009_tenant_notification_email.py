# Generated by Django 4.0 on 2022-12-18 09:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0008_tenant_facebook_profile_tenant_instagram_profile_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='notification_email',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
