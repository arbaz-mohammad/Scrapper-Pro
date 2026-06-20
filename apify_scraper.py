import logging
from apify_client import ApifyClient

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import urllib.parse

def scrape_linkedin_jobs(
    api_token: str,
    keyword: str,
    location: str,
    country: str = "all",
    job_type: str = None,
    date_posted: str = None,
    pages_to_fetch: int = 3,
    target_companies: str = None
):
    """
    Triggers the 'curious_coder/linkedin-jobs-scraper' actor on Apify to fetch job listings.
    This actor is compute-only and free to use without any rental fees.
    
    Args:
        api_token (str): Apify API token.
        keyword (str): Job title or skill keyword (e.g. "Python Developer").
        location (str): Location filter (e.g. "San Francisco, CA").
        country (str): Country context (ignored for URL-based scraping).
        job_type (str): Optional. Job type (FULLTIME, PARTTIME, CONTRACTOR, INTERN).
        date_posted (str): Optional. Recency filter (today, 3days, week, month).
        pages_to_fetch (int): Scale factor mapping to total count of jobs to scrape.
        target_companies (str): Optional. Comma-separated list of target companies.
        
    Returns:
        list[dict]: List of scraped job listings.
    """
    if not api_token:
        raise ValueError("Apify API Token is required.")
        
    client = ApifyClient(api_token)
    
    # Process target companies if provided
    target_companies_list = []
    if target_companies:
        target_companies_list = [c.strip() for c in target_companies.split(",") if c.strip()]
        
    # Modify keyword query if target companies are specified
    scraper_keyword = keyword
    if target_companies_list:
        companies_query = " OR ".join(f'"{c}"' for c in target_companies_list)
        scraper_keyword = f"({keyword}) AND ({companies_query})"
        
    # 1. Programmatically construct the LinkedIn Jobs Search URL
    encoded_keyword = urllib.parse.quote(scraper_keyword)
    encoded_location = urllib.parse.quote(location)
    
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_keyword}&location={encoded_location}"
    
    # Map and append Job Type filters
    if job_type and job_type != "Any":
        jt_map = {
            "FULLTIME": "F",
            "FULL-TIME": "F",
            "PARTTIME": "P",
            "PART-TIME": "P",
            "CONTRACT": "C",
            "CONTRACTOR": "C",
            "INTERN": "I",
            "INTERNSHIP": "I"
        }
        jt_val = jt_map.get(job_type.upper())
        if jt_val:
            search_url += f"&f_JT={jt_val}"
            
    # Map and append Date Posted filters
    if date_posted and date_posted != "Any":
        dp_map = {
            "TODAY": "r86400",
            "3DAYS": "r259200",
            "3 DAYS": "r259200",
            "WEEK": "r604800",
            "MONTH": "r2592000"
        }
        dp_val = dp_map.get(date_posted.upper())
        if dp_val:
            search_url += f"&f_TPR={dp_val}"
            
    # 2. Configure the curious_coder/linkedin-jobs-scraper inputs
    # 1 page of results normally yields 25 jobs, so we map count as pages_to_fetch * 25
    run_input = {
        "urls": [search_url],
        "scrapeCompany": False,  # Speed up runs and save compute credits
        "count": int(pages_to_fetch * 25),
        "splitByLocation": False
    }

    logger.info(f"Triggering curious_coder/linkedin-jobs-scraper with input: {run_input}")
    
    try:
        # Start the actor run and wait for it to finish (blocking call)
        run = client.actor("curious_coder/linkedin-jobs-scraper").call(run_input=run_input)
        
        # Check run status
        logger.info(f"Run completed. Status: {run.get('status')}")
        
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            logger.error("No dataset ID returned from the actor run.")
            return []
            
        # Fetch the results from the dataset
        dataset_items = client.dataset(dataset_id).list_items().items
        logger.info(f"Successfully retrieved {len(dataset_items)} items from dataset.")
        
        # Standardize the output fields to make it resilient to scraper schema updates
        standardized_jobs = []
        for item in dataset_items:
            # Map possible field names to a consistent schema
            title = item.get("positionName") or item.get("title") or item.get("jobTitle")
            company = item.get("companyName") or item.get("company") or item.get("companyId")
            job_url = item.get("link") or item.get("jobUrl") or item.get("url") or item.get("applyUrl") or item.get("applyLink")
            description = item.get("description") or item.get("jobDescription") or item.get("descriptionText")
            loc = item.get("locationName") or item.get("location") or item.get("jobLocation")
            posted_date = item.get("postedAt") or item.get("postedDate") or item.get("datePosted")
            
            # Skip items that lack critical fields
            if not title or not company:
                continue
                
            # If target companies are defined, filter locally as well
            if target_companies_list:
                comp_lower = company.lower().strip()
                if not any(tc.lower() in comp_lower for tc in target_companies_list):
                    continue
                    
            standardized_jobs.append({
                "title": title.strip(),
                "company": company.strip(),
                "location": loc.strip() if loc else "N/A",
                "job_url": job_url.strip() if job_url else "",
                "description": description.strip() if description else "No description provided.",
                "posted_date": posted_date.strip() if posted_date else "N/A"
            })
            
        return standardized_jobs
        
    except Exception as e:
        logger.exception("Error while running Apify scraper")
        raise e
