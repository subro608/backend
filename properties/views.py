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
    PropertyAmenitiesSerializer,
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
from django.db import transaction

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

    def upload_file(self, file_obj, file_name,bucket_name = ''):
        temp_file = None
        temp_file_path = None
        if not bucket_name:
            bucket_name = self.bucket_name

        try:
            # Create a temporary file with a unique name
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file_path = temp_file.name
                # Write chunks to the temporary file
                for chunk in file_obj.chunks():
                    temp_file.write(chunk)

            # File is now closed, we can safely upload it
            with open(temp_file_path, "rb") as upload_file:
                response = self.client.storage.from_(bucket_name).upload(
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
            public_url = self.client.storage.from_(bucket_name).get_public_url(
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

    def delete_file(self, file_path):
        try:
            self.client.storage.from_(self.bucket_name).remove([file_path])
        except Exception as e:
            raise Exception(f"Delete failed: {str(e)}")


class PropertyImageUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Upload up to 3 images for a property.
        Request should include:
        - property_id: string
        - images or image: list of image files or single image file
        """
        try:
            # Validate property_id
            serializer = PropertyImageSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            property_id = serializer.validated_data["property_id"]
            new_files = request.FILES.getlist("new_images")
            deleted_file_ids = request.data["deleted_images"]
            deleted_file_ids = json.loads(deleted_file_ids) if deleted_file_ids else []

            # Check if property exists
            if not Properties.objects.filter(id=property_id).exists():
                return Response({
                    "success": False,
                    "error": True,
                    "message": "Property not found"
                }, status=status.HTTP_404_NOT_FOUND)
            # Get existing image count
            existing_images = PropertyImage.objects.filter(property_id=property_id).count()
             # Check if total images would exceed limit
            if existing_images + len(new_files) - len(deleted_file_ids)> 3:
                return Response({
                    "success": False,
                    "error": True,
                    "message": f"Cannot upload {len(new_files) - len(deleted_file_ids)} images. Maximum total images allowed is 3. Currently has {existing_images} images."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            uploader = SupabaseUploader()

            for file_id in deleted_file_ids:
                try:
                    property_image = PropertyImage.objects.get(id=file_id)
                    file_path = (
                        f"{property_image.property_id}/{property_image.file_name}"
                    )
                    uploader.delete_file(file_path)
                    property_image.delete()
                except PropertyImage.DoesNotExist:
                    return Response({
                        "success": False,
                        "error": True,
                        "message": f"Image does not exists {file_id}"
                    }, status=status.HTTP_400_BAD_REQUEST)

            for file in new_files:
                # Upload the image to Supabase
                file_name = f"{property_id}/{file.name}"
                public_url = uploader.upload_file(file, file_name)

                # Save image metadata in the database
                PropertyImage.objects.create(
                    property_id=property_id,
                    file_name=file.name,
                    url=public_url,
                )
        except Exception as e:
            return Response({
                        "success": False,
                        "error": True,
                        "message": f"Failed to upload image {str(e)}"
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
                "success": True,
                "error": False,
                "data": {
                    "property_id": property_id,
                    "total_images": existing_images + len(new_files) - len(deleted_file_ids)
                },
                "message": f"Successfully uploaded {len(new_files)} images. Deleted {len(deleted_file_ids)} images"
            }, status=status.HTTP_201_CREATED)


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
            # Generate full address for geocoding
            full_address = f"{validated_data['street_address']}, {validated_data['city']}, {validated_data['state']} {validated_data['zip_code']}"
            
            # Get coordinates using the existing function
            location_info, error = get_location_coordinates(full_address)
            
            if not location_info:
                return Response(
                    {
                        "success": False,
                        "error": True,
                        "data": f"Failed to get coordinates for address: {error}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            latitude, longitude, formatted_address = location_info

            with transaction.atomic():
                # Add the property to the `properties` table with coordinates
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
                    description=validated_data.get("description"),
                    latitude=latitude,  # Add latitude
                    longitude=longitude,  # Add longitude
                )

                amenities = validated_data["amenities"]
                # Add amenities to the `property_amentities` table
                PropertyAmenities.objects.create(
                    property_id=str(property_obj.id),
                    air_conditioning=amenities["air_conditioning"],
                    parking=amenities["parking"],
                    dishwasher=amenities["dishwasher"],
                    heating=amenities["heating"],
                    gym=amenities["gym"],
                    refrigerator=amenities["refrigerator"],
                    laundry=amenities["laundry"],
                    swimming_pool=amenities["swimming_pool"],
                    microwave=amenities["microwave"],
                    created_at=timezone.now(),
                    modified_at=timezone.now(),
                )
                return Response(
                    {
                        "success": True,
                        "error": False,
                        "data": {
                            "property_id": str(property_obj.id),
                            "coordinates": {
                                "latitude": latitude,
                                "longitude": longitude
                            },
                            "formatted_address": formatted_address
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

    def get(self,request):
        try:
            user = request.user
            lessee_id = user.id
            wishlist_items = PropertyWishlist.objects.filter(
                lessee_id=lessee_id,
                is_wishlist=True
            ).values_list('property_id', flat=True)

            properties_query = Properties.objects.filter(id__in=wishlist_items)
            properties_query = properties_query.order_by("-created_at")

            page = request.GET.get("page", 1)  # Default to page 1 if not provided
            per_page = request.GET.get("per_page", 10)  # Default to 10 items per page

            paginator = Paginator(properties_query,per_page)
            properties_page = paginator.page(page)

            properties_data = []
            for property in properties_page:
                # Fetch related amenities, images, and POIs using helper methods
                amenities = property.get_amenities()
                images = list(property.get_images().values())
                pois = list(property.get_pois().values())

                # Add the property data with related data
                properties_data.append(
                    {
                        "id": property.id,
                        "title": property.title,
                        "rent": property.rent,
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
                            "description": property.description,
                        },
                        "created_at": property.created_at,
                        "amenities": PropertyAmenitiesSerializer(amenities).data,
                        "available_since": property.available_since,
                        "additional_notes": property.additional_notes,
                        "images": images,
                        "pois": pois,
                        "status_verification": property.status_verification,
                    }
                )
            
            return Response({
                'success': True,
                'error':False,
                'data':{
                    "total_count": paginator.count,
                    "total_pages": paginator.num_pages,
                    "current_page": properties_page.number,
                    "properties": properties_data,
                }
            }, status= status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': True,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            amenities = property.get_amenities()
            images = list(property.get_images().values())
            pois = list(property.get_pois().values())

            # Add the property data with related data
            properties_data.append(
                {
                    "id": property.id,
                    "title": property.title,
                    "rent": property.rent,
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
                        "description": property.description,
                    },
                    "created_at": property.created_at,
                    "amenities": PropertyAmenitiesSerializer(amenities).data,
                    "available_since": property.available_since,
                    "additional_notes": property.additional_notes,
                    "images": images,
                    "pois": pois,
                    "status_verification": property.status_verification,
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

class GetAllPropertiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = request.GET.get("page", 1)  # Default to page 1 if not provided
        per_page = request.GET.get("per_page", 10)  # Default to 10 items per page

        # Query properties data ordered by `created_at`
        properties_query = Properties.objects.filter(is_deleted=False).order_by("-created_at")
        paginator = Paginator(properties_query, per_page)

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
            amenities = property.get_amenities()
            images = list(property.get_images().values())
            pois = list(property.get_pois().values())

            # Add the property data with related data
            properties_data.append(
                {
                    "id": property.id,
                    "title": property.title,
                    "rent": property.rent,
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
                        "description": property.description,
                    },
                    "created_at": property.created_at,
                    "amenities": PropertyAmenitiesSerializer(amenities).data,
                    "available_since": property.available_since,
                    "additional_notes": property.additional_notes,
                    "images": images,
                    "pois": pois,
                    "status_verification": property.status_verification,
                }
            )

        # Return paginated response
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

class SubmitPropertyForVerificationView(APIView):
    permission_classes = [IsAuthenticated]
    STATUS_VERIFICATION_PROPERTY_NOT_SUBMITTED = 0
    STATUS_VERIFICATION_PROPERTY_SUBMITTED = 1
    STATUS_VERIFICATION_PROPERTY_DENIED = 2
    STATUS_VERIFICATION_PROPERTY_VERIFIED = 3

    def post(self, request):
        try:
            user = request.user
            # Validate lessor
            lessor = Lessor.objects.filter(user=user).first()
            if not lessor:
                return Response(
                    {"error": "Only valid lessors can submit properties for verification."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            property_id = request.data.get("property_id")
            if not property_id:
                return Response(
                    {"error": "Property ID is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Fetch the property
            property_obj = Properties.objects.filter(
                id=property_id, lessor_id=lessor.user_id, is_deleted=False
            ).first()
            
            if not property_obj:
                return Response(
                    {"error": "Property not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Update the status if not already submitted
            if property_obj.status_verification == self.STATUS_VERIFICATION_PROPERTY_SUBMITTED:
                return Response(
                    {"error": "Property is already submitted for verification."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            property_obj.status_verification = self.STATUS_VERIFICATION_PROPERTY_SUBMITTED
            property_obj.save()

            return Response(
                {"success": True, "message": "Property submitted for verification."},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            print(f"Error in SubmitPropertyForVerificationView: {str(e)}")  # Add logging
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            amenities_requestobj = request.data["amenities"]
            for field in amenity_fields:
                value = amenities_requestobj.get(field)
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

        if not property_obj:
            return Response(
                {
                    "success": False,
                    "error": True,
                    "data": "Property not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        amenities = property_obj.get_amenities()
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
                "available_since": property_obj.available_since,
                "additional_notes": property_obj.additional_notes
            },
            "created_at": property_obj.created_at,
            "modified_at": property_obj.modified_at,
            "amenities": PropertyAmenitiesSerializer(amenities).data,
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


class AddressValidationView(APIView):

    def post(self, request):
        """
        Validate address components by checking if they can be geocoded
        
        Request body should be:
        {
            "street_address": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip_code": "12345"
        }
        """
        # Extract address components
        street_address = request.data.get('street_address', '').strip()
        city = request.data.get('city', '').strip()
        state = request.data.get('state', '').strip()
        zip_code = str(request.data.get('zip_code', '')).strip()

        # Validate that required fields are present
        if not all([street_address, city, state, zip_code]):
            return Response({
                'success': False,
                'error': True,
                'message': 'All address components (street, city, state, zip) are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Construct full address string
            full_address = f"{street_address}, {city}, {state} {zip_code}"

            # Initialize Google Maps client
            gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

            # Attempt to geocode the address
            geocode_result = gmaps.geocode(full_address)

            # Check if geocoding returned any results
            if geocode_result:
                # Validate each component against the geocoded result
                formatted_address = geocode_result[0]['formatted_address']
                address_components = geocode_result[0]['address_components']

                # Initialize validation results
                validated_components = {
                    'street_address': False,
                    'city': False,
                    'state': False,
                    'zip_code': False
                }

                # Check components
                for component in address_components:
                    if 'street_number' in component['types'] or 'route' in component['types']:
                        validated_components['street_address'] = True
                    
                    if ('locality' in component['types'] or 'sublocality' in component['types'] or 'neighborhood' in component['types']) and city.lower() in component['long_name'].lower():
                        validated_components['city'] = True
                    
                    if 'administrative_area_level_1' in component['types'] and state.upper() == component['short_name']:
                        validated_components['state'] = True
                    
                    if 'postal_code' in component['types'] and zip_code in component['long_name']:
                        validated_components['zip_code'] = True

                # Generate error messages for invalid components
                error_messages = []
                if not validated_components['street_address']:
                    error_messages.append("Street address is incorrect or not found")
                if not validated_components['city']:
                    error_messages.append("City name is incorrect or not found")
                if not validated_components['state']:
                    error_messages.append("State is incorrect or not found")
                if not validated_components['zip_code']:
                    error_messages.append("ZIP code is incorrect or not found")

                # Determine overall legitimacy
                is_legit = all(validated_components.values())

                return Response({
                    'success': True,
                    'error': False,
                    'data': {
                        'legit': is_legit,
                        'formatted_address': formatted_address,
                        'validated_components': validated_components,
                        'error_messages': error_messages if error_messages else None
                    }
                }, status=status.HTTP_200_OK)
            else:
                # No results found, address is not valid
                return Response({
                    'success': True,
                    'error': False,
                    'data': {
                        'legit': False,
                        'validated_components': {
                            'street_address': False,
                            'city': False,
                            'state': False,
                            'zip_code': False
                        },
                        'error_messages': ["Address not found or invalid"]
                    }
                }, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle any errors in geocoding (network, API issues)
            return Response({
                'success': False,
                'error': True,
                'message': f'Address validation failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

import math


class PropertySearchView(APIView):
    # permission_classes = [PropertySearchView]

    def get(self, request):
        """
        Search properties with three scenarios:
        1. Basic: location and radius only
        2. With filters: location, radius, and filters (default date sorting)
        3. Complete: location, radius, filters, and specific sorting
        
        Required params:
        - location: string (address, borough, or neighborhood)
        - radius: int (in kilometers, default: 5)
        
        Optional params:
        - min_rent: float
        - max_rent: float
        - bedrooms: float
        - bathrooms: float
        - property_type: string
        - sort_by: string (rent_asc, rent_desc, date_asc, date_desc, beds_asc, beds_desc, baths_asc, baths_desc)
        - page: int
        - per_page: int
        """
        try:
            # Get required location parameters
            location = request.GET.get('location')
            radius = int(request.GET.get('radius', 5))
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 10))

            #get user data
            user = request.user
            lessee_id = user.id
            wishlist_items = set()
            if lessee_id:
                wishlist_items = {str(id) for id in PropertyWishlist.objects.filter(
                    lessee_id=lessee_id,
                    is_wishlist=True
                ).values_list('property_id', flat=True)}
            
            # Validate location parameter
            if not location:
                return Response({
                    'success': False,
                    'error': True,
                    'message': 'Location parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get coordinates from Google Maps
            gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
            geocode_result = gmaps.geocode(location)

            if not geocode_result:
                return Response({
                    'success': False,
                    'error': True,
                    'message': 'Location not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Get center coordinates
            center_lat = geocode_result[0]['geometry']['location']['lat']
            center_lng = geocode_result[0]['geometry']['location']['lng']
            formatted_address = geocode_result[0]['formatted_address']

            # Calculate search area
            lat_range = radius / 111.0
            lon_range = radius / (111.0 * math.cos(math.radians(center_lat)))

            # Get properties within radius
            properties = Properties.objects.filter(
                latitude__range=(center_lat - lat_range, center_lat + lat_range),
                longitude__range=(center_lng - lon_range, center_lng + lon_range),
                is_deleted=False
            )

            # Check for filter parameters
            min_rent = request.GET.get('min_rent')
            max_rent = request.GET.get('max_rent')
            bedrooms = request.GET.get('bedrooms')
            bathrooms = request.GET.get('bathrooms')
            property_type = request.GET.get('property_type')

            # Apply filters if any are present
            if min_rent:
                properties = properties.filter(rent__gte=float(min_rent))
            if max_rent:
                properties = properties.filter(rent__lte=float(max_rent))
            if bedrooms:
                properties = properties.filter(bedrooms__gte=float(bedrooms))
            if bathrooms:
                properties = properties.filter(bathrooms__gte=float(bathrooms))
            if property_type:
                properties = properties.filter(property_type__iexact=property_type)

            # Define sorting options
            sort_options = {
                'rent_asc': 'rent',
                'rent_desc': '-rent',
                'date_asc': 'created_at',
                'date_desc': '-created_at',
                'beds_asc': 'bedrooms',
                'beds_desc': '-bedrooms',
                'baths_asc': 'bathrooms',
                'baths_desc': '-bathrooms'
            }

            # Get sort parameter if it exists
            sort_by = request.GET.get('sort_by')
            
            # Apply sorting
            if sort_by and sort_by in sort_options:
                properties = properties.order_by(sort_options[sort_by])
            else:
                # Default sorting by date if filters are present
                has_filters = any([min_rent, max_rent, bedrooms, bathrooms, property_type])
                if has_filters:
                    properties = properties.order_by('-created_at')

            # Calculate distances and format properties
            properties_with_distance = []
            for prop in properties:
                # Calculate exact distance
                dlat = math.radians(float(prop.latitude) - center_lat)
                dlon = math.radians(float(prop.longitude) - center_lng)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(center_lat)) * \
                    math.cos(math.radians(float(prop.latitude))) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance = 6371 * c  # Radius of earth in kilometers

                if distance <= radius:
                    # Get related data
                    # amenities = prop.get_amenities().values().first() or {}
                    images = list(prop.get_images().values())
                    pois = list(prop.get_pois().values())

                    properties_with_distance.append({
                        'id': prop.id,
                        'title': prop.title,
                        'address': {
                            'street_address': prop.street_address,
                            'city': prop.city,
                            'state': prop.state,
                            'zip_code': prop.zip_code,
                        },
                        'details': {
                            'bedrooms': prop.bedrooms,
                            'bathrooms': prop.bathrooms,
                            'rent': prop.rent,
                            'property_type': prop.property_type,
                            'available_since': prop.available_since,
                            'created_at': prop.created_at,
                            'guarantor_required': prop.guarantor_required,
                            'additional_notes': prop.additional_notes
                        },
                        # 'amenities': amenities,
                        'images': images,
                        'pois': pois,
                        'distance': round(distance, 2),
                        'coordinates': {
                            'latitude': prop.latitude,
                            'longitude': prop.longitude
                        },
                        'isInWishlist': str(prop.id) in wishlist_items
                    })

            # Paginate results
            paginator = Paginator(properties_with_distance, per_page)
            page_obj = paginator.get_page(page)

            return Response({
                'success': True,
                'error': False,
                'data': {
                    'properties': list(page_obj),
                    'total_count': paginator.count,
                    'total_pages': paginator.num_pages,
                    'current_page': page,
                    'search_criteria': {
                        'location': formatted_address,
                        'radius': radius,
                        'filters_applied': {
                            'min_rent': min_rent,
                            'max_rent': max_rent,
                            'bedrooms': bedrooms,
                            'bathrooms': bathrooms,
                            'property_type': property_type
                        } if any([min_rent, max_rent, bedrooms, bathrooms, property_type]) else None,
                        'sort_by': sort_by if sort_by in sort_options else ('date_desc' if any([min_rent, max_rent, bedrooms, bathrooms, property_type]) else None)
                    },
                    'available_sort_options': list(sort_options.keys())
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'error': True,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)