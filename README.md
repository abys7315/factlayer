# 🔍 FactLayer — Cross-Document Fact Grounding & Intelligence Engine

> **In Simple Words**: Imagine you have two 50-page company reports. One says the company made **$100 Million**, while another says **$85 Million**. Did someone make a mistake, or did one report exclude taxes? And where is the proof on page 37?  
> **FactLayer** is an AI engine that reads complex enterprise PDFs, extracts every factual claim, pinpoints the **exact bounding box on the PDF page** where it was written (100% proof, zero hallucination), and automatically compares statements across documents to detect **Corroborations**, **Contradictions**, and **Updates**.

[![Live Frontend](https://img.shields.io/badge/Frontend-Vercel%20Live-000000?style=for-the-badge&logo=vercel)](https://factlayer-five.vercel.app)
[![Live Backend Docs](https://img.shields.io/badge/Backend%20Docs-Render%20Swagger-46E3B7?style=for-the-badge&logo=render)](https://factlayer-backend.onrender.com/docs)
[![GitHub Repository](https://img.shields.io/badge/GitHub-abys7315%2Ffactlayer-181717?style=for-the-badge&logo=github)](https://github.com/abys7315/factlayer)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776AB?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite-61DAFB?style=for-the-badge&logo=react)](https://vitejs.dev)
[![Gemini 2.0 Flash](https://img.shields.io/badge/LLM-Gemini%202.0%20Flash-4285F4?style=for-the-badge&logo=google)](https://aistudio.google.com)

---

## 🌐 Live Deployments

* **Frontend Web App**: [https://factlayer-five.vercel.app](https://factlayer-five.vercel.app)
* **Backend API & Swagger Documentation**: [https://factlayer-backend.onrender.com/docs](https://factlayer-backend.onrender.com/docs)
* **Live Health Check**: [https://factlayer-backend.onrender.com/health](https://factlayer-backend.onrender.com/health)

---

## 📑 Table of Contents

1. [What is FactLayer? (Beginner Overview)](#what-is-factlayer-beginner-overview)
2. [Video Demo (3 Minutes or Less)](#video-demo)
3. [The 4 Required Evaluation Cases (Explained Simply)](#the-4-required-evaluation-cases-explained-simply)
4. [Setup and Run Instructions](#setup-and-run-instructions)
   - [Option A: Running Locally (Step-by-Step)](#option-a-running-locally-step-by-step)
   - [Option B: Running with Docker](#option-b-running-with-docker)
   - [Environment Variables Guide](#environment-variables-guide)
5. [Approach](#approach)
   - [System Architecture Flowchart](#system-architecture-flowchart)
   - [The 11 Ingestion Stages (Under the Hood)](#the-11-ingestion-stages-under-the-hood)
   - [Important Decisions & Engineering Trade-offs](#important-decisions--engineering-trade-offs)
   - [AI Tools & Frameworks Used](#ai-tools--frameworks-used)
6. [Limitations and Next Steps](#limitations-and-next-steps)
7. [Additional Notes](#additional-notes)

---

## What is FactLayer? (Beginner Overview)

### The Problem
When financial analysts, legal auditors, or researchers examine documents (like annual reports, prospectuses, or press releases):
1. **Documents are massive**: Often 50 to 300 pages of legal disclaimers, tiny tables, and complex footnotes.
2. **Numbers conflict**: Different documents cite different numbers for revenue, profits, or headcount.
3. **Generic AI (ChatGPT) hallucinates**: Standard AI tools summarize text, but they often make up numbers, cannot tell you the exact pixel coordinates on the page, and fail at mathematical verification.

### The FactLayer Solution
FactLayer replaces guesswork with **verifiable facts**:
- **Structured Extraction**: Converts unstructured PDF paragraphs and tables into precise atomic claims: `(Subject, Predicate, Object, Fiscal Period, Currency)`.
- **Pixel-Level Provenance**: Every extracted fact has exact character coordinates `[x0, y0, x1, y1]` on the source PDF. You can click on any fact to see the exact bounding box where it appears.
- **Cross-Document Reconciliation**: When you upload Document B, FactLayer compares its facts with Document A to determine:
  - Do they agree? (**Corroboration**)
  - Did the number change because time passed? (**Supersession**)
  - Is there a real mistake/fraud? (**Contradiction**)
  - Are they using different accounting standards or units? (**Reconcilable Context**)

---

## Video Demo

### 🎥 [Watch 3-Minute Video Demo](https://youtu.be/DEMO_VIDEO_LINK_PLACEHOLDER)
*(Replace `DEMO_VIDEO_LINK_PLACEHOLDER` with your demo video link)*

### What the Demo Shows in Under 3 Minutes:
1. **Live Upload & 5-Step Pipeline**: Uploading an enterprise filing (`01-delhivery-prospectus-2022-excerpt.pdf`) and observing real-time progress (*Upload* → *Layout* → *Fact Extraction* → *Grounding* → *Graph*).
2. **Character-Level Grounding**: Clicking a fact to view its verbatim excerpt, confidence score, and exact bounding box coordinates `[x0, y0, x1, y1]`.
3. **The Four Required Evaluation Scenarios**:
   - **Case 1 (Exact Corroboration)**: Showing identical numbers verified across two separate documents.
   - **Case 2 (Reconcilable / Supersession)**: Showing a metric or CEO transition updated across fiscal periods.
   - **Case 3 (Genuine Contradiction)**: Flagging an unexplained discrepancy in the same metric for the same time period.
   - **Case 4 (Reconcilable Context)**: Showing how GAAP vs. Non-GAAP adjusted metrics are reconciled instead of falsely flagged.
4. **Interactive Knowledge Graph**: Exploring connected entity nodes and opening deep reasoning trace modals.

---

## The 4 Required Evaluation Cases (Explained Simply)

Business documents rarely have simple "True or False" statements. FactLayer solves the four fundamental scenarios required in cross-document reconciliation:

```
                  ┌──────────────────────────────────────────────┐
                  │ Does the claim appear in multiple documents? │
                  └──────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
         [Values Agree]                                 [Values Disagree]
                 │                                               │
                 ▼                               ┌───────────────┴───────────────┐
         ┌───────────────┐                       ▼                               ▼
         │    CASE 1     │               [Different Time?]             [Different Method/Scope?]
         │ Exact Corrob. │                       │                               │
         │  (Both agree) │               ┌───────┴───────┐               ┌───────┴───────┐
         └───────────────┘               ▼               ▼               ▼               ▼
                                      [ YES ]          [ NO ]         [ YES ]          [ NO ]
                                         │               │               │               │
                                         ▼               ▼               ▼               ▼
                                 ┌───────────────┐ ┌───────────┐ ┌───────────────┐ ┌───────────┐
                                 │    CASE 2     │ │  CASE 3   │ │    CASE 4     │ │  CASE 3   │
                                 │ Supersession  │ │  Genuine  │ │ Reconcilable  │ │  Genuine  │
                                 │ (Time update) │ │  Contra.  │ │ (Scope diff)  │ │  Contra.  │
                                 └───────────────┘ └───────────┘ └───────────────┘ └───────────┘
```

### Case 1: Exact Corroboration (Both Documents Agree)
* **What it means**: Two different documents make the exact same factual claim about the same entity for the same time period.
* **Real-World Example**:
  - **Document A (Annual Report)**: *"Delhivery generated ₹6,887 Cr revenue in FY22."*
  - **Document B (Press Release)**: *"In fiscal year 2022, revenue stood at ₹6,887.1 Cr."*
* **FactLayer Classification**: `CORROBORATION` (Confidence: 0.98).
* **How FactLayer knows**: The entity names resolve to the same canonical ID, fiscal years match (`FY2022`), and normalized numeric values are within 0.5% tolerance.

### Case 2: Reconcilable / Temporal Supersession (Updated Over Time)
* **What it means**: The values or facts differ, but it is **not** an error—one document is simply newer, updating or superseding the older one.
* **Real-World Example**:
  - **Document A (Q1 Filing)**: *"CEO: Jane Doe."*
  - **Document B (Q3 Filing)**: *"CEO: John Smith (appointed July 2022)."*
* **FactLayer Classification**: `RECONCILABLE` *(Temporal Supersession)*.
* **How FactLayer knows**: The system detects the same predicate (`has_ceo`), checks document publication dates ($T_B > T_A$), and creates a directed supersession edge in the timeline.

### Case 3: Genuine Contradiction (Direct Conflict)
* **What it means**: Both documents discuss the exact same entity, attribute, timeframe, and accounting basis, but report mutually exclusive numbers.
* **Real-World Example**:
  - **Document A (Official Filing)**: *"FY22 Adjusted EBITDA was ₹720 Cr."*
  - **Document B (Auditor Note)**: *"FY22 Adjusted EBITDA was ₹410 Cr."*
* **FactLayer Classification**: `CONTRADICTION` *(High Severity Audit Alert)*.
* **How FactLayer knows**: All contextual parameters match (Entity, Attribute, FY2022, Adjusted EBITDA), but the numeric delta exceeds 5%. The system flags this with a visual warning badge.

### Case 4: Reconcilable Context (Accounting or Scope Differences)
* **What it means**: Two numbers look contradictory at first glance, but are actually both true under different definitions (e.g., GAAP vs. Non-GAAP, or Standalone vs. Consolidated).
* **Real-World Example**:
  - **Document A**: *"Net Income was $18,000,000 (GAAP)."*
  - **Document B**: *"Adjusted EBITDA was $24,000,000 (Non-GAAP, adding back stock compensation)."*
* **FactLayer Classification**: `RECONCILABLE` *(Methodological / Accounting Difference)*.
* **How FactLayer knows**: The comparison engine compares context fingerprints (`scope=Consolidated`, `basis=GAAP` vs `basis=Non-GAAP`) and prevents false-alarm contradiction warnings.

---

## Setup and Run Instructions

### Option A: Running Locally (Step-by-Step)

#### Step 1: Clone the Repository
Open your terminal (PowerShell, Command Prompt, or Terminal on Mac/Linux):
```bash
git clone https://github.com/abys7315/factlayer.git
cd factlayer
```

#### Step 2: Configure Environment Variables
Copy `.env.example` to create your `.env` file:
```bash
# On Windows (PowerShell):
Copy-Item .env.example .env

# On Mac / Linux:
cp .env.example .env
```
Open `.env` in any text editor (like VS Code or Notepad) and paste your **Gemini API Key**:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
DATABASE_URL=sqlite+aiosqlite:///./factlayer.db
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173", "https://factlayer-five.vercel.app"]
```
> 💡 **Don't have a Gemini API key?** It takes 30 seconds to get a free key from [Google AI Studio](https://aistudio.google.com). No credit card required.

#### Step 3: Start the Backend (FastAPI)
Create and activate a Python virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment:
# On Windows (PowerShell):
venv\Scripts\Activate.ps1
# On Windows (Command Prompt):
venv\Scripts\activate.bat
# On Mac / Linux:
source venv/bin/activate

# Install required Python packages
pip install -r requirements.txt

# Run the FastAPI server
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```
✅ **Backend is running at**: `http://127.0.0.1:8000`  
✅ **Interactive API Docs (Swagger)**: `http://127.0.0.1:8000/docs`

#### Step 4: Start the Frontend (React + Vite)
Open a **second terminal window** and run:
```bash
cd frontend

# Install Node dependencies
npm install

# Start the frontend dev server
npm run dev
```
✅ **Open your browser at**: `http://localhost:5173`  
You will see the FactLayer dashboard ready to upload PDFs!

---

### Option B: Running with Docker

If you have [Docker Desktop](https://www.docker.com) installed:
```bash
# Ensure your .env file has GEMINI_API_KEY filled in
docker-compose up --build
```
* Frontend will be accessible at: `http://localhost:5173`
* Backend will be accessible at: `http://localhost:8000`

---

### Environment Variables Guide

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | `""` | **Required**. Your Google Gemini API Key. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./factlayer.db` | Database connection string. Uses zero-setup SQLite by default. |
| `EXTRACTION_MODEL` | `gemini-2.0-flash` | LLM model for high-throughput fact parsing. |
| `REASONING_MODEL` | `gemini-2.0-flash` | LLM model for deep ambiguity resolution. |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model for 384-dimensional dense vectors. |
| `MAX_UPLOAD_MB` | `100` | Maximum file size allowed for PDF uploads. |
| `MAX_PAGES` | `500` | Maximum page count allowed per document. |

---

## Approach

### System Architecture Flowchart

```mermaid
flowchart TD
    subgraph Client["Frontend Layer (React 18 + Vite)"]
        UI["Dashboard & PDF Uploader"]
        Progress["5-Step Pipeline Stepper"]
        Graph["Cytoscape Knowledge Graph"]
        Modal["Reasoning Trace Inspector"]
    end

    subgraph API["Backend Gateway (FastAPI)"]
        Router["Async API Endpoints (/api/v1)"]
        Val["Upload Validator (SHA-256 + Magic MIME)"]
    end

    subgraph Pipeline["Ingestion & Reasoning Engine (11 Stages)"]
        P1["1. PyMuPDF Layout & Block Parser"]
        P2["2. Selective OCR (Tesseract 300 DPI)"]
        P3["3. Context & Period Classifier"]
        P4["4. Regex Candidate Detector"]
        P5["5. Gemini 2.0 Flash Fact Extractor"]
        P6["6. Bounding-Box Grounding & Validation"]
        P7["7. Numeric & Currency Normalizer"]
        P8["8. Canonical Entity Resolver"]
        P9["9. Dense Embeddings (all-MiniLM-L6-v2)"]
        P10["10. Hybrid Retriever (Vector + Keyword)"]
        P11["11. Multi-Hypothesis Cross-Doc Reasoner"]
    end

    subgraph Storage["Persistence Layer"]
        DB[("Async Database (SQLite / Postgres)")]
        Vectors[("Dense Vector Index (Qdrant / NumPy)")]
    end

    UI -->|Upload PDF| Val
    Val --> Router
    Router --> Pipeline
    Pipeline --> Storage
    Progress <-->|Poll Stage Progress| Router
    Storage --> Graph
    Storage --> Modal
```

---

### The 11 Ingestion Stages (Under the Hood)

When you drop a PDF into FactLayer, it goes through 11 sequential, observable stages:

1. **`QUEUED`**: Streams binary bytes, computes a SHA-256 integrity hash, checks for duplicate uploads, and stages disk storage.
2. **`PARSING`**: PyMuPDF (`fitz`) parses text blocks, font sizes, line coordinates, and table structures across all pages.
3. **`OCR`**: Evaluates character density. If a scanned document or figure has quality `< 0.3`, Tesseract OCR runs at 300 DPI.
4. **`CONTEXT`**: Resolves document-level scope (Company name, fiscal year, default currency, and page classifications like Financial Statement vs. Notes).
5. **`DETECTION`**: Scans tokens with regex patterns to flag high-probability candidate blocks containing numbers, dates, or currency symbols.
6. **`EXTRACTING`**: Batches candidate blocks to **Gemini 2.0 Flash**, extracting structured facts `(Subject, Predicate, Object)` with explicit timestamps and confidence scores.
7. **`VALIDATION`**: Fuzzy-matches extracted facts back against raw PDF text coordinates to calculate character-exact bounding boxes `[x0, y0, x1, y1]`.
8. **`NORMALIZING`**: Standardizes currency scales (*"₹50 Lakh"* → `5,000,000 INR`, *"1.2 Cr"* → `12,000,000 INR`) and assigns unique context fingerprints.
9. **`RESOLVING`**: Merges name variations (*"Delhivery Ltd"*, *"The Company"*, *"Delhivery Pvt Ltd"*) into a single canonical entity.
10. **`EMBEDDING`**: Computes 384-dimensional semantic vectors using `sentence-transformers` (`all-MiniLM-L6-v2`).
11. **`LINKING`**: Finds related facts across all documents and runs them through the comparison engine to classify **Corroborations**, **Contradictions**, and **Supersessions**.

---

### Important Decisions & Engineering Trade-offs

#### 1. Verifiable Bounding-Box Grounding vs. Pure LLM Summarization
* **The Choice**: Many AI applications just feed a PDF into an LLM and ask for a summary. In contrast, FactLayer forces every fact to point to exact PDF page bounding-box coordinates `[x0, y0, x1, y1]`.
* **The Trade-off**: Requires more parsing steps upfront, but guarantees **zero hallucination**. If a number cannot be highlighted on the source page, it is rejected.

#### 2. Nuanced Reconciliation vs. Binary True/False
* **The Choice**: Most systems classify two differing numbers as a "contradiction." FactLayer recognizes that business numbers change naturally due to quarterly updates or accounting methods (`GAAP` vs. `Non-GAAP`).
* **The Trade-off**: Requires extracting context fingerprints (basis, period, scope), but eliminates annoying false-alarm contradiction warnings.

#### 3. Dual-Mode Database Architecture (Enterprise vs. Zero-Config)
* **The Choice**: Built with async SQLAlchemy supporting enterprise PostgreSQL with Qdrant vector database, but includes automatic fallback to `aiosqlite` and in-memory NumPy cosine similarity.
* **The Trade-off**: Allows developers to clone the repo and run it instantly on their laptop or free cloud tiers (Render/Vercel) with zero cloud setup costs.

---

### AI Tools & Frameworks Used

| Tool / Library | Role in FactLayer | Why We Chose It |
| :--- | :--- | :--- |
| **Google Gemini 2.0 Flash** | Structured Fact Extraction & LLM Reasoner | Extremely fast inference, large context window, strong JSON mode, free tier availability. |
| **PyMuPDF (`fitz`)** | PDF Parsing & Coordinate Extraction | High-performance C++ backend, extracts vector bounding boxes and table matrices accurately. |
| **Sentence-Transformers** | Dense Vector Embeddings (`all-MiniLM-L6-v2`) | Lightweight (80MB), runs locally on CPU without needing a GPU, produces 384-dim semantic vectors. |
| **Pytesseract** | OCR Fallback | Handles scanned pages or image figures where text is rasterized. |
| **FastAPI** | Asynchronous Backend API | High throughput, automatic Swagger OpenAPI docs, native Python async support. |
| **React 18 + Vite** | Interactive Web Frontend | Sub-second hot-module reloading, responsive glassmorphism UI, smooth animations. |
| **Cytoscape.js** | Knowledge Graph Visualizer | Interactive node-link graph with physics simulation, zooming, and filtering. |

---

## Limitations and Next Steps

### What Does Not Work Yet (Current Limitations)
1. **Free Cloud Tier CPU Latency**: On Render's Free Tier (0.1 shared vCPU, 512MB RAM), processing a large 27-page financial prospectus takes 60–90 seconds. (On a local PC with 8 cores, it takes ~5–10 seconds).
2. **Free Hosting Ephemeral Storage**: On free serverless containers, uploaded PDF files are wiped when the container restarts or goes to sleep.
3. **Complex Hand-Drawn Tables**: Borderless scanned tables with rotated multi-line cells occasionally require manual column realignment.
4. **Infographic Diagram Vision**: Complex graphical flowcharts are parsed via OCR text rather than native multi-modal visual embeddings.

### What We Would Build Next
1. **Distributed Worker Queues (Celery / Temporal + Redis)**: Move document ingestion to background worker pools with WebSocket progress streaming.
2. **Cloud Object Storage (AWS S3 / Cloudflare R2)**: Store original PDF files permanently in cloud buckets.
3. **Interactive PDF Canvas Viewer**: Render bounding boxes as interactive overlays directly on top of the original PDF inside the browser.
4. **Automated Master Entity Profiles**: Consolidate thousands of facts across 100+ documents into a single executive dashboard with timeline sliders.

---

## Additional Notes

### Security & Data Integrity
* **Idempotency**: Every document is hashed with SHA-256 upon arrival. If you upload the same PDF twice, FactLayer detects the hash and reuses existing verified facts without consuming extra LLM tokens.
* **Input Sanitization**: File names are sanitized to prevent directory traversal attacks (`../`), and MIME types are verified using magic bytes rather than trusting file extensions.

### Core API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/documents/upload` | Upload a PDF document and start the multi-stage ingestion pipeline. |
| `GET` | `/api/v1/documents` | List all ingested documents with page counts and processing status. |
| `GET` | `/api/v1/documents/{id}/status` | Check live stage progress (*QUEUED*, *PARSING*, *EXTRACTING*, etc.). |
| `GET` | `/api/v1/facts` | Query extracted facts with filters for entity, predicate, or document. |
| `GET` | `/api/v1/facts/{id}/evidence` | Retrieve exact bounding-box coordinates `[x0, y0, x1, y1]` and excerpts. |
| `GET` | `/api/v1/relationships` | Retrieve cross-document corroborations, contradictions, and supersessions. |
| `GET` | `/api/v1/graph` | Retrieve Cytoscape-formatted JSON for knowledge graph visualization. |
| `GET` | `/api/v1/documents/stats/overview` | Dashboard summary metrics (total facts, relationships, contradiction count). |

---

*FactLayer is built for audit-grade accuracy, financial intelligence, and cross-document truth verification.*
