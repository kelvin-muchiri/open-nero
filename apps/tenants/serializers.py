from rest_framework import serializers

from .models import Tenant


class PublicConfigsSerializer(serializers.ModelSerializer):
    primary_domain = serializers.SerializerMethodField()
    site_id = serializers.SerializerMethodField()

    def get_primary_domain(self, obj):
        domain = obj.domains.filter(is_primary=True).first()

        if not domain:
            return None

        return domain.domain

    def get_site_id(self, obj):
        return obj.schema_name

    class Meta:
        model = Tenant
        fields = (
            "name",
            "site_id",
            "primary_color",
            "secondary_color",
            "contact_email",
            "attachment_email",
            "twitter_profile",
            "facebook_profile",
            "instagram_profile",
            "tawkto_property_id",
            "tawkto_widget_id",
            "primary_domain",
            "theme",
            "ga_measurement_id",
        )
