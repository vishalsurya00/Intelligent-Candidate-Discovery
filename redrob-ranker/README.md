# Redrob Candidate Ranker

A Python project for a candidate ranking system for hiring hackathons.

## Project Structure
```
redrob-ranker/
├── rank.py           (Main ranker — empty for now, just a stub)
├── app.py            (Streamlit app — empty stub)
├── loader.py         (Data loader — fully built)
├── scorer.py         (Scorer — empty stub)
├── requirements.txt  (List of project dependencies)
└── README.md         (This README file)
```

## Features of the Candidate Loader (`loader.py`)
- Loads candidate data from standard JSONL (JSON lines) files.
- Safe and robust parsing that skips malformed lines with warnings.
- Tracks loading progress, printing status updates every 10,000 records.
- Reports loading statistics including execution time and memory usage metrics.
- Provides utility methods to load all records or a configurable sample.

## Getting Started

### Installation
Ensure you have the required dependencies installed:
```bash
pip install -r requirements.txt
```

### Running the Loader Tests
To verify the candidate loader functionality and test it against a sample candidate file:
```bash
python loader.py
```
