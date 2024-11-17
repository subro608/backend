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
    street_adress = models.TextField(blank=True, null=True)
    city = models.TextField(blank=True, null=True)
    state = models.TextField(blank=True, null=True)
    zip_code = models.SmallIntegerField(blank=True, null=True)
    property_type = models.TextField(blank=True, null=True)
    bedrooms = models.FloatField(blank=True, null=True)
    bathrooms = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField(blank=True, null=True)
    available_since = models.DateField(blank=True, null=True)
    guarantor_required = models.BooleanField(blank=True, null=True)
    additional_notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "properties"


class PropertyAmentities(models.Model):
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
    poi_ratings = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)  # Ratings (nullable)
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
    property = models.ForeignKey(
        Properties,  # Reference the Properties model
        on_delete=models.CASCADE,  # Delete images when the property is deleted
        db_column="property_id",  # Map to the property_id column in the database
        related_name="images"  # Optional: Easier access to related images
    )
    file_name = models.TextField()  # Original file name
    url = models.URLField()  # Public URL of the uploaded file
    uploaded_at = models.DateTimeField(auto_now_add=True)  # Timestamp for the upload

    class Meta:
        db_table = "property_images"  # Set table name
        managed = False  # Disable migrations if the table already exists