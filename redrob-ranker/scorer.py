"""
scorer.py: Candidate scoring module for Redrob hackathon.

This module contains the CandidateScorer class which computes a multi-dimensional 
suitability score for candidates applying for a Senior AI Engineer role. The evaluation 
leverages 5 distinct scoring components: skills, career background, years of experience, 
behavioral signals, and location fit.
"""

import os
import sys
import warnings
from datetime import datetime, date

class CandidateScorer:
    """
    Scorer class for evaluating candidates against a Senior AI Engineer profile.

    Why: Provides structured, fact-based criteria to rank candidates according to 
    skills alignment, career quality (product vs. consulting), experience duration, 
    engagement signals, and location preferences.
    """

    def __init__(self):
        """
        Initializes the CandidateScorer with target criteria.

        Why: Defines lists of desired skills, blacklist companies, and preferred 
        locations to avoid hardcoding inside the scoring functions.
        """
        self.MUST_HAVE = [
            "python", "embeddings", "vector database", "retrieval", "ranking", 
            "semantic search", "faiss", "pinecone", "weaviate", "qdrant", 
            "sentence-transformers", "information retrieval", "elasticsearch", 
            "opensearch", "recommendation system", "nlp", "transformers"
        ]
        
        self.NICE_TO_HAVE = [
            "llm fine-tuning", "lora", "learning-to-rank", "xgboost", 
            "distributed systems", "mlops", "kubernetes", "ray"
        ]

        self.BLACKLIST_COMPANIES = {
            "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", 
            "hcl", "tech mahindra", "mphasis"
        }

        self.PREFERRED_CITIES = [
            "pune", "noida", "hyderabad", "mumbai", "delhi", "gurugram", 
            "gurgaon", "bangalore", "bengaluru", "chennai"
        ]

    def score_skills(self, candidate: dict) -> float:
        """
        Calculates the skills score of a candidate based on MUST_HAVE and NICE_TO_HAVE matching.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: A skills score between 0.0 and 1.0.

        Why: Skills are the primary signal of technical competence. The trust multiplier 
             prevents keyword stuffing by factoring in endorsements, duration, and proficiency levels.
        """
        candidate_skills = candidate.get("skills", [])
        if not candidate_skills:
            return 0.0

        matched_skills = []
        
        # Iterate over all skills listed by the candidate
        for skill in candidate_skills:
            skill_name = skill.get("name", "").lower().strip()
            if not skill_name:
                continue

            # Check for MUST_HAVE or NICE_TO_HAVE matches (partial match, case-insensitive)
            is_must = any(mh in skill_name or skill_name in mh for mh in self.MUST_HAVE)
            is_nice = False
            if not is_must:
                is_nice = any(nth in skill_name or skill_name in nth for nth in self.NICE_TO_HAVE)

            if is_must or is_nice:
                match_score = 1.0 if is_must else 0.5
                
                # Fetch credentials details
                endorsements = float(skill.get("endorsements", 0))
                duration_months = float(skill.get("duration_months", 0))
                proficiency = skill.get("proficiency", "").lower().strip()

                # Calculate trust multiplier
                trust = min(1.0, (endorsements / 10.0) * 0.4 + (duration_months / 12.0) * 0.6)
                
                # Keyword stuffing detection
                if proficiency == "expert" and duration_months == 0:
                    trust = 0.1
                
                # Beginner penalty
                if proficiency == "beginner":
                    trust *= 0.5

                matched_skills.append((match_score, trust))

        if not matched_skills:
            return 0.0

        # Calculate weighted average: sum(match_score * match_score * trust) / sum(match_score)
        # We use match_score as the weight to give MUST_HAVE matches higher priority in the average
        total_weight = sum(m[0] for m in matched_skills)
        total_weighted_trust = sum(m[0] * (m[0] * m[1]) for m in matched_skills)

        skills_score = 0.0
        if total_weight > 0:
            raw_score = total_weighted_trust / total_weight
            # Apply a coverage factor to reward candidates with more matched skills (capped at 1.0)
            # A top candidate should ideally match at least 4 key skills
            coverage = min(1.0, len(matched_skills) / 4.0)
            skills_score = raw_score * coverage
        
        # Apply Title Penalty (Fix 1)
        PENALIZED_TITLES = [
            "marketing", "sales", "accountant", "hr", "human resources",
            "operations", "supply chain", "customer support", "finance",
            "procurement", "legal", "administrative", "receptionist"
        ]
        current_title = candidate.get("profile", {}).get("current_title", "").lower().strip()
        if any(pt in current_title for pt in PENALIZED_TITLES):
            skills_score *= 0.3

        return skills_score

    def score_career(self, candidate: dict) -> float:
        """
        Calculates the career score based on company backgrounds, AI/ML exposure, and tenure.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: A career score between 0.0 and 1.0.

        Why: Distinguishes product company experience from consulting roles, rewards 
             relevant project descriptions, and incentivizes healthy tenure.
        """
        history = candidate.get("career_history", [])
        if not history:
            return 0.0

        total_duration = 0.0
        blacklist_duration = 0.0
        non_blacklist_durations = []
        has_positive_signal = False
        has_aiml_keywords = False
        
        ai_keywords = [
            "embedding", "retrieval", "ranking", "recommendation", "search", 
            "nlp", "transformer", "vector", "machine learning", "deep learning"
        ]

        STRONG_POSITIVE_TITLES = [
            "machine learning", "ml engineer", "ai engineer", "data scientist",
            "nlp engineer", "research scientist", "recommendation", 
            "search engineer", "ranking engineer", "retrieval", 
            "backend engineer", "software engineer", "full stack",
            "platform engineer", "infrastructure"
        ]

        AI_KEYWORDS_SPECIFIC = [
            "embedding", "vector", "retrieval", "ranking", "search", "nlp", 
            "transformer", "recommendation", "machine learning", "neural"
        ]

        career_bonus = 0.0

        # Process each job in employment history
        for job in history:
            company = job.get("company", "").lower().strip()
            duration = float(job.get("duration_months", 0))
            company_size = job.get("company_size", "")
            industry = job.get("industry", "").lower()
            desc = job.get("description", "").lower()
            title = job.get("title", "").lower().strip()

            total_duration += duration

            # Check blacklist matches
            is_blacklisted = any(bc in company or company in bc for bc in self.BLACKLIST_COMPANIES)
            if is_blacklisted:
                blacklist_duration += duration
            else:
                non_blacklist_durations.append(duration)

            # Check positive signals (Product / Tech companies of right size)
            valid_size = company_size in {"201-500", "501-1000", "1001-5000", "5001-10000", "10001+"}
            valid_industry = any(ind in industry for ind in ["technology", "software", "ai", "internet"])
            if valid_size and valid_industry:
                has_positive_signal = True

            # Check for AI/ML keywords in description
            if any(kw in desc for kw in ai_keywords):
                has_aiml_keywords = True

            # AI/ML role detection bonus (Fix 2)
            if any(t in title for t in STRONG_POSITIVE_TITLES):
                career_bonus += 0.3
            
            kw_matches = sum(1 for kw in AI_KEYWORDS_SPECIFIC if kw in desc)
            if kw_matches >= 3:
                career_bonus += 0.2

        # Calculate blacklist ratio
        blacklist_ratio = (blacklist_duration / total_duration) if total_duration > 0 else 0.0

        # Calculate average tenure in non-blacklist companies
        avg_non_blacklist_duration = (sum(non_blacklist_durations) / len(non_blacklist_durations)) if non_blacklist_durations else 0.0

        # Accumulate career score components
        career_points = 0.0
        if has_positive_signal:
            career_points += 0.4
        if has_aiml_keywords:
            career_points += 0.3
        if avg_non_blacklist_duration > 18.0:
            career_points += 0.3

        # Add career bonus and cap at 1.0 (Fix 2)
        career_score = min(1.0, career_points + min(1.0, career_bonus))

        # Apply penalty if spent > 60% of career at blacklisted consulting companies
        if blacklist_ratio > 0.60:
            career_score *= 0.3

        return max(0.0, min(1.0, career_score))

    def score_experience(self, candidate: dict) -> float:
        """
        Calculates the experience score based on years of experience.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: An experience alignment score between 0.0 and 1.0.

        Why: Directly evaluates if a candidate falls into the ideal 5-9 years sweet spot.
        """
        profile = candidate.get("profile", {})
        years = float(profile.get("years_of_experience", 0.0))

        # Apply the specific experience curve
        if years < 3.0:
            return 0.1
        elif years < 4.0:
            return 0.4
        elif years < 5.0:
            return 0.7
        elif years <= 9.0:
            return 1.0
        elif years <= 12.0:
            return 0.8
        else:
            return 0.6

    def score_behavioral(self, candidate: dict) -> float:
        """
        Calculates the behavioral score from engagement, activity, and notice periods.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: A behavioral score between 0.0 and 1.0.

        Why: Streamlit Cloud hiring relies heavily on candidates who are responsive, 
             active, have short notice periods, and high assessment completion.
        """
        signals = candidate.get("redrob_signals", {})
        if not signals:
            return 0.0

        # 1. Evaluate last active date
        last_active_str = signals.get("last_active_date", "")
        active_score = 0.1
        days_diff = 999
        if last_active_str:
            try:
                # Assume YYYY-MM-DD
                ref_date = date(2026, 6, 19)
                last_active_dt = datetime.strptime(last_active_str, "%Y-%m-%d").date()
                days_diff = (ref_date - last_active_dt).days
                if days_diff <= 30:
                    active_score = 1.0
                elif days_diff <= 90:
                    active_score = 0.7
                elif days_diff <= 180:
                    active_score = 0.4
                else:
                    active_score = 0.1
            except Exception:
                active_score = 0.1

        # 2. Recruiter response rate
        recruiter_rate = float(signals.get("recruiter_response_rate", 0.0))
        recruiter_rate = max(0.0, min(1.0, recruiter_rate))

        # 3. Notice period score
        notice_days = signals.get("notice_period_days", 999)
        if notice_days is None:
            notice_days = 999
        try:
            notice_days = float(notice_days)
        except ValueError:
            notice_days = 999

        if notice_days <= 30:
            notice_score = 1.0
        elif notice_days <= 60:
            notice_score = 0.7
        elif notice_days <= 90:
            notice_score = 0.5
        else:
            notice_score = 0.3

        # 4. Interview completion rate
        interview_rate = float(signals.get("interview_completion_rate", 0.0))
        interview_rate = max(0.0, min(1.0, interview_rate))

        # 5. GitHub activity score (normalized from 0-100 to 0-1)
        github_raw = signals.get("github_activity_score", -1)
        if github_raw is None or github_raw == -1:
            github_score = 0.3
        else:
            try:
                github_score = float(github_raw) / 100.0
                github_score = max(0.0, min(1.0, github_score))
            except ValueError:
                github_score = 0.3

        # Final behavioral score = equal weighted average of all 5 signals
        behavioral_base = (active_score + recruiter_rate + notice_score + interview_rate + github_score) / 5.0

        # Open to work flag bonus (+0.2, capped at 1.0)
        open_to_work = signals.get("open_to_work_flag", False)
        if open_to_work is True:
            behavioral_score = min(1.0, behavioral_base + 0.2)
        else:
            behavioral_score = behavioral_base

        # Fix 3: Active-user boost / penalty
        if open_to_work is True and days_diff <= 30 and recruiter_rate > 0.6:
            behavioral_score = min(1.0, behavioral_score * 1.2)
        elif open_to_work is False and days_diff > 90:
            behavioral_score = behavioral_score * 0.5

        return behavioral_score

    def score_location(self, candidate: dict) -> float:
        """
        Calculates the location alignment score.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: A location score between 0.0 and 1.0.

        Why: Prefers candidates located in key Indian IT hubs or who are willing to relocate.
        """
        profile = candidate.get("profile", {})
        location = profile.get("location", "").lower().strip()
        country = profile.get("country", "").lower().strip()
        signals = candidate.get("redrob_signals", {})

        # Check if located in preferred city
        has_preferred_city = any(city in location for city in self.PREFERRED_CITIES)

        # Check relocation willingness
        willing_to_relocate = False
        if candidate.get("willing_to_relocate") is True:
            willing_to_relocate = True
        elif profile.get("willing_to_relocate") is True:
            willing_to_relocate = True
        elif signals.get("willing_to_relocate") is True:
            willing_to_relocate = True

        # Check if located in India
        is_india = "india" in country or country == "in"

        if has_preferred_city:
            return 1.0
        elif willing_to_relocate:
            return 0.8
        elif is_india:
            return 0.5
        else:
            return 0.2

    def score(self, candidate: dict) -> dict:
        """
        Combines all 5 components with their weights to yield a final matching score.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            dict: Dictionary containing the candidate_id, overall score, component scores, 
                  and a data-rich reasoning string.

        Why: Serves as the main scoring entrypoint for candidate evaluation.
        """
        candidate_id = candidate.get("candidate_id", "Unknown")
        profile = candidate.get("profile", {})
        signals = candidate.get("redrob_signals", {})

        # Run component evaluations
        skills_score = self.score_skills(candidate)
        career_score = self.score_career(candidate)
        experience_score = self.score_experience(candidate)
        behavioral_score = self.score_behavioral(candidate)
        location_score = self.score_location(candidate)

        # Apply weights: 0.35 skills, 0.25 career, 0.15 experience, 0.15 behavioral, 0.10 location
        final_score = (
            0.35 * skills_score +
            0.25 * career_score +
            0.15 * experience_score +
            0.15 * behavioral_score +
            0.10 * location_score
        )

        # Extract facts for reasoning string
        years_exp = float(profile.get("years_of_experience", 0.0))
        current_title = profile.get("current_title", "N/A")
        notice_days = signals.get("notice_period_days", "N/A")
        response_rate = float(signals.get("recruiter_response_rate", 0.0))

        # Extract current company name and size (Fix reasoning)
        current_company = "N/A"
        company_size = "N/A"
        history = candidate.get("career_history", [])
        if history:
            current_job = None
            for job in history:
                if job.get("is_current") is True:
                    current_job = job
                    break
            if not current_job:
                current_job = history[0]
            current_company = current_job.get("company", "N/A")
            company_size = current_job.get("company_size", "N/A")

        # Collect top 3 matched MUST_HAVE skills based on trust (Fix reasoning)
        matched_must_haves = []
        for skill in candidate.get("skills", []):
            skill_name = skill.get("name", "").strip()
            skill_name_lower = skill_name.lower()
            
            is_must = any(mh in skill_name_lower or skill_name_lower in mh for mh in self.MUST_HAVE)
            if is_must:
                endorsements = float(skill.get("endorsements", 0))
                duration_months = float(skill.get("duration_months", 0))
                proficiency = skill.get("proficiency", "").lower().strip()
                
                trust = min(1.0, (endorsements / 10.0) * 0.4 + (duration_months / 12.0) * 0.6)
                if proficiency == "expert" and duration_months == 0:
                    trust = 0.1
                if proficiency == "beginner":
                    trust *= 0.5
                    
                matched_must_haves.append((skill_name, trust))
                
        matched_must_haves.sort(key=lambda x: x[1], reverse=True)
        top_3_skills_list = [item[0] for item in matched_must_haves[:3]]
        top_3_skills = ", ".join(top_3_skills_list) if top_3_skills_list else "None"

        # Calculate blacklist ratio for concerns check
        total_duration = 0.0
        blacklist_duration = 0.0
        for job in history:
            company = job.get("company", "").lower().strip()
            duration = float(job.get("duration_months", 0))
            total_duration += duration
            if any(bc in company or company in bc for bc in self.BLACKLIST_COMPANIES):
                blacklist_duration += duration
        blacklist_ratio = (blacklist_duration / total_duration) if total_duration > 0 else 0.0

        # Collect concerns
        concerns = []
        if years_exp < 5.0:
            concerns.append(f"experience ({years_exp:.1f} yrs) is below requested 5-9 years")
        elif years_exp > 9.0:
            concerns.append(f"experience ({years_exp:.1f} yrs) exceeds requested 5-9 years")
        
        if blacklist_ratio > 0.60:
            concerns.append(f"spent {blacklist_ratio*100:.0f}% of career at consulting-only firms")
            
        if isinstance(notice_days, (int, float)) and notice_days > 60:
            concerns.append(f"has a long notice period of {notice_days} days")
            
        if location_score < 0.5:
            concerns.append("is not in a preferred city/country and is unwilling to relocate")
            
        if response_rate < 0.70:
            concerns.append(f"has a low recruiter response rate of {response_rate*100:.0f}%")

        if concerns:
            concern_str = f"Concern: {concerns[0]}."
        else:
            concern_str = "Strong behavioral signals."

        reasoning = (
            f"{years_exp:.1f} yrs exp as {current_title} at {current_company} "
            f"({company_size} co). Top skills: {top_3_skills}. "
            f"Notice: {notice_days}d. Response rate: {response_rate*100:.0f}%. "
            f"{concern_str}"
        )

        return {
            "candidate_id": candidate_id,
            "final_score": final_score,
            "skills_score": skills_score,
            "career_score": career_score,
            "experience_score": experience_score,
            "behavioral_score": behavioral_score,
            "location_score": location_score,
            "reasoning": reasoning
        }


if __name__ == "__main__":
    from loader import CandidateLoader

    # Load mock candidate database using the previously built loader
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sample_file_path = os.path.join(current_dir, "sample_candidates.json")

    print(f"Initializing CandidateLoader for: {sample_file_path}")
    loader = CandidateLoader(sample_file_path)
    candidates = loader.load_all()

    # Initialize Scorer
    scorer = CandidateScorer()

    # Score and print breakdowns for the first 5 candidates showing improvement
    print("\n=== Candidate Scoring Breakdown for First 5 Candidates ===")
    for i, candidate in enumerate(candidates[:5], start=1):
        scores = scorer.score(candidate)
        print(f"\nCandidate #{i} (ID: {scores['candidate_id']}):")
        print(f"  Final Score:      {scores['final_score']:.4f}")
        print(f"  Skills Score:      {scores['skills_score']:.4f}")
        print(f"  Career Score:      {scores['career_score']:.4f}")
        print(f"  Experience Score:  {scores['experience_score']:.4f}")
        print(f"  Behavioral Score:  {scores['behavioral_score']:.4f}")
        print(f"  Location Score:    {scores['location_score']:.4f}")
        print(f"  Reasoning:         {scores['reasoning']}")
        print("-" * 75)
