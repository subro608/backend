from django.urls import path
from .views import (
    CreatePropertyListingView,
    LocationAnalysisView,
    PropertyImageUploadView,
    GetPropertiesView,
    DeletePropertyView,
    GetPropertyDetailsView,
    ModifyPropertyView,
    GetAllPropertiesView,
    SubmitPropertyForVerificationView
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("add/", CreatePropertyListingView.as_view(), name="add-property"),
    path("update/", ModifyPropertyView.as_view(), name="update-property"),
    path("analyze_location/", LocationAnalysisView.as_view(), name="analyze_location"),
    path("upload-image/", PropertyImageUploadView.as_view(), name="upload-image"),
    path("", GetPropertiesView.as_view(), name="get-properties"),
    path("delete", DeletePropertyView.as_view(), name="delete-property"),
    path("get-all-properties", GetAllPropertiesView.as_view(), name="get-all-properties"),
    path(
        "<str:property_id>",
        GetPropertyDetailsView.as_view(),
        name="get-property-details",
    ),
    path("submit-verification/", SubmitPropertyForVerificationView.as_view(), name="submit_property_for_verification")
]

