import json
import os
import re
import time

import requests
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool


# =========================================================
# ENV
# =========================================================

load_dotenv("jobscout_ai/.env")

# Sign up free at https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
# (or https://www.openwebninja.com/api/jsearch) and add this key to jobscout_ai/.env
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_SEARCH_URL = f"https://{JSEARCH_HOST}/search-v2"
JSEARCH_DETAILS_URL = f"https://{JSEARCH_HOST}/job-details"


# =========================================================
# MODEL
# =========================================================

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0
)


# =========================================================
# SENIOR PATTERNS
# =========================================================

SENIOR_PATTERNS = [
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\blead\b",
    r"\bprincipal\b",
    r"\bstaff\b",
    r"\bmanager\b",
    r"\bhead\b",
    r"\bdirector\b",
    r"\bvp\b",
    r"\bvice president\b",
    r"\bchief\b",
    r"\btechnical lead\b",
]


# =========================================================
# EXPIRED PHRASES
# =========================================================

EXPIRED_PHRASES = [
    "job expired",
    "position has been filled",
    "no longer accepting applications",
    "applications are closed",
    "this job is no longer available",
    "job is no longer available",
    "position closed",
    "position has closed",
    "applications closed",
]


def has_senior_title(title):

    lower_title = title.lower()

    for pattern in SENIOR_PATTERNS:

        if re.search(pattern, lower_title):
            return True

    return False


def is_expired(content):

    text = content.lower()

    for phrase in EXPIRED_PHRASES:

        if phrase in text:
            return True

    return False


def requires_too_much_experience(text):

    lower_text = text.lower()

    patterns = [
        r"\b5\+?\s*years?\b",
        r"\b6\+?\s*years?\b",
        r"\b7\+?\s*years?\b",
        r"\b8\+?\s*years?\b",
        r"\b9\+?\s*years?\b",
        r"\b10\+?\s*years?\b",
        r"\b11\+?\s*years?\b",
        r"\b12\+?\s*years?\b",
        r"\b13\+?\s*years?\b",
        r"\b14\+?\s*years?\b",
        r"\b15\+?\s*years?\b",
    ]

    for pattern in patterns:

        if re.search(pattern, lower_text):
            return True

    return False


def clean_text(value):

    if value is None:
        return ""

    return str(value).strip()


def extract_json(text):

    if not text:
        return None

    text = text.strip()

    text = re.sub(r"```json", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        return None

    json_text = text[start:end + 1]

    try:
        return json.loads(json_text)

    except Exception:

        json_text = re.sub(r",\s*}", "}", json_text)
        json_text = re.sub(r",\s*]", "]", json_text)

        try:
            return json.loads(json_text)

        except Exception:
            return None


def clean_skill_list(value):

    if value is None:
        return []

    if isinstance(value, str):

        if value.strip().lower() in [
            "none", "none.", "n/a", "not specified", "not applicable",
        ]:
            return []

        parts = re.split(r",|;|\n|\|", value)

    elif isinstance(value, list):
        parts = value

    else:
        return []

    result = []
    seen = set()

    for item in parts:

        skill = str(item).strip()
        skill = re.sub(r"^[\-\*\•\d\.\)\s]+", "", skill)

        if not skill:
            continue

        lower = skill.lower()

        if lower in ["none", "none.", "n/a", "not specified", "not applicable"]:
            continue

        bad_phrases = [
            "candidate shows",
            "candidate demonstrates",
            "consider the candidate",
            "consider candidate",
            "recommendation",
            "suitable for",
            "strong fit",
            "good fit",
            "excellent fit",
            "limited professional experience",
            "lacks key",
            "candidate has",
        ]

        if any(phrase in lower for phrase in bad_phrases):
            continue

        if lower in seen:
            continue

        seen.add(lower)
        result.append(skill)

    return result


def remove_skill_duplicates(required, nice):

    required = clean_skill_list(required)
    nice = clean_skill_list(nice)

    required_keys = {x.lower() for x in required}

    final_nice = []

    for skill in nice:

        if skill.lower() in required_keys:
            continue

        final_nice.append(skill)

    return required, final_nice


# =========================================================
# JSEARCH — RAW FETCH
# =========================================================

def _fetch_jobs_from_jsearch(
    query,
    country=None,
    remote_only=False,
    num_pages=1,
):

    """
    Calls the JSearch API (Google for Jobs) and returns a list of
    normalized job dicts: title, company, url, content, location, is_remote.
    """

    if not RAPIDAPI_KEY:
        print("Missing RAPIDAPI_KEY in jobscout_ai/.env — skipping search.")
        return []

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": JSEARCH_HOST,
    }

    params = {
        "query": query,
        "num_pages": str(num_pages),
        "date_posted": "all",
    }

    if country:
        params["country"] = country

    if remote_only:
        params["remote_jobs_only"] = "true"

    try:
        response = requests.get(
            JSEARCH_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=45,
        )

        response.raise_for_status()
        payload = response.json()

    except requests.exceptions.Timeout:

        # Less-crawled regions (e.g. Pakistan) can trigger a slower live
        # search on JSearch's backend instead of a cached response.
        # Retry once with a longer timeout before giving up.
        try:
            response = requests.get(
                JSEARCH_SEARCH_URL,
                headers=headers,
                params=params,
                timeout=60,
            )

            response.raise_for_status()
            payload = response.json()

        except Exception as e:
            print(f"JSearch request error (after retry): {e}")
            return []

    except Exception as e:
        print(f"JSearch request error: {e}")
        return []

    raw_jobs = payload.get("data", {})

    if isinstance(raw_jobs, dict):
        raw_jobs = raw_jobs.get("jobs", [])

    jobs = []

    for item in raw_jobs:

        title = clean_text(item.get("job_title", ""))
        company = clean_text(item.get("employer_name", ""))
        description = clean_text(item.get("job_description", ""))

        # job_apply_link can be null — fall back to apply_options, then
        # the Google Jobs link, so we don't silently drop otherwise-good jobs.
        url = clean_text(item.get("job_apply_link") or "")

        if not url:
            apply_options = item.get("apply_options") or []
            if apply_options and isinstance(apply_options, list):
                url = clean_text(apply_options[0].get("apply_link", ""))

        if not url:
            url = clean_text(item.get("job_google_link", ""))

        city = clean_text(item.get("job_city", ""))
        job_country = clean_text(item.get("job_country", ""))
        is_remote = bool(item.get("job_is_remote", False))

        if not title or not url:
            continue

        location = ", ".join(p for p in [city, job_country] if p)

        if is_remote:
            location = (location + " (Remote)").strip() if location else "Remote"

        jobs.append({
            "title": title,
            "company": company,
            "url": url,
            "content": description[:2500],
            "location": location,
            "is_remote": is_remote,
        })

    time.sleep(1)

    return jobs


def _filter_jobs(jobs):

    """Applies the lightweight junior/senior + experience/expiry filters."""

    filtered = []

    for job in jobs:

        title = job.get("title", "")
        content = job.get("content", "")

        if has_senior_title(title):
            continue

        if is_expired(content):
            continue

        if requires_too_much_experience(content):
            continue

        filtered.append(job)

    return filtered


# =========================================================
# SEARCH JOBS (agent-facing tool)
# =========================================================

@tool
def search_jobs(query: str) -> str:

    """
    Search for individual job postings via JSearch (Google for Jobs).
    Returns a formatted text summary for the agent to read.
    """

    jobs = _fetch_jobs_from_jsearch(query)
    jobs = _filter_jobs(jobs)

    seen_urls = set()
    unique_jobs = []

    for job in jobs:

        if job["url"] in seen_urls:
            continue

        seen_urls.add(job["url"])
        unique_jobs.append(job)

    unique_jobs = unique_jobs[:5]

    if not unique_jobs:
        return "No suitable individual job postings found."

    output = "JOB SEARCH RESULTS\n\n"

    for i, job in enumerate(unique_jobs, 1):

        output += f"{i}. {job['title']}"

        if job["company"]:
            output += f" at {job['company']}"

        output += "\n"
        output += f"URL: {job['url']}\n"

        if job["location"]:
            output += f"Location: {job['location']}\n"

        output += f"Description: {job['content']}\n\n"

    return output


# =========================================================
# JOB DETAILS (agent-facing tool)
# =========================================================

@tool
def job_details(job_id: str) -> str:

    """
    Retrieve full details for a job using its JSearch job_id.
    """

    if not RAPIDAPI_KEY:
        return "Missing RAPIDAPI_KEY in jobscout_ai/.env."

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": JSEARCH_HOST,
    }

    try:
        response = requests.get(
            JSEARCH_DETAILS_URL,
            headers=headers,
            params={"job_id": job_id},
            timeout=20,
        )

        response.raise_for_status()
        payload = response.json()

    except Exception as e:
        return f"Job details error: {str(e)}"

    data = payload.get("data", [])

    if not data:
        return "Could not retrieve job details."

    description = clean_text(data[0].get("job_description", ""))

    return description[:6000] if description else "Could not retrieve job details."


# =========================================================
# JOB MATCH
# =========================================================

def calculate_job_match(cv_text, job):

    title = job["title"]
    url = job["url"]
    description = job["content"]

    prompt = f"""
You are an expert technical recruiter.

Compare the candidate CV with the job.

CANDIDATE CV:
{cv_text[:4000]}

JOB TITLE:
{title}

JOB DESCRIPTION:
{description[:3500]}

SCORING:

core_skills: 0-50
experience_level: 0-20
responsibilities_fit: 0-20
education_other: 0-10

The final score is the sum of these four values.

RULES:

- Use only evidence from the CV and job.
- Never invent skills.
- RAG means Retrieval-Augmented Generation.
- LLM orchestration counts as LLM application experience.
- Generative AI counts as relevant experience for GenAI/LLM jobs.
- LangChain, RAG, vector databases and agentic workflows are relevant.
- Equivalent skills should not be marked missing.
- Only clearly required skills belong in missing_required.
- Optional/preferred/bonus skills belong in missing_nice_to_have.
- Do not put responsibilities into skill lists.
- Do not put sentences into skill lists.
- Do not repeat skills.
- Internship and junior roles should be judged fairly for a student.
- Do not punish the candidate for every technology that is not listed.
- Do not treat optional technologies as required.

Return ONLY JSON:

{{
    "core_skills": 0,
    "experience_level": 0,
    "responsibilities_fit": 0,
    "education_other": 0,
    "matching_skills": [],
    "missing_required": [],
    "missing_nice_to_have": [],
    "recommendation": ""
}}

The recommendation MUST be a useful sentence.
Never return null or None.
"""

    try:
        response = llm.invoke(prompt)
        time.sleep(2)

        raw = clean_text(response.content)
        data = extract_json(raw)

        if not data:
            return None

        try:
            core = int(data.get("core_skills", 0))
        except Exception:
            core = 0

        try:
            experience = int(data.get("experience_level", 0))
        except Exception:
            experience = 0

        try:
            responsibilities = int(data.get("responsibilities_fit", 0))
        except Exception:
            responsibilities = 0

        try:
            education = int(data.get("education_other", 0))
        except Exception:
            education = 0

        core = max(0, min(50, core))
        experience = max(0, min(20, experience))
        responsibilities = max(0, min(20, responsibilities))
        education = max(0, min(10, education))

        score = core + experience + responsibilities + education

        matching = clean_skill_list(data.get("matching_skills", []))
        missing_required = clean_skill_list(data.get("missing_required", []))
        missing_nice = clean_skill_list(data.get("missing_nice_to_have", []))

        missing_required, missing_nice = remove_skill_duplicates(
            missing_required, missing_nice
        )

        recommendation = clean_text(data.get("recommendation", ""))

        if not recommendation or recommendation.lower() in ["none", "none.", "null", "n/a"]:

            if score >= 85:
                recommendation = "Excellent match for this role."
            elif score >= 70:
                recommendation = "Strong match for this role."
            elif score >= 55:
                recommendation = "Reasonable match with some skill gaps."
            else:
                recommendation = "Limited match because several job requirements are not covered."

        return {
            "title": title,
            "url": url,
            "score": score,
            "matching_skills": matching,
            "missing_required": missing_required,
            "missing_nice": missing_nice,
            "recommendation": recommendation,
        }

    except Exception:
        return None


# =========================================================
# LOCATION PRIORITY
# =========================================================

def get_location_priority(job):

    text = (job["title"] + " " + job["content"] + " " + job.get("location", "")).lower()

    if job.get("is_remote"):
        return 2

    pakistan_words = [
        "pakistan", "karachi", "lahore", "islamabad",
        "rawalpindi", "faisalabad", "punjab",
    ]

    remote_words = ["remote", "work from home", "worldwide", "anywhere"]

    if any(word in text for word in pakistan_words):
        return 3

    if any(word in text for word in remote_words):
        return 2

    return 0


# =========================================================
# RECOMMEND JOBS FROM CV
# =========================================================

@tool
def recommend_jobs_from_cv(cv_text: str) -> str:

    """
    Find and rank real individual jobs based on the candidate CV,
    using the JSearch API (Google for Jobs) as the source.
    """

    
    pakistan_queries = [
        "Python Developer",
        "Machine Learning Engineer",
        "AI Engineer",
        "Software Engineer Intern",
    ]

    remote_queries = [
        "Machine Learning Engineer",
        "AI Engineer",
        "Python Developer",
        "Generative AI Engineer",
    ]

    all_results = []

    for query in pakistan_queries:
        try:
            all_results.extend(_fetch_jobs_from_jsearch(query, country="pk"))
        except Exception as e:
            print(f"Search error (PK): {e}")

    for query in remote_queries:
        try:
            all_results.extend(_fetch_jobs_from_jsearch(query, remote_only=True))
        except Exception as e:
            print(f"Search error (remote): {e}")

    unique_jobs = []
    seen_urls = set()

    for job in all_results:

        url = job.get("url", "").strip()

        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        unique_jobs.append(job)

    filtered_jobs = _filter_jobs(unique_jobs)

    scored_jobs = []

    for job in filtered_jobs:

        try:
            match = calculate_job_match(cv_text, job)

            if not match:
                continue

            score = match.get("score")

            if score is None:
                continue

            try:
                score = int(score)
            except Exception:
                continue

            if score < 40:
                continue

            job["match_score"] = score
            job["matching_skills"] = match.get("matching_skills", [])
            job["missing_required"] = match.get("missing_required", [])
            job["missing_nice_to_have"] = match.get("missing_nice", [])
            job["recommendation"] = match.get("recommendation")

            scored_jobs.append(job)

        except Exception as e:
            print(f"Match calculation error: {e}")
            continue

    scored_jobs.sort(
        key=lambda job: (get_location_priority(job), job.get("match_score", 0)),
        reverse=True,
    )

    scored_jobs = scored_jobs[:5]

    if not scored_jobs:
        return (
            "No suitable jobs found based on the CV. "
            "Try again with a different job search."
        )

    output = "🎯 TOP JOB RECOMMENDATIONS\n\n"

    for index, job in enumerate(scored_jobs, start=1):

        title = job.get("title", "Untitled Job")
        company = job.get("company", "")
        url = job.get("url", "")
        location = job.get("location", "")
        score = job.get("match_score", 0)
        matching = job.get("matching_skills", [])
        missing_required = job.get("missing_required", [])
        missing_nice = job.get("missing_nice_to_have", [])
        recommendation = job.get("recommendation")

        if not recommendation:

            if score >= 70:
                recommendation = "Strong match for the candidate's current skills and experience."
            elif score >= 50:
                recommendation = "Reasonable match with some skills that may need improvement."
            else:
                recommendation = "Partial match. The candidate should review the missing skills before applying."

        output += f"{index}. {title}"

        if company:
            output += f" at {company}"

        output += "\n"
        output += f"URL: {url}\n"

        if location:
            output += f"Location: {location}\n"

        output += "\n"
        output += f"Match Score: {score}%\n"

        output += "Matching Skills: " + (", ".join(matching) if matching else "None") + "\n"
        output += "Missing Required Skills: " + (", ".join(missing_required) if missing_required else "None") + "\n"
        output += "Missing Nice-to-Have Skills: " + (", ".join(missing_nice) if missing_nice else "None") + "\n"
        output += f"Recommendation: {recommendation}\n\n"

        output += "-" * 60 + "\n\n"

    return output