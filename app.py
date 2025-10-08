import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
from streamlit_js_eval import streamlit_js_eval

st.set_page_config(page_title="Smart Delivery Route Optimizer", layout="wide")
st.title("🚗 Smart Delivery Route Optimizer with Live Tracking")

API_KEY = st.secrets["API_KEY"]
gmaps = googlemaps.Client(key=API_KEY)

st.sidebar.header("🗺️ Route Inputs")
pickup_1 = st.sidebar.text_input("First Pickup Address")
dropoff_1 = st.sidebar.text_input("First Dropoff Address")
pickup_2 = st.sidebar.text_input("Second Pickup Address")
dropoff_2 = st.sidebar.text_input("Second Dropoff Address")

max_before = st.sidebar.slider("Max deviation before 1st delivery (miles)", 0.5, 10.0, 2.0)
max_after = st.sidebar.slider("Max deviation after 1st delivery (miles)", 0.5, 10.0, 2.0)
switch_threshold = st.sidebar.slider("Switch route when within (miles)", 0.1, 1.0, 0.25)
enable_tracking = st.sidebar.toggle("Enable Live Tracking", value=False)

# --- Container to hold map ---
map_container = st.container()

if st.button("Compare & Track Routes"):
    try:
        # --- Geocode all locations ---
        locs = {name: gmaps.geocode(addr)[0]['geometry']['location'] for name, addr in {
            "pickup_1": pickup_1, "dropoff_1": dropoff_1,
            "pickup_2": pickup_2, "dropoff_2": dropoff_2
        }.items()}

        # --- Get current position (if enabled) ---
        current_loc = None
        if enable_tracking:
            loc = streamlit_js_eval(js_expressions="navigator.geolocation.getCurrentPosition((pos)=>pos.coords)", key="loc")
            if loc:
                current_loc = (loc['latitude'], loc['longitude'])

        # --- Create map centered on current or first pickup ---
        center = current_loc if current_loc else (locs["pickup_1"]["lat"], locs["pickup_1"]["lng"])
        m = folium.Map(location=center, zoom_start=13)

        # --- Helper to draw routes ---
        def draw_route(start, end, color):
            directions = gmaps.directions(locs[start], locs[end], mode="driving")
            points = []
            for leg in directions[0]['legs']:
                for step in leg['steps']:
                    points.append((step['start_location']['lat'], step['start_location']['lng']))
            folium.PolyLine(points, color=color, weight=5, opacity=0.8).add_to(m)
            return directions

        # --- Compute distances ---
        dist_before = geodesic(
            (locs["pickup_1"]["lat"], locs["pickup_1"]["lng"]),
            (locs["pickup_2"]["lat"], locs["pickup_2"]["lng"])
        ).miles
        dist_after = geodesic(
            (locs["dropoff_1"]["lat"], locs["dropoff_1"]["lng"]),
            (locs["pickup_2"]["lat"], locs["pickup_2"]["lng"])
        ).miles

        # --- Determine if route 2 fits ---
        within_limits = dist_before <= max_before and dist_after <= max_after
        if within_limits:
            st.success(f"✅ Route 2 fits: {dist_before:.2f} mi before, {dist_after:.2f} mi after")
        else:
            st.warning(f"⚠️ Route 2 exceeds limits: {dist_before:.2f} mi before, {dist_after:.2f} mi after")

        # --- Determine if route 1 completed ---
        route1_done = False
        if enable_tracking and current_loc:
            to_drop1 = geodesic(current_loc, (locs["dropoff_1"]["lat"], locs["dropoff_1"]["lng"])).miles
            st.write(f"📍 Distance to Drop-off 1: {to_drop1:.2f} mi")
            if to_drop1 <= switch_threshold:
                st.info("✅ You’re close to the first drop-off. Switching to Route 2.")
                route1_done = True

        # --- Draw markers ---
        folium.Marker([locs["pickup_1"]["lat"], locs["pickup_1"]["lng"]],
                      popup="Pickup 1", icon=folium.Icon(color="gray" if route1_done else "blue")).add_to(m)
        folium.Marker([locs["dropoff_1"]["lat"], locs["dropoff_1"]["lng"]],
                      popup="Drop-off 1", icon=folium.Icon(color="gray" if route1_done else "blue")).add_to(m)
        folium.Marker([locs["pickup_2"]["lat"], locs["pickup_2"]["lng"]],
                      popup="Pickup 2", icon=folium.Icon(color="blue" if route1_done else "red")).add_to(m)
        folium.Marker([locs["dropoff_2"]["lat"], locs["dropoff_2"]["lng"]],
                      popup="Drop-off 2", icon=folium.Icon(color="blue" if route1_done else "red")).add_to(m)

        # --- Draw routes ---
        if route1_done:
            draw_route("pickup_1", "dropoff_1", "gray")
            draw_route("pickup_2", "dropoff_2", "blue")
        else:
            draw_route("pickup_1", "dropoff_1", "blue")
            draw_route("pickup_2", "dropoff_2", "red")

        # --- Mark current position ---
        if current_loc:
            folium.CircleMarker(location=current_loc, radius=6, color="green",
                                fill=True, fill_color="green", popup="You").add_to(m)

        # --- Display map in container ---
        with map_container:
            st_folium(m, width=900, height=600)

    except Exception as e:
        st.error(f"Error: {e}")

