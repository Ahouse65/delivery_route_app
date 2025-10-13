import os
from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict, Any

import streamlit as st
import requests
from geopy.geocoders import Nominatim
from folium import Map, Marker, PolyLine, TileLayer, Icon
from streamlit_folium import st_folium

# -----------------------------
# Data model
# -----------------------------
@dataclass
class Place:
    raw: str
    lat: float
    lon: float
    label: str

    @property
    def coords(self) -> Tuple[float, float]:
        return (self.lat, self.lon)

# -----------------------------
# Load ORS API key
# -----------------------------
def load_api_key() -> Optional[str]:
    try:
        v = st.secrets.get("ORS_API_KEY")
        if v:
            return str(v)
    except:
        pass
    return os.environ.get("ORS_API_KEY")

# -----------------------------
# Geocoding
# -----------------------------
@st.cache_data(ttl=60*60*24)
def geocode(address: str, country_hint="US") -> Optional[Place]:
    txt = address.strip()
    # Try direct coordinates
    try:
        if "," in txt:
            lat, lon = map(float, txt.split(",", 1))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return Place(txt, lat, lon, f"{lat:.6f}, {lon:.6f}")
    except Exception:
        pass

    # Try Nominatim geocoding
    try:
        geolocator = Nominatim(user_agent="delivery-route-app")
        q = f"{txt}, {country_hint}" if country_hint and country_hint not in txt else txt
        res = geolocator.geocode(q)
        if res:
            return Place(txt, res.latitude, res.longitude, res.address)
    except Exception:
        return None
    return None

# -----------------------------
# Straight-line fallback
# -----------------------------
def straight_line_route(seq: List[Tuple[float,float]], buffer_pct=20) -> Dict[str,Any]:
    def approx_miles(p,q):
        return (((p[0]-q[0])**2 + (p[1]-q[1])**2)**0.5)*69.0
    distance = sum(approx_miles(seq[i], seq[i+1]) for i in range(len(seq)-1))
    duration = (distance/22.0)*60.0*(1+buffer_pct/100.0)
    return {
        "distance_m": distance*1609.34,
        "duration_s": duration*60.0,
        "geometry":[list(p) for p in seq],
        "source":"fallback"
    }

# -----------------------------
# ORS Directions
# -----------------------------
@st.cache_data(ttl=60*10)
def ors_directions(seq: List[Tuple[float,float]], api_key: Optional[str], profile="driving-car") -> Dict[str,Any]:
    if not api_key:
        return straight_line_route(seq)
    try:
        coords = [[lon, lat] for lat, lon in seq]
        url = f"https://api.openrouteservice.org/v2/directions/{profile}?format=geojson"
        headers = {"Authorization": api_key,"Content-Type":"application/json"}
        payload = {"coordinates": coords, "instructions":
