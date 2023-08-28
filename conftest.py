"""Global test fixture"""
import dateutil
import pytest
import requests
from django.db import connection, transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient

from apps.subscription.models import Paypal, Subscription
from apps.tenants.models import Tenant
from apps.users.models import User


@pytest.fixture(autouse=True)
def mute_signals(request):
    """Mute Django signals"""
    post_save.receivers = []
    pre_save.receivers = []
    pre_delete.receivers = []
    post_delete.receivers = []


@pytest.fixture()
def disable_network_calls(monkeypatch):
    """Disable any network calls

    If a test accidentally executes the real network call, disable the call
    """

    def stunted_get():
        raise RuntimeError("Network access not allowed during testing!")

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: stunted_get())
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: stunted_get())


@pytest.fixture(autouse=True)
def use_dummy_cache_backend(settings):
    """Dummy caching"""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }


@pytest.fixture(scope="session")
def use_fast_tenant(django_db_setup, django_db_blocker):
    """Set up fast tenant"""
    with django_db_blocker.unblock(), transaction.atomic():
        if not Tenant.objects.filter(
            schema_name=FastTenantTestCase.get_test_schema_name()
        ).exists():
            tenant = Tenant(schema_name=FastTenantTestCase.get_test_schema_name())
            tenant.save()
            tenant.domains.create(domain=FastTenantTestCase.get_test_tenant_domain())


@pytest.fixture
def fast_tenant_client():
    """Client that uses fast tenant"""
    tenant = Tenant.objects.get(schema_name=FastTenantTestCase.get_test_schema_name())
    return TenantClient(tenant)


@pytest.fixture
def use_tenant_connection(use_fast_tenant):
    """Set the database connection to use the tenant schema"""
    tenant = Tenant.objects.get(schema_name=FastTenantTestCase.get_test_schema_name())
    connection.set_tenant(tenant)

    yield

    connection.set_schema_to_public()


@pytest.fixture
def test_password():
    return "strong-test-pass"


@pytest.fixture
def create_active_subscription():
    subscription = Subscription.objects.create(
        is_on_trial=False,
        status=Subscription.Status.ACTIVE,
        start_time=dateutil.parser.parse(
            "2016-01-01T00:20:49Z",
        ),
        next_billing_time=dateutil.parser.parse(
            "2016-05-01T00:20:49Z",
        ),
    )
    Paypal.objects.create(
        subscription=subscription, paypal_subscription_id="payal_subscription_id"
    )


@pytest.fixture
def store_owner(test_password):
    """Return store owner"""
    return User.objects.create(
        username="store_owner",
        profile_type=User.ProfileType.STAFF,
        is_store_owner=True,
        is_email_verified=True,
        password=test_password,
    )


@pytest.fixture
def store_staff(test_password):
    """Return staff member"""
    return User.objects.create(
        username="store_staff",
        profile_type=User.ProfileType.STAFF,
        is_email_verified=True,
        password=test_password,
    )


@pytest.fixture
def customer(test_password):
    """Return customer"""
    return User.objects.create(
        username="store_customer",
        profile_type=User.ProfileType.CUSTOMER,
        is_email_verified=True,
        password=test_password,
    )


@pytest.fixture
def dummy_uuid():
    return "4a2aaa24-7a41-4d51-9e75-21a2e1ebb164"
