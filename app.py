import streamlit as st
from PIL import Image
import pytesseract
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Multi-App Screenshot Route Analyzer", layout="wide")
st.title("🚗 Multi-App Screenshot Route Analyzer")

st.markdown("""
Compare two delivery routes from screenshots (DoorDash, Uber Eats, Grubhub, etc.).
Each screenshot is scanned for pickup and drop-off addresses, which are geocoded and drawn on the map.
""")

geolocator = Nominatim(user_agent="route-analyzer")

def extract_addresses_from_image(image):
    """Run OCR and find likely address lines."""
    text = pytesseract.image_to_string(image)
    lines = [line.strip() for line in text.split("\n") if len(line.strip()) > 5]
    keywords = ["st", "ave", "rd", "dr", "blvd", "pl", "ct", "ln", "way", "circle"]
    addresses = [l for l in lines if any(k in l.lower() for k in keywords)]
    return text, addresses


col1, col2 = st.columns(2)
images = []
for i, c in enumerate([col1, col2]):
    uploaded = c.file_uploader(f"Upload Screenshot {i+1}", type=["png", "jpg", "jpeg"])
    if uploaded:
        img = Image.open(uploaded)
        c.image(img, caption=f"Screenshot {i+1}", use_column_width=True)
        images.append(img)
    else:
        images.append(None)

if all(images):
    st.divider()
    cols = st.columns(2)
    routes = []

    for i, (img, c) in enumerate(zip(images, cols)):
        c.subheader(f"App {i+1} OCR Results")
        text, addresses = extract_addresses_from_image(img)
        c.text_area("Extracted Text", text, height=150)
        if len(addresses) < 2:
            c.warning("⚠️ Couldn’t detect at least two address-like lines.")
            routes.append(None)
        else:
            c.write("📍 Possible addresses found:")
            for j, addr in enumerate(addresses):
                c.write(f"{j+1}. {addr}")
            pickup = c.selectbox("Pickup", options=addresses, key=f"pickup_{i}")
            dropoff = c.selectbox("Dropoff", options=addresses, index=min(1, len(addresses)-1), key=f"dropoff_{i}")
            routes.append((pickup, dropoff))

    if st.button("🗺️ Draw Combined Routes"):
        m = None
        colors = ["red", "blue"]

        for i, route in enumerate(routes):
            if route:
                p_addr, d_addr = route
                try:
                    p = geolocator.geocode(p_addr)
                    d = geolocator.geocode(d_addr)
                except Exception as e:
                    st.error(f"Geocoding failed for route {i+1}: {e}")
                    continue

                if p and d:
                    coords = [(p.latitude, p.longitude), (d.latitude, d.longitude)]
                    if not m:
                        m = folium.Map(location=coords[0], zoom_start=12)
                    folium.Marker(coords[0], popup=f"Pickup {i+1}", icon=folium.Icon(color="green")).add_to(m)
                    folium.Marker(coords[1], popup=f"Dropoff {i+1}", icon=folium.Icon(color="red")).add_to(m)
                    folium.PolyLine(coords, color=colors[i], weight=4, opacity=0.7).add_to(m)
                else:
                    st.warning(f"Couldn’t geocode both points for route {i+1}.")
        
        if m:
            st_folium(m, width=800, height=550)
        else:
            st.error("No valid routes to display.")

