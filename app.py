import streamlit as st
import os
import time
import pandas as pd
import csv
import datetime
from apify_scraper import scrape_linkedin_jobs
from matcher import (
    extract_text_from_pdf, 
    parse_skills, 
    calculate_local_match, 
    match_with_groq,
    extract_profile_with_groq,
    match_with_groq_pro_max,
    save_resume_cache, 
    load_resume_cache,
    generate_apply_pack,
    curate_resume_ats,
    generate_resume_pdf
)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_apify_token() -> str:
    """Retrieves the Apify API token checking Streamlit session state, secrets, or environment variables."""
    try:
        import streamlit as st
        if "apify_token" in st.session_state and st.session_state.apify_token:
            return st.session_state.apify_token
        if hasattr(st, "secrets") and "APIFY_TOKEN" in st.secrets:
            return st.secrets["APIFY_TOKEN"]
    except Exception:
        pass
    return os.getenv("APIFY_TOKEN") or ""

APPLIED_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "applied_jobs.csv")

def load_persisted_jobs() -> tuple:
    applied = set()
    interested = set()
    if os.path.exists(APPLIED_CSV):
        try:
            with open(APPLIED_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get("job_url")
                    status = row.get("status")
                    if url:
                        if status == "Applied":
                            applied.add(url)
                        elif status == "Interested":
                            interested.add(url)
        except Exception as e:
            print(f"Failed to load persisted jobs: {e}")
    return applied, interested

def save_applied_job(job_url: str, title: str, company: str, location: str, status: str = "Applied"):
    existing = []
    file_exists = os.path.exists(APPLIED_CSV)
    if file_exists:
        try:
            with open(APPLIED_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing = list(reader)
        except Exception:
            pass
            
            
    updated = False
    for row in existing:
        if row.get("job_url") == job_url:
            row["status"] = status
            row["title"] = title
            row["company"] = company
            row["location"] = location
            updated = True
            break
            
    if not updated:
        existing.append({
            "job_url": job_url,
            "title": title,
            "company": company,
            "location": location,
            "applied_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status
        })
        
    try:
        with open(APPLIED_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["job_url", "title", "company", "location", "applied_at", "status"])
            writer.writeheader()
            writer.writerows(existing)
    except Exception as e:
        print(f"Failed to save applied job: {e}")

def remove_applied_job(job_url: str):
    if not os.path.exists(APPLIED_CSV):
        return
    existing = []
    try:
        with open(APPLIED_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing = list(reader)
    except Exception:
        return
        
    filtered = [row for row in existing if row.get("job_url") != job_url]
    
    try:
        with open(APPLIED_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["job_url", "title", "company", "location", "applied_at", "status"])
            writer.writeheader()
            writer.writerows(filtered)
    except Exception as e:
        print(f"Failed to remove applied job: {e}")

def parse_date_for_sorting(date_str: str) -> float:
    if not date_str or date_str == "N/A":
        return 0.0
    date_str_lower = date_str.lower().strip()
    now = datetime.datetime.now()
    try:
        import re
        if re.match(r"^\d{4}-\d{2}-\d{2}", date_str_lower):
            dt = datetime.datetime.strptime(date_str_lower[:10], "%Y-%m-%d")
            return dt.timestamp()
            
        match = re.search(r"\d+", date_str_lower)
        if not match:
            return 0.0
        num = int(match.group())
        if "second" in date_str_lower:
            delta = datetime.timedelta(seconds=num)
        elif "minute" in date_str_lower:
            delta = datetime.timedelta(minutes=num)
        elif "hour" in date_str_lower:
            delta = datetime.timedelta(hours=num)
        elif "day" in date_str_lower:
            delta = datetime.timedelta(days=num)
        elif "week" in date_str_lower:
            delta = datetime.timedelta(weeks=num)
        elif "month" in date_str_lower:
            delta = datetime.timedelta(days=num * 30)
        elif "year" in date_str_lower:
            delta = datetime.timedelta(days=num * 365)
        else:
            return 0.0
        return (now - delta).timestamp()
    except Exception:
        return 0.0

def estimate_recruiter_email(fullname: str, domain: str, format_type: str) -> str:
    if not fullname or not domain:
        return ""
    name_parts = [p.strip().lower() for p in fullname.split() if p.strip()]
    if not name_parts:
        return ""
    first = name_parts[0]
    last = name_parts[-1] if len(name_parts) > 1 else ""
    
    domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
    format_type = format_type.lower()
    
    if "first.last" in format_type:
        email_prefix = f"{first}.{last}" if last else first
    elif "f.last" in format_type or "firstinitiallast" in format_type or "flast" in format_type:
        email_prefix = f"{first[0]}{last}" if last else first
    elif "first_last" in format_type:
        email_prefix = f"{first}_{last}" if last else first
    elif "first" == format_type:
        email_prefix = first
    else:
        email_prefix = f"{first}.{last}" if last else first
        
    return f"{email_prefix}@{domain}"



# App Setup & Configuration
st.set_page_config(
    page_title="Scrapper",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Workspace path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize Session State
if 'splash_shown' not in st.session_state:
    st.session_state.splash_shown = False
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'resume_text' not in st.session_state:
    st.session_state.resume_text = ""
if 'resume_skills' not in st.session_state:
    st.session_state.resume_skills = []
if 'scraped_jobs' not in st.session_state:
    st.session_state.scraped_jobs = []
if 'matching_results' not in st.session_state:
    st.session_state.matching_results = {}
if 'applied_jobs' not in st.session_state:
    applied, interested = load_persisted_jobs()
    st.session_state.applied_jobs = applied
    st.session_state.interested_jobs = interested
if 'history_brief' not in st.session_state:
    st.session_state.history_brief = ""

# --- Splash Screen (Light Mode Aesthetic) ---
if not st.session_state.splash_shown:
    st.session_state.splash_shown = True
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&display=swap');
        
        /* Hide default Streamlit elements during splash overlay display */
        .splash-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background-color: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 999999;
            flex-direction: column;
            font-family: 'Outfit', sans-serif;
            animation: fadeOutSplash 3.0s forwards;
        }
        
        @keyframes fadeOutSplash {
            0% { opacity: 1; pointer-events: all; visibility: visible; }
            75% { opacity: 1; pointer-events: all; visibility: visible; }
            100% { opacity: 0; pointer-events: none; visibility: hidden; }
        }
        
        .splash-title {
            font-size: 5rem;
            font-weight: 800;
            text-align: center;
            color: #000000;
            -webkit-text-fill-color: #000000;
            margin-bottom: 1rem;
            letter-spacing: 2px;
            filter: drop-shadow(0 2px 5px rgba(0, 0, 0, 0.05));
            animation: pulseText 2s infinite ease-in-out;
        }
        
        .splash-subtitle {
            font-size: 1.3rem;
            color: #333333;
            letter-spacing: 4px;
            text-transform: uppercase;
            font-weight: 600;
            opacity: 0;
            animation: fadeInSub 1.5s forwards 0.5s;
        }
        
        .loader-bar {
            width: 250px;
            height: 4px;
            background: #e2e8f0;
            border-radius: 2px;
            margin-top: 2rem;
            overflow: hidden;
            position: relative;
        }
        
        .loader-fill {
            height: 100%;
            width: 0%;
            background: #000000;
            position: absolute;
            animation: fillLoader 2.2s forwards 0.2s cubic-bezier(0.1, 0.8, 0.2, 1);
        }
        
        @keyframes pulseText {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.02); }
        }
        
        @keyframes fadeInSub {
            to { opacity: 1; }
        }
        
        @keyframes fillLoader {
            to { width: 100%; }
        }
        </style>
        
        <div class="splash-overlay">
            <div class="splash-title">Hey Arbaz</div>
            <div class="splash-subtitle">Initializing Scraper Engine</div>
            <div class="loader-bar">
                <div class="loader-fill"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# Retrieve authentication credentials dynamically (no hardcoded fallbacks)
def get_admin_credentials() -> tuple:
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            u = st.secrets.get("ADMIN_USERNAME")
            p = st.secrets.get("ADMIN_PASSWORD")
            if u and p:
                return u, p
    except Exception:
        pass
    return os.getenv("ADMIN_USERNAME"), os.getenv("ADMIN_PASSWORD")

ADMIN_USERNAME, ADMIN_PASSWORD = get_admin_credentials()

# --- Login Page ---
if not st.session_state.authenticated:
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        
        .login-title {
            font-family: 'Outfit', sans-serif;
            font-size: 2.3rem;
            font-weight: 800;
            text-align: center;
            color: #0f172a;
            margin-bottom: 0.5rem;
            letter-spacing: -0.5px;
            line-height: 1.2;
        }
        
        .login-subtitle {
            font-family: 'Outfit', sans-serif;
            font-size: 0.95rem;
            color: #64748b;
            text-align: center;
            margin-bottom: 2rem;
            font-weight: 500;
        }
        
        .login-container {
            max-width: 440px;
            margin: 60px auto;
            padding: 40px 30px;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
        }
        
        /* Form stylings to fit Outfit theme */
        .stTextInput > label {
            font-family: 'Outfit', sans-serif !important;
            font-weight: 600 !important;
            color: #334155 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Lets authnticate its you arbaz</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">Enter credentials to access Scrapper Pro</div>', unsafe_allow_html=True)
        
        # Streamlit form for login inputs
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Username", placeholder="e.g. Username")
            password_input = st.text_input("Password", type="password", placeholder="••••••••")
            submit_btn = st.form_submit_button("Authenticate 🔒", use_container_width=True)
            
            if submit_btn:
                if not ADMIN_USERNAME or not ADMIN_PASSWORD:
                    st.error("🔒 Authentication is not configured. Please define ADMIN_USERNAME and ADMIN_PASSWORD in your environment variables or secrets.")
                elif username_input.strip() == ADMIN_USERNAME and password_input == ADMIN_PASSWORD:
                    st.session_state.authenticated = True
                    st.success("Access Granted! Loading Scrapper Pro...")
                    st.experimental_rerun()
                else:
                    st.error("Invalid username or password. Please try again.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()  # Lock down the application and prevent further execution

# --- Load Cached Resume ---
cached_resume = load_resume_cache(WORKSPACE_DIR)
if cached_resume and not st.session_state.resume_text:
    st.session_state.resume_text = cached_resume.get("resume_text", "")
    st.session_state.resume_skills = cached_resume.get("skills", [])
    st.session_state.history_brief = cached_resume.get("history_brief", "No career brief cached. Please re-upload resume.")

# Custom CSS for Premium Navy Blue & White Aesthetic Theme
st.markdown("""
<style>
/* App font and text color settings */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
    color: #0f1e36;
}

/* Style Streamlit Expander to look like a Premium Job Card */
div[data-testid="stExpander"], .streamlit-expander {
    background: #ffffff !important;
    border: 1px solid #dcdfe4 !important;
    border-radius: 12px !important;
    margin-bottom: 20px !important;
    box-shadow: 0 4px 6px rgba(15, 30, 54, 0.01) !important;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
}

div[data-testid="stExpander"]:hover, .streamlit-expander:hover {
    transform: translateY(-3px) !important;
    border-color: #1e3a8a !important;
    box-shadow: 0 10px 20px rgba(30, 58, 138, 0.05) !important;
    background-color: #f0f4f8 !important;
}

/* Customize the expander header label text style */
div[data-testid="stExpander"] details summary, .streamlit-expanderHeader {
    font-size: 1.05rem !important;
    color: #0f1e36 !important;
    padding: 12px 18px !important;
    border-radius: 12px !important;
}

.job-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}

/* Match Pills styled with high contrast theme colors */
.match-pill-high {
    background: #e0f2fe;
    color: #0369a1;
    border: 1px solid #bae6fd;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.85rem;
}

.match-pill-med {
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #fde68a;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.85rem;
}

.match-pill-low {
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #fca5a5;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.85rem;
}

/* Skill Tags */
.tag-green {
    background: #ecfdf5;
    color: #065f46;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-right: 5px;
    margin-bottom: 5px;
    display: inline-block;
    border: 1px solid #a7f3d0;
}

.tag-red {
    background: #fef2f2;
    color: #991b1b;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-right: 5px;
    margin-bottom: 5px;
    display: inline-block;
    border: 1px solid #fca5a5;
}

/* Base button */
.apply-btn {
    display: inline-block;
    background: linear-gradient(135deg, #1e3a8a 0%, #0f1e36 100%);
    color: #ffffff !important;
    font-weight: 700;
    padding: 8px 16px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 0.9rem;
    transition: opacity 0.2s;
    text-align: center;
    border: none;
}

.apply-btn:hover {
    opacity: 0.9;
    box-shadow: 0 4px 10px rgba(30, 58, 138, 0.15);
}

.sec-btn {
    display: inline-block;
    background: #ffffff;
    color: #0f1e36 !important;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 0.9rem;
    border: 1px solid #cbd5e1;
    text-align: center;
}

.sec-btn:hover {
    background: #f0f4f8;
    border-color: #1e3a8a;
}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 10px 0;">
        <h2 style="margin: 0; font-weight: 800; letter-spacing: 1.5px; color: #0f172a;">🎯 Scraper PRO</h2>
        <p style="color: #64748b; font-size: 0.85rem; margin-top: 5px;">Scraper</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    # Quick Profile Status
    st.markdown("### 📄 Active Profile")
    if st.session_state.resume_text:
        st.success("Resume Loaded")
        st.caption(f"Skills Extracted: {len(st.session_state.resume_skills)}")
    else:
        st.warning("No Resume Uploaded")
        st.caption("Upload your profile in the 'Resume & Profile' tab.")
        
    st.markdown("---")
    st.markdown("### 📊 Search Pipeline")
    total_scraped = len(st.session_state.scraped_jobs)
    total_applied = len(st.session_state.applied_jobs)
    total_interested = len(st.session_state.interested_jobs)
    
    st.metric("Total Jobs Scraped", total_scraped)
    st.metric("Applications Submitted", total_applied)
    st.metric("Interested Pipelines", total_interested)
    
    st.markdown("---")
    with st.expander("🔑 API Configuration", expanded=False):
        apify_token_val = st.text_input(
            "Apify API Token",
            value=st.session_state.get("apify_token", os.getenv("APIFY_TOKEN") or ""),
            type="password",
            help="Get from console.apify.com/account/integrations"
        )
        groq_key_val = st.text_input(
            "Groq API Key",
            value=st.session_state.get("groq_api_key", os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY") or ""),
            type="password",
            help="Get from console.groq.com/keys"
        )
        st.session_state.apify_token = apify_token_val
        st.session_state.groq_api_key = groq_key_val
        
        if not apify_token_val or not groq_key_val:
            st.info("💡 Add credentials here, or define them in your `.env` file to skip entering them.")
            
    st.markdown("---")
    st.caption("Made for Arbaaz 🚀")
    if st.button("Logout 🔓", use_container_width=True):
        st.session_state.authenticated = False
        st.experimental_rerun()

# --- MAIN APP LAYOUT ---
st.title("Scrapper Pro 🎯")
st.write("Scrape public LinkedIn job listings anonymously via Apify and evaluate matches using custom NLP algorithms and Groq AI.")

tabs = st.tabs(["📄 Resume & Profile", "🚀 Job Search Dashboard", "🎯 Matching Board", "📊 Application Tracker"])

# --- TAB 1: RESUME & PROFILE ---
with tabs[0]:
    st.header("Upload and Extract Resume Context")
    
    # Check if a resume is already loaded in the session state
    if st.session_state.resume_text:
        # HIDE Uploader and show a clean enterprise overview card
        st.markdown(f"""
        <div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:25px; margin-bottom:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0; color:#0f172a;">📄 {cached_resume.get('filename') if cached_resume else 'Cached Resume File'}</h3>
                <span style="background:#f1f5f9; color:#0f172a; border:1px solid #cbd5e1; padding:4px 12px; border-radius:20px; font-weight:600; font-size:0.8rem;">Profile Loaded</span>
            </div>
            <p style="color:#64748b; font-size:0.9rem; margin-top:8px;">Your resume profile is loaded and cached. The skills parsed from your PDF will be matched against scraped LinkedIn jobs.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Display Career History Brief
        st.markdown("### 💼 Career Executive Summary (AI Parsed)")
        st.markdown(f"""
        <div style="background:#f8fafc; border-left:4px solid #0f172a; border-radius:4px; padding:15px; margin-bottom:20px;">
            <p style="margin:0; color:#0f172a; font-size:0.95rem; line-height:1.5;">{st.session_state.history_brief}</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("Extracted Tech Skills")
            if st.session_state.resume_skills:
                # Custom skill tags layout
                skills_html = "".join([f'<span class="tag-green" style="font-size:0.9rem; padding:4px 10px; margin-bottom:8px;">{s}</span>' for s in st.session_state.resume_skills])
                st.markdown(skills_html, unsafe_allow_html=True)
                st.write("")
                
                # Allow inline edits of skills
                edited_skills = st.multiselect(
                    "Refine parsed skills list:",
                    options=st.session_state.resume_skills + [s for s in parse_skills(st.session_state.resume_text) if s not in st.session_state.resume_skills],
                    default=st.session_state.resume_skills
                )
                if edited_skills != st.session_state.resume_skills:
                    st.session_state.resume_skills = edited_skills
                    save_resume_cache(
                        cached_resume.get("filename", "custom_skills") if cached_resume else "custom_skills",
                        st.session_state.resume_text,
                        edited_skills,
                        st.session_state.history_brief,
                        WORKSPACE_DIR
                    )
            
        with col2:
            st.subheader("Actions")
            if st.button("Change Resume 🔄", use_container_width=True):
                st.session_state.resume_text = ""
                st.session_state.resume_skills = []
                st.session_state.history_brief = ""
                cache_path = os.path.join(WORKSPACE_DIR, ".resume_cache.json")
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                st.experimental_rerun()
                
            st.markdown("---")
            with st.expander("Show Resume Text Preview"):
                st.text_area("Original Resume Text", st.session_state.resume_text, height=300, disabled=True)
    else:
        # Show file uploader only when no resume is loaded
        uploaded_file = st.file_uploader("Upload your resume (PDF) to begin:", type=["pdf"])
        if uploaded_file is not None:
            with st.spinner("Extracting profile details & technical skills using Groq AI..."):
                try:
                    resume_text = extract_text_from_pdf(uploaded_file)
                    st.session_state.resume_text = resume_text
                    
                    # Run Groq Profile Extractor
                    parsed_profile = extract_profile_with_groq(resume_text)
                    st.session_state.resume_skills = parsed_profile.get("skills", [])
                    st.session_state.history_brief = parsed_profile.get("history_brief", "No career summary available.")
                    
                    # Save to local cache
                    save_resume_cache(uploaded_file.name, resume_text, st.session_state.resume_skills, st.session_state.history_brief, WORKSPACE_DIR)
                    st.success("Resume parsed, skills, and career brief successfully cached!")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error reading PDF: {e}")

# --- TAB 2: JOB SEARCH DASHBOARD ---
with tabs[1]:
    st.header("Search & Scrape Setup")
    st.write("Configure your target job filters. The scraper will fetch public jobs directly from LinkedIn anonymously (no login required).")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Filter Parameters")
        
        keywords = st.text_input("Job Position (Keywords)", value="Python Data Engineer", placeholder="e.g. React Developer")
        addon = st.text_input("Addon Keywords (Optional)", value="Snowflake, SQL, PySpark", placeholder="e.g. Tailwind, Redux")
        st.caption("💡 **Tip:** Addon keywords are evaluated locally by our match scorer rather than being sent to LinkedIn. This keeps your search broad to maximize matching results!")
        location = st.text_input("Location", value="Hyderabad, India", placeholder="e.g. San Francisco, CA")
        target_companies = st.text_input("Target Companies (Optional)", value="", placeholder="e.g. Google, Microsoft, Meta")
        st.caption("💡 **Tip:** Enter company names comma-separated to restrict search to these employers. Leave blank to scrape any company.")
        
        # Combine keywords for scraper
        search_query = keywords
        if addon:
            search_query += f" {addon}"
            
    with col2:
        st.subheader("Scraper Controls")
        
        job_type = st.selectbox(
            "Job Type Filter", 
            options=["Any", "Full-Time", "Contract", "Part-Time", "Internship"], 
            index=0
        )
        
        date_posted = st.selectbox(
            "Date Posted Recency", 
            options=["Any", "Today", "3 Days", "Week", "Month"], 
            index=3
        )
        
        pages_to_fetch = st.slider("Pages to Scrape (1 page = ~25 jobs)", min_value=1, max_value=5, value=2)
        
    st.markdown("---")
    
    run_col1, run_col2 = st.columns([1, 2])
    with run_col1:
        # Trigger Button
        if st.button("🚀 Scrape & Analyze Jobs", use_container_width=True):
            token = get_apify_token()
            if not st.session_state.resume_text:
                st.error("Please upload your resume in the 'Resume & Profile' tab first to enable matching.")
            elif not token:
                st.error("Apify API Token is not configured. Please enter it in the sidebar API Configuration expander or set it in your .env file.")
            else:
                class StatusLogger:
                    def __init__(self, title):
                        self.title_placeholder = st.empty()
                        self.title_placeholder.info(title)
                        self.expander = st.expander("Detailed Progress Logs", expanded=True)
                        self.log_container = self.expander.empty()
                        self.logs = []
                        
                    def write(self, text):
                        self.logs.append(text)
                        self.log_container.markdown("\n".join([f"- {log}" for log in self.logs]))
                        
                    def update(self, label, state=None, expanded=False):
                        if state == "complete":
                            self.title_placeholder.success(label)
                        elif state == "error":
                            self.title_placeholder.error(label)
                        else:
                            self.title_placeholder.info(label)

                status = StatusLogger("Running Apify scraper (this may take 1-2 minutes)...")
                try:
                    status.write("Initializing Apify Client...")
                    mapped_job_type = None if job_type == "Any" else job_type
                    mapped_date = None if date_posted == "Any" else date_posted
                    
                    comp_log_str = f" at targeted companies ({target_companies})" if target_companies else ""
                    status.write(f"Running curious_coder/linkedin-jobs-scraper for '{keywords}' in '{location}'{comp_log_str}...")
                    jobs = scrape_linkedin_jobs(
                        api_token=token,
                        keyword=keywords,
                        location=location,
                        country="all",
                        job_type=mapped_job_type,
                        date_posted=mapped_date,
                        pages_to_fetch=pages_to_fetch,
                        target_companies=target_companies
                    )
                    
                    status.write(f"Scraper returned {len(jobs)} jobs. Calculating matching scores...")
                    st.session_state.scraped_jobs = jobs
                    st.session_state.matching_results = {} 
                    
                    # Parse addon keywords to feed local match scorer
                    addon_list = [s.strip() for s in addon.split(",") if s.strip()] if addon else None
                    
                    for idx, job in enumerate(jobs):
                        # Run Local Matcher
                        status.write(f"[{idx+1}/{len(jobs)}] Scoring '{job['title']}' at {job['company']}...")
                        match_data = calculate_local_match(
                            st.session_state.resume_text, 
                            st.session_state.resume_skills, 
                            job["description"],
                            custom_skills=addon_list
                        )
                        st.session_state.matching_results[job["job_url"]] = match_data
                        
                    status.update(label="Scraping & Matching Complete!", state="complete", expanded=False)
                    st.success(f"Successfully processed {len(jobs)} jobs! Head over to the 'Matching Board' to review.")
                except Exception as e:
                    status.update(label=f"Scraper Failed: {str(e)}", state="error")
                    st.error(f"An error occurred: {e}")
                    
    with run_col2:
        if st.session_state.scraped_jobs:
            df = pd.DataFrame(st.session_state.scraped_jobs)
            st.metric("Total Jobs Found", len(df))
            st.dataframe(
                df[["title", "company", "location", "posted_date"]], 
                use_container_width=True
            )
        else:
            st.info("No active run data. Set your filters above and click 'Scrape & Analyze Jobs' to pull job cards.")

# --- TAB 3: MATCHING BOARD ---
with tabs[2]:
    st.header("Job Match Intelligence Board")
    
    if not st.session_state.scraped_jobs:
        st.info("No scraped jobs found. Run a job search under the 'Job Search Dashboard' tab to pull job listings.")
    else:
        # Build list with match scores to allow sorting
        job_evals = []
        for job in st.session_state.scraped_jobs:
            url = job["job_url"]
            match_data = st.session_state.matching_results.get(url, {
                "score": 0, "matched_skills": [], "missing_skills": [], "explanation": "No score computed."
            })
            job_evals.append({
                "job": job,
                "score": match_data["score"],
                "matched_skills": match_data["matched_skills"],
                "missing_skills": match_data["missing_skills"],
                "explanation": match_data["explanation"]
            })
            
        # Filter controls
        f_col1, f_col2 = st.columns([2, 2])
        with f_col1:
            min_score = st.slider("Filter by Minimum Score:", 0, 100, 40, key="matching_min_score")
            hide_applied = st.checkbox("Hide Applied Jobs", value=False, key="matching_hide_applied")
        with f_col2:
            sort_by = st.radio("Sort Listings By:", options=["Highest Match Score", "Latest Posted Date"], index=0, horizontal=True)
            
        # Sort jobs
        if sort_by == "Latest Posted Date":
            job_evals = sorted(job_evals, key=lambda x: parse_date_for_sorting(x["job"]["posted_date"]), reverse=True)
        else:
            job_evals = sorted(job_evals, key=lambda x: x["score"], reverse=True)
            
        st.markdown("---")
        
        # Display Loop
        visible_cards = 0
        for idx, item in enumerate(job_evals):
            job = item["job"]
            score = item["score"]
            matched = item["matched_skills"]
            missing = item["missing_skills"]
            exp = item["explanation"]
            url = job["job_url"]
            
            # Apply filters
            if score < min_score:
                continue
            if hide_applied and url in st.session_state.applied_jobs:
                continue
                
            visible_cards += 1
            
            status_tag = ""
            if url in st.session_state.applied_jobs:
                status_tag = "  |  Applied ✅"
            elif url in st.session_state.interested_jobs:
                status_tag = "  |  Interested ⭐"
                
            expander_label = f"💼 **{job['title']}**  —  {job['company']} ({job['location']})  |  `{score}% Match`{status_tag}  |  Posted: {job['posted_date']}"
            
            with st.expander(expander_label):
                # Check if AI evaluation has been run
                ai_key = f"ai_eval_{idx}_{url}"
                has_ai = ai_key in st.session_state
                
                if has_ai:
                    ai_data = st.session_state[ai_key]
                    display_score = ai_data.get("score", score)
                    display_matched = ai_data.get("matched_skills", matched)
                    display_missing = ai_data.get("missing_skills", missing)
                    display_exp = ai_data.get("explanation", exp)
                    display_gap = ai_data.get("gap_analysis", "No gaps identified.")
                    display_tips = ai_data.get("optimization_tips", [])
                    
                    if display_score >= 80:
                        score_pill_ai = f'<span class="match-pill-high" style="font-size:0.9rem; padding:4px 12px; margin-left:10px;">🤖 AI Match: {display_score}%</span>'
                    elif display_score >= 50:
                        score_pill_ai = f'<span class="match-pill-med" style="font-size:0.9rem; padding:4px 12px; margin-left:10px;">🤖 AI Match: {display_score}%</span>'
                    else:
                        score_pill_ai = f'<span class="match-pill-low" style="font-size:0.9rem; padding:4px 12px; margin-left:10px;">🤖 AI Match: {display_score}%</span>'
                else:
                    display_score = score
                    display_matched = matched
                    display_missing = missing
                    display_exp = exp
                    display_gap = ""
                    display_tips = []
                    score_pill_ai = ""

                det_col1, det_col2 = st.columns([3, 1])
                
                with det_col1:
                    if has_ai:
                        st.markdown(f"#### {score_pill_ai}", unsafe_allow_html=True)
                        st.markdown(f"**AI Fit Summary:** {display_exp}")
                        st.markdown(f"**⚠️ Gap Analysis:** {display_gap}")
                        if display_tips:
                            st.markdown("**💡 ATS Optimization Tips:**")
                            for tip in display_tips:
                                st.markdown(f"- {tip}")
                    else:
                        st.markdown(f"**Baseline Match Score:** `{score}%` (Rule-based overlap)")
                        st.markdown(f"**Local Fit Summary:** {display_exp}")
                        
                        # Button to run Pro-Max AI evaluation
                        if st.button("🤖 Run Pro-Max AI Match Score (Groq)", key=f"btn_ai_eval_{idx}_{url}", use_container_width=True):
                            with st.spinner("Analyzing semantic fit with Groq Pro-Max..."):
                                try:
                                    addon_list = [s.strip() for s in addon.split(",") if s.strip()] if addon else None
                                    ai_result = match_with_groq_pro_max(
                                        st.session_state.resume_text,
                                        job["description"],
                                        custom_skills=addon_list
                                    )
                                    st.session_state[ai_key] = ai_result
                                    st.experimental_rerun()
                                except Exception as e:
                                    st.error(f"AI Evaluation failed: {e}")
                    
                    st.markdown("---")
                    
                    # Render Skill Badges
                    if display_matched:
                        st.markdown("**Matched Skills:**")
                        matched_badges = "".join([f'<span class="tag-green">{s}</span>' for s in display_matched])
                        st.markdown(matched_badges, unsafe_allow_html=True)
                        
                    if display_missing:
                        st.markdown("**Missing Skills (Keywords from Job Desc):**")
                        missing_badges = "".join([f'<span class="tag-red">{s}</span>' for s in display_missing])
                        st.markdown(missing_badges, unsafe_allow_html=True)
                        
                    st.markdown("---")
                    st.markdown("**Full Job Description snippet:**")
                    st.text_area("Description Text", job["description"][:1200] + ("..." if len(job["description"]) > 1200 else ""), height=200, disabled=True, key=f"desc_{idx}_{url}")
                    
                with det_col2:
                    st.markdown("### Actions")
                    
                    # Normal Apply Redirect
                    if url:
                        st.markdown(f'<a href="{url}" target="_blank" class="apply-btn" style="width:100%; text-align:center;">Normal Apply ↗</a>', unsafe_allow_html=True)
                    else:
                        st.warning("No URL available")
                        
                    st.write("")
                    
                    # Track Applied state
                    if url in st.session_state.applied_jobs:
                        st.success("Applied! ✅")
                        if st.button("Mark Unapplied", key=f"unapp_{idx}_{url}"):
                            st.session_state.applied_jobs.remove(url)
                            remove_applied_job(url)
                            st.experimental_rerun()
                    else:
                        if st.button("Mark Applied", key=f"app_{idx}_{url}", use_container_width=True):
                            st.session_state.applied_jobs.add(url)
                            if url in st.session_state.interested_jobs:
                                st.session_state.interested_jobs.remove(url)
                            save_applied_job(url, job["title"], job["company"], job["location"], "Applied")
                            st.experimental_rerun()
                            
                        if url in st.session_state.interested_jobs:
                            st.success("Interested ⭐")
                            if st.button("Unmark Interested", key=f"unint_{idx}_{url}", use_container_width=True):
                                st.session_state.interested_jobs.remove(url)
                                remove_applied_job(url)
                                st.experimental_rerun()
                        else:
                            if st.button("Mark Interested", key=f"int_{idx}_{url}", use_container_width=True):
                                st.session_state.interested_jobs.add(url)
                                save_applied_job(url, job["title"], job["company"], job["location"], "Interested")
                                st.experimental_rerun()
                
                # --- PHASE 2 ADVANCED INTEGRATION BLOCKS ---
                st.markdown("---")
                st.markdown("### ⚡ Advanced Recruiting Intelligence")
                
                adv_tab1, adv_tab2 = st.tabs(["📧 Advanced Apply (Cold Email)", "📄 ATS Resume Curation (PDF)"])
                
                # TAB 1: COLD EMAIL & RECRUITER CONTACTS
                with adv_tab1:
                    if st.button("Generate Cold Email & Contacts", key=f"gen_adv_{idx}_{url}"):
                        with st.spinner("Calling Groq AI to structure outreach..."):
                            try:
                                pack = generate_apply_pack(
                                    resume_text=st.session_state.resume_text,
                                    job_title=job["title"],
                                    company=job["company"],
                                    job_description=job["description"]
                                )
                                st.session_state[f"pack_{idx}_{url}"] = pack
                            except Exception as e:
                                st.error(f"Failed to generate outreach: {e}")
                                
                    if f"pack_{idx}_{url}" in st.session_state:
                        pack = st.session_state[f"pack_{idx}_{url}"]
                        
                        # Search query for LinkedIn recruiters
                        import urllib.parse
                        search_keywords = f"Talent Acquisition {job['company']} OR Recruiter {job['company']}"
                        encoded_search = urllib.parse.quote(search_keywords)
                        linkedin_search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_search}"
                        
                        col_rec1, col_rec2 = st.columns([1, 2])
                        with col_rec1:
                            st.markdown("##### 🔍 Step 1: Find Real Recruiter")
                            st.markdown(f'<a href="{linkedin_search_url}" target="_blank" class="apply-btn" style="width:100%; text-align:center; display:inline-block; text-decoration:none;">Find Recruiters on LinkedIn ↗</a>', unsafe_allow_html=True)
                            
                            st.markdown("---")
                            st.markdown("##### ✍️ Step 2: Paste Recruiter Name")
                            rec_name = st.text_input("Pasted Recruiter Name:", placeholder="e.g. Amit Sharma", key=f"rec_name_{idx}_{url}")
                            
                            # Estimate Email based on Groq domain details
                            domain = pack.get("company_domain", f"{job['company'].lower().replace(' ', '')}.com")
                            format_type = pack.get("email_format_type", "first.last")
                            
                            estimated_email = ""
                            if rec_name:
                                estimated_email = estimate_recruiter_email(rec_name, domain, format_type)
                                
                            st.markdown("##### 📧 Step 3: Estimated Recruiter Email")
                            st.caption(f"Domain: `{domain}` | Format: `{format_type}`")
                            rec_email = st.text_input("Recruiter Email (Editable):", value=estimated_email, key=f"rec_email_{idx}_{url}")
                            
                        with col_rec2:
                            st.markdown("##### 📩 Step 4: Review Email & Compose")
                            
                            # Substitute recruiter name into body greeting
                            orig_body = pack.get("email_body", "")
                            processed_body = orig_body
                            if rec_name:
                                first_name = rec_name.split()[0]
                                processed_body = orig_body.replace("[Recruiter Name]", first_name)
                                
                            subj_val = st.text_input("Subject Line:", value=pack.get("subject", ""), key=f"subj_{idx}_{url}")
                            body_val = st.text_area("Email Body:", value=processed_body, height=250, key=f"body_{idx}_{url}")
                            
                            # Gmail Compose Link
                            if rec_email:
                                subject_encoded = urllib.parse.quote(subj_val)
                                body_encoded = urllib.parse.quote(body_val)
                                gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={rec_email}&su={subject_encoded}&body={body_encoded}"
                                
                                st.markdown(f'<a href="{gmail_url}" target="_blank" class="apply-btn" style="width:100%; text-align:center; display:inline-block; background:#ea4335; color:white; border:none; padding:10px 20px; border-radius:8px; font-weight:bold; text-decoration:none;">Compose in Gmail ✉️</a>', unsafe_allow_html=True)
                            else:
                                st.info("ℹ️ Enter the recruiter name to compute their corporate email and enable Gmail Compose.")

                # TAB 2: ATS RESUME CURATION (PDF BUILDER)
                with adv_tab2:
                    st.write("Generates a version of your original resume with key technical terms substituted to align with the job description keywords. Spacing, achievements, and formatting are strictly preserved.")
                    
                    if st.button("Curate Wording & Build PDF", key=f"gen_pdf_{idx}_{url}"):
                        with st.spinner("Optimizing resume keywords and compiling PDF..."):
                            try:
                                # 1. Direct Groq Call to do word substitutions
                                curated_text = curate_resume_ats(
                                    resume_text=st.session_state.resume_text,
                                    job_description=job["description"]
                                )
                                
                                # 2. Build PDF using ReportLab
                                pdf_filename = f"Curated_Resume_{job['company'].replace(' ', '_')}.pdf"
                                pdf_path = os.path.join(WORKSPACE_DIR, pdf_filename)
                                generate_resume_pdf(curated_text, pdf_path)
                                
                                # Save details to session state
                                st.session_state[f"pdf_{idx}_{url}"] = {
                                    "path": pdf_path,
                                    "filename": pdf_filename,
                                    "text": curated_text
                                }
                                st.success("Resume optimized and PDF successfully built!")
                            except Exception as e:
                                st.error(f"Failed to curate resume: {e}")
                                
                    if f"pdf_{idx}_{url}" in st.session_state:
                        pdf_info = st.session_state[f"pdf_{idx}_{url}"]
                        
                        # Read PDF bytes to offer a download button
                        with open(pdf_info["path"], "rb") as f:
                            pdf_bytes = f.read()
                            
                        st.download_button(
                            label="⬇️ Download Curated Resume (PDF)",
                            data=pdf_bytes,
                            file_name=pdf_info["filename"],
                            mime="application/pdf",
                            key=f"dl_btn_{idx}_{url}",
                            use_container_width=True
                        )
                        
                        st.markdown("**Curated Resume Text Preview:**")
                        st.text_area("Curated Resume Text", pdf_info["text"], height=250, disabled=True, key=f"txt_{idx}_{url}", label_visibility="collapsed")

        if visible_cards == 0:
            st.info("No jobs match your current filters.")

# --- TAB 4: APPLICATION TRACKER ---
with tabs[3]:
    st.header("📊 Application Performance Tracker")
    st.write("Monitor your recruitment pipeline stats. The details are stored in your active session.")
    
    total_scraped = len(st.session_state.scraped_jobs)
    total_applied = len(st.session_state.applied_jobs)
    total_interested = len(st.session_state.interested_jobs)
    total_skipped = max(0, total_scraped - (total_applied + total_interested))
    
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric("Total Jobs Found", total_scraped)
    with m_col2:
        st.metric("Applied Listings", total_applied, delta=None)
    with m_col3:
        st.metric("Interested Roles", total_interested)
    with m_col4:
        st.metric("Skipped/Unsorted", total_skipped)
        
    st.markdown("---")
    
    # Render Application Tables
    st.subheader("Your Pipeline Detail")
    
    pipeline_jobs = []
    for job in st.session_state.scraped_jobs:
        url = job["job_url"]
        status = "Skipped"
        if url in st.session_state.applied_jobs:
            status = "Applied ✅"
        elif url in st.session_state.interested_jobs:
            status = "Interested ⭐"
            
        if status != "Skipped":
            pipeline_jobs.append({
                "Job Title": job["title"],
                "Company": job["company"],
                "Location": job["location"],
                "Status": status,
                "Apply Page Link": url
            })
            
    if pipeline_jobs:
        pipe_df = pd.DataFrame(pipeline_jobs)
        st.dataframe(pipe_df, use_container_width=True)
    else:
        st.info("No active pipeline logs. Go to the 'Matching Board' and mark jobs as 'Applied' or 'Interested' to populate this dashboard.")
