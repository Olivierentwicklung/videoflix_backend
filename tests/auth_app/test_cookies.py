from rest_framework.response import Response

from auth_app.api.cookies import delete_jwt_cookies


def test_delete_jwt_cookies_uses_configured_scope(settings):
    """Expire both JWT cookies with the paths and domain used at login."""
    settings.JWT_ACCESS_COOKIE_NAME = 'test_access'
    settings.JWT_REFRESH_COOKIE_NAME = 'test_refresh'
    settings.JWT_ACCESS_COOKIE_PATH = '/'
    settings.JWT_REFRESH_COOKIE_PATH = '/api/'
    settings.JWT_COOKIE_DOMAIN = 'example.com'
    settings.JWT_COOKIE_SAMESITE = 'Lax'

    response = delete_jwt_cookies(Response())

    access_cookie = response.cookies[settings.JWT_ACCESS_COOKIE_NAME]
    refresh_cookie = response.cookies[settings.JWT_REFRESH_COOKIE_NAME]

    assert access_cookie.value == ''
    assert access_cookie['max-age'] == 0
    assert access_cookie['path'] == settings.JWT_ACCESS_COOKIE_PATH
    assert access_cookie['domain'] == settings.JWT_COOKIE_DOMAIN
    assert access_cookie['samesite'] == settings.JWT_COOKIE_SAMESITE

    assert refresh_cookie.value == ''
    assert refresh_cookie['max-age'] == 0
    assert refresh_cookie['path'] == settings.JWT_REFRESH_COOKIE_PATH
    assert refresh_cookie['domain'] == settings.JWT_COOKIE_DOMAIN
    assert refresh_cookie['samesite'] == settings.JWT_COOKIE_SAMESITE
