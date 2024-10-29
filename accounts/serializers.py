from rest_framework import serializers
from .models import User, Lessee

class LesseeSerializer(serializers.ModelSerializer):
    email = serializers.EmailField() 
    class Meta:
        db_table = 'accounts_lessee'  # This sets the actual table name
        model = Lessee
        fields = ['name', 'guarantor_status', 'email']
class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "phone_number", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    # def create(self, validated_data):
    #     user = User.objects.create_user(
    #         email=validated_data["email"],
    #         phone_number=validated_data["phone_number"],
    #         password=validated_data["password"],
    #     )
    #     # Send verification code (pseudo code)
    #     # send_verification_code(user.email)
    #     return user
    def create(self, validated_data):
        # Create the user, but don't activate it yet.
        user = User.objects.create_user(**validated_data)
        return user