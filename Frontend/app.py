import streamlit as st
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
# load_dotenv()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

API_URL = os.getenv("API_URL") #"http://127.0.0.1:8000"  # FastAPI URL

# --------------------
# Page Configuration
# --------------------

st.set_page_config(
    page_title="Executive Alert Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for classic, elegant styling
st.markdown("""
<style>
    /* Import professional fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main container */
    .main {
        background-color: #f8f9fa;
        padding: 2rem;
    }
    
    /* Classic header */
    .classic-header {
        background: linear-gradient(to right, #1e3a8a, #1e40af, #2563eb);
        padding: 3rem 2rem;
        border-radius: 0;
        margin: -2rem -2rem 2rem -2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .header-title {
        color: white;
        font-size: 2.8rem;
        font-weight: 300;
        letter-spacing: -0.5px;
        margin: 0;
    }
    
    .header-subtitle {
        color: #dbeafe;
        font-size: 1rem;
        font-weight: 400;
        margin-top: 0.5rem;
        letter-spacing: 0.5px;
    }
    
    /* Stats cards */
    .stat-card {
        background: white;
        padding: 1.5rem;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
        border-top: 3px solid #2563eb;
        text-align: center;
    }
    
    .stat-number {
        font-size: 2.5rem;
        font-weight: 600;
        color: #1e40af;
        margin: 0;
    }
    
    .stat-label {
        font-size: 0.875rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 0.5rem;
        font-weight: 500;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: white !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 4px !important;
        padding: 1.25rem !important;
        font-size: 1.125rem !important;
        font-weight: 600 !important;
        color: #1f2937 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12) !important;
        margin-bottom: 1rem !important;
    }
    
    .streamlit-expanderHeader:hover {
        background-color: #f9fafb !important;
        border-color: #2563eb !important;
    }
    
    .streamlit-expanderContent {
        background-color: white !important;
        border: 1px solid #e5e7eb !important;
        border-top: none !important;
        padding: 1.5rem !important;
    }
    
    .alert-item {
        padding: 1.5rem;
        background: #f9fafb;
        border-radius: 4px;
        margin-bottom: 1.5rem;
        border-left: 3px solid #94a3b8;
    }
    
    .alert-item.high {
        border-left-color: #dc2626;
        background: #fef2f2;
    }
    
    .alert-item.medium {
        border-left-color: #f59e0b;
        background: #fffbeb;
    }
    
    .alert-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 0.75rem;
    }
    
    .alert-message {
        font-size: 1rem;
        color: #4b5563;
        line-height: 1.6;
        margin-bottom: 1rem;
    }
    
    /* Severity badges */
    .badge {
        display: inline-block;
        padding: 0.375rem 0.875rem;
        border-radius: 3px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    
    .badge-high {
        background-color: #dc2626;
        color: white;
    }
    
    .badge-medium {
        background-color: #f59e0b;
        color: white;
    }
    
    .badge-low {
        background-color: #059669;
        color: white;
    }
    
    /* Post content */
    .post-content {
        background: white;
        padding: 1rem;
        border-radius: 4px;
        border: 1px solid #e5e7eb;
        margin: 1rem 0;
        font-size: 0.95rem;
        line-height: 1.6;
        color: #374151;
    }
    
    /* Metrics */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin: 1rem 0;
    }
    
    .metric-box {
        background: white;
        padding: 1rem;
        border-radius: 4px;
        border: 1px solid #e5e7eb;
        text-align: center;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 600;
        color: #2563eb;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #6b7280;
        text-transform: uppercase;
        margin-top: 0.25rem;
        letter-spacing: 0.5px;
    }
    
    /* Links */
    .view-post-link {
        display: inline-block;
        color: #2563eb;
        text-decoration: none;
        font-weight: 500;
        padding: 0.5rem 1rem;
        border: 1px solid #2563eb;
        border-radius: 4px;
        transition: all 0.2s;
        font-size: 0.875rem;
    }
    
    .view-post-link:hover {
        background: #2563eb;
        color: white;
    }
    
    /* Action buttons */
    .stButton>button {
        background: white;
        color: #1e40af;
        border: 2px solid #2563eb;
        border-radius: 4px;
        padding: 0.625rem 1.5rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: all 0.2s;
    }
    
    .stButton>button:hover {
        background: #2563eb;
        color: white;
        border-color: #1e40af;
    }
    
    /* Dividers */
    hr {
        border: none;
        border-top: 1px solid #e5e7eb;
        margin: 2rem 0;
    }
    
    /* Remove Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Timestamp */
    .timestamp {
        text-align: right;
        color: #6b7280;
        font-size: 0.875rem;
        font-style: italic;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# --------------------
# Session State
# --------------------
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "last_fetch" not in st.session_state:
    st.session_state.last_fetch = None
if "show_add_form" not in st.session_state:
    st.session_state.show_add_form = False
if "show_delete_form" not in st.session_state:
    st.session_state.show_delete_form = False
if "companies_list" not in st.session_state:
    st.session_state.companies_list = []

# --------------------
# Helper Functions
# --------------------
def fetch_alerts():
    try:
        with st.spinner("Loading alerts..."):
            res = requests.get(f"{API_URL}/api/dashboard/alerts/today", timeout=10)
            if res.status_code == 200:
                st.session_state.alerts = res.json()
                st.session_state.last_fetch = datetime.now()
                st.success("✓ Alerts loaded successfully")
            else:
                st.error(f"Failed to load alerts (Status: {res.status_code})")
    except requests.exceptions.Timeout:
        st.error("Request timeout. Please check server connection.")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def run_scroll():
    try:
        with st.spinner("Processing..."):
            crawl_res = requests.post(f"{API_URL}/api/crawler/crawl/linkedin/all", params={"day": "yesterday"}, timeout=3600)
            scroll_res = requests.post(f"{API_URL}/api/crawler/scroll_companies", params={"day": "yesterday"}, timeout=3600)
            
            if crawl_res.status_code == 200 and scroll_res.status_code == 200:
                st.success("✓ Processing completed")
            else:
                st.error(f"Error occurred during processing")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def fetch_companies_list():
    try:
        res = requests.get(f"{API_URL}/api/companies/", timeout=10)
        if res.status_code == 200:
            st.session_state.companies_list = res.json()
        else:
            st.error(f"Failed to load companies (Status: {res.status_code})")
    except Exception as e:
        st.error(f"Error fetching companies: {str(e)}")

def add_company(company_data):
    try:
        res = requests.post(f"{API_URL}/api/companies/", json=company_data, timeout=10)
        if res.status_code == 201:
            st.success(f"✓ Company '{company_data['company_name']}' added successfully!")
            st.session_state.show_add_form = False
            return True
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            st.error(f"Failed to add company: {error_detail}")
            return False
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return False

def delete_company(company_id, company_name):
    try:
        res = requests.delete(f"{API_URL}/api/companies/{company_id}", timeout=10)
        if res.status_code == 204:
            st.success(f"✓ Company '{company_name}' deleted successfully!")
            st.session_state.show_delete_form = False
            fetch_companies_list()
            return True
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            st.error(f"Failed to delete company: {error_detail}")
            return False
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return False

# --------------------
# Main Dashboard
# --------------------

# Classic Header
st.markdown("""
<div class="classic-header">
    <h1 class="header-title">Executive Alert Dashboard</h1>
    <p class="header-subtitle">Real-time LinkedIn Monitoring & Intelligence</p>
</div>
""", unsafe_allow_html=True)

# Action Bar
col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 2, 2, 2, 2, 3, 1])

with col1:
    if st.button("🔄 Refresh Alerts", use_container_width=True):
        fetch_alerts()

with col2:
    if st.button("📊 Run Process", use_container_width=True):
        run_scroll()

with col3:
    if st.button("➕ Add Company", use_container_width=True):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_delete_form = False

with col4:
    if st.button("🗑️ Delete Company", use_container_width=True):
        fetch_companies_list()
        st.session_state.show_delete_form = not st.session_state.show_delete_form
        st.session_state.show_add_form = False

with col5:
    if st.button("🧹 Clear", use_container_width=True):
        st.session_state.alerts = []
        st.session_state.last_fetch = None
        st.info("Dashboard cleared")

with col7:
    if st.session_state.last_fetch:
        st.caption(f"Updated: {st.session_state.last_fetch.strftime('%I:%M %p')}")

st.markdown("<br>", unsafe_allow_html=True)

# Add Company Form
if st.session_state.show_add_form:
    with st.expander("➕ Add New Company", expanded=True):
        with st.form("add_company_form", clear_on_submit=True):
            st.markdown("### Company Information")
            
            col1, col2 = st.columns(2)
            
            with col1:
                company_name = st.text_input("Company Name *", placeholder="e.g., Acme Corporation")
                industry = st.text_input("Industry", placeholder="e.g., Technology, Finance")
                headquarters = st.text_input("Headquarters", placeholder="e.g., San Francisco, CA")
            
            with col2:
                founded_year = st.number_input("Founded Year", min_value=1800, max_value=datetime.now().year, value=2000, step=1)
                employee_count = st.number_input("Employee Count", min_value=0, value=0, step=1)
                website = st.text_input("Website", placeholder="e.g., https://example.com")
            
            col_submit, col_cancel = st.columns([1, 5])
            
            with col_submit:
                submitted = st.form_submit_button("Add Company", use_container_width=True)
            
            with col_cancel:
                if st.form_submit_button("Cancel", use_container_width=True):
                    st.session_state.show_add_form = False
                    st.rerun()
            
            if submitted:
                # Validation
                if not company_name or company_name.strip() == "":
                    st.error("Company name is required!")
                elif website and not (website.startswith("http://") or website.startswith("https://")):
                    st.error("Website must be a valid URL (starting with http:// or https://)")
                else:
                    company_data = {
                        "company_name": company_name.strip(),
                        "industry": industry.strip() if industry else None,
                        "headquarters": headquarters.strip() if headquarters else None,
                        "founded_year": founded_year if founded_year != 2000 else None,
                        "employee_count": employee_count if employee_count > 0 else None,
                        "website": website.strip() if website else None
                    }
                    
                    if add_company(company_data):
                        st.rerun()

# Delete Company Form
if st.session_state.show_delete_form:
    with st.expander("🗑️ Delete Company", expanded=True):
        if not st.session_state.companies_list:
            st.warning("No companies found in the database.")
        else:
            st.markdown("### Select Company to Delete")
            st.warning("⚠️ Warning: This action will delete the company and all associated data (posts, alerts, logs). This cannot be undone!")
            
            # Create a dropdown with company names
            company_options = {f"{c['company_name']}": c for c in st.session_state.companies_list}
            
            selected_company_str = st.selectbox(
                "Company",
                options=list(company_options.keys()),
                help="Select the company you want to delete"
            )
            
            if selected_company_str:
                selected_company = company_options[selected_company_str]
                
                # Show company details
                st.markdown("#### Company Details")
                detail_col1, detail_col2 = st.columns(2)
                
                with detail_col1:
                    st.markdown(f"**Name:** {selected_company.get('company_name', 'N/A')}")
                    st.markdown(f"**Industry:** {selected_company.get('industry', 'N/A')}")
                    st.markdown(f"**Headquarters:** {selected_company.get('headquarters', 'N/A')}")
                
                with detail_col2:
                    st.markdown(f"**Founded:** {selected_company.get('founded_year', 'N/A')}")
                    st.markdown(f"**Employees:** {selected_company.get('employee_count', 'N/A')}")
                    st.markdown(f"**Website:** {selected_company.get('website', 'N/A')}")
                
                st.markdown("---")
                
                # Confirmation checkbox
                confirm = st.checkbox(f"I confirm that I want to delete **{selected_company['company_name']}** and all its data")
                
                col_delete, col_cancel = st.columns([1, 5])
                
                with col_delete:
                    if st.button("Delete", type="primary", disabled=not confirm, use_container_width=True):
                        if delete_company(selected_company['company_id'], selected_company['company_name']):
                            st.rerun()
                
                with col_cancel:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.show_delete_form = False
                        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# Statistics Overview
if st.session_state.alerts:
    total_companies = len(st.session_state.alerts)
    all_alerts = sum(len(company.get("alerts", [])) for company in st.session_state.alerts)
    high_alerts = sum(len([a for a in company.get("alerts", []) if a.get("severity", "").lower() == "high"]) for company in st.session_state.alerts)
    medium_alerts = sum(len([a for a in company.get("alerts", []) if a.get("severity", "").lower() == "medium"]) for company in st.session_state.alerts)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{total_companies}</div>
            <div class="stat-label">Companies</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{all_alerts}</div>
            <div class="stat-label">Total Alerts</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number" style="color: #dc2626;">{high_alerts}</div>
            <div class="stat-label">High Priority</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number" style="color: #f59e0b;">{medium_alerts}</div>
            <div class="stat-label">Medium Priority</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

# Display Alerts
if st.session_state.alerts:
    for company in st.session_state.alerts:
        filtered_alerts = [a for a in company.get("alerts", []) if a.get("severity", "").lower() != "low"]
        if not filtered_alerts:
            continue
        
        company_name = company.get('company_name', 'Unknown Company')
        
        # Use expander for company - alerts shown only when clicked
        with st.expander(f"🏢 {company_name} — {len(filtered_alerts)} Alert{'s' if len(filtered_alerts) != 1 else ''}", expanded=False):
            
            for idx, alert in enumerate(filtered_alerts, 1):
                severity = alert.get('severity', 'unknown').lower()
                
                # Alert header with severity badge
                col_title, col_badge = st.columns([4, 1])
                with col_title:
                    st.markdown(f"**Alert #{idx}:** {alert.get('alert_message', 'N/A')}")
                with col_badge:
                    if severity == 'high':
                        st.markdown('<span class="badge badge-high">HIGH</span>', unsafe_allow_html=True)
                    elif severity == 'medium':
                        st.markdown('<span class="badge badge-medium">MEDIUM</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="badge badge-low">LOW</span>', unsafe_allow_html=True)
                
                # Post content
                post_data = alert.get('post', {})
                st.markdown("**Post Content:**")
                st.info(post_data.get('post_description', 'N/A'))
                
                # Metrics
                sentiment = post_data.get('sentiment_label', 'Neutral')
                sentiment_emoji = "😊" if sentiment.lower() == "positive" else "😢" if sentiment.lower() == "negative" else "😐"
                
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                with metric_col1:
                    st.metric("👍 Likes", post_data.get('likes', 0))
                with metric_col2:
                    st.metric("💬 Comments", post_data.get('comments_count', 0))
                with metric_col3:
                    st.metric("↗️ Shares", post_data.get('shares', 0))
                with metric_col4:
                    st.metric("Sentiment", f"{sentiment_emoji} {sentiment}")
                
                # LinkedIn link
                post_url = post_data.get('post_url')
                if post_url:
                    st.markdown(f'[🔗 View on LinkedIn →]({post_url})')
                
                if idx < len(filtered_alerts):
                    st.divider()
else:
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; background: white; border-radius: 4px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);">
        <h2 style="color: #6b7280; font-weight: 300; margin-bottom: 1rem;">No Alerts Available</h2>
        <p style="color: #9ca3af; font-size: 1.125rem;">Click "Refresh Alerts" to load the latest data</p>
    </div>
    """, unsafe_allow_html=True)