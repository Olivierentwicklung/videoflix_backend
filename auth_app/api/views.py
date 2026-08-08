from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_rq import get_queue
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_app.api.serializers import RegistrationSerializer
from auth_app.api.utils import send_activation_email


class RegistrationView(APIView):
    """Create inactive user accounts and queue their activation emails."""

    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(
        request=RegistrationSerializer,
        responses={201: RegistrationSerializer},
        tags=['Authentication'],
        description='Registriert einen neuen Benutzer im System.',
    )
    def post(self, request):
        """Register a user and enqueue the activation email with RQ."""
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        token = default_token_generator.make_token(user)  # type:ignore
        uid = urlsafe_base64_encode(force_bytes(user.pk))  # type:ignore

        queue = get_queue('default')
        queue.enqueue(send_activation_email, user, uid, token)

        return Response(
            {
                'user': {'id': user.pk, 'email': user.email},  # type:ignore
                'token': token,
            },
            status=status.HTTP_201_CREATED,
        )
