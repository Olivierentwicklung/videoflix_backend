from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    inline_serializer,
)
from rest_framework import serializers

ACTIVATION_DESCRIPTION = """
**Description**: Aktiviert das Benutzerkonto mithilfe des per E-Mail gesendeten Tokens.

**URL Parameters**:

| Name   | Type | Description                 |
| ------ | ---- | --------------------------- |
| uidb64 | -    | Base64-codierte Benutzer-ID |
| token  | -    | Aktivierungstoken           |

### Request Body

```json
{

}
```

### Success Response

Aktivierungsstatusnachricht.

```json
{
  "message": "Account successfully activated."
}
```

### Status Codes

-   **200**: Account erfolgreich aktiviert.
-   **400**: Aktivierung fehlgeschlagen.
-   **500**: Interner Serverfehler.

### Rate Limits

- No limit.

### Permissions required: 

- No Permissions required

### Extra Information:

-   No Extra Information
"""

ACTIVATION_PARAMETERS = [
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
        description='Einmalig verwendbarer Aktivierungstoken.',
    ),
]

ACTIVATION_RESPONSE = inline_serializer(
    name='ActivationResponse',
    fields={'message': serializers.CharField()},
)

ACTIVATION_RESPONSES = {
    200: OpenApiResponse(
        response=ACTIVATION_RESPONSE,
        description='Account erfolgreich aktiviert.',
        examples=[
            OpenApiExample(
                name='Activation successful',
                value={'message': 'Account successfully activated.'},
                response_only=True,
            )
        ],
    ),
    400: OpenApiResponse(
        response=ACTIVATION_RESPONSE,
        description='Aktivierung fehlgeschlagen.',
        examples=[
            OpenApiExample(
                name='Activation failed',
                value={'message': 'Activation failed.'},
                response_only=True,
            )
        ],
    ),
}
