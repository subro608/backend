# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Properties(models.Model):
    id = models.UUIDField(primary_key=True)
    lessor_id = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    street_address = models.TextField(blank=True, null=True)
    city = models.TextField(blank=True, null=True)
    state = models.TextField(blank=True, null=True)
    zip_code = models.SmallIntegerField(blank=True, null=True)
    property_type = models.TextField(blank=True, null=True)
    bedrooms = models.FloatField(blank=True, null=True)
    bathrooms = models.FloatField(blank=True, null=True)
    available_since = models.DateField(blank=True, null=True)
    guarantor_required = models.BooleanField(blank=True, null=True)
    additional_notes = models.TextField(blank=True, null=True)
    is_deleted = models.BooleanField(blank=True, null=True)
    rent = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField(blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)  # New field
    longitude = models.FloatField(blank=True, null=True)  # New field

    class Meta:
        managed = False
        db_table = "properties"

    def get_amenities(self):
        """Fetch related amenities for this property."""
        return PropertyAmenities.objects.filter(property_id=self.id)

    def get_images(self):
        """Fetch related images for this property."""
        return PropertyImage.objects.filter(property_id=self.id)

    def get_pois(self):
        """Fetch related POIs for this property."""
        return PropertyPois.objects.filter(property_id=self.id)


class PropertyAmenities(models.Model):

    property_id = models.TextField(primary_key=True)
    air_conditioning = models.BooleanField(blank=True, null=True)
    parking = models.BooleanField(blank=True, null=True)
    dishwasher = models.BooleanField(blank=True, null=True)
    heating = models.BooleanField(blank=True, null=True)
    gym = models.BooleanField(blank=True, null=True)
    refrigerator = models.BooleanField(blank=True, null=True)
    laundry = models.BooleanField(blank=True, null=True)
    swimming_pool = models.BooleanField(blank=True, null=True)
    microwave = models.BooleanField(blank=True, null=True)
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "property_amentities"


class PropertyPois(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-incremented ID
    property_id = models.TextField()  # Foreign key to `properties` table
    poi_name = models.TextField()  # Name and type of the point of interest
    poi_ratings = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )  # Ratings (nullable)
    poi_type = models.TextField()  # Type/category of the POI
    distance = models.TextField()  # Distance from the property
    latitude = models.FloatField()  # Latitude of the POI
    longitude = models.FloatField()  # Longitude of the POI
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for creation
    updated_at = models.DateTimeField(auto_now=True)  # Timestamp for updates

    class Meta:
        managed = False
        db_table = "property_pois"  # Reference the existing `property_pois` table


class PropertyImage(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-incremented ID
    property_id = models.TextField()  # Foreign key to `properties` table

    file_name = models.TextField()  # Original file name
    url = models.URLField()  # Public URL of the uploaded file
    uploaded_at = models.DateTimeField(auto_now_add=True)  # Timestamp for the upload

    class Meta:
        db_table = "property_images"  # Set table name
        managed = False  # Disable migrations if the table already exists

class PropertyWishlist(models.Model):
    id = models.AutoField(primary_key=True)
    lessee_id = models.UUIDField()  # Changed to UUIDField to match accounts_lessee
    property_id = models.UUIDField()
    is_wishlist = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'property_wishlist'
        unique_together = ('lessee_id', 'property_id')