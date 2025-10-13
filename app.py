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
    v = os.environ.get("ORS_API_KEY")
    if v:
        return v
    return None

# -----------------------------
# Geocoding
# -----------------------------
@st.cache_data(ttl=60*60*24)
def geocode(address: str, country_hint="US") -> Optional[Place]:
    txt = address.strip()
    try:
        if "," in txt:
            lat, lon = map(float, txt.split(",", 1))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return Place(txt, lat, lon, f"{lat:.6f}, {lon:.6f}")
    except:
        pass

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
# Straight-line fallback
# -----------------------------
def straight_line_route(seq: List[Tuple[float, float]], buffer_pct=20) -> Dict[str, Any]:
    def approx_miles(p,q):
        return (((p[0]-q[0])**2 + (p[1]-q[1])**2)**0.5)*69.0

    distance = sum(approx_miles(seq[i], seq[i+1]) for i in range(len(seq)-1))
    duration = (distance / 22.0) * 60.0 * (1 + buffer_pct/100.0)  # 22 mph avg + buffer

    return {
        "distance_m": distance * 1609.34,
        "duration_s": duration * 60.0,
        "geometry": [list(p) for p in seq],
        "source": "fallback"
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
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        payload = {"coordinates": coords, "instructions": False, "geometry_simplify": True, "preference":"fastest","units":"m"}
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
        return {"distance_m": distance, "duration_s": duration, "geometry": coords_latlon, "source": "ors"}
    except:
        return straight_line_route(seq)

# -----------------------------
# Map rendering
# -----------------------------
def render_map(p_start, p_a, p_b, r1, r2, total1_d, total1_t, total2_d, total2_t):
    pts = [p_start.coords, p_a.coords, p_b.coords]
    if r1.get("geometry"):
        pts.extend([tuple(p) for p in r1["geometry"]])
    if r2.get("geometry"):
        pts.extend([tuple(p) for p in r2["geometry"]])

    m = Map(location=p_start.coords, zoom_start=12)
    TileLayer("OpenStreetMap").add_to(m)
    Marker(p_start.coords, tooltip="Start", popup=p_start.label, icon=Icon(color="blue")).add_to(m)
    Marker(p_a.coords, tooltip="A", popup=p_a.label, icon=Icon(color="green")).add_to(m)
    Marker(p_b.coords, tooltip="B", popup=p_b.label, icon=Icon(color="red")).add_to(m)
    if r1.get("geometry"):
        PolyLine(r1["geometry"], color="blue", weight=4, opacity=0.8,
                 tooltip=f"Start→A→B | {total1_d:.2f} mi, {total1_t:.1f} min").add_to(m)
    if r2.get("geometry"):
        PolyLine(r2["geometry"], color="red", weight=4, opacity=0.5, dash_array="5,8",
                 tooltip=f"Start→B→A | {total2_d:.2f} mi, {total2_t:.1f} min").add_to(m)

    min_lat = min(p[0] for p in pts)
    max_lat = max(p[0] for p in pts)
    min_lon = min(p[1] for p in pts)
    max_lon = max(p[1] for p in pts)
    m.fit_bounds([[min_lat, min_lon],[max_lat,max_lon]])
    st_folium(m, width=None, height=540)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Delivery Route App", page_icon=":truck:", layout="wide")
st.title("Delivery Route Planner")

API_KEY = load_api_key()

with st.form("form"):
    start = st.text_input("Start location")
    a = st.text_input("Address A")
    b = st.text_input("Address B")
    buffer_pct = st.slider("ETA buffer %", 0, 100, 20)
    profile = st.selectbox("Travel mode", ["driving-car","cycling-regular","foot-walking"])
    submitted = st.form_submit_button("Route & Draw")

if submitted:
    missing = [n for n,v in [("Start",start),("A",a),("B",b)] if not v.strip()]
    if missing:
        st.error("Fill: "+", ".join(missing))
        st.stop()

    with st.spinner("Geocoding..."):
        p_start = geocode(start)
        p_a = geocode(a)
        p_b = geocode(b)

    bad = [n for n,v in [("Start",p_start),("A",p_a),("B",p_b)] if not v]
    if bad:
        st.error("Could not geocode: "+", ".join(bad))
        st.stop()

    r1 = ors_directions([p_start.coords, p_a.coords, p_b.coords], API_KEY, profile)
    r2 = ors_directions([p_start.coords, p_b.coords, p_a.coords], API_KEY, profile)

    def miles(m): return m/1609.34
    def minutes(s): return s/60
    total1_d, total1_t = miles(r1["distance_m"]), minutes(r1["duration_s"])*(1+buffer_pct/100)
    total2_d, total2_t = miles(r2["distance_m"]), minutes(r2["duration_s"])*(1+buffer_pct/100)

    st.subheader("Summary")
    c1,c2,c3 = st.columns([1,1,0.8])
    with c1:
        st.metric("Start→A→B distance", f"{total1_d:.2f} mi")
        st.metric("ETA (+buffer)", f"{total1_t:.1f} min")
    with c2:
        st.metric("Start→B→A distance", f"{total2_d:.2f} mi")
        st.metric("ETA (+buffer)", f"{total2_t:.1f} min")
    with c3:
        shorter = "A→B" if total1_t<=total2_t else "B→A"
        st.success(f"Shorter ETA: {shorter}")

    render_map(p_start,p_a,p_b,r1,r2,total1_d,total1_t,total2_d,total2_t)
