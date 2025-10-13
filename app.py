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
# ORS API key
# -----------------------------
def load_api_key() -> Optional[str]:
    try:
        return str(st.secrets.get("ORS_API_KEY"))
    except:
        return os.environ.get("ORS_API_KEY")

API_KEY = load_api_key()
if not API_KEY:
    st.error("No ORS_API_KEY found! Add it to Streamlit secrets or environment variables.")
    st.stop()

# -----------------------------
# Geocoding
# -----------------------------
@st.cache_data(ttl=24*60*60)
def geocode(address: str, country_hint="US") -> Optional[Place]:
    txt = address.strip()
    if not txt:
        return None
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
# ORS routing
# -----------------------------
@st.cache_data(ttl=10*60)
def ors_directions(seq: List[Place], api_key: str, profile="driving-car") -> Dict[str, Any]:
    try:
        coords = [[p.lon, p.lat] for p in seq]
        url = f"https://api.openrouteservice.org/v2/directions/{profile}?format=geojson"
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        payload = {
            "coordinates": coords,
            "instructions": False,
            "geometry_simplify": True,
            "preference": "fastest",
            "units": "m"
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            return {"error": f"ORS HTTP {resp.status_code}", "source":"fallback"}
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return {"error":"No features in ORS response", "source":"fallback"}
        geom = features[0].get("geometry", {}).get("coordinates", [])
        props = features[0].get("properties", {}).get("summary", {})
        distance = float(props.get("distance", 0))
        duration = float(props.get("duration", 0))
        coords_latlon = [[c[1], c[0]] for c in geom]
        return {"distance_m": distance, "duration_s": duration, "geometry": coords_latlon, "source":"ors"}
    except Exception as e:
        return {"error": str(e), "source":"fallback"}

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

    for i,p in enumerate(stops):
        color = "green" if i % 2 == 0 else "red"
        Marker(p.coords, tooltip=f"Stop {i+1}", popup=p.label, icon=Icon(color=color)).add_to(m)

    route_colors = ["blue", "red"]
    for i, r in enumerate(routes):
        if r.get("geometry"):
            PolyLine(
                r["geometry"],
                color=route_colors[i % len(route_colors)],
                weight=5,
                opacity=0.8,
                dash_array="5,5" if i > 0 else None
            ).add_to(m)

    min_lat = min(p[0] for p in pts)
    max_lat = max(p[0] for p in pts)
    min_lon = min(p[1] for p in pts)
    max_lon = max(p[1] for p in pts)
    m.fit_bounds([[min_lat, min_lon],[max_lat, max_lon]])
    st_folium(m, width=None, height=540)

# -----------------------------
# Streamlit layout
# -----------------------------
st.set_page_config(page_title="Delivery Route Planner", page_icon=":truck:", layout="wide")
st.title("Delivery Route Planner")

with st.sidebar.form("inputs"):
    st.header("Addresses")
    start = st.text_input("Start address", value=st.session_state.get("start",""))
    pickup_a = st.text_input("Pickup A", value=st.session_state.get("pickup_a",""))
    delivery_a = st.text_input("Delivery A", value=st.session_state.get("delivery_a",""))
    pickup_b = st.text_input("Pickup B", value=st.session_state.get("pickup_b",""))
    delivery_b = st.text_input("Delivery B", value=st.session_state.get("delivery_b",""))
    st.header("Settings")
    buffer_pct = st.slider("ETA buffer %", 0, 100, st.session_state.get("buffer_pct",20))
    profile = st.selectbox("Travel mode", ["driving-car","cycling-regular","foot-walking"], index=0)
    submitted = st.form_submit_button("Compute Routes")

if submitted:
    st.session_state.update({
        "start": start, "pickup_a": pickup_a, "delivery_a": delivery_a,
        "pickup_b": pickup_b, "delivery_b": delivery_b, "buffer_pct": buffer_pct
    })

    addresses = [("Start", start), ("Pickup A", pickup_a), ("Delivery A", delivery_a),
                 ("Pickup B", pickup_b), ("Delivery B", delivery_b)]

    geocoded = {}
    for name, addr in addresses:
        p = geocode(addr)
        if not p:
            st.error(f"Could not geocode {name}. Please enter a valid address.")
            st.stop()
        geocoded[name] = p

    seq1 = [geocoded["Start"], geocoded["Pickup A"], geocoded["Delivery A"],
            geocoded["Pickup B"], geocoded["Delivery B"]]
    seq2 = [geocoded["Start"], geocoded["Pickup B"], geocoded["Delivery B"],
            geocoded["Pickup A"], geocoded["Delivery A"]]

    route1 = ors_directions(seq1, API_KEY, profile)
    route2 = ors_directions(seq2, API_KEY, profile)

    st.session_state["routes"] = {
        "p_start": geocoded["Start"],
        "stops": [geocoded["Pickup A"], geocoded["Delivery A"],
                  geocoded["Pickup B"], geocoded["Delivery B"]],
        "route1": route1,
        "route2": route2,
        "buffer_pct": buffer_pct
    }

# -----------------------------
# Display routes and summary
# -----------------------------
if "routes" in st.session_state:
    rstate = st.session_state["routes"]
    route1, route2 = rstate["route1"], rstate["route2"]
    buffer_pct = rstate["buffer_pct"]
    p_start, stops = rstate["p_start"], rstate["stops"]

    # Handle ORS errors
    if route1.get("source") != "ors":
        st.error(f"Route 1 error: {route1.get('error','Unknown error')}")
    if route2.get("source") != "ors":
        st.error(f"Route 2 error: {route2.get('error','Unknown error')}")

    # Only compute summary if routes succeeded
    if "distance_m" in route1 and "distance_m" in route2:
        def miles(m): return m/1609.34
        def minutes(s): return s/60

        total1_d = miles(route1["distance_m"])
        total1_t = minutes(route1["duration_s"]) * (1 + buffer_pct/100)
        total2_d = miles(route2["distance_m"])
        total2_t = minutes(route2["duration_s"]) * (1 + buffer_pct/100)

        st.subheader("Route Summary")
        c1, c2, c3 = st.columns([1,1,0.8])
        with c1:
            st.metric("Route 1 distance", f"{total1_d:.2f} mi")
            st.metric("ETA (+buffer)", f"{total1
