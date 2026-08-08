import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
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
    assert mail.outbox[0].to == [registration_data['email']]
    assert response.data['token'] in mail.outbox[0].body


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
