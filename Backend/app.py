import streamlit as st
import requests
from datetime import datetime

API_URL = "http://127.0.0.1:8000"  # FastAPI URL

# --------------------
# Page Configuration
# --------------------
st.set_page_config(page_title="Alert Dashboard", layout="wide")

# --------------------
# Session State
# --------------------
if "token" not in st.session_state:
    st.session_state.token = None
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "loading" not in st.session_state:
    st.session_state.loading = False

# --------------------
# Helper Functions
# --------------------
def logout():
    st.session_state.token = None
    st.session_state.alerts = []
    st.rerun()

def fetch_alerts(headers):
    try:
        res = requests.get(f"{API_URL}/api/dashboard/alerts/today", headers=headers, timeout=10)
        if res.status_code == 200:
            st.session_state.alerts = res.json()
            st.success("✓ Alerts fetched!")
        else:
            st.error(f"Failed to fetch alerts (Status: {res.status_code})")
    except requests.exceptions.Timeout:
        st.error("Request timeout. Server may be unavailable.")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def run_scroll(headers):
    try:
        crawl_res = requests.post(f"{API_URL}/api/crawler/crawl/linkedin/all", headers=headers, params={"day": "yesterday"}, timeout=30)
        scroll_res = requests.post(f"{API_URL}/api/crawler/scroll_companies", headers=headers, params={"day": "yesterday"}, timeout=30)
        
        if crawl_res.status_code == 200 and scroll_res.status_code == 200:
            st.success("✓ Scroll completed!")
        else:
            st.error(f"Error: Crawl ({crawl_res.status_code}), Scroll ({scroll_res.status_code})")
    except requests.exceptions.Timeout:
        st.error("Request timeout. This operation may take longer.")
    except Exception as e:
        st.error(f"Error: {str(e)}")

# --------------------
# Authentication
# --------------------
if st.session_state.token is None:
    st.title("🔐 Alert Dashboard")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.subheader("Login")
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        
        if st.button("Login", use_container_width=True, type="primary"):
            if username and password:
                try:
                    response = requests.post(f"{API_URL}/api/auth/login", data={"username": username, "password": password}, timeout=10)
                    if response.status_code == 200:
                        st.session_state.token = response.json()["access_token"]
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
                except Exception as e:
                    st.error(f"Connection error: {str(e)}")
            else:
                st.warning("Please enter username and password")
else:
    # --------------------
    # Main Dashboard
    # --------------------
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    
    # Header with logout
    col1, col2 = st.columns([0.85, 0.15])
    with col1:
        st.title("📊 Alert Dashboard")
    with col2:
        if st.button("Logout", type="secondary"):
            logout()
    
    st.divider()
    
    # --------------------
    # Action Buttons
    # --------------------
    st.subheader("Actions")
    button_col1, button_col2, button_col3 = st.columns(3)
    
    with button_col1:
        if st.button("🔄 Fetch Alerts", use_container_width=True, key="fetch_alerts"):
            fetch_alerts(headers)
    
    with button_col2:
        if st.button("📱 Run Scroll", use_container_width=True, key="run_scroll", type="primary"):
            with st.spinner("Scrolling... this may take a moment"):
                run_scroll(headers)
    
    with button_col3:
        if st.button("🗑️ Clear Alerts", use_container_width=True, key="clear_alerts"):
            st.session_state.alerts = []
            st.info("Alerts cleared")
    
    st.divider()
    
    # --------------------
    # Display Alerts
    # --------------------
    if st.session_state.alerts:
        alert_count = sum(len([a for a in company.get("alerts", []) if a.get("severity") != "low"]) for company in st.session_state.alerts)
        st.subheader(f"📢 Today's Alerts ({alert_count} total, excluding low severity)")
        
        for company in st.session_state.alerts:
            filtered_alerts = [a for a in company.get("alerts", []) if a.get("severity") != "low"]
            if not filtered_alerts:
                continue
            
            with st.expander(f"**{company.get('company_name', 'Unknown')}** — {len(filtered_alerts)} alert{'s' if len(filtered_alerts) != 1 else ''}", expanded=False):
                for idx, alert in enumerate(filtered_alerts, 1):
                    col1, col2 = st.columns([0.7, 0.3])
                    
                    with col1:
                        st.write(f"**Alert {idx}:** {alert.get('alert_message', 'N/A')}")
                        st.write(f"**Severity:** {alert.get('severity', 'Unknown').upper()}")
                    
                    with col2:
                        sentiment = alert.get('post', {}).get('sentiment_label', 'N/A')
                        sentiment_icon = "😊" if sentiment.lower() == "positive" else "😢" if sentiment.lower() == "negative" else "😐"
                        st.metric("Sentiment", f"{sentiment_icon} {sentiment}")
                    
                    st.write(f"**Post:** {alert.get('post', {}).get('post_description', 'N/A')}")
                    
                    post_data = alert.get('post', {})
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    metric_col1.metric("👍 Likes", post_data.get('likes', 0))
                    metric_col2.metric("💬 Comments", post_data.get('comments_count', 0))
                    metric_col3.metric("↗️ Shares", post_data.get('shares', 0))
                    
                    post_url = post_data.get('post_url')
                    if post_url:
                        st.markdown(f"[🔗 View Post]({post_url})")
                    
                    st.divider()
    else:
        st.info("No alerts to display. Click 'Fetch Alerts' to load alerts.")