"""
loader.py: Data loader module for candidate records.

This module contains the CandidateLoader class which is responsible for loading 
candidate profile data from a JSON Lines (.jsonl) file format. It tracks statistics 
about loading time, memory consumption delta, processes the data line-by-line 
to minimize memory overhead, and safely skips malformed JSON records while emitting 
warnings.
"""

import os
import sys
import time
import json
import warnings

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
    Loader class for streaming and parsing candidate profiles from JSONL format.

    Why: Simplifies data ingestion pipelines for downstream scoring and ranking modules, 
    ensures error isolation via JSON decode safety, and monitors compute resource usage.
    """

    def __init__(self, file_path: str):
        """
        Initializes the CandidateLoader instance.

        Args:
            file_path (str): The system path to the .jsonl candidate file.

        Why: Configures the file source for subsequent read operations.
        """
        self.file_path = file_path

    def _load_data(self, limit: int = None) -> list:
        """
        A private helper method to open, stream, parse, and measure resources during ingestion.

        Args:
            limit (int, optional): The maximum number of valid records to load. 
                                   If None, all records are loaded.

        Raises:
            FileNotFoundError: If the configured file_path does not exist.

        Returns:
            list: A list of dicts representing parsed candidate profiles.

        Why: Consolidates common reading logic, resource usage calculations, 
             and JSON warning management to prevent code duplication.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Candidate file not found: {self.file_path}")

        start_time = time.perf_counter()
        start_memory = get_process_memory_mb()

        candidates = []
        processed_count = 0
        malformed_count = 0

        with open(self.file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue  # Skip empty or whitespace-only lines

                try:
                    candidate = json.loads(clean_line)
                    candidates.append(candidate)
                    processed_count += 1

                    # Print progress every 10,000 processed records
                    if processed_count % 10000 == 0:
                        print(f"[Progress] Processed {processed_count} lines. "
                              f"Successfully loaded {len(candidates)} candidates.")

                    if limit is not None and len(candidates) >= limit:
                        break
                except json.JSONDecodeError as e:
                    malformed_count += 1
                    warnings.warn(
                        f"Malformed line {line_num} in {self.file_path} was skipped. Error: {e}",
                        UserWarning
                    )

        end_time = time.perf_counter()
        end_memory = get_process_memory_mb()

        elapsed_time = end_time - start_time
        memory_delta = end_memory - start_memory

        print("\n--- Candidate Loading Statistics ---")
        print(f"File Path: {self.file_path}")
        print(f"Candidates Loaded: {len(candidates)}")
        print(f"Malformed Lines Skipped: {malformed_count}")
        print(f"Total Load Time: {elapsed_time:.4f} seconds")
        print(f"Memory Usage: Before = {start_memory:.2f} MB | After = {end_memory:.2f} MB | Delta = {memory_delta:.2f} MB")
        print("------------------------------------\n")

        return candidates

    def load_all(self) -> list:
        """
        Loads all candidate profiles from the JSONL file.

        Returns:
            list: A list of all parsed candidate dictionaries.

        Why: Offers a clean, high-level API to retrieve the entire candidate dataset.
        """
        return self._load_data()

    def load_sample(self, n: int = 50) -> list:
        """
        Loads the first n candidate profiles from the JSONL file.

        Args:
            n (int): The number of candidate profiles to load. Default is 50.

        Returns:
            list: A list of the first n parsed candidate dictionaries.

        Why: Allows quick data previewing, testing, and memory-saving experimentation.
        """
        return self._load_data(limit=n)


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

    # Force regeneration if file doesn't exist or lacks the new 'start_date' fields
    regenerate = True
    if os.path.exists(sample_file_path):
        try:
            with open(sample_file_path, "r", encoding="utf-8") as f:
                first_line = f.readline()
                if "start_date" in first_line:
                    regenerate = False
        except Exception:
            pass

    if regenerate:
        print(f"Generating updated {sample_file_path} with job timelines and mock honeypots...")
        
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
        # Claims 60 months, but dates only show 5 months
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
        # Over 3 expert skills with 0 endorsements and <3 duration
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
        # Claims 15 years, but history totals 1 year
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
        # 5 AI skills, but all roles are non-tech (Marketing/Sales)
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
        # Has > 20 skills (25) and experience mismatch
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

        # Write out to sample file
        with open(sample_file_path, "w", encoding="utf-8") as f:
            for cand in dummy_candidates:
                f.write(json.dumps(cand) + "\n")
                
        # Append a malformed line at the very end to test warnings handling capability
        with open(sample_file_path, "a", encoding="utf-8") as f:
            f.write("{malformed json string, key:value}\n")

        print(f"Successfully generated {len(dummy_candidates)} valid mock candidates "
              f"and 1 malformed line in {sample_file_path}.")

    # Initialize loader and run verification tests
    print("\nInitializing CandidateLoader...")
    loader = CandidateLoader(sample_file_path)

    print("Executing load_all()...")
    loaded_candidates = loader.load_all()

    # Verify that exactly 50 candidates were loaded successfully (skipping the malformed line)
    assert len(loaded_candidates) == 50, f"Expected 50 candidates to load, got {len(loaded_candidates)}"
    print("[Verification] Assertion Passed: Loaded exactly 50 candidates successfully!")

    # Print attributes of the first 3 candidates as requested
    print("\n--- Displaying Attributes for the First 3 Candidates ---")
    for i, candidate in enumerate(loaded_candidates[:3], start=1):
        cand_id = candidate.get("candidate_id", "N/A")
        
        profile = candidate.get("profile", {})
        title = profile.get("current_title", "N/A")
        years_exp = profile.get("years_of_experience", "N/A")
        
        signals = candidate.get("redrob_signals", {})
        open_to_work = signals.get("open_to_work_flag", "N/A")

        print(f"Candidate {i}:")
        print(f"  candidate_id:             {cand_id}")
        print(f"  profile.current_title:    {title}")
        print(f"  profile.years_experience: {years_exp}")
        print(f"  signals.open_to_work:     {open_to_work}")
        print("-" * 50)

