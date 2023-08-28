"""Utility methods"""

import base64

import requests
from django.http import HttpRequest
from paypalrestsdk.notifications import WebhookEvent


def verify_webhook_signature(request: HttpRequest, webhook_id: str) -> dict:
    """Verify Paypal webhook signature"""
    # The payload body sent in the webhook event
    event_body = request.body.decode("utf-8")
    # Paypal-Transmission-Id in webhook payload header
    transmission_id = request.META.get("HTTP_PAYPAL_TRANSMISSION_ID")
    # Paypal-Transmission-Time in webhook payload header
    timestamp = request.META.get("HTTP_PAYPAL_TRANSMISSION_TIME")
    # Paypal-Transmission-Sig in webhook payload header
    actual_signature = request.META.get("HTTP_PAYPAL_TRANSMISSION_SIG")
    # Paypal-Cert-Url in webhook payload header
    cert_url = request.META.get("HTTP_PAYPAL_CERT_URL")
    # PayPal-Auth-Algo in webhook payload header
    auth_algo = request.META.get("HTTP_PAYPAL_AUTH_ALGO")

    response = WebhookEvent.verify(
        transmission_id,
        timestamp,
        webhook_id,
        event_body,
        cert_url,
        actual_signature,
        auth_algo,
    )
    return response


def get_paypal_access_token(base_url, client_id, secret):
    url = f"{base_url}/oauth2/token"
    payload = "grant_type=client_credentials"
    encoded_auth = base64.b64encode((client_id + ":" + secret).encode())
    headers = {
        "Authorization": f"Basic {encoded_auth.decode()}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()

    except requests.exceptions.HTTPError as error:
        raise error
    # pylint: disable=broad-except
    except Exception as err:
        raise err

    return response.json()["access_token"]
