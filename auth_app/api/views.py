from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django_rq import get_queue
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
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
from auth_app.api.schema.password_confirm_schema import (
    PASSWORD_CONFIRM_DESCRIPTION,
    PASSWORD_CONFIRM_PARAMETERS,
    PASSWORD_CONFIRM_RESPONSES,
)
from auth_app.api.schema.password_reset_schema import (
    PASSWORD_RESET_DESCRIPTION,
    PASSWORD_RESET_RESPONSES,
)
from auth_app.api.schema.registration_schema import (
    REGISTRATION_DESCRIPTION,
    REGISTRATION_RESPONSES,
)
from auth_app.api.schema.token_refresh_schema import (
    TOKEN_REFRESH_DESCRIPTION,
    TOKEN_REFRESH_PARAMETERS,
    TOKEN_REFRESH_RESPONSES,
)
from auth_app.api.serializers import (
    LoginSerializer,
    PasswordConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
)
from auth_app.api.tokens import account_activation_token
from auth_app.api.utils import send_activation_email, send_password_reset_email

User = get_user_model()


class PasswordConfirmView(APIView):
    """Set a new password using an emailed one-time reset token."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        tags=AUTH_TAG,
        request=PasswordConfirmSerializer,
        parameters=PASSWORD_CONFIRM_PARAMETERS,
        responses=PASSWORD_CONFIRM_RESPONSES,
        description=PASSWORD_CONFIRM_DESCRIPTION,
        auth=[],
    )
    def post(self, request, uidb64, token):
        """Validate reset credentials, update the password, and revoke sessions."""
        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))
        except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
            return self._invalid_link_response()

        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(  # type:ignore
                    pk=user_id,
                    is_active=True,
                )
            except (User.DoesNotExist, TypeError, ValueError, OverflowError):
                return self._invalid_link_response()

            if not default_token_generator.check_token(user, token):
                return self._invalid_link_response()

            serializer = PasswordConfirmSerializer(
                data=request.data,
                context={'user': user},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            outstanding_tokens = OutstandingToken.objects.filter(user=user)
            for outstanding_token in outstanding_tokens.iterator():
                BlacklistedToken.objects.get_or_create(token=outstanding_token)

        return Response(
            {'detail': 'Your Password has been successfully reset.'},
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _invalid_link_response():
        """Return one response for every unusable password-reset link."""
        return Response(
            {'detail': 'Password reset link is invalid or expired.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PasswordResetView(APIView):
    """Queue password-reset emails without disclosing account existence."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        tags=AUTH_TAG,
        request=PasswordResetRequestSerializer,
        responses=PASSWORD_RESET_RESPONSES,
        description=PASSWORD_RESET_DESCRIPTION,
        auth=[],
    )
    def post(self, request):
        """Validate an email and queue reset links for eligible accounts."""
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        users = User.objects.filter(  # type:ignore
            email__iexact=serializer.validated_data['email'],  # type:ignore
            is_active=True,
        ).order_by('pk')

        queue = None
        for user in users:
            if not user.has_usable_password():
                continue

            if queue is None:
                queue = get_queue('default')

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            queue.enqueue(send_password_reset_email, user, uid, token)

        return Response(
            {
                'detail': 'An email has been sent to reset your password.',
            },
            status=status.HTTP_200_OK,
        )


class RegistrationView(APIView):
    """Create inactive user accounts and queue their activation emails."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        tags=AUTH_TAG,
        request=RegistrationSerializer,
        responses=REGISTRATION_RESPONSES,
        description=REGISTRATION_DESCRIPTION,
        auth=[],
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
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        tags=AUTH_TAG,
        request=None,
        parameters=ACTIVATION_PARAMETERS,
        responses=ACTIVATION_RESPONSES,
        description=ACTIVATION_DESCRIPTION,
        auth=[],
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


class CookieTokenRefreshView(APIView):
    """Rotate JWTs using only the HTTP-only refresh-token cookie."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        tags=AUTH_TAG,
        request=None,
        responses=TOKEN_REFRESH_RESPONSES,
        parameters=TOKEN_REFRESH_PARAMETERS,
        description=TOKEN_REFRESH_DESCRIPTION,
        auth=[],
    )
    def post(self, request):
        """Validate and rotate the refresh token, then issue fresh cookies."""
        raw_refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)

        if not raw_refresh_token:
            return self._error_response(
                'Refresh token is required.',
                status.HTTP_400_BAD_REQUEST,
            )

        CookieJWTAuthentication.enforce_csrf(request)

        serializer = TokenRefreshSerializer(data={'refresh': raw_refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except (AuthenticationFailed, TokenError, User.DoesNotExist):
            return self._error_response(
                'Refresh token is invalid or expired.',
                status.HTTP_401_UNAUTHORIZED,
            )

        access_token = serializer.validated_data['access']  # type:ignore
        refresh_token = serializer.validated_data['refresh']  # type:ignore
        response = Response(
            {
                'detail': 'Token refreshed',
                'access': access_token,
            },
            status=status.HTTP_200_OK,
        )
        set_jwt_cookies(response, access_token, refresh_token)
        response['Cache-Control'] = 'no-store'
        return response

    @staticmethod
    def _error_response(detail, response_status):
        """Return a non-cacheable error and expire stale JWT cookies."""
        response = Response({'detail': detail}, status=response_status)
        delete_jwt_cookies(response)
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
        raw_refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)

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
