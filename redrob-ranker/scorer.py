"""
scorer.py: Candidate scoring module for Redrob hackathon.

This module contains the CandidateScorer class which computes a multi-dimensional 
suitability score for candidates applying for a Senior AI Engineer role. The evaluation 
leverages 6 distinct scoring components: skills, career background, years of experience, 
behavioral signals, location fit, and certifications.
"""

from datetime import datetime, date
import re
import math
import os
import json

class CandidateScorer:
    """
    Scorer class for evaluating candidates against a Senior AI Engineer profile.
    Provides structured, fact-based criteria to rank candidates according to 
    skills alignment, career quality (product vs. consulting), experience duration, 
    engagement signals, location preferences, and certifications.
    """

    def __init__(self):
        """
        Initializes the CandidateScorer with target criteria.
        Defines lists of desired skills, blacklist companies, and preferred 
        locations to avoid hardcoding inside the scoring functions.
        """
        # Component 1 Skills Criteria
        self.MUST_HAVE_SKILLS = [
            "python", "embedding", "vector database", "vector db", "retrieval",
            "ranking", "semantic search", "faiss", "pinecone", "weaviate", "qdrant",
            "milvus", "sentence-transformer", "opensearch", "elasticsearch",
            "nlp", "natural language processing", "transformer", "information retrieval",
            "recommendation", "bge", "e5", "dense retrieval", "hybrid search",
            "reranking", "re-ranking", "neural search", "approximate nearest neighbor",
            "ann", "hnsw", "rag", "retrieval augmented"
        ]
        
        self.NICE_TO_HAVE_SKILLS = [
            "llm fine-tuning", "lora", "qlora", "peft", "learning-to-rank", "xgboost",
            "distributed systems", "mlops", "kubernetes", "ray", "a/b testing",
            "ndcg", "mrr", "map", "open-source", "spark", "kafka", "feature store",
            "model serving", "triton", "onnx", "langchain", "llamaindex", "openai"
        ]

        # Component 2 Career Background blacklists and positive targets
        self.CONSULTING_BLACKLIST = [
            "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", 
            "hcl", "tech mahindra", "mphasis", "hexaware", "mindtree", 
            "l&t infotech", "ltimindtree"
        ]

        self.STRONG_AI_TITLES = [
            "machine learning engineer", "ml engineer", "ai engineer", "data scientist", 
            "nlp engineer", "research scientist", "recommendation engineer", 
            "search engineer", "ranking engineer", "retrieval engineer", 
            "senior engineer", "software engineer", "backend engineer", 
            "platform engineer", "full stack engineer", "applied scientist", 
            "data engineer"
        ]

        self.DISQUALIFIED_ONLY_TITLES = [
            "marketing", "sales", "hr manager", "accountant", "graphic designer", 
            "content writer", "civil engineer", "mechanical engineer", 
            "customer support", "operations manager", "business analyst", 
            "supply chain"
        ]

        self.AI_KEYWORDS = [
            "embedding", "vector", "retrieval", "ranking", "recommendation", "search", 
            "nlp", "transformer", "neural", "machine learning", "deep learning", 
            "fine-tun", "rag", "llm", "bert", "gpt", "semantic", "dense", "sparse", 
            "hybrid", "rerank", "faiss", "pinecone", "weaviate", "elasticsearch", 
            "opensearch", "similarity", "approximate nearest neighbor", "hnsw"
        ]

        # Component 5 Location preferred hubs
        self.PREFERRED_CITIES_T1 = [
            "pune", "noida", "hyderabad", "mumbai", "delhi", "gurugram", 
            "gurgaon", "bangalore", "bengaluru", "chennai", "new delhi", "ncr"
        ]
        
        self.PREFERRED_CITIES_T2 = [
            "kolkata", "ahmedabad", "jaipur", "kochi", "coimbatore", "indore", "bhopal"
        ]

        # Component 6 Certifications criteria
        self.RELEVANT_CERTS = [
            "aws certified machine learning", "google professional ml",
            "tensorflow developer", "pytorch", "deep learning specialization",
            "coursera machine learning", "stanford ml", "fast.ai",
            "databricks ml", "snowflake", "kubernetes", "aws solutions architect",
            "google cloud professional", "microsoft azure ai",
            "professional data engineer", "nlp specialization",
            "hugging face", "deeplearning.ai", "mlops", "information retrieval"
        ]

    def score_skills(self, candidate: dict) -> float:
        """
        Scores candidate skill match against the JD using trust multipliers and title penalties.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: A skills score between 0.0 and 1.0.
        """
        try:
            skills = candidate.get("skills", [])
            if not skills:
                return 0.0

            signals = candidate.get("redrob_signals", {})
            skill_assessment_scores = signals.get("skill_assessment_scores", {})
            
            total_contribution = 0.0

            for s in skills:
                skill_name_orig = s.get("name", "")
                skill_name = skill_name_orig.lower().strip()
                if not skill_name:
                    continue

                # 1. Check MUST_HAVE or NICE_TO_HAVE matching (case-insensitive partial match)
                is_must = any(mh in skill_name or skill_name in mh for mh in self.MUST_HAVE_SKILLS)
                is_nice = False
                if not is_must:
                    is_nice = any(nth in skill_name or skill_name in nth for nth in self.NICE_TO_HAVE_SKILLS)

                if not (is_must or is_nice):
                    continue

                # 2. Calculate trust score
                endorsements = float(s.get("endorsements", 0) or 0)
                duration_months = float(s.get("duration_months", 0) or 0)
                proficiency = s.get("proficiency", "").lower().strip()

                trust = (endorsements / 15.0) * 0.35 + (duration_months / 18.0) * 0.65
                trust = min(1.0, max(0.05, trust))

                # Special cases for trust multiplier
                if proficiency == "expert" and duration_months == 0:
                    trust = 0.05
                elif proficiency == "expert" and duration_months < 3:
                    trust *= 0.3
                elif proficiency == "beginner":
                    trust *= 0.4
                elif proficiency == "intermediate":
                    trust *= 0.7
                elif proficiency == "advanced":
                    trust *= 0.9
                elif proficiency == "expert":
                    trust *= 1.0

                # 3. Check skill_assessment_scores in redrob_signals
                assessment_score = None
                if skill_assessment_scores:
                    if skill_name_orig in skill_assessment_scores:
                        assessment_score = skill_assessment_scores[skill_name_orig]
                    else:
                        for k, v in skill_assessment_scores.items():
                            if k.lower().strip() == skill_name:
                                assessment_score = v
                                break

                if assessment_score is not None:
                    assessment_bonus = (float(assessment_score) / 100.0) * 0.3
                    trust = min(1.0, trust + assessment_bonus)

                # 4. Contribution calculation
                if is_must:
                    contribution = trust * 1.0
                else:
                    contribution = trust * 0.4

                total_contribution += contribution

            # Cap total contribution at 1.0
            skills_score = min(1.0, total_contribution)

            # 5. Apply TITLE PENALTY
            PENALIZED_TITLES = [
                "marketing", "sales", "accountant", "hr", "human resources", 
                "operations", "supply chain", "customer support", "finance", 
                "procurement", "legal", "administrative", "civil engineer", 
                "mechanical engineer", "receptionist", "graphic designer", 
                "content writer"
            ]
            current_title = candidate.get("profile", {}).get("current_title", "").lower().strip()
            if any(pt in current_title for pt in PENALIZED_TITLES):
                skills_score *= 0.2

            return max(0.0, min(1.0, skills_score))
        except Exception:
            # Safe default fallback
            return 0.5

    def score_career(self, candidate: dict) -> float:
        """
        Scores career quality against JD requirements, rewarding relevant work 
        history/sizes/tenures and penalizing consulting-only background.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: A career score between 0.0 and 1.0.
        """
        try:
            career_history = candidate.get("career_history", [])
            if not career_history:
                return 0.0

            total_months = 0.0
            consulting_months = 0.0
            career_score = 0.0

            # 1. Calculate consulting ratio metrics
            for role in career_history:
                company = role.get("company", "").lower().strip()
                duration = float(role.get("duration_months", 0) or 0)
                total_months += duration
                
                # Check blacklist matching
                if any(bc in company for bc in self.CONSULTING_BLACKLIST):
                    consulting_months += duration

            consulting_ratio = consulting_months / max(total_months, 1.0)

            # 2. Process each role for bonuses
            for role in career_history:
                title = role.get("title", "").lower().strip()
                desc = role.get("description", "").lower()
                company_size = str(role.get("company_size", "")).strip()
                industry = role.get("industry", "").lower()

                # Title matches STRONG_AI_TITLES bonus (+0.25)
                if any(st in title for st in self.STRONG_AI_TITLES):
                    career_score += 0.25

                # AI_KEYWORDS in description check
                kw_count = sum(1 for kw in self.AI_KEYWORDS if kw in desc)
                if kw_count >= 5:
                    career_score += 0.20
                elif kw_count >= 3:
                    career_score += 0.10
                elif kw_count >= 1:
                    career_score += 0.05

                # Company size & industry check (+0.10)
                valid_size = company_size in ["201-500", "501-1000", "1001-5000", "5001-10000", "10001+"]
                valid_industry = any(ind in industry for ind in [
                    "technology", "software", "ai", "internet", "saas", 
                    "fintech", "edtech", "healthtech"
                ])
                if valid_size and valid_industry:
                    career_score += 0.10

            # Average tenure check (+0.10)
            avg_tenure = total_months / max(len(career_history), 1.0)
            if avg_tenure >= 18.0:
                career_score += 0.10

            # Apply consulting penalties
            if consulting_ratio > 0.8:
                career_score *= 0.1
            elif consulting_ratio > 0.5:
                career_score *= 0.4

            # 3. If ALL career titles are in DISQUALIFIED_ONLY_TITLES -> score = 0.05
            all_disqualified = True
            for role in career_history:
                title = role.get("title", "").lower().strip()
                # If even one title is not in disqualified list, then all are not disqualified
                if not any(dt in title for dt in self.DISQUALIFIED_ONLY_TITLES):
                    all_disqualified = False
                    break
            if all_disqualified:
                career_score = 0.05

            # 4. Cap at 1.0 and return
            return max(0.0, min(1.0, career_score))
        except Exception:
            return 0.5

    def score_experience(self, candidate: dict) -> float:
        """
        Scores years of experience against JD ideal range of 5-9 years.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: An experience alignment score between 0.0 and 1.0.
        """
        try:
            profile = candidate.get("profile", {})
            years = float(profile.get("years_of_experience", 0.0) or 0.0)

            # Map years to experience curve
            if years < 2.0:
                return 0.05
            elif years < 3.0:
                return 0.20
            elif years < 4.0:
                return 0.45
            elif years < 5.0:
                return 0.72
            elif years <= 7.0:
                return 1.00
            elif years <= 9.0:
                return 0.95
            elif years <= 11.0:
                return 0.80
            elif years <= 13.0:
                return 0.65
            else:
                return 0.50
        except Exception:
            return 0.5

    def score_behavioral(self, candidate: dict) -> float:
        """
        Scores candidate engagement based on 23 behavioral signals.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: A behavioral score between 0.0 and 1.0.
        """
        try:
            signals = candidate.get("redrob_signals", {})
            if not signals:
                return 0.0

            today = date.today()

            # 1. RECENCY (weight 0.20)
            recency_score = 0.05
            days_since_active = 999
            last_active_str = signals.get("last_active_date", "")
            if last_active_str:
                try:
                    last_active_date = datetime.strptime(last_active_str, "%Y-%m-%d").date()
                    days_since_active = (today - last_active_date).days
                    if days_since_active < 7:
                        recency_score = 1.0
                    elif days_since_active <= 30:
                        recency_score = 0.85
                    elif days_since_active <= 60:
                        recency_score = 0.65
                    elif days_since_active <= 90:
                        recency_score = 0.45
                    elif days_since_active <= 180:
                        recency_score = 0.20
                    else:
                        recency_score = 0.05
                except ValueError:
                    recency_score = 0.05

            # 2. AVAILABILITY (weight 0.18)
            open_flag = signals.get("open_to_work_flag", False)
            flag_score = 1.0 if open_flag else 0.3
            
            # Map applications submitted in last 30 days
            apps = signals.get("applications_submitted_30d")
            if apps is None:
                apps = signals.get("active_applications_count", 0)
            
            try:
                apps_val = float(apps or 0)
                if apps_val == 0:
                    apps_score = 0.0
                elif apps_val <= 2:
                    apps_score = 0.5
                elif apps_val <= 5:
                    apps_score = 0.8
                else:
                    apps_score = 1.0
            except ValueError:
                apps_score = 0.0

            availability_score = (flag_score + apps_score) / 2.0

            # 3. NOTICE PERIOD (weight 0.15)
            notice_val = signals.get("notice_period_days")
            notice_score = 0.10
            if notice_val is not None:
                try:
                    notice_days = float(notice_val)
                    if notice_days <= 15:
                        notice_score = 1.0
                    elif notice_days <= 30:
                        notice_score = 0.85
                    elif notice_days <= 45:
                        notice_score = 0.65
                    elif notice_days <= 60:
                        notice_score = 0.45
                    elif notice_days <= 90:
                        notice_score = 0.25
                    else:
                        notice_score = 0.10
                except ValueError:
                    notice_score = 0.10

            # 4. RESPONSIVENESS (weight 0.15)
            recruiter_rate = float(signals.get("recruiter_response_rate", 0.0) or 0.0)
            recruiter_rate = max(0.0, min(1.0, recruiter_rate))

            resp_time_val = signals.get("avg_response_time_hours")
            resp_time_score = 0.15
            if resp_time_val is not None:
                try:
                    hours = float(resp_time_val)
                    if hours < 2.0:
                        resp_time_score = 1.0
                    elif hours <= 6.0:
                        resp_time_score = 0.85
                    elif hours <= 24.0:
                        resp_time_score = 0.65
                    elif hours <= 48.0:
                        resp_time_score = 0.40
                    else:
                        resp_time_score = 0.15
                except ValueError:
                    resp_time_score = 0.15
            
            interview_rate = float(signals.get("interview_completion_rate", 0.0) or 0.0)
            interview_rate = max(0.0, min(1.0, interview_rate))

            responsiveness_score = (recruiter_rate + resp_time_score + interview_rate) / 3.0

            # 5. PLATFORM TRUST (weight 0.12)
            trust_sum = 0.0
            if signals.get("verified_email") is True:
                trust_sum += 0.5
            if signals.get("verified_phone") is True:
                trust_sum += 0.3
            if signals.get("linkedin_connected") is True:
                trust_sum += 0.2
            platform_trust_score = min(1.0, trust_sum)

            # 6. MARKET DEMAND (weight 0.10)
            saved = signals.get("saved_by_recruiters_30d")
            saved_score = 0.1
            if saved is not None:
                try:
                    s_val = float(saved)
                    if s_val == 0:
                        saved_score = 0.1
                    elif s_val <= 2:
                        saved_score = 0.4
                    elif s_val <= 5:
                        saved_score = 0.7
                    elif s_val <= 10:
                        saved_score = 0.9
                    else:
                        saved_score = 1.0
                except ValueError:
                    saved_score = 0.1

            views = signals.get("profile_views_received_30d", signals.get("profile_views_last_30_days"))
            views_score = 0.2
            if views is not None:
                try:
                    v_val = float(views)
                    if v_val <= 5:
                        views_score = 0.2
                    elif v_val <= 20:
                        views_score = 0.5
                    elif v_val <= 50:
                        views_score = 0.8
                    else:
                        views_score = 1.0
                except ValueError:
                    views_score = 0.2

            market_demand_score = (saved_score + views_score) / 2.0

            # 7. PROFILE QUALITY (weight 0.05)
            comp_score = signals.get("profile_completeness_score", signals.get("profile_completeness", 0.0))
            try:
                comp_val = float(comp_score or 0.0)
                if comp_val > 1.0:
                    profile_quality_score = comp_val / 100.0
                else:
                    profile_quality_score = comp_val
            except ValueError:
                profile_quality_score = 0.0
            profile_quality_score = max(0.0, min(1.0, profile_quality_score))

            # 8. GITHUB ACTIVITY (weight 0.05)
            github = signals.get("github_activity_score", -1)
            github_score = 0.3
            if github is not None and github != -1:
                try:
                    git_val = float(github)
                    if git_val <= 20:
                        github_score = 0.2
                    elif git_val <= 50:
                        github_score = 0.5
                    elif git_val <= 75:
                        github_score = 0.75
                    else:
                        github_score = 1.0
                except ValueError:
                    github_score = 0.3

            # Calculate weighted average
            behavioral_score = (
                0.20 * recency_score +
                0.18 * availability_score +
                0.15 * notice_score +
                0.15 * responsiveness_score +
                0.12 * platform_trust_score +
                0.10 * market_demand_score +
                0.05 * profile_quality_score +
                0.05 * github_score
            )

            # SPECIAL MULTIPLIERS
            if open_flag is True and days_since_active < 30 and recruiter_rate > 0.7:
                behavioral_score *= 1.15

            if open_flag is False and days_since_active > 180:
                behavioral_score *= 0.4

            offer_rate = signals.get("offer_acceptance_rate", -1)
            if offer_rate is not None and offer_rate != -1:
                try:
                    or_val = float(offer_rate)
                    if or_val < 0.3:
                        behavioral_score *= 0.85
                    elif or_val > 0.7:
                        behavioral_score *= 1.05
                except ValueError:
                    pass

            return max(0.0, min(1.0, behavioral_score))
        except Exception:
            return 0.5

    def score_location(self, candidate: dict) -> float:
        """
        Scores candidate location alignment based on preferred cities and relocation.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: A location score between 0.0 and 1.0.
        """
        try:
            profile = candidate.get("profile", {})
            location = profile.get("location", "").lower().strip()
            country = profile.get("country", "").lower().strip()
            signals = candidate.get("redrob_signals", {})

            # Tier 1 check
            if any(city in location for city in self.PREFERRED_CITIES_T1):
                return 1.0

            # Relocation check
            willing = (candidate.get("willing_to_relocate") is True or
                       profile.get("willing_to_relocate") is True or
                       signals.get("willing_to_relocate") is True)
            if willing:
                return 0.85

            is_india = "india" in country or country == "in"
            if is_india:
                # Tier 2 check
                if any(city in location for city in self.PREFERRED_CITIES_T2):
                    return 0.7
                return 0.5

            return 0.15
        except Exception:
            return 0.5

    def score_certifications(self, candidate: dict) -> float:
        """
        Scores candidate certifications for AI/ML relevance and recency.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            float: A certifications score between 0.0 and 1.0.
        """
        try:
            certifications = candidate.get("certifications")
            if certifications is None or not isinstance(certifications, list) or len(certifications) == 0:
                return 0.3

            cert_score = 0.0
            for cert in certifications:
                name = cert.get("name", "").lower().strip()
                if not name:
                    continue

                if any(rc in name for rc in self.RELEVANT_CERTS):
                    cert_score += 0.25
                    year = cert.get("year")
                    if year is not None:
                        try:
                            year_val = int(year)
                            if year_val >= 2022:
                                cert_score += 0.10
                        except ValueError:
                            pass

            return max(0.0, min(1.0, cert_score))
        except Exception:
            return 0.5

    def score(self, candidate: dict) -> dict:
        """
        Combines all 6 components to yield a final matching score and a unique, 
        fact-based reasoning summary.

        Args:
            candidate (dict): The candidate profile dictionary.

        Returns:
            dict: The scores breakdown and descriptive explanation.
        """
        candidate_id = candidate.get("candidate_id", "Unknown")

        # 1. Run all scoring components with safety guards
        skills_s = self.score_skills(candidate)
        career_s = self.score_career(candidate)
        experience_s = self.score_experience(candidate)
        behavioral_s = self.score_behavioral(candidate)
        location_s = self.score_location(candidate)
        certs_s = self.score_certifications(candidate)

        # 2. Combine using exact weights
        final_score = (
            0.30 * skills_s +
            0.28 * career_s +
            0.12 * experience_s +
            0.20 * behavioral_s +
            0.07 * location_s +
            0.03 * certs_s
        )

        final_score = round(max(0.0, min(1.0, final_score)), 6)

        # 3. Collect details for dynamic reasoning
        profile = candidate.get("profile", {})
        signals = candidate.get("redrob_signals", {})
        history = candidate.get("career_history", [])

        years = float(profile.get("years_of_experience", 0.0) or 0.0)
        title = profile.get("current_title", "Engineer")
        
        # Determine current/most recent company size and name
        current_company = "Unknown"
        company_size = "N/A"
        is_product = False
        consulting_months = 0.0
        total_months = 0.0

        for role in history:
            co = role.get("company", "").strip()
            co_lower = co.lower()
            dur = float(role.get("duration_months", 0) or 0)
            total_months += dur

            if any(bc in co_lower for bc in self.CONSULTING_BLACKLIST):
                consulting_months += dur

            if role.get("is_current") is True or current_company == "Unknown":
                current_company = co
                company_size = str(role.get("company_size", "N/A")).strip()
                
                # Product check
                ind_lower = role.get("industry", "").lower()
                valid_size = company_size in ["201-500", "501-1000", "1001-5000", "5001-10000", "10001+"]
                valid_ind = any(ind in ind_lower for ind in [
                    "technology", "software", "ai", "internet", "saas", 
                    "fintech", "edtech", "healthtech"
                ])
                if valid_size and valid_ind:
                    is_product = True

        consulting_ratio = consulting_months / max(total_months, 1.0)

        # Extract top 2 MUST_HAVE skills matched
        matched_must_haves = []
        for s in candidate.get("skills", []):
            name = s.get("name", "")
            name_lower = name.lower().strip()
            
            is_must = any(mh in name_lower or name_lower in mh for mh in self.MUST_HAVE_SKILLS)
            if is_must:
                # Recalculate trust for display / ranking in reasoning
                endorsements = float(s.get("endorsements", 0) or 0)
                dur = float(s.get("duration_months", 0) or 0)
                prof = s.get("proficiency", "Intermediate").strip()
                
                trust = (endorsements / 15.0) * 0.35 + (dur / 18.0) * 0.65
                trust = min(1.0, max(0.05, trust))
                matched_must_haves.append((name, trust, prof, int(dur)))

        # Sort by trust score descending
        matched_must_haves.sort(key=lambda x: x[1], reverse=True)

        top_skills_list = []
        for name, _, prof, dur in matched_must_haves[:2]:
            top_skills_list.append(f"{name} ({prof.lower()}, {dur}mo)")

        if top_skills_list:
            top_skills_str = "Top JD skills: " + ", ".join(top_skills_list)
        else:
            top_skills_str = "No vector DB or core NLP skills matched"

        notice = signals.get("notice_period_days", "N/A")
        notice_part = f"Notice: {notice}d" if notice is not None else "Notice: N/A"

        resp_rate = signals.get("recruiter_response_rate")
        resp_pct = f"{int(resp_rate * 100)}%" if resp_rate is not None else "N/A"

        # Generate a distinct positive signal
        positives = []
        if signals.get("open_to_work_flag") is True:
            positives.append("actively seeking (open to work)")
        if float(signals.get("github_activity_score", -1) or -1) > 60:
            positives.append(f"strong GitHub activity ({signals.get('github_activity_score')})")
        if float(signals.get("assessment_score", 0) or 0) > 80:
            positives.append(f"exceptional assessment score ({signals.get('assessment_score')})")
        if is_product:
            positives.append(f"product company foundation at {current_company}")
        if location_s >= 1.0:
            positives.append("located in core Indian IT hub")

        positive_sig = positives[0] if positives else "steady career timeline"

        # Generate concern or fit status
        if final_score >= 0.8:
            fit_str = "Strong fit for founding team AI role."
        else:
            concerns = []
            if years < 4.0:
                concerns.append(f"years of experience ({years:.1f} yrs) below ideal")
            elif years > 9.0:
                concerns.append(f"years of experience ({years:.1f} yrs) exceeds target")
            if notice is not None and isinstance(notice, (int, float)) and notice > 45:
                concerns.append("long notice period buyout hurdle")
            if resp_rate is not None and resp_rate < 0.6:
                concerns.append("below-average response rates")
            if consulting_ratio > 0.5:
                concerns.append("consulting/service firm dominance")
            if not matched_must_haves:
                concerns.append("missing Pinecone/FAISS semantic search keywords")
            if location_s < 0.5:
                concerns.append("non-local relocation required")

            concern_sig = concerns[0] if concerns else "marginal alignment with AI engineer core stack"
            fit_str = f"Concern: {concern_sig}."

        reasoning = (
            f"{years:.1f} yrs as {title} at {current_company} ({company_size} co). "
            f"{top_skills_str}. "
            f"{notice_part}. Response: {resp_pct}. "
            f"Signal: {positive_sig}. {fit_str}"
        )

        return {
            "candidate_id": candidate_id,
            "final_score": final_score,
            "skills_score": skills_s,
            "career_score": career_s,
            "experience_score": experience_s,
            "behavioral_score": behavioral_s,
            "location_score": location_s,
            "certifications_score": certs_s,
            "reasoning": reasoning
        }


if __name__ == "__main__":
    # Test block to verify correctness on sample_candidates.json
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sample_file_path = os.path.join(current_dir, "sample_candidates.json")

    if not os.path.exists(sample_file_path):
        print(f"Error: sample_candidates.json not found at {sample_file_path}")
    else:
        print(f"Loading sample candidates from: {sample_file_path}")
        with open(sample_file_path, "r", encoding="utf-8") as f:
            candidates = json.load(f)

        scorer = CandidateScorer()
        first_5 = candidates[:5]
        
        reasoning_strings = []
        print("\n=== Scoring first 5 candidates ===")
        for i, candidate in enumerate(first_5, start=1):
            scores = scorer.score(candidate)
            reasoning_strings.append(scores["reasoning"])
            print(f"\nCandidate #{i} (ID: {scores['candidate_id']}):")
            print(f"  Final Score:          {scores['final_score']:.6f}")
            print(f"  Skills Score:         {scores['skills_score']:.4f}")
            print(f"  Career Score:         {scores['career_score']:.4f}")
            print(f"  Experience Score:     {scores['experience_score']:.4f}")
            print(f"  Behavioral Score:     {scores['behavioral_score']:.4f}")
            print(f"  Location Score:       {scores['location_score']:.4f}")
            print(f"  Certifications Score: {scores['certifications_score']:.4f}")
            print(f"  Reasoning:            {scores['reasoning']}")
            print("-" * 80)

        # Check for reasoning uniqueness
        unique_reasonings = set(reasoning_strings)
        if len(unique_reasonings) == 5:
            print("\nReasoning uniqueness check: PASSED")
        else:
            print(f"\nReasoning uniqueness check: FAILED (only {len(unique_reasonings)} unique strings out of 5)")
