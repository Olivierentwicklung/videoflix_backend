"""OpenAPI documentation for password confirmation."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    inline_serializer,
)
from rest_framework import serializers

PASSWORD_CONFIRM_DESCRIPTION = """
**Description**: Bestaetigt die Passwortaenderung mit dem in der E-Mail
enthaltenen Token.

### URL Parameters

| Name   | Type   | Description                      |
| ------ | ------ | -------------------------------- |
| uidb64 | - | Base64-codierte Benutzer-ID      |
| token  | - | Token zur Passwort-Zuruecksetzung |

### Request Body

```json
{
  "new_password": "newsecurepassword",
  "confirm_password": "newsecurepassword"
}
```

### Success Response

Bestätigung über erfolgreiche Passwortänderung.

```json
{
  "detail": "Your Password has been successfully reset."
}
```

### Status Codes

- **200**: Passwort erfolgreich geaendert.
- **400**: Link ungueltig oder abgelaufen beziehungsweise Passwortdaten
  ungueltig.

### Rate Limits

- No limit.

### Permissions required

- Keine Authentifizierung erforderlich.

### Extra Information

- Beide Passwortfelder sind nur im Request sichtbar.
- Das neue Passwort muss die konfigurierte Django-Passwortrichtlinie erfuellen.
- Erfolgreiches Zuruecksetzen widerruft alle ausstehenden Refresh-Tokens.
"""

PASSWORD_CONFIRM_PARAMETERS = [
    OpenApiParameter(
        name='uidb64',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.PATH,
        description='Base64-codierte Benutzer-ID.',
    ),
    OpenApiParameter(
        name='token',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.PATH,
        description='Einmalig verwendbarer Passwort-Reset-Token.',
    ),
]

PASSWORD_CONFIRM_SUCCESS_RESPONSE = inline_serializer(
    name='PasswordConfirmSuccessResponse',
    fields={'detail': serializers.CharField()},
)

PASSWORD_CONFIRM_ERROR_RESPONSE = inline_serializer(
    name='PasswordConfirmErrorResponse',
    fields={
        'detail': serializers.CharField(required=False),
        'new_password': serializers.ListField(
            child=serializers.CharField(),
            required=False,
        ),
        'confirm_password': serializers.ListField(
            child=serializers.CharField(),
            required=False,
        ),
    },
)

PASSWORD_CONFIRM_RESPONSES = {
    200: OpenApiResponse(
        response=PASSWORD_CONFIRM_SUCCESS_RESPONSE,
        description='Passwort erfolgreich geaendert.',
        examples=[
            OpenApiExample(
                name='Password reset successful',
                value={'detail': 'Your Password has been successfully reset.'},
                response_only=True,
            )
        ],
    ),
    400: OpenApiResponse(
        response=PASSWORD_CONFIRM_ERROR_RESPONSE,
        description='Reset-Link oder Passwortdaten sind ungueltig.',
        examples=[
            OpenApiExample(
                name='Invalid or expired reset link',
                value={'detail': 'Password reset link is invalid or expired.'},
                response_only=True,
            ),
            OpenApiExample(
                name='Passwords do not match',
                value={
                    'confirm_password': ['Passwords do not match.'],
                },
                response_only=True,
            ),
        ],
    ),
}
