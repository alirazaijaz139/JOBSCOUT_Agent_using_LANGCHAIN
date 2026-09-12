import { useState, useRef } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'; 

function renderBold(text, keyPrefix) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? <strong key={`${keyPrefix}-b-${i}`}>{part}</strong> : part
  );
}

function renderSkillLine(i, label, value, variant) {
  if (value.trim().toLowerCase() === 'none') {
    return (
      <p key={i} className="line-row">
        <span className={`line-label label-${variant}`}>{label}</span>
        <span className="line-value muted">None</span>
      </p>
    );
  }
  const skills = value.split(',').map((s) => s.trim()).filter(Boolean);
  return (
    <div key={i} className="line-row skills-row">
      <span className={`line-label label-${variant}`}>{label}</span>
      <span className="skill-tags">
        {skills.map((s, idx) => (
          <span key={idx} className={`skill-chip chip-${variant}`}>{s}</span>
        ))}
      </span>
    </div>
  );
}

function renderLine(line, i) {
  const trimmed = line.trim();

  if (!trimmed) {
    return <div key={i} className="line-spacer" />;
  }

  if (/^-{5,}$/.test(trimmed)) {
    return <hr key={i} className="divider" />;
  }

  if (/^\d+\.\s/.test(trimmed)) {
    return <p key={i} className="job-heading">{renderBold(trimmed, i)}</p>;
  }

  const urlMatch = trimmed.match(/^URL:\s*(.+)$/);
  if (urlMatch) {
    return (
      <p key={i} className="line-row">
        <span className="line-label">URL</span>
        <a className="line-link" href={urlMatch[1]} target="_blank" rel="noreferrer">
          {urlMatch[1]}
        </a>
      </p>
    );
  }

  const locationMatch = trimmed.match(/^Location:\s*(.+)$/);
  if (locationMatch) {
    return (
      <p key={i} className="line-row">
        <span className="line-label">Location</span>
        <span className="line-value">{locationMatch[1]}</span>
      </p>
    );
  }

  const scoreMatch = trimmed.match(/^Match Score:\s*(\d+)%?/);
  if (scoreMatch) {
    const score = parseInt(scoreMatch[1], 10);
    const color =
      score >= 70 ? 'var(--accent)' : score >= 55 ? 'var(--warm)' : 'var(--danger)';
    return (
      <p key={i} className="line-row">
        <span className="line-label">Match Score</span>
        <span className="line-value" style={{ color, fontWeight: 700 }}>{score}%</span>
      </p>
    );
  }

  const matchingMatch = trimmed.match(/^Matching Skills:\s*(.+)$/);
  if (matchingMatch) {
    return renderSkillLine(i, 'Matching Skills', matchingMatch[1], 'matching');
  }

  const missingReqMatch = trimmed.match(/^Missing Required Skills:\s*(.+)$/);
  if (missingReqMatch) {
    return renderSkillLine(i, 'Missing Required Skills', missingReqMatch[1], 'missing-required');
  }

  const missingNiceMatch = trimmed.match(/^Missing Nice-to-Have Skills:\s*(.+)$/);
  if (missingNiceMatch) {
    return renderSkillLine(i, 'Missing Nice-to-Have Skills', missingNiceMatch[1], 'missing-nice');
  }

  const recMatch = trimmed.match(/^Recommendation:\s*(.+)$/);
  if (recMatch) {
    return (
      <p key={i} className="line-row recommendation-row">
        <span className="line-label">Recommendation</span>
        <span className="line-value recommendation-text">{renderBold(recMatch[1], i)}</span>
      </p>
    );
  }

  if (trimmed.startsWith('* ')) {
    return <p key={i} className="bullet-line">{renderBold(trimmed.slice(2), i)}</p>;
  }

  if (trimmed === '🎯 TOP JOB RECOMMENDATIONS') {
    return <p key={i} className="section-heading">{trimmed}</p>;
  }

  return <p key={i} className="plain-line">{renderBold(trimmed, i)}</p>;
}

function FormattedAnswer({ text }) {
  if (!text) return null;
  const lines = text.split('\n');
  return <div className="formatted-answer">{lines.map((line, i) => renderLine(line, i))}</div>;
}
function Logo() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" className="logo-mark" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="logoGradient" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#35d0ba" />
          <stop offset="50%" stopColor="#4f8ef7" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="34" height="34" rx="9" fill="#10182c" stroke="url(#logoGradient)" strokeWidth="1.5" />
      <text
        x="18"
        y="24"
        textAnchor="middle"
        fontFamily="'Space Grotesk', sans-serif"
        fontWeight="700"
        fontSize="15"
        fill="url(#logoGradient)"
      >
        SI
      </text>
    </svg>
  );
}

export default function App() {
  const fileInputRef = useRef(null);

  const [cvFile, setCvFile] = useState(null);
  const [cvUploaded, setCvUploaded] = useState(false);
  const [numChunks, setNumChunks] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const [activeTab, setActiveTab] = useState('ask');

  const [askQuestion, setAskQuestion] = useState('');
  const [askAnswer, setAskAnswer] = useState('');
  const [askLoading, setAskLoading] = useState(false);

  const [searchQuestion, setSearchQuestion] = useState('');
  const [searchAnswer, setSearchAnswer] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);

  const [recommendAnswer, setRecommendAnswer] = useState('');
  const [recommendLoading, setRecommendLoading] = useState(false);
  const [recommendError, setRecommendError] = useState('');

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setCvFile(file);
    setUploading(true);
    setUploadError('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post(`${API_BASE}/api/upload-cv`, formData);
      if (res.data.error) {
        setUploadError(res.data.error);
      } else {
        setNumChunks(res.data.num_chunks);
        setCvUploaded(true);
      }
    } catch (err) {
      setUploadError('Could not reach the backend. Is it running on port 8000?');
    } finally {
      setUploading(false);
    }
  }

  async function handleAsk() {
    if (!askQuestion.trim()) return;
    setAskLoading(true);
    setAskAnswer('');
    try {
      const res = await axios.post(`${API_BASE}/api/ask-cv`, { question: askQuestion });
      setAskAnswer(res.data.error || res.data.answer);
    } catch {
      setAskAnswer('Something went wrong reaching the backend.');
    } finally {
      setAskLoading(false);
    }
  }

  async function handleSearch() {
    if (!searchQuestion.trim()) return;
    setSearchLoading(true);
    setSearchAnswer('');
    try {
      const res = await axios.post(`${API_BASE}/api/search-jobs`, { question: searchQuestion });
      setSearchAnswer(res.data.answer);
    } catch {
      setSearchAnswer('Something went wrong reaching the backend.');
    } finally {
      setSearchLoading(false);
    }
  }

  async function handleRecommend() {
    setRecommendLoading(true);
    setRecommendError('');
    setRecommendAnswer('');
    try {
      const res = await axios.post(`${API_BASE}/api/recommend-jobs`);
      if (res.data.error) {
        setRecommendError(res.data.error);
      } else {
        setRecommendAnswer(res.data.recommendations);
      }
    } catch {
      setRecommendError('Something went wrong reaching the backend.');
    } finally {
      setRecommendLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1 className="wordmark">
          <Logo />
          JobScout AI
        </h1>
        <p className="tagline">
          Upload your CV and it scans real job postings, scores each one against
          your actual skills, and tells you exactly what's missing.
        </p>
      </header>

      <label
        className={`upload-zone ${cvUploaded ? 'has-file' : ''}`}
        htmlFor="cv-upload"
      >
        <input
          id="cv-upload"
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={handleFileChange}
        />

        {!cvUploaded ? (
          <>
            <p className="upload-title">
              {uploading ? 'Reading your CV…' : 'Drop your CV here, or click to upload'}
            </p>
            <p className="upload-hint">PDF or Word — parsed and indexed automatically</p>
          </>
        ) : (
          <div className="file-info">
            <span className="file-badge">CV loaded</span>
            <div>
              <div className="file-name">{cvFile?.name}</div>
              <div className="file-meta">{numChunks} sections indexed</div>
            </div>
          </div>
        )}

        {cvUploaded && (
          <button
            type="button"
            className="replace-btn"
            onClick={(e) => {
              e.preventDefault();
              fileInputRef.current?.click();
            }}
          >
            Replace
          </button>
        )}
      </label>

      {uploadError && <p className="error-text">{uploadError}</p>}

      <nav className="tabs">
        <button
          className={`tab ${activeTab === 'ask' ? 'active' : ''}`}
          onClick={() => setActiveTab('ask')}
          disabled={!cvUploaded}
        >
          Ask about your CV
        </button>
        <button
          className={`tab ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
        >
          Search jobs
        </button>
        <button
          className={`tab ${activeTab === 'recommend' ? 'active' : ''}`}
          onClick={() => setActiveTab('recommend')}
          disabled={!cvUploaded}
        >
          Recommended for you
        </button>
      </nav>

      {activeTab === 'ask' && (
        <section className="panel">
          <h2 className="panel-title">Ask about your CV</h2>
          <p className="panel-desc">
            Ask anything grounded in what's actually written in your CV.
          </p>
          <div className="input-row">
            <input
              className="text-input"
              placeholder="e.g. What AI projects have I worked on?"
              value={askQuestion}
              onChange={(e) => setAskQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            />
            <button className="btn" onClick={handleAsk} disabled={askLoading}>
              {askLoading ? 'Asking…' : 'Ask'}
            </button>
          </div>
          {askAnswer && <div className="answer-block"><FormattedAnswer text={askAnswer} /></div>}
        </section>
      )}

      {activeTab === 'search' && (
        <section className="panel">
          <h2 className="panel-title">Search jobs</h2>
          <p className="panel-desc">
            Search for a specific role, location, or skill directly.
          </p>
          <div className="input-row">
            <input
              className="text-input"
              placeholder="e.g. Find remote Python developer internships"
              value={searchQuestion}
              onChange={(e) => setSearchQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            <button className="btn" onClick={handleSearch} disabled={searchLoading}>
              {searchLoading ? 'Searching…' : 'Search'}
            </button>
          </div>
          {searchAnswer && <div className="answer-block"><FormattedAnswer text={searchAnswer} /></div>}
        </section>
      )}

      {activeTab === 'recommend' && (
        <section className="panel">
          <h2 className="panel-title">Recommended for you</h2>
          <p className="panel-desc">
            Runs several searches and scores every result against your CV —
            takes about two minutes.
          </p>
          <button
            className="btn btn-block"
            onClick={handleRecommend}
            disabled={recommendLoading}
          >
            {recommendLoading ? 'Scanning postings and scoring matches…' : 'Find my matches'}
          </button>

          {recommendError && <p className="error-text">{recommendError}</p>}

          {recommendAnswer && <div className="answer-block"><FormattedAnswer text={recommendAnswer} /></div>}
        </section>
      )}
    </div>
  );
}