"""OpenAPI documentation for the HLS video-segment endpoint."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, inline_serializer
from rest_framework import serializers

from video_app.api.constants import (
    HLS_SEGMENT_CONTENT_TYPE,
    SUPPORTED_VIDEO_RESOLUTIONS,
)

VIDEO_SEGMENT_DESCRIPTION = """
**Description**: Gibt ein einzelnes HLS-Videosegment fuer einen bestimmten Film
in der gewaehlten Aufloesung zurueck.

### URL Parameters

| Name | Type | Description |
| ---- | ---- | ----------- |
| movie_id | - | ID des Films. |
| resolution | - | Gewuenschte Aufloesung (z.B. `480p`, `720p`, `1080p`). |
| segment | - | Dateiname des Segments (z.B. '000.ts'). |

### Request Body

Kein Request Body.

```json
{

}
```

### Success Response

Binaere MPEG-TS-Datei (`Content-Type: video/MP2T`). Body enthält binäre Videodaten

```json
""
```

### Status Codes

- **200**: Segment erfolgreich geliefert.
- **401**: JWT-Authentifizierung fehlt oder ist ungueltig.
- **404**: Video, Aufloesung oder Segment nicht gefunden.

### Rate Limits

- No limit.

### Permissions required

- JWT-Authentifizierung erforderlich.

### Extra Information

- No Extra Information.

"""

VIDEO_SEGMENT_PARAMETERS = [
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
        description='Gewuenschte Aufloesung.',
        required=True,
        enum=SUPPORTED_VIDEO_RESOLUTIONS,
    ),
    OpenApiParameter(
        name='segment',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.PATH,
        description='Numerischer MPEG-TS-Segmentdateiname (z.B. `000.ts`).',
        required=True,
        pattern=r'^[0-9]+\.ts$',
    ),
]

VIDEO_SEGMENT_ERROR_RESPONSE = inline_serializer(
    name='VideoSegmentErrorResponse',
    fields={'detail': serializers.CharField()},
)

VIDEO_SEGMENT_RESPONSES = {
    (200, HLS_SEGMENT_CONTENT_TYPE): OpenApiResponse(
        response=OpenApiTypes.BINARY,
        description='Segment erfolgreich geliefert.',
    ),
    401: OpenApiResponse(
        response=VIDEO_SEGMENT_ERROR_RESPONSE,
        description='Kein gueltiger JWT wurde uebermittelt.',
    ),
    404: OpenApiResponse(
        response=VIDEO_SEGMENT_ERROR_RESPONSE,
        description='Video, Aufloesung oder Segment nicht gefunden.',
    ),
}
