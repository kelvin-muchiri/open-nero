# Generated by Django 4.0 on 2023-05-08 17:58

import apps.common.backends.storage
import apps.common.utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0020_delete_sociallink'),
    ]

    operations = [
        migrations.AlterField(
            model_name='image',
            name='image',
            field=models.FileField(max_length=500, storage=apps.common.backends.storage.PublicMediaStorage, upload_to='pages/images/', validators=[apps.common.utils.FileValidator(content_types=('image/webp', 'image/png', 'image/jpeg'))]),
        ),
    ]
