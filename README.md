# DOW UAP Intelligence

A local web app for exploring the **161 declassified UAP/UFO documents** released by the U.S. Department of War on May 8, 2026.

Runs entirely on your machine — no cloud APIs required. Uses [LM Studio](https://lmstudio.ai) for embeddings and chat inference.

---

## Features

- **Chat** — Ask questions grounded in retrieved document excerpts (RAG)
- **Mind Map** — Interactive knowledge graph of extracted entities and relationships
- **Entity Lookup** — Search people, places, craft, events across all documents
- **Document Reader** — Browse and full-text search the raw markdown files

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/RawdogReverend/dow-uap-intelligence.git
cd dow-uap-intelligence

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python3 app.py
```

That's it. Open `http://localhost:7070` and the built-in **Settings** panel walks you through the rest — connecting to LM Studio, downloading the documents, running OCR, indexing, and entity extraction all from inside the app.

---

## Requirements

- Python 3.11+
- [LM Studio](https://lmstudio.ai) running locally with:
  - An **embedding model** loaded (e.g. `nomic-embed-text`)
  - A **chat model** loaded (e.g. `qwen2.5-7b-instruct`)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — for scanned PDFs (most documents have a text layer, so this is usually optional)

---

## Manual Pipeline (CLI alternative)

The app handles everything via its UI, but you can also run each step from the command line:

```bash
# Download the documents (~133 PDFs)
python3 download-ufo-release1.py

# Convert PDFs to Markdown
python3 pdf_to_md.py

# Index for RAG search (requires embedding model in LM Studio)
python3 rag.py index

# Extract entities for Mind Map (optional, takes a while)
python3 mindmap.py extract
```

---

## Configuration

On first launch, click **Settings** (⚙️) to set your LM Studio URL and select models. Settings are saved to `config.json` (gitignored).

Environment variable overrides:

| Variable | Default | Description |
|---|---|---|
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LM Studio API base URL |
| `UAP_MD_DIR` | `<project>/data/markdown` | Markdown source directory |
| `UAP_DB_DIR` | `<project>/.chromadb` | Vector + graph DB directory |
| `PORT` | `7070` | Web app port |

---

## Project Structure

```
app.py                    # Flask web server + API routes
ui.html                   # Single-file frontend
rag.py                    # Vector indexing and retrieval
mindmap.py                # Entity extraction and knowledge graph
pdf_to_md.py              # PDF → Markdown conversion
download-ufo-release1.py  # Document downloader
data/
  pdfs/                   # Downloaded PDFs (gitignored)
  markdown/               # Converted markdown (gitignored)
.chromadb/                # Vector DB + graph DB (gitignored)
```
