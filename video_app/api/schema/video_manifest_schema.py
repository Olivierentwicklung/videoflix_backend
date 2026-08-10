"""OpenAPI documentation for the HLS manifest endpoint."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, inline_serializer
from rest_framework import serializers

VIDEO_MANIFEST_DESCRIPTION = """
**Description**: Gibt die HLS-Master-Playlist für einen bestimmten Film
 und eine gewählte Auflösung zurück.

### URL Parameters

| Name   | Type   | Description                      |
| ------ | ------ | -------------------------------- |
| movie_id | - | Die ID des Filmes.     |
| resolution  | - | Gewünschte Auflösung (z.B. '480p', '720p', '1080p'). |

### Request Body

```json
{

}
```

### Success Response

HLS-Manifestdatei (Content-Type: application/vnd.apple.mpegurl). 
Body enthält HLS-Manifestdatei im M3U8-Format.

```json
""
```

### Status Codes

- **200**: Manifest erfolgreich geliefert.
- **400**: Video oder Manifest nicht gefunden.


### Rate Limits

- No limit.

### Permissions required

- JWT-Authentifizierung erforderlich

### Extra Information

- No Extra Information.
"""

VIDEO_MANIFEST_PARAMETERS = [
    OpenApiParameter(
        name='movie_id',
        type=OpenApiTypes.INT,
        location=OpenApiParameter.PATH,
        description='ID des Films.',
        required=True,
    ),
    OpenApiParameter(
        name='resolution',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.PATH,
        description='Gewünschte Auflösung.',
        required=True,
        enum=['480p', '720p', '1080p'],
    ),
]

VIDEO_MANIFEST_ERROR_RESPONSE = inline_serializer(
    name='VideoManifestErrorResponse',
    fields={'detail': serializers.CharField()},
)

VIDEO_MANIFEST_RESPONSES = {
    (200, 'application/vnd.apple.mpegurl'): OpenApiResponse(
        response=OpenApiTypes.BINARY,
        description='Manifest erfolgreich geliefert.',
    ),
    401: OpenApiResponse(
        response=VIDEO_MANIFEST_ERROR_RESPONSE,
        description='Kein gültiger JWT wurde übermittelt.',
    ),
    404: OpenApiResponse(
        response=VIDEO_MANIFEST_ERROR_RESPONSE,
        description='Video, Auflösung oder Manifest nicht gefunden.',
    ),
}
