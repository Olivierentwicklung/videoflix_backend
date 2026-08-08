from django.urls import path

from auth_app.api.views import (
    ActivationView,
    CookieTokenObtainPairView,
    RegistrationView,
)

urlpatterns = [
    path('register/', RegistrationView.as_view(), name='register'),
    path('login/', CookieTokenObtainPairView.as_view(), name='login'),
    path(
        'activate/<uidb64>/<token>/',
        ActivationView.as_view(),
        name='activate',
    ),
]
