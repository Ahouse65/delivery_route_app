import streamlit as st
import googlemaps
from datetime import datetime


st.set_page_config(page_title="Delivery Route Matcher", page_icon="🚗")


st.title("🚗 Delivery Route Matcher")


st.write("Compare two delivery routes to see if they align closely enough to accept both orders.")


# Google Maps API key
API_KEY = st.secrets.get("API_KEY", "YOUR_API_KEY_HERE")
gmaps = googlemaps.Client(key=API_KEY)


# Input for Route 1
st.header("First Delivery App (DoorDash, UberEats, etc.)")
pickup_1 = st.text_input("Pickup Address (Route 1)")
dropoff_1 = st.text_input("Dropoff Address (Route 1)")


# Input for Route 2
st.header("Second Delivery App (Another Order)")
pickup_2 = st.text_input("Pickup Address (Route 2)")
dropoff_2 = st.text_input("Dropoff Address (Route 2)")


if st.button("Compare Routes"):
    if pickup_1 and dropoff_1 and pickup_2 and dropoff_2:
        # Geocode addresses
        loc1_pick = gmaps.geocode(pickup_1)[0]['geometry']['location']
        loc1_drop = gmaps.geocode(dropoff_1)[0]['geometry']['location']
        loc2_pick = gmaps.geocode(pickup_2)[0]['geometry']['location']
        loc2_drop = gmaps.geocode(dropoff_2)[0]['geometry']['location']


        # Calculate distance between pickups and dropoffs
        def haversine(lat1, lon1, lat2, lon2):
            from math import radians, sin, cos, sqrt, atan2
            R = 6371  # Earth radius in km
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
            return R * 2 * atan2(sqrt(a), sqrt(1 - a))


        pickup_distance = haversine(loc1_pick['lat'], loc1_pick['lng'], loc2_pick['lat'], loc2_pick['lng'])
        dropoff_distance = haversine(loc1_drop['lat'], loc1_drop['lng'], loc2_drop['lat'], loc2_drop['lng'])


        st.write(f"Pickup Distance: {pickup_distance:.2f} km")
        st.write(f"Dropoff Distance: {dropoff_distance:.2f} km")


        if pickup_distance < 2 and dropoff_distance < 2:
            st.success("✅ Routes are close enough to combine!")
        else:
            st.warning("⚠️ Routes are too far apart.")
    else:
        st.error("Please enter all four addresses before comparing.")