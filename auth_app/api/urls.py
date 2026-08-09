from django.urls import path

from auth_app.api.views import (
    ActivationView,
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    LogoutView,
    PasswordResetView,
    RegistrationView,
)

urlpatterns = [
    path('register/', RegistrationView.as_view(), name='register'),
    path('login/', CookieTokenObtainPairView.as_view(), name='login'),
    path(
        'token/refresh/',
        CookieTokenRefreshView.as_view(),
        name='token_refresh',
    ),
    path('logout/', LogoutView.as_view(), name='logout'),
    path(
        'password_reset/',
        PasswordResetView.as_view(),
        name='password_reset',
    ),
    path(
        'activate/<uidb64>/<token>/',
        ActivationView.as_view(),
        name='activate',
    ),
]
