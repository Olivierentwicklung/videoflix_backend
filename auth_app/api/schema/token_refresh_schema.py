"""OpenAPI documentation for JWT refresh requests."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    inline_serializer,
)
from rest_framework import serializers

TOKEN_REFRESH_DESCRIPTION = """
**Description**: Stellt mit dem Refresh-Token-Cookie einen neuen Access-Token
aus und rotiert den Refresh-Token.

Gibt ein neues Zugangstoken aus, wenn der alte Access-Token abgelaufen ist. 
Der Token im Response hat keine Verwendung für das FrontEnd da wir hier mit 
HTTP-ONLY-COOKIES arbeiten. Dieser ist nur zur Demonstration und Information für Dich.

### Request Body
```json
{
  
}
```

Der Request besitzt keinen Body. Der Refresh-Token wird ausschliesslich aus
dem `refresh_token`-Cookie gelesen.

### Success Response
Neuer Access-Token.

Der Access-Token im Response dient nur zur Demonstration und Information. Das
Frontend verwendet den neu gesetzten HTTP-only Access-Token-Cookie.

```json
{
  "detail": "Token refreshed",
  "access": "new_access_token"
}
```

### Status Codes

- **200**: Access- und Refresh-Token wurden erneuert.
- **400**: Refresh-Token-Cookie fehlt oder ist leer.
- **401**: Refresh-Token ist ungueltig, abgelaufen, gesperrt, vom falschen Typ
  oder keinem aktiven Benutzer zugeordnet.
- **403**: CSRF-Cookie oder `X-CSRFToken`-Header fehlt oder ist ungueltig.

### Rate Limits

- No limit.

### Permissions required

- `refresh_token`-Cookie und gueltiger CSRF-Nachweis erforderlich.

### Extra Information

- Setzt einen neuen `access_token`-Cookie.
- Rotiert den `refresh_token`-Cookie und sperrt den zuvor verwendeten Token.
- Bei Status 400 oder 401 werden beide JWT-Cookies geloescht.
- Der Browser-Client muss Credentials mitsenden.
"""

TOKEN_REFRESH_SUCCESS_RESPONSE = inline_serializer(
    name='TokenRefreshSuccessResponse',
    fields={
        'detail': serializers.CharField(),
        'access': serializers.CharField(),
    },
)

TOKEN_REFRESH_ERROR_RESPONSE = inline_serializer(
    name='TokenRefreshErrorResponse',
    fields={'detail': serializers.CharField()},
)

TOKEN_REFRESH_PARAMETERS = [
    OpenApiParameter(
        name='refresh_token',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.COOKIE,
        required=True,
        description='HTTP-only Refresh-Token-Cookie.',
    ),
    OpenApiParameter(
        name='X-CSRFToken',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.HEADER,
        required=True,
        description='Wert des csrftoken-Cookies.',
    ),
    OpenApiParameter(
        name='Set-Cookie',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.HEADER,
        response=[200, 400, 401],
        description=('Setzt rotierte JWT-Cookies oder loescht ungueltige JWT-Cookies.'),
    ),
]

TOKEN_REFRESH_RESPONSES = {
    200: OpenApiResponse(
        response=TOKEN_REFRESH_SUCCESS_RESPONSE,
        description='JWTs erfolgreich erneuert und als Cookies gesetzt.',
        examples=[
            OpenApiExample(
                name='Token refreshed',
                value={
                    'detail': 'Token refreshed',
                    'access': 'new_access_token',
                },
                response_only=True,
            )
        ],
    ),
    400: OpenApiResponse(
        response=TOKEN_REFRESH_ERROR_RESPONSE,
        description='Refresh-Token-Cookie fehlt oder ist leer.',
        examples=[
            OpenApiExample(
                name='Refresh token missing',
                value={'detail': 'Refresh token is required.'},
                response_only=True,
            )
        ],
    ),
    401: OpenApiResponse(
        response=TOKEN_REFRESH_ERROR_RESPONSE,
        description='Refresh-Token ist nicht verwendbar.',
        examples=[
            OpenApiExample(
                name='Refresh token invalid',
                value={'detail': 'Refresh token is invalid or expired.'},
                response_only=True,
            )
        ],
    ),
    403: OpenApiResponse(
        response=TOKEN_REFRESH_ERROR_RESPONSE,
        description='CSRF-Pruefung fehlgeschlagen.',
        examples=[
            OpenApiExample(
                name='CSRF failed',
                value={'detail': 'CSRF Failed: CSRF cookie not set.'},
                response_only=True,
            )
        ],
    ),
}
