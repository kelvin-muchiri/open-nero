# Generated by Django 4.0 on 2022-07-20 14:30

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0016_alter_footerlink_options_footerlink_sort_order'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='page',
            name='footer_sort_order',
        ),
        migrations.RemoveField(
            model_name='page',
            name='navbar_sort_order',
        ),
    ]
