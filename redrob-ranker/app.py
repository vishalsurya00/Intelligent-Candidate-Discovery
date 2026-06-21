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
# Custom CSS for a polished, premium look
# ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Import premium font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Header styling */
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
        letter-spacing: -0.02em;
    }
    .sub-title {
        font-size: 1.15rem;
        font-weight: 500;
        color: #6c63ff;
        margin-top: -0.3rem;
    }
    .hackathon-badge {
        display: inline-block;
        background: linear-gradient(135deg, #667eea20, #764ba220);
        border: 1px solid #667eea40;
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.78rem;
        font-weight: 500;
        color: #667eea;
        margin-top: 6px;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #f8f9ff 0%, #eef0ff 100%);
        border: 1px solid #e0e4ff;
        border-radius: 12px;
        padding: 18px 20px;
        text-align: center;
    }
    .metric-card h3 {
        font-size: 0.78rem;
        font-weight: 600;
        color: #667eea;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 4px;
    }
    .metric-card .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a1a2e;
    }

    /* Stat pills */
    .stat-row {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin: 12px 0;
    }
    .stat-pill {
        background: #f0f2ff;
        border: 1px solid #dde0ff;
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 0.85rem;
        font-weight: 500;
        color: #3b3f7a;
    }
    .stat-pill .num {
        font-weight: 700;
        color: #667eea;
    }

    /* Upload area styling */
    .upload-zone {
        background: linear-gradient(135deg, #fafbff 0%, #f0f2ff 100%);
        border: 2px dashed #c5caff;
        border-radius: 16px;
        padding: 48px 32px;
        text-align: center;
    }
    .upload-zone h3 {
        color: #3b3f7a;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .upload-zone p {
        color: #7a7faa;
        font-size: 0.92rem;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8f9ff 0%, #eef0ff 100%);
    }
    .sidebar-weight {
        display: flex;
        justify-content: space-between;
        padding: 6px 0;
        border-bottom: 1px solid #e4e7ff;
        font-size: 0.88rem;
    }
    .sidebar-weight .label {
        color: #3b3f7a;
        font-weight: 500;
    }
    .sidebar-weight .value {
        color: #667eea;
        font-weight: 700;
    }

    /* Footer */
    .footer {
        text-align: center;
        padding: 24px 0 12px;
        color: #aaa;
        font-size: 0.8rem;
        border-top: 1px solid #eee;
        margin-top: 40px;
    }

    /* Validation checkmarks */
    .check-item {
        font-size: 0.92rem;
        padding: 4px 0;
        color: #2d7a3a;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# SECTION 1 — Header
# ──────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">🎯 Redrob Intelligent Candidate Ranker</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Senior AI Engineer — Founding Team</p>', unsafe_allow_html=True)
st.markdown('<span class="hackathon-badge">Redrob Hackathon &nbsp;|&nbsp; Intelligent Candidate Discovery Challenge</span>', unsafe_allow_html=True)
st.divider()

# ──────────────────────────────────────────────────────────────────────
# SECTION 1.5 — Job Description
# ──────────────────────────────────────────────────────────────────────
st.subheader("📋 Job Description")
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

    st.info(f"📋 **Detected requirements:**\n- **Experience:** {exp_range}\n- **Skills:** {skills_str}\n- **Locations:** {location_str}")
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

    weights_html = """
    <div class="sidebar-weight"><span class="label">Skills Match</span><span class="value">30%</span></div>
    <div class="sidebar-weight"><span class="label">Career Quality</span><span class="value">28%</span></div>
    <div class="sidebar-weight"><span class="label">Experience Fit</span><span class="value">12%</span></div>
    <div class="sidebar-weight"><span class="label">Behavioral Signals</span><span class="value">20%</span></div>
    <div class="sidebar-weight"><span class="label">Location Fit</span><span class="value">7%</span></div>
    <div class="sidebar-weight" style="border-bottom:none;"><span class="label">Certifications</span><span class="value">3%</span></div>
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
        <h3>📂 Upload a Candidate File to Begin</h3>
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

    st.markdown('<div class="footer">Built for Redrob Hackathon &nbsp;|&nbsp; Intelligent Candidate Discovery Challenge 2026</div>', unsafe_allow_html=True)
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
        st.success(f"✅ File loaded: **{len(candidates)}** candidates found")

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

            st.markdown(f"""
            <div class="stat-row">
                <div class="stat-pill">📋 Total: <span class="num">{total}</span></div>
                <div class="stat-pill">✅ Scored: <span class="num">{clean_count}</span></div>
                <div class="stat-pill">🚨 Honeypots: <span class="num">{honeypot_count}</span></div>
                <div class="stat-pill">🏆 Top Score: <span class="num">{top_score:.4f}</span></div>
                <div class="stat-pill">📊 Avg Score: <span class="num">{avg_score:.4f}</span></div>
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
                st.markdown("### 🏆 Top Ranked Candidates")

                top_display = [r for r in all_results if not r.get("is_honeypot")][:20]

                ranking_rows = []
                for idx, r in enumerate(top_display, start=1):
                    ranking_rows.append({
                        "Rank": idx,
                        "Candidate ID": r["candidate_id"],
                        "Score": round(r["final_score"], 4),
                        "Current Title": r.get("current_title", "N/A"),
                        "Years Exp": r.get("years_exp", 0),
                        "Location": r.get("location", "N/A"),
                        "Reasoning": r["reasoning"],
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
                            "Rank": st.column_config.NumberColumn("Rank", width="small"),
                            "Years Exp": st.column_config.NumberColumn("Years Exp", format="%.1f"),
                            "Reasoning": st.column_config.TextColumn("Reasoning", width="large"),
                        },
                    )
                else:
                    st.warning("No scored candidates to display.")

            # ─── TAB 2: Score Breakdown ──────────────────────────────────────────
            with tab2:
                st.markdown("### 📊 Component Score Breakdown (Top 10)")

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
                    df_chart = df_breakdown.set_index("Candidate")
                    st.bar_chart(df_chart)

                    # Metric cards
                    st.markdown("#### Average Scores (Top 10)")
                    col1, col2, col3, col4 = st.columns(4)

                    avg_skills = sum(r["skills_score"] for r in top10) / len(top10)
                    avg_career = sum(r["career_score"] for r in top10) / len(top10)
                    avg_behav = sum(r["behavioral_score"] for r in top10) / len(top10)
                    avg_certs = sum(r["certifications_score"] for r in top10) / len(top10)

                    with col1:
                        st.markdown(f"""
                        <div class="metric-card">
                            <h3>Skills</h3>
                            <div class="metric-value">{avg_skills:.4f}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col2:
                        st.markdown(f"""
                        <div class="metric-card">
                            <h3>Career</h3>
                            <div class="metric-value">{avg_career:.4f}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col3:
                        st.markdown(f"""
                        <div class="metric-card">
                            <h3>Behavioral</h3>
                            <div class="metric-value">{avg_behav:.4f}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col4:
                        st.markdown(f"""
                        <div class="metric-card">
                            <h3>Certifications</h3>
                            <div class="metric-value">{avg_certs:.4f}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # Detailed breakdown table
                    st.markdown("#### Detailed Scores Table")
                    st.dataframe(df_breakdown, use_container_width=True, hide_index=True)
                else:
                    st.warning("No scored candidates available for breakdown.")

            # ─── TAB 3: Honeypot Report ──────────────────────────────────────────
            with tab3:
                st.markdown("### 🚨 Honeypot Detection Report")

                honeypots = [r["honeypot_result"] for r in all_results if r.get("is_honeypot")]

                if len(honeypots) == 0:
                    st.success("✅ No honeypot candidates detected in this dataset. All profiles appear clean.")
                else:
                    st.error(f"⚠️ **{len(honeypots)}** honeypot candidate(s) detected and disqualified.")

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
                    st.markdown("#### Detection Method Summary")
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
                st.markdown("### 📥 Download Submission CSV")

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
                st.markdown("#### ✅ Submission Validation")

                scored_ids = [r["candidate_id"] for r in submission_rows]
                unique_ids = len(set(scored_ids)) == len(scored_ids)
                scores_list = [r["final_score"] for r in submission_rows]
                non_increasing = all(scores_list[i] >= scores_list[i + 1] for i in range(len(scores_list) - 1))
                hp_in_top = sum(1 for r in submission_rows if r.get("is_honeypot"))

                checks = [
                    (f"✅ **{len(submission_rows)}** candidates ranked", True),
                    (f"✅ Scores are non-increasing" if non_increasing else "❌ Scores are NOT non-increasing", non_increasing),
                    (f"✅ No duplicate IDs" if unique_ids else "❌ Duplicate IDs found", unique_ids),
                    (f"✅ **{honeypot_count}** honeypots excluded from scoring" if hp_in_top == 0 else f"⚠️ {hp_in_top} honeypots still in top results", hp_in_top == 0),
                ]

                for label, passed in checks:
                    if passed:
                        st.markdown(f'<div class="check-item">{label}</div>', unsafe_allow_html=True)
                    else:
                        st.error(label)

# ──────────────────────────────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="footer">Built for Redrob Hackathon &nbsp;|&nbsp; Intelligent Candidate Discovery Challenge 2026</div>', unsafe_allow_html=True)

