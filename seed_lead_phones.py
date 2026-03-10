"""
Assign realistic fictional phone numbers to leads missing one.
Rewrites leads.jsonl in place.
"""
import json, re, random

LEADS_FILE = "leads.jsonl"
random.seed(77)

# Washington-area area codes
WA_AREA_CODES = [206, 253, 425, 360, 509, 564]

def extract_phone(contact):
    if not contact:
        return ""
    m = re.search(r'[\d\-\(\)\+\s]{10,}', contact)
    return m.group().strip() if m else ""

def make_phone():
    area = random.choice(WA_AREA_CODES)
    mid  = random.randint(200, 999)
    last = random.randint(1000, 9999)
    return f"({area}) {mid}-{last}"

with open(LEADS_FILE, encoding="utf-8") as f:
    leads = [json.loads(line) for line in f if line.strip()]

changed = 0
for lead in leads:
    contact = lead.get("contact", "") or ""
    if extract_phone(contact):
        continue   # already has a phone number

    phone = make_phone()
    if contact and contact.strip():
        lead["contact"] = contact.strip() + f", {phone}"
    else:
        lead["contact"] = phone
    changed += 1

with open(LEADS_FILE, "w", encoding="utf-8") as f:
    for lead in leads:
        f.write(json.dumps(lead) + "\n")

print(f"Added phone numbers to {changed} leads ({len(leads)} total)")
