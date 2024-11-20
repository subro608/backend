from django.shortcuts import render

# Create your views here.

import traceback
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.models import Lessor
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
import uuid
from accounts.models import Lessor
from .models import Properties, PropertyAmentities, PropertyPois, PropertyImage
from .serializers import CreatePropertyListingSerializer, PropertyImageSerializer
import googlemaps
from openai import OpenAI
from dotenv import load_dotenv

# from .serializers import PropertySerializer
from django.utils import timezone
import json
from tempfile import gettempdir
from .serializers import LocationAnalysisSerializer
from supabase import create_client
import os
import tempfile

# Load environment variables
load_dotenv()

# Initialize clients
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY3"))
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))


class SupabaseUploader:
    def __init__(self):
        self.client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY"),
        )
        self.bucket_name = "roomscout_media"

    def upload_image(self, file_obj, file_name):
        temp_file = None
        temp_file_path = None

        try:
            # Create a temporary file with a unique name
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file_path = temp_file.name
                # Write chunks to the temporary file
                for chunk in file_obj.chunks():
                    temp_file.write(chunk)

            # File is now closed, we can safely upload it
            with open(temp_file_path, "rb") as upload_file:
                response = self.client.storage.from_(self.bucket_name).upload(
                    file_name, upload_file
                )

            # Check for errors
            if (
                isinstance(response, dict)
                and "error" in response
                and response["error"] is not None
            ):
                raise Exception(response["error"]["message"])

            # Generate the public URL
            public_url = self.client.storage.from_(self.bucket_name).get_public_url(
                file_name
            )
            return public_url

        except Exception as e:
            raise Exception(f"Upload failed: {str(e)}")

        finally:
            # Clean up: ensure the temporary file is deleted
            try:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except Exception as cleanup_error:
                print(f"Warning: Failed to delete temporary file: {cleanup_error}")


class PropertyImageUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = PropertyImageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        property_id = serializer.validated_data["property_id"]
        image = request.FILES["image"]  # In-memory file object

        try:
            # Upload the image to Supabase
            uploader = SupabaseUploader()
            file_name = f"{property_id}/{image.name}"
            public_url = uploader.upload_image(image, file_name)

            # Save image metadata in the database
            PropertyImage.objects.create(
                property_id=property_id,
                file_name=image.name,
                url=public_url,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to upload image: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"url": public_url}, status=status.HTTP_201_CREATED)


def get_location_coordinates(location):
    """Get coordinates for a given location"""
    try:
        geocode_result = gmaps.geocode(location)
        if not geocode_result:
            return None, "Location not found"

        lat = geocode_result[0]["geometry"]["location"]["lat"]
        lng = geocode_result[0]["geometry"]["location"]["lng"]
        formatted_address = geocode_result[0]["formatted_address"]

        return (lat, lng, formatted_address), None
    except Exception as e:
        return None, str(e)


def generate_area_analysis(location_info, radius):
    """Generate comprehensive area analysis using OpenAI"""
    lat, lng, address = location_info

    # Get nearby places
    try:
        places_result = gmaps.places_nearby(location=(lat, lng), radius=radius)
    except Exception as e:
        # Return empty analysis if Google Places API fails
        return json.dumps(
            {"amenities": [], "error": f"Failed to fetch nearby places: {str(e)}"}
        )

    # Create a structured prompt that enforces JSON output
    prompt = f"""Analyze the following places data and create a JSON response with the 5 most important places of interest for a university student.
            POI means places of interest.
            Location: {address}
            Search Radius: {radius} meters
            Places Data: {places_result}

            The response must be in the following exact JSON format:
            {{
                "places_of_interest": [
                    {{
                        "poi_name": "Name and type of place",
                        "poi_ratings": "Rating or null if not available",
                        "poi_type": "Category of place of interest",
                        "distance": "Distance or travel time",
                        "coordinates": {{
                            "lat": latitude,
                            "lng": longitude
                        }}
                    }}
                ]
            }}

            Focus on student-relevant places of interest like pharmacies, grocery stores, subway stations, etc. Only include places within the {radius} meter radius.
            Ensure the output is valid JSON - use null for missing values, not None."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a JSON-outputting assistant that analyzes locations for student housing. Always output valid JSON following the exact schema provided.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1000,
        )

        # Get the response content
        content = response.choices[0].message.content.strip()

        # Remove any potential markdown code blocks
        content = content.replace("```json", "").replace("```", "").strip()

        # Validate JSON
        try:
            # Parse and re-serialize to ensure valid JSON
            parsed_json = json.loads(content)
            return json.dumps(parsed_json)
        except json.JSONDecodeError:
            # If parsing fails, return a valid JSON error response
            return json.dumps(
                {"amenities": [], "error": "Failed to generate valid JSON analysis"}
            )

    except Exception as e:
        # Return valid JSON even in case of OpenAI API error
        return json.dumps(
            {"amenities": [], "error": f"Analysis generation failed: {str(e)}"}
        )


class LocationAnalysisView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request):
        # Validate input data
        serializer = LocationAnalysisSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Ensure property_id is present
        if "property_id" not in serializer.validated_data:
            return Response(
                {"error": "Missing 'property_id' in the request payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract data from serializer
        property_id = serializer.validated_data["property_id"]
        location = serializer.validated_data["location"]
        radius = serializer.validated_data["radius"]

        # Get location coordinates
        location_info, error = get_location_coordinates(location)
        if not location_info:
            return Response({"error": error}, status=status.HTTP_404_NOT_FOUND)

        # Generate area analysis
        analysis = generate_area_analysis(location_info, radius)
        json_body = analysis.replace("```json", "").replace("```", "")
        analysis_output = json.loads(json_body)

        # Delete existing POIs for the property_id
        try:
            PropertyPois.objects.filter(property_id=property_id).delete()
        except Exception as e:
            return Response(
                {"error": f"Failed to delete existing POI data: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Insert new POIs into the property_pois table
        try:
            for poi in analysis_output.get("places_of_interest", []):
                PropertyPois.objects.create(
                    property_id=property_id,  # Use the validated property_id
                    poi_name=poi.get("poi_name"),
                    poi_ratings=poi.get("poi_ratings"),
                    poi_type=poi.get("poi_type"),
                    distance=poi.get("distance"),
                    latitude=poi["coordinates"]["lat"],
                    longitude=poi["coordinates"]["lng"],
                )
        except Exception as e:
            return Response(
                {"error": f"Failed to save POI data: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"address": location_info[2], "analysis": analysis_output},
            status=status.HTTP_200_OK,
        )


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

        # Validate input data
        serializer = CreatePropertyListingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract validated data
        validated_data = serializer.validated_data

        try:
            # Add the property to the `properties` table
            property_obj = Properties.objects.create(
                id=uuid.uuid4(),  # Generate a UUID
                lessor_id=lessor.user_id,  # Use `user_id` since it is the primary key
                title=validated_data["title"],
                street_adress=validated_data["street_address"],
                city=validated_data["city"],
                state=validated_data["state"],
                zip_code=validated_data["zip_code"],
                property_type=validated_data["property_type"],
                bedrooms=validated_data["bedrooms"],
                bathrooms=validated_data["bathrooms"],
                created_at=timezone.now(),
                modified_at=timezone.now(),
                available_since=validated_data["available_since"],
                guarantor_required=validated_data["guarantor_required"],
                additional_notes=validated_data.get("additional_notes", None),
            )

            # Add amenities to the `property_amentities` table
            PropertyAmentities.objects.create(
                property_id=str(
                    property_obj.id
                ),  # Use the UUID from the properties table
                air_conditioning=validated_data["air_conditioning"],
                parking=validated_data["parking"],
                dishwasher=validated_data["dishwasher"],
                heating=validated_data["heating"],
                gym=validated_data["gym"],
                refrigerator=validated_data["refrigerator"],
                laundry=validated_data["laundry"],
                swimming_pool=validated_data["swimming_pool"],
                microwave=validated_data["microwave"],
                created_at=timezone.now(),
                modified_at=timezone.now(),
            )

            return Response(
                {
                    "success": True,
                    "error": False,
                    "data": "Property and amenities added successfully.",
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": True,
                    "data": f"An error occurred: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
