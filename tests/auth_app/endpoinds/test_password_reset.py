from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import resolve, reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from fakeredis import FakeStrictRedis
from rest_framework import status
from rest_framework.test import APIClient
from rq import Queue

User = get_user_model()

SUCCESS_RESPONSE = {
    'detail': 'An email has been sent to reset your password.',
}


@pytest.fixture
def api_client():
    """Return a DRF client for password-reset requests."""
    return APIClient()


@pytest.fixture
def fake_rq_queue(monkeypatch):
    """Execute queued email jobs without requiring Redis or an RQ worker."""
    queue = Queue(
        'default',
        connection=FakeStrictRedis(),
        is_async=False,
    )

    def get_queue(*args, **kwargs):
        del args, kwargs
        return queue

    monkeypatch.setattr('django_rq.get_queue', get_queue)
    monkeypatch.setattr(
        'auth_app.api.views.get_queue',
        get_queue,
        raising=False,
    )
    return queue


@pytest.fixture
def active_user():
    """Create an active user eligible for a password reset."""
    return User.objects.create_user(  # type:ignore
        username='user@example.com',
        email='user@example.com',
        password='securepassword',
        is_active=True,
    )


def extract_reset_credentials(email):
    """Extract the UID and token query parameters from a reset email."""
    html_message = email.alternatives[0].content  # type:ignore
    marker = 'href="'
    link_start = html_message.index(marker) + len(marker)
    link_end = html_message.index('"', link_start)
    query = parse_qs(urlparse(html_message[link_start:link_end]).query)
    return query['uid'][0], query['token'][0]


@pytest.mark.django_db
def test_password_reset_sends_email_for_existing_active_user(
    api_client,
    fake_rq_queue,
    active_user,
):
    """Queue a reset email containing valid credentials for an active user."""
    response = api_client.post(
        reverse('password_reset'),
        {'email': active_user.email},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == SUCCESS_RESPONSE
    assert len(mail.outbox) == 1

    reset_email = mail.outbox[0]
    assert reset_email.to == [active_user.email]
    assert len(reset_email.alternatives) == 1  # type:ignore

    uidb64, token = extract_reset_credentials(reset_email)
    assert force_str(urlsafe_base64_decode(uidb64)) == str(active_user.pk)
    assert default_token_generator.check_token(active_user, token)


@pytest.mark.django_db
def test_password_reset_finds_email_case_insensitively(
    api_client,
    fake_rq_queue,
    active_user,
):
    """Find an existing account regardless of the submitted email casing."""
    response = api_client.post(
        reverse('password_reset'),
        {'email': active_user.email.upper()},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == SUCCESS_RESPONSE
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [active_user.email]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('email', 'is_active'),
    [
        ('unknown@example.com', None),
        ('inactive@example.com', False),
    ],
)
def test_password_reset_does_not_disclose_ineligible_accounts(
    api_client,
    fake_rq_queue,
    email,
    is_active,
):
    """Return the generic success response without revealing account state."""
    if is_active is not None:
        User.objects.create_user(  # type:ignore
            username=email,
            email=email,
            password='securepassword',
            is_active=is_active,
        )

    response = api_client.post(
        reverse('password_reset'),
        {'email': email},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == SUCCESS_RESPONSE
    assert not mail.outbox


@pytest.mark.django_db
@pytest.mark.parametrize('payload', [{}, {'email': ''}, {'email': 'invalid'}])
def test_password_reset_rejects_missing_or_invalid_email(api_client, payload):
    """Reject requests that do not contain a syntactically valid email."""
    response = api_client.post(
        reverse('password_reset'),
        payload,
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'email' in response.data
    assert not mail.outbox


@pytest.mark.django_db
def test_password_reset_does_not_require_authentication(
    api_client,
    fake_rq_queue,
    active_user,
):
    """Allow anonymous clients to request a reset email."""
    response = api_client.post(
        reverse('password_reset'),
        {'email': active_user.email},
        format='json',
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED
    assert response.status_code != status.HTTP_403_FORBIDDEN


def test_password_reset_has_no_throttles():
    """Keep the endpoint exempt from the configured DRF throttles."""
    view_class = resolve('/api/password_reset/').func.view_class  # type:ignore

    assert view_class.throttle_classes == []
