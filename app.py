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
    """Try loading ORS_API_KEY from Streamlit secrets, env var, or ors.properties file."""
    try:
        v = st.secrets.get("ORS_API_KEY")
        if v:
            return str(v)
    except Exception:
        pass

    v = os.environ.get("ORS_API_KEY")
    if v:
        return v

    prop_paths = ["ors.properties", "./ors.properties"]
    for path in prop_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read()
                for line in raw.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith(";"):
                        continue
                    if "=" in line and not line.startswith("["):
                        k, val = line.split("=", 1)
                        if k.strip() == "ORS_API_KEY":
                            return val.strip()
            except Exception:
                pass
    return None


# -----------------------------
# Data models
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
# Geocoding
# -----------------------------
@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def geocode_multi(address: str, country_hint: str = "US") -> Optional[Place]:
    txt = address.strip()
    # Try lat,lon input
    try:
        if "," in txt:
            lat_s, lon_s = [p.strip() for p in txt.split(",", 1)]
            lat_v, lon_v = float(lat_s), float(lon_s)
            if -90 <= lat_v <= 90 and -180 <= lon_v <= 180:
                return Place(raw=address, lat=lat_v, lon=lon_v, label=f"{lat_v:.6f}, {lon_v:.6f}")
    except Exception:
        pass

    # Provider 1: Nominatim
    nm = Nominatim(user_agent="route-app/1.0 (contact: example@example.com)")
    nm_geocode = RateLimiter(nm.geocode, min_delay_seconds=1)
    q = f"{txt}, {country_hint}" if country_hint and country_hint not in txt else txt
    try:
        res = nm_geocode(q)
        if res:
            return Place(raw=address, lat=res.latitude, lon=res.longitude, label=f"{res.address} [Nominatim]")
    except Exception:
        pass

    # Provider 2: Photon
    try:
        res = Photon(user_agent="route-app").geocode(txt)
        if res:
            return Place(raw=address, lat=res.latitude, lon=res.longitude, label=f"{res.address} [Photon]")
    except Exception:
        pass

    # Provider 3: ArcGIS
    try:
        res = ArcGIS(user_agent="route-app").geocode(txt)
        if res:
            return Place(raw=address, lat=res.latitude, lon=res.longitude, label=f"{res.address} [ArcGIS]")
    except Exception:
        pass

    return None


# -----------------------------
# OpenRouteService Directions
# -----------------------------
@st.cache_data(ttl=60 * 10, show_spinner=False)
def ors_directions(coords_latlon: List[Tuple[float, float]], api_key: str, profile: str = "driving-car") -> Dict[str, Any]:
    """Fetch route directions from OpenRouteService API."""
    try:
        if not api_key:
            return {"error": "Missing API key", "source": "fallback"}

        coords_lonlat = [[lon, lat] for (lat, lon) in coords_latlon]
        url = f"https://api.openrouteservice.org/v2/directions/{profile}?format=geojson"
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/geo+json, application/json",
        }
        payload = {
            "coordinates": coords_lonlat,
            "instructions": False,
            "geometry_simplify": True,
            "preference": "fastest",
            "units": "m",
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            return {"error": f"ORS HTTP {resp.status_code}: {resp.text[:200]}", "source": "fallback"}

        data = resp.json()

        # GeoJSON FeatureCollection (standard ORS format)
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            features = data.get("features", [])
            if not features:
                return {"error": "No features in ORS response", "source": "fallback"}
            feat = features[0]
            geom = feat.get("geometry", {}).get("coordinates", [])
            props = feat.get("properties", {}).get("summary", {})
            distance_m = float(props.get("distance", 0.0))
            duration_s = float(props.get("duration", 0.0))
            coords_latlon = [[c[1], c[0]] for c in geom]
            return {
                "distance_m": distance_m,
                "duration_s": duration_
