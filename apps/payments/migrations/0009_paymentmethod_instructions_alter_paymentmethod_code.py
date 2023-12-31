# Generated by Django 4.0 on 2022-12-05 06:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0008_alter_paymentmethod_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentmethod',
            name='instructions',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name='paymentmethod',
            name='code',
            field=models.CharField(choices=[('PAYPAL', 'Paypal'), ('BRAINTREE', 'Braintree'), ('INSTRUCTIONS', 'Instructions')], max_length=20),
        ),
    ]
