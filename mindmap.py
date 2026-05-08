#!/usr/bin/env python3
"""
Entity extraction, knowledge graph, and mindmap visualization
for DOW UFO Release 1 documents.

Commands:
    python3 mindmap.py extract            # extract entities from all markdown (uses LM Studio)
    python3 mindmap.py extract --file x   # extract from one file
    python3 mindmap.py view               # open full interactive graph in browser
    python3 mindmap.py view --topic ufo   # graph filtered to topic/keyword
    python3 mindmap.py lookup "Roswell"   # lookup entity + connections
    python3 mindmap.py stats              # entity/relationship counts

Env:
    LM_STUDIO_URL  — LM Studio base URL (default: http://localhost:1234/v1)
    LM_CHAT_MODEL  — model for extraction (default: auto-selects first loaded chat model)
    UAP_MD_DIR     — markdown dir (default: <project>/data/markdown)
    UAP_DB_DIR     — DB dir (default: <project>/.chromadb)
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import webbrowser
from pathlib import Path

MD_DIR = Path(os.environ.get("UAP_MD_DIR", Path(__file__).parent / "data" / "markdown"))
DB_PATH = Path(os.environ.get("UAP_DB_DIR", Path(__file__).parent / ".chromadb")) / "graph.db"
OUT_DIR = Path(__file__).parent / "visualizations"

LM_BASE_URL   = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_API_KEY    = os.environ.get("LM_API_KEY",    "lm-studio")
LM_CHAT_MODEL = os.environ.get("LM_CHAT_MODEL", "qwen2.5-7b-instruct-1m")

EXTRACT_PROMPT = """You are analyzing a declassified U.S. government document about UAP/UFOs.
Extract all notable entities and their relationships from the text below.

Return ONLY valid JSON in this exact format:
{
  "entities": [
    {"name": "string", "type": "PERSON|ORG|LOCATION|DATE|CRAFT|PHENOMENON|EVENT|DOCUMENT", "description": "brief description"}
  ],
  "relationships": [
    {"source": "entity name", "target": "entity name", "relation": "short verb phrase", "context": "one sentence"}
  ]
}

Rules:
- Entity names must be consistent (same name = same entity)
- Only extract entities clearly present in the text
- Relations should be directional verb phrases: "reported sighting at", "investigated", "authored", "located in", etc.
- Maximum 40 entities, 60 relationships
- Skip trivial/generic entities (e.g. "document", "report", "government")

Document source: {source}

Text:
{text}"""


# ── Database ──────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            id      INTEGER PRIMARY KEY,
            name    TEXT NOT NULL,
            type    TEXT NOT NULL,
            description TEXT,
            UNIQUE(name)
        );
        CREATE TABLE IF NOT EXISTS relationships (
            id      INTEGER PRIMARY KEY,
            source  TEXT NOT NULL,
            target  TEXT NOT NULL,
            relation TEXT NOT NULL,
            context TEXT,
            doc     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS processed_docs (
            source TEXT PRIMARY KEY,
            ts     TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source);
        CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target);
    """)
    conn.commit()
    return conn


# ── Extraction ────────────────────────────────────────────────────────────────

def get_chat_model(client) -> str:
    if LM_CHAT_MODEL:
        return LM_CHAT_MODEL
    models = client.models.list().data
    # Prefer non-embedding models
    for m in models:
        if "embed" not in m.id.lower():
            return m.id
    return models[0].id if models else "local-model"


def extract_entities(text: str, source: str, client, model: str) -> dict:
    MAX = 3000  # keep input small so output fits within token budget
    if len(text) > MAX:
        text = text[:MAX] + "\n...[truncated]"

    resp = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        temperature=0.1,
        messages=[{"role": "user", "content": EXTRACT_PROMPT.replace("{source}", source).replace("{text}", text)}],
    )
    raw = resp.choices[0].message.content.strip()

    # Strip <think>...</think> blocks (Qwen3, deepseek-r1, etc.)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    # Find the outermost JSON object in case there's prose around it
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Bad JSON from model. Raw response:\n{raw[:500]}")


def cmd_extract(args):
    from openai import OpenAI
    client = OpenAI(base_url=LM_BASE_URL, api_key=LM_API_KEY)
    model = get_chat_model(client)
    print(f"Using model: {model}\n")
    conn = get_db()

    if args.file:
        fname = args.file if args.file.endswith(".md") else args.file + ".md"
        md_files = [MD_DIR / fname]
    else:
        md_files = sorted(MD_DIR.glob("*.md"))

    if not md_files:
        print(f"No markdown files found in {MD_DIR}")
        sys.exit(1)

    already = {r[0] for r in conn.execute("SELECT source FROM processed_docs")}

    for i, md_path in enumerate(md_files, 1):
        source = md_path.stem
        if not args.force and source in already:
            print(f"  [{i:3}/{len(md_files)}] skip   {source}")
            continue

        text = md_path.read_text(encoding="utf-8", errors="ignore")
        if len(text.strip()) < 100:
            print(f"  [{i:3}/{len(md_files)}] empty  {source}")
            continue

        for attempt in range(1, 4):
            try:
                result = extract_entities(text, source, client, model)
                ents = result.get("entities", [])
                rels = result.get("relationships", [])

                for e in ents:
                    conn.execute(
                        "INSERT OR IGNORE INTO entities(name, type, description) VALUES(?,?,?)",
                        (e["name"], e.get("type", "UNKNOWN"), e.get("description", ""))
                    )

                for r in rels:
                    conn.execute(
                        "INSERT INTO relationships(source, target, relation, context, doc) VALUES(?,?,?,?,?)",
                        (r["source"], r["target"], r.get("relation", "related to"), r.get("context", ""), source)
                    )

                conn.execute("INSERT OR REPLACE INTO processed_docs(source) VALUES(?)", (source,))
                conn.commit()

                suffix = f" (attempt {attempt})" if attempt > 1 else ""
                print(f"  [{i:3}/{len(md_files)}] ok     {source}  ({len(ents)} entities, {len(rels)} rels){suffix}")
                break

            except (json.JSONDecodeError, ValueError):
                if attempt < 3:
                    print(f"  [{i:3}/{len(md_files)}] retry {attempt}/3  {source}")
                else:
                    print(f"  [{i:3}/{len(md_files)}] FAILED {source} after 3 attempts")
            except Exception as e:
                print(f"  [{i:3}/{len(md_files)}] ERROR  {source}: {e}")
                break

    conn.close()
    print("\nExtraction complete.")


# ── Graph building ─────────────────────────────────────────────────────────────

def build_graph(topic_filter: str = None):
    import networkx as nx

    conn = get_db()
    G = nx.DiGraph()

    # Add entity nodes
    for row in conn.execute("SELECT name, type, description FROM entities"):
        G.add_node(row["name"], type=row["type"], description=row["description"])

    # Add relationship edges
    query = "SELECT source, target, relation, context, doc FROM relationships"
    params = ()
    if topic_filter:
        kw = f"%{topic_filter}%"
        query += """ WHERE source LIKE ? OR target LIKE ? OR relation LIKE ?
                     OR context LIKE ? OR doc LIKE ?"""
        params = (kw, kw, kw, kw, kw)

    for row in conn.execute(query, params):
        src, tgt = row["source"], row["target"]
        if src not in G:
            G.add_node(src, type="UNKNOWN", description="")
        if tgt not in G:
            G.add_node(tgt, type="UNKNOWN", description="")
        if G.has_edge(src, tgt):
            G[src][tgt]["weight"] = G[src][tgt].get("weight", 1) + 1
            G[src][tgt]["docs"].add(row["doc"])
        else:
            G.add_edge(src, tgt, relation=row["relation"], context=row["context"],
                       weight=1, docs={row["doc"]})

    conn.close()
    return G


# ── Visualization ─────────────────────────────────────────────────────────────

TYPE_COLORS = {
    "PERSON":     "#e74c3c",
    "ORG":        "#3498db",
    "LOCATION":   "#2ecc71",
    "DATE":       "#95a5a6",
    "CRAFT":      "#f39c12",
    "PHENOMENON": "#9b59b6",
    "EVENT":      "#1abc9c",
    "DOCUMENT":   "#e67e22",
    "UNKNOWN":    "#bdc3c7",
}


def build_pyvis(G, title: str) -> str:
    from pyvis.network import Network
    import networkx as nx

    net = Network(height="92vh", width="100%", bgcolor="#0d1117", font_color="#c9d1d9",
                  directed=True, notebook=False)
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=120, spring_strength=0.04)

    # Degree-based sizing
    degrees = dict(G.degree())
    max_deg = max(degrees.values(), default=1)

    for node, data in G.nodes(data=True):
        ntype = data.get("type", "UNKNOWN")
        color = TYPE_COLORS.get(ntype, "#bdc3c7")
        size = 10 + 30 * (degrees.get(node, 0) / max_deg)
        desc = data.get("description", "")
        label = node if len(node) <= 30 else node[:28] + "…"
        net.add_node(
            node, label=label, title=f"<b>{node}</b><br>Type: {ntype}<br>{desc}",
            color=color, size=size, font={"size": 11, "color": "#c9d1d9"},
        )

    for src, tgt, data in G.edges(data=True):
        docs = ", ".join(sorted(data.get("docs", set())))
        weight = data.get("weight", 1)
        net.add_edge(
            src, tgt,
            title=f"{data.get('relation','')}<br><i>{data.get('context','')}</i><br>Docs: {docs}",
            label=data.get("relation", ""),
            width=1 + weight * 0.4,
            color={"color": "#444c56", "highlight": "#58a6ff"},
            font={"size": 9, "color": "#8b949e", "align": "middle"},
            arrows={"to": {"enabled": True, "scaleFactor": 0.5}},
        )

    # Legend HTML
    legend_items = "".join(
        f'<span style="background:{c};padding:2px 8px;border-radius:3px;margin:2px;font-size:11px">{t}</span>'
        for t, c in TYPE_COLORS.items() if t != "UNKNOWN"
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^\w-]", "_", title)
    out_path = OUT_DIR / f"{safe_title}.html"

    net.save_graph(str(out_path))

    # Inject title + legend + dark polish into the generated HTML
    html = out_path.read_text()
    inject = f"""
    <style>
      body {{ margin:0; background:#0d1117; font-family: monospace; }}
      #header {{ position:fixed; top:0; left:0; right:0; z-index:999;
                 background:rgba(13,17,23,.92); padding:8px 16px;
                 border-bottom:1px solid #30363d; display:flex;
                 align-items:center; gap:12px; flex-wrap:wrap; }}
      #header h1 {{ color:#e6edf3; font-size:14px; margin:0; }}
      #legend {{ display:flex; flex-wrap:wrap; gap:4px; }}
      #stats {{ color:#8b949e; font-size:11px; margin-left:auto; }}
      #mynetwork {{ margin-top:44px !important; }}
    </style>
    <div id="header">
      <h1>UAP Knowledge Graph — {title}</h1>
      <div id="legend">{legend_items}</div>
      <span id="stats">{G.number_of_nodes()} nodes · {G.number_of_edges()} edges</span>
    </div>
    """
    html = html.replace("<body>", f"<body>\n{inject}", 1)
    out_path.write_text(html)
    return str(out_path)


def cmd_view(args):
    import networkx as nx

    topic = args.topic
    print(f"Building graph{' (filter: ' + topic + ')' if topic else ''}...")
    G = build_graph(topic_filter=topic)

    if G.number_of_nodes() == 0:
        print("No data — run: python3 mindmap.py extract")
        sys.exit(1)

    title = topic if topic else "full"
    print(f"  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    path = build_pyvis(G, title)
    print(f"  Saved: {path}")
    webbrowser.open(f"file://{path}")


# ── Lookup ────────────────────────────────────────────────────────────────────

def cmd_lookup(args):
    term = args.term
    conn = get_db()

    # Entity match
    entities = conn.execute(
        "SELECT name, type, description FROM entities WHERE name LIKE ? ORDER BY name",
        (f"%{term}%",)
    ).fetchall()

    # Outgoing relationships
    rels_out = conn.execute(
        "SELECT source, target, relation, context, doc FROM relationships WHERE source LIKE ? ORDER BY source",
        (f"%{term}%",)
    ).fetchall()

    # Incoming relationships
    rels_in = conn.execute(
        "SELECT source, target, relation, context, doc FROM relationships WHERE target LIKE ? ORDER BY target",
        (f"%{term}%",)
    ).fetchall()

    # Docs mentioning the term
    docs = conn.execute(
        "SELECT DISTINCT doc FROM relationships WHERE source LIKE ? OR target LIKE ? ORDER BY doc",
        (f"%{term}%", f"%{term}%")
    ).fetchall()

    conn.close()

    if not entities and not rels_out and not rels_in:
        print(f"No results for '{term}'")
        return

    print(f"\n{'━'*60}")
    print(f"  LOOKUP: {term}")
    print(f"{'━'*60}")

    if entities:
        print(f"\n── Entities ({len(entities)}) ──")
        for e in entities:
            print(f"  [{e['type']}] {e['name']}")
            if e["description"]:
                print(f"         {e['description']}")

    if rels_out:
        print(f"\n── Outgoing relationships ({len(rels_out)}) ──")
        for r in rels_out:
            print(f"  {r['source']}  ──[{r['relation']}]──▶  {r['target']}")
            print(f"    context: {r['context']}")
            print(f"    source doc: {r['doc']}")

    if rels_in:
        print(f"\n── Incoming relationships ({len(rels_in)}) ──")
        for r in rels_in:
            print(f"  {r['source']}  ──[{r['relation']}]──▶  {r['target']}")
            print(f"    source doc: {r['doc']}")

    if docs:
        print(f"\n── Appears in {len(docs)} document(s) ──")
        for d in docs:
            print(f"  {d['doc']}")

    # Offer to open filtered graph
    print(f"\n  Tip: python3 mindmap.py view --topic \"{term}\"  (open filtered graph)")


# ── Stats ─────────────────────────────────────────────────────────────────────

def cmd_stats(args):
    conn = get_db()

    total_ents = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    total_rels = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    total_docs = conn.execute("SELECT COUNT(*) FROM processed_docs").fetchone()[0]

    print(f"\nGraph DB: {DB_PATH}")
    print(f"  Processed docs : {total_docs}")
    print(f"  Entities       : {total_ents}")
    print(f"  Relationships  : {total_rels}")

    print(f"\n── Entity types ──")
    for row in conn.execute("SELECT type, COUNT(*) as n FROM entities GROUP BY type ORDER BY n DESC"):
        print(f"  {row['type']:<15} {row['n']}")

    print(f"\n── Most connected entities (top 15) ──")
    rows = conn.execute("""
        SELECT name, COUNT(*) as n FROM (
            SELECT source as name FROM relationships
            UNION ALL
            SELECT target as name FROM relationships
        ) GROUP BY name ORDER BY n DESC LIMIT 15
    """).fetchall()
    for r in rows:
        print(f"  {r['n']:4}  {r['name']}")

    conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("extract", help="Extract entities from markdown files using Claude")
    p.add_argument("--file", help="Process a single file")
    p.add_argument("--force", action="store_true", help="Re-process already-extracted docs")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("view", help="Open interactive knowledge graph in browser")
    p.add_argument("--topic", help="Filter graph to keyword/topic")
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("lookup", help="Look up an entity or keyword")
    p.add_argument("term")
    p.set_defaults(func=cmd_lookup)

    p = sub.add_parser("stats", help="Show graph statistics")
    p.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
