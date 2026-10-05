"""
Flask backend for Smart Study Generator.
Serves the frontend AND the REST API from the same origin — no CORS needed.
API key lives here — NEVER sent to the frontend.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from groq import RateLimitError, BadRequestError

from agent import run_agent
from document_processor import process_uploaded_file, combine_document_texts
from guardrails import (
    sanitise_student_profile,
    sanitise_text,
    sanitise_filename,
    validate_uploaded_file,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Resolve the frontend folder relative to this file: backend/../frontend
_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Flask serves static files from the frontend folder
app = Flask(__name__, static_folder=str(_FRONTEND_DIR), static_url_path="")
# Keep CORS for any external tooling / dev server access
CORS(app, origins=["http://localhost:5500", "http://127.0.0.1:5500",
                   "http://localhost:8080", "http://localhost:5000",
                   "http://127.0.0.1:5000", "null"])


# ---------------------------------------------------------------------------
# Serve frontend files (index.html + assets)
# ---------------------------------------------------------------------------
@app.route("/")
def serve_index():
    return send_from_directory(str(_FRONTEND_DIR), "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    """Serve any frontend asset (style.css, script.js, etc.)."""
    return send_from_directory(str(_FRONTEND_DIR), filename)

# In-memory progress store (per-session; replace with a DB for production)
_progress_store: dict[str, dict] = {}
_session_docs: dict[str, list[dict]] = {}   # session_id → list of processed docs


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _get_or_create_session(session_id: str | None) -> str:
    if not session_id or len(session_id) > 64:
        return str(uuid.uuid4())
    return session_id


def _current_progress(session_id: str) -> dict:
    return _progress_store.setdefault(session_id, {
        "quiz_scores": [],
        "topics_studied": [],
        "weak_areas": [],
        "milestones": [],
        "total_queries": 0,
        "session_start": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def health():
    groq_key_set = bool(os.getenv("GROQ_API_KEY"))
    return jsonify({
        "status": "ok",
        "groq_configured": groq_key_set,
        "model": "qwen/qwen3.8-27b",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# POST /api/profile — save / update student profile in session
# ---------------------------------------------------------------------------
@app.route("/api/profile", methods=["POST"])
def save_profile():
    data = request.get_json(silent=True) or {}
    session_id = _get_or_create_session(data.get("session_id"))
    profile = sanitise_student_profile(data.get("profile", {}))

    progress = _current_progress(session_id)
    progress["profile"] = profile
    progress["total_queries"] = 0

    logger.info("Profile saved for session %s", session_id)
    return jsonify({"status": "ok", "session_id": session_id, "profile": profile})


# ---------------------------------------------------------------------------
# POST /api/upload — upload study documents
# ---------------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def upload_documents():
    session_id = _get_or_create_session(request.form.get("session_id"))
    uploaded_files = request.files.getlist("files")

    if not uploaded_files:
        return jsonify({"error": "No files uploaded"}), 400

    results = []
    docs = _session_docs.setdefault(session_id, [])

    for f in uploaded_files:
        raw_name = f.filename or "unnamed"
        safe_name = sanitise_filename(raw_name)
        content = f.read()

        valid, reason = validate_uploaded_file(safe_name, content)
        if not valid:
            results.append({"filename": safe_name, "status": "rejected", "reason": reason})
            continue

        doc = process_uploaded_file(safe_name, content)
        docs.append(doc)
        results.append({
            "filename": safe_name,
            "status": "processed",
            "type": doc["type"],
            "chars_extracted": doc["chars"],
        })
        logger.info("Processed file '%s' (%d chars) for session %s",
                    safe_name, doc["chars"], session_id)

    return jsonify({
        "session_id": session_id,
        "uploaded": results,
        "total_docs": len(docs),
    })


# ---------------------------------------------------------------------------
# POST /api/query — main agentic endpoint
# ---------------------------------------------------------------------------
@app.route("/api/query", methods=["POST"])
def query_agent():
    data = request.get_json(silent=True) or {}
    session_id = _get_or_create_session(data.get("session_id"))

    raw_query = data.get("query", "").strip()
    if not raw_query:
        return jsonify({"error": "Query cannot be empty"}), 400

    query = sanitise_text(raw_query, max_chars=5000)
    action_override = data.get("action")  # e.g. "create_flashcards" from UI button
    if not isinstance(action_override, str):
        action_override = None
    student_profile = _current_progress(session_id).get("profile", {})

    # Combine any uploaded documents
    docs = _session_docs.get(session_id, [])
    document_text = combine_document_texts(docs) if docs else ""

    progress = _current_progress(session_id)
    progress_data = {
        "quiz_scores": progress.get("quiz_scores", []),
        "topics_studied": progress.get("topics_studied", []),
        "weak_areas": progress.get("weak_areas", []),
        "total_queries": progress.get("total_queries", 0),
    }

    # Run the agent pipeline
    try:
        result = run_agent(
            query=query,
            student_profile=student_profile,
            document_text=document_text,
            progress_data=progress_data,
            action_override=action_override,
        )
    except EnvironmentError as exc:
        return jsonify({"error": str(exc)}), 503
    except RateLimitError:
        return jsonify({
            "error": (
                "⏳ The AI is receiving too many requests right now (free-tier rate limit). "
                "Please wait 10–15 seconds and try again."
            )
        }), 429
    except BadRequestError as exc:
        logger.error("Groq bad request: %s", exc)
        return jsonify({"error": f"Request error: {exc}"}), 400
    except Exception as exc:
        logger.exception("Agent error: %s", exc)
        return jsonify({"error": "An internal error occurred. Please try again."}), 500

    # Update progress
    progress["total_queries"] = progress.get("total_queries", 0) + 1
    if result.get("topics"):
        existing = set(progress.get("topics_studied", []))
        existing.update(result["topics"])
        progress["topics_studied"] = list(existing)[:50]

    return jsonify({
        "session_id": session_id,
        "intent": result["intent"],
        "response": result["response"],
        "topics": result.get("topics", []),
        "docs_in_context": len(docs),
    })


# ---------------------------------------------------------------------------
# POST /api/quiz-score — record a quiz score
# ---------------------------------------------------------------------------
@app.route("/api/quiz-score", methods=["POST"])
def record_quiz_score():
    data = request.get_json(silent=True) or {}
    session_id = _get_or_create_session(data.get("session_id"))

    score = data.get("score")
    total = data.get("total")
    topic = sanitise_text(str(data.get("topic", "General")), 100)

    if score is None or total is None:
        return jsonify({"error": "score and total are required"}), 400

    try:
        score = int(score)
        total = int(total)
    except (ValueError, TypeError):
        return jsonify({"error": "score and total must be integers"}), 400

    progress = _current_progress(session_id)
    progress["quiz_scores"].append({
        "score": score,
        "total": total,
        "topic": topic,
        "percentage": round(score / total * 100, 1) if total > 0 else 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Mark as weak if below 60%
    if total > 0 and score / total < 0.6:
        weak = set(progress.get("weak_areas", []))
        weak.add(topic)
        progress["weak_areas"] = list(weak)

    logger.info("Quiz score recorded: %d/%d (%s) for session %s", score, total, topic, session_id)
    return jsonify({"status": "recorded", "session_id": session_id})


# ---------------------------------------------------------------------------
# GET /api/progress — get progress dashboard data
# ---------------------------------------------------------------------------
@app.route("/api/progress", methods=["GET"])
def get_progress():
    session_id = _get_or_create_session(request.args.get("session_id"))
    progress = _current_progress(session_id)

    quiz_scores = progress.get("quiz_scores", [])
    avg_score = (
        round(sum(q["percentage"] for q in quiz_scores) / len(quiz_scores), 1)
        if quiz_scores else None
    )

    return jsonify({
        "session_id": session_id,
        "total_queries": progress.get("total_queries", 0),
        "topics_studied": progress.get("topics_studied", []),
        "weak_areas": progress.get("weak_areas", []),
        "quiz_scores": quiz_scores[-20:],   # last 20 scores
        "average_score": avg_score,
        "milestones": progress.get("milestones", []),
        "docs_uploaded": len(_session_docs.get(session_id, [])),
        "session_start": progress.get("session_start"),
    })


# ---------------------------------------------------------------------------
# POST /api/clear-session — reset session data
# ---------------------------------------------------------------------------
@app.route("/api/clear-session", methods=["POST"])
def clear_session():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if session_id:
        _progress_store.pop(session_id, None)
        _session_docs.pop(session_id, None)
    return jsonify({"status": "cleared"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info("Starting Smart Study Agent backend on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=debug)
