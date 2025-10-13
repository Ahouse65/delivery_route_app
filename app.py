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
# Helpers: load API key
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
                return Place(txt, lat, lon, f"{lat:.6f}, {lon:.6f}")
    except: pass

    q = f"{txt}, {country_hint}" if country_hint and country_hint not in txt else txt

    # Try providers
    for provider in [Nominatim(user_agent="route-app"), Photon(user_agent="route-app"), ArcGIS(user_agent="route-app")]:
        try:
            res = provider.geocode(q)
            if res:
                label = getattr(res, "address", str(res))
                return Place(txt, res.latitude, res.longitude, label)
        except: continue

    return None

# -----------------------------
# Fallback: straight line route
# -----------------------------
def straight_line_fallback(seq: List[Tuple[float,float]]) -> Dict[str,Any]:
    def approx_miles(p,q):
        return (((p[0]-q[0])**2 + (p[1]-q[1])**2)**0.5)*69.0
    d = sum(approx_miles(seq[i],seq[i+1]) for i in range(len(seq)-1))
    t_min = (d/22.0)*60.0  # 22 mph average
    return {
        "distance_m": d*1609.34,
        "duration_s": t_min*60.0,
        "geometry": [list(p) for p in seq],
        "source": "fallback"
    }

# -----------------------------
# ORS Directions
# -----------------------------
@st.cache(ttl=60*10)
def ors_directions(coords_latlon
