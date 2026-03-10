"""
Routes package for Ash (Pacific Construction Assistant).

Each module defines a Flask Blueprint. Register them all via register_blueprints().
"""

from routes.chat import chat_bp
from routes.dashboard import dashboard_bp
from routes.invoices import invoices_bp
from routes.jobs import jobs_bp
from routes.leads import leads_bp
from routes.payroll import payroll_bp

ALL_BLUEPRINTS = [
    chat_bp,
    dashboard_bp,
    invoices_bp,
    jobs_bp,
    leads_bp,
    payroll_bp,
]


def register_blueprints(app):
    """Register all route blueprints with the Flask app."""
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
