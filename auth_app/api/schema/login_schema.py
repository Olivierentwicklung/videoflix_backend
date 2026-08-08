from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    inline_serializer,
)
from rest_framework import serializers

LOGIN_DESCRIPTION = """
**Description**: Authentifiziert den Benutzer und gibt JWT-Tokens zurück.

### Request Body

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

### Success Response

JWT-Tokens, Benutzerinformationen und Cookies werden gesetzt. Der Response hat
 keine Verwendung im FrontEnd, da wir hier mit HTTP-ONLY-COOKIES arbeiten. 
 Dieser ist zur Demonstration und Information für Dich.

```json
{
  "detail": "Login successful",
  "user": {
    "id": 1,
    "username": "user@example.com"
  }
}
```

### Status Codes

- **200**: Login erfolgreich.
- **400**: Request-Felder fehlen oder sind ungültig.
- **401**: E-Mail oder Passwort ist falsch oder das Konto ist inaktiv.

### Rate Limits

- No limit.

### Permissions required

- No permissions required.

### Extra Information:

-   No Extra Information

### Cookies

- `access_token`: Kurzlebiger JWT für authentifizierte API-Anfragen; `HttpOnly`.
- `refresh_token`: Langlebiger JWT zur Erneuerung des Zugangs; `HttpOnly`.
- `csrftoken`: Muss bei schreibenden Cookie-authentifizierten Requests zusätzlich
  im Header `X-CSRFToken` gesendet werden.

Der Browser-Client muss Requests mit Credentials senden, zum Beispiel mit
`credentials: "include"`.
"""

LOGIN_USER_RESPONSE = inline_serializer(
    name='LoginUserResponse',
    fields={
        'id': serializers.IntegerField(),
        'username': serializers.CharField(),
    },
)

LOGIN_SUCCESS_RESPONSE = inline_serializer(
    name='LoginSuccessResponse',
    fields={
        'detail': serializers.CharField(),
        'user': LOGIN_USER_RESPONSE,
    },
)

LOGIN_VALIDATION_ERROR_RESPONSE = inline_serializer(
    name='LoginValidationErrorResponse',
    fields={
        'email': serializers.ListField(
            child=serializers.CharField(),
            required=False,
        ),
        'password': serializers.ListField(
            child=serializers.CharField(),
            required=False,
        ),
    },
)

LOGIN_AUTHENTICATION_ERROR_RESPONSE = inline_serializer(
    name='LoginAuthenticationErrorResponse',
    fields={'detail': serializers.CharField()},
)

LOGIN_REQUEST_EXAMPLES = [
    OpenApiExample(
        name='Login credentials',
        value={
            'email': 'user@example.com',
            'password': 'securepassword',
        },
        request_only=True,
    )
]

LOGIN_RESPONSE_HEADERS = [
    OpenApiParameter(
        name='Set-Cookie',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.HEADER,
        response=[200],
        description=(
            'Setzt access_token und refresh_token als HttpOnly-Cookies sowie '
            'csrftoken für den X-CSRFToken-Header.'
        ),
    )
]

LOGIN_RESPONSES = {
    200: OpenApiResponse(
        response=LOGIN_SUCCESS_RESPONSE,
        description='Login erfolgreich; JWT- und CSRF-Cookies wurden gesetzt.',
        examples=[
            OpenApiExample(
                name='Login successful',
                value={
                    'detail': 'Login successful',
                    'user': {
                        'id': 1,
                        'username': 'user@example.com',
                    },
                },
                response_only=True,
            )
        ],
    ),
    400: OpenApiResponse(
        response=LOGIN_VALIDATION_ERROR_RESPONSE,
        description='Fehlende oder ungültige Request-Felder.',
        examples=[
            OpenApiExample(
                name='Invalid email',
                value={'email': ['Enter a valid email address.']},
                response_only=True,
            )
        ],
    ),
    401: OpenApiResponse(
        response=LOGIN_AUTHENTICATION_ERROR_RESPONSE,
        description='Ungültige Zugangsdaten oder inaktives Konto.',
        examples=[
            OpenApiExample(
                name='Invalid credentials',
                value={'detail': 'Invalid email or password.'},
                response_only=True,
            )
        ],
    ),
}
