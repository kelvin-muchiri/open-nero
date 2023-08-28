"""
Custom storage backend classes
"""


from django.conf import settings
from django.utils.functional import cached_property
from django_tenants import utils
from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    """Custom static files storage backend"""

    location = settings.AWS_STATIC_LOCATION


class MediaStorage(S3Boto3Storage):
    """Custom media files storage backend"""

    file_overwrite = False

    @cached_property
    def relative_media_root(self):
        """Relative media root"""
        try:
            return settings.MULTITENANT_RELATIVE_MEDIA_ROOT
        except AttributeError:
            # MULTITENANT_RELATIVE_MEDIA_ROOT is an optional setting, use
            # the default value if none provided
            # Use %s instead of "" to avoid raising exception every time
            # in parse_tenant_config_path()
            return "%s"

    @property  # not cached like in parent class
    def location(self):
        """Location to store files"""
        return f"media/{utils.parse_tenant_config_path(self.relative_media_root)}"


class PublicMediaStorage(MediaStorage):
    @property
    def location(self):
        """Location to store files"""
        return (
            f"public/media/{utils.parse_tenant_config_path(self.relative_media_root)}"
        )
