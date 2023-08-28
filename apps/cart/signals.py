"""signals"""
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.cart.models import Attachment

# pylint: disable=unused-argument


@receiver(post_delete, sender=Attachment)
def remove_file_from_s3(sender, instance, **kwargs):
    """Delete file from Amazon S3 when instance is deleted"""
    instance.attachment.delete(save=False)
