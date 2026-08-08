from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django_rq import get_queue
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from auth_app.api.authentication import CookieJWTAuthentication
from auth_app.api.cookies import delete_jwt_cookies, set_jwt_cookies
from auth_app.api.schema.activation_schema import (
    ACTIVATION_DESCRIPTION,
    ACTIVATION_PARAMETERS,
    ACTIVATION_RESPONSES,
)
from auth_app.api.schema.base_schema import AUTH_TAG
from auth_app.api.schema.login_schema import (
    LOGIN_DESCRIPTION,
    LOGIN_REQUEST_EXAMPLES,
    LOGIN_RESPONSE_HEADERS,
    LOGIN_RESPONSES,
)
from auth_app.api.schema.logout_schema import (
    LOGOUT_DESCRIPTION,
    LOGOUT_PARAMETERS,
    LOGOUT_RESPONSES,
)
from auth_app.api.schema.registration_schema import REGISTRATION_DESCRIPTION
from auth_app.api.serializers import LoginSerializer, RegistrationSerializer
from auth_app.api.tokens import account_activation_token
from auth_app.api.utils import send_activation_email

User = get_user_model()


class RegistrationView(APIView):
    """Create inactive user accounts and queue their activation emails."""

    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(
        tags=AUTH_TAG,
        request=RegistrationSerializer,
        description=REGISTRATION_DESCRIPTION,
    )
    def post(self, request):
        """Register a user and enqueue the activation email with RQ."""
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        token = account_activation_token.make_token(user)  # type:ignore
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


class ActivationView(APIView):
    """Activate an inactive account using its emailed credentials."""

    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(
        tags=AUTH_TAG,
        request=None,
        parameters=ACTIVATION_PARAMETERS,
        responses=ACTIVATION_RESPONSES,
        description=ACTIVATION_DESCRIPTION,
    )
    def get(self, request, uidb64, token):
        """Validate the UID and one-time token, then activate the account."""
        del request

        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))
        except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
            return self._failure_response()

        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(pk=user_id)  # type:ignore
            except (User.DoesNotExist, TypeError, ValueError, OverflowError):
                return self._failure_response()

            if user.is_active or not account_activation_token.check_token(
                user,
                token,
            ):
                return self._failure_response()

            user.is_active = True
            user.save(update_fields=['is_active'])

        return Response(
            {'message': 'Account successfully activated.'},
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _failure_response():
        """Return the endpoint's generic response for activation failures."""
        return Response(
            {'message': 'Activation failed.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CookieTokenObtainPairView(TokenObtainPairView):
    """Authenticate by email and return JWTs only in secure cookies."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        tags=AUTH_TAG,
        request=LoginSerializer,
        responses=LOGIN_RESPONSES,
        parameters=LOGIN_RESPONSE_HEADERS,
        examples=LOGIN_REQUEST_EXAMPLES,
        description=LOGIN_DESCRIPTION,
        auth=[],
    )
    def post(self, request, *args, **kwargs):
        """Issue both JWT cookies and bootstrap CSRF protection."""
        response = super().post(request, *args, **kwargs)
        access_token = response.data.pop('access')  # type:ignore
        refresh_token = response.data.pop('refresh')  # type:ignore

        set_jwt_cookies(response, access_token, refresh_token)
        get_token(request)  # type:ignore
        response['Cache-Control'] = 'no-store'
        return response


class LogoutView(APIView):
    """Blacklist the refresh-token cookie and remove both JWT cookies."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        tags=AUTH_TAG,
        request=None,
        responses=LOGOUT_RESPONSES,
        parameters=LOGOUT_PARAMETERS,
        description=LOGOUT_DESCRIPTION,
        auth=[],
    )
    def post(self, request):
        """Invalidate the current refresh token without requiring access JWT."""
        raw_refresh_token = request.COOKIES.get(
            settings.JWT_REFRESH_COOKIE_NAME
        )

        if not raw_refresh_token:
            return self._logout_response(
                'Refresh token is required.',
                status.HTTP_400_BAD_REQUEST,
            )

        CookieJWTAuthentication.enforce_csrf(request)

        try:
            RefreshToken(raw_refresh_token).blacklist()
        except TokenError:
            return self._logout_response(
                'Refresh token is invalid or expired.',
                status.HTTP_400_BAD_REQUEST,
            )

        return self._logout_response(
            'Logout successful! All tokens will be deleted. '
            'Refresh token is now invalid.',
            status.HTTP_200_OK,
        )

    @staticmethod
    def _logout_response(detail, response_status):
        """Build a non-cacheable response that expires both JWT cookies."""
        response = Response({'detail': detail}, status=response_status)
        delete_jwt_cookies(response)
        response['Cache-Control'] = 'no-store'
        return response
