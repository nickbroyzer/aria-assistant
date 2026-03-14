"""
Ash scanner: Scans Gmail inbox for supplier-related emails and classifies them.

Searches for keywords related to orders, invoices, shipments, and delays,
then attempts to match emails to suppliers and orders in the database.
"""

import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from utils.gmail_auth import get_gmail_service
from utils.suppliers_db import load_suppliers, get_orders


def scan_inbox(max_results=50, days_back=7):
    """
    Scan Gmail inbox for supplier-related emails and classify them.

    Searches for supplier-related keywords over the past N days, extracts
    email details, and attempts to match to suppliers and orders in the DB.

    Args:
        max_results (int): Maximum number of emails to return. Default 50.
        days_back (int): Number of days back to search. Default 7.

    Returns:
        list: List of dicts with keys:
            - message_id: Gmail message ID
            - sender: Sender display name
            - sender_email: Sender email address
            - subject: Email subject
            - date: Email date (ISO format)
            - snippet: Email body snippet
            - email_type: Classified type (invoice, shipment, delay, etc.)
            - matched_supplier_id: Supplier ID if matched, else None
            - matched_supplier_name: Supplier name if matched, else None
            - matched_order_id: Order ID if matched, else None
            - matched_order_ref: Order reference if matched, else None
            - confidence: "high", "medium", or "low"
    """
    service = get_gmail_service()
    if not service:
        return []

    # Calculate date range
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    after_date = cutoff_date.strftime("%Y/%m/%d")

    # Build search query with supplier-related keywords
    keywords = [
        "invoice", "shipment", "delivery",
        "delay", "tracking", "freight",
    ]
    query = f"after:{after_date} ({' OR '.join(keywords)})"

    try:
        results = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = results.get("messages", [])
    except Exception:
        return []

    # Load supplier and order data for matching
    suppliers = load_suppliers()
    all_orders = []
    for supplier in suppliers:
        all_orders.extend(get_orders(supplier["id"]))

    scanned = []
    for msg in messages:
        try:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()

            headers = msg_data["payload"].get("headers", [])
            subject = next(
                (h["value"] for h in headers if h["name"] == "Subject"), ""
            )
            from_header = next(
                (h["value"] for h in headers if h["name"] == "From"), ""
            )
            date_header = next(
                (h["value"] for h in headers if h["name"] == "Date"), ""
            )

            # Parse sender
            sender, sender_email = _parse_from_header(from_header)

            # Get snippet
            snippet = msg_data.get("snippet", "")

            # Classify email type
            email_type = classify_email(subject, snippet)

            # Match supplier
            matched_supplier = match_supplier(sender, sender_email, suppliers)
            matched_supplier_id = (
                matched_supplier["id"] if matched_supplier else None
            )
            matched_supplier_name = (
                matched_supplier["name"] if matched_supplier else None
            )

            # Match order
            matched_order = None
            if matched_supplier_id:
                supplier_orders = get_orders(matched_supplier_id)
                matched_order = match_order(subject, snippet, supplier_orders)

            matched_order_id = matched_order["id"] if matched_order else None
            matched_order_ref = (
                matched_order.get("id", "") if matched_order else None
            )

            # Determine confidence
            confidence = _compute_confidence(
                email_type, matched_supplier, matched_order
            )

            scanned.append({
                "message_id": msg["id"],
                "sender": sender,
                "sender_email": sender_email,
                "subject": subject,
                "date": date_header,
                "snippet": snippet,
                "email_type": email_type,
                "matched_supplier_id": matched_supplier_id,
                "matched_supplier_name": matched_supplier_name,
                "matched_order_id": matched_order_id,
                "matched_order_ref": matched_order_ref,
                "confidence": confidence,
            })
        except Exception:
            continue

    return scanned


def classify_email(subject, snippet):
    """
    Classify email type based on subject and snippet.

    Args:
        subject (str): Email subject line.
        snippet (str): Email body snippet.

    Returns:
        str: Email type: "invoice", "shipment", "delay", "order_confirmation",
             "tracking", or "general".
    """
    text = (subject + " " + snippet).lower()

    if re.search(r"\b(invoice|bill|payment|paid|due)\b", text):
        return "invoice"
    elif re.search(r"\b(shipped|dispatch|sending|sent out)\b", text):
        return "shipment"
    elif re.search(r"\b(delay|delayed|postpone|push|reschedule|late)\b", text):
        return "delay"
    elif re.search(r"\b(order confirm|confirmed|received order|order #)\b", text):
        return "order_confirmation"
    elif re.search(r"\b(track|tracking|status|location|in transit)\b", text):
        return "tracking"
    else:
        return "general"


def match_supplier(sender, sender_email, suppliers):
    """
    Attempt to match sender to a supplier via fuzzy matching.

    Args:
        sender (str): Sender display name.
        sender_email (str): Sender email address.
        suppliers (list): List of supplier dicts from suppliers_db.

    Returns:
        dict: Matched supplier dict, or None if no match.
    """
    if not sender and not sender_email:
        return None

    # Extract domain from email
    email_domain = sender_email.split("@")[1] if "@" in sender_email else ""

    best_match = None
    best_ratio = 0.0

    for supplier in suppliers:
        supplier_name = supplier.get("name", "").lower()
        supplier_email = supplier.get("email", "").lower() if "email" in supplier else ""

        # Check exact domain match
        if email_domain and supplier_email:
            supplier_domain = supplier_email.split("@")[1]
            if supplier_domain == email_domain:
                return supplier

        # Fuzzy match on name
        ratio = SequenceMatcher(None, sender.lower(), supplier_name).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = supplier

    # Return if match is above threshold (60%)
    if best_ratio >= 0.6:
        return best_match

    return None


def match_order(subject, snippet, orders):
    """
    Attempt to match email to an order by finding reference numbers.

    Args:
        subject (str): Email subject line.
        snippet (str): Email body snippet.
        orders (list): List of order dicts from suppliers_db.

    Returns:
        dict: Matched order dict, or None if no match.
    """
    if not orders:
        return None

    text = (subject + " " + snippet).upper()

    for order in orders:
        # Look for order ID in various formats
        order_id = order.get("id", "").upper()
        if order_id and order_id in text:
            return order

        # Look for purchase order number (PO format variations)
        # This is a placeholder — adapt based on your PO numbering scheme
        po_pattern = r"PO[\s-]?(\d+)"
        po_matches = re.findall(po_pattern, text)
        if po_matches:
            # Could enhance this by checking against stored PO numbers
            pass

    return None


def _parse_from_header(from_header):
    """
    Parse an email From header into name and email address.

    Args:
        from_header (str): Raw From header value.

    Returns:
        tuple: (sender_name, sender_email)
    """
    # Format: "Name <email@domain.com>" or "email@domain.com"
    if "<" in from_header and ">" in from_header:
        name = from_header.split("<")[0].strip().strip('"')
        email = from_header.split("<")[1].split(">")[0].strip()
        return (name or email, email)
    else:
        return (from_header.strip(), from_header.strip())


def _compute_confidence(email_type, matched_supplier, matched_order):
    """
    Compute overall confidence score for the scan result.

    Args:
        email_type (str): Classified email type.
        matched_supplier (dict or None): Matched supplier, if any.
        matched_order (dict or None): Matched order, if any.

    Returns:
        str: "high", "medium", or "low".
    """
    score = 0

    # Base score from email type classification
    if email_type != "general":
        score += 2
    else:
        score += 1

    # Score for supplier match
    if matched_supplier:
        score += 2
    else:
        score += 0

    # Score for order match
    if matched_order:
        score += 1

    if score >= 4:
        return "high"
    elif score >= 2:
        return "medium"
    else:
        return "low"
