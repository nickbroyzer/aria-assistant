"""
Seed realistic fictional email communications for all leads.
Writes lead_comms.json.
"""
import json, uuid, random
from datetime import datetime, timezone, timedelta

with open("leads.jsonl") as f:
    leads = [json.loads(l) for l in f if l.strip()]

import re
def extract_email(contact):
    m = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]+', contact or '')
    return m.group() if m else ''

# Skip test/blank leads
SKIP_NAMES = {"test user","test customer","test lead",""}
real_leads = [l for l in leads if (l.get("name","") or "").lower() not in SKIP_NAMES and extract_email(l.get("contact","") or l.get("email",""))]

# Remove duplicate lead_ids (keep first)
seen = set()
unique_leads = []
for l in real_leads:
    lid = l.get("lead_id","")
    if lid and lid not in seen:
        seen.add(lid)
        unique_leads.append(l)

COMPANY_NAME = "Pacific Construction"
SENDER_NAME  = "Jay Mitchell"
SENDER_TITLE = "Project Manager"

# Conversation templates by project type keyword
CONV_SETS = [
    # ── Pallet Racking ──
    {
        "keyword": ["rack","racking","storage","warehouse"],
        "threads": [
            {
                "subject": "Pallet Racking Quote Request",
                "exchanges": [
                    ("inbound",  "Hi, we're looking to add pallet racking to our warehouse — roughly 8,000 sq ft space. We need high-density storage for palletized goods. Can you give us a ballpark on cost and timeline?"),
                    ("outbound", "Hi {name}, thanks for reaching out! Pallet racking for an 8,000 sq ft space is right in our wheelhouse. Depending on ceiling height and load requirements, we're typically looking at $35,000–$65,000 installed. I'd love to schedule a site walk to get you an accurate number. Are you free this week or next?"),
                    ("inbound",  "That range works. We're available Thursday afternoon or Friday morning. Friday works best for us — say 10 AM?"),
                    ("outbound", "Perfect — Friday at 10 AM it is. I'll send a calendar invite to this address. Could you share the facility address so I can get our estimator prepped? Also, do you have any existing racking we'd be working around?"),
                    ("inbound",  "Great, address is {company_addr}. No existing racking — it's a clean floor. We'd also like to discuss adding wire decking on all levels."),
                    ("outbound", "Wire decking on all levels is a smart call for forklift safety — we can absolutely spec that in. We'll bring our load-capacity worksheet Friday. See you then!"),
                    ("call",     "Spoke with {name} — confirmed site visit Friday 10 AM. They have a 24-ft clear height, 3 dock doors. Interested in selective racking with wire decking. Budget around $50K. Warm lead."),
                ],
            },
            {
                "subject": "Follow-up: Site Visit Debrief",
                "exchanges": [
                    ("outbound", "Hi {name}, great meeting you on-site Friday. Your facility is a great fit for a selective racking system with 5 levels. I'm putting together the formal proposal now and will have it to you by Wednesday. In the meantime, any questions come up?"),
                    ("inbound",  "Thanks Jay. One question — do you handle the seismic engineering sign-off or do we need to hire someone separately?"),
                    ("outbound", "Great question. We handle everything in-house including the seismic engineering and permit drawings — that's included in our quote. No separate hires needed on your end. Proposal coming Wednesday."),
                ],
            },
        ],
    },
    # ── Dock Equipment ──
    {
        "keyword": ["dock","leveler","loading"],
        "threads": [
            {
                "subject": "Dock Leveler Installation Inquiry",
                "exchanges": [
                    ("inbound",  "We have 4 dock doors that need hydraulic levelers and new dock seals. Current pit depth is 24 inches. Looking for a quote ASAP — our current levelers are failing."),
                    ("outbound", "Hi {name}, sounds urgent — we can prioritize this. Hydraulic levelers with pit work for 4 doors typically runs $18,000–$28,000 depending on leveler capacity and seal type. Can you send photos of the existing pits so we can assess before the site visit?"),
                    ("inbound",  "Photos attached (via email). Two pits are in good shape, two have some cracking on the curb angles."),
                    ("outbound", "Thanks for the photos. The cracking on those two pit edges is something we'll need to address — we'll core out and repair the concrete. Not a showstopper at all. I'll put together a proposal with two options: repair + new levelers, or full pit rebuild. Give me 2 days."),
                    ("call",     "Called {name} to confirm receipt of photos. They're also interested in dock bumpers and restraints for all 4 doors. Noted priority timeline — aiming for 3-week install start."),
                    ("inbound",  "Looking forward to the proposal. Can you also include dock bumpers and restraints in the quote?"),
                    ("outbound", "Absolutely — bumpers and restraints will be included as a line item. You'll have the full proposal by Thursday EOD."),
                ],
            },
        ],
    },
    # ── Mezzanine ──
    {
        "keyword": ["mezzanine","mezz","second floor","office above"],
        "threads": [
            {
                "subject": "Structural Mezzanine — New Office Space",
                "exchanges": [
                    ("inbound",  "We're interested in adding a mezzanine over our existing operations floor — roughly 2,000 sq ft of usable office space. Steel structure preferred. What's your typical timeline and cost range?"),
                    ("outbound", "Hi {name}, a 2,000 sq ft structural steel mezzanine is a great investment. Depending on live load requirements and stair configuration, installed cost typically runs $80,000–$140,000. Timeline from permit approval is usually 6–8 weeks. Would a preliminary site visit work this week?"),
                    ("inbound",  "Yes — we're open Tuesday or Wednesday. Wednesday afternoon is ideal."),
                    ("outbound", "Wednesday afternoon confirmed. I'll have our structural estimator along. A few things to prep: clear height from floor to roof structure, any existing utilities that may run through the footprint, and the intended use (office, storage, or mixed)?"),
                    ("inbound",  "Clear height is 28 ft. Some overhead conduit but nothing major. It'll be mixed use — small offices plus storage overflow."),
                    ("outbound", "28 ft gives us great headroom to work with. Mixed use is totally doable — we'll spec the floor loading accordingly. See you Wednesday!"),
                    ("call",     "Post site-visit call with {name}. They loved the proposal concept. Want to include a full stair with handrail and one access gate. Budget approved internally up to $120K. Moving to formal proposal stage."),
                ],
            },
        ],
    },
    # ── Tenant Improvement ──
    {
        "keyword": ["tenant","TI","improvement","build-out","buildout","office"],
        "threads": [
            {
                "subject": "Tenant Improvement — Lease Space Buildout",
                "exchanges": [
                    ("inbound",  "We just signed a 5-year lease on a 12,000 sq ft industrial space and need a full TI build-out — offices, breakroom, electrical upgrades, and HVAC. Who handles permitting?"),
                    ("outbound", "Congratulations on the new space! We handle full TI projects like this regularly. We manage permitting, all trades, and inspections under one contract — no coordination headache for you. Typical range for what you're describing is $45–$95 per sq ft depending on finish level. Can we schedule a walk-through?"),
                    ("inbound",  "That range is helpful. Yes — we can do a walk-through next Monday at 1 PM. Is that doable?"),
                    ("outbound", "Monday at 1 PM works perfectly. Please send the address and I'll confirm the visit. Also, do you have a space plan or architect drawings, or will we be working from scratch?"),
                    ("inbound",  "We have a rough floor plan from the landlord but nothing detailed. We'll need design-build."),
                    ("outbound", "No problem — we offer design-build services and partner with a local architect for permit drawings. We'll bring a full package. See you Monday."),
                    ("note",     "Internally flagged as high-value TI opportunity. 12,000 sq ft at mid-range finish = potential $660K–$780K contract. Prioritize proposal turnaround within 5 business days of walk-through."),
                ],
            },
        ],
    },
    # ── Security Cage ──
    {
        "keyword": ["cage","security","vault","wire","enclosure"],
        "threads": [
            {
                "subject": "Security Cage / Wire Partition Enclosure",
                "exchanges": [
                    ("inbound",  "We need a security cage in our warehouse for high-value inventory — roughly 20x30 ft, 10 ft tall, with a keyed entry gate. Do you fabricate and install?"),
                    ("outbound", "Hi {name}, yes — we design, fabricate, and install wire partition security cages. A 20x30 at 10 ft height typically runs $6,500–$12,000 depending on panel gauge and gate hardware. We can add padlock provisions, anti-climb tops, or card-reader mounting as needed. Want to schedule a quick site visit?"),
                    ("inbound",  "Perfect. Let's do a site visit — Thursday morning works. Can you bring samples of the panel mesh options?"),
                    ("outbound", "Thursday morning it is! I'll bring our sample panel kit — we offer 10-gauge and 12-gauge welded wire with several mesh opening sizes. I'll also bring photos of recent installs for reference. What time Thursday works best?"),
                    ("inbound",  "9 AM works great."),
                    ("outbound", "See you at 9 AM Thursday. Text me when you're at the facility and I'll meet you at the main entrance: {name} at {company}."),
                ],
            },
        ],
    },
    # ── General / cold lead ──
    {
        "keyword": [],
        "threads": [
            {
                "subject": "Initial Project Inquiry",
                "exchanges": [
                    ("inbound",  "Hi, came across your company online. We have a warehouse project we're trying to get off the ground and wanted to get a quote. Can you help?"),
                    ("outbound", "Hi {name}, thanks for reaching out to Pacific Construction! We'd love to learn more about your project. Could you share a bit more about what you're working on — scope, timeline, and facility location? That'll help us figure out the best way to help."),
                    ("inbound",  "Sure — we're looking at adding storage capacity to our existing facility. Haven't pinned down the exact approach yet but budget is probably $30–$50K."),
                    ("outbound", "That budget is very workable. There are a few directions we could go — pallet racking, a small mezzanine, or shelving systems. Each has pros and cons depending on your SKU mix and workflow. I'd suggest a free 30-minute site visit so I can see the space and give you an educated recommendation. Does that sound reasonable?"),
                    ("call",     "Initial call with {name} at {company}. Friendly conversation — they're early in the process. No specific timeline. Will send a follow-up email with our portfolio and project examples to keep them warm."),
                    ("outbound", "Hi {name}, great chatting earlier! I've attached a few project examples from similar facilities we've outfitted. When you're ready to move forward on that site visit, just reply here or call me directly at 253.826.2727. Looking forward to helping you maximize that space."),
                ],
            },
        ],
    },
]

def pick_conv(lead):
    details = (lead.get("project_details","") or "").lower()
    company = (lead.get("company","") or "").lower()
    combined = details + " " + company
    for cs in CONV_SETS[:-1]:
        if any(kw in combined for kw in cs["keyword"]):
            return cs
    return CONV_SETS[-1]   # fallback: general

def make_comms(lead, base_dt):
    name    = lead.get("name","") or "there"
    company = lead.get("company","") or "your company"
    cs = pick_conv(lead)
    comms = []
    t = base_dt
    for thread in cs["threads"]:
        subj = thread["subject"]
        for direction, body_tmpl in thread["exchanges"]:
            body = body_tmpl.format(
                name=name.split()[0],
                company=company,
                company_addr=f"123 Industrial Blvd, {lead.get('location','Seattle, WA')}",
            )
            # direction in (inbound/outbound/call/note) → map to type
            if direction == "call":
                comm_type, comm_dir = "call", "internal"
            elif direction == "note":
                comm_type, comm_dir = "note", "internal"
            elif direction == "inbound":
                comm_type, comm_dir = "email", "inbound"
            else:
                comm_type, comm_dir = "email", "outbound"

            sent_by = name.split()[0] if comm_dir == "inbound" else (SENDER_NAME if comm_type in ("email","outbound") else SENDER_NAME)
            if comm_dir == "internal":
                sent_by = SENDER_NAME

            comms.append({
                "comm_id":   str(uuid.uuid4()),
                "lead_id":   lead["lead_id"],
                "type":      comm_type,
                "direction": comm_dir,
                "subject":   subj,
                "body":      body,
                "sent_by":   sent_by,
                "timestamp": t.isoformat(),
            })
            # Advance time realistically
            if comm_type == "call":
                t += timedelta(hours=random.randint(1,6))
            elif comm_dir == "inbound":
                t += timedelta(hours=random.randint(2,28))
            else:
                t += timedelta(hours=random.randint(1,24))
        # Gap between threads
        t += timedelta(days=random.randint(1,4))
    return comms

random.seed(99)
all_comms = []

for lead in unique_leads:
    lid = lead.get("lead_id","")
    # Pick a random start date 30–90 days in the past
    days_ago = random.randint(14, 75)
    base_dt  = datetime.now(timezone.utc) - timedelta(days=days_ago)
    comms = make_comms(lead, base_dt)
    all_comms.extend(comms)
    print(f"  {lead.get('name','?'):<22} → {len(comms)} entries")

with open("lead_comms.json","w") as f:
    json.dump(all_comms, f, indent=2)

print(f"\nTotal: {len(all_comms)} communication entries across {len(unique_leads)} leads")
