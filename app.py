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
        if v:
            return str(v)
    except Exception:
        pass
    v = os.environ.get("ORS_API_KEY")
    if v:
        return v
    for path in ["ors.properties", "./ors.properties"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("ORS_API_KEY"):
                            return line.split("=", 1)[1].strip()
            except Exception:
                pass
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
    def coords(self) -> Tuple[float, float]:
        return self.lat, self.lon


# -----------------------------
# Geocoding
# -----------------------------
@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def geocode_multi(address: str, country_hint: str = "US") -> Optional[Place]:
    txt = address.strip()
    # Check for lat,lon
    try:
        if "," in txt:
            lat, lon = map(float, txt.split(",", 1))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return Place(raw=address, lat=lat, lon=lon, label=f"{lat:.6f}, {lon:.6f}")
    except Exception:
        pass

    q = f"{txt}, {country_hint}" if country_hint and country_hint not in txt else txt

    # Providers
    try:
        nm = Nominatim(user_agent="route-app")
        nm_geocode = RateLimiter(nm.geocode, min_delay_seconds=1)
        res = nm_geocode(q)
        if res:
            return Place(raw=address, lat=res.latitude, lon=res.longitude, label=f"{res.address} [Nominatim]")
    except Exception:
        pass

    try:
        res = Photon(user_agent="route-app").geocode(txt)
        if res:
            return Place(raw=address, lat=res.latitude, lon=res.longitude, label=f"{res.address} [Photon]")
    except Exception:
        pass

    try:
        res = ArcGIS(user_agent="route-app").geocode(txt)
        if res:
            return Place(raw=address, lat=res.latitude, lon=res.longitude, label=f"{res.address} [ArcGIS]")
    except Exception:
        pass

    return
