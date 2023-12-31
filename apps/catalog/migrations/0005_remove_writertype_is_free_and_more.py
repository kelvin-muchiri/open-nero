# Generated by Django 4.0 on 2022-02-18 13:00

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('catalog', '0004_remove_writertype_is_default'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='writertype',
            name='is_free',
        ),
        migrations.RemoveField(
            model_name='writertype',
            name='is_popular',
        ),
        migrations.CreateModel(
            name='WriterTypeTag',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_active', models.BooleanField(default=True, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=20)),
                ('created_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_related', related_query_name='%(app_label)s_%(class)ss', to='users.user')),
            ],
            options={
                'ordering': ('-created_at',),
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='writertype',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='writer_types', to='catalog.WriterTypeTag'),
        ),
    ]
