![Demo](static/images/logo.svg)

# 🎬Videoflix API

![Django](https://img.shields.io/badge/Django-5.2-green)
![DRF](https://img.shields.io/badge/DRF-3.17-blue)
![Auth](https://img.shields.io/badge/Auth-JWT_Cookies-orange)
![Streaming](https://img.shields.io/badge/Streaming-HLS-red)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Status](https://img.shields.io/badge/Project-Active-brightgreen)

A video-streaming backend built with Django REST Framework.

Videoflix provides account registration and activation, secure cookie-based JWT authentication, a protected video catalogue, and adaptive HLS streaming. Videos uploaded through Django Admin are processed asynchronously with Redis Queue and FFmpeg into 480p, 720p, and 1080p variants.

---

## 🚀 Features

- 🔐 Email-based registration and cookie-based JWT authentication
- 🍪 HTTP-only access and refresh-token cookies
- 🔄 Refresh-token rotation and blacklisting
- ✉️ Account activation and password-reset emails
- 🛡️ CSRF protection for cookie-authenticated requests
- 🎬 Authenticated video catalogue
- 📤 Video management through Django Admin
- ⚙️ Asynchronous media processing with Redis Queue
- 🖼️ Automatic thumbnail generation with FFmpeg
- 📺 Adaptive HLS output in 480p, 720p, and 1080p
- 🎧 Automatic silent audio track for source videos without audio
- 🗃️ PostgreSQL persistence and Redis-backed queues/cache
- 📖 Interactive OpenAPI documentation with DRF-spectacular
- 🧪 Automated tests with Pytest and Coverage
- 🐳 Reproducible local environment with Docker Compose

---

## 📦 Setup

### Requirements

Recommended setup:

- Git
- Docker Desktop with Docker Compose

For a native installation:

- Python 3.12+
- PostgreSQL
- Redis
- FFmpeg and FFprobe available on `PATH`
- An SMTP account for activation and password-reset emails

Verify the native media tools with:

```bash
ffmpeg -version
ffprobe -version
```

---

### Docker Installation

```bash
git clone https://github.com/Olivierentwicklung/videoflix_backend.git
cd videoflix_backend

# Linux / macOS
cp .env.template .env

# Windows PowerShell
Copy-Item .env.template .env
```

Open `.env` and replace the placeholders. At minimum, use strong values for the Django secret, JWT signing key, database credentials, and superuser password, then configure a working SMTP server:

```env
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=replace-with-a-strong-password
DJANGO_SUPERUSER_EMAIL=admin@example.com

SECRET_KEY=replace-with-a-long-random-django-secret
DJANGO_DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
CORS_ALLOWED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
CORS_ALLOW_CREDENTIALS=True
FRONTEND_URL=http://127.0.0.1:5500
BACKEND_URL=http://127.0.0.1:8000

JWT_SIGNING_KEY=replace-with-a-different-long-random-secret
JWT_ACCESS_TOKEN_MINUTES=5
JWT_REFRESH_TOKEN_DAYS=7
JWT_COOKIE_SECURE=False
JWT_COOKIE_SAMESITE=Lax
JWT_REFRESH_COOKIE_PATH=/api/token/refresh/
CSRF_COOKIE_SECURE=False
CSRF_COOKIE_SAMESITE=Lax

DB_NAME=videoflix_db
DB_USER=videoflix_user
DB_PASSWORD=replace-with-a-strong-database-password
DB_HOST=db
DB_PORT=5432

REDIS_HOST=redis
REDIS_LOCATION=redis://redis:6379/1
REDIS_PORT=6379
REDIS_DB=0

FFMPEG_BINARY=ffmpeg
FFPROBE_BINARY=ffprobe

EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email-user
EMAIL_HOST_PASSWORD=your-email-password
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=noreply@example.com
```

Build and start the complete stack:

```bash
docker compose up --build
```

The web container waits for PostgreSQL, collects static files, applies migrations, creates the configured superuser when necessary, starts an RQ worker, and launches Gunicorn at `http://127.0.0.1:8000`.

Run the tests in a separate terminal:

```bash
docker compose exec web pytest
```

Stop the containers without deleting their named volumes:

```bash
docker compose down
```

---

### Native Installation

Create and activate a virtual environment:

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Copy `.env.template` to `.env`. For services running directly on the host, change `DB_HOST`, `REDIS_HOST`, and `REDIS_LOCATION` from their Docker service names to `localhost` equivalents. Then run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py rqworker default
```

In another terminal with the virtual environment active:

```bash
python manage.py runserver
```

The test suite uses an in-memory SQLite database and a local email backend, so it can be run independently with:

```bash
pytest
```

---

## 🧪 Example Usage

### Open Django Administration

```text
http://127.0.0.1:8000/admin/
```

Create categories and upload source videos in Django Admin. Saving a new or replaced source video automatically queues its thumbnail and HLS processing job.

### Open Videoflix API Documentation

Swagger UI:

```text
http://127.0.0.1:8000/api/schema/swagger-ui/
```

ReDoc:

```text
http://127.0.0.1:8000/api/schema/redoc/
```

OpenAPI schema:

```text
http://127.0.0.1:8000/api/schema/
```

---

## 🔐 Authentication Endpoints

| Method | Endpoint                                  | Description                                    |
| ------ | ----------------------------------------- | ---------------------------------------------- |
| POST   | `/api/register/`                          | Register an inactive user and queue activation |
| GET    | `/api/activate/{uidb64}/{token}/`         | Activate an account from its emailed link      |
| POST   | `/api/login/`                             | Log in by email and set JWT and CSRF cookies   |
| POST   | `/api/token/refresh/`                     | Rotate tokens using the refresh-token cookie   |
| POST   | `/api/logout/`                            | Blacklist the refresh token and clear cookies  |
| POST   | `/api/password_reset/`                    | Request a password-reset email                 |
| POST   | `/api/password_confirm/{uidb64}/{token}/` | Set a new password from the emailed reset link |

### Cookie Authentication

A successful login sets three relevant cookies:

- `access_token` authenticates protected API requests.
- `refresh_token` obtains a new token pair after access expiry.
- `csrftoken` must be mirrored in the `X-CSRFToken` header for unsafe cookie-authenticated requests.

Browser requests must include credentials:

```javascript
fetch("http://127.0.0.1:8000/api/video/", {
  credentials: "include",
});
```

For `POST`, `PATCH`, `PUT`, and `DELETE` requests that rely on JWT cookies, send the CSRF token as well:

```javascript
fetch("http://127.0.0.1:8000/api/token/refresh/", {
  method: "POST",
  credentials: "include",
  headers: {
    "X-CSRFToken": readCookie("csrftoken"),
  },
});
```

The custom authentication class also accepts a standard Bearer access token:

```http
Authorization: Bearer <your_access_token>
```

---

## 🎬 Video Endpoints

| Method | Endpoint                                          | Description                       |
| ------ | ------------------------------------------------- | --------------------------------- |
| GET    | `/api/video/`                                     | List all videos in the catalogue  |
| GET    | `/api/video/{movie_id}/{resolution}/index.m3u8`   | Retrieve one HLS variant playlist |
| GET    | `/api/video/{movie_id}/{resolution}/{segment}.ts` | Stream one MPEG-TS video segment  |

All video endpoints require authentication. Supported resolution values are `480p`, `720p`, and `1080p`. Catalogue and streaming endpoints are read-only; video records and uploads are managed through Django Admin.

---

## 🧾 Example Requests

### Register User

```json
{
  "email": "user@example.com",
  "password": "SecurePassword!123",
  "confirmed_password": "SecurePassword!123"
}
```

New users remain inactive until they open the activation link sent by email.

### Login

```json
{
  "email": "user@example.com",
  "password": "SecurePassword!123"
}
```

Example response body:

```json
{
  "detail": "Login successful",
  "user": {
    "id": 1,
    "username": "user@example.com"
  }
}
```

The access and refresh tokens are delivered as HTTP-only cookies rather than in the login response body.

### Request Password Reset

```json
{
  "email": "user@example.com"
}
```

### Confirm New Password

```json
{
  "new_password": "EvenMoreSecurePassword!456",
  "confirm_password": "EvenMoreSecurePassword!456"
}
```

### Video Catalogue Response

```json
[
  {
    "id": 1,
    "created_at": "2026-08-11T10:30:00.000Z",
    "title": "Movie Title",
    "description": "Movie Description",
    "thumbnail_url": "http://127.0.0.1:8000/media/videos/8dbfe43e-aaaa-bbbb-cccc-11c9f2f6fbbc/thumbnail.jpg",
    "category": "Drama"
  }
]
```

Use the master playlist URL as the source for an HLS-capable player:

```text
http://127.0.0.1:8000/api/video/1/master.m3u8
```

---

## 🔄 Video Processing Workflow

```text
Admin uploads or replaces a source video
    │
    ▼
Django saves the video with status "pending"
    │
    ▼
Redis Queue submits an asynchronous processing job
    │
    ▼
FFprobe detects whether the source contains audio
    │
    ▼
FFmpeg extracts a thumbnail and transcodes aligned HLS variants
    │
    ▼
480p, 720p, and 1080p playlists and segments are validated
    │
    ▼
The video status becomes "ready" or stores a bounded failure diagnostic
```

Generated media is organized beneath `media/videos/{storage_id}/`. HLS segments use six-second aligned keyframe intervals, allowing compatible clients to switch quality during playback.

---

## 🗂️ Project Structure

```text
videoflix_backend/
├── manage.py
├── core/
│   ├── settings.py
│   ├── test_settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── auth_app/
│   ├── api/
│   │   ├── authentication.py
│   │   ├── cookies.py
│   │   ├── schema/
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   ├── utils.py
│   │   └── views.py
│   ├── templates/emails/
│   └── migrations/
│
├── video_app/
│   ├── api/
│   │   ├── schema/
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── models.py
│   ├── signals.py
│   ├── tasks.py
│   └── migrations/
│
├── tests/
│   ├── auth_app/
│   └── video_app/
│
├── .env.template
├── backend.Dockerfile
├── backend.entrypoint.sh
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── pytest.ini
└── README.md
```

---

## 🧠 ERD Overview

### Core Entities

- Django User
- Category
- Video

### Relationships

```text
Category 1 ───── many Video

Django User authenticates catalogue and streaming requests
```

- Every video belongs to exactly one category.
- One category can contain many videos.
- Category deletion is protected while videos still reference it.
- Video ownership is not user-specific; authenticated users share the catalogue.
- Each video owns one original upload and its generated thumbnail and HLS files.

---

## 🔒 Security

- HTTP-only JWT access and refresh cookies
- Short-lived access tokens and refresh-token rotation
- Refresh-token blacklisting after rotation and logout
- Cookie-aware JWT authentication with Bearer-header support
- CSRF enforcement for cookie-authenticated unsafe requests
- Configurable secure and SameSite cookie policies
- Credentialed CORS restricted to configured frontend origins
- Generic login and password-reset responses that limit account disclosure
- Inactive accounts until one-time email activation succeeds
- Django password hashing and password validation
- Protected catalogue, manifests, and media segments
- Strict resolution and segment-filename validation
- Path construction based on server-side video records
- Secrets and service credentials provided through environment variables

For production, set `DJANGO_DEBUG=False`, use HTTPS, enable secure cookies, configure exact allowed hosts/origins, and replace every development credential in `.env`.

---

## 🧑‍💻 Tech Stack

- Python 3.12
- Django 5.2
- Django REST Framework 3.17
- Simple JWT
- PostgreSQL
- Redis and Django RQ
- FFmpeg and FFprobe
- HLS adaptive streaming
- DRF-spectacular
- django-cors-headers
- WhiteNoise
- Gunicorn
- Docker Compose
- Pytest, Coverage, Ruff, and Pylint

---

## ✨ Purpose

Videoflix was developed to practice and demonstrate:

- Django REST Framework architecture
- Secure cookie-based JWT authentication
- Email activation and password-reset workflows
- Asynchronous background jobs with Redis Queue
- Adaptive video transcoding and HLS delivery
- Protected binary media endpoints
- Relational database design with PostgreSQL
- Dockerized application infrastructure
- OpenAPI documentation
- Automated API, model, media-processing, and security tests
- Clean and maintainable project organization
