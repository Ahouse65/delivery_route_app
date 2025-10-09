import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import LocateControl
from geopy.distance import geodesic

st.set_page_config(page_title="Quick Route Drawer", layout="wide")

FALLBACK_CENTER = (44.9778, -93.2650)
DEFAULT_ZOOM = 13

st.title("🗺️ Quick Route Drawer — Double-Click + Draggable Markers")

# Sidebar
st.sidebar.header("⚙️ Settings")
pickup_radius_threshold = st.sidebar.number_input(
    "Pickup proximity threshold (miles)", 0.1, 10.0, 1.0
)
dropoff_detour_threshold = st.sidebar.number_input(
    "Dropoff detour threshold (miles)", 0.1, 20.0, 3.0
)
st.sidebar.markdown(
    "**Instructions:**\n"
    "1. Select point type (pickup/dropoff A/B)\n"
    "2. Double-click on map to add marker\n"
    "3. Drag markers to adjust\n"
    "4. Click 'Update Points' to save new positions\n"
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
    map_center = st.session_state["a_pickup"]
    map_zoom = 16
elif st.session_state["a_pickup"] and st.session_state["a_dropoff"]:
    lat_center = (st.session_state["a_pickup"][0] + st.session_state["a_dropoff"][0]) / 2
    lon_center = (st.session_state["a_pickup"][1] + st.session_state["a_dropoff"][1]) / 2
    map_center = (lat_center, lon_center)
    map_zoom = DEFAULT_ZOOM
else:
    map_center = FALLBACK_CENTER
    map_zoom = DEFAULT_ZOOM

with col_map:
    # Create Folium map
    m = folium.Map(location=map_center, zoom_start=map_zoom, control_scale=True)
    LocateControl(auto_start=False).add_to(m)

    # Function to add draggable marker
    def add_draggable_marker(key, color, popup):
        point = st.session_state[key]
        if point:
            folium.Marker(
                location=point,
                icon=folium.Icon(color=color),
                popup=popup,
                draggable=True
            ).add_to(m)

    # Add existing markers
    add_draggable_marker("a_pickup", "red", "A pickup")
    add_draggable_marker("a_dropoff", "darkred", "A dropoff")
    add_draggable_marker("b_pickup", "blue", "B pickup")
    add_draggable_marker("b_dropoff", "darkblue", "B dropoff")

    # Draw lines
    if st.session_state["a_pickup"] and st.session_state["a_dropoff"]:
        folium.PolyLine([st.session_state["a_pickup"], st.session_state["a_dropoff"]],
                        color="red", weight=5, opacity=0.8).add_to(m)
    if st.session_state["b_pickup"] and st.session_state["b_dropoff"]:
        folium.PolyLine([st.session_state["b_pickup"], st.session_state["b_dropoff"]],
                        color="blue", weight=5, opacity=0.8).add_to(m)

    # Enable map lat/lon popup on double-click
    m.add_child(folium.LatLngPopup())

    map_data = st_folium(m, width="100%", height=650, returned_objects=['last_clicked'])

    # Handle last clicked as double-click simulation
    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lng = map_data["last_clicked"]["lng"]
        clicked = (lat,lng)
        if point_to_set == "Order A → Pickup":
            st.session_state["a_pickup"] = clicked
        elif point_to_set == "Order A → Dropoff":
            st.session_state["a_dropoff"] = clicked
        elif point_to_set == "Order B → Pickup":
            st.session_state["b_pickup"] = clicked
        elif point_to_set == "Order B → Dropoff":
            st.session_state["b_dropoff"] = clicked

# Quick controls
st.subheader("Controls")
if st.button("Clear all points"):
    for key in ["a_pickup","a_dropoff","b_pickup","b_dropoff"]:
        st.session_state[key] = None
    st.success("All points cleared!")
    st.stop()

# Analysis
def miles_between(p1, p2):
    try:
        return geodesic(p1, p2).miles
    except Exception:
        return None

a_len = miles_between(st.session_state["a_pickup"], st.session_state["a_dropoff"])
b_len = miles_between(st.session_state["b_pickup"], st.session_state["b_dropoff"])
pick_dist = miles_between(st.session_state["a_pickup"], st.session_state["b_pickup"])
drop_dist = miles_between(st.session_state["a_dropoff"], st.session_state["b_dropoff"])

if a_len: st.write(f"Order A route length: **{a_len:.2f} mi**")
if b_len: st.write(f"Order B route length: **{b_len:.2f} mi**")
if pick_dist: st.write(f"Distance between pickups: **{pick_dist:.2f} mi**")
if drop_dist: st.write(f"Distance between dropoffs: **{drop_dist:.2f} mi**")

decision = None
reasons = []

if st.session_state["a_pickup"] and st.session_state["a_dropoff"] and st.session_state["b_pickup"]:
    pickup_ok = pick_dist is not None and pick_dist <= pickup_radius_threshold
    dropoff_ok = (drop_dist is None) or (drop_dist <= dropoff_detour_threshold)

    reasons.append("Pickup proximity OK" if pickup_ok else "Pickup proximity TOO FAR")
    if st.session_state["b_dropoff"]:
        reasons.append("Dropoff detour OK" if dropoff_ok else "Dropoff detour TOO FAR")
    else:
        reasons.append("No B dropoff (pickup-only check)")

    if pickup_ok and dropoff_ok:
        decision = "✅ Combine (good match)"
    elif pickup_ok and not dropoff_ok:
        decision = "⚠️ Maybe (pickup OK, dropoff looks far)"
    else:
        decision = "❌ Do not combine (pickup too far)"
else:
    decision = "⚠️ Need Order A (pickup+dropoff) and Order B pickup to analyze."

st.markdown("### Recommendation")
st.write(f"**{decision}**")
if reasons:
    st.caption(" • ".join(reasons))

