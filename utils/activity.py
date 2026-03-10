"""
Activity logging for the dashboard audit trail.
"""

import json
import os
import uuid
from datetime import datetime, timezone

from flask import session

from utils.constants import ACTIVITY_FILE
from utils.file_locks import file_lock
from utils.auth import get_current_user


def log_activity(action: str, description: str, meta: dict = None):
    """Append a timestamped activity event to the activity log."""
    user = get_current_user()
    if user:
        actor = user.get("name") or user.get("username") or "Unknown"
    elif session.get("user_id") == "owner-jay":
        actor = "Jay"
    else:
        actor = "System"
    entry = {
        "id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "description": description,
        "actor": actor,
        "meta": meta or {}
    }
    try:
        with file_lock(ACTIVITY_FILE):
            with open(ACTIVITY_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def load_activity(limit=50):
    """Load the most recent activity entries."""
    if not os.path.exists(ACTIVITY_FILE):
        return []
    entries = []
    try:
        with file_lock(ACTIVITY_FILE):
            with open(ACTIVITY_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            pass
    except Exception:
        pass
    entries.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return entries[:limit]
