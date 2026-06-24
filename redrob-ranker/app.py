"""
app.py: Streamlit web application for the Redrob Candidate Ranking System.

This module provides a browser-based dashboard for judges to upload candidate 
files, execute the ranking pipeline, visualize score breakdowns, inspect 
honeypot detection results, and download submission CSVs.
"""

import io
import csv
import json
import warnings
import re
import pandas as pd
import streamlit as st

from scorer import CandidateScorer
from honeypot_detector import HoneypotDetector

# ──────────────────────────────────────────────────────────────────────
# Page Configuration
# ──────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Redrob Candidate Ranker",
    page_icon="🎯",
    layout="wide"
)

# ──────────────────────────────────────────────────────────────────────
# Custom CSS — Full Design System Injection
# ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Google Fonts ─────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    /* ── Global Reset & Typography ────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .main .block-container {
        background: #F8F9FF;
        padding-top: 1rem;
    }

    /* ── Hide Streamlit defaults ──────────────────────────────────── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent;}

    /* ── Custom Scrollbar ─────────────────────────────────────────── */
    ::-webkit-scrollbar {width: 8px; height: 8px;}
    ::-webkit-scrollbar-track {background: #F8F9FF;}
    ::-webkit-scrollbar-thumb {background: #6C3CE1; border-radius: 4px;}
    ::-webkit-scrollbar-thumb:hover {background: #5530B8;}

    /* ── Hero Header ──────────────────────────────────────────────── */
    .hero-banner {
        background: linear-gradient(135deg, #6C3CE1, #FF6B6B);
        border-radius: 16px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .hero-banner::before {
        content: '';
        position: absolute;
        top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: radial-gradient(circle at 30% 50%, rgba(255,255,255,0.08) 0%, transparent 60%);
        pointer-events: none;
    }
    .hero-title {
        font-size: 2.4rem;
        font-weight: 800;
        color: #FFFFFF;
        margin: 0;
        letter-spacing: -0.02em;
        text-shadow: 0 2px 10px rgba(0,0,0,0.15);
    }
    .hero-subtitle {
        font-size: 1.15rem;
        font-weight: 500;
        color: rgba(255,255,255,0.9);
        margin-top: 0.25rem;
        margin-bottom: 1rem;
    }
    .badge-row {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }
    .hero-badge {
        display: inline-flex;
        align-items: center;
        background: rgba(255,255,255,0.18);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 20px;
        padding: 5px 14px;
        font-size: 0.78rem;
        font-weight: 600;
        color: #FFFFFF;
        letter-spacing: 0.01em;
        transition: all 0.3s ease;
    }
    .hero-badge:hover {
        background: rgba(255,255,255,0.28);
        transform: translateY(-1px);
    }

    /* ── Sidebar ──────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: #1A1A2E !important;
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stMarkdown h4,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.15);
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 8px;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        color: #FFFFFF !important;
    }

    .sidebar-weight-bar {
        margin-bottom: 14px;
    }
    .sidebar-weight-bar .sw-label {
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
        font-size: 0.82rem;
        font-weight: 600;
        color: #FFFFFF;
    }
    .sidebar-weight-bar .sw-track {
        height: 8px;
        background: rgba(255,255,255,0.12);
        border-radius: 4px;
        overflow: hidden;
    }
    .sidebar-weight-bar .sw-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.6s ease;
    }

    /* ── Upload Zone ──────────────────────────────────────────────── */
    .upload-zone {
        border: 2px dashed #6C3CE1;
        background: linear-gradient(135deg, #F0EBFF, #FFF5F5);
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    .upload-zone:hover {
        border-color: #FF6B6B;
        box-shadow: 0 4px 20px rgba(108,60,225,0.12);
    }
    .upload-zone .upload-icon {
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    .upload-zone h3 {
        color: #1A1A2E;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .upload-zone p {
        color: #666888;
        font-size: 0.92rem;
    }

    /* ── File Loaded Success Banner ───────────────────────────────── */
    .file-loaded-banner {
        background: linear-gradient(90deg, #4CAF50, #45B39D);
        color: #FFFFFF;
        border-radius: 10px;
        padding: 0.85rem 1.25rem;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 12px rgba(76,175,80,0.25);
    }

    /* ── JD Section Header ────────────────────────────────────────── */
    .jd-section-header {
        background: linear-gradient(90deg, #6C3CE1, #9B59B6);
        color: #FFFFFF;
        font-weight: 700;
        font-size: 1.15rem;
        padding: 0.75rem 1.25rem;
        border-radius: 10px 10px 0 0;
        margin-bottom: 0;
    }
    .jd-requirements-box {
        background: #F0EBFF;
        border-left: 4px solid #6C3CE1;
        border-radius: 0 8px 8px 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        color: #1A1A2E;
        font-size: 0.92rem;
        line-height: 1.7;
    }

    /* ── Focus styles for text area ───────────────────────────────── */
    .stTextArea textarea:focus {
        border-color: #6C3CE1 !important;
        box-shadow: 0 0 0 2px rgba(108,60,225,0.2) !important;
    }

    /* ── Run Ranker Button ────────────────────────────────────────── */
    .stButton > button[kind="primary"],
    div[data-testid="stButton"] > button[kind="primary"],
    .stButton > button {
        background: linear-gradient(135deg, #6C3CE1, #FF6B6B) !important;
        color: white !important;
        border: none !important;
        border-radius: 50px !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        padding: 0.75rem 2rem !important;
        box-shadow: 0 4px 15px rgba(108,60,225,0.4) !important;
        transition: all 0.3s ease !important;
        letter-spacing: 0.01em;
    }
    .stButton > button:hover,
    div[data-testid="stButton"] > button:hover {
        box-shadow: 0 6px 25px rgba(108,60,225,0.55) !important;
        transform: translateY(-2px) !important;
    }

    /* ── Download Button ──────────────────────────────────────────── */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #4CAF50, #45B39D) !important;
        color: white !important;
        border: none !important;
        border-radius: 50px !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        padding: 0.75rem 2rem !important;
        box-shadow: 0 4px 15px rgba(76,175,80,0.35) !important;
        transition: all 0.3s ease !important;
    }
    .stDownloadButton > button:hover {
        box-shadow: 0 6px 25px rgba(76,175,80,0.5) !important;
        transform: translateY(-2px) !important;
    }

    /* ── Metric Cards ─────────────────────────────────────────────── */
    .metric-card-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 16px;
        margin: 1rem 0 1.5rem;
    }
    @media (max-width: 768px) {
        .metric-card-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    .metric-card-v2 {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 1.15rem 1rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    .metric-card-v2:hover {
        box-shadow: 0 6px 20px rgba(0,0,0,0.12);
        transform: translateY(-3px);
    }
    .metric-card-v2::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 4px;
    }
    .metric-card-v2.mc-purple::before  { background: #6C3CE1; }
    .metric-card-v2.mc-green::before   { background: #4CAF50; }
    .metric-card-v2.mc-coral::before   { background: #FF6B6B; }
    .metric-card-v2.mc-orange::before  { background: #FF9800; }
    .metric-card-v2.mc-blue::before    { background: #2196F3; }
    .metric-card-v2 .mc-icon {
        font-size: 1.6rem;
        margin-bottom: 4px;
    }
    .metric-card-v2 .mc-label {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #666888;
        margin-bottom: 2px;
    }
    .metric-card-v2 .mc-value {
        font-size: 1.7rem;
        font-weight: 800;
        color: #1A1A2E;
    }

    /* Honeypot pulse animation */
    @keyframes pulse-coral {
        0%   { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        50%  { box-shadow: 0 2px 20px rgba(255,107,107,0.45); }
        100% { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    }
    .metric-card-v2.mc-coral.mc-pulse {
        animation: pulse-coral 2s ease-in-out infinite;
    }

    /* ── Tab Styling ──────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
        border-bottom: none;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px !important;
        padding: 10px 20px !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        border: none !important;
        background: #EEF0F6 !important;
        color: #666888 !important;
        transition: all 0.3s ease !important;
    }
    .stTabs [aria-selected="true"][data-baseweb="tab"] {
        background: linear-gradient(135deg, #6C3CE1, #9B59B6) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 12px rgba(108,60,225,0.3) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        display: none;
    }
    .stTabs [data-baseweb="tab-border"] {
        display: none;
    }

    /* ── Honeypot Report Cards ────────────────────────────────────── */
    .honeypot-clear {
        background: linear-gradient(135deg, #4CAF50, #45B39D);
        color: #FFFFFF;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        font-size: 1.2rem;
        font-weight: 700;
        box-shadow: 0 4px 15px rgba(76,175,80,0.3);
    }
    .honeypot-clear .big-check {
        font-size: 3rem;
        display: block;
        margin-bottom: 0.5rem;
    }
    .honeypot-alert-header {
        background: linear-gradient(135deg, #FF6B6B, #E74C3C);
        color: #FFFFFF;
        border-radius: 12px 12px 0 0;
        padding: 1rem 1.25rem;
        font-weight: 700;
        font-size: 1.05rem;
    }
    .honeypot-danger-card {
        border-left: 4px solid #FF6B6B;
        background: #FFF5F5;
        border-radius: 0 8px 8px 0;
        padding: 1rem 1.25rem;
        margin-bottom: 12px;
        transition: all 0.3s ease;
    }
    .honeypot-danger-card:hover {
        box-shadow: 0 2px 12px rgba(255,107,107,0.15);
    }
    .flag-badge {
        display: inline-block;
        background: #FF6B6B;
        color: #FFFFFF;
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 3px 4px 3px 0;
    }
    .risk-bar-track {
        height: 8px;
        background: #FFE0E0;
        border-radius: 4px;
        overflow: hidden;
        margin-top: 6px;
    }
    .risk-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #FF6B6B, #E74C3C);
        border-radius: 4px;
        transition: width 0.6s ease;
    }

    /* ── Score Breakdown Metric Cards ─────────────────────────────── */
    .breakdown-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        transition: all 0.3s ease;
    }
    .breakdown-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    .breakdown-card .bc-icon { font-size: 1.5rem; }
    .breakdown-card .bc-label {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #666888;
    }
    .breakdown-card .bc-value {
        font-size: 1.5rem;
        font-weight: 800;
        color: #1A1A2E;
    }

    /* ── Section Headers ──────────────────────────────────────────── */
    .gradient-section-header {
        background: linear-gradient(135deg, #6C3CE1, #FF6B6B);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 800;
        font-size: 1.4rem;
        margin-bottom: 0.75rem;
    }

    /* ── Validation Checklist ─────────────────────────────────────── */
    .validation-card {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 0.75rem 1.25rem;
        margin-bottom: 8px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        font-size: 0.92rem;
        color: #1A1A2E;
        display: flex;
        align-items: center;
        gap: 8px;
        transition: all 0.3s ease;
    }
    .validation-card:hover {
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .validation-card .vc-dot {
        width: 10px; height: 10px;
        border-radius: 50%;
        background: #4CAF50;
        flex-shrink: 0;
    }
    .validation-card.vc-fail .vc-dot {
        background: #FF6B6B;
    }

    /* ── Footer ───────────────────────────────────────────────────── */
    .app-footer {
        background: #1A1A2E;
        color: rgba(255,255,255,0.7);
        text-align: center;
        padding: 1.5rem;
        border-radius: 12px;
        margin-top: 2.5rem;
        font-size: 0.82rem;
        line-height: 1.8;
    }
    .app-footer a {
        color: #FF6B6B;
        text-decoration: none;
        font-weight: 600;
        transition: color 0.3s ease;
    }
    .app-footer a:hover { color: #FFFFFF; }
    .app-footer .footer-title {
        color: #FFFFFF;
        font-weight: 700;
        font-size: 0.92rem;
    }

    /* ── Misc: Gradient text utility ──────────────────────────────── */
    .grad-text {
        background: linear-gradient(135deg, #6C3CE1, #FF6B6B);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 800;
    }

    /* ── Override Streamlit dividers ──────────────────────────────── */
    hr {
        border-color: #E8E8F4 !important;
    }

    /* ── Dataframe styling ────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }

    /* ── Info / Warning / Error box overrides ─────────────────────── */
    .stAlert > div {
        border-radius: 10px !important;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# SECTION 1 — Hero Header
# ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
    <p class="hero-title">🎯 Redrob Intelligent Candidate Ranker</p>
    <p class="hero-subtitle">Senior AI Engineer — Founding Team</p>
    <div class="badge-row">
        <span class="hero-badge">⚡ AI-Powered</span>
        <span class="hero-badge">🛡️ Fraud Detection</span>
        <span class="hero-badge">📊 23 Behavioral Signals</span>
        <span class="hero-badge">🚀 100K Candidates in 60s</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# SECTION 1.5 — Job Description
# ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="jd-section-header">📋 Job Description</div>', unsafe_allow_html=True)
jd_text = st.text_area(
    "Paste Job Description (optional)",
    placeholder="Paste a job description here to customize scoring, or leave blank to use the default Senior AI Engineer JD.",
    height=150
)

uploaded_jd_file = None
with st.expander("Or upload a JD file"):
    uploaded_jd_file = st.file_uploader(
        "Upload a JD file",
        type=["txt", "md", "docx"],
        key="jd_file_uploader"
    )

if uploaded_jd_file is not None:
    jd_filename = uploaded_jd_file.name.lower()
    if jd_filename.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(uploaded_jd_file)
            uploaded_jd_text = "\n".join([p.text for p in doc.paragraphs])
            jd_text = uploaded_jd_text
        except Exception as e:
            st.error(f"Could not parse docx file: {e}")
    else:
        try:
            uploaded_jd_text = uploaded_jd_file.read().decode("utf-8")
            jd_text = uploaded_jd_text
        except Exception as e:
            st.error(f"Error reading file: {e}")

custom_jd_provided = False
jd_override = None

if jd_text.strip():
    custom_jd_provided = True
    # 1. Experience years extraction
    # Look for years like "5-9 years" or "5 to 9 years" or en-dash "4–8 years"
    exp_match = re.search(r"(\d+)[\s\u2013-]+(?:to|[\u2013-])?[\s]*(\d+)\s*years?", jd_text, re.IGNORECASE)
    extracted_min_years = None
    extracted_max_years = None
    if exp_match:
        extracted_min_years = int(exp_match.group(1))
        extracted_max_years = int(exp_match.group(2))
        exp_range = f"{extracted_min_years}-{extracted_max_years} years"
    else:
        exp_range = "not specified"

    # 2. Location extraction
    cities_list = [
        "pune", "noida", "hyderabad", "mumbai", "delhi", "gurugram", 
        "gurgaon", "bangalore", "bengaluru", "chennai", "new delhi", "ncr",
        "kolkata", "ahmedabad", "jaipur", "kochi", "coimbatore", "indore", "bhopal"
    ]
    found_cities = []
    # Check if there is a "location" line
    location_line = ""
    for line in jd_text.splitlines():
        if "location" in line.lower():
            location_line = line
            break
            
    search_source = location_line if location_line else jd_text
    for city in cities_list:
        if re.search(rf"\b{city}\b", search_source, re.IGNORECASE):
            found_cities.append(city.title())
            
    found_cities = list(set(found_cities))
    location_str = ", ".join(found_cities) if found_cities else "not specified"

    # 3. Skills extraction
    scorer_instance = CandidateScorer()
    master_skills = scorer_instance.MUST_HAVE_SKILLS + scorer_instance.NICE_TO_HAVE_SKILLS
    found_skills = []
    for skill in master_skills:
        if re.search(rf"\b{re.escape(skill)}\b", jd_text, re.IGNORECASE):
            found_skills.append(skill)
            
    found_skills = list(set(found_skills))
    skills_str = ", ".join(found_skills) if found_skills else "none found"

    st.markdown(f"""
    <div class="jd-requirements-box">
        📋 <strong>Detected requirements:</strong><br>
        &nbsp;&nbsp;• <strong>Experience:</strong> {exp_range}<br>
        &nbsp;&nbsp;• <strong>Skills:</strong> {skills_str}<br>
        &nbsp;&nbsp;• <strong>Locations:</strong> {location_str}
    </div>
    """, unsafe_allow_html=True)
    st.warning("⚠️ **Note:** When a custom JD is provided, scoring dynamically adapts to its detected skills, experience range, and locations. This sandbox feature is separate from the official hackathon submission, which always scores against the competition's released JD via rank.py.")
    
    jd_override = {
        'min_years': extracted_min_years,
        'max_years': extracted_max_years,
        'skills': found_skills if found_skills else None,
        'locations': found_cities if found_cities else None,
    }
else:
    st.caption("ℹ️ **Using default JD:** Senior AI Engineer — Founding Team (Pune/Noida, 5-9 yrs, retrieval/ranking systems)")

st.divider()

# SECTION 2 — Sidebar
# ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown("**Scoring Weights**")

    weight_data = [
        ("Skills Match", 30, "#6C3CE1"),
        ("Career Quality", 28, "#FF6B6B"),
        ("Experience Fit", 12, "#2196F3"),
        ("Behavioral Signals", 20, "#4CAF50"),
        ("Location Fit", 7, "#FF9800"),
        ("Certifications", 3, "#00BCD4"),
    ]

    weights_html = ""
    for label, pct, color in weight_data:
        # Scale width: max weight is 30, so we scale to percentage of 100
        bar_width = int((pct / 30) * 100)
        weights_html += f"""
        <div class="sidebar-weight-bar">
            <div class="sw-label">
                <span>{label}</span>
                <span>{pct}%</span>
            </div>
            <div class="sw-track">
                <div class="sw-fill" style="width:{bar_width}%; background:{color};"></div>
            </div>
        </div>
        """
    st.markdown(weights_html, unsafe_allow_html=True)
    st.markdown("")

    with st.expander("ℹ️ How it works"):
        st.markdown("""
**6 Scoring Components:**
- **Skills Match (30%)** — Matches candidate skills against MUST_HAVE (Python, embeddings, vector DBs, NLP, transformers) and NICE_TO_HAVE lists. Uses a *trust multiplier* based on endorsements, proficiency, and usage duration to penalize keyword stuffing.
- **Career Quality (28%)** — Rewards product-company experience in tech/AI industries. Penalizes candidates who spent >60% of career at consulting firms (TCS, Infosys, Wipro, etc.).
- **Experience Fit (12%)** — Ideal range is **5–9 years**. Scores peak at 1.0 for this range and taper off for junior or very senior profiles.
- **Behavioral Signals (20%)** — Evaluates recency of activity, recruiter response rate, notice period, interview completion rate, and GitHub activity.
- **Location (7%)** — Prefers Pune, Noida, Hyderabad, Mumbai, Delhi NCR, Bangalore, Chennai. Lower scores for non-India locations.
- **Certifications (3%)** — Rewards relevant certifications in AI/ML or cloud architectures.

**Honeypot Detection:**
- ⏱️ **Timeline Check** — Flags impossible date-duration gaps
- 🎭 **Skill Fraud** — Catches zero-duration expert claims
- 📊 **Experience Mismatch** — Detects inflated years
- 🔀 **Title Mismatch** — Flags AI skills on non-tech titles
- 📝 **Assessment Mismatch** — Flags self-reported expert/advanced skills that contradict platform test results
        """)

    st.markdown("---")
    st.markdown("**Target Role**")
    st.caption("Senior AI Engineer — Founding Team at Redrob. Focus on production ML systems, embeddings, vector search, and ranking infrastructure.")


# ──────────────────────────────────────────────────────────────────────
# Helper: Parse uploaded file into list of candidate dicts
# ──────────────────────────────────────────────────────────────────────
def parse_candidate_file(file_bytes: bytes, filename: str) -> list:
    """
    Parses uploaded file bytes into a list of candidate dictionaries.

    Supports both JSON array format and JSON Lines (.jsonl) format.

    Args:
        file_bytes (bytes): Raw file content from st.file_uploader.
        filename (str): Original filename for format detection.

    Returns:
        list: List of parsed candidate dictionaries.
    """
    text = file_bytes.decode("utf-8")
    candidates = []

    # Try JSON array first
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            candidates = json.loads(stripped)
            return candidates
        except json.JSONDecodeError:
            pass

    # Fall back to JSONL (one JSON object per line)
    for line_num, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            candidates.append(json.loads(line))
        except json.JSONDecodeError:
            warnings.warn(f"Skipped malformed line {line_num}")

    return candidates


# ──────────────────────────────────────────────────────────────────────
# Helper: Run the full scoring pipeline
# ──────────────────────────────────────────────────────────────────────
def run_pipeline(candidates: list, jd_override: dict = None) -> dict:
    """
    Executes the scoring and honeypot detection pipeline on all candidates.

    Args:
        candidates (list): List of candidate dicts.
        jd_override (dict): Optional scoring parameter overrides.

    Returns:
        dict: Pipeline results containing scored_results, honeypot_results, 
              sorted_results, and summary statistics.
    """
    scorer = CandidateScorer(jd_override=jd_override)
    detector = HoneypotDetector()

    scored_results = []
    honeypot_results = []

    for candidate in candidates:
        cand_id = candidate.get("candidate_id", "Unknown")

        try:
            honeypot_result = detector.is_honeypot(candidate)
        except Exception as e:
            st.error(f"Honeypot check failed for "
                     f"{cand_id}: {type(e).__name__}: {e}")
            honeypot_result = {
                "candidate_id": cand_id,
                "is_honeypot": False,
                "flagged": False,
                "honeypot_score": 0.0,
                "flags": []
            }

        try:
            if honeypot_result.get("is_honeypot") or honeypot_result.get("flagged"):
                honeypot_result["is_honeypot"] = True
                honeypot_results.append(honeypot_result)
                flags_joined = "; ".join(honeypot_result["flags"])
                scored_results.append({
                    "candidate_id": cand_id,
                    "final_score": 0.0,
                    "skills_score": 0.0,
                    "career_score": 0.0,
                    "experience_score": 0.0,
                    "behavioral_score": 0.0,
                    "location_score": 0.0,
                    "certifications_score": 0.0,
                    "reasoning": f"DISQUALIFIED: {flags_joined}",
                    "is_honeypot": True,
                    "honeypot_result": honeypot_result,
                    # Carry forward profile fields for display
                    "current_title": candidate.get("profile", {}).get("current_title", "N/A"),
                    "years_exp": candidate.get("profile", {}).get("years_of_experience", 0),
                    "location": candidate.get("profile", {}).get("location", "N/A"),
                })
            else:
                score_result = scorer.score(candidate)
                profile = candidate.get("profile", {})
                score_result["is_honeypot"] = False
                score_result["honeypot_result"] = honeypot_result
                score_result["current_title"] = profile.get("current_title", "N/A")
                score_result["years_exp"] = profile.get("years_of_experience", 0)
                score_result["location"] = profile.get("location", "N/A")
                scored_results.append(score_result)
        except Exception as e:
            st.error(f"Scoring pipeline failed for candidate {cand_id}: {type(e).__name__}: {e}")
            scored_results.append({
                "candidate_id": cand_id,
                "final_score": 0.0,
                "skills_score": 0.0,
                "career_score": 0.0,
                "experience_score": 0.0,
                "behavioral_score": 0.0,
                "location_score": 0.0,
                "certifications_score": 0.0,
                "reasoning": "ERROR: could not score",
                "is_honeypot": False,
                "honeypot_result": {
                    "candidate_id": cand_id,
                    "is_honeypot": False,
                    "honeypot_score": 0.0,
                    "flags": []
                },
                "current_title": "N/A",
                "years_exp": 0,
                "location": "N/A",
            })

    # Sort: final_score descending, candidate_id ascending for tiebreak
    scored_results.sort(key=lambda x: (-x["final_score"], x["candidate_id"]))

    return {
        "all_results": scored_results,
        "honeypots": honeypot_results,
        "total": len(candidates),
        "honeypot_count": len(honeypot_results),
        "jd_override": jd_override
    }



# ──────────────────────────────────────────────────────────────────────
# SECTION 3 — File Upload
# ──────────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload a candidates file (.json, .jsonl, .gz, or .jsonl.gz)",
    type=["json", "jsonl", "gz"],
    help="Upload a candidates file (.json, .jsonl, or .jsonl.gz). Streaming-based — handles files of any size."
)

# Check if file has changed or was removed
current_file_id = None
if uploaded_file is not None:
    current_file_id = f"{uploaded_file.name}_{uploaded_file.size}"

if "last_file_id" not in st.session_state:
    st.session_state["last_file_id"] = None

if current_file_id != st.session_state["last_file_id"]:
    # Reset all cached result keys
    for key in ["pipeline_results", "ran", "scored_results", "honeypot_results", "ranking_complete"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state["last_file_id"] = current_file_id

if uploaded_file is None:
    # Friendly placeholder when no file is uploaded
    st.markdown("""
    <div class="upload-zone">
        <div class="upload-icon">📁</div>
        <h3>Upload a Candidate File to Begin</h3>
        <p>
            Drag and drop a <code>.json</code>, <code>.jsonl</code>, or <code>.gz</code> candidate file above, 
            or use the file picker. The app will score every candidate against the 
            <strong>Senior AI Engineer</strong> role, detect honeypot profiles, 
            and generate a ranked submission CSV.
        </p>
        <p style="margin-top:16px; font-size:0.82rem; color:#999;">
            Supports JSON arrays, JSON Lines, and compressed formats &nbsp;·&nbsp; Streaming-based — handles files of any size.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="app-footer">
        <span class="footer-title">Built for Redrob Hackathon</span> &nbsp;|&nbsp; 
        Intelligent Candidate Discovery Challenge 2026 &nbsp;|&nbsp; 
        Powered by 6-Component AI Scoring Engine<br>
        <a href="https://github.com/vishalsurya00/Intelligent-Candidate-Discovery" target="_blank">⭐ GitHub Repository</a>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ──────────────────────────────────────────────────────────────────────
# SECTION 4 — File loaded preview
# ──────────────────────────────────────────────────────────────────────
if uploaded_file is not None:
    import tempfile
    import gzip
    import os
    from loader import CandidateLoader

    try:
        uploaded_file.seek(0)
        # Decompress if file is gzipped
        if uploaded_file.name.endswith(".gz"):
            with gzip.GzipFile(fileobj=uploaded_file, mode="rb") as gz:
                decompressed_data = gz.read()
            # Write to a plain temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode="wb") as temp_f:
                temp_f.write(decompressed_data)
                temp_file_path = temp_f.name
        else:
            # Write plain bytes directly to temp file
            file_bytes = uploaded_file.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode="wb") as temp_f:
                temp_f.write(file_bytes)
                temp_file_path = temp_f.name

        # Load candidates using CandidateLoader
        loader = CandidateLoader(temp_file_path)
        candidates = loader.load_all()
    except Exception as e:
        st.error(f"❌ Error parsing candidate file: {e}")
        candidates = []
    finally:
        # Clean up temp file
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

    if not candidates:
        st.error("❌ No valid candidates found in the uploaded file. Please check the format.")
    else:
        st.markdown(f"""
        <div class="file-loaded-banner">
            ✅ File loaded: <strong>{len(candidates)}</strong> candidates found
        </div>
        """, unsafe_allow_html=True)

        # Preview table of first 5 candidates
        preview_rows = []
        for c in candidates[:5]:
            profile = c.get("profile", {})
            signals = c.get("redrob_signals", {})
            preview_rows.append({
                "Candidate ID": c.get("candidate_id", "N/A"),
                "Current Title": profile.get("current_title", "N/A"),
                "Years of Experience": profile.get("years_of_experience", "N/A"),
                "Location": profile.get("location", "N/A"),
                "Open to Work": "✅ Yes" if signals.get("open_to_work_flag") else "❌ No",
            })

        st.markdown("**Preview (first 5 candidates):**")
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

        # Run button
        run_clicked = st.button("🚀 Run Ranker", type="primary", use_container_width=True)

        # ──────────────────────────────────────────────────────────────────────
        # SECTION 5 — Results (after clicking Run Ranker)
        # ──────────────────────────────────────────────────────────────────────
        # Use session_state to persist results across reruns
        if run_clicked:
            with st.spinner("🔍 Scoring candidates and detecting honeypots..."):
                results = run_pipeline(candidates, jd_override=jd_override if custom_jd_provided else None)
                st.session_state["pipeline_results"] = results
                st.session_state["ran"] = True

        if not st.session_state.get("ran"):
            st.info("👆 Click **Run Ranker** to score all candidates and see results.")
        else:
            results = st.session_state["pipeline_results"]
            all_results = results["all_results"]
            honeypots = results["honeypots"]
            total = results["total"]
            honeypot_count = results["honeypot_count"]

            # Summary stats
            clean_count = total - honeypot_count
            top_score = all_results[0]["final_score"] if all_results else 0.0
            avg_score = sum(r["final_score"] for r in all_results if not r.get("is_honeypot")) / max(clean_count, 1)

            # Metric Cards — styled 5-column grid
            hp_pulse = "mc-pulse" if honeypot_count > 0 else ""
            st.markdown(f"""
            <div class="metric-card-grid">
                <div class="metric-card-v2 mc-purple">
                    <div class="mc-icon">📋</div>
                    <div class="mc-label">Total</div>
                    <div class="mc-value">{total}</div>
                </div>
                <div class="metric-card-v2 mc-green">
                    <div class="mc-icon">✅</div>
                    <div class="mc-label">Scored</div>
                    <div class="mc-value">{clean_count}</div>
                </div>
                <div class="metric-card-v2 mc-coral {hp_pulse}">
                    <div class="mc-icon">🚨</div>
                    <div class="mc-label">Honeypots</div>
                    <div class="mc-value">{honeypot_count}</div>
                </div>
                <div class="metric-card-v2 mc-orange">
                    <div class="mc-icon">🏆</div>
                    <div class="mc-label">Top Score</div>
                    <div class="mc-value">{top_score:.4f}</div>
                </div>
                <div class="metric-card-v2 mc-blue">
                    <div class="mc-icon">📊</div>
                    <div class="mc-label">Avg Score</div>
                    <div class="mc-value">{avg_score:.4f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Show caption if custom JD was used
            used_override = results.get("jd_override")
            if used_override:
                min_years = used_override.get('min_years')
                max_years = used_override.get('max_years')
                skills = used_override.get('skills', []) or []
                locations = used_override.get('locations', []) or []
                st.caption(f"Scored against custom JD: {min_years}-{max_years} yrs, "
                           f"skills: {', '.join(skills[:5])}{'...' if len(skills)>5 else ''}, "
                           f"locations: {', '.join(locations)}")

            st.divider()

            # ──────────────────────────────────────────────────────────────────────
            # Results Tabs
            # ──────────────────────────────────────────────────────────────────────
            tab1, tab2, tab3, tab4 = st.tabs([
                "🏆 Top Rankings",
                "📊 Score Breakdown",
                "🚨 Honeypot Report",
                "📥 Download"
            ])

            # ─── TAB 1: Top Rankings ─────────────────────────────────────────────
            with tab1:
                st.markdown('<p class="gradient-section-header">🏆 Top Ranked Candidates</p>', unsafe_allow_html=True)

                top_display = [r for r in all_results if not r.get("is_honeypot")][:20]

                ranking_rows = []
                for idx, r in enumerate(top_display, start=1):
                    # Medal emoji for top 3
                    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, "")
                    rank_label = f"{medal} {idx}" if medal else str(idx)
                    ranking_rows.append({
                        "Rank": rank_label,
                        "Candidate ID": r["candidate_id"],
                        "Score": round(r["final_score"], 4),
                        "Current Title": r.get("current_title", "N/A"),
                        "Years Exp": r.get("years_exp", 0),
                        "Location": r.get("location", "N/A"),
                        "Reasoning": r["reasoning"][:80] + "..." if len(r.get("reasoning", "")) > 80 else r.get("reasoning", ""),
                    })

                if ranking_rows:
                    df_rankings = pd.DataFrame(ranking_rows)
                    st.dataframe(
                        df_rankings,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Score": st.column_config.ProgressColumn(
                                "Score",
                                help="Final weighted score (0–1)",
                                format="%.4f",
                                min_value=0.0,
                                max_value=1.0,
                            ),
                            "Rank": st.column_config.TextColumn("Rank", width="small"),
                            "Years Exp": st.column_config.NumberColumn("Years Exp", format="%.1f"),
                            "Reasoning": st.column_config.TextColumn("Reasoning", width="large"),
                        },
                    )

                    # Expandable reasoning for top candidates
                    with st.expander("🔍 Full reasoning for top candidates"):
                        for idx, r in enumerate(top_display[:5], start=1):
                            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"#{idx}")
                            st.markdown(f"**{medal} {r['candidate_id']}** — Score: `{r['final_score']:.4f}`")
                            st.caption(r["reasoning"])
                            st.markdown("---")
                else:
                    st.warning("No scored candidates to display.")

            # ─── TAB 2: Score Breakdown ──────────────────────────────────────────
            with tab2:
                st.markdown('<p class="gradient-section-header">📊 Component Score Breakdown (Top 10)</p>', unsafe_allow_html=True)

                top10 = [r for r in all_results if not r.get("is_honeypot")][:10]

                if top10:
                    # Build breakdown dataframe
                    breakdown_rows = []
                    for r in top10:
                        short_id = r["candidate_id"][-5:]  # e.g., "00037"
                        breakdown_rows.append({
                            "Candidate": short_id,
                            "Skills": round(r["skills_score"], 4),
                            "Career": round(r["career_score"], 4),
                            "Experience": round(r["experience_score"], 4),
                            "Behavioral": round(r["behavioral_score"], 4),
                            "Location": round(r["location_score"], 4),
                            "Certifications": round(r["certifications_score"], 4),
                        })

                    df_breakdown = pd.DataFrame(breakdown_rows)

                    # Plotly grouped bar chart with component colors
                    try:
                        import plotly.graph_objects as go

                        component_colors = {
                            "Skills": "#6C3CE1",
                            "Career": "#FF6B6B",
                            "Experience": "#2196F3",
                            "Behavioral": "#4CAF50",
                            "Location": "#FF9800",
                            "Certifications": "#00BCD4",
                        }

                        fig = go.Figure()
                        for comp, color in component_colors.items():
                            fig.add_trace(go.Bar(
                                name=comp,
                                x=df_breakdown["Candidate"],
                                y=df_breakdown[comp],
                                marker_color=color,
                                marker_line_width=0,
                            ))

                        fig.update_layout(
                            barmode="group",
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Inter", color="#1A1A2E"),
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="center",
                                x=0.5,
                                font=dict(size=12),
                            ),
                            xaxis=dict(
                                title="Candidate",
                                gridcolor="#E8E8F4",
                            ),
                            yaxis=dict(
                                title="Score",
                                gridcolor="#E8E8F4",
                                range=[0, 1],
                            ),
                            margin=dict(l=40, r=20, t=40, b=40),
                            height=420,
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except ImportError:
                        # Fallback to streamlit bar chart if plotly unavailable
                        df_chart = df_breakdown.set_index("Candidate")
                        st.bar_chart(df_chart)

                    # Metric cards for averages
                    st.markdown('<p class="gradient-section-header" style="font-size:1.1rem;">Average Scores (Top 10)</p>', unsafe_allow_html=True)

                    avg_skills = sum(r["skills_score"] for r in top10) / len(top10)
                    avg_career = sum(r["career_score"] for r in top10) / len(top10)
                    avg_exp = sum(r["experience_score"] for r in top10) / len(top10)
                    avg_behav = sum(r["behavioral_score"] for r in top10) / len(top10)
                    avg_loc = sum(r["location_score"] for r in top10) / len(top10)
                    avg_certs = sum(r["certifications_score"] for r in top10) / len(top10)

                    avg_data = [
                        ("🧠", "Skills", avg_skills, "#6C3CE1"),
                        ("💼", "Career", avg_career, "#FF6B6B"),
                        ("📅", "Experience", avg_exp, "#2196F3"),
                        ("📈", "Behavioral", avg_behav, "#4CAF50"),
                        ("📍", "Location", avg_loc, "#FF9800"),
                        ("🎓", "Certs", avg_certs, "#00BCD4"),
                    ]

                    cols = st.columns(6)
                    for col, (icon, label, val, color) in zip(cols, avg_data):
                        with col:
                            st.markdown(f"""
                            <div class="breakdown-card">
                                <div class="bc-icon">{icon}</div>
                                <div class="bc-label" style="color:{color};">{label}</div>
                                <div class="bc-value">{val:.4f}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    # Detailed breakdown table
                    st.markdown('<p class="gradient-section-header" style="font-size:1.1rem; margin-top:1rem;">Detailed Scores Table</p>', unsafe_allow_html=True)
                    st.dataframe(df_breakdown, use_container_width=True, hide_index=True)
                else:
                    st.warning("No scored candidates available for breakdown.")

            # ─── TAB 3: Honeypot Report ──────────────────────────────────────────
            with tab3:
                st.markdown('<p class="gradient-section-header">🚨 Honeypot Detection Report</p>', unsafe_allow_html=True)

                honeypots = [r["honeypot_result"] for r in all_results if r.get("is_honeypot")]

                if len(honeypots) == 0:
                    st.markdown("""
                    <div class="honeypot-clear">
                        <span class="big-check">✅</span>
                        All Clear — No Fraudulent Profiles Detected
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="honeypot-alert-header">
                        ⚠️ {len(honeypots)} honeypot candidate(s) detected and disqualified
                    </div>
                    """, unsafe_allow_html=True)

                    # Individual danger cards
                    for h in honeypots:
                        flags_html = "".join(
                            f'<span class="flag-badge">{flag}</span>' for flag in h["flags"]
                        )
                        risk_pct = int(h["honeypot_score"] * 100)
                        st.markdown(f"""
                        <div class="honeypot-danger-card">
                            <strong style="color:#1A1A2E;">🆔 {h["candidate_id"]}</strong>
                            <div style="margin-top:6px; font-size:0.85rem; color:#666888;">
                                Risk Score: <strong style="color:#FF6B6B;">{h["honeypot_score"]:.2f}</strong>
                            </div>
                            <div class="risk-bar-track">
                                <div class="risk-bar-fill" style="width:{risk_pct}%;"></div>
                            </div>
                            <div style="margin-top:8px;">{flags_html}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # Also show a summary table
                    honeypot_rows = []
                    for h in honeypots:
                        honeypot_rows.append({
                            "Candidate ID": h["candidate_id"],
                            "Honeypot Score": round(h["honeypot_score"], 2),
                            "Flags": " | ".join(h["flags"]),
                        })

                    df_honeypots = pd.DataFrame(honeypot_rows)
                    st.dataframe(
                        df_honeypots,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Honeypot Score": st.column_config.ProgressColumn(
                                "Honeypot Score",
                                help="Fraud confidence (0=clean, 1=definitely fake)",
                                format="%.2f",
                                min_value=0.0,
                                max_value=1.0,
                            ),
                            "Flags": st.column_config.TextColumn("Flags", width="large"),
                        },
                    )

                    # Show detection breakdown
                    st.markdown('<p class="gradient-section-header" style="font-size:1.1rem;">Detection Method Summary</p>', unsafe_allow_html=True)
                    method_counts = {
                        "Timeline": 0,
                        "Skill Fraud": 0,
                        "Experience": 0,
                        "Title Mismatch": 0,
                        "Assessment Mismatch": 0
                    }
                    for h in honeypots:
                        for flag in h["flags"]:
                            flag_lower = flag.lower()
                            if "timeline" in flag_lower:
                                method_counts["Timeline"] += 1
                            elif "skill fraud" in flag_lower:
                                method_counts["Skill Fraud"] += 1
                            elif "experience" in flag_lower:
                                method_counts["Experience"] += 1
                            elif "title" in flag_lower:
                                method_counts["Title Mismatch"] += 1
                            elif "assessment" in flag_lower:
                                method_counts["Assessment Mismatch"] += 1

                    method_df = pd.DataFrame([
                        {"Method": k, "Detections": v} for k, v in method_counts.items() if v > 0
                    ])
                    if not method_df.empty:
                        st.bar_chart(method_df.set_index("Method"))

            # ─── TAB 4: Download ─────────────────────────────────────────────────
            with tab4:
                st.markdown('<p class="gradient-section-header">📥 Download Submission CSV</p>', unsafe_allow_html=True)

                # Generate full submission CSV in memory
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["candidate_id", "rank", "score", "reasoning"])

                submission_rows = all_results[:100]  # Top 100 for submission
                for pos, r in enumerate(submission_rows, start=1):
                    writer.writerow([
                        r["candidate_id"],
                        pos,
                        round(r["final_score"], 6),
                        r["reasoning"],
                    ])

                csv_content = output.getvalue()

                st.download_button(
                    label="⬇️ Download submission.csv",
                    data=csv_content,
                    file_name="submission.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                )

                # Preview first 10 rows
                st.markdown("**Preview (first 10 rows):**")
                preview_csv_rows = []
                for pos, r in enumerate(submission_rows[:10], start=1):
                    preview_csv_rows.append({
                        "Candidate ID": r["candidate_id"],
                        "Rank": pos,
                        "Score": round(r["final_score"], 6),
                        "Reasoning": r["reasoning"][:120] + "..." if len(r.get("reasoning", "")) > 120 else r.get("reasoning", ""),
                    })
                st.dataframe(pd.DataFrame(preview_csv_rows), use_container_width=True, hide_index=True)

                # Validation summary
                st.markdown('<p class="gradient-section-header" style="font-size:1.1rem; margin-top:1rem;">✅ Submission Validation</p>', unsafe_allow_html=True)

                scored_ids = [r["candidate_id"] for r in submission_rows]
                unique_ids = len(set(scored_ids)) == len(scored_ids)
                scores_list = [r["final_score"] for r in submission_rows]
                non_increasing = all(scores_list[i] >= scores_list[i + 1] for i in range(len(scores_list) - 1))
                hp_in_top = sum(1 for r in submission_rows if r.get("is_honeypot"))

                checks = [
                    (f"✅ <strong>{len(submission_rows)}</strong> candidates ranked", True),
                    ("✅ Scores are non-increasing" if non_increasing else "❌ Scores are NOT non-increasing", non_increasing),
                    ("✅ No duplicate IDs" if unique_ids else "❌ Duplicate IDs found", unique_ids),
                    (f"✅ <strong>{honeypot_count}</strong> honeypots excluded from scoring" if hp_in_top == 0 else f"⚠️ {hp_in_top} honeypots still in top results", hp_in_top == 0),
                ]

                for label, passed in checks:
                    vc_class = "" if passed else "vc-fail"
                    st.markdown(f"""
                    <div class="validation-card {vc_class}">
                        <span class="vc-dot"></span>
                        <span>{label}</span>
                    </div>
                    """, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-footer">
    <span class="footer-title">Built for Redrob Hackathon</span> &nbsp;|&nbsp; 
    Intelligent Candidate Discovery Challenge 2026 &nbsp;|&nbsp; 
    Powered by 6-Component AI Scoring Engine<br>
    <a href="https://github.com/vishalsurya00/Intelligent-Candidate-Discovery" target="_blank">⭐ GitHub Repository</a>
</div>
""", unsafe_allow_html=True)
