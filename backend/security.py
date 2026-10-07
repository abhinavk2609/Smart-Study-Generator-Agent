"""
Security middleware for Smart Study Agent.
- Rate limiting per IP (requests/minute)
- Auto IP-block after 5 suspicious attempts
- Security headers on every response
- Request size enforcement
- Attack pattern detection
"""

import logging
import time
from collections import defaultdict
from threading import Lock
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RATE_LIMIT_REQUESTS   = 30        # max requests per window per IP
RATE_LIMIT_WINDOW     = 60        # seconds
BLOCK_THRESHOLD       = 5         # suspicious strikes before permanent block
BLOCK_DURATION        = 600       # seconds IP stays blocked (10 min)
MAX_BODY_SIZE         = 1_000_000 # 1 MB max request body

# ---------------------------------------------------------------------------
# In-memory stores  (replace with Redis for multi-process production)
# ---------------------------------------------------------------------------
_lock          = Lock()
_rate_buckets  = defaultdict(list)   # ip → [timestamps]
_strike_counts = defaultdict(int)    # ip → strike count
_blocked_until = {}                  # ip → unblock_timestamp

# ---------------------------------------------------------------------------
# Attack signatures (beyond guardrails.py prompt checks)
# ---------------------------------------------------------------------------
_ATTACK_PATHS = {
    "/admin", "/phpmyadmin", "/.env", "/wp-admin", "/wp-login.php",
    "/config", "/backup", "/.git", "/shell", "/cmd", "/eval",
    "/etc/passwd", "/proc/self", "/actuator", "/.aws",
}

_SUSPICIOUS_UA_FRAGMENTS = [
    "sqlmap", "nikto", "nmap", "masscan", "zgrab",
    "dirbuster", "gobuster", "hydra", "burpsuite", "metasploit",
]

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _get_ip() -> str:
    """Get real client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _is_blocked(ip: str) -> bool:
    until = _blocked_until.get(ip)
    if until is None:
        return False
    if time.time() < until:
        return True
    # Block expired — clean up
    del _blocked_until[ip]
    _strike_counts[ip] = 0
    return False


def _block_ip(ip: str, reason: str):
    until = time.time() + BLOCK_DURATION
    _blocked_until[ip] = until
    logger.warning("🔴 IP BLOCKED: %s | Reason: %s | Until: %.0f", ip, reason, until)


def _add_strike(ip: str, reason: str):
    _strike_counts[ip] += 1
    count = _strike_counts[ip]
    logger.warning("⚠️  Strike %d/5 for IP %s | Reason: %s", count, ip, reason)
    if count >= BLOCK_THRESHOLD:
        _block_ip(ip, f"Exceeded {BLOCK_THRESHOLD} strikes ({reason})")


def _check_rate_limit(ip: str) -> bool:
    """Returns True if the IP is within rate limit, False if exceeded."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    with _lock:
        # Keep only timestamps within the current window
        _rate_buckets[ip] = [t for t in _rate_buckets[ip] if t > window_start]
        if len(_rate_buckets[ip]) >= RATE_LIMIT_REQUESTS:
            return False
        _rate_buckets[ip].append(now)
        return True


def _check_suspicious_ua(ua: str) -> bool:
    """Returns True if user-agent looks like a scanner/attack tool."""
    ua_lower = ua.lower()
    return any(frag in ua_lower for frag in _SUSPICIOUS_UA_FRAGMENTS)


def _check_attack_path(path: str) -> bool:
    """Returns True if path matches known attack probe patterns."""
    path_lower = path.lower()
    return any(path_lower.startswith(p) or p in path_lower for p in _ATTACK_PATHS)


# ---------------------------------------------------------------------------
# Flask before_request hook — call this from app.py
# ---------------------------------------------------------------------------

def security_check():
    """
    Run before every request. Returns a Flask response on block/reject,
    or None to allow the request through.
    """
    ip = _get_ip()
    g.client_ip = ip  # store for logging

    # 1 — Already blocked?
    with _lock:
        blocked = _is_blocked(ip)
    if blocked:
        remaining = int(_blocked_until.get(ip, 0) - time.time())
        logger.warning("🔴 Blocked IP attempted access: %s", ip)
        return jsonify({
            "error": f"Your IP has been temporarily blocked due to suspicious activity. "
                     f"Try again in {remaining // 60} min {remaining % 60} sec."
        }), 403

    # 2 — Attack path probe?
    if _check_attack_path(request.path):
        with _lock:
            _add_strike(ip, f"attack path probe: {request.path}")
        return jsonify({"error": "Not found."}), 404

    # 3 — Suspicious User-Agent?
    ua = request.headers.get("User-Agent", "")
    if _check_suspicious_ua(ua):
        with _lock:
            _add_strike(ip, f"scanner UA: {ua[:60]}")
        return jsonify({"error": "Forbidden."}), 403

    # 4 — Request body too large?
    content_length = request.content_length or 0
    if content_length > MAX_BODY_SIZE:
        with _lock:
            _add_strike(ip, f"oversized body: {content_length} bytes")
        return jsonify({"error": "Request too large."}), 413

    # 5 — Rate limit?
    with _lock:
        allowed = _check_rate_limit(ip)
    if not allowed:
        with _lock:
            _add_strike(ip, "rate limit exceeded")
        return jsonify({
            "error": "Too many requests. Please slow down and try again in a minute."
        }), 429

    return None  # all clear


# ---------------------------------------------------------------------------
# Flask after_request hook — security headers on every response
# ---------------------------------------------------------------------------

def add_security_headers(response):
    """Add hardening headers to every response."""
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]          = "DENY"
    response.headers["X-XSS-Protection"]         = "1; mode=block"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"]   = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # Remove server fingerprint
    response.headers.pop("Server", None)
    return response


# ---------------------------------------------------------------------------
# Admin: blocked IPs status (internal use only)
# ---------------------------------------------------------------------------

def get_security_status() -> dict:
    now = time.time()
    with _lock:
        blocked = {
            ip: {"blocked_until": int(t), "seconds_remaining": int(t - now)}
            for ip, t in _blocked_until.items() if t > now
        }
        strikes = {ip: c for ip, c in _strike_counts.items() if c > 0}
    return {
        "blocked_ips": blocked,
        "strike_counts": strikes,
        "rate_limit": f"{RATE_LIMIT_REQUESTS} req/{RATE_LIMIT_WINDOW}s",
        "block_threshold": BLOCK_THRESHOLD,
        "block_duration_seconds": BLOCK_DURATION,
    }
