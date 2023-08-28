"""Views"""
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SendMailSerializer
from .tasks import send_email


class SendMailAPIView(APIView):
    """Send mail"""

    permission_classes = (AllowAny,)
    serializer_class = SendMailSerializer

    def post(self, request, *args, **kwargs):
        """Method method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        if (
            not settings.AWS_SES_ACCESS_KEY_ID
            and not settings.AWS_SES_SECRET_ACCESS_KEY
        ):
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        send_email.delay(
            recipient=serializer.data["recipient"],
            subject=serializer.data["subject"],
            message=serializer.data["message"],
            sender_email=serializer.data["sender_email"],
            sender_name=serializer.data["sender_name"],
        )

        return Response(status=status.HTTP_200_OK)
