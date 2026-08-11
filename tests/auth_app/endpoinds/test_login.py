"""Tests for user login endpoints."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import resolve, reverse
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()


@pytest.fixture(name='api_client')
def api_client_fixture():
    """Return a DRF client for login endpoint requests."""
    return APIClient()


@pytest.fixture(name='active_user')
def active_user_fixture():
    """Create an active user that can log in."""
    return User.objects.create_user(  # type:ignore
        username='user@example.com',
        email='user@example.com',
        password='securepassword',
    )


@pytest.fixture(name='login_data')
def login_data_fixture():
    """Return valid credentials for the active-user fixture."""
    return {
        'email': 'user@example.com',
        'password': 'securepassword',
    }


@pytest.mark.django_db
def test_login_returns_user_and_sets_valid_jwt_cookies(
    api_client,
    active_user,
    login_data,
    settings,
):
    """Return public user data and transport both JWTs only in cookies."""
    settings.JWT_COOKIE_SECURE = True
    settings.JWT_COOKIE_SAMESITE = 'Lax'

    response = api_client.post(reverse('login'), login_data, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        'detail': 'Login successful',
        'user': {
            'id': active_user.pk,
            'username': active_user.username,
        },
    }
    assert 'access' not in response.data
    assert 'refresh' not in response.data

    access_cookie = response.cookies[settings.JWT_ACCESS_COOKIE_NAME]
    refresh_cookie = response.cookies[settings.JWT_REFRESH_COOKIE_NAME]

    assert access_cookie.value
    assert access_cookie['httponly'] is True
    assert access_cookie['secure'] is True
    assert access_cookie['samesite'] == settings.JWT_COOKIE_SAMESITE
    assert access_cookie['path'] == settings.JWT_ACCESS_COOKIE_PATH
    assert int(access_cookie['max-age']) == int(
        settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
    )

    assert refresh_cookie.value
    assert refresh_cookie['httponly'] is True
    assert refresh_cookie['secure'] is True
    assert refresh_cookie['samesite'] == settings.JWT_COOKIE_SAMESITE
    assert refresh_cookie['path'] == settings.JWT_REFRESH_COOKIE_PATH
    assert int(refresh_cookie['max-age']) == int(
        settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
    )

    assert AccessToken(access_cookie.value)['user_id'] == str(active_user.pk)
    assert RefreshToken(refresh_cookie.value)['user_id'] == str(active_user.pk)
    assert response['Cache-Control'] == 'no-store'


@pytest.mark.django_db
def test_login_sets_csrf_cookie_for_authenticated_writes(
    api_client,
    active_user,
    login_data,
    settings,
):
    """Bootstrap the readable CSRF cookie required after cookie login."""
    del active_user

    response = api_client.post(reverse('login'), login_data, format='json')

    csrf_cookie = response.cookies[settings.CSRF_COOKIE_NAME]
    assert csrf_cookie.value
    assert csrf_cookie['httponly'] == ''
    assert bool(csrf_cookie['secure']) is settings.CSRF_COOKIE_SECURE
    assert csrf_cookie['samesite'] == settings.CSRF_COOKIE_SAMESITE


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('email', 'password'),
    [
        ('unknown@example.com', 'securepassword'),
        ('user@example.com', 'wrongpassword'),
    ],
)
def test_login_rejects_invalid_credentials_generically(
    api_client,
    active_user,
    email,
    password,
):
    """Do not reveal whether an email address exists."""
    del active_user

    response = api_client.post(
        reverse('login'),
        {'email': email, 'password': password},
        format='json',
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'detail': 'Invalid email or password.'}
    assert not response.cookies


@pytest.mark.django_db
def test_login_rejects_inactive_user_with_generic_response(
    api_client,
    active_user,
    login_data,
):
    """Reject inactive accounts without disclosing their activation state."""
    active_user.is_active = False
    active_user.save(update_fields=['is_active'])

    response = api_client.post(reverse('login'), login_data, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'detail': 'Invalid email or password.'}
    assert not response.cookies


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('email', 'not-an-email'),
        ('email', ''),
        ('password', ''),
    ],
)
def test_login_rejects_invalid_fields(
    api_client,
    active_user,
    login_data,
    field,
    value,
):
    """Return field-level validation errors for malformed input."""
    del active_user
    login_data[field] = value

    response = api_client.post(reverse('login'), login_data, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.data
    assert not response.cookies


@pytest.mark.django_db
@pytest.mark.parametrize('missing_field', ['email', 'password'])
def test_login_rejects_missing_fields(
    api_client,
    active_user,
    login_data,
    missing_field,
):
    """Require both documented login fields."""
    del active_user
    login_data.pop(missing_field)

    response = api_client.post(reverse('login'), login_data, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert missing_field in response.data
    assert not response.cookies


@pytest.mark.django_db
def test_login_matches_email_case_insensitively(
    api_client,
    active_user,
    login_data,
):
    """Treat email casing consistently with registration duplicate checks."""
    login_data['email'] = login_data['email'].upper()

    response = api_client.post(reverse('login'), login_data, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data['user']['id'] == active_user.pk


@pytest.mark.django_db
def test_login_ignores_stale_authentication_cookie(
    api_client,
    active_user,
    login_data,
    settings,
):
    """Allow a fresh login even when the browser carries an invalid access JWT."""
    del active_user
    api_client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = 'invalid-token'

    response = api_client.post(reverse('login'), login_data, format='json')

    assert response.status_code == status.HTTP_200_OK


def test_login_rejects_unsupported_method(api_client):
    """Expose login only through POST."""
    response = api_client.get(reverse('login'))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_login_is_public_unthrottled_and_ignores_existing_authentication():
    """Match the endpoint's explicit permission and rate-limit contract."""
    view_class = resolve(reverse('login')).func.view_class

    assert view_class.permission_classes == [AllowAny]
    assert view_class.authentication_classes == []
    assert view_class.throttle_classes == []
