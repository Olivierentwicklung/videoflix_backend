from email.mime.image import MIMEImage
from html import unescape
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

ACTIVATION_LOGO_PATH = (
    Path(__file__).resolve().parent.parent / 'email_assets' / 'logo.png'
)
ACTIVATION_LOGO_CID = 'videoflix-logo'


def send_html_email(
    subject,
    template_name,
    context,
    recipient,
    inline_images=None,
):
    """Render and send an email with plain-text and HTML versions."""
    html_message = render_to_string(template_name, context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=unescape(strip_tags(html_message)),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    email.attach_alternative(html_message, 'text/html')

    if inline_images:
        email.mixed_subtype = 'related'

        for content_id, image_path in inline_images.items():
            with image_path.open('rb') as image_file:
                image = MIMEImage(image_file.read())

            image.add_header('Content-ID', f'<{content_id}>')
            image.add_header(
                'Content-Disposition',
                'inline',
                filename=image_path.name,
            )
            email.attach(image)

    return email.send()


def send_activation_email(user, uid, token):
    """Send an account activation email to the given user."""
    activation_link = (
        f'{settings.FRONTEND_URL}/pages/auth/activate.html'
        f'?uid={uid}&token={token}'
    )
    return send_html_email(
        subject='Activate your Videoflix account',
        template_name='emails/activation_email.html',
        context={
            'activation_link': activation_link,
            'email': user.email,
            'site_url': settings.FRONTEND_URL,
        },
        recipient=user.email,
        inline_images={ACTIVATION_LOGO_CID: ACTIVATION_LOGO_PATH},
    )
