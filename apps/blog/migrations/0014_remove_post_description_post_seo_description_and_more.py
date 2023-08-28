# Generated by Django 4.0 on 2022-12-16 07:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0013_alter_post_featured_image'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='post',
            name='description',
        ),
        migrations.AddField(
            model_name='post',
            name='seo_description',
            field=models.CharField(blank=True, help_text='An SEO friendly with a max length of 160', max_length=160, null=True),
        ),
        migrations.AddField(
            model_name='post',
            name='seo_title',
            field=models.CharField(blank=True, help_text='An SEO friendly title with a max length of 60', max_length=60, null=True),
        ),
        migrations.AlterField(
            model_name='post',
            name='title',
            field=models.CharField(max_length=255),
        ),
    ]