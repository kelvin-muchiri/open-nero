from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PublicConfigsSerializer


class PublicConfigsAPIView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        """Method POST"""
        serializer = PublicConfigsSerializer(request.tenant)
        return Response(serializer.data)
