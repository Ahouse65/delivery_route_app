import os
from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict, Any

import streamlit as st
import requests
from geopy.geocoders import Nominatim, Photon, ArcGIS
from geopy.extra.rate_limiter import RateLimiter
import folium
from streamlit_folium import st_folium

# -----------------------------
# Load ORS API key
# -----------------------------
def load_api_key() -> Optional[str]:
    try:
        v = st.secrets.get("ORS_API_KEY")
        if v: return str(v)
    except: pass
    v = os.environ.get("ORS_API_KEY")
    if v: return v
    for path in ["ors.properties", "./ors.properties"]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ORS_API_KEY"):
                        return line.split("=",1)[1].strip()
    return None

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
    def coords(self) -> Tuple[float,float]:
        return self.lat, self.lon

# -----------------------------
# Geocoding
# -----------------------------
@st.cache(ttl=60*60*24)
def geocode_multi(address: str, country_hint: str = "US") -> Optional[Place]:
    txt = address.strip()
    try:
        if "," in txt:
            lat, lon = map(float, txt.split(",",1))
            if -90<=lat<=90 and -180<=lon<=180:
                return Place(txt, lat, lon, f"{lat:.6
