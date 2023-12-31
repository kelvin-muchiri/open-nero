# Generated by Django 4.0 on 2022-02-02 12:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catalog', '0001_initial'),
        ('cart', '0002_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_related', related_query_name='%(app_label)s_%(class)ss', to='users.user'),
        ),
        migrations.AddField(
            model_name='item',
            name='deadline',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cart', to='catalog.deadline'),
        ),
        migrations.AddField(
            model_name='item',
            name='level',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='cart', to='catalog.level'),
        ),
        migrations.AddField(
            model_name='item',
            name='paper',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cart', to='catalog.paper'),
        ),
        migrations.AddField(
            model_name='item',
            name='paper_format',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cart', to='catalog.format'),
        ),
        migrations.AddField(
            model_name='item',
            name='writer_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='catalog.writertype'),
        ),
        migrations.AddField(
            model_name='cart',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_related', related_query_name='%(app_label)s_%(class)ss', to='users.user'),
        ),
        migrations.AddField(
            model_name='cart',
            name='owner',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='users.user'),
        ),
        migrations.AddField(
            model_name='attachment',
            name='cart_item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='cart.item'),
        ),
        migrations.AddField(
            model_name='attachment',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_related', related_query_name='%(app_label)s_%(class)ss', to='users.user'),
        ),
    ]
