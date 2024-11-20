import pytest
from django.urls import reverse
from django.core.cache import cache
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from .models import User
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
class TestRegisterView:

    @pytest.fixture
    def client(self):
        return APIClient()

    def test_successful_registration(self, client):
        """
        Test that a new user can register successfully,
        receives a verification code, and an unverified status.
        """
        payload = {
            "email": "test@university.edu",
            "password": "newpassword@123",
            "phone_number": "9234512346",
            "phone_code": "+1",
            "role": 2,
        }
        response = client.post(reverse("register"), payload)

        # Check the response status code and message
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data
        assert "Verification code sent" in response.data["message"]

        # Check that an email was sent
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Verify your email"
        email_body = mail.outbox[0].body

        # Extract verification code from email
        verification_code = re.search(
            r"verification code is: (\d{6})", email_body
        ).group(1)
        assert verification_code is not None

        # Verify the data is stored in cache with verification code as key
        cached_user = cache.get(f"verification_code_{verification_code}")
        assert cached_user is not None
        assert cached_user.email == payload["email"]
        assert cached_user.phone_number == payload["phone_number"]
        assert cached_user.phone_code == payload["phone_code"]
        assert cached_user.role == payload["role"]
        assert not cached_user.is_verified

    def test_registration_with_existing_email(self, client):
        """
        Test that attempting to register with an email that already exists
        returns a 400 Bad Request error.
        """
        existing_user = User.objects.create_user(
            email="existing@university.edu",
            password="newpassword123",
            phone_number="9234512345",
            phone_code="+1",
            role=2,  # LESSEE role
        )

        payload = {
            "email": "existing@university.edu",
            "password": "newpassword123",
            "phone_number": "9234512345",
            "phone_code": "+1",
            "role": 2,
        }
        response = client.post(reverse("register"), payload)

        print(response)

        # Expecting 400 BAD REQUEST since the email is already taken
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data
        assert "already exists" in str(response.data["email"][0]).lower()

    def test_login(self, client):
        """
        Test that a user can login successfully and receive an access token.
        """

        user = User.objects.create_user(
            email="existing@university.edu",
            password="newpassword123",
            phone_number="9234512345",
            phone_code="+1",
            role=2,  # LESSEE role
        )
        # Set user as verified
        user.is_verified = True
        user.save()
        payload = {"email": "existing@university.edu", "password": "newpassword123"}

        response = client.post(reverse("login"), payload)

        # Check the response status code
        assert response.status_code == status.HTTP_200_OK
        # Check for token in response (instead of access)
        assert "token" in response.data
        assert "refreshToken" in response.data
        assert "user" in response.data
        assert response.data["user"]["email"] == user.email
        assert response.data["user"]["role"] == user.role

    def test_login_unverified_user(self, client):
        """
        Test that an unverified user cannot login.
        """
        # Create an unverified user
        user = User.objects.create_user(
            email="unverified@university.edu",
            password="newpassword123",
            phone_number="9234512345",
            phone_code="+1",
            role=2,  # LESSEE role
        )

        payload = {"email": "unverified@university.edu", "password": "newpassword123"}

        response = client.post(reverse("login"), payload)

        # Should be forbidden since user is not verified
        assert response.status_code == status.HTTP_403_FORBIDDEN
