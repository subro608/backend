from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
import uuid

class UserManager(BaseUserManager):
    def create_user(self, email, phone_number, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.verification_code = str(uuid.uuid4())[:6]  # Generate a 6-digit verification code
        user.verification_expiration = timezone.now() + timezone.timedelta(hours=1)  # Code expires in 1 hour
        user.save(using=self._db)

        print(password)

        return user


class User(AbstractBaseUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=True)  # Email verification status
    verification_code = models.CharField(max_length=6, blank=True, null=True)  # Verification code
    verification_expiration = models.DateTimeField(null=True, blank=True)  # Expiration time for the code
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]

    objects = UserManager()
