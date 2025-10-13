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
# Helpers
# -----------------------------
def load_api_key() -> Optional[str]:
    try:
        v = st.secrets.get("ORS_API_KEY")
        if v: return str(v)
    except Exception: pass
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
@st.cache_data(ttl=60*60*24)
def geocode_multi(address: str, country_hint: str = "US") -> Optional[Place]:
    txt = address.strip()
    try:
        if "," in txt:
            lat, lon = map(float, txt.split(",",1))
            if -90<=lat<=90 and -180<=lon<=180:
                return Place(txt, lat, lon, f"{lat:.6f}, {lon:.6f}")
    except: pass

    q = f"{txt}, {country_hint}" if country_hint and country_hint not in txt else txt
    for provider in [Nominatim(user_agent="route-app"), Photon(user_agent="route-app"), ArcGIS(user_agent="route-app")]:
        try:
            res = provider.geocode(q)
            if res:
                return Place(txt, res.latitude, res.longitude, getattr(res, "address", str(res)))
        except: continue
    return None

# -----------------------------
# ORS Directions
# -----------------------------
@st.cache_data(ttl=60*10)
def ors_directions(coords_latlon: List[Tuple[float,float]], api_key: Optional[str], profile="driving-car") -> Dict[str,Any]:
    if not api_key:
        return straight_line_fallback(coords_latlon)
    try:
        coords_lonlat = [[lon,lat] for lat,lon in coords_latlon]
        url = f"https://api.openrouteservice.org/v2/directions/{profile}?format=geojson"
        headers={"Authorization":api_key,"Content-Type":"application/json"}
        payload={"coordinates":coords_lonlat,"instructions":False,"geometry_simplify":True,"preference":"fastest","units":"m"}
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code!=200: return straight_line_fallback(coords_latlon)
        data = resp.json()
        features = data.get("features", [])
        if not features: return straight_line_fallback(coords_latlon)
