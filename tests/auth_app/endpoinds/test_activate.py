from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

from auth_app.api.tokens import account_activation_token

User = get_user_model()


@pytest.fixture
def api_client():
    """Return a DRF client for activation endpoint requests."""
    return APIClient()


@pytest.fixture
def inactive_user():
    """Create an inactive user that can be activated."""
    return User.objects.create_user(  # type:ignore
        username='user@example.com',
        email='user@example.com',
        password='securepassword',
        is_active=False,
    )


def activation_url(user, token=None):
    """Build the activation URL for a user and optional token."""
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    activation_token = token or account_activation_token.make_token(user)
    return reverse(
        'activate',
        kwargs={
            'uidb64': uidb64,
            'token': activation_token,
        },
    )


@pytest.mark.django_db
def test_activate_activates_user_with_valid_credentials(
    api_client,
    inactive_user,
):
    """Activate an inactive user when UID and token are valid."""
    response = api_client.get(activation_url(inactive_user))

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        'message': 'Account successfully activated.',
    }

    inactive_user.refresh_from_db()
    assert inactive_user.is_active is True


@pytest.mark.django_db
@pytest.mark.parametrize('uidb64', ['invalid-uid', 'MA'])
def test_activate_rejects_invalid_or_unknown_uid(
    api_client,
    inactive_user,
    uidb64,
):
    """Reject malformed UIDs and UIDs that do not identify a user."""
    token = account_activation_token.make_token(inactive_user)
    response = api_client.get(
        reverse(
            'activate',
            kwargs={'uidb64': uidb64, 'token': token},
        )
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'message': 'Activation failed.'}

    inactive_user.refresh_from_db()
    assert inactive_user.is_active is False


@pytest.mark.django_db
def test_activate_rejects_invalid_token(api_client, inactive_user):
    """Reject a token that was not issued for the user."""
    response = api_client.get(activation_url(inactive_user, token='invalid-token'))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'message': 'Activation failed.'}

    inactive_user.refresh_from_db()
    assert inactive_user.is_active is False


@pytest.mark.django_db
def test_activate_rejects_expired_token(
    api_client,
    inactive_user,
    monkeypatch,
    settings,
):
    """Reject an otherwise valid token after its configured lifetime."""
    issued_at = datetime(2026, 1, 1, 12, 0, 0)
    monkeypatch.setattr(account_activation_token, '_now', lambda: issued_at)
    token = account_activation_token.make_token(inactive_user)

    expired_at = issued_at + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1)
    monkeypatch.setattr(account_activation_token, '_now', lambda: expired_at)

    response = api_client.get(activation_url(inactive_user, token=token))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'message': 'Activation failed.'}

    inactive_user.refresh_from_db()
    assert inactive_user.is_active is False


@pytest.mark.django_db
def test_activate_rejects_reused_token(api_client, inactive_user):
    """Invalidate an activation token after its first successful use."""
    url = activation_url(inactive_user)

    first_response = api_client.get(url)
    second_response = api_client.get(url)

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_400_BAD_REQUEST
    assert second_response.data == {'message': 'Activation failed.'}

    inactive_user.refresh_from_db()
    assert inactive_user.is_active is True
