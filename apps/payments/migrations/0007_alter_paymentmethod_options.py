# Generated by Django 4.0 on 2022-04-05 11:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0006_paymentmethod'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='paymentmethod',
            options={'ordering': ('sort_order',)},
        ),
    ]
