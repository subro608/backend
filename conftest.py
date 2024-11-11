import pytest
from django.contrib.auth.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(username="globaluser", password="12345")


@pytest.fixture
def global_client(client, user):
    client.login(username="globaluser", password="12345")
    return client
