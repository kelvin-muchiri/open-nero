# Generated by Django 4.0 on 2022-06-14 04:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0004_page_draft'),
    ]

    operations = [
        migrations.AlterField(
            model_name='page',
            name='blocks',
            field=models.JSONField(default=list),
        ),
    ]
