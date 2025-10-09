import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import LocateControl
from geopy.distance import geodesic

st.set_page_config(page_title="Quick Route Drawer", layout="wide")

FALLBACK_CENTER = (44.9778, -93.2650)
DEFAULT_ZOOM = 13

st.title("🗺️ Quick Route Drawer — Twin Cities (Screenshot Reference)")

# Sidebar
st.sidebar.header("⚙️ Settings")
pickup_radius_threshold = st.sidebar.number_input(
    "Pickup proximity threshold (miles)", 0.1, 10.0, 1.0
)
dropoff_detour_threshold = st.sidebar.number_input(
    "Dropoff detour threshold (miles)", 0.1, 20.0, 3.0
)
st.sidebar.markdown(
    "**How to use:**\n"
    "1. Select point to set.\n"
    "2. Click on the map to place point.\n"
    "3. Optionally, upload a screenshot for reference.\n"
    "4. Review distances and recommendation."
)

# Initialize session state
for key in ["a_pickup","a_dropoff","b_pickup","b_dropoff"]:
    if key not in st.session_state:
        st.session_state[key] = None

# Point selection
point_to_set = st.radio(
    "Select point to set",
    ("Order A → Pickup", "Order A → Dropoff", "Order B → Pickup", "Order B → Dropoff"),
    index=0, horizontal=True
)

# Columns: map and screenshot
col_map, col_screenshot = st.columns([2,1])

with col_screenshot:
    st.subheader("Screenshot Reference (optional)")
    uploaded_file = st.file_uploader("Upload route screenshot", type=["png","jpg","jpeg"])
    if uploaded_file is not None:
        st.image(uploaded_file, use_column_width=True)

# Determine map center and zoom
if st.session_state["a_pickup"]:
    # Center on Order A pickup with zoomed-in view
    map_center = st.session_state["a_pickup"]
    map_zoom = 16
elif st.session_state["a_pickup"] and st.session_state["a_dropoff"]:
    # Center on midpoint of Order A route
    lat_center = (st.session_state["a_pickup"][0] + st.session_state["a_dropoff"][0]) / 2
    lon_center = (st.session_state["a_pickup"][1] + st.session_state["a_dropoff"][1]) / 2
    map_center = (lat_center, lon_center)
    map_zoom = DEFAULT_ZOOM
else:
    map_center = FALLBACK_CENTER
    map_zoom = DEFAULT_ZOOM

with col_map:
    # Create map
    m = folium.Map(location=map_center, zoom_st

