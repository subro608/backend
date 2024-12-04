from django.shortcuts import render
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
from .models import Properties, PropertyAmenities, PropertyPois, PropertyImage, PropertyWishlist
from .serializers import (
    CreatePropertyListingSerializer,
    PropertyImageSerializer,
    LocationAnalysisSerializer,
    RemoveWishlistSerializer,
    DeletePropertySerializer,
    WishlistSerializer,
    ModifyPropertyListingSerializer,
)
import googlemaps
from openai import OpenAI
from dotenv import load_dotenv

from django.utils import timezone
import json
from supabase import create_client
import os
import tempfile
from rest_framework.pagination import PageNumberPagination

from househunt.settings import (
    OPENAI_API_KEY,
    GOOGLE_MAPS_API_KEY,
    SUPABASE_URL,
    SUPABASE_KEY,
)

from django.core.paginator import Paginator

print(OPENAI_API_KEY, "OPENAI_API_KEYOPENAI_API_KEYOPENAI_API_KEY")
# Initialize clients
print("supabase", SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)


class SupabaseUploader:
    def __init__(self):
        self.client = create_client(
            supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY
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
    permission_classes = [IsAuthenticated]

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
                street_address=validated_data["street_address"],
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
                rent=validated_data.get("rent", 0),
            )

            # Add amenities to the `property_amentities` table
            PropertyAmenities.objects.create(
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
                    "data": {
                        "property_id": str(property_obj.id),
                    },
                    "message": "Property and amenities added successfully.",
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


class PropertyWishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Validate input data
            serializer = WishlistSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        'success': False,
                        'error': True,
                        'message': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            lessee_id = serializer.validated_data['lessee_id']
            property_id = serializer.validated_data['property_id']

            # Check if property exists
            if not Properties.objects.filter(id=property_id).exists():
                return Response(
                    {
                        'success': False,
                        'error': True,
                        'message': 'Property does not exist.'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Create or update wishlist entry
            wishlist_item, created = PropertyWishlist.objects.get_or_create(
                lessee_id=lessee_id,
                property_id=property_id,
                defaults={'is_wishlist': True}
            )

            if not created:
                # Toggle wishlist status if entry already exists
                wishlist_item.is_wishlist = not wishlist_item.is_wishlist
                wishlist_item.save()

            return Response(
                {
                    'success': True,
                    'error': False,
                    'data': {
                        'lessee_id': lessee_id,
                        'property_id': property_id,
                        'is_wishlist': wishlist_item.is_wishlist,
                        'message': 'Property added to wishlist' if wishlist_item.is_wishlist else 'Property removed from wishlist'
                    }
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    'success': False,
                    'error': True,
                    'message': f'An error occurred: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class GetAllPropertiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_wishlist = request.GET.get('is_wishlist', 'false').lower() == 'true'  # Convert string to boolean
        lessee_id = request.GET.get('lessee_id', None)

        print(f"Debug - is_wishlist: {is_wishlist}, type: {type(is_wishlist)}")
        print(f"Debug - lessee_id: {lessee_id}, type: {type(lessee_id)}")

        # If it's a wishlist request, we need lessee_id
        if is_wishlist and not lessee_id:
            return Response(
                {
                    "success": False,
                    "message": "lessee_id is required for wishlist.",
                    "error": True,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Query properties data based on type
        if is_wishlist:
            # Get wishlist property IDs
            wishlist_items = PropertyWishlist.objects.filter(
                lessee_id=lessee_id,
                is_wishlist=True
            ).values_list('property_id', flat=True)
            
            print(f"Debug - wishlist_items: {list(wishlist_items)}")
            
            properties_query = Properties.objects.filter(id__in=wishlist_items)
            
            print(f"Debug - properties found: {properties_query.count()}")
        else:
            if not Lessor.objects.filter(user=user).exists():
                return Response(
                    {"error": "Only valid lessors can view their property listings."},
                    status=status.HTTP_403_FORBIDDEN
                )

            lessor = Lessor.objects.get(user=user)
            properties_query = Properties.objects.filter(lessor_id=lessor.user_id)

        # Order by created_at
        properties_query = properties_query.order_by("-created_at")
        paginator = Paginator(properties_query, int(request.GET.get("per_page", 10)))
        page = request.GET.get("page", 1)

        try:
            properties_page = paginator.page(page)
        except:
            return Response(
                {
                    "data": None,
                    "success": False,
                    "error": True,
                    "message": "Invalid page number",
                },
                status=400,
            )

        # Build response with related data
        properties_data = []
        for property in properties_page:
            # Fetch related amenities, images, and POIs using helper methods
            amenities = property.get_amenities().values()
            images = list(property.get_images().values())
            pois = list(property.get_pois().values())

            properties_data.append(
                {
                    "id": property.id,
                    "title": property.title,
                    "address": {
                        "street_address": property.street_address,
                        "city": property.city,
                        "state": property.state,
                        "zip_code": property.zip_code,
                    },
                    "details": {
                        "bedrooms": property.bedrooms,
                        "bathrooms": property.bathrooms,
                        "property_type": property.property_type,
                        "guarantor_required": property.guarantor_required,
                    },
                    "created_at": property.created_at,
                    "amenities": list(amenities),
                    "images": images,
                    "pois": pois,
                }
            )

        response = {
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": properties_page.number,
            "properties": properties_data,
        }

        return Response(
            {
                "error": False,
                "data": response,
                "success": True,
                "message": "Properties returned successfully.",
            },
            status=200,
        )

# API View to delete a property

class RemoveWishlistView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            # Validate input data
            serializer = RemoveWishlistSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        'success': False,
                        'error': True,
                        'message': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            lessee_id = serializer.validated_data['lessee_id']
            property_id = serializer.validated_data['property_id']

            # Try to find and delete the wishlist entry
            try:
                wishlist_item = PropertyWishlist.objects.get(
                    lessee_id=lessee_id,
                    property_id=property_id,
                    is_wishlist=True
                )
                wishlist_item.delete()
                
                return Response(
                    {
                        'success': True,
                        'error': False,
                        'data': {
                            'lessee_id': lessee_id,
                            'property_id': property_id,
                            'message': 'Property successfully removed from wishlist'
                        }
                    },
                    status=status.HTTP_200_OK
                )
                
            except PropertyWishlist.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'error': True,
                        'message': 'Property not found in wishlist'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

        except Exception as e:
            return Response(
                {
                    'success': False,
                    'error': True,
                    'message': f'An error occurred: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class DeletePropertyView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        user = request.user

        lessor = Lessor.objects.get(user=user)

        if not lessor:
            return Response(
                {
                    "success": False,
                    "message": "Only valid lessors can delete their property listings.",
                    "error": True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate input data
        serializer = DeletePropertySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract validated data
        validated_data = serializer.validated_data

        print(validated_data)

        # update property object to set is_deleted to True

        try:
            # Add the property to the `properties` table
            property_obj = Properties.objects.get(
                id=validated_data["property_id"], lessor_id=lessor.user_id
            )

            if not property_obj:
                return Response(
                    {
                        "success": False,
                        "error": True,
                        "data": "Property not found.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # if property is already deleted should be bad request
            if property_obj.is_deleted:
                return Response(
                    {
                        "success": False,
                        "error": True,
                        "data": "Property already deleted.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            property_obj.is_deleted = True
            property_obj.save()

            return Response(
                {
                    "success": True,
                    "error": False,
                    "data": "Property deleted successfully.",
                },
                status=status.HTTP_200_OK,
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


# api view to modify a property
class ModifyPropertyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            lessor = Lessor.objects.get(user=user)

            if not lessor:
                return Response(
                    {
                        "success": False,
                        "message": "Only valid lessors can modify their property listings.",
                        "error": True,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Validate input data
            serializer = ModifyPropertyListingSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            validated_data = serializer.validated_data
            property_id = validated_data["property_id"]

            # Get the property object
            property_obj = Properties.objects.get(
                id=property_id,
                lessor_id=lessor.user_id,
                is_deleted=False,
            )

            if not property_obj:
                return Response(
                    {
                        "success": False,
                        "error": True,
                        "data": "Property not found.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Update allowed property fields
            property_fields = [
                "additional_notes",
                "rent",
                "title",
                "guarantor_required",
                "available_since"
            ]

            for field in property_fields:
                value = request.data.get(field)
                if value is not None:
                    setattr(property_obj, field, value)

            property_obj.modified_at = timezone.now()
            property_obj.save()

            # Update amenities in separate table
            amenity_fields = [
                "air_conditioning",
                "parking",
                "dishwasher",
                "heating",
                "gym",
                "refrigerator",
                "laundry",
                "swimming_pool",
                "microwave"
            ]

            # Get or create amenities object
            amenities_obj, created = PropertyAmenities.objects.get_or_create(
                property_id=str(property_id),
                defaults={
                    'created_at': timezone.now(),
                    'modified_at': timezone.now()
                }
            )

            # Update amenities
            amenities_updated = False
            for field in amenity_fields:
                if field in request.data:
                    value = request.data.get(field)
                    if value is not None:
                        setattr(amenities_obj, field, value)
                        amenities_updated = True

            if amenities_updated:
                amenities_obj.modified_at = timezone.now()
                amenities_obj.save()

            return Response(
                {
                    "success": True,
                    "error": False,
                    "data": {
                        "message": "Property updated successfully",
                        "property_id": str(property_id)
                    }
                },
                status=status.HTTP_200_OK,
            )

        except Properties.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": True,
                    "data": "Property not found",
                },
                status=status.HTTP_404_NOT_FOUND,
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


class GetPropertyDetailsView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, property_id):
        user = request.user
        lessor = Lessor.objects.get(user=user)

        # Debug prints
        print(f"Searching for property_id: {property_id}")
        print(f"Current lessor_id: {lessor.user_id}")
        
        # Check if property exists at all
        property_exists = Properties.objects.filter(id=property_id).first()
        print(f"Property exists in DB: {property_exists}")
        
        if property_exists:
            print(f"Property lessor_id: {property_exists.lessor_id}")
            print(f"Property is_deleted: {property_exists.is_deleted}")

        # Original query
        property_obj = Properties.objects.filter(
            id=property_id, 
            lessor_id=lessor.user_id,
            is_deleted=False
        ).first()

        print(property_obj)

        if not property_obj:
            return Response(
                {
                    "success": False,
                    "error": True,
                    "data": "Property not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        amenities = property_obj.get_amenities().values()
        images = list(property_obj.get_images().values())
        pois = list(property_obj.get_pois().values())

        # Add the property data with related data
        result = {
            "id": property_obj.id,
            "title": property_obj.title,
            "address": {
                "street_address": property_obj.street_address,
                "city": property_obj.city,
                "state": property_obj.state,
                "zip_code": property_obj.zip_code,
            },
            "details": {
                "bedrooms": property_obj.bedrooms,
                "bathrooms": property_obj.bathrooms,
                "property_type": property_obj.property_type,
                "guarantor_required": property_obj.guarantor_required,
                "rent": property_obj.rent,
                "available_since": property_obj.available_since
            },
            "created_at": property_obj.created_at,
            "modified_at": property_obj.modified_at,
            "amenities": amenities,
            "images": images,
            "pois": pois,
        }

        return Response(
            {
                "error": False,
                "data": result,
                "message": "Property details returned successfully.",
                "success": True,
            },
            status=status.HTTP_200_OK,
        )
