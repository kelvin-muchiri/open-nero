"""
Custom command to load default pages for a tenant

./manage.py tenant_command load_pages <industry> --schema=<schema_name>

"""

import json
import os

from django.conf import settings
from django.db import connection
from django.db.utils import IntegrityError
from django_tenants.management.commands import BaseTenantCommand
from django_tenants.utils import get_tenant_model

from apps.pages.models import Page


class Command(BaseTenantCommand):
    COMMAND_NAME = "tenant_command"
    help = "Loads default pages for a tenant"

    def add_arguments(self, parser):
        parser.add_argument(
            "industry",
            type=str,
            help="The industry which the tenant belongs to",
        )

    def handle(self, *args, **options):
        industry = options["industry"]
        schema_name = connection.get_schema()
        tenant = get_tenant_model().objects.get(schema_name=schema_name)

        if industry == "essay_writing":
            filepath = os.path.join(
                settings.BASE_DIR,
                "apps/pages/management/commands/fixtures",
                "essay_writing.json",
            )

            with open(filepath, encoding="utf-8") as file:
                records = json.loads(file.read().replace("<tname>", tenant.name))

                for record in records:
                    try:
                        Page.objects.create(**record)

                    except IntegrityError:
                        self.stdout.write(
                            self.style.ERROR(f"{record['slug']} already exists")
                        )

            self.stdout.write(self.style.SUCCESS("Finished loading default pages"))
