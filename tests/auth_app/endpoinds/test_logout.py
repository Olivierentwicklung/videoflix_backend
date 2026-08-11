"""Tests for user logout endpoints."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import resolve, reverse
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@pytest.fixture(name='api_client')
def api_client_fixture():
    """Return a DRF client for logout endpoint requests."""
    return APIClient()


@pytest.fixture(name='active_user')
def active_user_fixture():
    """Create an active user whose refresh token can be revoked."""
    return User.objects.create_user(  # type:ignore
        username='logout@example.com',
        email='logout@example.com',
        password='securepassword',
    )


@pytest.fixture(name='refresh_token')
def refresh_token_fixture(active_user):
    """Return a valid refresh token for the active-user fixture."""
    return str(RefreshToken.for_user(active_user))


def assert_jwt_cookies_deleted(response, settings):
    """Assert that both JWT cookies are expired with their original scope."""
    cookie_paths = {
        settings.JWT_ACCESS_COOKIE_NAME: settings.JWT_ACCESS_COOKIE_PATH,
        settings.JWT_REFRESH_COOKIE_NAME: settings.JWT_REFRESH_COOKIE_PATH,
    }

    for cookie_name, expected_path in cookie_paths.items():
        cookie = response.cookies[cookie_name]
        assert cookie.value == ''
        assert cookie['max-age'] == 0
        assert cookie['path'] == expected_path
        assert cookie['domain'] == (settings.JWT_COOKIE_DOMAIN or '')
        assert cookie['samesite'] == settings.JWT_COOKIE_SAMESITE


@pytest.mark.django_db
def test_logout_returns_exact_success_contract(
    api_client,
    refresh_token,
    settings,
):
    """Return the documented response for a valid refresh cookie."""
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = refresh_token

    response = api_client.post(reverse('logout'), {}, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        'detail': (
            'Logout successful! All tokens will be deleted. '
            'Refresh token is now invalid.'
        )
    }
    assert response['Cache-Control'] == 'no-store'


@pytest.mark.django_db
def test_logout_blacklists_refresh_token_and_deletes_cookies(
    api_client,
    active_user,
    settings,
):
    """Persist revocation and expire both browser JWT cookies on success."""
    refresh = RefreshToken.for_user(active_user)
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = str(refresh)

    response = api_client.post(reverse('logout'), {}, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists()
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
@pytest.mark.parametrize('refresh_cookie', [None, ''])
def test_logout_rejects_missing_or_empty_refresh_cookie(
    api_client,
    settings,
    refresh_cookie,
):
    """Require a non-empty refresh-token cookie."""
    if refresh_cookie is not None:
        api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = refresh_cookie

    response = api_client.post(reverse('logout'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'detail': 'Refresh token is required.'}
    assert response['Cache-Control'] == 'no-store'
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_logout_rejects_invalid_refresh_token(api_client, settings):
    """Return the stable bad-request contract for an invalid refresh JWT."""
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = 'invalid-token'

    response = api_client.post(reverse('logout'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert response['Cache-Control'] == 'no-store'
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_logout_rejects_expired_refresh_token(
    api_client,
    active_user,
    settings,
):
    """Reject an expired refresh JWT and clean up both browser cookies."""
    refresh = RefreshToken.for_user(active_user)
    refresh.set_exp(lifetime=timedelta(seconds=-1))
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = str(refresh)

    response = api_client.post(reverse('logout'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_logout_rejects_already_blacklisted_refresh_token(
    api_client,
    active_user,
    settings,
):
    """Return the stable error contract for a previously revoked token."""
    refresh = RefreshToken.for_user(active_user)
    raw_refresh = str(refresh)
    refresh.blacklist()
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = raw_refresh

    response = api_client.post(reverse('logout'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_logout_ignores_invalid_access_cookie(
    api_client,
    refresh_token,
    settings,
):
    """Allow logout even when the access-token cookie cannot authenticate."""
    api_client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = 'invalid-token'
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = refresh_token

    response = api_client.post(reverse('logout'), {}, format='json')

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_logout_enforces_csrf_for_refresh_cookie(refresh_token, settings):
    """Reject cookie-authenticated logout without a CSRF cookie and header."""
    api_client = APIClient(enforce_csrf_checks=True)
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = refresh_token

    response = api_client.post(reverse('logout'), {}, format='json')

    assert response.status_code == status.HTTP_403_FORBIDDEN  # type:ignore


@pytest.mark.django_db
def test_logout_accepts_valid_csrf_cookie_and_header(active_user, settings):
    """Allow browser logout when the CSRF cookie/header pair matches."""
    api_client = APIClient(enforce_csrf_checks=True)
    login_response = api_client.post(
        reverse('login'),
        {
            'email': active_user.email,
            'password': 'securepassword',
        },
        format='json',
    )
    csrf_token = login_response.cookies[settings.CSRF_COOKIE_NAME].value  # type:ignore

    response = api_client.post(
        reverse('logout'),
        {},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == status.HTTP_200_OK  # type:ignore


@pytest.mark.parametrize('method', ['get', 'put', 'patch', 'delete'])
def test_logout_rejects_unsupported_methods(api_client, method):
    """Expose logout only through POST."""
    response = getattr(api_client, method)(reverse('logout'))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_logout_is_public_unthrottled_and_skips_access_authentication():
    """Lock the endpoint's refresh-cookie-only access contract."""
    view_class = resolve(reverse('logout')).func.view_class  # type:ignore

    assert view_class.permission_classes == [AllowAny]
    assert view_class.authentication_classes == []
    assert view_class.throttle_classes == []


def test_logout_openapi_contract():
    """Expose cookie, CSRF, empty-body, and response contracts in OpenAPI."""
    operation = SchemaGenerator().get_schema(
        request=None,
        public=True,
    )['paths']['/api/logout/']['post']

    parameters = {
        (parameter['name'], parameter['in']): parameter
        for parameter in operation['parameters']
    }

    assert 'requestBody' not in operation
    assert parameters[('refresh_token', 'cookie')]['required'] is True
    assert parameters[('X-CSRFToken', 'header')]['required'] is True
    assert set(operation['responses']) == {'200', '400', '403'}
