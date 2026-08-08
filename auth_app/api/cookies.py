"""Helpers for transporting JWTs in secure HTTP-only cookies."""

from django.conf import settings


def set_jwt_cookies(response, access_token, refresh_token):
    """Attach access and refresh JWTs using the central cookie policy."""
    common_options = {
        'httponly': settings.JWT_COOKIE_HTTPONLY,
        'secure': settings.JWT_COOKIE_SECURE,
        'samesite': settings.JWT_COOKIE_SAMESITE,
        'domain': settings.JWT_COOKIE_DOMAIN,
    }

    response.set_cookie(
        key=settings.JWT_ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=int(
            settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
        ),
        path=settings.JWT_ACCESS_COOKIE_PATH,
        **common_options,
    )
    response.set_cookie(
        key=settings.JWT_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=int(
            settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
        ),
        path=settings.JWT_REFRESH_COOKIE_PATH,
        **common_options,
    )

    return response


def delete_jwt_cookies(response):
    """Expire both JWT cookies using the paths used when they were set."""
    common_options = {
        'domain': settings.JWT_COOKIE_DOMAIN,
        'samesite': settings.JWT_COOKIE_SAMESITE,
    }

    response.delete_cookie(
        key=settings.JWT_ACCESS_COOKIE_NAME,
        path=settings.JWT_ACCESS_COOKIE_PATH,
        **common_options,
    )
    response.delete_cookie(
        key=settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_REFRESH_COOKIE_PATH,
        **common_options,
    )

    return response
