# Generated by Django 4.0 on 2022-02-03 17:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main_auth', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='emailverification',
            options={'ordering': ('-created_at',)},
        ),
    ]
