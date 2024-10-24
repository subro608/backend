from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
import uuid
from django.conf import settings

class UserManager(BaseUserManager):
    def create_user(self, email, phone_number, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.verification_code = str(uuid.uuid4())[:6]  # Generate a 6-digit verification code
        user.verification_expiration = timezone.now() + timezone.timedelta(hours=1)  # Code expires in 1 hour
        user.is_verified = False  # Default to unverified
        user.save(using=self._db)
        return user



class User(AbstractBaseUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)  # Default to False, as email should be verified
    verification_code = models.CharField(max_length=6, blank=True, null=True)  # Verification code
    verification_expiration = models.DateTimeField(null=True, blank=True)  # Expiration time for the code


    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]

    objects = UserManager()

    def __str__(self):
        return self.email

    def is_code_valid(self):
        """Check if the verification code is still valid."""
        return timezone.now() < self.verification_expiration

class Lessee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',  # Use 'user_id' as defined in Supabase
        primary_key=True  # Explicitly set user_id as the primary key
    )
    name = models.CharField(max_length=255)
    guarantor_status = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False  # Supabase manages the table schema
        db_table = 'accounts_lessee'  # Ensure the table name matches Supabase

    def __str__(self):
        return f"{self.name} - {self.user.email}"
