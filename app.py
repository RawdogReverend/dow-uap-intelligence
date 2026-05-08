#!/usr/bin/env python3
"""DOW UAP Files — local web UI.  Run: python3 app.py"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path
from threading import Timer

try:
    from flask import Flask, Response, jsonify, request
except ImportError:
    print("pip install flask"); sys.exit(1)

ROOT       = Path(__file__).parent
CONFIG_F   = ROOT / "config.json"
PDF_DIR    = ROOT / "data" / "pdfs"
MD_DIR     = ROOT / "data" / "markdown"
DB_DIR     = ROOT / ".chromadb"
GRAPH_DB   = DB_DIR / "graph.db"
COLLECTION = "uap_release1"

ENTITY_COLORS = {
    "PERSON":"#f87171","ORG":"#60a5fa","LOCATION":"#4ade80","DATE":"#fbbf24",
    "CRAFT":"#c084fc","PHENOMENON":"#34d399","EVENT":"#fb923c",
    "DOCUMENT":"#94a3b8","UNKNOWN":"#64748b",
}

SYSTEM_PROMPT = (
    "You are an expert analyst helping researchers understand declassified U.S. government "
    "documents about Unidentified Anomalous Phenomena (UAP/UFO) released by the Department of War "
    "on May 8, 2026. Answer questions based strictly on the provided document excerpts. "
    "Quote relevant passages when helpful. "
    "If the answer is not clearly supported by the excerpts, say so explicitly. "
    "Cite source documents by name at the end of your answer."
)

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

def load_cfg():
    return json.loads(CONFIG_F.read_text()) if CONFIG_F.exists() else {}

def save_cfg(d):
    CONFIG_F.write_text(json.dumps(d, indent=2))

def cfg(key, default=""):
    return load_cfg().get(key, default)

# ── RAG ───────────────────────────────────────────────────────────────────────

def lm():
    from openai import OpenAI
    return OpenAI(base_url=cfg("lm_base_url", "http://localhost:1234/v1"), api_key="lm-studio")

def embed(texts):
    resp = lm().embeddings.create(model=cfg("embed_model"), input=texts)
    return [d.embedding for d in resp.data]

def retrieve(query, top_k=8):
    import chromadb
    col = chromadb.PersistentClient(path=str(DB_DIR)).get_or_create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine"})
    if col.count() == 0:
        return []
    res = col.query(query_embeddings=embed([query]), n_results=top_k,
                    include=["documents", "metadatas", "distances"])
    return [{"text": doc, "source": meta["source"], "score": round(1 - dist, 4)}
            for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])]

def build_context(hits):
    by_src = {}
    for h in hits:
        by_src.setdefault(h["source"], []).append(h["text"])
    return "\n\n".join(f"--- SOURCE: {s} ---\n" + "\n\n".join(t) for s, t in by_src.items())

# ── Graph ─────────────────────────────────────────────────────────────────────

CLICK_INJECT = """<script>
(function poll(){
  if(typeof network!=='undefined'){
    network.on('click',function(p){
      if(p.nodes.length) window.parent.postMessage({type:'node',id:p.nodes[0]},'*');
    });
  } else setTimeout(poll,100);
})();
</script>"""

def build_graph_html(filter_types=None, min_deg=1):
    try:
        import networkx as nx
        from pyvis.network import Network
    except ImportError:
        return "<p style='color:#f87171;font-family:sans-serif;padding:2rem'>pip install networkx pyvis</p>"
    if not GRAPH_DB.exists():
        return "<p style='color:#64748b;font-family:sans-serif;padding:2rem'>No graph DB — run entity extraction first.</p>"

    conn = sqlite3.connect(str(GRAPH_DB))
    G = nx.DiGraph()
    for name, etype, desc in conn.execute("SELECT name, type, description FROM entities"):
        if filter_types and etype not in filter_types:
            continue
        G.add_node(name, etype=etype, desc=desc or "")
    for src, tgt, rel, doc in conn.execute("SELECT source, target, relation, doc FROM relationships"):
        if src in G and tgt in G:
            G.add_edge(src, tgt, label=rel, doc=doc)
    conn.close()

    if min_deg > 0:
        G.remove_nodes_from([n for n in list(G) if G.degree(n) < min_deg])
    if not G.number_of_nodes():
        return "<p style='color:#64748b;font-family:sans-serif;padding:2rem'>No nodes match filters.</p>"

    net = Network(height="100vh", width="100%", bgcolor="#07090f", font_color="#c8d8e8", directed=True)
    net.from_nx(G)
    for node in net.nodes:
        nid   = node["id"]
        etype = G.nodes[nid].get("etype", "UNKNOWN")
        deg   = G.degree(nid)
        desc  = G.nodes[nid].get("desc", "")[:120]
        node["color"] = ENTITY_COLORS.get(etype, "#64748b")
        node["size"]  = max(10, min(55, 10 + deg * 4))
        node["title"] = f"<div style='font-family:sans-serif;font-size:13px'><b>{nid}</b><br><i style='color:#94a3b8'>{etype}</i><br>{desc}</div>"
        node["font"]  = {"size": 12}
    for edge in net.edges:
        edge["color"] = {"color": "#1e3050", "opacity": 0.7}
        edge["title"] = edge.get("label", "")
        edge["width"] = 1.5

    net.force_atlas_2based(gravity=-40, spring_length=110, spring_strength=0.06)

    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    net.save_graph(tmp.name)
    html = Path(tmp.name).read_text()
    Path(tmp.name).unlink(missing_ok=True)
    return html.replace("</body>", CLICK_INJECT + "</body>")

# ── Status ────────────────────────────────────────────────────────────────────

def get_status():
    try:
        import chromadb
        col = chromadb.PersistentClient(path=str(DB_DIR)).get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine"})
        chunks = col.count()
    except Exception:
        chunks = 0
    ents = rels = 0
    if GRAPH_DB.exists():
        db = sqlite3.connect(str(GRAPH_DB))
        ents = db.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        rels = db.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
        db.close()
    return {
        "pdfs":   len(list(PDF_DIR.glob("*.pdf"))) if PDF_DIR.exists() else 0,
        "mds":    len(list(MD_DIR.glob("*.md")))   if MD_DIR.exists()  else 0,
        "chunks": chunks, "ents": ents, "rels": rels,
    }

# ── Helpers ───────────────────────────────────────────────────────────────────

def sse(data):
    return f"data: {json.dumps(data)}\n\n"

def sse_response(gen):
    return Response(gen, mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return (ROOT / "ui.html").read_text()

@app.route("/api/config")
def get_config():
    return jsonify(load_cfg())

@app.route("/api/setup", methods=["POST"])
def setup():
    save_cfg(request.json)
    return jsonify({"ok": True})

@app.route("/api/models")
def get_models():
    from openai import OpenAI
    url = request.args.get("url", "http://localhost:1234/v1")
    try:
        models = [m.id for m in OpenAI(base_url=url, api_key="lm-studio").models.list().data]
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/status")
def status():
    return jsonify(get_status())

@app.route("/api/pipeline/<step>", methods=["POST"])
def run_pipeline(step):
    body = request.get_json(silent=True) or {}
    STEPS = {
        "download": [sys.executable, "download-ufo-release1.py"],
        "ocr":      [sys.executable, "pdf_to_md.py", "--jobs", str(body.get("jobs", 4))],
        "index":    [sys.executable, "rag.py", "index"] + (["--force"] if body.get("force") else []),
        "extract":  [sys.executable, "mindmap.py", "extract"] + (["--force"] if body.get("force") else []),
    }
    if step not in STEPS:
        return jsonify({"error": "unknown step"}), 400
    def gen():
        env = os.environ.copy()
        env["LM_STUDIO_URL"] = cfg("lm_base_url", "http://localhost:1234/v1")
        env["EMBED_MODEL"]   = cfg("embed_model", "")
        proc = subprocess.Popen(STEPS[step], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, cwd=str(ROOT), env=env)
        for line in proc.stdout:
            yield sse({"line": line.rstrip()})
        proc.wait()
        yield sse({"done": True, "code": proc.returncode})
    return sse_response(gen())

@app.route("/api/chat", methods=["POST"])
def chat():
    body       = request.get_json(silent=True) or {}
    query      = body.get("query", "")
    history    = body.get("history", [])
    c          = load_cfg()
    top_k      = int(c.get("top_k", 8))
    max_tokens = int(c.get("max_tokens", 2048))
    temperature= float(c.get("temperature", 0.7))
    min_score  = float(c.get("min_rag_score", 0.0))
    def gen():
        try:
            hits    = retrieve(query, top_k)
            if min_score > 0:
                hits = [h for h in hits if h["score"] >= min_score]
            if not hits:
                yield sse({"sources": [], "hits": []})
                yield sse({"token": "No document excerpts met the minimum relevance threshold. Try lowering Min RAG Score in settings."})
                yield sse({"done": True})
                return
            context = build_context(hits)
            sources = sorted({h["source"] for h in hits})
            yield sse({"sources": sources, "hits": hits})
            msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
            for m in history[-12:]:
                msgs.append({"role": m["role"], "content": m["content"]})
            msgs.append({"role": "user",
                         "content": f"<documents>\n{context}\n</documents>\n\nQuestion: {query}"})
            stream = lm().chat.completions.create(
                model=cfg("chat_model"), messages=msgs, stream=True,
                max_tokens=max_tokens, temperature=temperature)
            for chunk in stream:
                t = chunk.choices[0].delta.content or ""
                if t:
                    yield sse({"token": t})
        except Exception as e:
            yield sse({"error": str(e)})
        yield sse({"done": True})
    return sse_response(gen())

@app.route("/api/mindmap")
def mindmap():
    types   = request.args.get("types", "")
    min_deg = int(request.args.get("min_deg", 1))
    ft      = set(types.split(",")) if types else None
    return Response(build_graph_html(ft, min_deg), mimetype="text/html")

@app.route("/api/entity/<path:name>")
def get_entity(name):
    if not GRAPH_DB.exists():
        return jsonify({"error": "no graph"}), 404
    conn = sqlite3.connect(str(GRAPH_DB))
    conn.row_factory = sqlite3.Row
    ent  = conn.execute("SELECT * FROM entities WHERE name=?", (name,)).fetchone()
    if not ent:
        conn.close()
        return jsonify({"error": "not found"}), 404
    outs = conn.execute("SELECT target,relation,context,doc FROM relationships WHERE source=? LIMIT 30", (name,)).fetchall()
    incs = conn.execute("SELECT source,relation,doc FROM relationships WHERE target=? LIMIT 30",          (name,)).fetchall()
    docs = conn.execute("SELECT DISTINCT doc FROM relationships WHERE source=? OR target=?", (name, name)).fetchall()
    conn.close()
    return jsonify({
        "name": ent["name"], "type": ent["type"], "description": ent["description"],
        "outgoing": [dict(r) for r in outs],
        "incoming": [dict(r) for r in incs],
        "docs": [r["doc"] for r in docs],
    })

@app.route("/api/lookup")
def lookup():
    q = request.args.get("q", "")
    if not q or not GRAPH_DB.exists():
        return jsonify([])
    conn = sqlite3.connect(str(GRAPH_DB))
    conn.row_factory = sqlite3.Row
    pat  = f"%{q}%"
    ents = conn.execute(
        "SELECT name,type,description FROM entities WHERE name LIKE ? OR description LIKE ? ORDER BY name LIMIT 40",
        (pat, pat)).fetchall()
    out = []
    for e in ents:
        outs = conn.execute("SELECT target,relation,context,doc FROM relationships WHERE source=? LIMIT 25", (e["name"],)).fetchall()
        incs = conn.execute("SELECT source,relation,doc FROM relationships WHERE target=? LIMIT 25",          (e["name"],)).fetchall()
        out.append({"name": e["name"], "type": e["type"], "description": e["description"],
                    "outgoing": [dict(r) for r in outs], "incoming": [dict(r) for r in incs]})
    conn.close()
    return jsonify(out)

@app.route("/api/docs")
def list_docs():
    if not MD_DIR.exists():
        return jsonify([])
    docs = sorted(
        [{"name": p.stem, "size": p.stat().st_size}
         for p in MD_DIR.glob("*.md")],
        key=lambda d: d["name"]
    )
    return jsonify(docs)

@app.route("/api/doc/<path:name>")
def get_doc(name):
    safe = re.sub(r"[^\w\-. ]", "", name)
    p    = MD_DIR / (safe if safe.endswith(".md") else safe + ".md")
    if not p.exists():
        return jsonify({"error": "not found"}), 404
    text = p.read_text(encoding="utf-8", errors="ignore")
    return jsonify({"name": p.stem, "text": text, "size": p.stat().st_size})

@app.route("/api/stats")
def stats():
    s = get_status()
    if GRAPH_DB.exists():
        db = sqlite3.connect(str(GRAPH_DB))
        s["breakdown"] = [{"type": r[0], "count": r[1]}
                          for r in db.execute("SELECT type,COUNT(*) n FROM entities GROUP BY type ORDER BY n DESC").fetchall()]
        s["top_entities"] = [{"name": r[0], "type": r[1], "n": r[2]}
                             for r in db.execute("""
            SELECT e.name, e.type, COUNT(r.rowid) n FROM entities e
            LEFT JOIN (SELECT rowid,source nm FROM relationships UNION ALL SELECT rowid,target FROM relationships) r
            ON r.nm=e.name GROUP BY e.name ORDER BY n DESC LIMIT 20
        """).fetchall()]
        db.close()
    return jsonify(s)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7070))
    Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    print(f"\n🛸  DOW UAP Files  →  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
