"""
Visitor memory and returning-customer session management.
"""

import json
import os
from datetime import datetime, timezone

from utils.constants import MEMORY_FILE, USER_SESSIONS_FILE
from utils.file_locks import file_lock


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with file_lock(MEMORY_FILE):
            with open(MEMORY_FILE) as f:
                return json.load(f)
    return {}


def save_memory(data):
    with file_lock(MEMORY_FILE):
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f)


def load_user_sessions():
    if os.path.exists(USER_SESSIONS_FILE):
        with file_lock(USER_SESSIONS_FILE):
            with open(USER_SESSIONS_FILE) as f:
                return json.load(f)
    return {}


def save_user_sessions(data):
    with file_lock(USER_SESSIONS_FILE):
        with open(USER_SESSIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)


def get_user_memory(name: str) -> dict:
    sessions = load_user_sessions()
    return sessions.get(name.lower().strip(), {})


def update_user_memory(name: str, facts: dict):
    sessions = load_user_sessions()
    key = name.lower().strip()
    existing = sessions.get(key, {})
    existing.update({k: v for k, v in facts.items() if v})
    existing["sessions"] = existing.get("sessions", 0) + 1
    existing["last_seen"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sessions[key] = existing
    save_user_sessions(sessions)
