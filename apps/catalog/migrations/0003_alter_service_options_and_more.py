# Generated by Django 4.0 on 2022-02-03 17:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='service',
            options={'ordering': ('-created_at',)},
        ),
        migrations.AlterModelOptions(
            name='writertypeservice',
            options={'ordering': ('-created_at',)},
        ),
    ]