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

## Requirements

- Python 3.11+
- [LM Studio](https://lmstudio.ai) running locally with:
  - An **embedding model** loaded (e.g. `nomic-embed-text`)
  - A **chat model** loaded (e.g. `qwen2.5-7b-instruct`)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — for scanned PDFs

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Setup

### 1. Download the documents

```bash
python3 download-ufo-release1.py
```

Downloads ~133 PDFs and images into `data/pdfs/`.

### 2. Convert PDFs to Markdown

```bash
python3 pdf_to_md.py
```

Uses `pymupdf4llm` for text-layer PDFs and Tesseract OCR as fallback. Output goes to `data/markdown/`.

### 3. Index for search (RAG)

Start LM Studio with an embedding model loaded, then:

```bash
python3 rag.py index
```

### 4. Extract entities (optional — for Mind Map)

```bash
python3 mindmap.py extract
```

Requires a chat model loaded in LM Studio. This step can take a while.

### 5. Run the app

```bash
python3 app.py
```

Opens at `http://localhost:7070`.

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
app.py                  # Flask web server + API routes
ui.html                 # Single-file frontend
rag.py                  # Vector indexing and retrieval
mindmap.py              # Entity extraction and knowledge graph
pdf_to_md.py            # PDF → Markdown conversion
download-ufo-release1.py # Document downloader
data/
  pdfs/                 # Downloaded PDFs (gitignored)
  markdown/             # Converted markdown (gitignored)
.chromadb/              # Vector DB + graph DB (gitignored)
```
