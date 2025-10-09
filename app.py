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
    ("Order A → Pickup", "Order A → Dropoff", "Order B → Pickup", "Order B → Dropoff"),
    index=0,
    horizontal=True,
)

col1, col2 = st.columns([2, 1])

with col1:
    # Create folium map
    m = folium.Map(location=FALLBACK_CENTER, zoom_start=DEFAULT_ZOOM, control_scale=True)
    # Add locate control
    LocateControl(auto_start=False).add_to(m)

    # Draw existing markers and paths
    def add_marker_if(point, color, popup):
        if point:
            folium.Marker(location=point, icon=folium.Icon(color=color), popup=popup).add_to(m)

    add_marker_if(st.session_state["a_pickup"], "red", "A pickup")
    add_marker_if(st.session_state["a_dropoff"], "darkred", "A dropoff")
    add_marker_if(st.session_state["b_pickup"], "blue", "B pickup")
    add_marker_if(st.session_state["b_dropoff"], "darkblue", "B dropoff")

    # Draw lines if both ends are set
    if st.session_state["a_pickup"] and st.session_state["a_dropoff"]:
        folium.PolyLine(
            locations=[st.session_state["a_pickup"], st.session_state["a_dropoff"]],
            color="red", weight=5, opacity=0.8
        ).add_to(m)
    if st.session_state["b_pickup"] and st.session_state["b_dropoff"]:
        folium.PolyLine(
            locations=[st.session_state["b_pickup"], st.session_state["b_dropoff"]],
            color="blue", weight=5, opacity=0.8
        ).add_to(m)

    # Render map and get clicks
    map_data = st_folium(m, width="100%", height=650)

    # Handle clicks
    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lng = map_data["last_clicked"]["lng"]
        clicked = (lat, lng)

        if point_to_set == "Order A → Pickup":
            st.session_state["a_pickup"] = clicked
            st.success(f"Set Order A pickup at {clicked[0]:.5f}, {clicked[1]:.5f}")
        elif point_to_set == "Order A → Dropoff":
            st.session_state["a_dropoff"] = clicked
            st.success(f"Set Order A dropoff at {clicked[0]:.5f}, {clicked[1]:.5f}")
        elif point_to_set == "Order B → Pickup":
            st.session_state["b_pickup"] = clicked
            st.success(f"Set Order B pickup at {clicked[0]:.5f}, {clicked[1]:.5f}")
        elif point_to_set == "Order B → Dropoff":
            st.session_state["b_dropoff"] = clicked
            st.success(f"Set Order B dropoff at {clicked[0]:.5f}, {clicked[1]:.5f}")

with col2:
    st.subheader("Quick Controls")
    if st.button("Clear all points"):
        st.session_state["a_pickup"] = None
        st.session_state["a_dropoff"] = None
        st.session_state["b_pickup"] = None
        st.session_state["b_dropoff"] = None
        st.experimental_rerun()

    st.markdown("---")
    st.subheader("Current points")
    st.write("**Order A**")
    st.write("Pickup:", st.session_state["a_pickup"])
    st.write("Dropoff:", st.session_state["a_dropoff"])
    st.write("**Order B**")
    st.write("Pickup:", st.session_state["b_pickup"])
    st.write("Dropoff:", st.session_state["b_dropoff"])

    st.markdown("---")
    st.subheader("Analysis")

    def miles_between(p1, p2):
        try:
            return geodesic(p1, p2).miles
        except Exception:
            return None

    a_length = miles_between(st.session_state["a_pickup"], st.session_state["a_dropoff"]) if st.session_state["a_pickup"] and st.session_state["a_dropoff"] else None
    b_length = miles_between(st.session_state["b_pickup"], st.session_state["b_dropoff"]) if st.session_state["b_pickup"] and st.session_state["b_dropoff"] else None
    pickups_distance = miles_between(st.session_state["a_pickup"], st.session_state["b_pickup"]) if st.session_state["a_pickup"] and st.session_state["b_pickup"] else None
    dropoffs_distance = miles_between(st.session_state["a_dropoff"], st.session_state["b_dropoff"]) if st.session_state["a_dropoff"] and st.session_state["b_dropoff"] else None

    if a_length is not None:
        st.write(f"Order A route length: **{a_length:.2f} miles**")
    else:
        st.write("Order A route length: —")
    if b_length is not None:
        st.write(f"Order B route length: **{b_length:.2f} miles**")
    else:
        st.write("Order B route length: —")
    if pickups_distance is not None:
        st.write(f"Distance between pickups: **{pickups_distance:.2f} miles**")
    else:
        st.write("Distance between pickups: —")
    if dropoffs_distance is not None:
        st.write(f"Distance between dropoffs: **{dropoffs_distance:.2f} miles**")
    else:
        st.write("Distance between dropoffs: —")

    # Heuristic recommendation
    decision = None
    reasons = []

    if st.session_state["a_pickup"] and st.session_state["a_dropoff"] and st.session_state["b_pickup"]:
        pickup_ok = pickups_distance is not None and pickups_distance <= pickup_radius_threshold
        dropoff_ok = (dropoffs_distance is None) or (dropoffs_distance <= dropoff_detour_threshold)

        reasons.append("Pickup proximity OK" if pickup_ok else "Pickup proximity TOO FAR")
        if st.session_state["b_dropoff"]:
            reasons.append("Dropoff detour OK" if dropoff_ok else "Dropoff detour TOO FAR")
        else:
            reasons.append("No B dropoff provided (pickup-only check)")

        if pickup_ok and dropoff_ok:
            decision = "✅ Combine (good match)"
        elif pickup_ok and not dropoff_ok:
            decision = "⚠️ Maybe (pickup OK, dropoff looks far)"
        else:
            decision = "❌ Do not combine (pickup too far)"
    else:
        decision = "⚠️ Need at least Order A (pickup+dropoff) and Order B pickup to analyze."

    st.markdown("### Recommendation")
    st.write(f"**{decision}**")
    if reasons:
        st.caption(" • ".join(reasons))

st.markdown("---")
st.caption(
    "Notes: Distances are straight-line (geodesic) approximations — "
    "they give a fast heuristic. Use for quick decisions. For exact driving times, use a routing API later."
)

