"""Utility methods"""
import random
import re

from django.conf import settings


def generate_email_verification_code():
    """Generate email verification code"""
    numbers = [0]
    while numbers[0] == 0:
        numbers = random.sample(range(10), 4)

    return "".join(map(str, numbers))


def normalize_domain(domain):
    """Normalize the domain

    Replaces any characters that do not match A-Z or 0-9 or hyphen(-)
    with hyphen
    """
    valid_domain = re.sub("[^a-zA-Z0-9-]+", "-", domain)

    # strip hyphens if any from the end and start
    if valid_domain[-1] == "-":
        valid_domain = valid_domain[:-1]

    if valid_domain[0] == "-":
        valid_domain = valid_domain[1:]

    return valid_domain.lower()


def normalize_schema_name(schema_name):
    """Normalize schema name into a valid Postgres schema name"""
    schema_name = normalize_domain(schema_name)

    return schema_name.replace("-", "_")


def get_full_domain(domain):
    """Returns a tenants full domain name"""
    domain = normalize_domain(domain)

    if settings.TENANT_DEFAULT_DOMAIN_PREFIX:
        domain = settings.TENANT_DEFAULT_DOMAIN_PREFIX + domain

    if settings.TENANT_DEFAULT_DOMAIN_SUFFIX:
        domain = domain + settings.TENANT_DEFAULT_DOMAIN_SUFFIX

    return domain
