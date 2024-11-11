from django.urls import path
from .views import (
    RegisterView,
    VerifyEmailView,
    LoginView,
    LesseeSetupView,
    LessorSetupView,
    TestView,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify/", VerifyEmailView.as_view(), name="verify-email"),
    path("login/", LoginView.as_view(), name="login"),
    path("lessee_setup/", LesseeSetupView.as_view(), name="lessee-setup"),
    path("lessor_setup/", LessorSetupView.as_view(), name="lessor-setup"),
    path("test/", TestView.as_view(), name="test"),
    path(
        "token/", TokenObtainPairView.as_view(), name="token_obtain_pair"
    ),  # Endpoint to get access and refresh tokens
    path(
        "token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),  # Endpoint to refresh access token
]
