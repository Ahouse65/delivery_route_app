import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import LocateControl
from geopy.distance import geodesic

st.set_page_config(page_title="Quick Route Drawer", layout="wide")

# Twin Cities fallback center (Minneapolis)
FALLBACK_CENTER = (44.9778, -93.2650)
DEFAULT_ZOOM = 13

st.title("🗺️ Quick Route Drawer — Twin Cities")

# Sidebar settings
st.sidebar.header("⚙️ Settings")
pickup_radius_threshold = st.sidebar.number_input(
    "Pickup proximity threshold (miles)", min_value=0.1, max_value=10.0, value=1.0, step=0.1
)
dropoff_detour_threshold = st.sidebar.number_input(
    "Dropoff detour threshold (miles)", min_value=0.1, max_value=20.0, value=3.0, step=0.1
)
st.sidebar.markdown(
    "**How to use**\n\n"
    "1. Select which point to set in the controls below.\n"
    "2. Click on the map to place that point.\n"
    "3. Use the Locate (circle) button on the map to center on your phone's location.\n"
    "4. Review distances and recommendation."
)

# Initialize session state for points
if "a_pickup" not in st.session_state:
    st.session_state["a_pickup"] = None
if "a_dropoff" not in st.session_state:
    st.session_state["a_dropoff"] = None
if "b_pickup" not in st.session_state:
    st.session_state["b_pickup"] = None
if "b_dropoff" not in st.session_state:
    st.session_state["b_dropoff"] = None

# UI controls for which point to set
st.subheader("Select point to set (click on map to place)")
point_to_set = st.radio(
    "Point to set",
    ("Order A → Pickup", "Order

