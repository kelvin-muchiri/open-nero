"""
Utilities for handling SMS
"""

import africastalking


def remove_duplicate_recipients(recipients):
    """Remove duplicate recipient phone numbers."""
    return list(set(recipients))


def parse_phone(phone):
    """Format phone number"""
    phone = str(phone)
    if not phone.startswith("+"):
        return "+" + phone

    return phone


def on_finish(error, response):
    """
    Enables asynchrous use of AT
    Call back function for send SMS
    """
    if error is not None:
        raise error

    return response


def send_sms(username, api_key, message, recipients, sender_id=None):
    """Function for actually sending an SMS"""

    recipients = [
        parse_phone(recipient) for recipient in remove_duplicate_recipients(recipients)
    ]
    africastalking.initialize(username=username, api_key=api_key)
    sms = africastalking.SMS
    sms.send(
        message=message, recipients=recipients, sender_id=sender_id, callback=on_finish
    )
