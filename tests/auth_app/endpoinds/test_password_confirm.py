from datetime import datetime, timedelta

import pytest
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import resolve, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

SUCCESS_RESPONSE = {
    'detail': 'Your Password has been successfully reset.',
}
INVALID_LINK_RESPONSE = {
    'detail': 'Password reset link is invalid or expired.',
}
NEW_PASSWORD = 'EvenMoreSecurePassword!321'


@pytest.fixture
def api_client():
    """Return a DRF client for password-confirm requests."""
    return APIClient()


@pytest.fixture
def active_user():
    """Create an active user with a resettable password."""
    return User.objects.create_user(  # type:ignore
        username='user@example.com',
        email='user@example.com',
        password='OldSecurePassword!123',
        is_active=True,
    )


def password_confirm_url(user, token=None):
    """Build a password-confirm URL for a user and optional token."""
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    reset_token = token or default_token_generator.make_token(user)
    return reverse(
        'password_confirm',
        kwargs={'uidb64': uidb64, 'token': reset_token},
    )


def valid_payload(password=NEW_PASSWORD):
    """Return matching password-confirm fields."""
    return {
        'new_password': password,
        'confirm_password': password,
    }


@pytest.mark.django_db
def test_password_confirm_resets_password(api_client, active_user):
    """Reset the password and return the documented success response."""
    old_password_hash = active_user.password

    response = api_client.post(
        password_confirm_url(active_user),
        valid_payload(),
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == SUCCESS_RESPONSE

    active_user.refresh_from_db()
    assert active_user.password != old_password_hash
    assert active_user.password != NEW_PASSWORD
    assert active_user.check_password(NEW_PASSWORD)
    assert (
        authenticate(
            username=active_user.username,
            password=NEW_PASSWORD,
        )
        == active_user
    )
    assert (
        authenticate(
            username=active_user.username,
            password='OldSecurePassword!123',
        )
        is None
    )


@pytest.mark.django_db
def test_password_confirm_rejects_reused_token(api_client, active_user):
    """Invalidate the reset token after the password is changed."""
    url = password_confirm_url(active_user)

    first_response = api_client.post(url, valid_payload(), format='json')
    second_response = api_client.post(url, valid_payload(), format='json')

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_400_BAD_REQUEST
    assert second_response.data == INVALID_LINK_RESPONSE


@pytest.mark.django_db
@pytest.mark.parametrize('uidb64', ['invalid-uid', 'OTk5OTk5'])
def test_password_confirm_rejects_invalid_or_unknown_uid(
    api_client,
    active_user,
    uidb64,
):
    """Return one generic error for malformed and unknown user IDs."""
    token = default_token_generator.make_token(active_user)
    response = api_client.post(
        reverse(
            'password_confirm',
            kwargs={'uidb64': uidb64, 'token': token},
        ),
        valid_payload(),
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == INVALID_LINK_RESPONSE


@pytest.mark.django_db
def test_password_confirm_rejects_invalid_token(api_client, active_user):
    """Reject a token that was not issued for the target user."""
    response = api_client.post(
        password_confirm_url(active_user, token='invalid-token'),
        valid_payload(),
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == INVALID_LINK_RESPONSE


@pytest.mark.django_db
def test_password_confirm_rejects_expired_token(
    api_client,
    active_user,
    monkeypatch,
):
    """Reject an otherwise valid token after its configured lifetime."""
    issued_at = datetime(2026, 1, 1, 12, 0, 0)
    monkeypatch.setattr(default_token_generator, '_now', lambda: issued_at)
    token = default_token_generator.make_token(active_user)

    expired_at = issued_at + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1)
    monkeypatch.setattr(default_token_generator, '_now', lambda: expired_at)

    response = api_client.post(
        password_confirm_url(active_user, token=token),
        valid_payload(),
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == INVALID_LINK_RESPONSE


@pytest.mark.django_db
def test_password_confirm_rejects_inactive_user(api_client):
    """Do not reset the password of an inactive account."""
    user = User.objects.create_user(  # type:ignore
        username='inactive@example.com',
        email='inactive@example.com',
        password='OldSecurePassword!123',
        is_active=False,
    )
    old_password_hash = user.password

    response = api_client.post(
        password_confirm_url(user),
        valid_payload(),
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == INVALID_LINK_RESPONSE
    user.refresh_from_db()
    assert user.password == old_password_hash


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('payload', 'error_fields'),
    [
        ({}, {'new_password', 'confirm_password'}),
        (
            {'new_password': '', 'confirm_password': ''},
            {'new_password', 'confirm_password'},
        ),
    ],
)
def test_password_confirm_requires_non_blank_password_fields(
    api_client,
    active_user,
    payload,
    error_fields,
):
    """Require both password fields and reject blank values."""
    response = api_client.post(
        password_confirm_url(active_user),
        payload,
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert set(response.data) == error_fields


@pytest.mark.django_db
def test_password_confirm_requires_matching_passwords(api_client, active_user):
    """Attach a mismatch error to the confirmation field."""
    response = api_client.post(
        password_confirm_url(active_user),
        {
            'new_password': NEW_PASSWORD,
            'confirm_password': 'DifferentSecurePassword!456',
        },
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {
        'confirm_password': ['Passwords do not match.'],
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    'password',
    [
        'short',
        'password',
        '1234567890123456',
        'user@example.com',
    ],
)
def test_password_confirm_applies_django_password_validators(
    api_client,
    active_user,
    password,
):
    """Reject short, common, numeric, and user-similar passwords."""
    response = api_client.post(
        password_confirm_url(active_user),
        valid_payload(password),
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'new_password' in response.data


@pytest.mark.django_db
def test_password_confirm_blacklists_outstanding_refresh_tokens(
    api_client,
    active_user,
):
    """Revoke every outstanding refresh token after a successful reset."""
    refresh_tokens = [RefreshToken.for_user(active_user) for _ in range(2)]
    token_ids = [token['jti'] for token in refresh_tokens]

    response = api_client.post(
        password_confirm_url(active_user),
        valid_payload(),
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert BlacklistedToken.objects.filter(token__jti__in=token_ids).count() == 2


@pytest.mark.django_db
def test_password_confirm_does_not_require_authentication(api_client, active_user):
    """Allow anonymous clients to confirm a password reset."""
    response = api_client.post(
        password_confirm_url(active_user),
        valid_payload(),
        format='json',
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED
    assert response.status_code != status.HTTP_403_FORBIDDEN


def test_password_confirm_has_no_throttles():
    """Keep the endpoint exempt from configured DRF throttles."""
    view_class = resolve(
        '/api/password_confirm/example-uid/example-token/'
    ).func.view_class  # type:ignore

    assert view_class.throttle_classes == []
