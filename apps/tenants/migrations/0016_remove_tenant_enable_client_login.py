# Generated by Django 4.0 on 2023-08-20 15:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0015_alter_tenant_enable_client_login'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tenant',
            name='enable_client_login',
        ),
    ]
