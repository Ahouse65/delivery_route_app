import os
from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict, Any

import streamlit as st
import requests
from geopy.geocoders import Nominatim, Photon, ArcGIS
from geopy.extra.rate_limiter import RateLimiter
import folium
from streamlit_folium import st_folium
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
            return {
                "error": f"ORS HTTP {resp.status_code}: {resp.text[:200]}",
                "source": "fallback",
            }

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
                "duration_s": duration_s,
                "geometry": coords_latlon,
                "source": "ors",
            }

        return {"error": "Unknown ORS response format", "source": "fallback"}

    except Exception as e:
        return {"error": str(e), "source": "fallback"}

