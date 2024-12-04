from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
import uuid
from django.conf import settings


class UserManager(BaseUserManager):
    def create_user(
        self,
        email,
        phone_number,
        password=None,
        is_verified=False,
        role=None,
        **extra_fields,
    ):
        if not email:
            raise ValueError("The Email field must be set")
        # if role not in ["LESSEE", "LESSOR"]:
        #     raise ValueError("Role must be 'LESSEE' or 'LESSOR'")
        email = self.normalize_email(email)
        user = self.model(
            email=email, phone_number=phone_number, role=role, **extra_fields
        )
        user.set_password(password)
        user.verification_code = str(uuid.uuid4())[
            :6
        ]  # Generate a 6-digit verification code
        user.verification_expiration = timezone.now() + timezone.timedelta(
            hours=1
        )  # Code expires in 1 hour
        user.is_verified = is_verified  # Default to unverified
        user.save(using=self._db)
        return user


class Role(models.IntegerChoices):
    ADMIN = 1
    LESSEE = 2
    LESSOR = 3


class User(AbstractBaseUser):

    role = models.IntegerField(
        choices=Role.choices, null=True
    )  # 'ADMIN','LESSEE' or 'LESSOR'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=10)
    phone_code = models.CharField(max_length=3)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(
        default=False
    )  # Default to False, as email should be verified
    verification_code = models.CharField(
        max_length=6, blank=True, null=True
    )  # Verification code
    verification_expiration = models.DateTimeField(
        null=True, blank=True
    )  # Expiration time for the code
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number", "phone_code", "role"]

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("phone_number", "phone_code"),
                name="ux_phone",
                violation_error_message="User with given phone number already exists.",
            ),
        ]

    def __str__(self):
        return self.email

    def is_code_valid(self):
        """Check if the verification code is still valid."""
        return timezone.now() < self.verification_expiration


class IDCardDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_name = models.TextField()
    public_url = models.URLField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idcard_documents"


class Lessee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        to_field="id",  # Explicitly reference the UUID field
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)  # Independent email field, not a foreign key
    document = models.OneToOneField(
        IDCardDocument, on_delete=models.CASCADE, to_field="id", null=True
    )
    is_email_verified = models.BooleanField(default=False)
    is_document_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "accounts_lessee"

    def __str__(self):
        return f"{self.name} - {self.email}"


class Lessor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        to_field="id",  # Explicitly reference the UUID field
    )

    is_landlord = models.BooleanField(default=True)
    document_id = models.CharField(max_length=50, unique=True)
    is_verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "accounts_lessor"

    def __str__(self):
        return f"{self.name} - {'Landlord' if self.is_landlord else 'Broker'}"

    def save(self, *args, **kwargs):
        if not self.user_id and hasattr(self, "user"):
            self.user_id = self.user.id
        super().save(*args, **kwargs)
