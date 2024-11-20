from rest_framework import serializers


class LocationAnalysisSerializer(serializers.Serializer):
    location = serializers.CharField(required=True)
    radius = serializers.IntegerField(required=True, min_value=100, max_value=5000)
    property_id = serializers.CharField(max_length=255)

    def validate_radius(self, value):
        """
        Check that the radius is within reasonable bounds
        """
        if value > 200:
            raise serializers.ValidationError("Radius cannot exceed 5000 meters")
        return value


class PropertyImageSerializer(serializers.Serializer):
    property_id = serializers.CharField(max_length=255)
    image = serializers.ImageField()  # Validate the image file


class CreatePropertyListingSerializer(serializers.Serializer):
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
    air_conditioning = serializers.BooleanField(default=False)
    parking = serializers.BooleanField(default=False)
    dishwasher = serializers.BooleanField(default=False)
    heating = serializers.BooleanField(default=False)
    gym = serializers.BooleanField(default=False)
    refrigerator = serializers.BooleanField(default=False)
    laundry = serializers.BooleanField(default=False)
    swimming_pool = serializers.BooleanField(default=False)
    microwave = serializers.BooleanField(default=False)
