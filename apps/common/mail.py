"""Send mail helper methods"""

import logging

import requests
from django.conf import settings


def send_mail(subject, message, recipient, sender_email, sender_name):
    """
    Send email
    """

    if not settings.MAIL_SERVER_URL:
        logging.error("setting MAIL_SERVER_URL not set")
        return

    data = {
        "recipient": recipient,
        "subject": subject,
        "message": message,
        "sender_email": sender_email,
        "sender_name": sender_name,
    }

    try:
        response = requests.post(
            f"{settings.MAIL_SERVER_URL}mail/send/",
            json=data,
        )
        response.raise_for_status()

    except requests.exceptions.HTTPError as error:
        raise error
