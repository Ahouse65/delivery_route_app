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
    name: str
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
# Geocoding
# -----------------------------
@st.cache_data(ttl=24*60*60)
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
def straight_line_route(seq: List[Place], buffer_pct=20) -> Dict[str, Any]:
    def approx_miles(p,q):
        return (((p.lat - q.lat)**2 + (p.lon - q.lon)**2)**0.5)*69.0
    distance = sum(approx_miles(seq[i], seq[i+1]) for i in range(len(seq)-1))
    duration = (distance/22.0)*60*(1 + buffer_pct/100)
    return {"distance_m": distance*1609.34, "duration_s": duration*60, "geometry":[list(p.coords) for p in seq], "source":"fallback"}

# -----------------------------
# ORS directions
# -----------------------------
@st.cache_data(ttl=10*60)
def ors_directions(seq: List[Place], api_key: Optional[str], profile="driving-car") -> Dict[str, Any]:
    if not api_key:
        return straight_line_route(seq)
    try:
        coords = [[p.lon, p.lat] for p in seq]
        url = f"https://api.openrouteservice.org/v2/directions/{profile}?format=geojson"
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        payload = {"coordinates": coords, "instructions": False, "geometry_simplify": True, "preference": "fastest", "units": "m"}
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
        return {"distance_m": distance, "duration_s": duration, "geometry": coords_latlon, "source":"ors"}
    except:
        return straight_line_route(seq)

# -----------------------------
# Map rendering
# -----------------------------
def render_map(p_start: Place, stops: List[Place], routes: List[Dict[str,Any]]):
    pts = [p_start.coords] + [p.coords for p in stops]
    for r in routes:
        if r.get("geometry"):
            pts.extend([tuple(p) for p in r["geometry"]])

    m = Map(location=p_start.coords, zoom_start=12)
    TileLayer("OpenStreetMap").add_to(m)
    Marker(p_start.coords, tooltip="Start", popup=p_start.label, icon=Icon(color="blue")).add_to(m)

    # Pickups green, deliveries red
    for i,p in enumerate(stops):
        color = "green" if i % 2 == 0 else "red"
        Marker(p.coords, tooltip=f"Stop {i+1}", popup=p.label, icon=Icon(color=color)).add_to(m)

    colors = ["blue","red"]
    for i, r in enumerate(routes):
        if r.get("geometry"):
            PolyLine(r["geometry"], color=colors[i % 2], weight=4, opacity=0.8).add_to(m)

    min_lat = min(p[0] for p in pts)
    max_lat = max(p[0] for p in pts)
    min_lon = min(p[1] for p in pts)
    max_lon = max(p[1] for p in pts)
    m.fit_bounds([[min_lat, min_lon],[max_lat, max_lon]])
    st_folium(m, width=None, height=540)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Delivery Route Planner", page_icon=":truck:", layout="wide")
st.title("Delivery Route Planner with ORS Routing")

API_KEY = load_api_key()

with st.form("delivery_form"):
    start = st.text_input("Start address")
    pickup_a = st.text_input("Pickup A")
    delivery_a = st.text_input("Delivery A")
    pickup_b = st.text_input("Pickup B")
    delivery_b = st.text_input("Delivery B")
    buffer_pct = st.slider("ETA buffer %", 0, 100, 20)
    profile = st.selectbox("Travel mode", ["driving-car","cycling-regular","foot-walking"])
    submitted = st.form_submit_button("Compute Routes")

if submitted:
    missing = [n for n,v in [("Start", start),("Pickup A", pickup_a),("Delivery A", delivery_a),
                              ("Pickup B", pickup_b),("Delivery B", delivery_b)] if not v.strip()]
    if missing:
        st.error("Please fill: " + ", ".join(missing))
        st.stop()

    with st.spinner("Geocoding addresses..."):
        p_start = geocode(start)
        p_pickup_a = geocode(pickup_a)
        p_delivery_a = geocode(delivery_a)
        p_pickup_b = geocode(pickup_b)
        p_delivery_b = geocode(delivery_b)

    bad = [n for n,v in [("Start", p_start),("Pickup A", p_pickup_a),("Delivery A", p_delivery_a),
                          ("Pickup B", p_pickup_b), ("Delivery B", p_delivery_b)] if not v]
    if bad:
        st.error("Could not geocode: " + ", ".join(bad))
        st.stop()

    seq1 = [p_start, p_pickup_a, p_delivery_a, p_pickup_b, p_delivery_b]
    seq2 = [p_start, p_pickup_b, p_delivery_b, p_pickup_a, p_delivery_a]

    route1 = ors_directions(seq1, API_KEY, profile)
    route2 = ors_directions(seq2, API_KEY, profile)

    def miles(m): return m/1609.34
    def minutes(s): return s/60

    total1_d, total1_t = miles(route1["distance_m"]), minutes(route1["duration_s"])*(1+buffer_pct/100)
    total2_d, total2_t = miles(route2["distance_m"]), minutes(route2["duration_s"])*(1+buffer_pct/100)

    st.subheader("Route Summary")
    c1,c2,c3 = st.columns([1,1,0.8])
    with c1:
        st.metric("Route 1 distance", f"{total1_d:.2f} mi")
        st.metric("ETA (+buffer)", f"{total1_t:.1f} min")
    with c2:
        st.metric("Route 2 distance", f"{total2_d:.2f} mi")
        st.metric("ETA (+buffer)", f"{total2_t:.1f} min")
    with c3:
        shorter = "Route 1" if total1_t <= total2_t else "Route 2"
        st.success(f"Shorter ETA: {shorter}")

    stops = [p_pickup_a, p_delivery_a, p_pickup_b, p_delivery_b]
    render_map(p_start, stops, [route1, route2])
