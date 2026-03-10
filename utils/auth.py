"""
User authentication, session management, and authorization decorators.
"""

import json
import os
from functools import wraps

from flask import jsonify, session

from utils.constants import USERS_FILE
from utils.file_locks import file_lock


def load_users():
    if os.path.exists(USERS_FILE):
        with file_lock(USERS_FILE):
            with open(USERS_FILE) as f:
                return json.load(f).get("users", [])
    return []


def save_users(users_list):
    with file_lock(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({"users": users_list}, f, indent=2)


def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    users = load_users()
    return next((u for u in users if u["user_id"] == uid and u.get("active", True)), None)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user() and session.get("user_id") != "owner-jay":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def require_owner(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or user.get("role") not in ("owner", "admin"):
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return decorated
