import pytest
from django.urls import reverse
from django.core.cache import cache
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from pathlib import Path
from django.conf import settings
from django.db import connections
import time
from accounts.models import User, Lessee, Lessor, Role, IDCardDocument
from django.utils import timezone
from properties.models import Properties, PropertyAmenities, PropertyWishlist
import os
import uuid
import json


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_databases(request):
    """Cleanup test databases after all tests complete."""
    yield  # Let the tests run first

    # Close all database connections
    connections.close_all()

    # Wait a brief moment to ensure connections are fully closed
    time.sleep(1)

    # Get the backend directory path
    backend_dir = Path(settings.BASE_DIR)
    test_db_pattern = "test_db_*.sqlite3"

    # Find and remove all test database files
    max_attempts = 3
    for db_file in backend_dir.glob(test_db_pattern):
        for attempt in range(max_attempts):
            try:
                os.remove(db_file)
                print(f"\nRemoved test database: {db_file}")
                break
            except PermissionError:
                if attempt < max_attempts - 1:
                    print(f"\nAttempt {attempt + 1}: File still in use, waiting...")
                    time.sleep(2)  # Wait a bit longer between attempts
                    connections.close_all()  # Try closing connections again
                else:
                    print(
                        f"\nWarning: Could not remove {db_file} after {max_attempts} attempts"
                    )
            except Exception as e:
                print(f"\nUnexpected error while removing {db_file}: {e}")
                break


# Add this fixture to properly close connections after each test
@pytest.fixture(autouse=True)
def _close_db_connections():
    """Close database connections after each test."""
    yield
    connections.close_all()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def valid_user(db):
    user = User.objects.create_user(
        email="lessor@gmail.com",
        password="password123",
        phone_number="1234567890",
        phone_code="+1",
        role=Role.LESSOR,
        is_verified=True,
    )

    Lessor.objects.create(
        user=user, document_id="DOC123", is_landlord=True, is_verified=True
    )
    return user


@pytest.fixture
def id_card_document():
    document = IDCardDocument.objects.create(
        file_name="test_document.pdf",
        public_url="http://example.com/test_document.pdf",
        uploaded_at=timezone.now(),
    )
    return document


@pytest.fixture
def valid_lessee_user(db, id_card_document):
    user = User.objects.create_user(
        email="lessee@nyu.edu",
        password="password123",
        phone_number="1234567899",
        phone_code="+1",
        role=Role.LESSEE,
        is_verified=True,
    )

    Lessee.objects.create(
        user=user, document_id=str(id_card_document.id), is_verified=True
    )

    return user


@pytest.fixture
def auth_client(api_client, valid_user):
    response = api_client.post(
        reverse("login"), {"email": valid_user.email, "password": "password123"}
    )
    token = response.data["token"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def property_data():
    return {
        "title": "Test Property",
        "street_address": "123 Test St",
        "city": "Test City",
        "state": "TS",
        "zip_code": "12345",
        "property_type": "Apartment",
        "bedrooms": 2,
        "bathrooms": 1,
        "available_since": timezone.now().date(),
        "guarantor_required": False,
        "additional_notes": "Test notes",
        "rent": 1000,
        "description": "Test description",
        "amenities": {
            "air_conditioning": True,
            "parking": True,
            "dishwasher": True,
            "heating": True,
            "gym": True,
            "refrigerator": True,
            "laundry": True,
            "swimming_pool": True,
            "microwave": True,
        },
    }


@pytest.fixture
def property(valid_user):
    property = Properties.objects.create(
        id=uuid.uuid4(),
        title="Test Property",
        street_address="1566 W 11th St",
        city="Brooklyn",
        state="NY",
        zip_code="11204",
        property_type="Apartment",
        bedrooms=2,
        bathrooms=1,
        available_since=timezone.now().date(),
        guarantor_required=False,
        additional_notes="Test notes",
        rent=1000,
        description="Test description",
        lessor=valid_user.lessor,
        created_at=timezone.now(),
        modified_at=timezone.now(),
    )
    PropertyAmenities.objects.create(
        property_id=str(property.id),
        air_conditioning=True,
        parking=True,
        dishwasher=True,
        heating=True,
        gym=True,
        refrigerator=True,
        laundry=True,
        swimming_pool=True,
        microwave=True,
        created_at=timezone.now(),
        modified_at=timezone.now(),
    )
    return property


@pytest.mark.django_db
def test_create_property_listing(auth_client, property_data):
    url = reverse("add-property")
    response = auth_client.post(url, property_data, format="json")

    print(response.data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["success"] is True
    assert Properties.objects.count() == 1
    assert PropertyAmenities.objects.count() == 1
    assert Properties.objects.get().title == "Test Property"


@pytest.mark.django_db
def test_create_property_listing_invalid_user(auth_client, property_data):

    # make the valid_user is_verified False
    user = User.objects.get(email="lessor@gmail.com")
    lessor = Lessor.objects.get(user=user)
    lessor.is_verified = False
    lessor.save()

    url = reverse("add-property")
    response = auth_client.post(url, property_data, format="json")

    print(response)
    print(response.data)

    lessor.is_verified = True
    lessor.save()

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["success"] is False
    assert response.data["error"] is True
    assert (
        response.data["message"]
        == "Only verified lessors can create property listings."
    )


@pytest.mark.django_db
def test_create_property_listing_invalid_data(auth_client):
    url = reverse("add-property")
    invalid_data = {
        "title": "",
        "street_address": "123 Test St",
        "city": "Test City",
        "state": "TS",
        "zip_code": "12345",
        "property_type": "Apartment",
        "bedrooms": 2,
        "bathrooms": 1,
        "available_since": timezone.now().date(),
        "guarantor_required": False,
        "additional_notes": "Test notes",
        "rent": 1000,
        "description": "Test description",
        "amenities": {
            "air_conditioning": True,
            "parking": True,
            "dishwasher": True,
            "heating": True,
            "gym": True,
            "refrigerator": True,
            "laundry": True,
            "swimming_pool": True,
            "microwave": True,
        },
    }
    response = auth_client.post(url, invalid_data, format="json")

    print(response)
    print(response.data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_property_image_upload(auth_client, property):
    url = reverse("upload-image")
    data = {
        "property_id": str(property.id),
        "new_images": [],
        "deleted_images": json.dumps([]),
    }
    response = auth_client.post(url, data, format="multipart")
    assert response.status_code == status.HTTP_201_CREATED


def test_property_image_upload_invalid_property(auth_client):
    url = reverse("upload-image")
    data = {
        "property_id": str(uuid.uuid4()),
        "new_images": [],
        "deleted_images": json.dumps([]),
    }
    response = auth_client.post(url, data, format="multipart")

    print(response.data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_location_analysis(auth_client, property):
    url = reverse("analyze_location")
    data = {
        "property_id": str(property.id),
        "location": f"{property.street_address}, {property.city}, {property.state} {property.zip_code}",
        "radius": 500,
    }
    response = auth_client.post(url, data, format="json")

    print(response.data)
    assert response.status_code == status.HTTP_200_OK


def test_location_analysis_invalid_property(auth_client):
    url = reverse("analyze_location")
    data = {
        "property_id": str(uuid.uuid4()),
        "location": "Test Location",
        "radius": 1000,
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_property_wishlist(auth_client, property, valid_lessee_user):
    url = reverse("property-wishlist")
    data = {
        "lessee_id": valid_lessee_user.id,
        "property_id": str(property.id),
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert PropertyWishlist.objects.count() == 1


def test_property_wishlist_invalid_property(auth_client, valid_lessee_user):
    url = reverse("property-wishlist")
    data = {
        "lessee_id": valid_lessee_user.id,
        "property_id": str(uuid.uuid4()),
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_all_properties(auth_client):
    url = reverse("get-properties")
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_200_OK


def test_get_my_listings(auth_client):
    url = reverse("get-my-listings")
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_200_OK


def test_submit_property_for_verification(auth_client, property):
    url = reverse("submit_property_for_verification")
    data = {
        "property_id": str(property.id),
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK


def test_submit_property_for_verification_invalid_property(auth_client):
    url = reverse("submit_property_for_verification")
    data = {
        "property_id": str(uuid.uuid4()),
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_remove_wishlist(auth_client, property, valid_lessee_user):

    # first add property to wishlist
    url = reverse("property-wishlist")
    data = {
        "lessee_id": valid_lessee_user.id,
        "property_id": str(property.id),
    }
    response = auth_client.post(url, data, format="json")

    url = reverse("remove-from-wishlist")
    data = {
        "lessee_id": valid_lessee_user.id,
        "property_id": str(property.id),
    }
    response = auth_client.post(url, data, format="json")

    print(response.data)
    assert response.status_code == status.HTTP_200_OK


def test_remove_wishlist_invalid_property(auth_client, valid_lessee_user):
    url = reverse("remove-from-wishlist")
    data = {
        "lessee_id": valid_lessee_user.id,
        "property_id": str(uuid.uuid4()),
    }
    response = auth_client.post(url, data, format="json")

    print(response.data)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_property(auth_client, property):
    url = reverse("delete-property")
    data = {
        "property_id": str(property.id),
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK


def test_delete_property_invalid_property(auth_client):
    url = reverse("delete-property")
    data = {
        "property_id": str(uuid.uuid4()),
    }
    response = auth_client.post(url, data, format="json")

    print(response.data)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_modify_property(auth_client, property):
    url = reverse("modify-property")
    data = {
        "property_id": str(property.id),
        "title": "Updated Test Property",
        "street_address": "123 Test St",
        "city": "Test City",
        "state": "Test State",
        "zip_code": "12345",
        "property_type": "Apartment",
        "bedrooms": 2,
        "bathrooms": 1,
        "available_since": "2023-01-01",
        "guarantor_required": False,
        "amenities": {
            "air_conditioning": True,
            "parking": True,
            "dishwasher": True,
            "heating": True,
            "gym": True,
            "refrigerator": True,
            "laundry": True,
            "swimming_pool": True,
            "microwave": True,
        },
        "rent": 1200,
        "description": "Updated Test Description",
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK


def test_modify_property_invalid_property(auth_client):
    url = reverse("modify-property")
    data = {
        "property_id": str(uuid.uuid4()),
        "title": "Updated Test Property",
        "street_address": "123 Test St",
        "city": "Test City",
        "state": "Test State",
        "zip_code": "12345",
        "property_type": "Apartment",
        "bedrooms": 2,
        "bathrooms": 1,
        "available_since": "2023-01-01",
        "guarantor_required": False,
        "amenities": {
            "air_conditioning": True,
            "parking": True,
            "dishwasher": True,
            "heating": True,
            "gym": True,
            "refrigerator": True,
            "laundry": True,
            "swimming_pool": True,
            "microwave": True,
        },
        "rent": 1200,
        "description": "Updated Test Description",
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_property_details(auth_client, property):

    print(property.id)

    url = reverse("get-property-details", args=[str(property.id)])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_200_OK


def test_get_property_details_invalid_property(auth_client):
    url = reverse("get-property-details", args=[str(uuid.uuid4())])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_address_validation(auth_client):
    url = reverse("validate_address")
    data = {
        "street_address": "123 Test St",
        "city": "Test City",
        "state": "Test State",
        "zip_code": "12345",
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK


def test_address_validation_invalid_data(auth_client):
    url = reverse("validate_address")
    data = {
        "street_address": "",
        "city": "Test City",
        "state": "Test State",
        "zip_code": "12345",
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_property_search(auth_client):
    url = reverse("property-search")
    data = {
        "location": "Test Location",
        "radius": 5,
        "min_rent": 500,
        "max_rent": 1500,
        "bedrooms": 2,
        "bathrooms": 1,
        "property_type": "Apartment",
        "sort_by": "rent_asc",
        "page": 1,
        "per_page": 10,
    }
    response = auth_client.get(url, data)
    print(response.data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_property_search_invalid_data(auth_client):
    url = reverse("property-search")
    data = {
        "location": "",
        "radius": 5,
        "min_rent": 500,
        "max_rent": 1500,
        "bedrooms": 2,
        "bathrooms": 1,
        "property_type": "Apartment",
        "sort_by": "rent_asc",
        "page": 1,
        "per_page": 10,
    }
    response = auth_client.get(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
