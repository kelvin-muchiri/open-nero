# Generated by Django 4.0 on 2022-07-27 05:59

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('pages', '0017_remove_page_footer_sort_order_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SocialLink',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_active', models.BooleanField(default=True, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=20)),
                ('link_type', models.CharField(blank=True, choices=[('FACEBOOK', 'Facebook'), ('TWITTER', 'Twitter'), ('INSTARAM', 'Instagram')], max_length=50, null=True)),
                ('link_to', models.URLField()),
                ('sort_order', models.PositiveSmallIntegerField(blank=True, default=0, help_text='The position of display when ordering is done by this field', null=True)),
                ('created_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_related', related_query_name='%(app_label)s_%(class)ss', to='users.user')),
                ('footer_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='social_links', to='pages.footergroup')),
            ],
            options={
                'ordering': ('sort_order',),
                'abstract': False,
            },
        ),
    ]
