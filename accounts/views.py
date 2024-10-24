from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from .serializers import RegisterSerializer, LesseeSerializer
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail  # To send email
from django.utils import timezone
from django.core.cache import cache  # To store verification codes temporarily
from django.utils.crypto import get_random_string
from django.contrib.auth.backends import ModelBackend
from rest_framework.authtoken.models import Token

User = get_user_model()
class LesseeSetupView(APIView):
    def post(self, request):
        user_email = request.data.get('email')  # Get the login email
        name = request.data.get('name')
        guarantor_status = request.data.get('guarantor_status')

        # Validate email exists in the user database
        try:
            user = User.objects.filter(email=user_email).first()
        except User.DoesNotExist:
            return Response({"error": "Invalid email."}, status=status.HTTP_400_BAD_REQUEST)

        # Create a Lessee entry
        lessee_data = {
            'name': name,
            'user_email': user_email,
            'guarantor_status': guarantor_status,
        }
        serializer = LesseeSerializer(data=lessee_data)

        if serializer.is_valid():
            lessee = serializer.save(user=user)  # Save lessee info connected to user

            # Send notification email
            email_subject = "Lessee Setup Successful"
            email_body = f"Dear {name}, your lessee information has been successfully recorded."
            send_mail(
                email_subject,
                email_body,
                'househunt.view@gmail.com',  # From email
                [user_email],  # To email
                fail_silently=False,
            )

            return Response({"message": "Lessee information saved successfully."}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class RegisterView(APIView):
    def post(self, request):
        email = request.data.get("email")
        phone_number = request.data.get("phone_number")
        password = request.data.get("password")

        # Validate the data using the serializer
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            # Generate a verification token
            verification_code = get_random_string(6, allowed_chars='0123456789')

            # Store the email, password, and phone_number in cache using verification code as the key
            cache.set(f'verification_code_{verification_code}', {
                'email': email,
                'phone_number': phone_number,
                'password': password
            }, timeout=600)  # Cache for 10 minutes (600 seconds)

            # Send the verification email with the token
            email_subject = "Verify your email"
            email_body = f"Your verification code is: {verification_code}"
            send_mail(
                email_subject,
                email_body,
                'househunt.view@gmail.com',  # From email
                [email],  # To email
                fail_silently=False,
            )

            # Respond with success but don't save the user yet
            return Response(
                {"message": "Verification code sent. Please check your email to verify."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    def post(self, request):
        verification_code = request.data.get("verification_code")

        if not verification_code:
            return Response({"error": "Verification code is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve the stored user data (email, phone_number, password) from cache using the verification code
        cached_data = cache.get(f'verification_code_{verification_code}')

        if not cached_data:
            return Response({"error": "Invalid or expired verification code."}, status=status.HTTP_400_BAD_REQUEST)

        # Create the user using the cached data
        user_data = {
            'email': cached_data['email'],
            'phone_number': cached_data['phone_number'],
            'password': cached_data['password'],  # Raw password to be hashed in the serializer
        }

        serializer = RegisterSerializer(data=user_data)
        if serializer.is_valid():
            serializer.save()  # Save the user
            cache.delete(f'verification_code_{verification_code}')  # Remove the cached data after successful registration
            return Response({"message": "User registered successfully."}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')

        # Debugging - Print the login attempt
        print(f"Login attempt - Email: {email}, Password: {password}")

        # Check if email and password are provided
        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Normalize email to lowercase
        email = email.lower()

        # Try to retrieve the user based on the email
        print(User.objects)
        # exit(-1)
        try:
            user = User.objects.filter(email=email).first()
            print(f"User found: {user}")
        except User.DoesNotExist:
            print("User does not exist")
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Debugging - Check if the password is correct
        if not user.check_password(password):
            print("Password is incorrect")
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Debugging - Check if the user's email is verified
        if not user.is_verified:
            print("Email not verified")
            return Response(
                {"error": "Your email has not been verified. Please verify your email before logging in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Debugging - Check if the user is active
        if not user.is_active:
            print("User account inactive")
            return Response(
                {"error": "Account is inactive. Please contact support."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Generate tokens using Simple JWT
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return Response(
            {
                "refresh": str(refresh),
                "access": access_token,
            },
            status=status.HTTP_200_OK,
        )
