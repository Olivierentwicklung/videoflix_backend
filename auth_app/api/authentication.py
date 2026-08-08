"""Authentication classes for JWTs transported in HTTP-only cookies."""

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate with a Bearer header or the access-token cookie."""

    def authenticate(self, request: Request):
        """Validate a header token first, then fall back to the JWT cookie."""
        if self.get_header(request) is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(settings.JWT_ACCESS_COOKIE_NAME)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)
        self.enforce_csrf(request)
        return user, validated_token

    @staticmethod
    def enforce_csrf(request: Request):
        """Require Django's CSRF cookie/header pair for cookie authentication."""
        check = CSRFCheck(lambda _: None)  # type:ignore
        check.process_request(request)  # type:ignore
        reason = check.process_view(request, None, (), {})  # type:ignore

        if reason:
            raise exceptions.PermissionDenied(f'CSRF Failed: {reason}')
