from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    inline_serializer,
)
from rest_framework import serializers

LOGOUT_DESCRIPTION = """
**Description**: Meldet den Benutzer ab, sperrt den aktuellen Refresh-Token
und loescht die Access- und Refresh-Token-Cookies.

### Request Body
```json
{
  
}
```

### Success Response

No description available.

```json
{
  "detail": "Logout successful! All tokens will be deleted. 
  Refresh token is now invalid."
}
```

### Status Codes

- **200**: Logout erfolgreich.
- **400**: Refresh-Token fehlt, ist ungueltig, abgelaufen oder bereits gesperrt.
- **403**: CSRF-Cookie oder `X-CSRFToken`-Header fehlt oder ist ungueltig.

### Rate Limits

- No limit.

### Permissions required

- `refresh_token`-Cookie und gueltiger CSRF-Nachweis erforderlich.

### Extra Information

- Löscht die Cookies access_token und refresh_token. Der Refresh-Token wird auf 
eine Blackalist gesetzt.
- Die Cookies `access_token` und `refresh_token` werden geloescht.
- Der aktuelle Refresh-Token wird auf die Blacklist gesetzt.
- Ein zuvor kopierter Access-Token bleibt bis zu seinem Ablauf gueltig.
"""

LOGOUT_DETAIL_RESPONSE = inline_serializer(
    name='LogoutDetailResponse',
    fields={'detail': serializers.CharField()},
)

LOGOUT_PARAMETERS = [
    OpenApiParameter(
        name='refresh_token',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.COOKIE,
        required=True,
        description='HttpOnly Refresh-Token-Cookie.',
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
        response=[200, 400],
        description='Loescht access_token und refresh_token im Browser.',
    ),
]

LOGOUT_RESPONSES = {
    200: OpenApiResponse(
        response=LOGOUT_DETAIL_RESPONSE,
        description='Logout erfolgreich; Refresh-Token wurde gesperrt.',
        examples=[
            OpenApiExample(
                name='Logout successful',
                value={
                    'detail': (
                        'Logout successful! All tokens will be deleted. '
                        'Refresh token is now invalid.'
                    )
                },
                response_only=True,
            )
        ],
    ),
    400: OpenApiResponse(
        response=LOGOUT_DETAIL_RESPONSE,
        description='Refresh-Token fehlt oder ist nicht mehr gueltig.',
        examples=[
            OpenApiExample(
                name='Refresh token missing',
                value={'detail': 'Refresh token is required.'},
                response_only=True,
            ),
            OpenApiExample(
                name='Refresh token invalid',
                value={'detail': 'Refresh token is invalid or expired.'},
                response_only=True,
            ),
        ],
    ),
    403: OpenApiResponse(
        response=LOGOUT_DETAIL_RESPONSE,
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
