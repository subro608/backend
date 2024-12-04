from rest_framework import serializers
from .models import User, Lessee, Lessor, IDCardDocument


class LessorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lessor
        fields = ["name", "email", "is_landlord", "document_id"]

    def validate_document_id(self, value):
        """
        Validate document ID format
        """
        if not value.strip():
            raise serializers.ValidationError("Document ID is required")
        # Add specific format validation based on ACRIS requirements
        return value.strip().upper()

class IDCardDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = IDCardDocument
        fields = ['file_name','public_url','uploaded_at']


class LesseeSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    document = IDCardDocumentSerializer(read_only = True)

    class Meta:
        db_table = "accounts_lessee"  # This sets the actual table name
        model = Lessee
        fields = ["name", "email","document","is_email_verified","is_document_verified"]

class RegisterSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "email",
            "phone_number",
            "phone_code",
            "password",
            "is_verified",
            "role",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=User.objects.all(),
                fields=["phone_number", "phone_code"],
                message="User with given phone number already exists!",
            )
        ]

    def create(self, validated_data):
        # Create the user and set `is_verified` to True if needed
        user = User.objects.create_user(
            email=validated_data["email"],
            phone_number=validated_data["phone_number"],
            phone_code=validated_data["phone_code"],
            password=validated_data["password"],
            is_verified=validated_data.get(
                "is_verified", False
            ),  # Default to False if not provided
            role=validated_data["role"],
        )
        return user
