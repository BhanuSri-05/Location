import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import requests
import streamlit.components.v1 as components

# Page config
st.set_page_config(page_title="Smart Multi-Language Navigator", layout="wide", page_icon="🧭")

# Custom CSS
st.markdown("""
<style>
    .main-header {font-size: 2.8rem; color: #00D4FF; text-align: center; margin: 1rem 0; text-shadow: 0 0 15px rgba(0,212,255,0.4);}
    .section-card {background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #e0e6ed; padding: 1.5rem; border-radius: 15px; border: 1px solid #00D4FF; margin-bottom: 1.5rem;}
    .direction-box {background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%); color: white; padding: 1.5rem; border-radius: 15px; text-align: center; font-size: 1.4rem; font-weight: bold; margin: 1rem 0;}
    .stButton>button {width: 100%;}
</style>
""", unsafe_allow_html=True)

# Language Dictionary
LANGUAGES = {
    "🇺🇸 English": {
        "lang_code": "en-US",
        "straight": "Go straight ahead",
        "right": "Turn right",
        "sharp_right": "Turn sharply right",
        "left": "Turn left",
        "sharp_left": "Turn sharply left",
        "done": "You have arrived at your destination!",
        "meters": "meters"
    },
    "🇮🇳 Hindi": {
        "lang_code": "hi-IN",
        "straight": "सीधे चलें",
        "right": "दाएँ मुड़ें",
        "sharp_right": "तेज दाएँ मुड़ें",
        "left": "बाएँ मुड़ें",
        "sharp_left": "तेज बाएँ मुड़ें",
        "done": "आप अपने गंतव्य पर पहुँच गए हैं!",
        "meters": "मीटर"
    },
    "🇮🇳 Telugu": {
        "lang_code": "te-IN",
        "straight": "నేరుగా వెళ్లండి",
        "right": "కుడి వైపు తిరగండి",
        "sharp_right": "తీవ్రంగా కుడి మలుపు",
        "left": "ఎడమ వైపు తిరగండి",
        "sharp_left": "తీవ్రంగా ఎడమ మలుపు",
        "done": "మీరు మీ గమ్యానికి చేరుకున్నారు!",
        "meters": "మీటర్లు"
    }
}

# Initialize session state
if 'user_location' not in st.session_state: st.session_state.user_location = None
if 'nearby_places' not in st.session_state: st.session_state.nearby_places = {}
if 'destination' not in st.session_state: st.session_state.destination = None
if 'route_steps' not in st.session_state: st.session_state.route_steps = []
if 'current_step_index' not in st.session_state: st.session_state.current_step_index = 0
if 'selected_language' not in st.session_state: st.session_state.selected_language = "🇺🇸 English"

# Haversine distance
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Calculate bearing
def get_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360

# Determine turn direction
def get_direction_text(lang, bearing_prev, bearing_next, distance):
    diff = (bearing_next - bearing_prev + 360) % 360
    lang_dict = LANGUAGES[lang]
    
    if diff < 20 or diff > 340:
        direction = lang_dict["straight"]
    elif 20 <= diff < 80:
        direction = lang_dict["right"]
    elif 80 <= diff < 160:
        direction = lang_dict["sharp_right"]
    elif 200 <= diff < 340:
        direction = lang_dict["sharp_left"]
    elif 160 <= diff <= 200:
        direction = lang_dict["left"]
    else:
        direction = lang_dict["straight"]
    
    return f"{direction} ({int(distance)} {lang_dict['meters']})"

# Fetch nearby places
def fetch_nearby_places(lat, lon, radius=600):
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"](around:{radius},{lat},{lon});
      node["shop"](around:{radius},{lat},{lon});
      node["office"](around:{radius},{lat},{lon});
    );
    out center;
    """
    try:
        response = requests.get(overpass_url, params={'data': query}, timeout=10)
        data = response.json()
        places = {}
        for elem in data.get('elements', []):
            tags = elem.get('tags', {})
            name = tags.get('name', tags.get('amenity', tags.get('shop', 'Place')))
            lat_c = elem.get('lat') or elem.get('center', {}).get('lat')
            lon_c = elem.get('lon') or elem.get('center', {}).get('lon')
            if lat_c and lon_c:
                places[name] = [float(lat_c), float(lon_c)]
        return dict(list(places.items())[:12]) if places else {"No places found": [lat+0.001, lon+0.001]}
    except:
        return {"Sample Place": [lat+0.001, lon+0.001]}

# Generate simulated route steps
def generate_route_steps(start, end, lang):
    steps = []
    total_dist = haversine(*start, *end)
    if total_dist < 15:
        return [LANGUAGES[lang]["done"]]
    
    num_steps = max(4, min(10, int(total_dist // 25)))
    waypoints = [start]
    
    for i in range(1, num_steps):
        ratio = i / num_steps
        offset = 0.00008 * math.sin(i * 1.8)
        lat = start[0] + ratio * (end[0] - start[0]) + offset
        lon = start[1] + ratio * (end[1] - start[1]) + offset * 0.6
        waypoints.append([lat, lon])
    waypoints.append(end)
    
    prev_bearing = get_bearing(*waypoints[0], *waypoints[1])
    for i in range(1, len(waypoints)-1):
        curr_bearing = get_bearing(*waypoints[i], *waypoints[i+1])
        dist = haversine(*waypoints[i-1], *waypoints[i])
        step = get_direction_text(lang, prev_bearing, curr_bearing, dist)
        steps.append(step)
        prev_bearing = curr_bearing
    
    steps.append(LANGUAGES[lang]["done"])
    return steps

# Speak full instruction
def speak_full_instruction(text, lang_code):
    escaped_text = text.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
    js = f"""
    <script>
    if ('speechSynthesis' in window) {{
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance("{escaped_text}");
        utterance.lang = '{lang_code}';
        utterance.rate = 0.95;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        window.speechSynthesis.speak(utterance);
    }}
    </script>
    """
    components.html(js, height=0)

# === AUTOMATIC LOCATION DETECTION ===
components.html("""
<script>
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        function(position) {
            Streamlit.setComponentValue({
                lat: position.coords.latitude,
                lon: position.coords.longitude
            });
        },
        function(error) {
            console.log("Location error: " + error.message);
        },
        {enableHighAccuracy: true, timeout: 15000, maximumAge: 60000}
    );
}
</script>
""", height=0)

# Capture the location from JavaScript
if hasattr(st.session_state, "_st_component_value") and st.session_state._st_component_value:
    geo = st.session_state._st_component_value
    if isinstance(geo, dict) and "lat" in geo and "lon" in geo:
        st.session_state.user_location = [geo["lat"], geo["lon"]]

# Header
st.markdown('<h1 class="main-header">🧭 Smart Multi-Language Navigator</h1>', unsafe_allow_html=True)

# Language Selection
st.markdown("### 🌐 Choose Language")
lang_cols = st.columns(3)
langs = list(LANGUAGES.keys())
for i, lang_name in enumerate(langs):
    with lang_cols[i]:
        if st.button(f"**{lang_name}**", use_container_width=True):
            st.session_state.selected_language = lang_name
            st.rerun()

st.markdown(f"**Selected:** {st.session_state.selected_language}")

# Main Layout
col_left, col_right = st.columns([1, 1.2], gap="large")

with col_left:
    st.subheader("📍 Your Location")

    if st.session_state.user_location:
        lat, lon = st.session_state.user_location
        st.success(f"✅ Location Detected Automatically\nLat: {lat:.6f} | Lon: {lon:.6f}")
    else:
        st.info("🔄 Detecting your location...\nAllow location permission when prompted (especially on mobile).")

    if st.button("🔄 Retry Location Detection"):
        st.rerun()

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("🎯 Find Nearby Places")
    
    if st.session_state.user_location:
        if st.button("🔍 Search Nearby Places"):
            with st.spinner("Searching..."):
                places = fetch_nearby_places(*st.session_state.user_location)
                st.session_state.nearby_places = places
                st.rerun()
        
        if st.session_state.nearby_places:
            selected = st.selectbox("Select Destination", [""] + list(st.session_state.nearby_places.keys()))
            if selected and st.button("🚀 Start Navigation"):
                coords = st.session_state.nearby_places[selected]
                st.session_state.destination = {"name": selected, "coords": coords}
                st.session_state.route_steps = generate_route_steps(
                    st.session_state.user_location, coords, st.session_state.selected_language
                )
                st.session_state.current_step_index = 0
                st.success(f"Route to {selected} ready!")

    st.markdown('</div>', unsafe_allow_html=True)

    # Navigation Control
    if st.session_state.route_steps and st.session_state.current_step_index < len(st.session_state.route_steps):
        st.subheader("🚶 Current Instruction")
        
        current = st.session_state.route_steps[st.session_state.current_step_index]
        st.markdown(f'<div class="direction-box">{current}</div>', unsafe_allow_html=True)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("🔊 Speak Full Instruction"):
                lang_code = LANGUAGES[st.session_state.selected_language]["lang_code"]
                speak_full_instruction(current, lang_code)
        with col_s2:
            if st.button("➡️ Next Step"):
                st.session_state.current_step_index += 1
                st.rerun()
        
        if st.button("🔄 Reset Route"):
            st.session_state.current_step_index = 0
            st.session_state.destination = None
            st.session_state.route_steps = []
            st.rerun()
        
        progress = (st.session_state.current_step_index + 1) / len(st.session_state.route_steps)
        st.progress(progress)
        st.markdown(f"**Step {st.session_state.current_step_index + 1} of {len(st.session_state.route_steps)}**")

with col_right:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("🗺️ Map View")
    
    if st.session_state.user_location:
        m = folium.Map(location=st.session_state.user_location, zoom_start=18)
        folium.Marker(
            st.session_state.user_location,
            popup="You are here",
            icon=folium.Icon(color="green", icon="user", prefix="fa")
        ).add_to(m)
        
        if st.session_state.destination:
            dest_coords = st.session_state.destination["coords"]
            folium.Marker(
                dest_coords,
                popup=st.session_state.destination["name"],
                icon=folium.Icon(color="red", icon="flag", prefix="fa")
            ).add_to(m)
            folium.PolyLine(
                [st.session_state.user_location, dest_coords],
                color="#00D4FF", weight=8, opacity=0.8
            ).add_to(m)
        
        st_folium(m, width=700, height=500)
    else:
        st.info("Set or allow location to view the map")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Final status
if st.session_state.route_steps and st.session_state.current_step_index >= len(st.session_state.route_steps):
    st.success("🎉 " + LANGUAGES[st.session_state.selected_language]["done"])

st.caption("Automatic real GPS location • Multi-language voice navigation • Works worldwide on mobile")
