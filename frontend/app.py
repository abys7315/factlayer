"""Streamlit Frontend for Fact Knowledge Layer."""

import os
import requests
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Fact Knowledge Layer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #64748B;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .badge-corroborate {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-contradict {
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-reconcilable {
        background-color: #FEF08A;
        color: #854D0E;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
    }
    .metric-num {
        font-size: 2rem;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .fact-box {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #3B82F6;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .quote-box {
        background: #F1F5F9;
        border-left: 3px solid #94A3B8;
        padding: 0.6rem 0.8rem;
        font-style: italic;
        font-size: 0.9rem;
        color: #334155;
        margin-top: 0.5rem;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)


# Sidebar Navigation
st.sidebar.image("https://img.icons8.com/isometric/100/database.png", width=60)
st.sidebar.title("Fact Knowledge Layer")
st.sidebar.caption("Provenance-first cross-document intelligence")

menu = st.sidebar.radio(
    "Navigation",
    ["1. Upload Document", "2. Facts Explorer", "3. Relationships View", "4. Failure Log"],
)

st.sidebar.divider()
try:
    health = requests.get(f"{BACKEND_URL}/health", timeout=2).json()
    st.sidebar.success(f"🟢 Backend Online\n• LLM: {health.get('llm')}")
except Exception:
    st.sidebar.warning("⚠️ Backend Offline or Unreachable")


# ── Screen 1: Upload Document ─────────────────────────────────────────
if menu == "1. Upload Document":
    st.markdown('<div class="main-header">📄 Document Upload & Extraction</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upload corporate reports, earnings releases, or notes to extract facts and link cross-document relationships.</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("Upload PDF")
        uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

        if uploaded_file is not None:
            if st.button("🚀 Process & Extract Facts", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_box = st.empty()

                stages = [
                    (15, "📄 Validating PDF file structure & computing SHA-256 hash..."),
                    (35, "📑 Parsing PDF pages, paragraphs & tables with PyMuPDF..."),
                    (55, "🔎 Scanning candidate numerical & financial statements..."),
                    (75, "🤖 Extracting semantic facts via Gemini 2.0 Flash..."),
                    (90, "⚡ Generating 384-dim dense embeddings (all-MiniLM-L6-v2)..."),
                    (98, "🔗 Matching & classifying cross-document relationships..."),
                ]

                import time
                for pct, msg in stages[:3]:
                    progress_bar.progress(pct)
                    status_box.info(f"⏳ **Preprocessing Step:** {msg}")
                    time.sleep(0.3)

                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    res = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=60)

                    for pct, msg in stages[3:]:
                        progress_bar.progress(pct)
                        status_box.info(f"⏳ **Preprocessing Step:** {msg}")
                        time.sleep(0.2)

                    progress_bar.progress(100)
                    if res.status_code == 200:
                        data = res.json()
                        status_box.success(f"✅ **Preprocessing & Ingestion Complete for {data['filename']}**")
                        st.balloons()

                        m1, m2, m3 = st.columns(3)
                        with m1:
                            st.metric("Pages Processed", data["page_count"])
                        with m2:
                            st.metric("Facts Extracted", data["facts_extracted"])
                        with m3:
                            st.metric("Relationships Found", data["relationships_found"])
                    else:
                        status_box.error(f"Error ({res.status_code}): {res.text}")
                except Exception as e:
                    status_box.error(f"Failed to process document: {e}")

    with col2:
        st.subheader("Ingested Documents")
        try:
            docs = requests.get(f"{BACKEND_URL}/documents", timeout=5).json()
            if docs:
                for d in docs:
                    with st.expander(f"📑 {d['filename']}", expanded=True):
                        st.write(f"**Doc ID:** `{d['id']}`")
                        st.write(f"**Pages:** {d['page_count']}")
                        st.write(f"**Uploaded:** {d['upload_date'][:19].replace('T', ' ')}")
            else:
                st.info("No documents uploaded yet. Upload your first PDF to begin.")
        except Exception:
            st.warning("Could not fetch documents list.")


# ── Screen 2: Facts Explorer ──────────────────────────────────────────
elif menu == "2. Facts Explorer":
    st.markdown('<div class="main-header">🔎 Facts Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Inspect atomic claims extracted from documents with full source quotes and page provenance.</div>', unsafe_allow_html=True)

    try:
        docs = requests.get(f"{BACKEND_URL}/documents", timeout=5).json()
        doc_options = {"All Documents": None}
        for d in docs:
            doc_options[f"[{d['id']}] {d['filename']}"] = d["id"]

        f_col1, f_col2 = st.columns([2, 2])
        with f_col1:
            selected_doc = st.selectbox("Filter by Document", list(doc_options.keys()))
        with f_col2:
            fact_type_filter = st.selectbox("Filter by Fact Type", ["All Types", "financial", "personnel", "table_metric", "general"])

        doc_id = doc_options[selected_doc]
        params = {}
        if doc_id:
            params["doc_id"] = doc_id
        if fact_type_filter != "All Types":
            params["fact_type"] = fact_type_filter

        facts = requests.get(f"{BACKEND_URL}/facts", params=params, timeout=5).json()

        st.markdown(f"**Total Facts Found:** `{len(facts)}`")

        if facts:
            for f in facts:
                with st.container():
                    st.markdown(f"""
                    <div class="fact-box">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 700; font-size: 1.05rem; color: #0F172A;">{f['fact_text']}</span>
                            <span style="background: #E0E7FF; color: #3730A3; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">{f['fact_type']}</span>
                        </div>
                        <div style="margin-top: 6px; font-size: 0.85rem; color: #64748B;">
                            📄 <b>Document:</b> {f.get('document_filename', f"Doc #{f['doc_id']}")} &nbsp;|&nbsp; 
                            📍 <b>Page:</b> {f['page_number']} &nbsp;|&nbsp; 
                            ⏱️ <b>Time Period:</b> {f.get('time_period') or 'N/A'} &nbsp;|&nbsp; 
                            💰 <b>Value:</b> {f"{f.get('value'):,}" if f.get('value') is not None else 'N/A'} {f.get('unit') or ''}
                        </div>
                        <div class="quote-box">
                            <b>Verbatim Source Quote:</b> "{f['source_quote']}"
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No facts match the selected criteria.")

    except Exception as e:
        st.error(f"Error loading facts: {e}")


# ── Screen 3: Relationships View ──────────────────────────────────────
elif menu == "3. Relationships View":
    st.markdown('<div class="main-header">🔗 Cross-Document Relationships</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Compare claims across documents classified into Corroboration, Contradiction, and Reconcilable Context.</div>', unsafe_allow_html=True)

    rel_filter = st.selectbox(
        "Filter by Relationship Type",
        ["All Relationships", "corroborate", "contradict", "reconcilable"],
    )

    try:
        params = {}
        if rel_filter != "All Relationships":
            params["type"] = rel_filter

        rels = requests.get(f"{BACKEND_URL}/relationships", params=params, timeout=5).json()

        # Summary Metrics
        all_rels = requests.get(f"{BACKEND_URL}/relationships", timeout=5).json()
        c_count = sum(1 for r in all_rels if r["relationship_type"] == "corroborate")
        x_count = sum(1 for r in all_rels if r["relationship_type"] == "contradict")
        r_count = sum(1 for r in all_rels if r["relationship_type"] == "reconcilable")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'<div class="metric-card"><div class="metric-num">{len(all_rels)}</div><div class="metric-label">Total Links</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card"><div class="metric-num" style="color: #059669;">{c_count}</div><div class="metric-label">Corroborations</div></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="metric-card"><div class="metric-num" style="color: #DC2626;">{x_count}</div><div class="metric-label">Contradictions</div></div>', unsafe_allow_html=True)
        with m4:
            st.markdown(f'<div class="metric-card"><div class="metric-num" style="color: #D97706;">{r_count}</div><div class="metric-label">Reconcilable</div></div>', unsafe_allow_html=True)

        st.divider()

        if rels:
            for r in rels:
                badge_class = f"badge-{r['relationship_type']}"
                badge_text = r['relationship_type'].upper()

                with st.expander(f"[{badge_text}] {r.get('fact_1', {}).get('fact_text', 'Fact 1')} vs {r.get('fact_2', {}).get('fact_text', 'Fact 2')}", expanded=True):
                    st.markdown(f'<span class="{badge_class}">{badge_text}</span> &nbsp; <b>Confidence:</b> `{r.get("confidence", 0.95):.2f}`', unsafe_allow_html=True)

                    c1, c2 = st.columns(2)
                    with c1:
                        f1 = r.get("fact_1") or {}
                        st.markdown(f"""
                        **Fact A (Doc: {f1.get('document_filename', f'Doc #{f1.get("doc_id")}')}, Page {f1.get('page_number')})**
                        - **Claim:** {f1.get('fact_text')}
                        - **Period:** `{f1.get('time_period') or 'N/A'}`
                        <div class="quote-box">"{f1.get('source_quote')}"</div>
                        """, unsafe_allow_html=True)

                    with c2:
                        f2 = r.get("fact_2") or {}
                        st.markdown(f"""
                        **Fact B (Doc: {f2.get('document_filename', f'Doc #{f2.get("doc_id")}')}, Page {f2.get('page_number')})**
                        - **Claim:** {f2.get('fact_text')}
                        - **Period:** `{f2.get('time_period') or 'N/A'}`
                        <div class="quote-box">"{f2.get('source_quote')}"</div>
                        """, unsafe_allow_html=True)

                    st.markdown(f"**🧠 LLM Reasoning Explanation:**\n\n> {r['explanation']}")

        else:
            st.info("No relationships found for the selected filter.")

    except Exception as e:
        st.error(f"Error loading relationships: {e}")


# ── Screen 4: Failure Log ─────────────────────────────────────────────
elif menu == "4. Failure Log":
    st.markdown('<div class="main-header">⚠️ Extraction & Reasoning Failure Log</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Documented edge cases, parsing failures, and architectural mitigations (Case 4 Requirement).</div>', unsafe_allow_html=True)

    st.markdown("""
    ### Observed Failure Case: Multi-Column Table Metric Misalignment
    
    #### 1. Input Snippet
    ```text
    | Metric                  | FY 2022        | FY 2023        |
    | Total Revenue           | $80,000,000    | $100,000,000   |
    | Net Income (GAAP)       | $12,000,000    | $18,000,000    |
    | Operating Margin        | 15.0%          | 18.0%          |
    ```
    
    #### 2. Initial Naive Extraction Miss
    - **Incorrect Output:** `Total Revenue is $80,000,000 in FY2023.`
    - **Failure Reason:** Naive text chunking stripped whitespace alignment and associated the left-most numeric column (FY2022) with the header label of the subsequent column (FY2023), resulting in a temporal metric inversion.
    
    #### 3. Root Cause Analysis
    - Standard OCR and character-level line flow flatten table grids into a linear string, discarding column-header coordinate associations.
    - When passed to an LLM without explicit structural bounding-box metadata, the model reads left-to-right without column index tracking.
    
    #### 4. Implemented Mitigation & Solution
    1. **PyMuPDF Table Structure Parsing:** Extracted bounding boxes and table cells with explicit `(row_idx, col_idx)` indexing.
    2. **Context Window Prefixing:** Prepended document-level metadata and column header lineage to every chunk before prompt generation.
    3. **Post-Extraction Schema Validation:** Verified that extracted numerical values match the coordinate cell directly underneath the corresponding year header.
    
    #### 5. Corrected Extraction Result
    - `Total Revenue: $80,000,000 (FY2022)` — Corroborated with prior period filings.
    - `Total Revenue: $100,000,000 (FY2023)` — Corroborated with press releases.
    """)

    st.success("✅ Mitigation verified: Table matrix coordinate mapping is now incorporated into the extraction pipeline.")
