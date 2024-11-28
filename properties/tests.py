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
import re
import os


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


@pytest.mark.django_db
class TestCreatePropertyListingView:

    @pytest.fixture
    def api_client(self):
        return APIClient()

    def test_create_property_listing(self, client):

        url = reverse("add-property")
        data = {
            "rent": 1000.0,
            "title": "Test Property",
            "street_address": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "zip_code": 62701,
            "property_type": "House",
            "bedrooms": 3.0,
            "bathrooms": 2.0,
            "available_since": "2022-01-01",
            "guarantor_required": False,
            "additional_notes": "Test notes",
            "air_conditioning": True,
            "parking": True,
            "dishwasher": True,
            "heating": True,
            "gym": True,
            "refrigerator": True,
            "laundry": True,
            "swimming_pool": True,
            "microwave": True,
        }
        response = client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"] is True
        assert response.data["error"] is False
        assert response.data["data"] == "Property and amenities added successfully."
