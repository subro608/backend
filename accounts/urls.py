from django.urls import path
from .views import RegisterView, VerifyEmailView, LoginView, LesseeSetupView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify/", VerifyEmailView.as_view(), name="verify-email"),
    path("login/", LoginView.as_view(), name="login"),
    path("lessee_setup/", LesseeSetupView.as_view(), name="lessee-setup"),
]
