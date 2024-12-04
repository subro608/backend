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
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("add/", CreatePropertyListingView.as_view(), name="add-property"),
    path("analyze_location/", LocationAnalysisView.as_view(), name="analyze_location"),
    path("upload-image/", PropertyImageUploadView.as_view(), name="upload-image"),
    path("", GetAllPropertiesView.as_view(), name="get-properties"),
    path('wishlist/', PropertyWishlistView.as_view(), name='property-wishlist'),
    path("delete", DeletePropertyView.as_view(), name="delete-property"),
    path('remove/', RemoveWishlistView.as_view(), name='remove-from-wishlist'),
    path("modify/", ModifyPropertyView.as_view(), name="modify-property"), 
    path(
        "<str:property_id>",
        GetPropertyDetailsView.as_view(),
        name="get-property-details",
    ),
]
