"""Common helper methods"""

import json
import logging
import urllib

import boto3
import magic
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.deconstruct import deconstructible
from django.utils.http import urlencode

from apps.tenants.models import Tenant

# pylint: disable=raise-missing-from
# pylint: disable=too-many-arguments


@deconstructible
class FileValidator:
    """File validation using python magic"""

    error_messages = {
        "max_size": (
            "Ensure this file size is not greater than %(max_size)s."
            " Your file size is %(size)s."
        ),
        "min_size": (
            "Ensure this file size is not less than %(min_size)s. "
            "Your file size is %(size)s."
        ),
        "content_type": "Files of type %(content_type)s are not supported.",
    }

    def __init__(self, max_size=None, min_size=None, content_types=()):
        self.max_size = max_size
        self.min_size = min_size
        self.content_types = content_types

    def __call__(self, data):
        if self.max_size is not None and data.size > self.max_size:
            params = {
                "max_size": filesizeformat(self.max_size),
                "size": filesizeformat(data.size),
            }
            raise ValidationError(self.error_messages["max_size"], "max_size", params)

        if self.min_size is not None and data.size < self.min_size:
            params = {
                "min_size": filesizeformat(self.mix_size),
                "size": filesizeformat(data.size),
            }
            raise ValidationError(self.error_messages["min_size"], "min_size", params)

        if self.content_types:
            content_type = magic.from_buffer(data.read(), mime=True)
            if content_type not in self.content_types:
                params = {"content_type": content_type}
                raise ValidationError(
                    self.error_messages["content_type"], "content_type", params
                )

    def __eq__(self, other):
        return isinstance(other, FileValidator)


def get_absolute_web_url(tenant, relative_url):
    """Get a tenant's fontend full URL for a path"""
    domain = tenant.domains.filter(is_primary=True).first()

    if not domain:
        return None

    frontend_domain = domain.domain.replace("api.", "")
    return f"{settings.WEBAPP_PROTOCOL}://{frontend_domain}{relative_url}"


def check_model_or_throw_validation_error(model, lookup_id, attribute_lookup_name=None):
    """Check if a model instance id exists"""
    if attribute_lookup_name:
        try:
            lookup = {attribute_lookup_name: lookup_id}
            model.objects.get(**lookup)
        except model.DoesNotExist:
            raise ValidationError(
                f"{model.__name__} with id {lookup_id} does not exist"
            )
    else:
        try:
            model.objects.get(id=lookup_id)
        except model.DoesNotExist:
            raise ValidationError(
                f"{model.__name__} with id {lookup_id} does not exist"
            )

    return lookup_id


def create_presigned_url(bucket_name, object_name, expiration=60):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )
    try:
        response = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_name},
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response


def reverse_querystring(
    view, urlconf=None, args=None, kwargs=None, current_app=None, query_kwargs=None
):
    """Custom reverse to handle query strings.
    Usage:
        reverse('app.views.my_view', kwargs={'pk': 123}, query_kwargs={'search': 'Bob'})
    """
    base_url = reverse(
        view, urlconf=urlconf, args=args, kwargs=kwargs, current_app=current_app
    )
    if query_kwargs:
        return f"{base_url}?{urlencode(query_kwargs)}"
    return base_url


def has_model_field_changed(instance, field):
    """Used to check if the field of an object has changed"""
    if not instance.pk:
        return False
    # pylint: disable=protected-access
    old_value = (
        instance.__class__._default_manager.filter(pk=instance.pk)
        .values(field)
        .get()[field]
    )
    return getattr(instance, field) != old_value


def validate_google_captcha(tenant: Tenant, captcha_response: dict):
    """Validate google captcha response"""
    values = {
        "secret": settings.GOOGLE_RECAPTCHA_SECRET_KEY,
        "response": captcha_response,
    }
    data = urllib.parse.urlencode(values).encode()
    req = urllib.request.Request(settings.GOOGLE_RECAPTCHA_API, data=data)  # nosec

    with urllib.request.urlopen(req) as response:  # nosec
        result = json.loads(response.read().decode())  # nosec

        # Incase verifying of domain origin is disabled, we check that the
        # hostname is valid (https://developers.google.com/recaptcha/docs/domain_validation)
        if (
            result.get("success")
            and tenant.domains.filter(domain=result.get("hostname")).exists()
        ):
            return True

    return False
