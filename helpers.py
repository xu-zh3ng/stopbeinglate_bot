import re 
import requests
import dateparser
import os
from dotenv import load_dotenv

load_dotenv()
gmaps_API = os.getenv("gmaps_API")

def get_coords(url: str):
    patterns = [
        r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
        r"@(-?\d+\.\d+),(-?\d+\.\d+)",         
        r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)",      
        r"[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)",      
        r"(-?\d+\.\d+),\+(-?\d+\.\d+)",
    ]

    for pattern in patterns:
        valid = re.search(pattern, url)
        
        if valid:
            return float(valid.group(1)), float(valid.group(2))
        
    return None

def get_placename(url: str):
    match = re.search(r"place/([^/]+)/", url)
    if match:
        placename = match.group(1)
        return (placename.replace("+"," "))
    return None


def get_travel_time(origin_lat, origin_lon, mode, dest_placeid = None, dest_lat = None, dest_lon = None):
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": gmaps_API,
        "X-Goog-FieldMask": "routes.duration"  
    }
    
    body = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lon}}},
        "destination": {},
        "travelMode": mode.upper()  # DRIVE, TRANSIT, WALK
    }
    if dest_placeid:
        body["destination"] = {"placeId": dest_placeid}
    else:
        body["destination"] = {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lon}}}
    response = requests.post(url, json=body, headers=headers)
    data = response.json()
    
    if "routes" in data and data["routes"]:
        seconds = int(data["routes"][0]["duration"].rstrip("s"))
        return round(seconds / 60)
    return None

def meetup_time(time):
    dt = dateparser.parse(time, settings={
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": "Asia/Singapore",
        "DATE_ORDER": "DMY"
    })
    return dt

def get_placeid(input: str):
    url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": gmaps_API,
        "X-Goog-FieldMask": "places.id,places.displayName,places.location"
    }
    
    body = {
        "textQuery": input,
    }
    
    response = requests.post(url, json=body, headers=headers)
    data = response.json()
    
    if "places" in data and data["places"]:
        temp = {"placeid" : data["places"][0]["id"],
                "name" : data["places"][0]["displayName"]["text"],
                "lat" : data["places"][0]["location"]["latitude"],
                "long" : data["places"][0]["location"]["longitude"]}
        return temp
    return None
