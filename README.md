# JobScout AI

An autonomous AI career assistant. Upload your CV, and JobScout AI parses it via RAG, plans job search queries, searches real job listings, scores each match against your CV, and shows ranked recommendations with explanations.

## Features

- **CV Upload & Parsing** — Upload a PDF or Word CV; text is extracted, chunked, and embedded into a Chroma vector database for retrieval-augmented Q&A.
- **Autonomous Job Search** — An LLM agent (Groq) plans and runs job search queries based on your CV, using the JSearch API (Google for Jobs) to pull real postings from LinkedIn, Indeed, Glassdoor, and more.
- **CV-to-Job Matching** — Each job is scored 0–100 against your CV (skills, experience, education, responsibilities fit), with matching skills, missing skills, and a written recommendation.
- **Custom React Dashboard** — Upload a CV, ask questions about it, search for jobs manually, or get automatic ranked recommendations, all in a dedicated React UI.

## Tech Stack

- **LLM Orchestration:** LangChain, Groq (`openai/gpt-oss-20b`)
- **RAG:** Chroma vector store, Google Generative AI embeddings
- **Job Search:** JSearch API (RapidAPI)
- **Backend:** FastAPI (REST API wrapping the agent/RAG/job-search logic)
- **Frontend:** React (Vite)
- **CV Parsing:** pypdf, python-docx

## Project Structure
JobScout-AI/
├── agent.py # LangChain agent setup (search_jobs, job_details, recommend_jobs_from_cv tools)
├── Tools/
│ └── job_search_tool.py # JSearch API integration + CV match scoring
├── frontend/ # React (Vite) UI
│ └── src/
│ ├── App.jsx
│ ├── App.css
│ └── index.css
└── jobscout_ai/
├── backend.py # FastAPI backend (REST API for the React frontend)
├── requirements.txt # Python dependencies
├── .env # API keys (not committed)
└── RAG/
├── loader.py # Text chunking
├── embeddings.py # Embedding model setup
├── vectorstore.py # Chroma vector store
└── retrieval.py # Retriever setup



## Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd JobScout-AI
```

### 2. Backend setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r jobscout_ai/requirements.txt
```

Create `jobscout_ai/.env` with:



GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_google_api_key
RAPIDAPI_KEY=your_rapidapi_key



Run the backend:

```bash
python -m uvicorn jobscout_ai.backend:app --reload --port 8000
```

### 3. Frontend setup

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`



By default the frontend calls the backend at `http://localhost:8000`. To point it at a different backend (e.g. a deployed one), set `VITE_API_BASE` in a `frontend/.env` file:

VITE_API_BASE=https://your-deployed-backend-url




## Usage

1. Upload your CV (PDF or Word).
2. Use **Ask about your CV** for questions grounded in your CV content.
3. Use **Search jobs** to manually search for specific roles.
4. Click **Recommended for you** → **Find my matches** for automatic ranked job recommendations (takes ~2 minutes — it runs multiple searches and scores each result against your CV).

## Deployment

- **Backend:** deployed on [Render](https://render.com) as a Python web service (`jobscout_ai/backend.py`), with `GROQ_API_KEY`, `GOOGLE_API_KEY`, and `RAPIDAPI_KEY` set as environment variables.
- **Frontend:** deployed on [Vercel](https://vercel.com), with root directory set to `frontend/` and `VITE_API_BASE` pointing to the Render backend URL.

Live demo: `<your-live-frontend-url>`

## Notes

- The JSearch free tier is rate-limited (~200 requests/month) — each "Find my matches" run uses several requests.
- Pakistan-region searches may take longer (up to 60s+ retry) than other regions due to JSearch's live-crawl behavior for less-cached locations.
- The Render free tier sleeps after inactivity — the first request after waking up can take 30-50 seconds before normal response times resume.