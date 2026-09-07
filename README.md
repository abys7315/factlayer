# Fact Knowledge Layer

> Provenance-first cross-document fact extraction, grounding, and relationship reasoning pipeline.

---

## 1. Overview & Architecture

The **Fact Knowledge Layer** extracts atomic factual claims from PDFs, grounds each claim directly to verbatim source evidence and page numbers, and reconciles claims across documents into **Corroborations**, **Contradictions**, and **Reconcilable Context** (differing timeframes, units, or accounting scopes).

```
[Upload PDF] 
     │
     ▼
[Text & Page Extraction] (PyMuPDF / fitz)
     │
     ▼
[Fact Extraction] (Gemini 2.0 Flash + Deterministic Fallback)
     │
     ▼
[Fact Storage & Embeddings] (SQLite + sentence-transformers / all-MiniLM-L6-v2)
     │
     ▼
[Cross-Document Similarity Matching] (Cosine Similarity Top-K)
     │
     ▼
[Relationship Classification] (Gemini Prompt 2 + Contextual Reasoning)
     │
     ▼
[Interactive UI & API] (Streamlit + React Dashboard + FastAPI)
```

---

## 2. Four Required Evaluation Scenarios

| Scenario | Definition | Example in System | Classification |
|---|---|---|---|
| **Case 1: Exact Corroboration** | Same claim and time period stated across different documents | Annual Report: *$100,000,000 revenue in FY23* vs Press Release: *$100 million in fiscal 2023* | `corroborate` |
| **Case 2: Reconcilable / Supersession** | Factual change explained by temporal update or leadership change | FY23 CEO: *Jane Doe* vs FY24 CEO: *John Smith (appointed July 2024)* | `reconcilable` |
| **Case 3: Genuine Contradiction** | Same entity, attribute, and timeframe with conflicting values | Filing claim: *$100,000,000 FY23 revenue* vs Analyst audit: *$85,000,000 FY23 revenue* | `contradict` |
| **Case 4: Reconcilable Context** | Differing accounting scopes or regional scopes | GAAP Net Income: *$18,000,000* vs Non-GAAP Adjusted: *$24,000,000* | `reconcilable` |

---

## 3. Tech Stack (100% Free Tier, No Paid APIs)

- **Backend**: Python 3.10+ / 3.11 + FastAPI + Uvicorn
- **PDF Parsing**: PyMuPDF (`fitz` / `pymupdf`)
- **LLM**: Google Gemini 2.0 Flash via `google-genai` SDK
- **Embeddings**: `sentence-transformers` (`all-MiniLM-L6-v2`) running locally
- **Vector Search**: In-memory dense cosine similarity
- **Database**: SQLite via SQLAlchemy (`data/facts.db`)
- **Frontend**: Streamlit UI (`frontend/app.py`) + React Dashboard

---

## 4. Setup & Run Instructions

### Prerequisites
- Python 3.10+ or 3.11
- Gemini API Key (free from [Google AI Studio](https://aistudio.google.com))

### 1. Installation
```bash
# Clone repository
git clone <your-repo-url>
cd fact-knowledge-layer

# Create virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy template and add your Gemini API key
cp .env.example .env
```
Edit `.env`:
```env
GEMINI_API_KEY=your_actual_gemini_api_key
DATABASE_URL=sqlite:///data/facts.db
```

### 3. Launch Backend
```bash
# Start FastAPI backend server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation: `http://127.0.0.1:8000/docs`

### 4. Launch Streamlit UI
In a separate terminal:
```bash
# Start Streamlit frontend
streamlit run frontend/app.py
```
Open your browser at `http://localhost:8501`.

---

## 5. API Endpoints

- `POST /upload` — Upload a PDF, extract facts, generate embeddings, and compute cross-document relationships.
- `GET /documents` — List all ingested documents.
- `GET /facts` — List extracted facts (filterable by `doc_id` and `fact_type`).
- `GET /facts/{id}` — Fact details, verbatim source quote, page number, and related cross-doc claims.
- `GET /relationships` — List classified relationships (filterable by `type`: `corroborate`, `contradict`, `reconcilable`).
- `GET /health` — Service health check.

---

## 6. Design Decisions & Trade-offs

1. **LLM-Based vs. Rule-Based Extraction**:
   - The extraction prompt dynamically infers `fact_type` (financial, personnel, legal, date, location) rather than enforcing rigid predefined enums, allowing the schema to evolve naturally across arbitrary corporate documents.
   - Deterministic rule and regex fallbacks ensure zero-downtime reliability even during quota limits or offline testing.

2. **SQLite + Local Embeddings vs. Heavy Vector DB**:
   - For prototype and medium-scale ingestion (hundreds of documents), SQLite with in-memory NumPy cosine similarity provides instant deployment, zero setup cost, and full transaction ACID safety without requiring separate vector cloud infrastructure.

3. **Multi-Hypothesis Cross-Document Classification**:
   - Rather than forcing a binary True/False judgment, the classifier explicitly distinguishes between direct contradictions and contextual reconciliations (different reporting periods, GAAP vs Non-GAAP, or differing units).

---

## 7. Limitations & Next Steps

- **Asynchronous Worker Queue**: The prototype processes documents synchronously during `POST /upload`; production deployments can offload to Celery / ARQ background workers with Redis.
- **Table Coordinate Bounding-Boxes**: Multi-page table spanning can be enhanced with character-exact polygon overlays in PDF viewer.
- **Incremental Clustering**: Grouping large clusters of corroborated claims into single canonical master entities across 100+ documents.

---

## 8. Additional Notes

- **AI Tools Used**: Developed with Google Gemini 2.0 Flash for semantic fact extraction and comparative reasoning traces.
