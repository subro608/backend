from django.urls import path
from .views import (
    CreatePropertyListingView,
    LocationAnalysisView,
    PropertyImageUploadView,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("add/", CreatePropertyListingView.as_view(), name="add-property"),
    path("analyze_location/", LocationAnalysisView.as_view(), name="analyze_location"),
    path("upload-image/", PropertyImageUploadView.as_view(), name="upload-image"),
]
