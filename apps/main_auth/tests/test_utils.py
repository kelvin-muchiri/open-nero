"""Tests for utils module"""
import pytest

from ..utils import get_full_domain, normalize_domain, normalize_schema_name


@pytest.fixture
def with_tenant_domain_suffix(settings):
    settings.TENANT_DEFAULT_DOMAIN_SUFFIX = ".example.com"


@pytest.fixture
def with_tenant_domain_prefix(settings):
    settings.TENANT_DEFAULT_DOMAIN_PREFIX = "api."


@pytest.fixture
def no_tenant_domain_suffix(settings):
    settings.TENANT_DEFAULT_DOMAIN_SUFFIX = None


@pytest.fixture
def no_tenant_domain_prefix(settings):
    settings.TENANT_DEFAULT_DOMAIN_PREFIX = None


@pytest.mark.parametrize(
    "domain",
    [
        "Nice Site",
        "NICE SITE",
        "NIcE siTE",
        "nice site",
        "nice-site",
        "nice&&&site",
        "&nice&&&site&",
        "&nice &&&site&",
        "&nice .&&&site&",
        "&&&&nice .&&&site&&&&&",
    ],
)
def test_normalize_domain(domain):
    """
    Replaces any characters that do not match A-Z or 0-9 or hyphen(-)
    with hyphen
    """
    assert normalize_domain(domain) == "nice-site"


@pytest.mark.parametrize(
    "schema_name",
    [
        "Nice Site",
        "NICE SITE",
        "NIcE siTE",
        "nice site",
        "nice-site",
        "nice&&&site",
        "&nice&&&site&",
        "&nice &&&site&",
        "&nice .&&&site&",
        "&&&&nice .&&&site&&&&&",
    ],
)
def test_normalize_schema_name(schema_name):
    """Schema name should be normalized to a valid Postgres schema name"""
    assert normalize_schema_name(schema_name) == "nice_site"


def test_get_full_domain(with_tenant_domain_suffix, with_tenant_domain_prefix):
    """Domain is correct when both suffix and prefix set"""
    assert get_full_domain("essay-masters") == "api.essay-masters.example.com"


def test_get_full_domain_no_settings(no_tenant_domain_suffix, no_tenant_domain_prefix):
    """Domain is correct when both suffix and prefix not set"""
    assert get_full_domain("essay-masters") == "essay-masters"


def test_get_full_domain_no_suffix(with_tenant_domain_prefix, no_tenant_domain_suffix):
    """Domain is correct if suffix not set"""
    assert get_full_domain("essay-masters") == "api.essay-masters"


def test_get_full_domain_no_prefix(with_tenant_domain_suffix, no_tenant_domain_prefix):
    """Domain is correct if prefix not set"""
    assert get_full_domain("essay-masters") == "essay-masters.example.com"
