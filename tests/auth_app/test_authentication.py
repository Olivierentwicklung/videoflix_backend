import pytest
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from rest_framework import exceptions
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from auth_app.api.authentication import CookieJWTAuthentication

User = get_user_model()


@pytest.fixture(name='active_user')
def active_user_fixture():
    """Create an active user for JWT authentication tests."""
    return User.objects.create_user(  # type:ignore
        username='user@example.com',
        email='user@example.com',
        password='securepassword',
    )


def access_token_for(user):
    """Issue an access token for the supplied user."""
    return str(RefreshToken.for_user(user).access_token)


@pytest.mark.django_db
def test_authenticates_safe_request_from_configured_cookie(active_user, settings):
    """Authenticate a safe request using the configured access cookie."""
    settings.JWT_ACCESS_COOKIE_NAME = 'custom_access_token'
    raw_request = APIRequestFactory().get('/api/protected/')
    raw_request.COOKIES[settings.JWT_ACCESS_COOKIE_NAME] = access_token_for(
        active_user
    )

    result = CookieJWTAuthentication().authenticate(Request(raw_request))

    assert result is not None
    authenticated_user, _ = result
    assert authenticated_user == active_user


@pytest.mark.django_db
def test_cookie_authentication_rejects_unsafe_request_without_csrf(active_user):
    """Reject cookie-authenticated writes without CSRF credentials."""
    raw_request = APIRequestFactory(enforce_csrf_checks=True).post(
        '/api/protected/'
    )
    raw_request.COOKIES['access_token'] = access_token_for(active_user)

    with pytest.raises(exceptions.PermissionDenied, match='CSRF Failed'):
        CookieJWTAuthentication().authenticate(Request(raw_request))


@pytest.mark.django_db
def test_cookie_authentication_accepts_unsafe_request_with_csrf(active_user):
    """Accept cookie-authenticated writes with a valid CSRF cookie/header pair."""
    raw_request = APIRequestFactory(enforce_csrf_checks=True).post(
        '/api/protected/'
    )
    csrf_token = get_token(raw_request)
    raw_request.COOKIES['csrftoken'] = raw_request.META['CSRF_COOKIE']
    raw_request.META['HTTP_X_CSRFTOKEN'] = csrf_token
    raw_request.COOKIES['access_token'] = access_token_for(active_user)

    result = CookieJWTAuthentication().authenticate(Request(raw_request))

    assert result is not None
    authenticated_user, _ = result
    assert authenticated_user == active_user


@pytest.mark.django_db
def test_bearer_authentication_does_not_require_csrf(active_user):
    """Keep CSRF checks out of explicit Authorization-header authentication."""
    raw_request = APIRequestFactory().post(
        '/api/protected/',
        HTTP_AUTHORIZATION=f'Bearer {access_token_for(active_user)}',
    )

    result = CookieJWTAuthentication().authenticate(Request(raw_request))

    assert result is not None
    authenticated_user, _ = result
    assert authenticated_user == active_user


def test_returns_none_without_header_or_cookie():
    """Allow other authenticators to run when no JWT credentials are supplied."""
    raw_request = APIRequestFactory().get('/api/protected/')

    assert CookieJWTAuthentication().authenticate(Request(raw_request)) is None
