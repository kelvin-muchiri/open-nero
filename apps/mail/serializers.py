"""Serializer classes for mail app views"""

from rest_framework import serializers

# pylint: disable=W0223


class SendMailSerializer(serializers.Serializer):
    """Serilizer class for send mail endpoint"""

    recipient = serializers.EmailField()
    subject = serializers.CharField()
    message = serializers.CharField()
    sender_email = serializers.EmailField()
    sender_name = serializers.CharField()
