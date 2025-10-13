import os
from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict, Any

import streamlit as st
import requests
from geopy.geocoders import Nominatim, Photon, ArcGIS
from geopy.extra.rate_limiter import RateLimiter
import folium
from streamlit_folium import st_folium


# -----------------------------
# Helpers: load API key from secrets/env/properties
# -----------------------------
def load_api_key() -> Optional[str]:
    # 1) Streamlit secrets
    try:
        v = st.secrets.get("ORS_API_KEY")
        if v:
            return str(v)
    except Exception:
        pass
    # 2) Environment variable
    v = os.environ.get("ORS_API_KEY")
    if v:
        return v
    # 3) Local properties file in current directory
    prop_paths = ["ors.properties", "./ors.properties"]
    for path in prop_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read()
                # Try simple key=value
                for line in raw.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith(";"):
                        continue
                    if "=" in line and not line.startswith("["):
                        k, val = line.split("=", 1)
                        if k.strip() == "ORS_API_KEY":
                            return val.strip()
                # Try INI style
                try:
                    import configparser
                    cp = configparser.ConfigParser()
                    cp.read(path, encoding="utf-8")
                    for sect in cp.sections():
                        if cp.has_option(sect, "ORS_API_KEY"):
                            return cp.get(sect, "ORS_API_KEY").strip()
                except Exception:
                    pass
            except Exception:
                pass
    return None


# -----------------------------
# Data models
# -----------------------------
@dataclass
class Place:
    raw: str
    lat: float
    lon: float
    label: str

    @property
    def coords(self) -> Tuple[float, float]:
        return (self.lat, self.lon)


# -----------------------------
# Geocoding (multi-provider + coordinates support)
# -----------------------------
@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def geocode_multi(address: str, country_hint: str = "US") -> Optional[Place]:
    """Try multiple providers: Nominatim -> Photon -> ArcGIS. Accepts 'lat, lon'."""
    txt = address.strip()

    # Direct coordinates input
    try:
        if "," in txt:
            lat_s, lon_s = [p.strip() for p in txt.split(",", 1)]
            lat_v, lon_v = float(lat_s), float(lon_s)
            if -90 <= lat_v <= 90 and -180 <= lon_v <= 180:
                return Place(raw=address, lat=lat_v, lon=lon_v, label=f"{lat_v:.6f}, {lon_v:.6f}")
    except Exception:
        pass

    # Provider 1: Nominatim
    nm = Nominatim(user_agent="stacker-mvp/1.0 (contact: you@example.com)")
    nm_geocode = RateLimiter(nm.geocode, min_delay_seconds=1)
    q = f"{txt}, {country_hint}" if country_hint and country_hint not in txt else txt
    try:
        res = nm_geocode(q)
        if res:
            return Place(raw=address, lat=res.latitude, lon=res.longitude, label=f"{res.address} [Nominatim]")
    except Exception:
        pass

    # Provider 2: Photon
    try:
        res = Photon(user_agent="stacker-mvp").geocode(txt)
        if res:
            return Place(raw=address, lat=res.latitude, lon=res.longitude, label=f"{res.address} [Photon]")
    except Exception:
        pass

    # Provider 3: ArcGIS
    try:
        res = ArcGIS(user_agent="stacker-mvp").geocode(txt)
        if res:
            return Place(raw=address, lat=res.latitude, lon=res.longitude, label=f"{res.address} [ArcGIS]")
    except Exception:
        pass

    return None


# -----------------------------
# OpenRouteService directions
# -----------------------------
@st.cache_data(ttl=60 * 10, show_spinner=False)
def ors_directions(coords_latlon: List[Tuple[float, float]], api_key: str, profile: str = "driving-car") -> Dict[str, Any]:
    """Call ORS for a route through the given coordinates (lat,lon).
    Supports GeoJSON FeatureCollection, classic dict geometry, or encoded polyline.
    Always returns: distance_m, duration_s, geometry (lat,lon list), source ('ors'|'fallback'), optional error."""
    try:
        if not api_key:
            return {"error": "Missing API key", "source": "fallback"}

        # ORS expects [lon, lat]
        coords_lonlat = [[lon, lat] for (lat, lon) in coords_latlon]

        url = f"https://api.openrouteservice.org/v2/directions/{profile}?format=geojson"
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/geo+json, application/json",
        }
        payload = {
            "coordinates": coords_lonlat,
            "instructions": False,
            "geometry_simplify": True,
            "preference": "fastest",
            "units": "m",
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            return {"error": f"ORS HTTP {resp.status_code}: {resp.text[:300]}", "source": "fallback"}

        try:
            data = resp.json()
        except Exception:
            return {"error": f"Non-JSON response: {resp.text[:300]}", "source": "fallback"}

        # (A) GeoJSON FeatureCollection
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            feats = data.get("features") or []
            if not feats:
                return {"error": "GeoJSON has no features", "source": "fallback"}
            feat = feats[0]
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []  # [ [lon,lat], ... ]
            props = feat.get("properties") or {}
            summary = props.get("summary") or {}
            distance_m = float(summary.get("distance", 0.0))
            duration_s = float(summary.get("duration", 0.0))
            geojson_latlon = [[c[1], c[0]] for c in coords]
            return {
                "distance_m": distance_m,
                "duration_s": duration_s,
                "geometry": geojson_latlon,
                "source": "ors",
            }

        # (B) Classic schema {"routes":[{"summary":{...},"geometry": <dict|str> }]}
        if isinstance(data, dict) and "routes" in data:
            route = (data.get("routes") or [{}])[0]
            summary = route.get("summary") or {}
            geom = route.get("geometry")
            coords_latlon: List[List[float]] = []
            if isinstance(geom, dict):
                coords = geom.get("coordinates") or []
                coords_latlon = [[c[1], c[0]] for c in coords]
            elif isinstance(geom, str):
                try:
                    import polyline as _poly
                    pts = _poly.decode(geom, precision=5)
                    if len(pts) < 2:
                        pts = _poly.decode(geom, precision=6)
                    coords_latlon = [[lat, lon] for (lat, lon) in pts]
                except Exception as _e:
                    return {"error": f"Encoded geometry but could not decode: {str(_e)[:200]}", "source": "fallback"}
            else:
                return {"error": f"Unknown geometry type: {type(geom)}", "source": "fallback"}

            distance_m = float(summary.get("distance", 0.0))
            duration_s = float(summary.get("duration", 0.0))
            return {
                "distance_m": distance_m,
                "duration_s": duration_s,
                "geometry": coords_latlon,
                "source": "ors",
            }

        return {"error": f"Unknown ORS response shape: {str(data)[:300]}", "source": "fallback"}

    except Exception as e:
        return {"error": str(e), "source": "fallback"}


# -----------------------------
# Map helper (fits bounds & draws tiles/routes)
# -----------------------------
def render_map_with_bounds(p_start, p_a, p_b, r1, r2, total1_d, total1_t, total2_d, total2_t):
    # Collect points for bounds
    pts = [p_start.coords, p_a.coords, p_b.coords]
    if isinstance(r1.get("geometry"), list):
        pts.extend([tuple(p) for p in r1["geometry"]])
    if isinstance(r2.get("geometry"), list):
        pts.extend([tuple(p) for p in r2["geometry"]])

    center = [p_start.lat, p_start.lon]
    m = folium.Map(location=center, zoom_start=13, control_scale=True, tiles=None)
    folium.TileLayer("OpenStreetMap", name="OSM").add_to(m)
    folium.TileLayer("CartoDB positron", name="Positron").add_to(m)
    folium.LayerControl(position="topright", collapsed=True).add_to(m)

    # Markers
    folium.Marker([p_start.lat, p_start.lon], tooltip="Start", popup=p_start.label,
                  icon=folium.Icon(color="blue", icon="home")).add_to(m)
    folium.Marker([p_a.lat, p_a.lon], tooltip="A", popup=p_a.label,
                  icon=folium.Icon(color="green", icon="flag")).add_to(m)
    folium.Marker([p_b.lat, p_b.lon], tooltip="B", popup=p_b.label,
                  icon=folium.Icon(color="red", icon="flag")).add_to(m)

    # Polylines
    drew_any = False
    if r1.get("geometry"):
        folium.PolyLine(
            r1["geometry"], weight=5, opacity=0.85, color="#1f77b4",
            tooltip=f"Start → A → B | {total1_d:.2f} mi, {total1_t:.1f} min"
        ).add_to(m); drew_any = True

    if r2.get("geometry"):
        folium.PolyLine(
            r2["geometry"], weight=5, opacity=0.65, dash_array="5,8", color="#d62728",
            tooltip=f"Start → B → A | {total2_d:.2f} mi, {total2_t:.1f} min"
        ).add_to(m); drew_any = True

    # Fit bounds
    if pts:
        try:
            min_lat = min(p[0] for p in pts); max_lat = max(p[0] for p in pts)
            min_lon = min(p[1] for p in pts); max_lon = max(p[1] for p in pts)
            m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])
        except Exception:
            pass

    if not drew_any:
        st.warning("No route geometry returned to draw. Toggle 'Force ORS' to inspect raw responses.")

    st.markdown("### Map (ORS)")
    st_folium(m, width=None, height=540, returned_objects=[])


# -----------------------------
# Streamlit app
# -----------------------------
st.set_page_config(page_title="Real Routes (ORS)", page_icon=":world_map:", layout="wide")
st.title("Road Routes & ETAs — OpenRouteService prototype")

with st.form("addr_form"):
    st.subheader("Inputs")
    start = st.text_input("Your current address (Start)", key="addr_start",
                          placeholder="e.g., 123 Main St, Minneapolis, MN or '44.98, -93.27'")
    a = st.text_input("Address A", key="addr_a",
                      placeholder="e.g., Chipotle, 401 Nicollet Mall, Minneapolis, MN or coords")
    b = st.text_input("Address B", key="addr_b",
                      placeholder="e.g., 50 South 6th St, Minneapolis, MN or coords")

    col1, col2, col3 = st.columns(3)
    with col1:
        buffer_pct = st.slider("ETA buffer (%)", min_value=0, max_value=100, value=20, key="cfg_buffer")
    with col2:
        country_hint = st.text_input("Country hint", value="US", key="cfg_country",
                                     help="Appends this to addresses for better geocoding.")
    with col3:
        profile = st.selectbox("Profile",
                               ["driving-car", "driving-hgv", "cycling-regular", "foot-walking"],
                               index=0, key="cfg_profile")

    # no API key input / no test button anymore
    force_ors = st.checkbox("Force ORS (no fallback)", value=False,
                            help="If ORS fails, show the error instead of straight-line fallback.")

    submitted = st.form_submit_button("Route & Draw", type="primary")

# Load key once (from secrets/env/properties)
API_KEY = load_api_key()
if not API_KEY:
    st.error("No ORS API key found. Create an 'ors.properties' file with `ORS_API_KEY=your-key`, "
             "or set ORS_API_KEY in environment or Streamlit secrets.")
    st.stop()

# Handle submission
if submitted:
    missing = [name for name, val in [("Start", start), ("Address A", a), ("Address B", b)] if not val.strip()]
    if missing:
        st.error("Please fill: " + ", ".join(missing))
    else:
        with st.spinner("Geocoding…"):
            p_start = geocode_multi(start, country_hint)
            p_a = geocode_multi(a, country_hint)
            p_b = geocode_multi(b, country_hint)

        if not p_start or not p_a or not p_b:
            bad = []
            if not p_start: bad.append("Start")
            if not p_a: bad.append("A")
            if not p_b: bad.append("B")
            st.error("Could not geocode: " + ", ".join(bad))
        else:
            with st.spinner("Fetching road routes from ORS…"):
                r1 = ors_directions([p_start.coords, p_a.coords, p_b.coords], API_KEY, profile)
                r2 = ors_directions([p_start.coords, p_b.coords, p_a.coords], API_KEY, profile)

            # If forcing ORS, surface errors and stop
            if force_ors:
                def has_schema_ok(r):
                    return r and all(k in r for k in ("distance_m", "duration_s", "geometry")) and r.get("source") == "ors"
                if not has_schema_ok(r1) or not has_schema_ok(r2):
                    st.error("ORS did not return usable routes. See raw responses below.")
                    err_text = "A→B: " + str(r1)[:800] + "\n\nB→A: " + str(r2)[:800]
                    st.code(err_text)
                    st.stop()

            # Fall back if needed or if keys are missing
            def straight_fallback(seq: List[Place]) -> Dict[str, Any]:
                def approx_miles(p, q):
                    # quick lat/lon to miles approximation
                    return (((p.lat - q.lat) ** 2 + (p.lon - q.lon) ** 2) ** 0.5) * 69.0
                d = approx_miles(seq[0], seq[1]) + approx_miles(seq[1], seq[2])
                t_min = (d / 22.0) * 60.0 * (1 + buffer_pct / 100.0)
                return {
                    "distance_m": d * 1609.34,
                    "duration_s": t_min * 60.0,
                    "geometry": [list(seq[0].coords), list(seq[1].coords), list(seq[2].coords)],
                    "source": "fallback",
                }

            def ensure_schema(route: Optional[Dict[str, Any]], seq: List[Place]) -> Dict[str, Any]:
                if not route:
                    return straight_fallback(seq)
                for k in ("distance_m", "duration_s", "geometry"):
                    if k not in route:
                        return straight_fallback(seq)
                return route

            r1 = ensure_schema(r1, [p_start, p_a, p_b])
            r2 = ensure_schema(r2, [p_start, p_b, p_a])

            st.session_state["ors_state"] = {
                "p_start": p_start,
                "p_a": p_a,
                "p_b": p_b,
                "buffer_pct": buffer_pct,
                "profile": profile,
                "r1": r1,
                "r2": r2,
            }

# Render from session state
state = st.session_state.get("ors_state")
if state:
    p_start: Place = state["p_start"]; p_a: Place = state["p_a"]; p_b: Place = state["p_b"]
    r1 = state["r1"]; r2 = state["r2"]
    buffer_pct = state["buffer_pct"]

    def miles(meters: float) -> float:
        return meters / 1609.34

    def minutes(seconds: float) -> float:
        return seconds / 60.0

    total1_d = miles(r1.get("distance_m", 0.0)) ; total1_t = minutes(r1.get("duration_s", 0.0)) * (1 + buffer_pct/100.0)
    total2_d = miles(r2.get("distance_m", 0.0)) ; total2_t = minutes(r2.get("duration_s", 0.0)) * (1 + buffer_pct/100.0)

    st.subheader("Summary (road routes)")
    c1, c2, c3 = st.columns([1, 1, 0.8])
    with c1:
        st.metric("Start → A → B distance", f"{total1_d:.2f} mi")
        st.metric("Est. time + buffer", f"{total1_t:.1f} min")
    with c2:
        st.metric("Start → B → A distance", f"{total2_d:.2f} mi")
        st.metric("Est. time + buffer", f"{total2_t:.1f} min")
    with c3:
        shorter = "A→B" if total1_t <= total2_t else "B→A"
        st.success(f"Shorter ETA (buffered): {shorter}")
        st.caption("Tip: Store ORS_API_KEY in ors.properties, env, or Streamlit secrets. For encoded geometry support, ensure `pip install polyline`.")

    # Map
    render_map_with_bounds(p_start, p_a, p_b, r1, r2, total1_d, total1_t, total2_d, total2_t)     can you help me make this app
