from html import unescape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_html_email(subject, template_name, context, recipient):
    """Render and send an email with plain-text and HTML versions."""
    html_message = render_to_string(template_name, context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=unescape(strip_tags(html_message)),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    email.attach_alternative(html_message, 'text/html')
    return email.send()


def send_activation_email(user, uid, token):
    """Send an account activation email to the given user."""
    activation_link = (
        f'{settings.FRONTEND_URL}/pages/auth/activate.html'
        f'?uid={uid}&token={token}'
    )
    logo_url = f'{settings.BACKEND_URL}/static/images/logo.svg'

    return send_html_email(
        subject='Activate your Videoflix account',
        template_name='emails/activation_email.html',
        context={
            'activation_link': activation_link,
            'email': user.email,
            'logo_url': logo_url,
            'site_url': settings.FRONTEND_URL,
        },
        recipient=user.email,
    )
