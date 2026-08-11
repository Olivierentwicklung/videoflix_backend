"""OpenAPI documentation for user registration."""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    inline_serializer,
)
from rest_framework import serializers

REGISTRATION_DESCRIPTION = """

**Description**: Registriert einen neuen Benutzer im System.

### Request Body

```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "confirmed_password": "securepassword"
}
```

### Success Response

Nach erfolgreicher Registrierung wird eine Aktivierungs-E-Mail versendet. 
Der Response inkl. dem Token hat keine Verwendung im FrontEnd, da wir hier 
mit HTTP-ONLY-COOKIES arbeiten. Dieser ist zur Demonstration und Information für Dich.

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com"
  },
  "token": "activation_token"
}
```

### Status Codes

-   **201**: Benutzer erfolgreich erstellt.
-   **400**: Ungültige Daten.
-   **500**: Interner Serverfehler.

### Rate Limits

- No limit.

### Permissions required: 

- No Permissions required

### Extra Information:

-   Konto bleibt inaktiv bis Aktivierung via E-Mail.

"""

REGISTRATION_USER_RESPONSE = inline_serializer(
    name='RegistrationUserResponse',
    fields={
        'id': serializers.IntegerField(),
        'email': serializers.EmailField(),
    },
)

REGISTRATION_SUCCESS_RESPONSE = inline_serializer(
    name='RegistrationSuccessResponse',
    fields={
        'user': REGISTRATION_USER_RESPONSE,
        'token': serializers.CharField(),
    },
)

REGISTRATION_VALIDATION_ERROR_RESPONSE = inline_serializer(
    name='RegistrationValidationErrorResponse',
    fields={
        'email': serializers.ListField(
            child=serializers.CharField(),
            required=False,
        ),
        'password': serializers.ListField(
            child=serializers.CharField(),
            required=False,
        ),
        'confirmed_password': serializers.ListField(
            child=serializers.CharField(),
            required=False,
        ),
        'non_field_errors': serializers.ListField(
            child=serializers.CharField(),
            required=False,
        ),
    },
)

REGISTRATION_RESPONSES = {
    201: OpenApiResponse(
        response=REGISTRATION_SUCCESS_RESPONSE,
        description='Benutzer erfolgreich registriert.',
        examples=[
            OpenApiExample(
                name='Registration successful',
                value={
                    'user': {
                        'id': 1,
                        'email': 'user@example.com',
                    },
                    'token': 'activation_token',
                },
                response_only=True,
            )
        ],
    ),
    400: OpenApiResponse(
        response=REGISTRATION_VALIDATION_ERROR_RESPONSE,
        description='Ungueltige oder bereits verwendete Registrierungsdaten.',
        examples=[
            OpenApiExample(
                name='Email already registered',
                value={
                    'email': [
                        'A user with this email address already exists.'
                    ]
                },
                response_only=True,
            )
        ],
    ),
    500: OpenApiResponse(
        description='Unerwarteter interner Serverfehler.',
    ),
}
