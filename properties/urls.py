from django.urls import path
from .views import (
    CreatePropertyListingView,
    LocationAnalysisView,
    PropertyImageUploadView,
    GetAllPropertiesView,
    PropertyWishlistView,
    DeletePropertyView,
    RemoveWishlistView,
    ModifyPropertyView,
    GetPropertyDetailsView,
    ModifyPropertyView,
    GetAllPropertiesView,
    SubmitPropertyForVerificationView,
    AddressValidationView,
    PropertySearchView

)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("add/", CreatePropertyListingView.as_view(), name="add-property"),
    path("update/", ModifyPropertyView.as_view(), name="update-property"),
    path("analyze_location/", LocationAnalysisView.as_view(), name="analyze_location"),
    path('images/upload/', PropertyImageUploadView.as_view(), name='upload-image'),
    path("", GetAllPropertiesView.as_view(), name="get-properties"),
    path('wishlist/', PropertyWishlistView.as_view(), name='property-wishlist'),
    path("delete/", DeletePropertyView.as_view(), name="delete-property"),
    path('remove/', RemoveWishlistView.as_view(), name='remove-from-wishlist'),
    path("modify/", ModifyPropertyView.as_view(), name="modify-property"), 
    path('validate_address/', AddressValidationView.as_view(), name='validate_address'),
    path("get-all-properties", GetAllPropertiesView.as_view(), name="get-all-properties"),
    path(
        "<uuid:property_id>/",
        GetPropertyDetailsView.as_view(),
        name="get-property-details",
    ),
    path("submit-verification/", SubmitPropertyForVerificationView.as_view(), name="submit_property_for_verification"),
    path('search/', PropertySearchView.as_view(), name='property-search'),
]

