# Generated by Django 4.0 on 2022-04-06 11:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0007_alter_paymentmethod_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentmethod',
            name='title',
            field=models.CharField(max_length=50),
        ),
    ]