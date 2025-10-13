import streamlit as st
from dataclasses import dataclass
from typing import Tuple, List
import folium
from streamlit_folium import st_folium

# -----------------------------
# Data model
# -----------------------------
@dataclass
class Place:
    name: str
    lat: float
    lon: float

    @property
    def coords(self) -> Tuple[float, float]:
        return (self.lat, self.lon)

# -----------------------------
# Simple distance & ETA
# -----------------------------
def straight_line_route(seq: List[Place], buffer_pct=20):
    def approx_miles(p,q):
        return (((p.lat - q.lat)**2 + (p.lon - q.lon)**2)**0.5) * 69.0
    distance = sum(approx_miles(seq[i], seq[i+1]) for i in range(len(seq)-1))
    duration = (distance / 22.0) * 60 * (1 + buffer_pct/100)  # 22 mph average
    return distance, duration

# -----------------------------
# Map rendering
# -----------------------------
def render_map(p_start: Place, stops: List[Place]):
    m = folium.Map(location=p_start.coords, zoom_start=12)
    folium.Marker(p_start.coords, tooltip="Start", icon=folium.Icon(color="blue")).add_to(m)
    colors = ["green","red","green","red"]
    for i,p in enumerate(stops):
        folium.Marker(p.coords, tooltip=p.name, icon=folium.Icon(color=colors[i])).add_to(m)
    # Draw lines
    points = [p_start.coords] + [p.coords for p in stops]
    folium.PolyLine(points, color="blue", weight=4, opacity=0.7).add_to(m)
    st_folium(m, width=None, height=500)

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("Minimal Delivery Route App")

start_name = st.text_input("Start Name", "Warehouse")
start_lat = st.number_input("Start Latitude", 44.98)
start_lon = st.number_input("Start Longitude", -93.27)

pickup_a_name = st.text_input("Pickup A Name", "Pickup A")
pickup_a_lat = st.number_input("Pickup A Latitude", 44.95)
pickup_a_lon = st.number_input("Pickup A Longitude", -93.30)

delivery_a_name = st.text_input("Delivery A Name", "Delivery A")
delivery_a_lat = st.number_input("Delivery A Latitude", 44.96)
delivery_a_lon = st.number_input("Delivery A Longitude", -93.28)

pickup_b_name = st.text_input("Pickup B Name", "Pickup B")
pickup_b_lat = st.number_input("Pickup B Latitude", 44.97)
pickup_b_lon = st.number_input("Pickup B Longitude", -93.31)

delivery_b_name = st.text_input("Delivery B Name", "Delivery B")
delivery_b_lat = st.number_input("Delivery B Latitude", 44.99)
delivery_b_lon = st.number_input("Delivery B Longitude", -93.29)

buffer_pct = st.slider("ETA buffer %", 0, 100, 20)

if st.button("Compute Route"):
    p_start = Place(start_name, start_lat, start_lon)
    stops = [
        Place(pickup_a_name, pickup_a_lat, pickup_a_lon),
        Place(delivery_a_name, delivery_a_lat, delivery_a_lon),
        Place(pickup_b_name, pickup_b_lat, pickup_b_lon),
        Place(delivery_b_name, delivery_b_lat, delivery_b_lon)
    ]
    distance, duration = straight_line_route([p_start]+stops, buffer_pct)
    st.metric("Total Distance (mi)", f"{distance:.2f}")
    st.metric("Estimated Time (+buffer, min)", f"{duration:.1f}")
    render_map(p_start, stops)

