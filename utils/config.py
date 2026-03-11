"""
Configuration management: load/save config.json, tax rate, integration credentials.
"""

import json
import os

from werkzeug.security import check_password_hash

from utils.constants import CONFIG_FILE, DEV_PASSWORD_DEFAULT
from utils.file_locks import file_lock


def load_config():
    if os.path.exists(CONFIG_FILE):
        with file_lock(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                return json.load(f)
    return {"comp_pin": "1234", "comp_pin_changed": ""}


def save_config(data):
    with file_lock(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)


def get_tax_rate():
    """Read tax rate from config (stored as percentage, e.g. 10.2), return as decimal."""
    cfg = load_config()
    return cfg.get("company", {}).get("tax_rate", 10.2) / 100


def safe_float(val, default=0.0):
    """Convert val to float, returning default on failure. Use for all user input."""
    try:
        return float(val) if val is not None and val != "" else default
    except (ValueError, TypeError):
        return default


def _integ_val(key):
    """Return integration credential: config.json overrides .env."""
    cfg = load_config().get("integrations", {})
    return cfg.get(key) or os.getenv(key, "")


def _check_dev_password(password):
    """Return True if password matches the stored dev password (or default)."""
    cfg = load_config()
    stored_hash = cfg.get("dev_password_hash")
    if stored_hash:
        return check_password_hash(stored_hash, password)
    return password == DEV_PASSWORD_DEFAULT
