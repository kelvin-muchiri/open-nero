# Generated by Django 4.0 on 2022-02-08 17:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_alter_payment_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='status',
            field=models.CharField(choices=[('COMPLETED', 'Completed'), ('REFUNDED', 'Refunded'), ('PARTIALLY_REFUNDED', 'Partially Refunded'), ('FAILED', 'Failed'), ('PENDING', 'Pending'), ('DECLINED', 'Declined')], default='PENDING', max_length=32),
        ),
    ]
