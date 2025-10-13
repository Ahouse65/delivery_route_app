import os
from dataclasses import dataclass
from typing import Tuple, List, Optional, Dict, Any

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
        return str(st.secrets.get("ORS_API_KEY"))
    except:
        return os.environ.get("ORS_API_KEY")

# -----------------------------
# Geocoding helper
# -----------------------------
@st.cache_data(ttl=24*60*60)
def geocode(address: str, country_hint="US") -> Optional[Place]:
    txt = address.strip()
    # Direct coordinates input
    try:
        if "," in txt:
            lat, lon = map(float, txt.split(",", 1))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return Place(txt, lat, lon, f"{lat:.6f}, {lon:.6f}")
    except:
        pass
    # Use Nominatim
    try:
        geolocator = Nominatim(user_agent="delivery-route-app")
        q = f"{txt}, {country_hint}" if country_hint and country_hint not in txt else txt
        res = geolocator.geocode(q)
        if res:
            return Place(txt, res.latitude, res.longitude, res.address)
    except:
        return None
    return None

# -----------------------------
# ORS directions
# -----------------------------
@st.cache_data(ttl=10*60)
def ors_directions(seq: List[Tuple[float,float]], api_key: Optional[str], profile="driving-car") -> Dict[str, Any]:
    if not api_key:
        return straight_line_route(seq)
    try:
        coords = [[lon, lat] for lat, lon in seq]
        url = f"https://api.openrouteservice.org/v2/directions/{profile}?format=geojson"
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        payload = {
            "coordinates": coords,
            "instructions": False,
            "geometry_simplify": True,
            "preference": "fastest",
            "units": "m",
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            return straight_line_route(seq)
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return straight_line_route(seq)
        geom = features[0].get("geometry", {}).get("coordinates", [])
        props = features[0].get("properties", {}).get("summary", {})
        distance = float(props.get("distance", 0))
        duration = float(props.get("duration", 0))
        coords_latlon = [[c[1], c[0]] for c in geom]
        return {"distance_m": distance, "duration_s": duration, "geometry": coords
