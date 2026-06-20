# Scrapper Pro 🎯

Scrapper Pro is a professional, enterprise-grade job scraper, compatibility evaluator, and resume optimizer designed to automate and customize your job hunting process. It utilizes **Streamlit** for a modern, fluid user interface and **Apify** for anonymous, rate-resilient LinkedIn job scraping. It features a local NLP keyword scoring engine and leverages **Groq AI (Llama 3.3)** for semantic match analysis, cold email drafting, and ATS-optimized resume keyword curation.

---

## 🚀 Key Features

* **Anonymized LinkedIn Scraping**: Leverages Apify's compute-only LinkedIn job scraper. Fetches job postings without logging in, keeping your personal accounts completely safe from suspensions.
* **Smart PDF Resume Parsing**: Automatically extracts text and profiles your skill set across programming, databases, DevOps, and cloud technologies.
* **Hybrid Match Scorer**: Evaluates job compatibility on a `0-100%` scale by combining direct skill-overlap scoring (70%) with a TF-IDF text cosine-similarity algorithm (30%).
* **Pro-Max AI Evaluation**: Utilizes Groq REST API (`llama-3.3-70b-versatile`) to perform semantic gap analysis, role alignment scoring, and generate custom resume optimization tips.
* **Recruiter Outreach Pack**: Automatically generates professional cold email drafts and estimates company recruiter emails using domains and naming formats.
* **ATS Resume Curator**: Suggests or builds custom resume text by substituting synonyms and key technical skills to align precisely with the job description.
* **Interactive Dashboard**: Track your jobs with High/Medium/Low match scoring, filter job listings, and save pipelines to a local CSV database.

---

## 🛠️ Tech Stack & Requirements

* **Frontend Framework**: Streamlit (Light Mode Premium Theme)
* **Data Handling**: Pandas, CSV
* **Parsing & Similarity Math**: PyPDF2, Scikit-Learn (TF-IDF Vectorization)
* **Cloud & Scraper Services**: Apify API
* **Large Language Models**: Groq REST API (llama-3.3-70b-versatile)

---

## ⚙️ Configuration & Installation

### 1. Clone & Install Dependencies
First, clone this repository and install the required Python libraries:
```bash
git clone https://github.com/arbaz-mohammad/Scrapper-Pro.git
cd Scrapper-Pro
pip install -r requirements.txt
```

### 2. Configure API Keys
Scrapper Pro does not hardcode any sensitive credentials. You can configure credentials in one of three ways:

#### Option A: Local `.env` File (Recommended)
Copy the `.env.example` template to `.env` in the root folder and fill in your keys:
```env
APIFY_TOKEN=your_apify_api_token
GROQ_API_KEY=your_groq_api_key
```

#### Option B: Live Streamlit UI Settings
You can expand the **🔑 API Configuration** panel in the Streamlit sidebar at runtime and paste your credentials securely. They will remain loaded for your active browser session.

#### Option C: Streamlit Secrets
If deploying the app on Streamlit Community Cloud, add the secrets under **App Settings -> Secrets**:
```toml
APIFY_TOKEN = "your_apify_api_token"
GROQ_API_KEY = "your_groq_api_key"
```

---

## 💻 Running the Application

### Launch via Batch File (Windows)
Double-click the `run_app.bat` file in the root directory, or launch from PowerShell/CMD:
```powershell
.\run_app.bat
```

### Launch via Streamlit Command
```bash
streamlit run app.py --server.port 8502
```
Once started, the application will open automatically in your browser at `http://localhost:8502`.

---

## 📈 Standard Workflow

1. **Upload Resume**: Go to the **Resume & Profile** tab, upload your PDF resume, and review your extracted skills and parsed profile.
2. **Search Setup**: Select your target job title, keywords, location, and dates under **Job Search Dashboard**, and click **Scrape & Analyze Jobs**.
3. **Review Matches**: Open the **Matching Board** to check your compatibility scores. Expand any job card to read the AI Gap Analysis, matching skills list, and optimization recommendations.
4. **Outreach & Optimize**: Click **Generate Cold Email** to view recruiter contacts, copy templates, or hit **Curate Wording & Build PDF** to compile an ATS-friendly version of your resume.
5. **Track Progress**: Save jobs as "Interested" or "Applied" to view and organize them in the **Application Tracker**.

---

## 🔒 Security & Privacy

* **Zero Hardcoded Secrets**: This repository does not store active API tokens. All credentials must be provided via local environment settings or inputted directly in the UI.
* **Ignored Data**: Personal resumes (`*.pdf`), local pipeline data (`applied_jobs.csv`), and state files (`.resume_cache.json`) are automatically ignored via `.gitignore` to prevent leaking personal information.
