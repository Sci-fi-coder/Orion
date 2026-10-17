# ORION — Orchestrated Research Intelligence and Output Network

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange.svg)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **"Stop reading papers. Start interrogating them."**

ORION is an autonomous, multi-agent AI research intelligence system. Given a natural language topic or scientific hypothesis, ORION decomposes the query, concurrently retrieves academic literature from ArXiv and verified web sources in parallel, evaluates and resolves conflicting claims, grades empirical evidence quality, and synthesizes structured answers with inline citations — orchestrated through a self-correcting LangGraph agentic loop.

---

## Architecture Overview

```text
User Query
     ↓
[COORDINATOR] — Decomposes topic into 3-5 sub-questions
     ↓
[RESEARCHER] — Parallel ArXiv + Web search (ThreadPoolExecutor)
  → Hybrid scoring: semantic + citations + recency + venue
  → PDF download → section-aware chunking → ChromaDB
     ↓
[SYNTHESIZER] — Confidence gate → stance classification
  → SUPPORTS / CONTRADICTS / NEUTRAL per source
  → Evidence grading: EXPERIMENTAL / THEORETICAL / SURVEY / ASSERTION
  → Structured answer with inline citations
  → Devil's Advocate mode
     ↓
[CRITIC] — Quality evaluation → adaptive replan (max 2)
     ↓
Final Research Report
```

---

## What Makes ORION Different from Standard RAG?

| Dimension | Standard RAG | ORION Research Engine |
| :--- | :--- | :--- |
| **Query Strategy** | Single vector similarity search on user prompt | **Decomposition**: Coordinator generates 3–5 targeted sub-questions and strategy |
| **Source Scoring** | Pure cosine similarity distance threshold | **Multi-Factor Hybrid Ranking**: Semantic score + citation count + publication recency + venue tier |
| **Conflict Handling** | Silently aggregates or hallucinates over conflicting texts | **Stance Classification**: Explicitly flags `SUPPORTS`, `CONTRADICTS`, and `NEUTRAL` claims |
| **Confidence Control** | Returns whatever top-$k$ chunks exist, even if irrelevant | **Distance-Based Confidence Gate**: Refuses poor context; computes calibrated metric (0 to 1) |
| **Agent Structure** | Linear pipe (Embed $\rightarrow$ Search $\rightarrow$ Prompt LLM) | **Multi-Agent State Graph**: Coordinator, Researcher, Synthesizer, and Critic |
| **Plan Adaptability** | Static single pass; fails silently if context is thin | **Dynamic Self-Correction**: Critic agent evaluates synthesis and triggers up to 2 adaptive replans |

---

## Tech Stack

| Technology | Role in System |
| :--- | :--- |
| **Python 3.11+** | Core runtime environment |
| **LangGraph** | Multi-agent cyclic state-machine orchestration |
| **LiteLLM Router** | Resilient model routing with automatic fallback (Groq $\rightarrow$ Gemini $\rightarrow$ Cerebras) |
| **FastAPI & Uvicorn** | High-performance asynchronous REST backend |
| **ChromaDB** | High-speed local vector database for semantic chunk retrieval |
| **sentence-transformers** | Dense local embeddings (`all-MiniLM-L6-v2`) for semantic search |
| **ArXiv API** | Academic preprint search and metadata extraction |
| **Semantic Scholar API** | Citation counts, venue impact, and author indexing |
| **Tavily API** | Real-time targeted web intelligence gathering |
| **PyMuPDF (fitz)** | High-throughput PDF extraction with section-aware parsing |
| **SQLite & SQLAlchemy** | Persistent workspaces, papers catalog, and telemetry logs |
| **Vanilla HTML5 / CSS / JS** | Phosphor-green "Breaking Bad" science lab research terminal UI |

---

## Agentic Concepts Demonstrated

- **Parallel Agent Execution**: Researcher concurrently queries ArXiv and Tavily Web search using multi-threaded execution pools (`ThreadPoolExecutor`).
- **Hybrid Domain Scoring**: Rank papers using a weighted formula combining semantic relevance, citation velocity, publication year decay, and venue prestige.
- **Section-Aware Chunking**: PyMuPDF parses scientific papers respecting structural headers (Abstract, Methods, Results, Discussion) rather than arbitrary character splits.
- **Contradiction Detection & Stance Mapping**: Classifies every retrieved context chunk against the hypothesis as `SUPPORTS`, `CONTRADICTS`, or `NEUTRAL`.
- **Empirical Evidence Grading**: Grades context veracity into `EXPERIMENTAL`, `THEORETICAL`, `SURVEY`, or `ASSERTION`.
- **Confidence Gating & Guardrails**: Rejects hallucinated generation when semantic distance exceeds threshold ($\tau = 1.2$).
- **Adversarial Devil's Advocate Mode**: Synthesizes structured counter-arguments, methodological limitations, and dissenting viewpoints.
- **Self-Correcting Adaptive Replanning**: Critic agent assesses synthesis coherence and triggers automatic graph loopbacks to the Researcher agent (up to 2 iterations).

---

## Setup & Installation

### 1. Clone Repository

```bash
git clone https://github.com/Sci-fi-coder/Orion.git
cd Orion
```

### 2. Create Virtual Environment & Install Dependencies

```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY="your-groq-api-key"
GEMINI_API_KEY="your-gemini-api-key"
CEREBRAS_API_KEY="your-cerebras-api-key"
TAVILY_API_KEY="your-tavily-api-key"
```

### 4. Launch Backend API

```bash
cd backend
python main.py
```

The FastAPI backend will start on `http://localhost:8000`. You can verify API health at `http://localhost:8000/health`.

### 5. Launch Research Terminal Frontend

Open `frontend/index.html` in your web browser (or serve it using any static file server):

```bash
# Example using Python:
cd frontend
python -m http.server 3000
```
Then navigate to `http://localhost:3000` in your browser.

---

## Project Structure

```text
orion/
├── agents/
│   ├── coordinator.py       # Topic decomposition & sub-question planning
│   ├── critic.py            # Quality assessment & adaptive replan routing
│   ├── researcher.py        # Parallel ArXiv + Web retrieval & hybrid scoring
│   └── synthesizer.py       # Evidence grading, stance classification & citation synthesis
├── backend/
│   └── main.py              # FastAPI server, REST API endpoints & CORS
├── frontend/
│   ├── app.js               # Reactive frontend engine, polling & telemetry
│   ├── index.html           # Breaking Bad lab / CRT research terminal interface
│   └── style.css            # Terminal theme, hex grid, scanlines & particles
├── tools/
│   ├── arxiv_tool.py        # ArXiv API search, Semantic Scholar metadata & scoring
│   ├── ingest_tool.py       # PyMuPDF section-aware PDF parser & ChromaDB vector store
│   ├── memory_tool.py       # Workspace memory, paper cache & query persistence
│   └── search_tool.py       # Tavily parallel web search integration
├── config.py                # Multi-LLM fallback router (Groq -> Gemini -> Cerebras)
├── database.py              # SQLAlchemy SQLite models (Workspace, Paper, Query)
├── graph.py                 # LangGraph state graph compilation & orchestration
├── requirements.txt         # Python package dependencies
├── .env                     # API keys configuration
└── README.md                # Project documentation
```

---

## API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Healthcheck and database connectivity status |
| `POST` | `/research` | Trigger multi-agent research loop on topic |
| `POST` | `/workspace/create` | Create a new isolated research workspace |
| `GET` | `/workspace/{id}/papers` | List all ingested papers and metadata for a workspace |
| `GET` | `/workspace/{id}/metrics` | Fetch query counts and average confidence telemetry |
| `DELETE`| `/workspace/{id}/clear` | Purge query history for a workspace |

---

## License

This project is licensed under the [MIT License](LICENSE).
