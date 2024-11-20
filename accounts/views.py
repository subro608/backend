from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User, Lessee, Lessor
from .serializers import RegisterSerializer, LesseeSerializer
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail  # To send email
from django.utils import timezone
from django.core.cache import cache  # To store verification codes temporarily
from django.utils.crypto import get_random_string
from django.contrib.auth.backends import ModelBackend
from rest_framework.authtoken.models import Token
from django.conf import settings
from rest_framework.permissions import IsAuthenticated, AllowAny


class LesseeSetupView(APIView):
    def post(self, request):
        # if request.user.role != 'LESSEE':
        #     return Response({"error": "User must be a LESSEE to set up a lessee profile."}, status=status.HTTP_403_FORBIDDEN)

        user_email = request.data.get("email")
        name = request.data.get("name")
        guarantor_status = request.data.get("guarantor_status")

        # Validate email has .edu extension
        if not user_email.endswith(".edu"):
            return Response(
                {"error": "Only .edu email addresses are allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if a user with this email exists
        user = User.objects.filter(email=user_email, role="LESSEE").first()
        if not user:
            return Response(
                {"error": "Either invalid email or incorrecct role"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if a lessee account already exists for this user
        if Lessee.objects.filter(user=user).exists():
            return Response(
                {"error": "Account already exists."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Create a new Lessee entry associated with this user
        lessee_data = {
            "name": name,
            "guarantor_status": guarantor_status,
            "email": user_email,  # Save email in Lessee
        }
        serializer = LesseeSerializer(data=lessee_data)

        if serializer.is_valid():
            lessee = serializer.save(user=user)  # Save lessee info connected to user

            # Send notification email
            email_subject = "Lessee Setup Successful"
            email_body = (
                f"Dear {name}, your lessee information has been successfully recorded."
            )
            send_mail(
                email_subject,
                email_body,
                "househunt.view@gmail.com",  # From email
                [user_email],  # To email
                fail_silently=False,
            )

            return Response(
                {"message": "Lessee information saved successfully."},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LessorSetupView(APIView):
    def post(self, request):
        # Extract data from request
        user_email = request.data.get("email")
        name = request.data.get("name")
        is_landlord = request.data.get("is_landlord", True)  # Default to landlord
        document_id = request.data.get("document_id")

        # Validate email has .edu extension if required (assuming similar to Lessee)
        if not user_email:
            return Response(
                {"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Check if a user with this email exists and has role 'LESSOR'
        user = User.objects.filter(email=user_email, role="LESSOR").first()
        if not user:
            return Response(
                {"error": "Invalid email or incorrect role"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if lessor profile already exists for this user
        if Lessor.objects.filter(user=user).exists():
            return Response(
                {"error": "Lessor profile already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify document ID with ACRIS
        verification_result = self.verify_with_acris(document_id, is_landlord)
        if not verification_result["success"]:
            return Response(
                {"error": verification_result["message"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prepare data for Lessor creation
        lessor_data = {
            "name": name,
            "email": user_email,
            "is_landlord": is_landlord,
            "document_id": document_id,
        }

        # Create a new Lessor entry associated with this user
        try:
            lessor = Lessor.objects.create(
                user=user,
                name=name,
                email=user_email,
                is_landlord=is_landlord,
                document_id=document_id,
                is_verified=True,
                verification_date=timezone.now(),
            )

            # Send confirmation email
            self.send_verification_email(lessor)

            return Response(
                {
                    "message": "Lessor profile created successfully.",
                    "is_verified": True,
                    "verification_date": lessor.verification_date,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": "Failed to create lessor profile.", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def verify_with_acris(self, document_id, is_landlord):
        """
        Mock ACRIS verification - Replace with actual ACRIS API integration
        """
        try:
            # Mock API call to ACRIS database
            response = {"success": True, "message": "Document verified successfully"}
            return response

        except Exception as e:
            return {"success": False, "message": f"Verification failed: {str(e)}"}

    def send_verification_email(self, lessor):
        """
        Send confirmation email to verified lessor
        """
        subject = "HouseHunt - Lessor Verification Successful"
        message = f"""
        Dear {lessor.name},

        Your {('landlord' if lessor.is_landlord else 'broker')} profile has been successfully verified.
        Document ID: {lessor.document_id}
        Verification Date: {lessor.verification_date}

        You can now start using HouseHunt's services.

        Best regards,
        The HouseHunt Team
        """
        send_mail(
            subject,
            message,
            "househunt.view@gmail.com",
            [lessor.email],
            fail_silently=False,
        )


# class LessorSetupView(APIView):

#     def post(self, request):
#         # Extract data from request
#         name = request.data.get('name')
#         is_landlord = request.data.get('is_landlord', True)  # Default to landlord
#         document_id = request.data.get('document_id')
#         email = request.user.email  # Use the authenticated user's email

#         # Validate required fields
#         if not all([name, document_id]):
#             return Response({
#                 "error": "All fields are required."
#             }, status=status.HTTP_400_BAD_REQUEST)

#         # Check if lessor profile already exists
#         if Lessor.objects.filter(user=request.user).exists():
#             return Response({
#                 "error": "Lessor profile already exists."
#             }, status=status.HTTP_400_BAD_REQUEST)

#         # Verify document ID with ACRIS
#         verification_result = self.verify_with_acris(document_id, is_landlord)
#         if not verification_result['success']:
#             return Response({
#                 "error": verification_result['message']
#             }, status=status.HTTP_400_BAD_REQUEST)

#         # Create lessor profile
#         try:
#             lessor = Lessor.objects.create(
#                 user=request.user,
#                 name=name,
#                 email=email,
#                 is_landlord=is_landlord,
#                 document_id=document_id,
#                 is_verified=True,
#                 verification_date=timezone.now()
#             )

#             # Send confirmation email
#             self.send_verification_email(lessor)

#             return Response({
#                 "message": "Lessor profile created successfully.",
#                 "is_verified": True,
#                 "verification_date": lessor.verification_date
#             }, status=status.HTTP_201_CREATED)

#         except Exception as e:
#             return Response({
#                 "error": "Failed to create lessor profile.",
#                 "details": str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def verify_with_acris(self, document_id, is_landlord):
#         """
#         Mock ACRIS verification - Replace with actual ACRIS API integration
#         """
#         try:
#             # Mock API call to ACRIS database
#             # In production, replace with actual ACRIS API endpoint
#             response = {
#                 'success': True,
#                 'message': 'Document verified successfully'
#             }

#             # Add actual verification logic here
#             return response

#         except Exception as e:
#             return {
#                 'success': False,
#                 'message': f"Verification failed: {str(e)}"
#             }

#     def send_verification_email(self, lessor):
#         """
#         Send confirmation email to verified lessor
#         """
#         subject = "HouseHunt - Lessor Verification Successful"
#         message = f"""
#         Dear {lessor.name},

#         Your {('landlord' if lessor.is_landlord else 'broker')} profile has been successfully verified.
#         Document ID: {lessor.document_id}
#         Verification Date: {lessor.verification_date}

#         You can now start using HouseHunt's services.

#         Best regards,
#         The HouseHunt Team
#         """

#         from django.core.mail import send_mail
#         send_mail(
#             subject,
#             message,
#             'househunt.view@gmail.com',
#             [lessor.email],
#             fail_silently=False,
#         )


User = get_user_model()


class RegisterView(APIView):
    def post(self, request):
        email = request.data.get("email")
        phone_number = request.data.get("phone_number")
        phone_code = request.data.get("phone_code")
        password = request.data.get("password")
        role = request.data.get("role")  # Expecting 'LESSEE' or 'LESSOR'

        # if role not in ["LESSEE", "LESSOR"]:
        #     return Response(
        #         {"error": "Role must be either 'LESSEE' or 'LESSOR'."},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        # Validate the data using the serializer
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():

            user = serializer.save()  # Save the user

            # Generate a verification token
            verification_code = get_random_string(6, allowed_chars="0123456789")

            # Store the email, password, and phone_number in cache using verification code as the key
            cache.set(
                f"verification_code_{verification_code}",
                user,
                timeout=600,
            )  # Cache for 10 minutes (600 seconds)

            # Send the verification email with the token
            email_subject = "Verify your email"
            email_body = f"Your verification code is: {verification_code}"
            send_mail(
                email_subject,
                email_body,
                "househunt.view@gmail.com",  # From email
                [email],  # To email
                fail_silently=False,
            )

            # Respond with success but don't save the user yet
            return Response(
                {
                    "message": "Verification code sent. Please check your email to verify."
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    def post(self, request):
        verification_code = request.data.get("verification_code")

        if not verification_code:
            return Response(
                {"error": "Verification code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve the stored user data (email, phone_number, password) from cache using the verification code
        cached_data = cache.get(f"verification_code_{verification_code}")

        if not cached_data:
            return Response(
                {"error": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.get(id=cached_data.id)
        # Create the user using the cached data
        user_data = {
            "is_verified": True,
        }

        serializer = RegisterSerializer(user, data=user_data, partial=True)
        if serializer.is_valid():
            serializer.save()  # update the user
            cache.delete(
                f"verification_code_{verification_code}"
            )  # Remove the cached data after successful registration
            return Response(
                {"message": "User registered successfully."},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        password = request.data.get("password")

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
                {"error": "Email Unverified"},
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
                "refreshToken": str(refresh),
                "token": access_token,
                "user": {"email": user.email, "role": user.role},
            },
            status=status.HTTP_200_OK,
        )


class TestView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user

        return Response(
            {"message": "You are authenticated!"}, status=status.HTTP_200_OK
        )
