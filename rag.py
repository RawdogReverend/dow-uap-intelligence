#!/usr/bin/env python3
"""
RAG system for DOW UFO Release 1 markdown files.

Commands:
    python3 rag.py index              # ingest all markdown files into vector DB
    python3 rag.py index --force      # re-index everything
    python3 rag.py query "question"   # single query
    python3 rag.py chat               # interactive chat loop
    python3 rag.py stats              # show index stats

Env:
    ANTHROPIC_API_KEY  — required for query/chat
    LM_STUDIO_URL      — LM Studio base URL (default: http://localhost:1234/v1)
    EMBED_MODEL        — embedding model name loaded in LM Studio
    UAP_MD_DIR         — markdown dir (default: <project>/data/markdown)
    UAP_DB_DIR         — chroma DB dir (default: <project>/.chromadb)
"""

import argparse
import os
import re
import sys
from pathlib import Path

MD_DIR = Path(os.environ.get("UAP_MD_DIR", Path(__file__).parent / "data" / "markdown"))
DB_DIR = Path(os.environ.get("UAP_DB_DIR", Path(__file__).parent / ".chromadb"))

COLLECTION   = "uap_release1"
LM_CHAT_MODEL = os.environ.get("LM_CHAT_MODEL", "qwen2.5-7b-instruct-1m")
CHUNK_SIZE   = 800
CHUNK_OVERLAP = 150
TOP_K = 8

# Embedding backend — one of: "lmstudio" | "ollama"
EMBED_BACKEND = os.environ.get("EMBED_BACKEND", "lmstudio")
EMBED_MODEL   = os.environ.get("EMBED_MODEL",   "text-embedding-nomic-embed-text-v1.5")
LM_BASE_URL   = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
OLLAMA_URL    = os.environ.get("OLLAMA_URL",    "http://localhost:11434")


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split markdown into overlapping character chunks, preserving section headers."""
    # Strip HTML comments (page markers from OCR)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        # Extend to end of sentence if possible
        if end < len(text):
            for sep in ("\n\n", ". ", "\n", " "):
                pos = text.rfind(sep, start + CHUNK_SIZE // 2, end)
                if pos != -1:
                    end = pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append({"text": chunk, "source": source, "start": start})
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


# ── Embeddings ────────────────────────────────────────────────────────────────

def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings. Dispatches to LM Studio or Ollama."""
    if EMBED_BACKEND == "ollama":
        return _embed_ollama(texts)
    return _embed_lmstudio(texts)


def _embed_lmstudio(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(base_url=LM_BASE_URL, api_key="lm-studio")
    results = []
    batch_size = 16
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        results.extend(d.embedding for d in resp.data)
    return results


def _embed_ollama(texts: list[str]) -> list[list[float]]:
    import urllib.request, json
    results = []
    for text in texts:
        payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            results.append(json.load(r)["embedding"])
    return results


# ── Index ─────────────────────────────────────────────────────────────────────

def get_collection(client):
    return client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def index(force: bool = False):
    import chromadb

    md_files = sorted(MD_DIR.glob("*.md"))
    if not md_files:
        print(f"No markdown files found in {MD_DIR}")
        print("Run pdf_to_md.py first.")
        sys.exit(1)

    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    col = get_collection(client)

    if force:
        client.delete_collection(COLLECTION)
        col = get_collection(client)
        print("Collection cleared.")

    existing = set(col.get(include=[])["ids"])

    print(f"Embedding backend : {EMBED_BACKEND}")
    print(f"Embedding model   : {EMBED_MODEL}\n")

    total_chunks = 0
    skipped = 0

    for i, md_path in enumerate(md_files, 1):
        source = md_path.stem
        marker_id = f"{source}::0"
        if not force and marker_id in existing:
            skipped += 1
            continue

        text = md_path.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_markdown(text, source)
        if not chunks:
            continue

        ids = [f"{source}::{j}" for j in range(len(chunks))]
        texts = [c["text"] for c in chunks]
        metas = [{"source": c["source"], "start": c["start"]} for c in chunks]

        embeddings = embed(texts)

        # Upsert in batches of 100
        batch = 100
        for b in range(0, len(ids), batch):
            col.upsert(
                ids=ids[b:b+batch],
                embeddings=embeddings[b:b+batch],
                documents=texts[b:b+batch],
                metadatas=metas[b:b+batch],
            )

        total_chunks += len(chunks)
        print(f"  [{i:3}/{len(md_files)}] indexed {len(chunks):4} chunks — {source}")

    print(f"\nDone. {total_chunks} new chunks indexed, {skipped} files skipped (already indexed).")
    print(f"Total in DB: {col.count()}")


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    import chromadb

    client = chromadb.PersistentClient(path=str(DB_DIR))
    col = get_collection(client)

    if col.count() == 0:
        print("Index is empty. Run: python3 rag.py index")
        sys.exit(1)

    q_embedding = embed([query])

    results = col.query(
        query_embeddings=q_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "text": doc,
            "source": meta["source"],
            "score": round(1 - dist, 4),  # cosine similarity
        })
    return hits


# ── Generation ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an analyst helping researchers understand declassified U.S. government \
documents about Unidentified Anomalous Phenomena (UAP/UFO) released by the Department of War \
on May 8, 2026. Answer questions based strictly on the provided document excerpts. \
If the answer isn't in the excerpts, say so clearly. Cite the source document(s) by name."""


def build_context(hits: list[dict]) -> str:
    parts = []
    seen_sources = {}
    for h in hits:
        src = h["source"]
        seen_sources.setdefault(src, []).append(h["text"])

    for src, texts in seen_sources.items():
        parts.append(f"--- SOURCE: {src} ---\n" + "\n\n".join(texts))

    return "\n\n".join(parts)


def get_chat_model(client) -> str:
    if LM_CHAT_MODEL:
        return LM_CHAT_MODEL
    models = [m.id for m in client.models.list().data if "embed" not in m.id.lower()]
    if not models:
        print("No chat model found in LM Studio. Load one or set LM_CHAT_MODEL.")
        sys.exit(1)
    return models[0]


def ask(query: str, history: list[dict] | None = None) -> str:
    from openai import OpenAI

    hits = retrieve(query)
    context = build_context(hits)
    sources_used = sorted({h["source"] for h in hits})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history or []
    messages.append({
        "role": "user",
        "content": f"<documents>\n{context}\n</documents>\n\nQuestion: {query}",
    })

    client = OpenAI(base_url=LM_BASE_URL, api_key="lm-studio")
    model = get_chat_model(client)
    response = client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=messages,
    )

    answer = response.choices[0].message.content
    return answer, sources_used, hits


# ── CLI ───────────────────────────────────────────────────────────────────────

def cmd_index(args):
    index(force=args.force)


def cmd_query(args):
    query = " ".join(args.question)
    print(f"\nQuery: {query}\n")
    answer, sources, hits = ask(query)
    print(answer)
    print(f"\n── Sources ({len(sources)}) ──")
    for s in sources:
        score = max(h["score"] for h in hits if h["source"] == s)
        print(f"  {s}  (score: {score})")


def cmd_chat(args):
    print("UAP Document RAG — type 'quit' to exit, 'sources' to see last sources\n")
    history = []
    last_sources = []

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            break
        if query.lower() == "sources":
            for s in last_sources:
                print(f"  {s}")
            continue

        answer, last_sources, hits = ask(query, history)
        print(f"\nAssistant: {answer}\n")

        # Keep last 6 turns in history
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": answer})
        history = history[-12:]


def cmd_stats(args):
    import chromadb
    client = chromadb.PersistentClient(path=str(DB_DIR))
    col = get_collection(client)
    count = col.count()
    print(f"Collection     : {COLLECTION}")
    print(f"DB path        : {DB_DIR}")
    print(f"Chunks         : {count}")
    print(f"MD dir         : {MD_DIR}")
    print(f"MD files       : {len(list(MD_DIR.glob('*.md')))}")
    print(f"Embed backend  : {EMBED_BACKEND}")
    print(f"Embed model    : {EMBED_MODEL}")
    url = OLLAMA_URL if EMBED_BACKEND == "ollama" else LM_BASE_URL
    print(f"Embed URL      : {url}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")

    p_index = sub.add_parser("index", help="Ingest markdown files into vector DB")
    p_index.add_argument("--force", action="store_true", help="Re-index everything")
    p_index.set_defaults(func=cmd_index)

    p_query = sub.add_parser("query", help="Single question")
    p_query.add_argument("question", nargs="+")
    p_query.set_defaults(func=cmd_query)

    p_chat = sub.add_parser("chat", help="Interactive chat")
    p_chat.set_defaults(func=cmd_chat)

    p_stats = sub.add_parser("stats", help="Show index stats")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
