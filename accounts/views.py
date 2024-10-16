from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from .serializers import RegisterSerializer
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User registered successfully. Please verify your email."},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    def post(self, request):
        # Logic to verify user using a verification code
        return Response({"message": "Email verified successfully."})


# class LoginView(APIView):
#     def post(self, request):
#         email = request.data.get("email")
#         password = request.data.get("password")

#         # Check if email and password are provided
#         if not email or not password:
#             return Response(
#                 {"error": "Email and password are required."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         user = authenticate(request, email=email, password=password)

#         print(user)
#         if user:
#             # Generate tokens using Simple JWT
#             refresh = RefreshToken.for_user(user)
#             access_token = str(refresh.access_token)

#             return Response(
#                 {"refresh": str(refresh), "access": access_token},
#                 status=status.HTTP_200_OK,
#             )
#         return Response(
#             {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
#         )


User = get_user_model()


class LoginView(APIView):
    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        print(email, password)

        # Check if email and password are provided
        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Authenticate the user
        user = authenticate(request, email=email, password=password)

        if user is not None:
            # Generate tokens using Simple JWT
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            return Response(
                {"refresh": str(refresh), "access": access_token},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"error": "Invalid credentials, please try again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
