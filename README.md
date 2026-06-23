# Socratic Spark

A full-stack Socratic tutoring web app with 5 security/quality enforcement layers.

## Architecture

```
socratic-spark/
├── backend/
│   ├── main.py                    # FastAPI app, CORS, lifespan
│   ├── routes/
│   │   ├── chat.py               # POST /chat — main chat endpoint
│   │   ├── curriculum.py         # POST /curriculum/upload
│   │   └── audit.py              # GET /audit/sessions, GET /audit/{id}
│   ├── services/
│   │   ├── input_filter.py       # Layer 1: regex + Claude Haiku classifier
│   │   ├── rag.py                # Layer 2: ChromaDB ingestion + retrieval
│   │   ├── tutor.py              # Layer 3: hardened system prompt + Claude Sonnet
│   │   └── output_validator.py   # Layer 4: response validation + retry
│   ├── db/
│   │   └── session_store.py      # Layer 5: SQLite audit log + rate limiting
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── StudentView.jsx
│   │   │   └── TeacherView.jsx
│   │   └── components/
│   │       ├── ChatWindow.jsx
│   │       ├── CurriculumUpload.jsx
│   │       └── AuditLog.jsx
│   └── package.json
└── .env
```

## Setup

### 1. Environment variables

Copy `.env` and fill in your Anthropic API key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
TEACHER_PASSWORD=changeme
CHROMA_DB_PATH=./chroma_db
SQLITE_DB_PATH=./sessions.db
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The backend will be available at http://localhost:8000.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:5173.

## How it works

### Student flow
1. Enter a subject name and upload a `.txt` or `.pdf` curriculum file
2. The backend chunks the file into ~300-word segments and stores them in ChromaDB
3. A unique `session_id` is returned and the chat session begins
4. Every student message passes through 5 enforcement layers before Claude responds

### Teacher flow
1. Navigate to the **Teacher** tab in the nav bar
2. Log in with `TEACHER_PASSWORD` (default: `changeme`)
3. Browse all sessions with stats: message count, blocked attempts, validator retries
4. Click any session to see the full audit log
   - Messages where `was_blocked=true` are highlighted in red
   - Messages where `validator_retries > 0` are highlighted in amber

## The 5 enforcement layers

| Layer | Where | What it does |
|-------|-------|-------------|
| 1 | `input_filter.py` | Regex blocklist for jailbreak phrases, then Claude Haiku as a security classifier |
| 2 | `rag.py` | ChromaDB retrieval — top-5 curriculum chunks are the ONLY knowledge Claude gets |
| 3 | `tutor.py` | Hardened system prompt injected with curriculum chunks; Claude Sonnet for tutoring |
| 4 | `output_validator.py` | Validates response ends with `?`, no direct-answer phrases, no URLs; retries up to 2× |
| 5 | `session_store.py` | SQLite audit log for every message; rate limit 30 msgs/student/hour |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/curriculum/upload` | Upload curriculum file (form-data: `subject`, `file`) |
| POST | `/chat` | Send a student message (`{session_id, message}`) |
| GET | `/audit/sessions` | List all sessions (requires `Authorization: Bearer <password>`) |
| GET | `/audit/{session_id}` | Full audit log for a session (requires auth) |
| GET | `/health` | Health check |
