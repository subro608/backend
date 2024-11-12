from django.shortcuts import render

# Create your views here.


from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.models import Lessor

# from .serializers import PropertySerializer
from django.utils import timezone


class CreatePropertyListingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Check if the user is a valid lessor
        if not Lessor.objects.filter(user=user).exists():
            return Response(
                {"error": "Only valid lessors can create property listings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        lessor = Lessor.objects.get(user=user)

        if not lessor.is_verified:
            return Response(
                {
                    "success": False,
                    "error": True,
                    "data": "Only verified lessors can create property listings.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Extract data from request
        property_data = request.data

        print(property_data)

        return Response(
            {"success": True, "error": False, "data": "OK"},
            status=status.HTTP_200_OK,
        )

        # # Validate and save the property listing
        # serializer = PropertySerializer(data=property_data)
        # if serializer.is_valid():
        #     serializer.save(lessor=user)
        #     return Response(
        #         {"message": "Property listing created successfully."},
        #         status=status.HTTP_201_CREATED,
        #     )
        # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
