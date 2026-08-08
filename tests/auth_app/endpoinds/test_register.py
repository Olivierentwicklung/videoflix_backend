from html import unescape

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from fakeredis import FakeStrictRedis
from rest_framework import status
from rest_framework.test import APIClient
from rq import Queue

User = get_user_model()


@pytest.fixture
def api_client():
    """Return a DRF client for requests to the registration endpoint."""
    return APIClient()


@pytest.fixture
def fake_rq_queue(monkeypatch):
    """Execute queued jobs immediately without requiring Redis or an RQ worker."""
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
def registration_data():
    """Return a valid registration payload for use in endpoint tests."""
    return {
        'email': 'user@example.com',
        'password': 'securepassword',
        'confirmed_password': 'securepassword',
    }


@pytest.mark.django_db
def test_register_creates_inactive_user(
    api_client,
    fake_rq_queue,
    registration_data,
):
    """Create an inactive user and send an activation email on registration."""
    response = api_client.post(
        reverse('register'),
        registration_data,
        format='json',
    )

    assert response.status_code == status.HTTP_201_CREATED

    user = User.objects.get(email=registration_data['email'])
    assert user.is_active is False
    assert user.check_password(registration_data['password'])
    assert response.data == {
        'user': {
            'id': user.pk,
            'email': registration_data['email'],
        },
        'token': response.data['token'],
    }

    assert len(mail.outbox) == 1
    activation_email = mail.outbox[0]
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    activation_url = (
        'http://127.0.0.1:5500/pages/auth/activate.html'
        f'?uid={uid}&token={response.data["token"]}'
    )

    assert activation_email.to == [registration_data['email']]
    assert activation_email.subject == 'Activate your Videoflix account'
    assert activation_url in activation_email.body
    assert len(activation_email.alternatives) == 1  # type:ignore
    assert activation_email.alternatives[0].mimetype == 'text/html'  # type:ignore
    html_message = unescape(activation_email.alternatives[0].content)  # type:ignore
    assert activation_url in html_message
    assert 'http://127.0.0.1:8000/static/images/logo.svg' in html_message


@pytest.mark.django_db
def test_register_rejects_non_matching_passwords(api_client, registration_data):
    """Reject registration when password confirmation does not match."""
    registration_data['confirmed_password'] = 'differentpassword'

    response = api_client.post(
        reverse('register'),
        registration_data,
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'confirmed_password' in response.data
    assert not User.objects.exists()
    assert not mail.outbox


@pytest.mark.django_db
def test_register_rejects_existing_email_case_insensitively(
    api_client,
    registration_data,
):
    """Reject an email already registered with different letter casing."""
    User.objects.create_user(  # type:ignore
        username=registration_data['email'],
        email=registration_data['email'],
        password=registration_data['password'],
    )
    registration_data['email'] = registration_data['email'].upper()

    response = api_client.post(
        reverse('register'),
        registration_data,
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'email' in response.data
    assert User.objects.count() == 1
    assert not mail.outbox


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('email', 'not-an-email'),
        ('email', ''),
        ('password', ''),
        ('confirmed_password', ''),
    ],
)
def test_register_rejects_invalid_required_fields(
    api_client,
    registration_data,
    field,
    value,
):
    """Reject invalid or empty values for every required request field."""
    registration_data[field] = value

    response = api_client.post(
        reverse('register'),
        registration_data,
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.data
    assert not User.objects.exists()
    assert not mail.outbox
