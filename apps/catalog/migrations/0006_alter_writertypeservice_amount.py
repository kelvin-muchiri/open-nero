# Generated by Django 4.0 on 2022-02-18 13:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_remove_writertype_is_free_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='writertypeservice',
            name='amount',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Price per page. Leave blank or fill 0.00 if free', max_digits=15, null=True),
        ),
    ]
