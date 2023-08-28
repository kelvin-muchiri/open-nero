"""Celery tasks"""
import logging

import boto3
from botocore.exceptions import ClientError
from celery import shared_task
from django.conf import settings


@shared_task
def send_email(recipient, subject, message, sender_email, sender_name):
    """Send email using AWS Simple Email Service"""
    if not settings.AWS_SES_ACCESS_KEY_ID or not settings.AWS_SES_SECRET_ACCESS_KEY:
        logging.error(
            "setting AWS_SES_ACCESS_KEY_ID or AWS_SES_SECRET_ACCESS_KEY missing"
        )
        return

    client = boto3.client(
        "ses",
        region_name=settings.AWS_SES_REGION,
        aws_access_key_id=settings.AWS_SES_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SES_SECRET_ACCESS_KEY,
    )

    # Try to send the email.
    try:
        # Provide the contents of the email.
        client.send_email(
            Destination={
                "ToAddresses": [recipient],
            },
            Message={
                "Body": {
                    "Html": {
                        "Charset": "utf-8",
                        "Data": message,
                    },
                },
                "Subject": {
                    "Charset": "utf-8",
                    "Data": subject,
                },
            },
            Source=f"{sender_name} <{sender_email}>",
        )

    except ClientError as error:
        logging.error(
            "Email send failed with error %s", error.response["Error"]["Message"]
        )
