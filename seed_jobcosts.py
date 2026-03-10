"""
Seed realistic job cost records for all active jobs.
Each job gets multiple cost entries across relevant categories.
"""
import json, uuid, random
from datetime import date, timedelta

with open('jobs.json') as f: jobs = json.load(f)
active = [j for j in jobs if j.get('status') == 'active']

TODAY = date(2026, 3, 8)

# Vendors by category
VENDORS = {
    'Materials': [
        'Home Depot Pro', 'Fastenal', 'Pacific Steel & Recycling', 'ABC Supply Co',
        'Grainger Industrial', 'Uline', 'MSC Industrial', 'Graybar Electric',
        'Ferguson Enterprises', 'HD Supply', 'Interline Brands', 'Wesco International',
    ],
    'Labor & Subs': [
        'Pacific Electric LLC', 'Northwest Concrete Inc', 'Cascade Welding Co',
        'Puget Sound Plumbing', 'Olympic Painting & Coating', 'Summit Flooring Co',
        'Rainier Mechanical', 'Sound Drywall & Framing', 'Tacoma Steel Erectors',
        'Auburn Roofing Specialists',
    ],
    'Equipment': [
        'United Rentals', 'Sunbelt Rentals', 'H&E Equipment Services',
        'Herc Rentals', 'RSC Equipment Rental', 'Neff Rental',
    ],
    'Permits': [
        'City of Kent Building Dept', 'City of Auburn Permits',
        'City of Tacoma Development Services', 'King County DPER',
        'Pierce County Planning', 'City of Renton Planning Dept',
        'City of Federal Way Permits', 'WA Labor & Industries',
    ],
    'Other': [
        'Pacific Waste Services', 'Shred-it', 'Aramark Uniforms',
        'Cintas Corporation', 'Office Depot', 'NAPA Auto Parts',
        'Verizon Business', 'Amazon Business',
    ],
}

DESCRIPTIONS = {
    'Pallet Racking': {
        'Materials':    ['Structural rack uprights & beams', 'Anchor bolts & base plates', 'Row spacers & column guards', 'Wire decking panels', 'Safety netting & rack ends'],
        'Labor & Subs': ['Steel erection crew — rack installation', 'Concrete anchoring labor', 'Site prep & layout crew'],
        'Equipment':    ['Scissor lift rental — 3 days', 'Forklift rental for material staging', 'Boom lift rental — installation'],
        'Permits':      ['Building permit — racking system', 'Seismic engineering review fee'],
        'Other':        ['Debris removal & cleanup', 'Safety signage & labels'],
    },
    'Dock Equipment': {
        'Materials':    ['Dock leveler — hydraulic', 'Dock seals & shelters', 'Dock bumpers & restraints', 'Pit frame & curb angles', 'Hydraulic fluid & hardware'],
        'Labor & Subs': ['Dock installation crew', 'Electrical connection for hydraulics', 'Concrete pit cutting & repair'],
        'Equipment':    ['Concrete saw rental', 'Generator rental — 2 days'],
        'Permits':      ['Building permit — dock modification', 'Electrical permit'],
        'Other':        ['Concrete disposal', 'Touch-up paint & sealant'],
    },
    'Security Cage': {
        'Materials':    ['Welded wire mesh panels', 'Steel framing & posts', 'Gate hardware & locks', 'Padlock & access hardware', 'Concrete anchors'],
        'Labor & Subs': ['Cage fabrication & welding crew', 'Installation labor'],
        'Equipment':    ['Welding equipment rental', 'Scissor lift — 1 day'],
        'Permits':      ['Building permit — cage enclosure'],
        'Other':        ['Scrap steel disposal'],
    },
    'Tenant Improvement': {
        'Materials':    ['Steel stud framing & track', 'Drywall — 5/8" Type X', 'Insulation batts R-19', 'Suspended ceiling grid & tiles', 'Lighting fixtures & hardware', 'HVAC diffusers & ductwork', 'Electrical panels & wiring', 'Plumbing rough-in materials', 'Flooring — polished concrete sealer', 'Door frames, hardware & closers'],
        'Labor & Subs': ['Framing & drywall subcontractor', 'Electrical subcontractor', 'Plumbing subcontractor', 'HVAC subcontractor', 'Painting subcontractor', 'Flooring subcontractor'],
        'Equipment':    ['Scissor lift rental — 2 weeks', 'Dumpster rental — 4 weeks', 'Concrete grinder rental'],
        'Permits':      ['Building permit — TI', 'Electrical permit', 'Mechanical permit', 'Plumbing permit', 'Fire alarm permit'],
        'Other':        ['Temporary power hookup', 'Jobsite portable toilet — monthly', 'Debris hauling & disposal'],
    },
    'Permit Drawings': {
        'Materials':    ['Blueprint printing & binding', 'Plan sets — engineering prints'],
        'Labor & Subs': ['Structural engineer — peer review', 'Civil engineer — site plan'],
        'Equipment':    [],
        'Permits':      ['Plan check fee', 'State review fee'],
        'Other':        ['Courier & submission fees', 'Digital plan submission fee'],
    },
    'ADA Compliance': {
        'Materials':    ['ADA grab bars & hardware', 'Accessible signage', 'Concrete ramp materials', 'Tactile warning strips'],
        'Labor & Subs': ['Concrete contractor — ramp pour', 'Carpentry crew — interior mods'],
        'Equipment':    ['Concrete mixer rental'],
        'Permits':      ['Building permit — ADA upgrade'],
        'Other':        ['Inspection fee', 'Compliance consultant'],
    },
    'Structural Engineering': {
        'Materials':    ['Engineering report printing', 'Site survey materials'],
        'Labor & Subs': ['Geotechnical engineer', 'Survey crew — site assessment'],
        'Equipment':    [],
        'Permits':      ['Engineering stamp fee', 'Plan review fee'],
        'Other':        ['Travel & site visit expenses'],
    },
    'Foundation Design': {
        'Materials':    ['Soil boring materials', 'Report binding & delivery'],
        'Labor & Subs': ['Geotechnical drilling crew', 'Foundation engineer'],
        'Equipment':    ['Drill rig rental — 1 day'],
        'Permits':      ['Design review fee'],
        'Other':        ['Lab testing — soil samples'],
    },
    'As-Built Docs': {
        'Materials':    ['Blueprint printing', 'As-built set binding'],
        'Labor & Subs': ['Survey crew — as-built measurements', 'CAD drafting subcontractor'],
        'Equipment':    [],
        'Permits':      ['Document submission fee'],
        'Other':        ['Digital delivery & archiving'],
    },
    'Mezzanine': {
        'Materials':    ['Structural steel — columns & beams', 'Floor grating or decking panels', 'Stair stringers & hardware', 'Handrail & guardrail system', 'Concrete anchors & base plates'],
        'Labor & Subs': ['Steel erection crew', 'Welding crew — connections', 'Electrical for lighting on mezzanine'],
        'Equipment':    ['Crane rental — steel erection', 'Scissor lift rental — 4 days'],
        'Permits':      ['Building permit — mezzanine', 'Structural engineering stamp'],
        'Other':        ['Steel scrap disposal', 'Safety signage'],
    },
}

def get_descs(job_type, category):
    # Fall back to generic if job type not in map
    d = DESCRIPTIONS.get(job_type, {})
    return d.get(category, [f'{category} supplies', f'{category} services', f'{category} materials'])

def rand_date(start_date_str, spread_days=60):
    try:
        start = date.fromisoformat(start_date_str)
    except:
        start = TODAY - timedelta(days=spread_days)
    earliest = max(start, TODAY - timedelta(days=spread_days))
    latest   = min(TODAY, earliest + timedelta(days=spread_days))
    if latest <= earliest:
        return earliest.isoformat()
    delta = (latest - earliest).days
    return (earliest + timedelta(days=random.randint(0, delta))).isoformat()

costs = []

for job in active:
    jid    = job['job_id']
    jnum   = job['job_number']
    client = job.get('client_name', job.get('client_company', ''))
    jtype  = job.get('job_type', 'General')
    value  = float(job.get('value', 0))
    start  = job.get('start_date', '')

    random.seed(hash(jid) % (2**32))

    # Target cost ratio: 45–65% of job value
    target_cost = value * random.uniform(0.45, 0.65)

    # Decide which categories apply based on job type
    if value < 10000:
        # Small jobs: mostly materials + permits
        cat_weights = {'Materials': 0.45, 'Labor & Subs': 0.25, 'Equipment': 0.05, 'Permits': 0.20, 'Other': 0.05}
    elif value < 50000:
        cat_weights = {'Materials': 0.40, 'Labor & Subs': 0.35, 'Equipment': 0.10, 'Permits': 0.08, 'Other': 0.07}
    else:
        cat_weights = {'Materials': 0.35, 'Labor & Subs': 0.40, 'Equipment': 0.12, 'Permits': 0.06, 'Other': 0.07}

    entries = []
    for cat, weight in cat_weights.items():
        if weight < 0.07 and value < 8000:
            continue
        descs = get_descs(jtype, cat)
        if not descs:
            continue
        cat_budget = target_cost * weight
        vendors    = VENDORS[cat]
        n_entries  = max(1, min(len(descs), int(cat_budget / max(value * 0.04, 200)) + random.randint(1, 2)))
        n_entries  = min(n_entries, len(descs))
        chosen_descs = random.sample(descs, n_entries)
        per = cat_budget / n_entries
        for desc in chosen_descs:
            amount = round(per * random.uniform(0.7, 1.3), 2)
            amount = max(amount, 50.0)
            d = rand_date(start)
            is_paid = date.fromisoformat(d) < TODAY - timedelta(days=10)
            entries.append({
                'cost_id':      str(uuid.uuid4()),
                'job_id':       jid,
                'job_number':   jnum,
                'client_name':  client,
                'vendor':       random.choice(vendors),
                'description':  desc,
                'category':     cat,
                'amount':       amount,
                'date':         d,
                'status':       'paid' if is_paid else 'pending',
                'invoice_ref':  f'INV-{random.randint(10000,99999)}',
                'notes':        '',
                'created_at':   f'2026-{random.randint(1,3):02d}-{random.randint(1,28):02d}T00:00:00+00:00',
            })

    costs.extend(entries)
    total_cost = sum(e['amount'] for e in entries)
    margin = ((value - total_cost) / value * 100) if value else 0
    print(f"{jnum} | {client[:25]:<25} | ${value:>10,.0f} value | ${total_cost:>9,.0f} costs | {margin:.0f}% margin | {len(entries)} entries")

with open('jobcosts.json', 'w') as f:
    json.dump(costs, f, indent=2)

print(f"\nTotal cost records: {len(costs)}")
print(f"Total cost value:  ${sum(c['amount'] for c in costs):,.2f}")
