import streamlit as st
import googlemaps
from geopy.distance import geodesic
from streamlit_js_eval import streamlit_js_eval
import pydeck as pdk

st.set_page_config(page_title="Smart Delivery Route Optimizer", layout="wide")
st.title("🚗 Smart Delivery Route Optimizer with Live Tracking (Pydeck)")

# --- Google Maps API ---
API_KEY = st.secrets["API_KEY"]
gmaps = googlemaps.Client(key=API_KEY)

# --- Sidebar inputs ---
st.sidebar.header("🗺️ Route Inputs")
pickup_1 = st.sidebar.text_input("First Pickup Address")
dropoff_1 = st.sidebar.text_input("First Dropoff Address")
pickup_2 = st.sidebar.text_input("Second Pickup Address")
dropoff_2 = st.sidebar.text_input("Second Dropoff Address")

max_before = st.sidebar.slider("Max deviation before 1st delivery (miles)", 0.5, 10.0, 2.0)
max_after = st.sidebar.slider("Max deviation after 1st delivery (miles)", 0.5, 10.0, 2.0)
switch_threshold = st.sidebar.slider("Switch route when within (miles)", 0.1, 1.0, 0.25)
enable_tracking = st.sidebar.toggle("Enable Live Tracking", value=False)

# --- Helper: geocode addresses ---
def geocode_address(addr):
    try:
        loc = gmaps.geocode(addr)[0]['geometry']['location']
        return (loc['lat'], loc['lng'])
    except:
        return None

# --- Only run comparison when button is pressed ---
if st.button("Compare & Track Routes"):
    try:
        locs = {
            "pickup_1": geocode_address(pickup_1),
            "dropoff_1": geocode_address(dropoff_1),
            "pickup_2": geocode_address(pickup_2),
            "dropoff_2": geocode_address(dropoff_2)
        }

        if None in locs.values():
            st.error("⚠️ One or more addresses could not be geocoded.")
        else:
            # --- Get current location if tracking enabled ---
            current_loc = None
            if enable_tracking:
                loc = streamlit_js_eval(js_expressions="navigator.geolocation.getCurrentPosition((pos)=>pos.coords)", key="loc")
                if loc:
                    current_loc = (loc['latitude'], loc['longitude'])

            # --- Compute distances for route 2 decision ---
            dist_before = geodesic(locs["pickup_1"], locs["pickup_2"]).miles
            dist_after = geodesic(locs["dropoff_1"], locs["pickup_2"]).miles
            within_limits = dist_before <= max_before and dist_after <= max_after

            if within_limits:
                st.success(f"✅ Route 2 fits: {dist_before:.2f} mi before, {dist_after:.2f} mi after")
            else:
                st.warning(f"⚠️ Route 2 exceeds limits: {dist_before:.2f} mi before, {dist_after:.2f} mi after")

            # --- Determine if Route 1 is done ---
            route1_done = False
            if enable_tracking and current_loc:
                to_drop1 = geodesic(current_loc, locs["dropoff_1"]).miles
                st.write(f"📍 Distance to Drop-off 1: {to_drop1:.2f} mi")
                if to_drop1 <= switch_threshold:
                    st.info("✅ You’re close to the first drop-off. Switching to Route 2.")
                    route1_done = True

            # --- Prepare pydeck layers ---
            # Markers
            markers = [
                {"position": locs["pickup_1"], "color": [0, 0, 255], "radius": 100, "name": "Pickup 1"},
                {"position": locs["dropoff_1"], "color": [0, 0, 255], "radius": 100, "name": "Dropoff 1"},
                {"position": locs["pickup_2"], "color": [255, 0, 0], "radius": 100, "name": "Pickup 2"},
                {"position": locs["dropoff_2"], "color": [255, 0, 0], "radius": 100, "name": "Dropoff 2"},
            ]
            if route1_done:
                # Gray out route1 markers
                markers[0]["color"] = [128, 128, 128]
                markers[1]["color"] = [128, 128, 128]

            # Scatterplot layer for markers
            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=markers,
                get_position="position",
                get_fill_color="color",
                get_radius="radius",
                pickable=True
            )

            def latlon_to_lonlat(latlon):
    return [latlon[1], latlon[0]]  # [lon, lat]

path_layer = pdk.Layer(
    "PathLayer",
    data=[
        {"path": [latlon_to_lonlat(locs["pickup_1"]), latlon_to_lonlat(locs["dropoff_1"])],
         "color": [128, 128, 128] if route1_done else [0, 0, 255]},
        {"path": [latlon_to_lonlat(locs["pickup_2"]), latlon_to_lonlat(locs["dropoff_2"])],
         "color": [0, 0, 255] if route1_done else [255, 0, 0]}
    ],
    get_path="path",
    get_color="color",
    width_scale=10,
    width_min_pixels=5
)

            )

            # Add current location marker
            if current_loc:
                markers.append({"position": current_loc, "color": [0, 255, 0], "radius": 100, "name": "You"})
                scatter_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=markers,
                    get_position="position",
                    get_fill_color="color",
                    get_radius="radius",
                    pickable=True
                )

            # --- Deck initialization ---
            deck = pdk.Deck(
                layers=[scatter_layer, path_layer],
                initial_view_state=pdk.ViewState(
                    latitude=locs["pickup_1"][0],
                    longitude=locs["pickup_1"][1],
                    zoom=13,
                    pitch=0
                ),
                tooltip={"text": "{name}"}
            )

            # --- Display map ---
            st.pydeck_chart(deck)

    except Exception as e:
        st.error(f"Error: {e}")


