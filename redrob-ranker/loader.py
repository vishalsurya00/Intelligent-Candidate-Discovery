"""
loader.py: Data loader module for candidate records.

This module contains the CandidateLoader class which is responsible for loading 
candidate profile data from JSON, JSON Lines (.jsonl), or gzipped (.gz) file formats.
It tracks statistics about loading time, memory consumption delta, and processes 
the data line-by-line using streaming to minimize memory overhead. It also safely 
skips malformed JSON records while emitting warnings.
"""

import os
import sys
import time
import json
import warnings
import gzip
from pathlib import Path

def get_process_memory_mb() -> float:
    """
    Returns the current process resident set size (RSS) memory in megabytes.

    This function attempts to use 'psutil' to query process memory statistics. 
    If 'psutil' is not installed, it falls back to low-level Windows APIs using 
    'ctypes'. If both fail, it returns 0.0.

    Why: Accurate memory reporting is a key feature of the candidate loader, 
    and this wrapper guarantees reliable metrics across standard and non-standard 
    environments.

    Returns:
        float: The process RSS memory in megabytes (MB).
    """
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024.0 * 1024.0)
    except ImportError:
        # Fallback for Windows system using ctypes to get memory usage
        try:
            import ctypes
            from ctypes import wintypes
            
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            
            GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
            GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
            
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if GetProcessMemoryInfo(GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / (1024.0 * 1024.0)
        except Exception:
            pass
        return 0.0


class CandidateLoader:
    """
    Loader class for streaming and parsing candidate profiles from JSONL and JSON format.

    Why: Handles files of various formats (plain JSON, JSONL, and gzipped JSONL) with high memory
    efficiency via streaming, ensuring robustness and isolation of JSON decode errors.
    """

    def __init__(self, file_path: str):
        """
        Initializes the CandidateLoader instance and auto-detects file format.

        Args:
            file_path (str): The system path to the .jsonl, .json, or .gz candidate file.

        Why: Configures the file source for subsequent read operations and detects compression format.
        """
        self.file_path = file_path
        
        # Auto-detect file format based on extension
        path_str = str(file_path)
        if path_str.endswith(".gz"):
            self.is_gzipped = True
            print("Detected format: gzipped JSONL")
        elif path_str.endswith(".jsonl") or path_str.endswith(".json"):
            self.is_gzipped = False
            print("Detected format: plain JSONL/JSON")
        else:
            self.is_gzipped = False
            print("Detected format: plain JSONL/JSON")

    def _print_stats(self):
        """
        Prints detailed statistics about the candidate data loading process, including
        format detection, estimated file size, and memory usage.

        Why: Provides insights on the performance and resource efficiency of the data ingestion.
        """
        # Determine file format string
        format_str = "gzipped JSONL" if self.is_gzipped else "plain JSONL/JSON"
        
        # Estimate file size in MB
        try:
            file_size_bytes = os.path.getsize(self.file_path)
            file_size_mb = file_size_bytes / (1024.0 * 1024.0)
        except Exception:
            file_size_mb = 0.0
            
        # Get properties from self or default if they haven't been run/set
        loaded = getattr(self, "loaded_count", 0)
        skipped = getattr(self, "skipped_count", 0)
        elapsed = getattr(self, "elapsed_time", 0.0)
        before_mem = getattr(self, "start_memory", 0.0)
        after_mem = getattr(self, "end_memory", 0.0)
        delta_mem = getattr(self, "memory_delta", 0.0)
        is_streaming = getattr(self, "streaming", True)
        
        streaming_str = "Yes" if is_streaming else "No"
        
        print("\n--- Candidate Loading Statistics ---")
        print(f"File Path: {self.file_path}")
        print(f"File Format: {format_str}")
        print(f"Estimated File Size: {file_size_mb:.2f} MB")
        print(f"Used Streaming Mode: {streaming_str}")
        print(f"Candidates Loaded: {loaded}")
        print(f"Malformed Lines Skipped: {skipped}")
        print(f"Total Load Time: {elapsed:.4f} seconds")
        print(f"Memory Usage: Before = {before_mem:.2f} MB | After = {after_mem:.2f} MB | Delta = {delta_mem:.2f} MB")
        print("------------------------------------\n")

    def load_all(self) -> list:
        """
        Loads all candidate profiles from the file using a streaming approach if JSONL,
        or full file parsing if a JSON array format.

        Returns:
            list: A list of dicts representing parsed candidate profiles.

        Why: Provides memory-efficient ingestion for large JSONL files, while remaining compatible
             with JSON array formats.
        """
        start_time = time.perf_counter()
        start_memory = get_process_memory_mb()
        
        candidates = []
        skipped = 0
        
        # Check if file exists first to avoid unhandled errors
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Candidate file not found: {self.file_path}")
        
        # Auto-select open function based on format detection
        open_func = gzip.open if self.is_gzipped else open
        mode = "rt" if self.is_gzipped else "r"
        
        # We track whether we used streaming mode
        self.streaming = True
        
        with open_func(self.file_path, mode, encoding="utf-8") as f:
            # Handle both .jsonl (one per line) 
            # AND .json (array format like sample_candidates.json)
            
            # Read first character to check if it's a JSON array format (starts with '[')
            first_char = f.read(1)
            f.seek(0)  # reset to beginning
            
            if first_char == "[":
                # JSON array format (like sample_candidates.json)
                self.streaming = False
                try:
                    data = json.load(f)
                    candidates = data if isinstance(data, list) else [data]
                except json.JSONDecodeError as e:
                    warnings.warn(f"Failed to parse JSON array: {e}")
            else:
                # JSONL format — read line by line (memory efficient)
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        candidates.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        warnings.warn(
                            f"Malformed line {line_num} in {self.file_path} "
                            f"was skipped. Error: {e}"
                        )
                        skipped += 1
                    
                    # Progress log every 10,000 lines
                    if line_num % 10000 == 0:
                        print(f"[Progress] Processed {line_num} lines. "
                              f"Successfully loaded {len(candidates)} candidates.")
        
        self.skipped_count = skipped
        self.loaded_count = len(candidates)
        
        # Measure elapsed time and memory delta for stats reporting
        self.elapsed_time = time.perf_counter() - start_time
        self.start_memory = start_memory
        self.end_memory = get_process_memory_mb()
        self.memory_delta = self.end_memory - start_memory
        
        self._print_stats()
        return candidates

    def load_sample(self, n: int = 50) -> list:
        """
        Loads the first n candidate profiles from the file using the streaming approach.

        Args:
            n (int): The maximum number of candidate profiles to load. Default is 50.

        Returns:
            list: A list of the first n parsed candidate dictionaries.

        Why: Allows quick data previewing, testing, and memory-saving experimentation on both
             gzipped and plain formats.
        """
        candidates = []
        
        # Check if file exists first to avoid unhandled errors
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Candidate file not found: {self.file_path}")
            
        open_func = gzip.open if self.is_gzipped else open
        mode = "rt" if self.is_gzipped else "r"
        
        with open_func(self.file_path, mode, encoding="utf-8") as f:
            # Read first character to check for JSON array format
            first_char = f.read(1)
            f.seek(0)
            
            if first_char == "[":
                # JSON array format — load entire array and slice first n elements
                try:
                    data = json.load(f)
                    candidates = (data if isinstance(data, list) else [data])[:n]
                except json.JSONDecodeError as e:
                    warnings.warn(f"Failed to parse JSON array in load_sample: {e}")
            else:
                # JSONL format — stream line-by-line and stop as soon as we have n candidates
                for line in f:
                    if len(candidates) >= n:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        candidates.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        return candidates

    def get_candidate_ids(self) -> set:
        """
        Returns just the set of all candidate_ids from the dataset without loading full profiles.

        Returns:
            set: A set of candidate ID strings.

        Why: Extremely useful for validating output submission files against valid IDs
             efficiently without high memory footprint.
        """
        ids = set()
        
        # Check if file exists first to avoid unhandled errors
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Candidate file not found: {self.file_path}")
            
        open_func = gzip.open if self.is_gzipped else open
        mode = "rt" if self.is_gzipped else "r"
        
        with open_func(self.file_path, mode, encoding="utf-8") as f:
            # Read first character to check for JSON array format
            first_char = f.read(1)
            f.seek(0)
            
            if first_char == "[":
                # JSON array format — load full JSON to retrieve IDs
                try:
                    data = json.load(f)
                    candidates = data if isinstance(data, list) else [data]
                    for cand in candidates:
                        if isinstance(cand, dict):
                            ids.add(cand.get("candidate_id", ""))
                except json.JSONDecodeError as e:
                    warnings.warn(f"Failed to parse JSON array in get_candidate_ids: {e}")
            else:
                # JSONL format — stream line-by-line, extracting candidate_id only
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("["):
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            ids.add(obj.get("candidate_id", ""))
                    except json.JSONDecodeError:
                        continue
        return ids


if __name__ == "__main__":
    import random
    from datetime import date

    def subtract_months(target_date: date, months: int) -> date:
        """
        Safely subtracts a number of months from a date object.
        """
        year = target_date.year - (months // 12)
        month = target_date.month - (months % 12)
        if month <= 0:
            year -= 1
            month += 12
        day = min(target_date.day, 28)
        return date(year, month, day)

    # Resolve path to the sample candidate file in the same directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sample_file_path = os.path.join(current_dir, "sample_candidates.json")
    gzipped_file_path = sample_file_path + ".gz"

    # Always generate/regenerate if either file is missing or if we want to ensure format compliance
    regenerate = True
    if os.path.exists(sample_file_path) and os.path.exists(gzipped_file_path):
        # Check if sample_candidates.json is a JSON array
        try:
            with open(sample_file_path, "r", encoding="utf-8") as f:
                first_char = f.read(1)
                if first_char == "[":
                    regenerate = False
        except Exception:
            pass

    if regenerate:
        print(f"Generating mock candidates to test both JSON array and gzipped formats...")
        
        titles = [
            "Software Engineer", "Senior Software Engineer", "Tech Lead",
            "Data Scientist", "Machine Learning Engineer", "Product Manager",
            "Frontend Developer", "Backend Developer", "DevOps Engineer"
        ]
        locations = ["San Francisco", "New York", "London", "Bengaluru", "Berlin", "Toronto", "Sydney"]
        countries = ["United States", "United States", "United Kingdom", "India", "Germany", "Canada", "Australia"]
        skill_names = ["Python", "JavaScript", "Go", "SQL", "React", "Docker", "AWS", "Kubernetes", "PyTorch", "Git"]
        degrees = ["B.S.", "M.S.", "Ph.D.", "B.Tech", "M.Tech"]
        fields = ["Computer Science", "Data Science", "Software Engineering", "Mathematics", "Electrical Engineering"]
        institutions = ["Stanford University", "MIT", "UC Berkeley", "IIT Bombay", "University of Oxford", "CMU"]

        dummy_candidates = []
        
        # 1. Generate 45 clean candidates with valid timelines
        for i in range(1, 46):
            cand_id = f"CAND_{i:07d}"
            title_idx = random.randint(0, len(titles) - 1)
            loc_idx = random.randint(0, len(locations) - 1)

            # Skills
            cand_skills = []
            num_skills = random.randint(2, 6)
            chosen_skills = random.sample(skill_names, num_skills)
            for skill in chosen_skills:
                prof = random.choice(["Beginner", "Intermediate", "Advanced", "Expert"])
                dur = random.randint(12, 60) # Ensure duration is non-zero
                endorse = random.randint(1, 15) # Ensure endorsements is non-zero
                cand_skills.append({
                    "name": skill,
                    "proficiency": prof,
                    "endorsements": endorse,
                    "duration_months": dur
                })

            # Career History with start/end dates
            career = []
            num_jobs = random.randint(1, 3)
            current_date_tracker = date(2026, 6, 18)
            for j in range(num_jobs):
                is_curr = (j == 0)
                dur = random.randint(12, 36)

                if is_curr:
                    end_dt_str = None if random.choice([True, False]) else "2026-06-18"
                    end_dt = date(2026, 6, 18)
                else:
                    end_dt = current_date_tracker
                    end_dt_str = end_dt.strftime("%Y-%m-%d")

                start_dt = subtract_months(end_dt, dur)
                start_dt_str = start_dt.strftime("%Y-%m-%d")

                career.append({
                    "company": f"Company {chr(65 + random.randint(0, 25))}",
                    "title": random.choice(titles),
                    "industry": random.choice(["Technology", "Finance", "Healthcare", "E-commerce"]),
                    "company_size": random.choice(["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]),
                    "start_date": start_dt_str,
                    "end_date": end_dt_str,
                    "duration_months": dur,
                    "is_current": is_curr,
                    "description": "Responsible for core service implementations and technical feature delivery."
                })
                # Set tracker for previous job (with a gap)
                current_date_tracker = subtract_months(start_dt, random.randint(1, 6))

            # Stated experience is derived from career duration to prevent mismatch flags
            total_months = sum(float(role.get("duration_months", 0)) for role in career)
            years_exp = round(total_months / 12.0 + random.uniform(0.0, 1.0), 1)

            # Education
            edu = []
            num_edu = random.randint(1, 2)
            for _ in range(num_edu):
                edu.append({
                    "institution": random.choice(institutions),
                    "degree": random.choice(degrees),
                    "field_of_study": random.choice(fields),
                    "tier": random.choice([1, 2, 3])
                })

            # Redrob Signals
            signals = {
                "open_to_work_flag": random.choice([True, False]),
                "last_active_date": "2026-06-18",
                "recruiter_response_rate": round(random.uniform(0.5, 1.0), 2),
                "notice_period_days": random.choice([0, 15, 30, 60, 90]),
                "github_activity_score": random.randint(0, 100),
                "interview_completion_rate": round(random.uniform(0.6, 1.0), 2),
                "profile_completeness": round(random.uniform(0.7, 1.0), 2),
                "assessment_score": random.randint(50, 100),
                "coding_speed_percentile": random.randint(10, 99),
                "problem_solving_score": random.randint(50, 100),
                "communication_rating": round(random.uniform(3.0, 5.0), 1),
                "technical_vibe_score": random.randint(30, 100),
                "cultural_fit_score": random.randint(50, 100),
                "active_applications_count": random.randint(0, 10),
                "profile_views_last_30_days": random.randint(0, 150),
                "average_test_time_minutes": random.randint(20, 120),
                "system_design_score": random.randint(50, 100),
                "reliability_index": round(random.uniform(0.8, 1.0), 2),
                "years_in_current_role": round(random.uniform(0.5, 5.0), 1),
                "salary_expectation_k": random.randint(50, 200),
                "visa_status_required": random.choice([True, False]),
                "remote_preference": random.choice(["Remote", "Hybrid", "Onsite"]),
                "career_growth_velocity": round(random.uniform(1.0, 5.0), 1)
            }

            dummy_candidates.append({
                "candidate_id": cand_id,
                "profile": {
                    "years_of_experience": years_exp,
                    "current_title": titles[title_idx],
                    "location": locations[loc_idx],
                    "country": countries[loc_idx]
                },
                "skills": cand_skills,
                "career_history": career,
                "education": edu,
                "redrob_signals": signals
            })

        # 2. Inject 5 mock Honeypot candidates

        # Honeypot 1: Timeline Impossibility (CAND_0000046)
        dummy_candidates.append({
            "candidate_id": "CAND_0000046",
            "profile": {"years_of_experience": 6.5, "current_title": "Senior AI Engineer", "location": "Pune", "country": "India"},
            "skills": [{"name": "Python", "proficiency": "Expert", "endorsements": 8, "duration_months": 60}],
            "career_history": [{
                "company": "Fake Corp",
                "title": "Machine Learning Engineer",
                "industry": "Technology",
                "company_size": "201-500",
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
                "duration_months": 60,
                "is_current": False,
                "description": "Used embeddings and vector databases to build systems."
            }],
            "education": [{"institution": "Stanford University", "degree": "M.S.", "field_of_study": "Computer Science", "tier": 1}],
            "redrob_signals": {"open_to_work_flag": True, "last_active_date": "2026-06-18", "recruiter_response_rate": 0.9, "notice_period_days": 30, "github_activity_score": 80, "interview_completion_rate": 0.95}
        })

        # Honeypot 2: Skill Fraud (CAND_0000047)
        dummy_candidates.append({
            "candidate_id": "CAND_0000047",
            "profile": {"years_of_experience": 5.0, "current_title": "AI Engineer", "location": "Noida", "country": "India"},
            "skills": [
                {"name": "Python", "proficiency": "Expert", "endorsements": 0, "duration_months": 0},
                {"name": "Embeddings", "proficiency": "Expert", "endorsements": 0, "duration_months": 0},
                {"name": "Vector Database", "proficiency": "Advanced", "endorsements": 0, "duration_months": 0},
                {"name": "Transformers", "proficiency": "Expert", "endorsements": 0, "duration_months": 1}
            ],
            "career_history": [{
                "company": "Logistics Ltd",
                "title": "Software Developer",
                "industry": "Technology",
                "company_size": "51-200",
                "start_date": "2023-01-01",
                "end_date": "2026-01-01",
                "duration_months": 36,
                "is_current": False,
                "description": "Standard software development."
            }],
            "education": [{"institution": "IIT Bombay", "degree": "B.Tech", "field_of_study": "Computer Science", "tier": 1}],
            "redrob_signals": {"open_to_work_flag": True, "last_active_date": "2026-06-18", "recruiter_response_rate": 0.9, "notice_period_days": 30, "github_activity_score": 50, "interview_completion_rate": 0.95}
        })

        # Honeypot 3: Experience Mismatch (CAND_0000048)
        dummy_candidates.append({
            "candidate_id": "CAND_0000048",
            "profile": {"years_of_experience": 15.0, "current_title": "Tech Lead", "location": "Bangalore", "country": "India"},
            "skills": [{"name": "Python", "proficiency": "Expert", "endorsements": 10, "duration_months": 12}],
            "career_history": [{
                "company": "Startup A",
                "title": "Developer",
                "industry": "Technology",
                "company_size": "11-50",
                "start_date": "2025-01-01",
                "end_date": "2026-01-01",
                "duration_months": 12,
                "is_current": True,
                "description": "Developer."
            }],
            "education": [{"institution": "BITS Pilani", "degree": "B.E.", "field_of_study": "Computer Science", "tier": 1}],
            "redrob_signals": {"open_to_work_flag": False, "last_active_date": "2026-06-18", "recruiter_response_rate": 0.85, "notice_period_days": 30, "github_activity_score": 60, "interview_completion_rate": 0.9}
        })

        # Honeypot 4: Title-Skill Mismatch (CAND_0000049)
        dummy_candidates.append({
            "candidate_id": "CAND_0000049",
            "profile": {"years_of_experience": 8.0, "current_title": "Marketing Manager", "location": "Hyderabad", "country": "India"},
            "skills": [
                {"name": "Python", "proficiency": "Expert", "endorsements": 10, "duration_months": 48},
                {"name": "Machine Learning", "proficiency": "Expert", "endorsements": 5, "duration_months": 36},
                {"name": "Deep Learning", "proficiency": "Expert", "endorsements": 8, "duration_months": 24},
                {"name": "NLP", "proficiency": "Expert", "endorsements": 4, "duration_months": 24},
                {"name": "Transformers", "proficiency": "Expert", "endorsements": 5, "duration_months": 12}
            ],
            "career_history": [{
                "company": "Retail Corp",
                "title": "Marketing Coordinator",
                "industry": "Retail",
                "company_size": "501-1000",
                "start_date": "2020-01-01",
                "end_date": "2024-01-01",
                "duration_months": 48,
                "is_current": False,
                "description": "Executed digital marketing campaigns and managed social media presence."
            }, {
                "company": "Agency B",
                "title": "Sales Associate",
                "industry": "Marketing",
                "company_size": "11-50",
                "start_date": "2016-01-01",
                "end_date": "2020-01-01",
                "duration_months": 48,
                "is_current": False,
                "description": "Generated outbound sales leads and handled cold calls."
            }],
            "education": [{"institution": "Delhi University", "degree": "BBA", "field_of_study": "Marketing", "tier": 2}],
            "redrob_signals": {"open_to_work_flag": True, "last_active_date": "2026-06-18", "recruiter_response_rate": 0.75, "notice_period_days": 15, "github_activity_score": 20, "interview_completion_rate": 0.8}
        })

        # Honeypot 5: Multiple Flags (CAND_0000050)
        dummy_candidates.append({
            "candidate_id": "CAND_0000050",
            "profile": {"years_of_experience": 12.0, "current_title": "Product Owner", "location": "Mumbai", "country": "India"},
            "skills": [{"name": f"Skill {k}", "proficiency": "Expert", "endorsements": 5, "duration_months": 12} for k in range(25)],
            "career_history": [{
                "company": "Financial Services",
                "title": "Business Analyst",
                "industry": "Finance",
                "company_size": "1000+",
                "start_date": "2024-01-01",
                "end_date": "2026-01-01",
                "duration_months": 24,
                "is_current": True,
                "description": "Gathered software requirements."
            }],
            "education": [{"institution": "Mumbai University", "degree": "B.Com", "field_of_study": "Finance", "tier": 2}],
            "redrob_signals": {"open_to_work_flag": False, "last_active_date": "2026-06-18", "recruiter_response_rate": 0.9, "notice_period_days": 60, "github_activity_score": 10, "interview_completion_rate": 0.95}
        })

        # Write to sample_candidates.json as a JSON array format
        with open(sample_file_path, "w", encoding="utf-8") as f:
            json.dump(dummy_candidates, f, indent=2)
        print(f"Successfully generated {sample_file_path} in JSON array format.")

        # Write to sample_candidates.json.gz as a gzipped JSONL format with a malformed line
        with gzip.open(gzipped_file_path, "wt", encoding="utf-8") as f:
            for cand in dummy_candidates:
                f.write(json.dumps(cand) + "\n")
            f.write("{malformed json string, key:value}\n")
        print(f"Successfully generated {gzipped_file_path} in gzipped JSONL format with a malformed line.")

    # Run verification tests on both formats
    for path, description in [(sample_file_path, "JSON array format"), (gzipped_file_path, "gzipped JSONL format")]:
        print(f"\n================ Testing format: {description} ================")
        
        # This will test __init__ and print format detection info
        loader = CandidateLoader(path)
        
        # 1. Load all candidates
        print(f"Executing load_all() on {os.path.basename(path)}...")
        candidates = loader.load_all()
        
        # Verify candidate counts
        expected_count = 50
        assert len(candidates) == expected_count, f"Expected {expected_count} candidates, got {len(candidates)}"
        print(f"[Verification] Assertion Passed: Loaded exactly {len(candidates)} candidates successfully!")
        
        # 2. Print first 3 candidate IDs and titles
        print("\n--- Displaying Attributes for the First 3 Candidates ---")
        for i, candidate in enumerate(candidates[:3], start=1):
            cand_id = candidate.get("candidate_id", "N/A")
            profile = candidate.get("profile", {})
            title = profile.get("current_title", "N/A")
            print(f"  Candidate {i}: ID = {cand_id} | Title = {title}")
        print("-" * 50)
        
        # 3. Stats printed automatically via load_all() showing format detection worked
        
        # 4. Test load_sample(n=5) and print result count
        print(f"\nExecuting load_sample(n=5) on {os.path.basename(path)}...")
        sampled = loader.load_sample(n=5)
        print(f"Successfully loaded {len(sampled)} sample candidates.")
        assert len(sampled) == 5, f"Expected 5 candidates, got {len(sampled)}"
        print("  Sample IDs:", [c.get("candidate_id") for c in sampled])
        
        # Test get_candidate_ids()
        print(f"\nExecuting get_candidate_ids() on {os.path.basename(path)}...")
        ids = loader.get_candidate_ids()
        print(f"Total candidate IDs retrieved: {len(ids)}")
        print("  Sample IDs in set:", sorted(list(ids))[:5])
        print("========================================================\n")
