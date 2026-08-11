"""OpenAPI documentation for password reset requests."""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    inline_serializer,
)
from rest_framework import serializers

PASSWORD_RESET_DESCRIPTION = """
**Description**: Sendet einen Link zum Zuruecksetzen des Passworts an die
E-Mail-Adresse des Benutzers.

### Request Body

```json
{
  "email": "user@example.com"
}
```

### Success Response

Bestätigt, dass eine E-Mail zum Zurücksetzen gesendet wurde.

```json
{
  "detail": "An email has been sent to reset your password."
}
```

### Status Codes

- **200**: Anfrage wurde verarbeitet. Reset-E-Mail wurde versendet.
- **400**: E-Mail-Adresse fehlt oder ist syntaktisch ungueltig.

### Rate Limits

- No limit.

### Permissions required

- Keine Authentifizierung erforderlich.

### Extra Information

- Eine E-Mail wird nur fuer ein aktives Konto mit nutzbarem Passwort versendet.
- Die Antwort verraet nicht, ob ein Konto mit der E-Mail-Adresse existiert.
- Nur möglich, wenn ein Benutzer mit dieser E-Mail existiert.
"""

PASSWORD_RESET_SUCCESS_RESPONSE = inline_serializer(
    name='PasswordResetSuccessResponse',
    fields={'detail': serializers.CharField()},
)

PASSWORD_RESET_VALIDATION_ERROR_RESPONSE = inline_serializer(
    name='PasswordResetValidationErrorResponse',
    fields={
        'email': serializers.ListField(
            child=serializers.CharField(),
        ),
    },
)

PASSWORD_RESET_RESPONSES = {
    200: OpenApiResponse(
        response=PASSWORD_RESET_SUCCESS_RESPONSE,
        description='Passwort-Reset-Anfrage wurde verarbeitet.',
        examples=[
            OpenApiExample(
                name='Password reset email requested',
                value={'detail': ('An email has been sent to reset your password.')},
                response_only=True,
            )
        ],
    ),
    400: OpenApiResponse(
        response=PASSWORD_RESET_VALIDATION_ERROR_RESPONSE,
        description='Fehlende oder ungueltige E-Mail-Adresse.',
        examples=[
            OpenApiExample(
                name='Invalid email address',
                value={'email': ['Enter a valid email address.']},
                response_only=True,
            )
        ],
    ),
}
