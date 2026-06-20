from __future__ import annotations
import re
import json
import os
import PyPDF2
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# A curated dictionary of popular industry skills and technologies
TECH_SKILLS_DB = [
    # Programming Languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "C", "Go", "Golang", "Rust", 
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "SQL", "HTML", "CSS", "Bash", "Shell",
    # Frameworks & Libraries
    "React", "Angular", "Vue", "Next.js", "Nuxt.js", "Express", "Node.js", "Django", "Flask", 
    "FastAPI", "Spring Boot", "Laravel", "Ruby on Rails", "PyTorch", "TensorFlow", "Keras", 
    "Scikit-Learn", "Pandas", "NumPy", "OpenCV", "Hugging Face", "Tailwind CSS", "Bootstrap", "PySpark",
    # Cloud & DevOps
    "AWS", "Amazon Web Services", "Azure", "Google Cloud", "GCP", "Docker", "Kubernetes", 
    "Terraform", "Ansible", "Jenkins", "GitHub Actions", "CI/CD", "Git", "Linux", "Unix",
    # Databases & Caching
    "PostgreSQL", "MySQL", "MongoDB", "SQLite", "Redis", "Elasticsearch", "Cassandra", 
    "DynamoDB", "Firebase", "Oracle", "MariaDB", "Snowflake",
    # Architecture & Concepts
    "Microservices", "REST API", "RESTful", "GraphQL", "gRPC", "WebSockets", "Serverless",
    "Agile", "Scrum", "DevOps", "OOP", "Object-Oriented", "MVC", "System Design",
    # AI & Data Science
    "Machine Learning", "Deep Learning", "Artificial Intelligence", "AI", "NLP", 
    "Natural Language Processing", "Computer Vision", "LLM", "Large Language Models",
    "Generative AI", "RAG", "Data Engineering", "Data Analytics", "Spark", "Hadoop",
    "Power BI", "Tableau", "Llama", "Ollama", "Groq"
]

CACHE_FILE = ".resume_cache.json"

def extract_text_from_pdf(pdf_file) -> str:
    """Extracts all text from an uploaded PDF file-like object."""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        raise RuntimeError(f"Failed to parse PDF resume: {e}")

def parse_skills(text: str) -> list[str]:
    """Scans text for occurrences of skills in TECH_SKILLS_DB using word boundary matching."""
    text_lower = text.lower()
    found_skills = set()
    
    for skill in TECH_SKILLS_DB:
        # Match using word boundaries, accounting for special characters like C++, C#, .NET
        escaped_skill = re.escape(skill.lower())
        # Handle special endings like ++, #, .js
        if skill.endswith("++") or skill.endswith("#") or skill.endswith(".js"):
            pattern = rf"\b{escaped_skill}(?:\b|\s|$)"
        else:
            pattern = rf"\b{escaped_skill}\b"
            
        if re.search(pattern, text_lower):
            found_skills.add(skill)
            
    return sorted(list(found_skills))

def calculate_local_match(resume_text: str, resume_skills: list[str], job_description: str, custom_skills: list[str] = None) -> dict:
    """
    Computes a hybrid match score between the resume skills/text and the job description.
    Uses:
    1. Skill Overlap (70% weight) - intersection of resume skills and job description skills.
    2. Cosine Similarity (30% weight) - overall TF-IDF textual overlap.
    """
    if not job_description or job_description.strip() == "No description provided.":
        return {
            "score": 50,
            "matched_skills": [],
            "missing_skills": [],
            "explanation": "No job description available to analyze compatibility."
        }
        
    job_desc_lower = job_description.lower()
    
    # 1. Skill analysis
    job_skills = []
    matched_skills = []
    missing_skills = []
    
    # Merge predefined database with custom search keywords
    skills_to_check = list(TECH_SKILLS_DB)
    if custom_skills:
        for s in custom_skills:
            if s and s.strip() and s.strip() not in skills_to_check:
                skills_to_check.append(s.strip())
                
    # Identify which known skills are required in the job description
    for skill in skills_to_check:
        escaped = re.escape(skill.lower())
        if skill.endswith("++") or skill.endswith("#") or skill.endswith(".js"):
            pattern = rf"\b{escaped}(?:\b|\s|$)"
        else:
            pattern = rf"\b{escaped}\b"
            
        if re.search(pattern, job_desc_lower):
            job_skills.append(skill)
            if skill in resume_skills:
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)
                
    # Calculate skill overlap percentage
    if job_skills:
        skill_score = (len(matched_skills) / len(job_skills)) * 100
    else:
        # If no technology keywords are in the job description, default to text similarity only
        skill_score = None
        
    # 2. Overall Text Similarity using Cosine Similarity
    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf = vectorizer.fit_transform([resume_text, job_description])
        text_similarity = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0] * 100
    except Exception:
        text_similarity = 0.0

    # Combine scores
    if skill_score is not None:
        final_score = int(round((0.7 * skill_score) + (0.3 * text_similarity)))
    else:
        final_score = int(round(text_similarity))
        
    # Constrain score between 0 and 100
    final_score = max(0, min(100, final_score))
    
    # Dynamic Explanation
    if final_score >= 80:
        explanation = "Excellent match! Your skill set aligns strongly with the core requirements of this role."
    elif final_score >= 50:
        explanation = f"Good match. You possess several key skills ({', '.join(matched_skills[:3])}), but adding {', '.join(missing_skills[:2]) if missing_skills else 'more context'} could make your profile stronger."
    else:
        explanation = "Low match. This job requires technologies or experience not highlighted on your resume."
        
    return {
        "score": final_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "explanation": explanation
    }

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_groq_key() -> str:
    """Retrieves the Groq API key checking Streamlit session state, secrets, or environment variables."""
    try:
        import streamlit as st
        if "groq_api_key" in st.session_state and st.session_state.groq_api_key:
            return st.session_state.groq_api_key
        if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY") or ""

def call_groq_rest(prompt: str, json_response: bool = False) -> str:
    """Makes a direct POST request to Groq REST API (OpenAI compatible) using llama-3.3-70b-versatile."""
    import requests
    
    key = get_groq_key()
    if not key:
        raise ValueError("Groq API Key is not configured. Please set it in the sidebar API Configuration, secrets, or environment variables.")
        
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    if json_response:
        payload["response_format"] = {"type": "json_object"}
        
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        res_data = response.json()
        text = res_data['choices'][0]['message']['content']
        return text
    except Exception as e:
        raise RuntimeError(f"Groq API Call Failed: {e}")

def match_with_groq(resume_text: str, job_description: str) -> dict:
    """Uses Groq API to analyze candidate fit and return structured matching details."""
    try:
        prompt = f"""
        You are an expert ATS (Applicant Tracking System) recruiter.
        Analyze the candidate's Resume Text against the Job Description.
        
        Resume Text:
        {resume_text}
        
        Job Description:
        {job_description}
        
        Provide a highly professional evaluation of fit.
        Return ONLY a JSON object with the following schema (no markdown, no backticks, no text wrapping, just pure JSON):
        {{
            "score": <integer from 0 to 100 indicating compatibility>,
            "matched_skills": [<list of strings of matching technologies/concepts>],
            "missing_skills": [<list of strings of important required tech/skills missing from the resume>],
            "explanation": "<brief, professional 2-3 sentence summary of the evaluation and recommendations for optimization>"
        }}
        """
        res_text = call_groq_rest(prompt, json_response=True)
        return json.loads(res_text.strip())
    except Exception as e:
        # Fallback to local matching if API call fails
        parsed_resume_skills = parse_skills(resume_text)
        fallback_result = calculate_local_match(resume_text, parsed_resume_skills, job_description)
        fallback_result["explanation"] = f"Groq API Error: {str(e)}. Falling back to local match: {fallback_result['explanation']}"
        return fallback_result

def extract_profile_with_groq(resume_text: str) -> dict:
    """Uses Groq REST API to parse resume text and extract technical skills and a professional history brief."""
    prompt = f"""
    You are an expert technical recruiter and ATS parser.
    Analyze the candidate's resume text and extract:
    1. A comprehensive list of technical skills, programming languages, cloud platforms, databases, frameworks, and methodologies.
    2. A brief, professional executive summary of their work history (companies, roles, total years of experience, and key domains).
    
    Candidate Resume Text:
    {resume_text}
    
    Return a JSON object with the following fields:
    - skills: [<list of strings of parsed technical skills>]
    - history_brief: "<a concise 3-4 sentence paragraph summarizing their career history, core domains, and experience level>"
    
    Return ONLY valid JSON. Do not wrap in markdown or backticks.
    """
    try:
        res_text = call_groq_rest(prompt, json_response=True)
        return json.loads(res_text.strip())
    except Exception as e:
        # Fallback to simple rule-based skills and default history brief if API fails
        fallback_skills = parse_skills(resume_text)
        return {
            "skills": fallback_skills,
            "history_brief": f"Rule-based fallback activated. Groq extraction failed: {str(e)}"
        }

def match_with_groq_pro_max(resume_text: str, job_description: str, custom_skills: list[str] = None) -> dict:
    """
    Uses Groq REST API to perform a deep semantic matching evaluation of the candidate's resume
    against the job description, including score, gap analysis, and optimization suggestions.
    """
    skills_context = f" Additional required focus keywords to verify: {', '.join(custom_skills)}." if custom_skills else ""
    
    prompt = f"""
    You are an elite corporate technical recruiter and ATS (Applicant Tracking System) architect.
    Your task is to perform a deep semantic comparison between the candidate's Resume Text and the Job Description.{skills_context}
    
    Candidate Resume Text:
    {resume_text}
    
    Job Description:
    {job_description}
    
    Analyze:
    1. Tech Stack Compatibility: Check for required technologies, libraries, and tools. Account for semantic synonyms (e.g., "Go" and "Golang", "AWS" and "Amazon Web Services").
    2. Role & Seniority Fit: Evaluate if the candidate's historical work responsibilities align with the job requirements.
    3. Gap Analysis: Identify missing technical competencies, methodologies, or experience gaps.
    4. Actionable Optimization Tips: Give specific bullet points on what achievements or tools the candidate should highlight to bypass the ATS.
    
    Return a JSON object with the following fields:
    - score: <an integer from 0 to 100 representing the deep semantic alignment score>
    - matched_skills: [<list of technical skills matched between the resume and the job description>]
    - missing_skills: [<list of technical skills/concepts required by the job description but missing from the resume>]
    - gap_analysis: "<a clear, honest 2-3 sentence summary explaining the core experience or domain knowledge gaps>"
    - optimization_tips: [<list of 3-4 specific, actionable tips to optimize the resume for this exact job description>]
    - explanation: "<a 2-3 sentence executive summary of the fit and compatibility evaluation>"
    
    Return ONLY valid JSON. Do not wrap in markdown or backticks.
    """
    try:
        res_text = call_groq_rest(prompt, json_response=True)
        return json.loads(res_text.strip())
    except Exception as e:
        # Fallback to local match if API fails or rate limits are hit
        parsed_resume_skills = parse_skills(resume_text)
        fallback = calculate_local_match(resume_text, parsed_resume_skills, job_description, custom_skills)
        fallback["gap_analysis"] = f"AI scoring unavailable due to rate limits or API error ({str(e)})."
        fallback["optimization_tips"] = ["Highlight database matching.", "Ensure cloud certifications are visible."]
        return fallback

# Local Caching Functions
def save_resume_cache(filename: str, resume_text: str, parsed_skills: list[str], history_brief: str, workspace_dir: str):
    """Saves parsed resume info to a local cache file in the workspace directory."""
    cache_path = os.path.join(workspace_dir, CACHE_FILE)
    try:
        data = {
            "filename": filename,
            "resume_text": resume_text,
            "skills": parsed_skills,
            "history_brief": history_brief
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Failed to save resume cache: {e}")

def load_resume_cache(workspace_dir: str) -> dict | None:
    """Loads parsed resume info from cache if it exists."""
    cache_path = os.path.join(workspace_dir, CACHE_FILE)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

# --- Phase 2 REST-Based Groq API Integration ---

def generate_apply_pack(resume_text: str, job_title: str, company: str, job_description: str) -> dict:
    """Generates cold email and recruiter configuration details using Groq REST API."""
    prompt = f"""
    You are an expert technical recruiter and sales outreach copywriter.
    Generate a personalized outreach pack for a candidate (Arbaaz) applying to this job.
    
    Candidate Resume Text:
    {resume_text}
    
    Job Title: {job_title}
    Company: {company}
    Job Description:
    {job_description}
    
    Return a JSON object with the following fields:
    - subject: A catchy, professional cold email subject line.
    - email_body: A personalized cold email body from the candidate (Arbaaz) to the recruiter. Keep it concise (2-3 paragraphs), highlight the match between resume skills and the job specs. Start the greeting exactly with "Dear [Recruiter Name]," so it can be replaced.
    - company_domain: The estimated website corporate domain of {company} (e.g. "persistent.com" or "amazon.com").
    - email_format_type: The estimated email naming convention. Return one of these exact values: "first.last", "f.last", "first_last", or "first".
    
    Return ONLY valid JSON. Do not wrap in markdown or backticks.
    """
    res_text = call_groq_rest(prompt, json_response=True)
    return json.loads(res_text.strip())

def curate_resume_ats(resume_text: str, job_description: str) -> str:
    """Use Groq REST API to strictly replace keywords in the resume text to match the job description."""
    prompt = f"""
    You are an ATS (Applicant Tracking System) optimization expert.
    Your task is to analyze the candidate's resume and substitute specific words or phrases to align it with the job description.
    
    CRITICAL RULES:
    1. Do NOT change the layout, the structure, or the sections of the original resume.
    2. Do NOT rewrite whole paragraphs, delete job experiences, or invent new jobs/degrees.
    3. Strictly preserve the original tone and historical metrics.
    4. Only REPLACE key words or phrases (e.g., synonyms of technologies, database names, cloud tools, or methodologies) within the text to match the job description's keywords.
    5. Return the full, compiled, modified resume text.
    
    Candidate Resume Text:
    {resume_text}
    
    Job Description:
    {job_description}
    
    Output the modified resume text below, preserving the exact original spacing and line breaks:
    """
    return call_groq_rest(prompt, json_response=False)

# --- ReportLab PDF Resume Generator ---

def generate_resume_pdf(text: str, filename: str):
    """Compiles curated resume text into a professional executive layout PDF using ReportLab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    
    doc = SimpleDocTemplate(
        filename, 
        pagesize=letter,
        rightMargin=40, 
        leftMargin=40,
        topMargin=40, 
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'ResumeTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#000000'),
        alignment=1,
        spaceAfter=3
    )
    
    contact_style = ParagraphStyle(
        'ResumeContact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155'),
        alignment=1,
        spaceAfter=8
    )
    
    section_style = ParagraphStyle(
        'ResumeSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#000000'),
        spaceBefore=10,
        spaceAfter=3,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'ResumeBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor('#000000'),
        spaceAfter=3
    )
    
    bullet_style = ParagraphStyle(
        'ResumeBullet',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2.5
    )

    story = []
    lines = text.split('\n')
    
    first_line = True
    second_line = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Treat first non-empty line as name
        if first_line:
            story.append(Paragraph(line, title_style))
            first_line = False
            second_line = True
            continue
            
        # Treat second line as contact info
        if second_line:
            story.append(Paragraph(line, contact_style))
            second_line = False
            continue
            
        # Sections (Short, all capital letters)
        if line.isupper() and len(line) < 35:
            section_p = Paragraph(line, section_style)
            t = Table([[section_p]], colWidths=[532])
            t.setStyle(TableStyle([
                ('LINEBELOW', (0,0), (-1,-1), 0.75, colors.HexColor('#cbd5e1')),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('TOPPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 3))
        # Bullet Points
        elif line.startswith('•') or line.startswith('-') or line.startswith('*') or line.startswith('\u2022'):
            clean_line = line.lstrip('•-* \u2022').strip()
            # Escape HTML characters to prevent ReportLab XML parser errors
            clean_line = clean_line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(f"&bull; {clean_line}", bullet_style))
        # Regular text lines
        else:
            clean_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(clean_line, body_style))
            
    doc.build(story)
