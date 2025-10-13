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
@st.cache(ttl=60 * 60 * 24)
def geocode_multi(address: str, country_hint: str = "US") -> Optional[Place]:
    txt = address.strip()
    try:
        if "," in txt:
            lat, lon = map(float, txt.split(",", 1))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return Place(raw=address, lat=lat, lon=lon, label=f"{lat:.6f}, {lon:.6f}")
    except Exception:
        pass

    q = f"{txt}, {country_hint}" if country_hint and country_hint not in txt else txt

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

    return None

# -----------------------------
# ORS Directions
# -----------------------------
@st.cache(ttl=60 * 10)
def ors_directions(coords_latlon: List[Tuple[float, float]], api_key: str, profile: str = "driving-car") -> Dict[str, Any]:
    try:
        if not api_key:
            return {"error": "Missing API key", "source": "fallback"}

        coords_lonlat = [[lon, lat] for (lat, lon) in coords_latlon]
        url = f"https://api.openrouteservice.org/v2/directions/{profile}?format=geojson"
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        payload = {"coordinates": coords_lonlat, "instructions": False, "geometry_simplify": True, "preference": "fastest", "units": "m"}

        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            return {"error": f"ORS HTTP {resp.status_code}: {resp.text[:200]}", "source": "fallback"}

        data = resp.json()
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
            return {"distance_m": distance_m, "duration_s": duration_s, "geometry": coords_latlon, "source": "ors"}

        return {"error": "Unknown ORS response format", "source": "fallback"}
    except Exception as e:
        return {"error": str(e), "source": "fallback"}

# -----------------------------
# Map rendering
# -----------------------------
def render_map_with_bounds(p_start, p_a, p_b, r1, r2, total1_d, total1_t, total2_d, total2_t):
    pts = [p_start.coords, p_a.coords, p_b.coords]
    if isinstance(r1.get("geometry"), list):
        pts.extend([tuple(p) for p in r1["geometry"]])
    if isinstance(r2.get("geometry"), list):
        pts.extend([tuple(p) for p in r2["geometry"]])

    m = folium.Map(location=p_start.coords, zoom_start=12, control_scale=True)
    folium.TileLayer("OpenStreetMap").add_to(m)

    folium.Marker(p_start.coords, tooltip="Start", popup=p_start.label, icon=folium.Icon(color="blue", icon="home")).add_to(m)
    folium.Marker(p_a.coords, tooltip="A", popup=p_a.label, icon=folium.Icon(color="green", icon="flag")).add_to(m)
    folium.Marker(p_b.coords, tooltip="B", popup=p_b.label, icon=folium.Icon(color="red", icon="flag")).add_to(m)

    if r1.get("geometry"):
        folium.PolyLine(r1["geometry"], color="blue", weight=4, opacity=0.8, tooltip=f"Start→A→B | {total1_d:.2f} mi, {total1_t:.1f} min").add_to(m)
    if r2.get("geometry"):
        folium.PolyLine(r2["geometry"], color="red", weight=4, opacity=0.5, dash_array="5,8", tooltip=f"Start→B→A | {total2_d:.2f} mi, {total2_t:.1f} min").add_to(m)

    min_lat = min(p[0] for p in pts)
    max_lat = max(p[0] for p in pts)
    min_lon = min(p[1] for p in pts)
    max_lon = max(p[1] for p in pts)
    m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

    st_folium(m, width=None, height=540)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Delivery Routes", page_icon=":truck:", layout="wide")
st.title("Delivery Route Planner — OpenRouteService")

API_KEY = load_api_key()
if not API_KEY:
    st.error("No ORS_API_KEY found. Add it in ors.properties, environment, or Streamlit secrets.")
    st.stop()

with st.form("addr_form"):
    st.subheader("Inputs")
    start = st.text_input("Start location", placeholder="123 Main St, City, State or lat,lon")
    a = st.text_input("Address A", placeholder="Address A")
    b = st.text_input("Address B", placeholder="Address B")

    col1, col2, col3 = st.columns(3)
    with col1:
        buffer_pct = st.slider("ETA buffer (%)", 0, 100, 20)
    with col2:
        country_hint = st.text_input("Country hint", value="US")
    with col3:
        profile = st.selectbox("Travel mode", ["driving-car", "cycling-regular", "foot-walking"])

    submitted = st.form_submit_button("Route & Draw", type="primary")

if submitted:
    missing = [n for n, v in [("Start", start), ("A", a), ("B", b)] if not v.strip()]
    if missing:
        st.error("Please fill: " + ", ".join(missing))
        st.stop()

    with st.spinner("Geocoding..."):
        p_start = geocode_multi(start, country_hint)
        p_a = geocode_multi(a, country_hint)
        p_b = geocode_multi(b, country_hint)

    if not p_start or not p_a or not p_b:
        bad = [n for n, v in [("Start", p_start), ("A", p_a), ("B", p_b)] if not v]
        st.error("Could not geocode: " + ", ".join(bad))
        st.stop()

    with st.spinner("Fetching ORS routes..."):
        r1 = ors_directions([p_start.coords, p_a.coords, p_b.coords], API_KEY, profile)
        r2 = ors_directions([p_start.coords, p_b.coords, p_a.coords], API_KEY, profile)

    def miles(m): return m / 1609.34
    def minutes(s): return s / 60

    total1_d, total1_t = miles(r1.get("distance_m", 0)), minutes(r1.get("duration_s", 0)) * (1 + buffer_pct/100)
    total2_d, total2_t = miles(r2.get("distance_m", 0)), minutes(r2.get("duration_s", 0)) * (1 + buffer_pct/100)

    st.subheader("Summary")
    c1, c2, c3 = st.columns([1,1,0.8])
    with c1:
        st.metric("Start → A → B distance", f"{total1_d:.2f} mi")
        st.metric("ETA (+buffer)", f"{total1_t:.1f} min")
    with c2:
        st.metric("Start → B → A distance", f"{total2_d:.2f} mi")
        st.metric("ETA (+buffer)", f"{total2_t:.1f} min")
    with c3:
        shorter = "A→B" if total1_t <= total2_t else "B→A"
        st.success(f"Shorter ETA: {shorter}")

    render_map_with_bounds(p_start, p_a, p_b, r1, r2, total1_d, total1_t, total2_d, total2_t)
