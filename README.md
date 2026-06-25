# Redrob Intelligent Candidate Ranker
## Redrob Hackathon — Intelligent Candidate Discovery Challenge 2026

## Overview
The **Redrob Intelligent Candidate Ranker** ranks 100,000 candidates for a Senior AI Engineer founding-team role. It uses a 6-component scoring engine with 5-check honeypot/fraud detection to identify high-quality applicants. The entire pipeline runs in roughly 60-75 seconds on CPU only, with no network calls and no LLM calls at scoring time.

## Architecture
- **[redrob-ranker/loader.py](redrob-ranker/loader.py)**: Loads candidates from `.json`, `.jsonl`, `.gz`, or `.jsonl.gz` — auto-detects format, streams large files (tested up to 465MB) so memory usage stays flat regardless of file size.
- **[redrob-ranker/scorer.py](redrob-ranker/scorer.py)**: 6-component scoring engine (skills 30%, career 28%, experience 12%, behavioral 20%, location 7%, certifications 3%) using all 23 `redrob_signals` fields; generates unique, JD-connected, fact-specific reasoning per candidate.
- **[redrob-ranker/honeypot_detector.py](redrob-ranker/honeypot_detector.py)**: 5 independent fraud checks — timeline impossibility, skill fraud/keyword stuffing, experience mismatch, title-skill mismatch, and assessment-score contradiction (claimed proficiency vs platform-verified test score).
- **[redrob-ranker/rank.py](redrob-ranker/rank.py)**: Main pipeline — load, ID cross-check, score + honeypot filter, sort, write top-100 CSV. This is the `reproduce_command` entry point.
- **[redrob-ranker/app.py](redrob-ranker/app.py)**: Streamlit sandbox UI — file upload (any size via streaming), optional JD paste/upload section, live ranking, 4-tab results view (Top Rankings, Score Breakdown, Honeypot Report, Download).

## Setup Instructions
### Requirements
- Python 3.10+
- `pip install -r requirements.txt`

### Running the Ranker (reproduce_command)
```bash
python rank.py --candidates candidates.jsonl --out submission.csv
```
This is the exact command used to produce the submitted CSV. Verified to run successfully from a clean git clone with no machine-specific dependencies.

### Running the Streamlit App locally
```bash
streamlit run app.py
```

## Performance (most recent verified run)
- 100,000 candidates scored in ~60-75 seconds total pipeline time
- 1,253 honeypot/fraud candidates detected and excluded — consistent across multiple independent runs including a fresh-clone reproducibility test
- Top 100 score range: 0.905 to 0.980
- Validated with the official `validate_submission.py`: **PASSED**

## Scoring Components

| Component | Weight | What it checks |
| :--- | :--- | :--- |
| **Skills Match** | 30% | MUST_HAVE/NICE_TO_HAVE skill match with a trust multiplier from endorsements, duration, proficiency, and platform skill-assessment scores; penalized for non-technical current titles |
| **Career Quality** | 28% | Consulting-firm penalty, AI/ML role detection from titles and descriptions, company size/industry, tenure stability |
| **Experience Fit** | 12% | Curve peaking at 5-9 years |
| **Behavioral Signals** | 20% | All 23 `redrob_signals` — recency, availability, notice period, responsiveness, platform trust, market demand, profile quality, GitHub activity |
| **Location** | 7% | Tier-1/Tier-2 Indian cities, relocation willingness |
| **Certifications** | 3% | AI/ML-relevant certifications, recency bonus |

## Honeypot / Fraud Detection
5 independent checks, each contributing to a 0-1 `honeypot_score`:
1. **Timeline impossibility** — career dates don't match stated duration
2. **Skill fraud** — "expert" proficiency with zero usage duration, or unrealistic skill-count (20+)
3. **Experience mismatch** — stated years vs sum of career history
4. **Title-skill mismatch** — AI/ML skills claimed but all career titles are non-technical
5. **Assessment mismatch** — claimed proficiency contradicts the platform's own `skill_assessment_scores`

Any flagged candidate is excluded by setting `final_score` to 0.0 with a `DISQUALIFIED` reasoning string, ensuring honeypots never appear in the top 100 regardless of other scores.

## Sandbox
Live demo: [https://intelligent-candidate-discovery-cuvce8kvpupbfnud55zucv.streamlit.app](https://intelligent-candidate-discovery-cuvce8kvpupbfnud55zucv.streamlit.app)

Upload `sample_candidates.json` to test. Includes an optional Job Description input (paste or upload) — currently a preview feature for demonstrating generalizability; scoring uses the hackathon's official JD to ensure accurate evaluation against the competition's grading criteria.

## Reproducibility
Verified by cloning the repository into a clean directory, installing dependencies from `requirements.txt`, and running the `reproduce_command` against the full `candidates.jsonl` — produced an identical 100-row, validator-passing `submission.csv` with 1,253 honeypots excluded, matching prior runs exactly.
