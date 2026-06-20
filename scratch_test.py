import os
import sys
from matcher import extract_text_from_pdf, parse_skills, calculate_local_match
from apify_scraper import scrape_linkedin_jobs

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration
RESUME_FILE = "Mohammad_Arbaz_Resume_06042026.pdf"
APIFY_TOKEN = os.getenv("APIFY_TOKEN") or ""
TEST_KEYWORD = "Python Data Engineer"
TEST_LOCATION = "Hyderabad, India"

def run_integration_tests():
    print("=" * 60)
    print("STARTING INTEGRATION TESTS FOR LINKEDIN JOB HUNTER")
    print("=" * 60)
    
    # 1. Verify Resume File Existence
    if not os.path.exists(RESUME_FILE):
        print(f"[-] ERROR: Resume file '{RESUME_FILE}' not found in workspace.")
        sys.exit(1)
    print(f"[+] Found resume file: {RESUME_FILE}")
    
    # 2. Test PDF Text Extraction
    print("\n[Running Test 1/4] Extracting text from PDF...")
    try:
        with open(RESUME_FILE, "rb") as f:
            resume_text = extract_text_from_pdf(f)
        if not resume_text.strip():
            print("[-] ERROR: Extracted resume text is empty.")
            sys.exit(1)
        print(f"[+] Successfully extracted {len(resume_text)} characters from PDF.")
    except Exception as e:
        print(f"[-] ERROR: Failed to extract PDF text: {e}")
        sys.exit(1)
        
    # 3. Test Skills Parsing (Case-Insensitive)
    print("\n[Running Test 2/4] Parsing technical skills from text...")
    try:
        skills = parse_skills(resume_text)
        print(f"[+] Successfully parsed {len(skills)} skills:")
        print(f"    {', '.join(skills)}")
        
        # Verify specific expected skills from Mohammad Arbaz's resume
        expected_skills = ["Python", "SQL", "Snowflake", "PySpark", "MongoDB", "MySQL"]
        missing_expected = [s for s in expected_skills if s not in skills]
        if missing_expected:
            print(f"[-] WARNING: Expected skills {missing_expected} were not parsed.")
        else:
            print("[+] Success: All key benchmark skills (Python, SQL, Snowflake, etc.) parsed successfully!")
    except Exception as e:
        print(f"[-] ERROR: Failed to parse skills: {e}")
        sys.exit(1)
        
    # 4. Test Apify Scraper Connectivity
    print("\n[Running Test 3/4] Triggering Apify LinkedIn Scraper (1 Page)...")
    try:
        jobs = scrape_linkedin_jobs(
            api_token=APIFY_TOKEN,
            keyword=TEST_KEYWORD,
            location=TEST_LOCATION,
            country="india",
            job_type="Any",
            date_posted="Any",
            pages_to_fetch=1
        )
        print(f"[+] Success: Scraper completed successfully. Retrieved {len(jobs)} jobs.")
        if not jobs:
            print("[-] WARNING: Apify returned 0 jobs for search criteria.")
    except Exception as e:
        print(f"[-] ERROR: Apify scraping execution failed: {e}")
        sys.exit(1)
        
    # 5. Test Job Matching & Scoring
    print("\n[Running Test 4/4] Running local scoring engine on scraped jobs...")
    try:
        scored_jobs = []
        for idx, job in enumerate(jobs):
            match_result = calculate_local_match(
                resume_text=resume_text,
                resume_skills=skills,
                job_description=job["description"]
            )
            scored_jobs.append({
                "title": job["title"],
                "company": job["company"],
                "score": match_result["score"],
                "matched_skills": match_result["matched_skills"],
                "missing_skills": match_result["missing_skills"]
            })
            
        # Sort by match score
        scored_jobs = sorted(scored_jobs, key=lambda x: x["score"], reverse=True)
        
        print(f"[+] Scored {len(scored_jobs)} jobs successfully.")
        print("\n" + "=" * 60)
        print("JOB MATCHING REPORT SUMMARY")
        print("=" * 60)
        for idx, s_job in enumerate(scored_jobs[:5]):
            print(f"[{idx+1}] {s_job['title']} at {s_job['company']}")
            print(f"    Match Score: {s_job['score']}%")
            print(f"    Matched Skills: {', '.join(s_job['matched_skills'][:5])}")
            print(f"    Missing Skills: {', '.join(s_job['missing_skills'][:5])}")
            print("-" * 40)
            
    except Exception as e:
        print(f"[-] ERROR: Job matching engine failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_integration_tests()
