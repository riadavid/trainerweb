import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import requests
from PIL import Image
from datetime import datetime
import folium
from streamlit_folium import st_folium
import base64

# ---------- Firebase Setup ----------
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://trainerlocatorv2-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

# ---------- Reverse Geocoding Function ----------
def get_state(lat, lon):
    try:
        api_key = st.secrets["api_ninjas"]["key"]
        url = f"https://api.api-ninjas.com/v1/reversegeocoding?lat={lat}&lon={lon}"
        response = requests.get(url, headers={"X-Api-Key": api_key})
        if response.status_code == 200:
            data = response.json()
            return data[0].get("state", "Unknown")
    except Exception as e:
        print(f"Reverse geocoding failed: {e}")
    return "Unknown"

# ---------- Streamlit Config ----------
st.set_page_config(page_title="Trainer Map", layout="wide")

# ---------- Admin Login System ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login():
    with open("image.png", "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode()

    st.markdown(f"""    
        <style>
            body {{
                background-image: url("data:image/png;base64,{encoded}");
                background-size: 200; 
                background-repeat: repeat;
                background-attachment: fixed;
            }}
            .stApp {{
                background-color: rgba(173, 216, 230, 0.6);
                padding: 2rem;
                border-radius: 10px;
                max-width: 700px;
                margin: auto;
                margin-top: 100px;
            }}
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='text-align:center;'>🔐 Admin Login</h2>", unsafe_allow_html=True)

    st.markdown('<label class="login-label">Username</label>', unsafe_allow_html=True)
    username = st.text_input("", key="username_input")

    st.markdown('<label class="login-label">Password</label>', unsafe_allow_html=True)
    password = st.text_input("", type="password", key="password_input")

    if st.button("Login"):
        if (username == st.secrets["admin"]["username"] and 
            password == st.secrets["admin"]["password"]):
            st.session_state.authenticated = True
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.error("❌ Invalid credentials.")

# ---------- Compact Header with Logo and Logout ----------
def render_header():
    col1, col2 = st.columns([6, 1])
    
    with col1:
        st.markdown(
            f"""
            <div style='display: flex; align-items: center;'>
                <img src='data:image/png;base64,{base64.b64encode(open("logo.jpg", "rb").read()).decode()}' style='height: 70px; padding-left: 20px;' />
                <h1 style='padding-left: 15px; font-size: 35px;'>📍Trainer Live Location Dashboard</h1>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        logout_button = st.button("🚪 Logout", key="custom_logout")
        if logout_button:
            st.session_state.authenticated = False
            st.rerun()

# ---------- Show Login or Dashboard ----------
if not st.session_state.authenticated:
    login()
    st.stop()
else:
    # Remove extra padding
    st.markdown("""
        <style>
            .block-container {
                padding-top: 5rem;
                padding-bottom: 1rem;
                padding-left: 0rem !important;
                padding-right: 0rem !important;
            }
        </style>
    """, unsafe_allow_html=True)
    render_header()

# ---------- Fonts & Styling ----------
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
    }

    .map-container {
        border: 2px solid #ff4b4b;
        border-radius: 10px;
        padding: 0px;
        margin-bottom: 30px;
    }
    </style>
""", unsafe_allow_html=True)

# ---------- Last Updated Timestamp ----------
st.markdown(f"<p style='text-align:right; color:gray; font-size:15px;'>Last updated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}</p>", unsafe_allow_html=True)
st.markdown("<hr style='border-top: 1px solid #bbb;'>", unsafe_allow_html=True)

# ---------- Fetch Trainer Data ----------
ref = db.reference("trainers")
data = ref.get()

if data:
    trainers = []
    for trainer_id, info in data.items():
        lat = info.get("latitude")
        lon = info.get("longitude")
        if lat and lon:
            state = get_state(lat, lon)
            trainers.append({
                "Name": info.get("name", "Unknown"),
                "Phone": trainer_id,
                "Latitude": lat,
                "Longitude": lon,
                "Timestamp": info.get("timestamp", ""),
                "State": state
            })

    df = pd.DataFrame(trainers)

    # ---------- Filter by State ----------
    st.markdown("### 🔍 Filter by State")
    states = ["All"] + sorted(df["State"].unique())
    selected_state = st.selectbox("Choose a state to view trainer locations:", states)

    if selected_state != "All":
        df_filtered = df[df["State"] == selected_state]
        center_lat = df_filtered["Latitude"].mean() if not df_filtered.empty else 20.5937
        center_lon = df_filtered["Longitude"].mean() if not df_filtered.empty else 78.9629
        zoom_level = 6
    else:
        df_filtered = df
        center_lat, center_lon = 20.5937, 78.9629
        zoom_level = 4

    # ---------- Show Map ----------
    st.markdown("### 🗺️ Trainer Locations")
    st.markdown("<div class='map-container'>", unsafe_allow_html=True)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)

    for _, row in df_filtered.iterrows():
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=f"<b>{row['Name']}</b><br>📞 {row['Phone']}<br>🕒 {row['Timestamp']}<br>📍 {row['State']}",
            icon=folium.Icon(color='darkblue', icon='map-marker', prefix='fa')
        ).add_to(m)

    st_data = st_folium(m, width="100%", height=500)
    st.markdown("</div>", unsafe_allow_html=True)

    # ---------- Show Table ----------
    with st.expander("📋 Trainer Details Table", expanded=True):
        st.dataframe(df_filtered.style.set_properties(**{
            'background-color': '#ffffff',
            'color': '#1d1d1d',
            'border-color': '#ff4b4b'
        }))
else:
    st.warning("⚠️ No trainer location data found yet.")
