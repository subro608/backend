from rest_framework import serializers

from .models import Properties, PropertyAmenities, PropertyImage, PropertyPois


class LocationAnalysisSerializer(serializers.Serializer):
    location = serializers.CharField(required=True)
    radius = serializers.IntegerField(required=True, min_value=100, max_value=5000)
    property_id = serializers.CharField(max_length=255)

    def validate_radius(self, value):
        """
        Check that the radius is within reasonable bounds
        """
        if value > 1000:
            raise serializers.ValidationError("Radius cannot exceed 1000 meters")
        return value


class PropertyImageSerializer(serializers.Serializer):
    property_id = serializers.CharField(max_length=255)

class AmenitiesSerializer(serializers.Serializer):
    air_conditioning = serializers.BooleanField(default=False)
    parking = serializers.BooleanField(default=False)
    dishwasher = serializers.BooleanField(default=False)
    heating = serializers.BooleanField(default=False)
    gym = serializers.BooleanField(default=False)
    refrigerator = serializers.BooleanField(default=False)
    laundry = serializers.BooleanField(default=False)
    swimming_pool = serializers.BooleanField(default=False)
    microwave = serializers.BooleanField(default=False)


class CreatePropertyListingSerializer(serializers.Serializer):
    rent = serializers.FloatField()
    title = serializers.CharField(max_length=255)
    street_address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    zip_code = serializers.IntegerField()
    property_type = serializers.CharField(max_length=50)
    bedrooms = serializers.FloatField()
    bathrooms = serializers.FloatField()
    available_since = serializers.DateField()
    guarantor_required = serializers.BooleanField(default=False)
    additional_notes = serializers.CharField(allow_blank=True, required=False)
    amenities = AmenitiesSerializer()
    description = serializers.CharField()
    latitude = serializers.FloatField(read_only=True)  # Read-only as it's generated
    longitude = serializers.FloatField(read_only=True)  # Read-only as it's generated


class ModifyPropertyListingSerializer(serializers.Serializer):
    property_id = serializers.CharField(max_length=255)


class DeletePropertySerializer(serializers.Serializer):
    property_id = serializers.CharField(max_length=255)

class RemoveWishlistSerializer(serializers.Serializer):
    lessee_id = serializers.CharField(required=True)
    property_id = serializers.UUIDField(required=True)

    class Meta:
        fields = ['lessee_id', 'property_id']

class WishlistSerializer(serializers.Serializer):
    lessee_id = serializers.UUIDField(required=True)
    property_id = serializers.UUIDField(required=True)

class PropertyAmenitiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyAmenities
        fields = [
            "property_id",
            "air_conditioning",
            "parking",
            "dishwasher",
            "heating",
            "gym",
            "refrigerator",
            "laundry",
            "swimming_pool",
            "microwave"
        ]


# class PropertyPoisSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = PropertyPois
#         fields = ["poi_name", "distance"]


# class PropertyImageSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = PropertyImage
#         fields = ["image_url"]


# class PropertiesSerializer(serializers.ModelSerializer):

#     amenities = PropertyAmenitiesSerializer(many=True, read_only=True)
#     pois = PropertyPoisSerializer(many=True, read_only=True)
#     images = PropertyImageSerializer(many=True, read_only=True)

#     class Meta:
#         model = Properties
#         fields = [
#             "id",
#             "title",
#             "street_address",
#             "city",
#             "state",
#             "zip_code",
#             "property_type",
#             "bedrooms",
#             "bathrooms",
#             "created_at",
#             "modified_at",
#             "available_since",
#             "guarantor_required",
#             "amenities",
#             "pois",
#             "images",
#         ]
