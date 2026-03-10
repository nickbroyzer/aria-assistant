"""
Assign realistic fictional emails to leads that are missing one.
Rewrites leads.jsonl in place.
"""
import json, re, random

LEADS_FILE = "leads.jsonl"

# Fictional company domains for leads with a known company
COMPANY_DOMAINS = {
    "pacific northwest cold storage": "pnwcoldstorage.com",
    "abc logistics":      "abclogistics.com",
    "abc warehousing":    "abcwarehousing.com",
    "johnson logistics":  "johnsonlogistics.com",
    "loal systems":       "loalsystems.com",
    "pacific construction": "pacificconstruction.com",
}

# Pool of placeholder contacts when name/company give us nothing
PLACEHOLDER_CONTACTS = [
    ("David Rivera",    "drivera",    "cascadewarehouse.com"),
    ("Jennifer Park",   "jpark",      "pacnorthwestlogistics.com"),
    ("Marcus Webb",     "mwebb",      "webdistribution.net"),
    ("Tanya Okafor",    "tokafor",    "okafor-industrial.com"),
    ("Steve Hannigan",  "shannigan",  "hanniganfreight.com"),
    ("Linda Chow",      "lchow",      "chow-supply.com"),
    ("Ray Delgado",     "rdelgado",   "delgado-warehouse.com"),
    ("Carla Nunes",     "cnunes",     "nunescold.com"),
    ("Brett Kowalski",  "bkowalski",  "kowalskiops.com"),
    ("Amy Tran",        "atran",      "tranlogisticsgroup.com"),
]

def extract_email(contact):
    if not contact:
        return ""
    m = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]+', contact)
    return m.group() if m else ""

def make_email(name, company):
    """Generate a plausible email from name + company."""
    parts = name.lower().split()
    if len(parts) >= 2:
        local = f"{parts[0][0]}{parts[-1]}"  # first initial + last name
    elif parts:
        local = parts[0]
    else:
        local = "contact"
    local = re.sub(r'[^a-z0-9]', '', local)

    co_key = (company or "").lower().strip()
    domain = COMPANY_DOMAINS.get(co_key)
    if not domain:
        # derive from company name
        words = re.sub(r'[^a-z0-9 ]', '', co_key).split()
        words = [w for w in words if w not in ('inc','llc','co','corp','the','and')]
        if words:
            domain = "".join(words[:2]) + ".com"
        else:
            domain = "gmail.com"

    return f"{local}@{domain}"

with open(LEADS_FILE, encoding="utf-8") as f:
    leads = [json.loads(line) for line in f if line.strip()]

random.seed(42)
placeholder_pool = list(PLACEHOLDER_CONTACTS)
random.shuffle(placeholder_pool)
placeholder_idx = 0

changed = 0
for lead in leads:
    existing = extract_email(lead.get("contact", "")) or lead.get("email", "")
    if existing:
        # already has email — ensure it's in the contact field legibly
        continue

    name    = (lead.get("name") or "").strip()
    company = (lead.get("company") or "").strip()

    if name and name.lower() not in ("kolya", "test user", "test customer", "test lead", ""):
        email = make_email(name, company)
    else:
        # Use placeholder pool, cycling if needed
        pname, plocal, pdomain = placeholder_pool[placeholder_idx % len(placeholder_pool)]
        placeholder_idx += 1
        email = f"{plocal}@{pdomain}"
        # Also update name/company if totally blank
        if not name or name.lower() in ("kolya", "test user", "test customer", "test lead"):
            lead["name"]    = pname
            lead["company"] = pdomain.split(".")[0].replace("-", " ").title() + " LLC"

    # Write email into contact field (append if contact has phone only)
    contact = lead.get("contact", "")
    if contact and "@" not in contact:
        lead["contact"] = f"{email}, {contact}"
    else:
        lead["contact"] = email
    changed += 1

with open(LEADS_FILE, "w", encoding="utf-8") as f:
    for lead in leads:
        f.write(json.dumps(lead) + "\n")

print(f"Updated {changed} leads with fictional emails ({len(leads)} total)")
