import streamlit as st
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import json

load_dotenv()
# load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

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
    
    /* Market Intelligence Styles */
    .intelligence-header {
        background: linear-gradient(to right, #7c3aed, #8b5cf6, #a78bfa);
        padding: 2rem;
        border-radius: 8px;
        margin: 2rem 0 1.5rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .intelligence-title {
        color: white;
        font-size: 2rem;
        font-weight: 400;
        letter-spacing: -0.5px;
        margin: 0;
    }
    
    .intelligence-subtitle {
        color: #e9d5ff;
        font-size: 0.9rem;
        font-weight: 400;
        margin-top: 0.5rem;
        letter-spacing: 0.3px;
    }
    
    .company-card {
        background: white;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
        border: 1px solid #e5e7eb;
        transition: all 0.2s;
        cursor: pointer;
        height: 100%;
    }
    
    .company-card:hover {
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.15);
        border-color: #8b5cf6;
        transform: translateY(-2px);
    }
    
    .company-card-name {
        font-size: 1.25rem;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 0.75rem;
    }
    
    .company-card-stats {
        display: flex;
        gap: 1rem;
        margin: 0.75rem 0;
        font-size: 0.85rem;
        color: #6b7280;
    }
    
    .company-card-date {
        font-size: 0.8rem;
        color: #9ca3af;
        margin-top: 0.5rem;
    }
    
    .tech-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
        margin: 0.25rem;
        background: #f3e8ff;
        color: #7c3aed;
    }
    
    .analysis-section {
        background: #fafafa;
        padding: 1.25rem;
        border-radius: 6px;
        margin: 1rem 0;
        border-left: 3px solid #8b5cf6;
    }
    
    .analysis-section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #7c3aed;
        margin-bottom: 0.75rem;
    }
    
    .product-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
        background: white;
        border-radius: 4px;
        overflow: hidden;
    }
    
    .product-table th {
        background: #f9fafb;
        padding: 0.75rem;
        text-align: left;
        font-weight: 600;
        color: #374151;
        border-bottom: 2px solid #e5e7eb;
    }
    
    .product-table td {
        padding: 0.75rem;
        border-bottom: 1px solid #f3f4f6;
        color: #4b5563;
    }
    
    .strategic-prediction {
        background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
        padding: 1.5rem;
        border-radius: 8px;
        border: 2px solid #e9d5ff;
        margin: 1.5rem 0;
    }
    
    .strategic-prediction-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #6b21a8;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
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
if "show_intelligence" not in st.session_state:
    st.session_state.show_intelligence = False
if "intelligence_data" not in st.session_state:
    st.session_state.intelligence_data = []
if "selected_company_analysis" not in st.session_state:
    st.session_state.selected_company_analysis = None

# --------------------
# Helper Functions
# --------------------

def fetch_alerts(start_date=None, end_date=None):
    try:
        with st.spinner("Loading alerts..."):
            if not start_date:
                start_date = datetime.now().date()
            if not end_date:
                end_date = start_date

            url = f"{API_URL}/api/dashboard/alerts/by-date"
            params = {"start_date": start_date, "end_date": end_date}

            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                st.session_state.alerts = res.json()
                st.session_state.last_fetch = datetime.now()
                st.success(f"✓ Alerts from {start_date} to {end_date} loaded successfully")
            else:
                st.error(f"Failed to load alerts (Status: {res.status_code})")
    except requests.exceptions.Timeout:
        st.error("Request timeout. Please check server connection.")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def run_scroll(start_date=None, end_date=None):
    try:
        with st.spinner("Processing..."):
            crawl_res = requests.post(url = f"{API_URL}/api/crawler/crawl/linkedin/all", 
                                      params = {"start_date": start_date, "end_date": end_date}, 
                                      timeout=3600)
            scroll_res = requests.post(url = f"{API_URL}/api/crawler/scroll_companies", 
                                       params = {"start_date": start_date, "end_date": end_date}, 
                                       timeout=3600)
            
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

def fetch_intelligence_data():
    try:
        with st.spinner("Loading market intelligence..."):
            res = requests.get(f"{API_URL}/api/crawler/firecrawl-insights", timeout=30)
            if res.status_code == 200:
                st.session_state.intelligence_data = res.json()
                st.success("✓ Market intelligence loaded successfully")
            else:
                st.error(f"Failed to load intelligence data (Status: {res.status_code})")
    except requests.exceptions.Timeout:
        st.error("Request timeout. Please check server connection.")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def parse_json_field(json_str):
    """Safely parse JSON string fields"""
    try:
        return json.loads(json_str)
    except:
        return {}

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

from datetime import date

# Default to today
today = date.today()

col_date1, col_date2 = st.columns([2, 2])
with col_date1:
    start_date = st.date_input("Start Date", today)
with col_date2:
    end_date = st.date_input("End Date", today)

# Action Bar
col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 2, 2, 2, 2, 2, 2, 1])

with col1:
    if st.button("🔄 Refresh Alerts", use_container_width=True):
        fetch_alerts(start_date, end_date)

with col2:
    if st.button("📊 Run Process", use_container_width=True):
        run_scroll(start_date, end_date)

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
    if st.button("📈 Market Intel", use_container_width=True):
        if not st.session_state.show_intelligence:
            fetch_intelligence_data()
        st.session_state.show_intelligence = not st.session_state.show_intelligence
        st.session_state.selected_company_analysis = None

with col6:
    if st.button("🧹 Clear", use_container_width=True):
        st.session_state.alerts = []
        st.session_state.last_fetch = None
        st.info("Dashboard cleared")

with col8:
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
            
            company_options = {f"{c['company_name']}": c for c in st.session_state.companies_list}
            
            selected_company_str = st.selectbox(
                "Company",
                options=list(company_options.keys()),
                help="Select the company you want to delete"
            )
            
            if selected_company_str:
                selected_company = company_options[selected_company_str]
                
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
        
        with st.expander(f"🏢 {company_name} — {len(filtered_alerts)} Alert{'s' if len(filtered_alerts) != 1 else ''}", expanded=False):
            
            for idx, alert in enumerate(filtered_alerts, 1):
                severity = alert.get('severity', 'unknown').lower()
                
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
                
                post_data = alert.get('post', {})
                st.markdown("**Post Content:**")
                st.info(post_data.get('post_description', 'N/A'))
                
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
                
                post_url = post_data.get('post_url')
                if post_url:
                    st.markdown(f'[🔗 View on LinkedIn ↗]({post_url})')
                
                if idx < len(filtered_alerts):
                    st.divider()
else:
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; background: white; border-radius: 4px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);">
        <h2 style="color: #6b7280; font-weight: 300; margin-bottom: 1rem;">No Alerts Available</h2>
        <p style="color: #9ca3af; font-size: 1.125rem;">Click "Refresh Alerts" to load the latest data</p>
    </div>
    """, unsafe_allow_html=True)

# --------------------
# Market Intelligence Section
# --------------------

if st.session_state.show_intelligence:
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Intelligence Header
    st.markdown("""
    <div class="intelligence-header">
        <h2 class="intelligence-title">📈 Competitive Market Intelligence</h2>
        <p class="intelligence-subtitle">Strategic insights and competitor analysis • Updated weekly</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Back to company list button if viewing specific company
    if st.session_state.selected_company_analysis:
        if st.button("← Back to Company List", use_container_width=False):
            st.session_state.selected_company_analysis = None
            st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
    
    # Show company grid or detailed analysis
    if not st.session_state.selected_company_analysis:
        # Company Grid View
        if not st.session_state.intelligence_data:
            st.markdown("""
            <div style="text-align: center; padding: 4rem 2rem; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);">
                <h3 style="color: #6b7280; font-weight: 300;">No Intelligence Data Available</h3>
                <p style="color: #9ca3af; font-size: 1rem;">Market intelligence will be updated weekly</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"**{len(st.session_state.intelligence_data)} Companies Analyzed**")
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Display companies in grid (3 columns)
            cols_per_row = 3
            for i in range(0, len(st.session_state.intelligence_data), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    idx = i + j
                    if idx < len(st.session_state.intelligence_data):
                        company_intel = st.session_state.intelligence_data[idx]
                        
                        with cols[j]:
                            # Parse JSON fields
                            raw_data = parse_json_field(company_intel.get('raw_data', '{}'))
                            products = raw_data.get('products', {})
                            tech_stack = raw_data.get('tech_stack', [])
                            
                            # Company card
                            card_html = f"""
                            <div class="company-card">
                                <div class="company-card-name">🏢 {company_intel.get('company_name', 'Unknown')}</div>
                                <div class="company-card-stats">
                                    <span>📦 {len(products)} Products</span>
                                    <span>⚙️ {len(tech_stack)} Tech</span>
                                </div>
                            """
                            
                            # Tech badges (show first 3)
                            if tech_stack:
                                card_html += '<div style="margin-top: 0.75rem;">'
                                for tech in tech_stack[:3]:
                                    card_html += f'<span class="tech-badge">{tech}</span>'
                                if len(tech_stack) > 3:
                                    card_html += f'<span class="tech-badge">+{len(tech_stack) - 3} more</span>'
                                card_html += '</div>'
                            
                            # Analysis date
                            created_date = company_intel.get('created_at', '')
                            if created_date:
                                try:
                                    date_obj = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                                    formatted_date = date_obj.strftime('%b %d, %Y')
                                    card_html += f'<div class="company-card-date">Last analyzed: {formatted_date}</div>'
                                except:
                                    pass
                            
                            card_html += '</div>'
                            
                            st.markdown(card_html, unsafe_allow_html=True)
                            
                            # Click button to view details
                            if st.button(f"View Analysis", key=f"view_{company_intel.get('id')}", use_container_width=True):
                                st.session_state.selected_company_analysis = company_intel
                                st.rerun()
    
    else:
        # Detailed Company Analysis View
        company_intel = st.session_state.selected_company_analysis
        
        # Parse JSON data
        raw_data = parse_json_field(company_intel.get('raw_data', '{}'))
        analysis_data = parse_json_field(company_intel.get('analysis_json', '{}'))
        
        # Company Header
        st.markdown(f"## 🏢 {company_intel.get('company_name', 'Unknown Company')}")
        
        col_web, col_date = st.columns([3, 1])
        with col_web:
            website = company_intel.get('website_url', '')
            if website:
                st.markdown(f"🌐 [{website}]({website})")
        with col_date:
            created_date = company_intel.get('created_at', '')
            if created_date:
                try:
                    date_obj = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                    st.caption(f"Analyzed: {date_obj.strftime('%b %d, %Y')}")
                except:
                    pass
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Quick Overview Cards
        products = raw_data.get('products', {})
        tech_stack = raw_data.get('tech_stack', [])
        key_features = raw_data.get('key_features', [])
        
        overview_col1, overview_col2, overview_col3, overview_col4 = st.columns(4)
        with overview_col1:
            st.metric("📦 Products", len(products))
        with overview_col2:
            st.metric("⚙️ Technologies", len(tech_stack))
        with overview_col3:
            st.metric("✨ Key Features", len(key_features))
        with overview_col4:
            marketing_focus = raw_data.get('marketing_focus', 'N/A')
            st.metric("🎯 Target", marketing_focus) #if len(str(marketing_focus)) < 15 else str(marketing_focus)[:] + "...")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Strategic Prediction (Highlighted)
        predicted_direction = analysis_data.get('predicted_strategic_direction', '')
        if predicted_direction:
            st.markdown(f"""
            <div class="strategic-prediction">
                <div class="strategic-prediction-title">
                    🎯 Predicted Strategic Direction
                </div>
                <p style="color: #4c1d95; line-height: 1.7; margin: 0;">{predicted_direction}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs(["📦 Products & Services", "⚙️ Technology & Features", "📊 Strategic Insights", "🔍 Raw Data"])
        
        import pandas as pd

        with tab1:
            st.markdown("### Products & Services Portfolio")
            
            if products:
                products_list = []
                for key, product in products.items():
                    products_list.append({
                        'Product Name': product.get('name', 'N/A'),
                        'Price': product.get('price', 'Not specified'),
                        'Description': product.get('description', 'N/A')
                    })
                
                df = pd.DataFrame(products_list)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No product information available")

        with tab2:
            st.markdown("### Technology Stack & Key Features")
            
            col_tech, col_features = st.columns(2)
            
            with col_tech:
                st.markdown("#### 🔧 Technology Stack")
                if tech_stack:
                    for tech in tech_stack:
                        st.markdown(f'<span class="tech-badge">{tech}</span>', unsafe_allow_html=True)
                else:
                    st.info("No technology stack information available")
            
            with col_features:
                st.markdown("#### ✨ Key Features")
                if key_features:
                    for feature in key_features:
                        st.markdown(f"• {feature}")
                else:
                    st.info("No key features information available")
            
            # Marketing Focus
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### 🎯 Marketing Focus")
            marketing_focus = raw_data.get('marketing_focus', 'Not specified')
            st.markdown(f"""
            <div class="analysis-section">
                <p style="margin: 0; color: #374151;">{marketing_focus}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with tab3:
            st.markdown("### Strategic Analysis & Market Insights")
            
            # Define analysis sections with icons
            analysis_sections = [
                ('product_evolution_signals', '📈 Product Evolution Signals'),
                ('pricing_strategy_changes', '💰 Pricing Strategy Changes'),
                ('target_audience_focus', '🎯 Target Audience Focus'),
                ('geographic_or_demographic_expansion', '🌍 Geographic/Demographic Expansion'),
                ('messaging_and_branding_shifts', '📢 Messaging & Branding Shifts'),
                ('technology_and_platform_innovation', '🚀 Technology & Platform Innovation'),
                ('partnerships_funding_and_hiring_trends', '🤝 Partnerships & Funding Trends'),
                ('customer_feedback_patterns', '💬 Customer Feedback Patterns')
            ]
            
            for key, title in analysis_sections:
                data = analysis_data.get(key, [])
                if data and isinstance(data, list) and len(data) > 0:
                    with st.expander(title, expanded=False):
                        for item in data:
                            st.markdown(f"• {item}")
                elif data and isinstance(data, str):
                    with st.expander(title, expanded=False):
                        st.markdown(data)
        
        with tab4:
            st.markdown("### Raw Analysis Data")
            st.markdown("**Complete raw data and analysis JSON:**")
            
            col_raw1, col_raw2 = st.columns(2)
            
            with col_raw1:
                st.markdown("#### Raw Data")
                st.json(raw_data)
            
            with col_raw2:
                st.markdown("#### Analysis JSON")
                st.json(analysis_data)