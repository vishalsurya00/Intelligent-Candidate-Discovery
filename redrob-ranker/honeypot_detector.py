"""
honeypot_detector.py: Honeypot candidate detection module.

This module contains the HoneypotDetector class which identifies candidate profiles
containing impossible, fraudulent, or inconsistent data. Flagging these profiles
prevents disqualification during candidate submission processing.
"""

import os
import json
import warnings
from datetime import datetime

class HoneypotDetector:
    """
    Detector class containing heuristics to find fraudulent candidate profiles.

    Why: Identifies and flags profiles with timeline impossibilities, skill stuffing,
         experience inflation, and non-technical histories claiming AI expertise.
    """

    def check_timeline_impossibility(self, candidate: dict) -> dict:
        """
        Checks if career history contains impossible timeline claims.

        Args:
            candidate (dict): The candidate profile data.

        Returns:
            dict: A dictionary with 'flagged' (bool) and 'reason' (str).

        Why: Ensures start and end dates reported for roles align with stated duration_months.
        """
        try:
            history = candidate.get("career_history", [])
            for idx, role in enumerate(history):
                start_str = role.get("start_date")
                end_str = role.get("end_date")
                is_current = role.get("is_current", False)
                stated_dur = role.get("duration_months")

                # If end_date is null/None and role is current, it's a valid open-ended timeline
                if not end_str and is_current:
                    continue

                if not start_str or not end_str:
                    continue

                if stated_dur is None:
                    continue

                # Parse dates to calculate the absolute month difference
                start_dt = datetime.strptime(start_str, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end_str, "%Y-%m-%d").date()

                actual_months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
                stated_months = float(stated_dur)

                # Flag if the discrepancy between dates and stated months exceeds 6 months
                if abs(actual_months - stated_months) > 6:
                    return {
                        "flagged": True,
                        "reason": (f"Timeline Impossibility: Role #{idx+1} ({role.get('title')} at {role.get('company')}) "
                                   f"claims {stated_months} months, but dates show actual duration of {actual_months} months.")
                    }
        except Exception as e:
            # Gracefully ignore if data is missing or malformed to avoid crashing the pipeline
            pass
        
        return {"flagged": False, "reason": ""}

    def check_skill_fraud(self, candidate: dict) -> dict:
        """
        Detects keyword stuffing by analyzing skills claims against experience duration.

        Args:
            candidate (dict): The candidate profile data.

        Returns:
            dict: A dictionary with 'flagged' (bool) and 'reason' (str).

        Why: Identifies users claiming high proficiency with zero duration or endorsements.
        """
        try:
            skills = candidate.get("skills", [])
            if not skills:
                return {"flagged": False, "reason": ""}

            # Unrealistic skills count flag
            if len(skills) > 20:
                return {
                    "flagged": True,
                    "reason": f"Skill Fraud: Unrealistic skills list containing {len(skills)} skills (limit is 20)."
                }

            fraud_count = 0
            for skill in skills:
                proficiency = skill.get("proficiency", "").lower().strip()
                duration = float(skill.get("duration_months", 0))
                endorsements = int(skill.get("endorsements", 0))

                # Criteria 1: Expert/Advanced with 0 months duration
                cond1 = (proficiency in ["expert", "advanced"]) and (duration == 0)
                
                # Criteria 2: Expert with 0 endorsements and under 3 months duration
                cond2 = (proficiency == "expert") and (endorsements == 0) and (duration < 3)

                if cond1 or cond2:
                    fraud_count += 1

            # Flag if candidate has more than 3 suspicious skills claims
            if fraud_count > 3:
                return {
                    "flagged": True,
                    "reason": f"Skill Fraud: Keyword stuffer with {fraud_count} expert/advanced skills having zero duration or endorsements."
                }
        except Exception:
            pass

        return {"flagged": False, "reason": ""}

    def check_experience_mismatch(self, candidate: dict) -> dict:
        """
        Checks if the stated years of experience aligns with the career history.

        Args:
            candidate (dict): The candidate profile data.

        Returns:
            dict: A dictionary with 'flagged' (bool) and 'reason' (str).

        Why: Flags inflation (stated years exceed history) or overlap mismatch (history exceeds stated years).
        """
        try:
            profile = candidate.get("profile", {})
            stated_years = float(profile.get("years_of_experience", 0.0))

            history = candidate.get("career_history", [])
            total_months = sum(float(role.get("duration_months", 0)) for role in history)
            total_career_years = total_months / 12.0

            # Stated years exceed history by more than 3 years
            if stated_years > total_career_years + 3.0:
                return {
                    "flagged": True,
                    "reason": f"Experience Mismatch: Claimed {stated_years} years of experience, but career history sums to only {total_career_years:.2f} years."
                }

            # Career history exceeds stated years by more than 5 years (overlapping fake roles)
            if stated_years < total_career_years - 5.0:
                return {
                    "flagged": True,
                    "reason": f"Experience Mismatch: Claimed {stated_years} years of experience, but career history sums to {total_career_years:.2f} years (suspicious overlapping roles)."
                }
        except Exception:
            pass

        return {"flagged": False, "reason": ""}

    def check_title_skill_mismatch(self, candidate: dict) -> dict:
        """
        Detects mismatch between deep AI/ML skills and entirely non-tech job titles.

        Args:
            candidate (dict): The candidate profile data.

        Returns:
            dict: A dictionary with 'flagged' (bool) and 'reason' (str).

        Why: Catches non-technical profiles filled with AI keyword stuffing.
        """
        try:
            AI_SKILL_KEYWORDS = [
                "python", "machine learning", "deep learning", "nlp", "transformer", 
                "embedding", "vector", "pytorch", "tensorflow", "scikit-learn", 
                "faiss", "rag", "llm", "retrieval"
            ]
            
            NON_TECH_TITLES = [
                "marketing", "sales", "hr", "human resources", "accountant", 
                "finance", "operations", "supply chain", "procurement", 
                "customer service", "business development"
            ]

            skills = candidate.get("skills", [])
            history = candidate.get("career_history", [])

            # Count matches in candidate's skills list
            ai_skill_count = 0
            for skill in skills:
                name = skill.get("name", "").lower().strip()
                if any(kw in name or name in kw for kw in AI_SKILL_KEYWORDS):
                    ai_skill_count += 1

            if not history:
                return {"flagged": False, "reason": ""}

            # Check if all roles are non-technical
            non_tech_roles = 0
            for role in history:
                title = role.get("title", "").lower().strip()
                if any(nt in title for nt in NON_TECH_TITLES):
                    non_tech_roles += 1

            # Flag if candidate lists 5+ AI skills but has only non-tech job titles
            if ai_skill_count >= 5 and non_tech_roles == len(history):
                role_titles = [r.get("title") for r in history]
                return {
                    "flagged": True,
                    "reason": f"Title-Skill Mismatch: Claims {ai_skill_count} AI skills, but all roles are non-technical: {role_titles}."
                }
        except Exception:
            pass

        return {"flagged": False, "reason": ""}

    def check_assessment_mismatch(self, candidate: dict) -> dict:
        """
        Detects candidates whose self-reported skill proficiency contradicts
        their platform-verified skill_assessment_scores.

        Args:
            candidate (dict): The candidate profile data.

        Returns:
            dict: A dictionary with 'flagged' (bool) and 'reason' (str).

        Why: Ensures claims of 'expert' or 'advanced' proficiency are validated
             by platform assessment tests.
        """
        try:
            signals = candidate.get("redrob_signals", {})
            skill_assessment_scores = signals.get("skill_assessment_scores", {})
            if not skill_assessment_scores:
                return {"flagged": False, "reason": ""}

            skills = candidate.get("skills", [])
            contradictions = 0
            details = []

            for s in skills:
                name_orig = s.get("name", "")
                name_lower = name_orig.lower().strip()
                proficiency = s.get("proficiency", "").lower().strip()

                # Find matching assessment score case-insensitively
                matched_score = None
                if name_orig in skill_assessment_scores:
                    matched_score = skill_assessment_scores[name_orig]
                else:
                    for k, v in skill_assessment_scores.items():
                        if k.lower().strip() == name_lower:
                            matched_score = v
                            break

                if matched_score is not None:
                    try:
                        score_val = float(matched_score)
                        if proficiency == "expert" and score_val < 30:
                            contradictions += 1
                            details.append(f"{name_orig} (expert vs score {score_val})")
                        elif proficiency == "advanced" and score_val < 20:
                            contradictions += 1
                            details.append(f"{name_orig} (advanced vs score {score_val})")
                    except ValueError:
                        pass

            if contradictions >= 2:
                details_str = ", ".join(details)
                return {
                    "flagged": True,
                    "reason": f"Assessment Mismatch: Found {contradictions} proficiency contradictions: {details_str}."
                }
        except Exception:
            pass

        return {"flagged": False, "reason": ""}

    def is_honeypot(self, candidate: dict) -> dict:
        """
        Executes all 5 honeypot detection heuristics and returns the verdict.

        Args:
            candidate (dict): The candidate profile data.

        Returns:
            dict: Verdict dictionary including risk score and list of flag reasons.

        Why: Combines all heuristics into a single validation endpoint.
        """
        candidate_id = candidate.get("candidate_id", "Unknown")

        # Execute checks
        timeline_check = self.check_timeline_impossibility(candidate)
        skill_check = self.check_skill_fraud(candidate)
        experience_check = self.check_experience_mismatch(candidate)
        title_check = self.check_title_skill_mismatch(candidate)
        assessment_check = self.check_assessment_mismatch(candidate)

        # Accumulate flag reasons
        flags = []
        if timeline_check.get("flagged"):
            flags.append(timeline_check.get("reason"))
        if skill_check.get("flagged"):
            flags.append(skill_check.get("reason"))
        if experience_check.get("flagged"):
            flags.append(experience_check.get("reason"))
        if title_check.get("flagged"):
            flags.append(title_check.get("reason"))
        if assessment_check.get("flagged"):
            flags.append(assessment_check.get("reason"))

        flagged_count = len(flags)
        is_fake = flagged_count > 0
        honeypot_score = flagged_count / 5.0

        return {
            "candidate_id": candidate_id,
            "is_honeypot": is_fake,
            "honeypot_score": honeypot_score,
            "flags": flags
        }


if __name__ == "__main__":
    from loader import CandidateLoader

    # Load the candidate dataset
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sample_file_path = os.path.join(current_dir, "sample_candidates.json")

    print(f"Loading candidate records from: {sample_file_path}")
    loader = CandidateLoader(sample_file_path)
    candidates = loader.load_all()

    # Initialize the detector
    detector = HoneypotDetector()

    # Audit all candidate profiles
    flagged_candidates = []
    all_results = []

    for candidate in candidates:
        result = detector.is_honeypot(candidate)
        all_results.append(result)
        if result["is_honeypot"]:
            flagged_candidates.append(result)

    # Print summary reports
    print("\n================ HONEYPOT AUDIT SUMMARY ================")
    print(f"Total Candidates Audited:  {len(candidates)}")
    print(f"Total Honeypots Flagged:   {len(flagged_candidates)} / {len(candidates)}")
    print("========================================================\n")

    print("--- Detailed Flagged Candidate Breakdown ---")
    for fc in flagged_candidates:
        print(f"\nCandidate ID: {fc['candidate_id']} | Honeypot Risk Score: {fc['honeypot_score']:.2f}")
        for flag in fc["flags"]:
            print(f"  - {flag}")
        print("-" * 55)

    # Find the top 3 candidates with the highest risk scores
    sorted_risk = sorted(all_results, key=lambda x: x["honeypot_score"], reverse=True)
    
    print("\n--- Top 3 Candidates with Highest Honeypot Risk Scores ---")
    for i, res in enumerate(sorted_risk[:3], start=1):
        print(f"{i}. Candidate ID: {res['candidate_id']} | Score: {res['honeypot_score']:.2f} | Flags Raised: {len(res['flags'])}")
        for f in res["flags"]:
            print(f"    - {f}")
        print("-" * 55)
