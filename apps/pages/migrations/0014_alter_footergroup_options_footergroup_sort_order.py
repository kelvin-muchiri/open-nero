# Generated by Django 4.0 on 2022-07-19 14:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0013_alter_navbarlink_options'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='footergroup',
            options={'ordering': ('sort_order',)},
        ),
        migrations.AddField(
            model_name='footergroup',
            name='sort_order',
            field=models.PositiveSmallIntegerField(blank=True, default=0, help_text='The position of display when ordering is done by this field', null=True),
        ),
    ]
