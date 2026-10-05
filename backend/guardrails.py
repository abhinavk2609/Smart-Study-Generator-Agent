"""
Guardrails — input sanitisation, prompt-injection protection, and output safety.
All user input and uploaded file content is treated as untrusted.
"""

import re
import html
import unicodedata
from typing import Any


# ---------------------------------------------------------------------------
# Blocked patterns — phrases that attempt to override system instructions,
# extract the API key, or inject adversarial prompts.
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore (all |previous |above |prior )?instructions?", re.I),
    re.compile(r"disregard (your |all |the )?(previous |prior |system )?instructions?", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"act as (a |an )?(?!student|tutor|teacher)", re.I),
    re.compile(r"(reveal|show|print|output|tell me|what is|give me).*?(api[_ ]?key|secret|password|token)", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN mode", re.I),
    re.compile(r"override (safety|guardrail|filter)", re.I),
    re.compile(r"pretend (you are|to be)", re.I),
    re.compile(r"forget (your |all |previous )?instructions?", re.I),
    re.compile(r"<\s*(script|iframe|object|embed|form)", re.I),   # HTML injection
    re.compile(r"(eval|exec|__import__|os\.system)\s*\(", re.I),   # code injection
]

# Maximum sizes
MAX_TEXT_INPUT_CHARS = 20_000
MAX_FILENAME_CHARS = 255
MAX_STUDENT_FIELD_CHARS = 500


def sanitise_text(text: str, max_chars: int = MAX_TEXT_INPUT_CHARS) -> str:
    """Strip control characters, normalise unicode, escape HTML, and truncate."""
    if not isinstance(text, str):
        return ""
    # Normalise unicode to NFC
    text = unicodedata.normalize("NFC", text)
    # Remove non-printable control characters (but keep newlines / tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Escape HTML special characters to prevent XSS if echoed back
    text = html.escape(text, quote=True)
    return text[:max_chars]


def check_prompt_injection(text: str) -> tuple[bool, str]:
    """
    Returns (is_safe, reason).
    If is_safe is False, the request should be rejected.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return False, f"Blocked: potentially unsafe input detected (pattern: {pattern.pattern[:40]})"
    return True, "ok"


def sanitise_student_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Sanitise all string fields in the student profile dict."""
    safe = {}
    allowed_keys = {
        "name", "course", "subjects", "learning_preference",
        "study_hours_per_day", "syllabus", "exam_date", "weak_areas",
    }
    for key in allowed_keys:
        value = profile.get(key, "")
        if isinstance(value, (int, float)):
            safe[key] = value
        else:
            safe[key] = sanitise_text(str(value), MAX_STUDENT_FIELD_CHARS)
    return safe


def sanitise_filename(filename: str) -> str:
    """Return a safe filename with only alphanumerics, dots, dashes, underscores."""
    filename = os.path.basename(filename) if "\\" in filename or "/" in filename else filename
    filename = re.sub(r"[^\w.\-]", "_", filename)
    return filename[:MAX_FILENAME_CHARS]


def validate_uploaded_file(filename: str, content_bytes: bytes) -> tuple[bool, str]:
    """
    Basic validation of uploaded file.
    Returns (is_valid, reason).
    """
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

    if len(content_bytes) == 0:
        return False, "Uploaded file is empty."
    if len(content_bytes) > MAX_FILE_SIZE:
        return False, f"File exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)} MB."

    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".md"}
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        return False, f"File type '{ext}' is not supported. Allowed: {', '.join(allowed_extensions)}"

    return True, "ok"


def wrap_ai_disclaimer(text: str) -> str:
    """Append a standard AI-generated content disclaimer."""
    disclaimer = (
        "\n\n---\n"
        "⚠️ **AI-Generated Content**: This material was created by an AI model. "
        "Please verify important academic information with your teacher, textbook, "
        "or official curriculum sources before relying on it for exams."
    )
    return text + disclaimer


def safe_system_prompt_addition(user_text: str) -> str:
    """
    Wrap user-supplied text for inclusion in a system/user prompt such that it
    cannot break out of its designated role even if injection is attempted.
    """
    return f"[BEGIN USER-PROVIDED CONTENT]\n{user_text}\n[END USER-PROVIDED CONTENT]"


# Import os here (used in sanitise_filename) — kept at bottom to avoid circular issues
import os  # noqa: E402
