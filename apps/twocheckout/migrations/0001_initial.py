# Generated by Django 4.0 on 2022-12-19 05:22

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Twocheckout',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_active', models.BooleanField(default=True, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('seller_id', models.CharField(max_length=255)),
                ('secret', models.CharField(max_length=255)),
                ('created_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_related', related_query_name='%(app_label)s_%(class)ss', to='users.user')),
            ],
            options={
                'ordering': ('-created_at',),
                'abstract': False,
            },
        ),
    ]