@st.cache_data(ttl=60*10)
def ors_directions(coords_latlon: List[Tuple[float,float]], api_key: Optional[str], profile="driving-car") -> Dict[str,Any]:
    if not api_key:
        return straight_line_fallback(coords_latlon)
    try:
        coords_lonlat = [[lon,lat] for lat,lon in coords_latlon]
        url = f"https://api.openrouteservice.org/v2/directions/{profile}?format=geojson"
        headers={"Authorization":api_key,"Content-Type":"application/json"}
        payload={"coordinates":coords_lonlat,"instructions":False,"geometry_simplify":True,"preference":"fastest","units":"m"}
        resp = requests.post(url, headers=headers, json=payload, timeout=20)

        if resp.status_code != 200:
            return straight_line_fallback(coords_latlon)

        data = resp.json()
        features = data.get("features", [])
        if not features:
            return straight_line_fallback(coords_latlon)

        geom = features[0].get("geometry", {}).get("coordinates", [])
        props = features[0].get("properties", {}).get("summary", {})
        distance_m = float(props.get("distance",0))
        duration_s = float(props.get("duration",0))
        coords_latlon_conv = [[c[1],c[0]] for c in geom]

        return {
            "distance_m": distance_m,
            "duration_s": duration_s,
            "geometry": coords_latlon_conv,
            "source": "ors"
        }

    except Exception:
        # Fallback if anything goes wrong
        return straight_line_fallback(coords_latlon)
