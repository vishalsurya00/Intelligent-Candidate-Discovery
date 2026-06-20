"""
rank.py: Main entry point for the Redrob candidate ranking system.

This module coordinates the end-to-end ranking pipeline for the hackathon. 
It loads candidates from JSONL files, filters out and penalizes fraudulent 
honeypot profiles, scores clean candidates using the CandidateScorer, 
and generates a compliant submission CSV.
"""

import os
import csv
import sys
import time
import argparse
import re
from tqdm import tqdm

# Import candidate data handling components
from loader import CandidateLoader
from scorer import CandidateScorer
from honeypot_detector import HoneypotDetector

class CandidateRanker:
    """
    Ranker engine orchestrating candidate parsing, filtering, scoring, and output generation.

    Why: Serves as the central pipeline runner to ensure correct order of execution 
         and validation checks.
    """

    def __init__(self, candidates_path: str, output_path: str):
        """
        Initializes the CandidateRanker with input and output paths.

        Args:
            candidates_path (str): Path to the input JSONL file containing candidate data.
            output_path (str): Path where the final submission CSV should be written.

        Why: Configures references for all pipeline stages.
        """
        self.candidates_path = candidates_path
        self.output_path = output_path
        
        # Instantiate dependencies
        self.loader = CandidateLoader(candidates_path)
        self.scorer = CandidateScorer()
        self.detector = HoneypotDetector()
        
        # Store results
        self.results = []
        self.top_candidates = []
        self.written_count = 0

    def run(self):
        """
        Runs the full candidate ranking pipeline end-to-end.

        Why: Sequentially executes load, check-and-score, sorting, and file writing stages
             while printing wall-clock execution metrics.
        """
        start_wall_time = time.perf_counter()

        # -------------------------------------------------------------
        # STAGE 1: Load candidates
        # -------------------------------------------------------------
        stage1_start = time.perf_counter()
        print("\n--- Stage 1: Loading Candidate Dataset ---")
        candidates = self.loader.load_all()
        stage1_time = time.perf_counter() - stage1_start
        print(f"Stage 1: Loaded {len(candidates)} candidates in {stage1_time:.4f} seconds")

        # -------------------------------------------------------------
        # STAGE 1.5: ID Cross-Check
        # -------------------------------------------------------------
        stage1_5_start = time.perf_counter()
        print("\n--- Stage 1.5: Running ID Cross-Check ---")
        invalid_id_count = 0
        id_pattern = re.compile(r"^CAND_[0-9]{7}$")
        for idx, candidate in enumerate(candidates):
            cand_id = candidate.get("candidate_id", "")
            if not isinstance(cand_id, str) or not id_pattern.match(cand_id):
                invalid_id_count += 1
                warnings.warn(f"Invalid candidate_id format found at record {idx+1}: {cand_id}")
        
        stage1_5_time = time.perf_counter() - stage1_5_start
        print(f"Stage 1.5: ID Cross-Check completed in {stage1_5_time:.4f} seconds. Invalid candidate IDs found: {invalid_id_count}")

        # -------------------------------------------------------------
        # STAGE 2: Score + honeypot check (combined loop for speed)
        # -------------------------------------------------------------
        stage2_start = time.perf_counter()
        print("\n--- Stage 2: Processing and Scoring Candidates ---")
        
        self.results = []
        honeypot_count = 0
        processed_count = 0

        # Iterating through all candidates with a tqdm progress bar
        for candidate in tqdm(candidates, desc="Scoring Candidates"):
            try:
                cand_id = candidate.get("candidate_id", "Unknown")
                
                # Check if the candidate profile is a fraudulent honeypot
                honeypot_verdict = self.detector.is_honeypot(candidate)
                
                if honeypot_verdict["is_honeypot"]:
                    honeypot_count += 1
                    flags_joined = "; ".join(honeypot_verdict["flags"])
                    score_result = {
                        "candidate_id": cand_id,
                        "final_score": 0.0,
                        "skills_score": 0.0,
                        "career_score": 0.0,
                        "experience_score": 0.0,
                        "behavioral_score": 0.0,
                        "location_score": 0.0,
                        "certifications_score": 0.0,
                        "reasoning": f"DISQUALIFIED: {flags_joined}"
                    }
                else:
                    # Score standard non-honeypot candidate profiles
                    score_result = self.scorer.score(candidate)
            except Exception as e:
                # Catch exceptions on bad records to prevent crashing the pipeline run
                score_result = {
                    "candidate_id": candidate.get("candidate_id", "Unknown"),
                    "final_score": 0.0,
                    "skills_score": 0.0,
                    "career_score": 0.0,
                    "experience_score": 0.0,
                    "behavioral_score": 0.0,
                    "location_score": 0.0,
                    "certifications_score": 0.0,
                    "reasoning": "ERROR: could not score"
                }

            self.results.append(score_result)
            processed_count += 1

            # Print text logs every 10,000 candidates processed
            if processed_count % 10000 == 0:
                print(f"[Progress] Scored {processed_count} profiles. Active honeypot filters flagged {honeypot_count}.")

        stage2_time = time.perf_counter() - stage2_start
        print(f"Stage 2: Scored {len(candidates)} candidates in {stage2_time:.4f} seconds ({honeypot_count} honeypots removed)")

        # -------------------------------------------------------------
        # STAGE 3: Sort and select top 100
        # -------------------------------------------------------------
        stage3_start = time.perf_counter()
        print("\n--- Stage 3: Sorting and Selecting Top Candidates ---")

        # Sorting rule: final_score descending, tiebroken by candidate_id ascending
        self.results.sort(key=lambda x: (-x["final_score"], x["candidate_id"]))
        
        # Take the top 100 (or fewer if total dataset is small)
        self.top_candidates = self.results[:100]
        
        # Determine score range metrics
        if self.top_candidates:
            max_score = self.top_candidates[0]["final_score"]
            min_score = self.top_candidates[-1]["final_score"]
        else:
            max_score, min_score = 0.0, 0.0

        stage3_time = time.perf_counter() - stage3_start
        limit_str = f"Top {len(self.top_candidates)}" if len(self.results) < 100 else "Top 100"
        print(f"Stage 3: {limit_str} selected. Score range: {min_score:.3f} to {max_score:.3f}")

        # -------------------------------------------------------------
        # STAGE 4: Write CSV
        # -------------------------------------------------------------
        stage4_start = time.perf_counter()
        print("\n--- Stage 4: Writing Results to Submission CSV ---")

        # Verification step: scores must be non-increasing in output sequence
        for idx in range(len(self.top_candidates) - 1):
            if self.top_candidates[idx]["final_score"] < self.top_candidates[idx + 1]["final_score"]:
                raise ValueError(
                    f"Sorting Discrepancy Error: Candidate at rank {idx+1} has score {self.top_candidates[idx]['final_score']}, "
                    f"which is less than candidate at rank {idx+2} with score {self.top_candidates[idx+1]['final_score']}."
                )

        # Write CSV fields
        try:
            with open(self.output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Write standard headers
                writer.writerow(["candidate_id", "rank", "score", "reasoning"])
                
                for pos, result in enumerate(self.top_candidates, start=1):
                    writer.writerow([
                        result["candidate_id"],
                        pos,
                        round(result["final_score"], 6),
                        result["reasoning"]
                    ])
            self.written_count = len(self.top_candidates)
        except IOError as e:
            print(f"[Error] Failed to write CSV file: {e}")
            raise e

        stage4_time = time.perf_counter() - stage4_start
        print(f"Stage 4: CSV written to {self.output_path}")

        total_wall_time = time.perf_counter() - start_wall_time
        print(f"Total wall-clock execution time: {total_wall_time:.4f} seconds\n")

    def validate_output(self) -> bool:
        """
        Performs post-write validation on the generated submission CSV.

        Reads the CSV file, verifying that it contains the expected row count, 
        each rank from 1 to expected appears exactly once, there are no duplicate 
        candidate IDs, and scores are strictly non-increasing.

        Why: Ensures the output file is in the exact format required by the 
             Streamlit Cloud submission portal, preventing submission errors.

        Returns:
            bool: True if validation passes, False otherwise.
        """
        if not os.path.exists(self.output_path):
            print(f"[Validation] FAILED: Output file {self.output_path} does not exist.")
            return False

        try:
            records = []
            with open(self.output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)

            # Determine dynamic expected row count (typically 100, or fewer if testing with smaller dataset)
            expected_rows = getattr(self, "written_count", 100)
            if len(records) != expected_rows:
                print(f"[Validation] FAILED: CSV contains {len(records)} rows, expected {expected_rows}.")
                return False

            ranks = []
            candidate_ids = set()
            prev_score = float('inf')

            for idx, row in enumerate(records, start=1):
                cand_id = row.get("candidate_id")
                rank_str = row.get("rank")
                score_str = row.get("score")

                if not cand_id or not rank_str or not score_str:
                    print(f"[Validation] FAILED: Missing fields in CSV row {idx}.")
                    return False

                # Convert values
                rank_val = int(rank_str)
                score_val = float(score_str)

                # Check for duplicate candidate IDs
                if cand_id in candidate_ids:
                    print(f"[Validation] FAILED: Duplicate candidate ID '{cand_id}' found at rank {rank_val}.")
                    return False
                candidate_ids.add(cand_id)

                ranks.append(rank_val)

                # Check that scores are non-increasing
                if score_val > prev_score:
                    print(f"[Validation] FAILED: Score increases at rank {rank_val} (previous: {prev_score}, current: {score_val}).")
                    return False
                prev_score = score_val

            # Check that ranks appear sequentially exactly once
            expected_ranks = list(range(1, expected_rows + 1))
            if sorted(ranks) != expected_ranks:
                print("[Validation] FAILED: Ranks are not sequential.")
                return False

            print(f"[Validation] PASSED: CSV is fully compliant with submission rules ({expected_rows} rows, unique IDs, correct ranks, non-increasing scores).")
            return True

        except Exception as e:
            print(f"[Validation] FAILED: Unexpected error during file check: {e}")
            return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Redrob Hackathon — Candidate Ranker"
    )
    parser.add_argument(
        "--candidates", 
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_candidates.json"),
        help="Path to candidates JSONL file"
    )
    parser.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "submission.csv"), 
        help="Output CSV path"
    )
    args = parser.parse_args()
    
    # Run ranking pipeline
    ranker = CandidateRanker(args.candidates, args.out)
    ranker.run()
    ranker.validate_output()
