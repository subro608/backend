from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from properties.views import SupabaseUploader
from .models import User, Lessee, Lessor, IDCardDocument, Role
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
from django.http import JsonResponse
from django.db import transaction
from django.forms.models import model_to_dict
import json

signer = TimestampSigner()


class LesseeSetupView(APIView):
    parser_classes = [MultiPartParser, FormParser]

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

    def get(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            lessee_info = Lessee.objects.get(pk=pk)
            serializer = LesseeSerializer(lessee_info)
        except Lessee.DoesNotExist:
            return Response(
                {"error": {"message": "Profile not setup yet", "status": 1907}},
                status=status.HTTP_200_OK,
            )

        return JsonResponse({"data": serializer.data}, status=status.HTTP_200_OK)

    def put(self, request, pk=None):

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = LesseeSerializer(data=request.data)

        if serializer.is_valid():
            if user.email == request.data["email"]:
                try:
                    with transaction.atomic():
                        document_file = request.FILES["document"]
                        file_name = document_file.name
                        uploader = SupabaseUploader()
                        public_url = uploader.upload_file(document_file,f"{user.id}/{document_file.name}","roomscout_documents")
                        id_card = IDCardDocument.objects.create(
                            file_name=file_name,
                            public_url=public_url,
                        )

                        Lessee.objects.create(
                            user_id=user.id,
                            name=request.data["name"],
                            email=request.data["email"],
                            document_id=id_card.id,
                            is_email_verified=True,
                        )

                    return Response(
                        {
                            "message": f"Created Lesse profile with existing email {id_card.id}"
                        }
                    )
                except Exception as e:
                    print(str(e))
                    return Response(
                        {"error": "Failed to save information"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:
                try:
                    with transaction.atomic():
                        document_file = request.FILES["document"]
                        file_name = document_file.name
                        uploader = SupabaseUploader()
                        public_url = uploader.upload_file(
                            document_file, f"{user.id}/{document_file.name}"
                        )
                        id_card = IDCardDocument.objects.create(
                            file_name=file_name,
                            public_url=public_url,
                        )

                        Lessee.objects.create(
                            user_id=user.id,
                            name=request.data["name"],
                            email=request.data["email"],
                            document_id=id_card.id,
                        )
                        email = request.data["email"]
                        token = signer.sign(email)
                        verification_url = f"{settings.FRONTEND_URL}/verify-email/?token={token}&role={Role.LESSEE}"
                        email_subject = "Please verify your email"
                        email_body = f"Please verify your email by clicking the link: {verification_url}"
                        print(f"Verification url : {verification_url}")
                        send_mail(
                            email_subject,
                            email_body,
                            f"{settings.EMAIL_HOST_USER}",  # From email
                            [email],  # To email
                            fail_silently=False,
                        )
                    return Response(
                        {"message": "Lessee information saved successfully."},
                        status=status.HTTP_201_CREATED,
                    )
                except Exception as e:
                    print(str(e))
                    return Response(
                        {"error": "Failed to save information"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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

            # Send the verification email with the token
            token = signer.sign(email)
            verification_url = f"{settings.FRONTEND_URL}/verify-email/?token={token}"
            email_subject = "Please verify your email"
            email_body = (
                f"Please verify your email by clicking the link: {verification_url}"
            )
            send_mail(
                email_subject,
                email_body,
                f"{settings.EMAIL_HOST_USER}",  # From email
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
        try:
            verification_token = request.data.get("token")
            verification_role = request.data.get("role")
            if not verification_token:
                return Response(
                    {"error": "Verification token is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                email = signer.unsign(verification_token, max_age=3600)
            except SignatureExpired:
                return Response(
                    {
                        "error": {
                            "message": "Verification token has expired. Generate New one!",
                            "status": 1905,
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except BadSignature:
                return Response(
                    {"error": {"message": "Invalid Token!", "status": 1906}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not verification_role:
                user = User.objects.get(email=email)
                user_data = {
                    "is_verified": True,
                }
                user_serializer = RegisterSerializer(user, data=user_data, partial=True)
                if user_serializer.is_valid():
                    user_serializer.save()
                    return Response(
                        {"message": "Email verified successfully!"},
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        user_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

            elif verification_role == Role.LESSEE:
                lessee = Lessee.objects.get(email=email)
                lessee_data = {"is_email_verified": True}
                lessee_serializer = LesseeSerializer(
                    lessee, data=lessee_data, partial=True
                )
                if lessee_serializer.is_valid():
                    lessee_serializer.save()
                    return Response(
                        {"message": "Email verified successfully!"},
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        lessee_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

            return Response(
                {"error": {"message": "Something went wrong!"}},
                status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": {"message": "Something went wrong!"}},
                status.HTTP_400_BAD_REQUEST,
            )

    def generate_new_link(request):
        request_object = json.loads(request.body)
        verification_token = request_object.get("token")
        verification_role = request_object.get("role")
        if not verification_token:
            return JsonResponse(
                {"error": {"message": "Verification token is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            email = signer.unsign(verification_token)
        except BadSignature:
            return JsonResponse(
                {"error": {"message": "Invalid Token!", "status": 1906}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not verification_role:
            token = signer.sign(email)
            verification_url = f"{settings.FRONTEND_URL}/verify-email/?token={token}"
            email_subject = "Please verify your email"
            email_body = (
                f"Please verify your email by clicking the link: {verification_url}"
            )
            send_mail(
                email_subject,
                email_body,
                f"{settings.EMAIL_HOST_USER}",  # From email
                [email],  # To email
                fail_silently=False,
            )

            # Respond with success but don't save the user yet
            return JsonResponse(
                {
                    "message": "Verification link sent. Please check your email to verify."
                },
                status=status.HTTP_200_OK,
            )
        elif verification_role == Role.LESSEE:
            token = signer.sign(email)
            verification_url = (
                f"{settings.FRONTEND_URL}/verify-email/{token}?role={Role.LESSEE}"
            )
            email_subject = "Please verify your email"
            email_body = (
                f"Please verify your email by clicking the link: {verification_url}"
            )
            send_mail(
                email_subject,
                email_body,
                f"{settings.EMAIL_HOST_USER}",  # From email
                [email],  # To email
                fail_silently=False,
            )
            return JsonResponse(
                {
                    "message": "Verification link sent. Please check your email to verify."
                },
                status=status.HTTP_200_OK,
            )
        return JsonResponse(
            {"error": {"message": "Retry Failed!"}},
            status=status.HTTP_400_BAD_REQUEST,
        )


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
        # print(User.objects)
        # exit(-1)
        try:
            user = User.objects.get(email=email)
            print(f"User found: {user}")
        except User.DoesNotExist:
            print("User does not exist")
            return Response(
                {"error": {"message": "Invalid email or password.", "status": 1901}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Debugging - Check if the password is correct
        if not user.check_password(password):
            print("Password is incorrect")
            return Response(
                {"error": {"message": "Invalid email or password.", "status": 1901}},
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
                "user": {"userId": user.id, "email": user.email, "role": user.role},
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
