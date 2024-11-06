from rest_framework import serializers
from .models import User, Lessee, Lessor

class LessorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lessor
        fields = ['name', 'email', 'is_landlord', 'document_id']
        
    def validate_document_id(self, value):
        """
        Validate document ID format
        """
        if not value.strip():
            raise serializers.ValidationError("Document ID is required")
        # Add specific format validation based on ACRIS requirements
        return value.strip().upper()
    
class LesseeSerializer(serializers.ModelSerializer):
    email = serializers.EmailField() 
    class Meta:
        db_table = 'accounts_lessee'  # This sets the actual table name
        model = Lessee
        fields = ['name', 'guarantor_status', 'email']
class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "phone_number", "password", "is_verified"]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def create(self, validated_data):
        # Create the user and set `is_verified` to True if needed
        user = User.objects.create_user(
            email=validated_data["email"],
            phone_number=validated_data["phone_number"],
            password=validated_data["password"],
            is_verified=validated_data.get("is_verified", False)  # Default to False if not provided
        )
        return user