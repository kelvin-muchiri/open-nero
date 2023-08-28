# Generated by Django 4.0 on 2022-02-08 15:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_alter_order_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Paid'), (2, 'Awaiting Payment'), (3, 'Refunded'), (4, 'Declined'), (5, 'Partially Refunded')], default=2),
        ),
    ]