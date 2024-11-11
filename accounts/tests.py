import pytest
from django.urls import reverse
from django.core.cache import cache
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from .models import User


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
            "email": "existing@university.edu",
            "password": "newpassword123",
            "phone_number": "+19234512346",
        }
        response = client.post(reverse("register"), payload)

        # Check the response status code
        assert response.status_code == status.HTTP_200_OK

        # Verify the user was created in the database
        user = User.objects.get(email=payload["email"])
        assert user is not None
        assert user.is_verified is False  # Ensure the user is not verified immediately

        # Check the verification code is stored in the cache
        cached_data = cache.get(f"verification_code_{user.email}")
        assert cached_data is not None
        assert cached_data["email"] == payload["email"]

        # Confirm an email was sent
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Verify Your Email"
        assert user.email in mail.outbox[0].to

    def test_registration_with_existing_email(self, client):
        """
        Test that attempting to register with an email that already exists
        returns a 400 Bad Request error.
        """
        existing_user = User.objects.create_user(
            email="existing@university.edu",
            password="newpassword123",
            phone_number="+19234512345",
        )

        payload = {
            "email": "existing@university.edu",
            "password": "newpassword123",
            "phone_number": "+19234512345",
        }
        response = client.post(reverse("register"), payload)

        print(response)

        # Expecting 400 BAD REQUEST since the email is already taken
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["email"][0] == "user with this email already exists."

    def test_login(self, client):
        """
        Test that a user can login successfully and receive an access token.
        """

        existing_user = User.objects.create_user(
            email="existing@university.edu",
            password="newpassword123",
            phone_number="+19234512345",
        )

        payload = {
            "email": "existing@university.edu",
            "password": "newpassword123",
        }

        response = client.post(reverse("login"), payload)

        # Check the response status code
        assert response.status_code == status.HTTP_200_OK

        # Check the response data
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["access"] is not None
