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

# --- Helper: convert (lat, lon) to (lon, lat) for pydeck ---
def latlon_to_lonlat(latlon):
    return [latlon[1], latlon[0]]  # pydeck expects [lon, lat]

# --- Helper: get route points from Google Maps Directions API ---
def get_route_points(start, end):
    directions = gmaps.directions(start, end, mode="driving")
    points = []
    if directions:
        for leg in directions[0]['legs']:
            for step in leg['steps']:
                points.append((step['start_location']['lat'], step['start_location']['lng']))
            # add end location of last step
            points.append((leg['end_location']['lat'], leg['end_location']['lng']))
    return [latlon_to_lonlat(p) for p in points]

# --- Run comparison when button is pressed ---
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
            # --- Current location ---
            current_loc = None
            if enable_tracking:
                loc = streamlit_js_eval(
                    js_expressions="navigator.geolocation.getCurrentPosition((pos)=>pos.coords)", key="loc"
                )
                if loc:
                    current_loc = (loc['latitude'], loc['longitude'])

            # --- Distance checks ---
            dist_before = geodesic(locs["pickup_1"], locs["pickup_2"]).miles
            dist_after = geodesic(locs["dropoff_1"], locs["pickup_2"]).miles
            within_limits = dist_before <= max_before and dist_after <= max_after

            if within_limits:
                st.success(f"✅ Route 2 fits: {dist_before:.2f} mi before, {dist_after:.2f} mi after")
            else:
                st.warning(f"⚠️ Route 2 exceeds limits: {dist_before:.2f} mi before, {dist_after:.2f} mi after")

            # --- Route 1 completion check ---
            route1_done = False
            if enable_tracking and current_loc:
                to_drop1 = geodesic(current_loc, locs["dropoff_1"]).miles
                st.write(f"📍 Distance to Drop-off 1: {to_drop1:.2f} mi")
                if to_drop1 <= switch_threshold:
                    st.info("✅ You’re close to the first drop-off. Switching to Route 2.")
                    route1_done = True

            # --- Labels data (green P/D) ---
            labels = [
                {"position": latlon_to_lonlat(locs["pickup_1"]), "label": "P"},
                {"position": latlon_to_lonlat(locs["dropoff_1"]), "label": "D"},
                {"position": latlon_to_lonlat(locs["pickup_2"]), "label": "P"},
                {"position": latlon_to_lonlat(locs["dropoff_2"]), "label": "D"}
            ]

            if current_loc:
                labels.append({"position": latlon_to_lonlat(current_loc), "label": "You"})

            # --- Text layer ---
            text_layer = pdk.Layer(
                "TextLayer",
                data=labels,
                get_position="position",
                get_text="label",
                get_color=[0,200,0],  # bright green
                get_size=32,
                get_alignment_baseline="'center'",
                get_alignment_horizontal="'center'"
            )

            # --- Path layer (curved/accurate routing) ---
            path_layer = pdk.Layer(
                "PathLayer",
                data=[
                    {"path": get_route_points(pickup_1, dropoff_1), "color": [128,128,128] if route1_done else [0,0,255]},
                    {"path": get_route_points(pickup_2, dropoff_2), "color": [0,0,255] if route1_done else [255,0,0]}
                ],
                get_path="path",
                get_color="color",
                width_scale=10,
                width_min_pixels=5
            )

            # --- Map center & zoom ---
            all_lats = [loc[0] for loc in locs.values()]
            all_lons = [loc[1] for loc in locs.values()]
            if current_loc:
                all_lats.append(current_loc[0])
                all_lons.append(current_loc[1])

            mid_lat = (max(all_lats) + min(all_lats)) / 2
            mid_lon = (max(all_lons) + min(all_lons)) / 2
            lat_range = max(all_lats) - min(all_lats)
            lon_range = max(all_lons) - min(all_lons)
            zoom = max(1, 13 - max(lat_range, lon_range)*10)

            # --- Deck ---
            deck = pdk.Deck(
                layers=[text_layer, path_layer],
                initial_view_state=pdk.ViewState(
                    latitude=mid_lat,
                    longitude=mid_lon,
                    zoom=zoom,
                    pitch=0
                ),
                tooltip={"text": "{label}"}
            )

            st.pydeck_chart(deck)

    except Exception as e:
        st.error(f"Error: {e}")
