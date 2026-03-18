"""
Retell AI API client — pulls call data directly instead of relying on webhooks.

Functions:
    get_recent_calls(limit)  → list of cleaned call dicts
    get_call_detail(call_id) → full call dict or None
"""

import os
import time

import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY", "")
BASE_URL = "https://api.retellai.com/v2"

# Simple module-level cache: {"data": [...], "ts": float}
_calls_cache = {"data": [], "ts": 0.0}
_CACHE_TTL = 60  # seconds


def _headers():
    return {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json",
    }


def get_recent_calls(limit=10):
    """Fetch recent calls from Retell API. Cached for 60 seconds."""
    now = time.time()
    if _calls_cache["data"] and (now - _calls_cache["ts"]) < _CACHE_TTL:
        return _calls_cache["data"][:limit]

    try:
        resp = requests.post(
            f"{BASE_URL}/list-calls",
            headers=_headers(),
            json={"limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()
    except Exception:
        return []

    calls = []
    for c in raw:
        duration_ms = c.get("duration_ms")
        calls.append({
            "call_id": c.get("call_id"),
            "phone_number": c.get("from_number"),
            "duration_seconds": round(duration_ms / 1000) if duration_ms else None,
            "start_timestamp": c.get("start_timestamp"),
            "transcript": c.get("transcript"),
            "call_status": c.get("call_status"),
            "disconnection_reason": c.get("disconnection_reason"),
        })

    _calls_cache["data"] = calls
    _calls_cache["ts"] = now
    return calls[:limit]


def get_call_detail(call_id):
    """Fetch full detail for a single call, including transcript_object."""
    try:
        resp = requests.get(
            f"{BASE_URL}/get-call/{call_id}",
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None
