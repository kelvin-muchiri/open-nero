"""signals"""
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Image

# pylint: disable=unused-argument


@receiver(post_delete, sender=Image)
def remove_file_from_s3(sender, instance, **kwargs):
    """Delete file from Amazon S3 when instance is deleted"""
    instance.image.delete(save=False)
