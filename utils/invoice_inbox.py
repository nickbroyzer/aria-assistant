"""Invoice inbox polling, email parsing, and background poller thread."""

import base64
import imaplib
import io
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from email.header import decode_header
from email import message_from_bytes

import pdfplumber

from utils.config import load_config, _integ_val
from utils.data import load_jobs, load_invoice_inbox, save_invoice_inbox
from utils.email import send_invoice_notification


def _parse_amount(text):
    """Extract the largest dollar amount from a string."""
    matches = re.findall(r'\$?([\d,]+\.?\d{0,2})', text)
    amounts = []
    for m in matches:
        try:
            amounts.append(float(m.replace(',', '')))
        except:
            pass
    return max(amounts) if amounts else 0.0


def _parse_invoice_number(text):
    """Try to extract an invoice number from text."""
    patterns = [
        r'invoice\s*#?\s*:?\s*([A-Z0-9\-]{4,20})',
        r'inv\s*#?\s*:?\s*([A-Z0-9\-]{4,20})',
        r'#\s*([A-Z0-9\-]{4,20})',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _parse_date(text):
    """Try to extract a date from text, return YYYY-MM-DD."""
    patterns = [
        r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'(\w+ \d{1,2},?\s*\d{4})',
        r'(\d{4}[\/\-]\d{2}[\/\-]\d{2})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            raw = m.group(1)
            for fmt in ('%m/%d/%Y','%m-%d-%Y','%B %d, %Y','%B %d %Y','%Y-%m-%d','%m/%d/%y'):
                try:
                    return datetime.strptime(raw.strip(), fmt).strftime('%Y-%m-%d')
                except:
                    pass
    return datetime.now().strftime('%Y-%m-%d')


def _parse_pdf_text(pdf_bytes):
    """Extract text from PDF bytes using pdfplumber."""
    try:
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return text
    except Exception as e:
        print(f"PDF parse error: {e}")
        return ""


def _categorize_from_text(text):
    """Guess category from invoice text."""
    t = text.lower()
    if any(w in t for w in ['electric','wiring','conduit','panel','lighting']):
        return 'Labor & Subs'
    if any(w in t for w in ['rental','rent','lift','crane','equipment']):
        return 'Equipment'
    if any(w in t for w in ['permit','inspection','plan check','fee','city of','county']):
        return 'Permits'
    if any(w in t for w in ['concrete','steel','lumber','supply','materials','hardware','fastener']):
        return 'Materials'
    if any(w in t for w in ['labor','install','crew','subcontract','framing','welding']):
        return 'Labor & Subs'
    return 'Other'


def _match_job_from_text(text):
    """Try to match a job number from invoice text."""
    m = re.search(r'JOB-(\d{4}-\d{3})', text, re.IGNORECASE)
    if m:
        job_num = m.group(0).upper()
        jobs = load_jobs()
        job = next((j for j in jobs if j.get('job_number','').upper() == job_num), None)
        if job:
            return job
    return None


def poll_invoice_inbox():
    """
    Check the designated invoice inbox (IMAP) for new emails with attachments.
    Creates draft cost records in 'pending_review' status for each invoice found.
    """
    inbox_email = _integ_val("INVOICE_INBOX_EMAIL") or _integ_val("GMAIL_SENDER")
    inbox_pw    = _integ_val("INVOICE_INBOX_PASSWORD") or _integ_val("GMAIL_APP_PASSWORD")
    if not inbox_email or not inbox_pw:
        print("Invoice poller: no inbox credentials configured")
        return 0

    processed = load_invoice_inbox()
    seen_ids   = {r["email_message_id"] for r in processed}
    new_items  = []

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(inbox_email, inbox_pw)
        mail.select("INBOX")

        # Search for emails with subject hints or just all unseen
        _, msg_nums = mail.search(None, 'UNSEEN')
        ids = msg_nums[0].split()
        print(f"Invoice poller: {len(ids)} unseen emails")

        for num in ids:
            _, data = mail.fetch(num, "(RFC822)")
            raw = data[0][1]
            msg = message_from_bytes(raw)

            msg_id   = msg.get("Message-ID", f"<{uuid.uuid4()}>")
            if msg_id in seen_ids:
                continue

            # Decode subject + sender
            subj_raw = msg.get("Subject", "")
            subj_parts = decode_header(subj_raw)
            subject = " ".join(
                p.decode(enc or "utf-8") if isinstance(p, bytes) else p
                for p, enc in subj_parts
            )
            sender_raw = msg.get("From", "")
            vendor_name = sender_raw.split("<")[0].strip().strip('"') or sender_raw

            # Only process if it looks like an invoice
            invoice_keywords = ["invoice","bill","statement","receipt","payment due","amount due","inv #","inv#"]
            subject_lower = subject.lower()
            body_text = ""
            pdf_bytes  = None
            has_invoice_hint = any(k in subject_lower for k in invoice_keywords)

            # Walk MIME parts
            for part in msg.walk():
                ct   = part.get_content_type()
                disp = str(part.get("Content-Disposition", ""))
                if ct == "text/plain":
                    try: body_text += part.get_payload(decode=True).decode(errors="replace")
                    except: pass
                if ct == "text/html" and not body_text:
                    try:
                        html = part.get_payload(decode=True).decode(errors="replace")
                        body_text += re.sub(r'<[^>]+>', ' ', html)
                    except: pass
                if ct == "application/pdf" or (disp and "attach" in disp and ".pdf" in disp.lower()):
                    pdf_bytes = part.get_payload(decode=True)
                    has_invoice_hint = True

            if not has_invoice_hint:
                # Mark as seen but skip — not an invoice
                mail.store(num, '+FLAGS', '\\Seen')
                processed.append({"email_message_id": msg_id, "skipped": True, "subject": subject})
                continue

            # Parse text
            full_text = body_text
            if pdf_bytes:
                full_text += "\n" + _parse_pdf_text(pdf_bytes)

            amount      = _parse_amount(full_text)
            inv_number  = _parse_invoice_number(full_text)
            inv_date    = _parse_date(full_text)
            category    = _categorize_from_text(full_text)
            matched_job = _match_job_from_text(full_text)

            item = {
                "inbox_id":          str(uuid.uuid4()),
                "email_message_id":  msg_id,
                "received_at":       datetime.now(timezone.utc).isoformat(),
                "subject":           subject,
                "vendor_name":       vendor_name,
                "vendor_email":      sender_raw,
                "invoice_ref":       inv_number,
                "date":              inv_date,
                "amount":            round(amount, 2),
                "category":          category,
                "job_id":            matched_job["job_id"] if matched_job else "",
                "job_number":        matched_job["job_number"] if matched_job else "",
                "client_name":       matched_job.get("client_name","") if matched_job else "",
                "description":       subject[:120],
                "parsed_text":       full_text[:2000],
                "has_pdf":           bool(pdf_bytes),
                "status":            "pending_review",
                "reviewed_by":       None,
                "cost_id":           None,  # filled when approved
                "skipped":           False,
            }
            new_items.append(item)
            processed.append(item)
            seen_ids.add(msg_id)

            # Mark as read
            mail.store(num, '+FLAGS', '\\Seen')

        mail.logout()

    except Exception as e:
        print(f"Invoice inbox poll error: {e}")
        return 0

    if new_items:
        save_invoice_inbox(processed)
        for item in new_items:
            if not item.get("skipped"):
                send_invoice_notification(item)
        print(f"Invoice poller: {len(new_items)} new invoices queued for review")

    return len(new_items)


def _start_invoice_poller():
    """Background thread that polls the invoice inbox every 30 minutes."""
    def _loop():
        while True:
            time.sleep(1800)
            try:
                poll_invoice_inbox()
            except Exception as e:
                print(f"Invoice poller error: {e}")
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
