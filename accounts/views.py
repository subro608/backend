from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from properties.views import SupabaseUploader
from .models import User, Lessee, Lessor, IDCardDocument, Role, BrokerLicenseType
from .serializers import RegisterSerializer, LesseeSerializer, LessorSerializer
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

    def get(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {
                    "success": False, 
                    "error": True, 
                    "message": "User not found"
                }, status=status.HTTP_404_NOT_FOUND
            )

        try:
            lessee_info = Lessee.objects.get(pk=pk)
            serializer = LesseeSerializer(lessee_info)
        except Lessee.DoesNotExist:
            return Response(
                {
                    "success": False, 
                    "error": True, 
                    "message": "Profile not setup yet"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return JsonResponse({
            "success": True, 
            "error": False,
            "data": serializer.data}, status=status.HTTP_200_OK)

    def put(self, request, pk=None):

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"success":False,
                 "error": True,
                 "message":"User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if lessor profile already exists for this user
        if Lessee.objects.filter(user=user).exists():
            return Response(
                {"success":False,
                 "error": True,
                 "message":"Lessee profile already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LesseeSerializer(data=request.data)

        if serializer.is_valid():
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
                    
                    user.name = request.data["name"]
                    user.save()
                    Lessee.objects.create(
                        user_id=user.id,
                        document_id=id_card.id,
                        is_verified=False,
                    )

                return Response(
                    {
                        "success": True,
                        "error": False,
                        "message": "Lessee profile created successfully.",
                    },
                    status=status.HTTP_201_CREATED,
                )
            except Exception as e:
                return Response(
                    {
                        "success":False,
                        "error": True,
                        "message": f"Failed to save information {str(e)}"
                    },status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LessorSetupView(APIView):
    def put(self, request, pk=None):
        # Extract data from request
        name = request.data.get("name")
        is_landlord = request.data.get("is_landlord", True)  # Default to landlord
        document_id = request.data.get("document_id")
        license_type_id = request.data.get("license_type_id")
        license_number = request.data.get("license_number")
        license_type = None

        # Check if a user with this email exists and has role 'LESSOR'
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"success":False,
                 "error": True,
                 "message":"User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if lessor profile already exists for this user
        if Lessor.objects.filter(user=user).exists():
            return Response(
                {"success":False,
                 "error": True,
                 "message":"Lessor profile already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not is_landlord:
            try:
                license_type = BrokerLicenseType.objects.get(id=license_type_id)
            except BrokerLicenseType.DoesNotExist:
                return Response(
                    {"success":False,
                    "error": True,
                    "message":"Invalid License Type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Create a new Lessor entry associated with this user
        try:
            with transaction.atomic():

                #update user name
                user.name = name
                user.save()

                #save lessor profile info
                lessor = Lessor.objects.create(
                    user=user,
                    is_landlord=is_landlord,
                    document_id=document_id,
                    license_type=license_type,
                    license_number=license_number,
                    is_verified=False,
                    verification_date=timezone.now(),
                )

                return Response(
                    {
                        "success": True,
                        "error": False,
                        "message": "Lessor profile created successfully.",
                    },
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": True,
                    "message": f"Failed to create lessor profile. {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {
                    "success": False, 
                    "error": True, 
                    "message": "User not found"
                }, status=status.HTTP_404_NOT_FOUND
            )

        try:
            lessor_info = Lessor.objects.get(pk=pk)
            serializer = LessorSerializer(lessor_info)
        except Lessor.DoesNotExist:
            return Response(
                {
                    "success": False, 
                    "error": True, 
                    "message": "Profile not setup yet"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return JsonResponse({
            "success": True, 
            "error": False,
            "data": serializer.data}, status=status.HTTP_200_OK)
    
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


User = get_user_model()


class RegisterView(APIView):
    def post(self, request):
        email = request.data.get("email")
        phone_number = request.data.get("phone_number")
        phone_code = request.data.get("phone_code")
        password = request.data.get("password")
        role = request.data.get("role")  # Expecting 'LESSEE' or 'LESSOR'

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
                "user": {
                    "userId": user.id, 
                    "email": user.email,
                    "name": user.name, 
                    "role": user.role, 
                    "isVerified":user.is_verified},
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
