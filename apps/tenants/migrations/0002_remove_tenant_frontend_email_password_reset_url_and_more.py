# Generated by Django 4.0 on 2022-06-28 06:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tenant',
            name='frontend_email_password_reset_url',
        ),
        migrations.RemoveField(
            model_name='tenant',
            name='frontend_email_verify_url',
        ),
    ]
