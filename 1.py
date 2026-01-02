import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import requests
from streamlit_geolocation import streamlit_geolocation  # Run: py -m pip install streamlit-geolocation
import streamlit.components.v1 as components

# Page config & CSS
st.set_page_config(page_title="Smart Multi-Language GPS Navigator", layout="wide", page_icon="🧭")
st.markdown("""
<style>
    .main-header {font-size: 2.8rem; color: #00D4FF; text-align: center; margin: 1rem 0;}
    .direction-box {background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%); color: white; padding: 1.5rem; border-radius: 15px; text-align: center; font-size: 1.4rem; font-weight: bold; margin: 1rem 0;}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">🧭 Smart Multi-Language GPS Navigator</h1>', unsafe_allow_html=True)

# ==================== MULTI-LANGUAGE SUPPORT ====================
LANGUAGES = {
    "English 🇬🇧": {
        "lang_code": "en-US",
        "straight": "Go straight",
        "right": "Turn right",
        "sharp_right": "Turn sharply right",
        "left": "Turn left",
        "sharp_left": "Turn sharply left",
        "arrived": "You have arrived at your destination!",
        "meters": "meters"
    },
    "Hindi हिन्दी 🇮🇳": {
        "lang_code": "hi-IN",
        "straight": "सीधे चलें",
        "right": "दाएँ मुड़ें",
        "sharp_right": "तेज दाएँ मुड़ें",
        "left": "बाएँ मुड़ें",
        "sharp_left": "तेज बाएँ मुड़ें",
        "arrived": "आप अपने गंतव्य पर पहुँच गए हैं!",
        "meters": "मीटर"
    },
    "Telugu తెలుగు 🇮🇳": {
        "lang_code": "te-IN",
        "straight": "నేరుగా వెళ్ళండి",
        "right": "కుడి వైపు తిరగండి",
        "sharp_right": "తీవ్రంగా కుడి మలుపు",
        "left": "ఎడమ వైపు తిరగండి",
        "sharp_left": "తీవ్రంగా ఎడమ మలుపు",
        "arrived": "మీరు మీ గమ్యానికి చేరుకున్నారు!",
        "meters": "మీటర్లు"
    }
}

# Language selection at top
st.sidebar.header("🌐 Select Language")
selected_lang_name = st.sidebar.radio("Choose your language", options=list(LANGUAGES.keys()))
selected_lang = LANGUAGES[selected_lang_name]

# Session state
for key, default in {
    'user_location': None,
    'nearby_places': {},
    'destination': None,
    'route_steps': [],
    'current_step_index': 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ==================== NAVIGATION FUNCTIONS (MULTI-LANGUAGE) ====================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_bearing(lat1, lon1, lat2, lon2):
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360

def get_direction_text(prev_bearing, curr_bearing, distance, lang):
    diff = (curr_bearing - prev_bearing + 360) % 360
    if diff < 20 or diff > 340:
        direction = lang["straight"]
    elif 20 <= diff < 80:
        direction = lang["right"]
    elif 80 <= diff < 160:
        direction = lang["sharp_right"]
    elif 160 <= diff <= 200:
        direction = lang["left"]
    elif 200 <= diff < 340:
        direction = lang["sharp_left"]
    else:
        direction = lang["straight"]
    return f"{direction} ({int(distance)} {lang['meters']})"

def generate_route_steps(start, end, lang):
    steps = []
    total_dist = haversine(*start, *end)
    if total_dist < 20:
        return [lang["arrived"]]

    num_steps = max(5, min(12, int(total_dist // 40)))
    waypoints = [start]
    for i in range(1, num_steps):
        ratio = i / num_steps
        offset_lat = 0.00008 * math.sin(i * 1.5)
        offset_lon = 0.00006 * math.cos(i * 1.8)
        lat = start[0] + ratio * (end[0] - start[0]) + offset_lat
        lon = start[1] + ratio * (end[1] - start[1]) + offset_lon
        waypoints.append([lat, lon])
    waypoints.append(end)

    prev_bearing = get_bearing(*waypoints[0], *waypoints[1])
    for i in range(1, len(waypoints)-1):
        curr_bearing = get_bearing(*waypoints[i], *waypoints[i+1])
        dist = haversine(*waypoints[i-1], *waypoints[i])
        steps.append(get_direction_text(prev_bearing, curr_bearing, dist, lang))
        prev_bearing = curr_bearing
    steps.append(lang["arrived"])
    return steps

# Text-to-Speech Function
def speak_instruction(text, lang_code):
    escaped_text = text.replace('"', '\\"')
    js = f"""
    <script>
    if ('speechSynthesis' in window) {{
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance("{escaped_text}");
        utterance.lang = "{lang_code}";
        utterance.rate = 0.9;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        window.speechSynthesis.speak(utterance);
    }} else {{
        alert("Text-to-speech not supported in your browser");
    }}
    </script>
    """
    components.html(js, height=0)

# ==================== LOCATION DETECTION ====================
st.subheader("📍 Get Your Precise Current Location")

location = streamlit_geolocation()

if location and location.get("latitude") and location.get("longitude"):
    lat = location["latitude"]
    lon = location["longitude"]
    accuracy = location.get("accuracy", "Unknown")
    st.session_state.user_location = [lat, lon]
    st.success(f"✅ Precise GPS Location Detected!\nLat: {lat:.6f} | Lon: {lon:.6f}\nAccuracy: ~{accuracy}m")
else:
    st.info("👆 Click the 'Get Location' button below → Allow permission.\nBest on mobile with GPS enabled.")

if not st.session_state.user_location:
    st.info("🔄 GPS not available → using approximate IP location...")
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=10)
        data = resp.json()
        if data["status"] == "success":
            st.session_state.user_location = [data["lat"], data["lon"]]
            st.warning(f"IP Location: {data.get('city', 'Unknown')}, {data.get('regionName', '')}")
    except:
        st.error("Location failed.")

user_location = st.session_state.user_location

# ==================== NEARBY PLACES (WIDER SEARCH) ====================
if user_location:
    st.subheader("🔍 Nearby Places (within ~2km)")

    if st.button("Search Nearby Places"):
        with st.spinner("Fetching places..."):
            overpass_url = "https://overpass-api.de/api/interpreter"
            query = f"""
            [out:json][timeout:30];
            (
              node["amenity"~"restaurant|cafe|hospital|bank|school|college|fuel|pharmacy|police|post_office"](around:2000,{user_location[0]},{user_location[1]});
              node["shop"~"supermarket|convenience|clothes|bakery"](around:2000,{user_location[0]},{user_location[1]});
              node["tourism"~"hotel|attraction"](around:2000,{user_location[0]},{user_location[1]});
              node["highway"="bus_stop"](around:2000,{user_location[0]},{user_location[1]});
            );
            out center 30;
            """
            try:
                response = requests.get(overpass_url, params={'data': query}, timeout=20)
                data = response.json()
                places = {}
                for elem in data.get('elements', [])[:30]:
                    tags = elem.get('tags', {})
                    name = tags.get('name') or tags.get('amenity') or tags.get('shop') or tags.get('highway') or 'Nearby Place'
                    if name:
                        lat_c = elem.get('lat') or elem.get('center', {}).get('lat')
                        lon_c = elem.get('lon') or elem.get('center', {}).get('lon')
                        if lat_c and lon_c:
                            places[name] = [float(lat_c), float(lon_c)]
                if places:
                    st.session_state.nearby_places = places
                    st.success(f"Found {len(places)} nearby places!")
                else:
                    fallback = [user_location[0] + 0.002, user_location[1] + 0.002]
                    st.session_state.nearby_places = {"Nearby Spot": fallback}
                    st.info("No places found. Try in a bigger city.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.nearby_places:
        st.write("### 📍 Found Nearby Places:")
        for name, coords in st.session_state.nearby_places.items():
            st.write(f"**• {name}**")

        selected = st.selectbox("Select Destination", options=list(st.session_state.nearby_places.keys()))
        if st.button("🚀 Start Navigation"):
            coords = st.session_state.nearby_places[selected]
            st.session_state.destination = {"name": selected, "coords": coords}
            st.session_state.route_steps = generate_route_steps(user_location, coords, selected_lang)
            st.session_state.current_step_index = 0
            st.success(f"Navigation started to **{selected}**!")

    # ==================== STEP-BY-STEP DIRECTIONS WITH SPEECH ====================
    if st.session_state.route_steps and st.session_state.current_step_index < len(st.session_state.route_steps):
        current = st.session_state.route_steps[st.session_state.current_step_index]
        st.subheader("🚶 Current Instruction")
        st.markdown(f'<div class="direction-box">{current}</div>', unsafe_allow_html=True)

        # Speak button
        if st.button("🔊 Speak Instruction"):
            speak_instruction(current, selected_lang["lang_code"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➡️ Next Step"):
                st.session_state.current_step_index += 1
                st.rerun()
        with col2:
            if st.button("🔄 Reset Navigation"):
                st.session_state.route_steps = []
                st.session_state.destination = None
                st.session_state.current_step_index = 0
                st.rerun()

        progress = (st.session_state.current_step_index + 1) / len(st.session_state.route_steps)
        st.progress(progress)
        st.caption(f"Step {st.session_state.current_step_index + 1} of {len(st.session_state.route_steps)}")

    elif st.session_state.route_steps:
        st.success("🎉 " + selected_lang["arrived"])
        st.balloons()
        speak_instruction(selected_lang["arrived"], selected_lang["lang_code"])

    # ==================== MAP VIEW ====================
    st.subheader("🗺️ Map View")
    m = folium.Map(location=user_location, zoom_start=16)
    folium.Marker(user_location, popup="You are here", icon=folium.Icon(color="green", icon="user", prefix="fa")).add_to(m)

    if st.session_state.destination:
        dest = st.session_state.destination["coords"]
        folium.Marker(dest, popup=st.session_state.destination["name"], icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa")).add_to(m)
        folium.PolyLine([user_location, dest], color="#00D4FF", weight=8, opacity=0.8).add_to(m)

    st_folium(m, width=700, height=500)
else:
    st.info("Waiting for location...")

st.caption("Multi-Language Voice Navigation • Precise GPS • Dynamic Places • Worldwide")
