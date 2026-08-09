from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import resolve, reverse
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()


@pytest.fixture(name='api_client')
def api_client_fixture():
    """Return a DRF client for token-refresh requests."""
    return APIClient()


@pytest.fixture(name='active_user')
def active_user_fixture():
    """Create an active user whose refresh token can be rotated."""
    return User.objects.create_user(  # type:ignore
        username='refresh@example.com',
        email='refresh@example.com',
        password='securepassword',
    )


@pytest.fixture(name='refresh_token')
def refresh_token_fixture(active_user):
    """Return a valid refresh token for the active-user fixture."""
    return str(RefreshToken.for_user(active_user))


def set_refresh_cookie(api_client, settings, token):
    """Attach a refresh token using the configured cookie name."""
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = str(token)


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
def test_token_refresh_returns_exact_success_contract(
    api_client,
    active_user,
    refresh_token,
    settings,
):
    """Return the documented body and a usable access token."""
    set_refresh_cookie(api_client, settings, refresh_token)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        'detail': 'Token refreshed',
        'access': response.data['access'],
    }
    assert (
        response.data['access']
        == response.cookies[settings.JWT_ACCESS_COOKIE_NAME].value
    )
    assert AccessToken(response.data['access'])['user_id'] == str(active_user.pk)
    assert 'refresh' not in response.data
    assert response['Cache-Control'] == 'no-store'


@pytest.mark.django_db
def test_token_refresh_rotates_and_blacklists_refresh_token(
    api_client,
    active_user,
    settings,
):
    """Rotate the refresh cookie and revoke the token that was consumed."""
    original = RefreshToken.for_user(active_user)
    original_value = str(original)
    set_refresh_cookie(api_client, settings, original_value)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    rotated_value = response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value
    assert response.status_code == status.HTTP_200_OK
    assert rotated_value != original_value
    assert RefreshToken(rotated_value)['user_id'] == str(active_user.pk)
    assert BlacklistedToken.objects.filter(token__jti=original['jti']).exists()


@pytest.mark.django_db
def test_token_refresh_sets_both_cookies_with_central_policy(
    api_client,
    refresh_token,
    settings,
):
    """Apply the configured security, lifetime, and path to rotated JWTs."""
    settings.JWT_COOKIE_SECURE = True
    settings.JWT_COOKIE_SAMESITE = 'Lax'
    set_refresh_cookie(api_client, settings, refresh_token)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    expected_cookies = {
        settings.JWT_ACCESS_COOKIE_NAME: (
            settings.JWT_ACCESS_COOKIE_PATH,
            settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
        ),
        settings.JWT_REFRESH_COOKIE_NAME: (
            settings.JWT_REFRESH_COOKIE_PATH,
            settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
        ),
    }
    for cookie_name, (expected_path, expected_lifetime) in expected_cookies.items():
        cookie = response.cookies[cookie_name]
        assert cookie.value
        assert cookie['httponly'] is True
        assert cookie['secure'] is True
        assert cookie['samesite'] == settings.JWT_COOKIE_SAMESITE
        assert cookie['path'] == expected_path
        assert int(cookie['max-age']) == int(expected_lifetime.total_seconds())


@pytest.mark.django_db
@pytest.mark.parametrize('refresh_cookie', [None, ''])
def test_token_refresh_rejects_missing_or_empty_cookie(
    api_client,
    settings,
    refresh_cookie,
):
    """Return 400 and clear stale authentication when the cookie is absent."""
    if refresh_cookie is not None:
        set_refresh_cookie(api_client, settings, refresh_cookie)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'detail': 'Refresh token is required.'}
    assert response['Cache-Control'] == 'no-store'
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_token_refresh_does_not_accept_token_from_request_body(
    api_client,
    refresh_token,
    settings,
):
    """Require the HttpOnly cookie instead of accepting a body fallback."""
    response = api_client.post(
        reverse('token_refresh'),
        {'refresh': refresh_token},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'detail': 'Refresh token is required.'}
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_token_refresh_ignores_request_body_when_cookie_is_present(
    api_client,
    refresh_token,
    settings,
):
    """Use only the cookie even if the body contains another token value."""
    set_refresh_cookie(api_client, settings, refresh_token)

    response = api_client.post(
        reverse('token_refresh'),
        {'refresh': 'invalid-body-token'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_token_refresh_rejects_malformed_token(api_client, settings):
    """Return the stable 401 contract for malformed refresh tokens."""
    set_refresh_cookie(api_client, settings, 'invalid-token')

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert response['Cache-Control'] == 'no-store'
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_token_refresh_rejects_expired_token(
    api_client,
    active_user,
    settings,
):
    """Reject an expired refresh token and clear both JWT cookies."""
    refresh = RefreshToken.for_user(active_user)
    refresh.set_exp(lifetime=timedelta(seconds=-1))
    set_refresh_cookie(api_client, settings, refresh)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_token_refresh_rejects_blacklisted_token(
    api_client,
    active_user,
    settings,
):
    """Reject a previously revoked refresh token."""
    refresh = RefreshToken.for_user(active_user)
    raw_refresh = str(refresh)
    refresh.blacklist()
    set_refresh_cookie(api_client, settings, raw_refresh)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_token_refresh_rejects_access_token_in_refresh_cookie(
    api_client,
    active_user,
    settings,
):
    """Reject a valid JWT whose token type is not refresh."""
    access = RefreshToken.for_user(active_user).access_token
    set_refresh_cookie(api_client, settings, access)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_token_refresh_rejects_token_for_inactive_user(
    api_client,
    active_user,
    settings,
):
    """Do not issue new credentials after the user is deactivated."""
    refresh = RefreshToken.for_user(active_user)
    active_user.is_active = False
    active_user.save(update_fields=['is_active'])
    set_refresh_cookie(api_client, settings, refresh)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_token_refresh_rejects_token_for_deleted_user(
    api_client,
    active_user,
    settings,
):
    """Treat a token whose user no longer exists as invalid."""
    refresh = RefreshToken.for_user(active_user)
    active_user.delete()
    set_refresh_cookie(api_client, settings, refresh)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert_jwt_cookies_deleted(response, settings)


@pytest.mark.django_db
def test_token_refresh_rejects_reuse_after_rotation(
    api_client,
    refresh_token,
    settings,
):
    """Reject the original refresh token after it has been rotated."""
    set_refresh_cookie(api_client, settings, refresh_token)
    first_response = api_client.post(
        reverse('token_refresh'),
        {},
        format='json',
    )
    assert first_response.status_code == status.HTTP_200_OK

    set_refresh_cookie(api_client, settings, refresh_token)
    second_response = api_client.post(
        reverse('token_refresh'),
        {},
        format='json',
    )

    assert second_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert second_response.data == {'detail': 'Refresh token is invalid or expired.'}
    assert_jwt_cookies_deleted(second_response, settings)


@pytest.mark.django_db
def test_token_refresh_ignores_invalid_access_cookie(
    api_client,
    refresh_token,
    settings,
):
    """Refresh successfully without authenticating the stale access cookie."""
    api_client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = 'invalid-token'
    set_refresh_cookie(api_client, settings, refresh_token)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_token_refresh_enforces_csrf_for_refresh_cookie(
    refresh_token,
    settings,
):
    """Reject cookie-based refresh without a CSRF cookie and header."""
    api_client = APIClient(enforce_csrf_checks=True)
    set_refresh_cookie(api_client, settings, refresh_token)

    response = api_client.post(reverse('token_refresh'), {}, format='json')

    assert response.status_code == status.HTTP_403_FORBIDDEN  # type:ignore


@pytest.mark.django_db
def test_token_refresh_accepts_valid_csrf_cookie_and_header(
    active_user,
    settings,
):
    """Allow browser refresh when the CSRF cookie/header pair matches."""
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
        reverse('token_refresh'),
        {},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == status.HTTP_200_OK  # type:ignore


@pytest.mark.parametrize('method', ['get', 'put', 'patch', 'delete'])
def test_token_refresh_rejects_unsupported_methods(api_client, method):
    """Expose token refresh only through POST."""
    response = getattr(api_client, method)(reverse('token_refresh'))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_token_refresh_is_public_unthrottled_and_skips_access_authentication():
    """Lock the endpoint's refresh-cookie-only access contract."""
    view_class = resolve(reverse('token_refresh')).func.view_class  # type:ignore

    assert view_class.permission_classes == [AllowAny]
    assert view_class.authentication_classes == []
    assert view_class.throttle_classes == []


def test_token_refresh_openapi_contract():
    """Expose cookie, CSRF, empty-body, and response contracts in OpenAPI."""
    operation = SchemaGenerator().get_schema(
        request=None,
        public=True,
    )['paths']['/api/token/refresh/']['post']

    parameters = {
        (parameter['name'], parameter['in']): parameter
        for parameter in operation['parameters']
    }

    assert 'requestBody' not in operation
    assert not operation.get('security')
    assert parameters[('refresh_token', 'cookie')]['required'] is True
    assert parameters[('X-CSRFToken', 'header')]['required'] is True
    assert set(operation['responses']) == {'200', '400', '401', '403'}
    for response_status in ('200', '400', '401'):
        assert 'Set-Cookie' in operation['responses'][response_status]['headers']
    assert 'headers' not in operation['responses']['403']
