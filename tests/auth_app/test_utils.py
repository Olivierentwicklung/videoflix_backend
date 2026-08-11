"""Tests for authentication email utilities."""

from django.core import mail

from auth_app.api.utils import send_html_email


def test_send_html_email_without_inline_images():
    """Send a multipart email without creating related image parts."""
    sent_count = send_html_email(
        subject='Test email',
        template_name='emails/activation_email.html',
        context={
            'activation_link': 'https://example.com/activate',
            'email': 'user@example.com',
            'site_url': 'https://example.com',
        },
        recipient='user@example.com',
    )

    assert sent_count == 1
    assert len(mail.outbox) == 1

    message = mail.outbox[0]
    assert message.to == ['user@example.com']
    assert message.subject == 'Test email'
    assert message.mixed_subtype == 'mixed'  # type:ignore
    assert message.attachments == []
    assert len(message.alternatives) == 1  # type:ignore
    assert message.alternatives[0].mimetype == 'text/html'  # type:ignore
