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
