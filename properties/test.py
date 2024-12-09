import os
import sys
import django

# Get the absolute path of the backend directory
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add backend directory to Python path
sys.path.append(BACKEND_DIR)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'househunt.settings')
django.setup()

import googlemaps
from properties.models import Properties  # Now we can import from the app
from househunt.settings import GOOGLE_MAPS_API_KEY

# Initialize Google Maps client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Get only properties where both latitude AND longitude are null
null_coord_properties = Properties.objects.filter(latitude__isnull=True).filter(longitude__isnull=True)

print(f"Found {null_coord_properties.count()} properties with null coordinates")

for prop in null_coord_properties:
    # Create full address
    full_address = f"{prop.street_address}, {prop.city}, {prop.state} {prop.zip_code}"
    print(f"Processing: {full_address}")
    
    try:
        # Get coordinates from Google Maps
        result = gmaps.geocode(full_address)
        
        if result:
            lat = result[0]['geometry']['location']['lat']
            lng = result[0]['geometry']['location']['lng']
            
            # Update property
            prop.latitude = lat
            prop.longitude = lng
            prop.save()
            
            print(f"Updated coordinates: ({lat}, {lng})")
        else:
            print(f"No coordinates found")
            
    except Exception as e:
        print(f"Error: {str(e)}")

print("Update complete!")