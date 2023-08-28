"""tests for apps.common.utils"""

from django.test import TestCase, override_settings

from apps.tenants.models import Domain, Tenant

from ..utils import get_absolute_web_url


class GetFrontendURLTesCase(TestCase):
    """Tests for get_absolute_web_url"""

    @override_settings(WEBAPP_PROTOCOL="https")
    def test_url(self):
        """Returns correct full URL"""
        tenant = Tenant.objects.create(schema_name="best", name="Best")
        tenant.save()
        domain = Domain()
        domain.domain = "api.best.com"
        domain.tenant = tenant
        domain.is_primary = True
        domain.save()
        self.assertEqual(
            get_absolute_web_url(tenant, "/verify/email"),
            "https://best.com/verify/email",
        )

    @override_settings(WEBAPP_PROTOCOL="https")
    def test_no_primary_domain(self):
        """Returns None if no primary domain found"""
        tenant = Tenant.objects.create(schema_name="nice", name="Nice")
        tenant.save()
        self.assertIsNone(get_absolute_web_url(tenant, "/verify/email"))
