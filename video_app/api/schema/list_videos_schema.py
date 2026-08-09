"""OpenAPI documentation for the video catalogue endpoint."""

from django.conf import settings
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    inline_serializer,
)
from rest_framework import serializers

from video_app.api.serializers import VideoListSerializer

VIDEO_LIST_DESCRIPTION = """
**Description**: Gibt eine Liste aller verfügbaren Videos zurück.

### Request Body

Kein Request Body erforderlich.
```json
{

}
```

### Success Response

Enthält eine Liste mit Metadaten zu allen verfügbaren Videos.

```json
[
  {
    "id": 1,
    "created_at": "2023-01-01T12:00:00Z",
    "title": "Movie Title",
    "description": "Movie Description",
    "thumbnail_url": "http://example.com/media/thumbnail/image.jpg",
    "category": "Drama"
  },
  {
    "id": 2,
    "created_at": "2023-01-02T12:00:00Z",
    "title": "Another Movie",
    "description": "Another Description",
    "thumbnail_url": "http://example.com/media/thumbnail/image2.jpg",
    "category": "Romance"
  }
]
```

### Status Codes

- **200**: Liste erfolgreich zurückgegeben.
- **401**: Nicht authentifiziert.
- **500**: Interner Serverfehler.

### Rate Limits

- No limit.

### Permissions required

- JWT-Authentifizierung erforderlich.

### Extra Information

- No Extra Information.
"""

VIDEO_LIST_ERROR_RESPONSE = inline_serializer(
    name='VideoListErrorResponse',
    fields={'detail': serializers.CharField()},
)

VIDEO_LIST_RESPONSES = {
    200: OpenApiResponse(
        response=VideoListSerializer(many=True),
        description='Liste erfolgreich zurückgegeben.',
        examples=[
            OpenApiExample(
                name='Available videos',
                value=[
                    {
                        'id': 1,
                        'created_at': '2023-01-01T12:00:00Z',
                        'title': 'Movie Title',
                        'description': 'Movie Description',
                        'thumbnail_url': (
                            'http://example.com/media/thumbnails/image.jpg'
                        ),
                        'category': 'Drama',
                    },
                    {
                        'id': 2,
                        'created_at': '2023-01-02T12:00:00Z',
                        'title': 'Another Movie',
                        'description': 'Another Description',
                        'thumbnail_url': (
                            'http://example.com/media/thumbnails/image2.jpg'
                        ),
                        'category': 'Romance',
                    },
                ],
                response_only=True,
            )
        ],
    ),
    401: OpenApiResponse(
        response=VIDEO_LIST_ERROR_RESPONSE,
        description='Kein gültiger JWT wurde übermittelt.',
        examples=[
            OpenApiExample(
                name='Authentication required',
                value={'detail': 'Authentication credentials were not provided.'},
                response_only=True,
            )
        ],
    ),
    500: OpenApiResponse(description='Unerwarteter interner Serverfehler.'),
}


class CookieJWTAuthenticationScheme(SimpleJWTScheme):
    """Describe the supported Bearer-header and access-cookie JWT transports."""

    target_class = 'auth_app.api.authentication.CookieJWTAuthentication'
    name = ['jwtHeaderAuth', 'jwtCookieAuth']

    def get_security_requirement(self, auto_schema):
        """Document the header and cookie transports as alternatives."""
        del auto_schema
        return [{name: []} for name in self.name]

    def get_security_definition(self, auto_schema):  # type:ignore
        """Return OpenAPI security schemes for both JWT transports."""
        return [
            super().get_security_definition(auto_schema),
            {
                'type': 'apiKey',
                'in': 'cookie',
                'name': settings.JWT_ACCESS_COOKIE_NAME,
                'description': 'JWT access token in an HTTP-only cookie.',
            },
        ]
