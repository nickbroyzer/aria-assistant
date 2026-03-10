"""
Seed 5-20 projects per architect, mix of past/active/future.
Creates jobs with architect company in subcontractors field,
and pay records linked to each job.
"""
import json, uuid, random
from datetime import date, timedelta

with open('people.json') as f:  people  = json.load(f)
with open('jobs.json')   as f:  jobs    = json.load(f)
with open('payroll.json') as f: payroll = json.load(f)

# ── Year counter ──────────────────────────────────────────────────────────────
year_counters = {}
for j in jobs:
    parts = j['job_number'].split('-')
    yr, num = parts[1], int(parts[2])
    year_counters[yr] = max(year_counters.get(yr, 0), num)

def next_job_number(year):
    yr = str(year)
    year_counters[yr] = year_counters.get(yr, 0) + 1
    return f"JOB-{yr}-{year_counters[yr]:03d}"

TODAY = date(2026, 3, 8)

# ── Clients ───────────────────────────────────────────────────────────────────
CLIENTS = [
    ("Amazon Distribution Center",    "Amazon DC"),
    ("Costco Wholesale Corp",          "Costco"),
    ("Boeing Facilities Group",        "Boeing"),
    ("Prologis REIT",                  "Prologis"),
    ("DHL Supply Chain",               "DHL"),
    ("UPS Supply Chain Solutions",     "UPS"),
    ("Pacific Distribution LLC",       "Pacific Distribution"),
    ("Cascade Logistics Inc",          "Cascade Logistics"),
    ("Rainier Cold Storage",           "Rainier Cold Storage"),
    ("Puget Sound Manufacturing",      "PSM Industries"),
    ("Kent Valley Freight",            "KV Freight"),
    ("Tukwila Industrial Park",        "TIP Management"),
    ("Renton Metalworks",              "Renton Metalworks"),
    ("Tacoma Container Services",      "Tacoma Container"),
    ("Federal Way Distribution",       "FWD Corp"),
    ("Woodinville Beverage Co",        "Woodinville Bev"),
    ("Sumner Pallet & Storage",        "Sumner Storage"),
    ("Fife Distribution Center",       "Fife DC"),
    ("Burien Industrial Group",        "Burien Industrial"),
    ("Marysville Sheet Metal",         "Marysville Metal"),
    ("SeaTac Air Cargo Services",      "SeaTac Cargo"),
    ("Mukilteo Fabrication Inc",       "Mukilteo Fab"),
    ("Kirkland Commerce Park",         "Kirkland Commerce"),
    ("Redmond Tech Facility",          "Redmond TechPark"),
]

CITIES = ['Auburn', 'Kent', 'Tacoma', 'Tukwila', 'Renton', 'Woodinville',
          'Fife', 'Sumner', 'Puyallup', 'Federal Way', 'SeaTac', 'Burien',
          'Everett', 'Marysville', 'Mukilteo', 'Lynnwood', 'Kirkland',
          'Redmond', 'Bellevue', 'Issaquah', 'Bothell', 'Shoreline']

# ── Project templates per architect ──────────────────────────────────────────
SARAH_PROJECTS = [
    # (job_type, description_template, fee_range, duration_days)
    ("Warehouse TI",        "Permit drawings — dock door expansion, {city} facility",          (4500, 9500),   45),
    ("Warehouse TI",        "Full TI design package — {client} distribution center, {city}",  (12000, 28000), 90),
    ("Dock Equipment",      "Architectural drawings — dock leveler pit & door framing",        (3500, 7000),   30),
    ("Mezzanine Design",    "Mezzanine structural drawings — {client}, {city}",                (6000, 14000),  60),
    ("Commercial Build",    "New industrial build — design & permit set, {city}",              (18000, 45000), 120),
    ("Warehouse TI",        "Multi-door TI package — {client} {city} warehouse",               (8000, 16000),  60),
    ("Site Plan",           "Site plan & grading drawings — {client} expansion",               (5000, 11000),  45),
    ("Permit Drawings",     "Building permit application package — {city} facility",           (4000, 8500),   30),
    ("LEED Consultation",   "LEED certification consultation — {client} facility",             (7500, 15000),  60),
    ("As-Built Docs",       "As-built documentation set — {client}, post-construction",        (3000, 6000),   21),
    ("Fire/Life Safety",    "Fire & life safety plan revision — {city} warehouse",             (4500, 9000),   30),
    ("ADA Compliance",      "ADA compliance drawings & site accessibility plan",               (3500, 7500),   30),
    ("Warehouse TI",        "Cold storage expansion drawings — {client}, {city}",              (9000, 20000),  75),
    ("Permit Drawings",     "Dock door cut-in permit drawings — {client} {city}",              (2800, 5500),   21),
    ("Commercial Build",    "Ground-up industrial facility design — {city}",                   (25000, 60000), 150),
]

ROBERT_PROJECTS = [
    ("Commercial Renovation", "Commercial renovation design — {client}, {city}",              (8000, 18000),  60),
    ("Warehouse TI",          "Full permit package — {client} warehouse TI, {city}",          (10000, 22000), 75),
    ("Dock Equipment",        "Dock door structural drawings — {client} facility",             (4000, 8000),   30),
    ("Mezzanine Design",      "Mezzanine fab drawings — {client}, {city}",                    (7000, 16000),  60),
    ("Permit Drawings",       "City permit submittal — overhead door openings, {city}",       (3500, 7000),   30),
    ("Commercial Build",      "Industrial facility design — ground up, {city}",               (20000, 55000), 120),
    ("Structural Review",     "Structural plan review & engineer stamp — {client}",            (2500, 5500),   21),
    ("As-Built Docs",         "As-built drawings — post-installation documentation",           (2800, 5000),   21),
    ("Warehouse TI",          "Multi-tenant warehouse TI package — {city}",                   (11000, 24000), 90),
    ("Site Plan",             "Site plan update — {client} facility expansion, {city}",       (4500, 9500),   45),
    ("Permit Drawings",       "Expedited permit drawings — dock door addition, {city}",       (3000, 6500),   21),
    ("Commercial Renovation", "Facility renovation — dock bay redesign, {client}",            (9000, 19000),  75),
]

DANA_PROJECTS = [
    ("Structural Engineering", "Structural drawings — mezzanine steel framing, {city}",       (5500, 12000),  45),
    ("Structural Engineering", "Dock pit structural design — {client} facility",              (4000, 8500),   30),
    ("Structural Engineering", "Overhead door header engineering — {client}, {city}",         (3000, 6500),   21),
    ("Structural Engineering", "Racking anchor design & calculations — {client}",             (2500, 5500),   21),
    ("Structural Engineering", "Crane runway beam structural analysis — {city}",              (6000, 13000),  45),
    ("Structural Review",      "Peer review — mezzanine framing plans, {client}",             (2000, 4500),   14),
    ("Structural Engineering", "Multi-bay dock structural package — {city}",                  (7500, 16000),  60),
    ("Foundation Design",      "Slab-on-grade & anchor bolt design — {client}, {city}",      (4500, 9000),   30),
    ("Structural Engineering", "Conveyor support structure design — {client}",                (5000, 11000),  45),
    ("Structural Review",      "Structural integrity assessment — existing facility, {city}", (3500, 7500),   30),
    ("Foundation Design",      "Epoxy anchor & embed plate engineering — {city} facility",   (2800, 5800),   21),
    ("Structural Engineering", "Steel canopy & shelter design — {client} dock area",          (4000, 8000),   30),
    ("Structural Engineering", "Seismic upgrade drawings — {client} warehouse, {city}",       (8000, 18000),  75),
]

ARCH_DATA = [
    {
        'person': next(p for p in people if p['name'] == 'Sarah Chen'),
        'projects': SARAH_PROJECTS,
        'count': 15,
        'start_year': 2020,
    },
    {
        'person': next(p for p in people if p['name'] == 'Robert Nakamura'),
        'projects': ROBERT_PROJECTS,
        'count': 12,
        'start_year': 2019,
    },
    {
        'person': next(p for p in people if p['name'] == 'Dana Reeves'),
        'projects': DANA_PROJECTS,
        'count': 10,
        'start_year': 2021,
    },
]

new_jobs = []
new_pay  = []

for arch in ARCH_DATA:
    person   = arch['person']
    pid      = person['person_id']
    company  = person['company']
    projects = arch['projects']
    count    = arch['count']
    random.seed(hash(person['name']) % (2**32))

    # Spread projects across the date range
    # Mix: ~60% complete, ~20% active, ~20% quoted (future)
    start_dt = date(arch['start_year'], 1, 1)
    total_days = (TODAY - start_dt).days

    # Generate count projects with distributed start dates
    templates = random.choices(projects, k=count)
    statuses  = (['complete'] * int(count * 0.6) +
                 ['active']   * int(count * 0.2) +
                 ['quoted']   * (count - int(count * 0.6) - int(count * 0.2)))
    random.shuffle(statuses)

    for i, (tmpl, status) in enumerate(zip(templates, statuses)):
        job_type, desc_tmpl, fee_range, duration = tmpl

        random.seed(hash(f"{person['name']}{i}") % (2**32))
        client_full, client_short = random.choice(CLIENTS)
        city = random.choice(CITIES)
        fee  = random.randint(*fee_range)

        desc = desc_tmpl.format(client=client_short, city=city)

        if status == 'complete':
            # Past project — spread evenly across history
            offset = int((i / count) * total_days * 0.8)
            start  = start_dt + timedelta(days=offset)
            end    = start + timedelta(days=duration)
            if end >= TODAY:
                end = TODAY - timedelta(days=random.randint(10, 60))
                start = end - timedelta(days=duration)
            pay_status = 'paid'
        elif status == 'active':
            # Currently in progress
            start = TODAY - timedelta(days=random.randint(10, 45))
            end   = TODAY + timedelta(days=random.randint(14, 60))
            pay_status = 'pending'
        else:  # quoted / upcoming
            start = TODAY + timedelta(days=random.randint(14, 120))
            end   = start + timedelta(days=duration)
            pay_status = 'pending'

        yr = start.year
        job_id     = str(uuid.uuid4())
        job_number = next_job_number(yr)

        job = {
            "job_id":         job_id,
            "job_number":     job_number,
            "client_name":    client_short,
            "client_company": client_full,
            "client_phone":   "",
            "client_email":   "",
            "job_type":       job_type,
            "status":         status,
            "value":          fee,
            "start_date":     start.isoformat(),
            "end_date":       end.isoformat(),
            "address":        f"{city}, WA",
            "description":    desc,
            "workers":        "",
            "subcontractors": company,
            "notes":          f"Architecture/design contract — {company}",
        }
        new_jobs.append(job)

        # Pay record linked to this job
        pay_date = end.isoformat() if status == 'complete' else (
                   (TODAY + timedelta(days=30)).isoformat() if status == 'active'
                   else (start + timedelta(days=duration + 14)).isoformat())

        pay_rec = {
            "pay_id":      str(uuid.uuid4()),
            "person_id":   pid,
            "job_id":      job_id,
            "job_number":  job_number,
            "description": f"Architecture fee — {desc[:60]}",
            "pay_date":    pay_date,
            "period_start": start.isoformat(),
            "period_end":   end.isoformat(),
            "amount_due":  float(fee),
            "amount_paid": float(fee) if pay_status == 'paid' else 0.0,
            "status":      pay_status,
        }
        new_pay.append(pay_rec)

    print(f"{person['name']:20} — {len([j for j in new_jobs if company in j.get('subcontractors','')])} jobs created")

# ── Save ──────────────────────────────────────────────────────────────────────
all_jobs = jobs + new_jobs
all_pay  = payroll + new_pay

with open('jobs.json',    'w') as f: json.dump(all_jobs, f, indent=2)
with open('payroll.json', 'w') as f: json.dump(all_pay,  f, indent=2)

print(f"\nNew jobs:        {len(new_jobs)}")
print(f"New pay records: {len(new_pay)}")
print(f"Total jobs:      {len(all_jobs)}")
print(f"Total pay:       {len(all_pay)}")

# Status breakdown
for arch in ARCH_DATA:
    company = arch['person']['company']
    arch_jobs = [j for j in new_jobs if company in j.get('subcontractors', '')]
    by_status = {}
    for j in arch_jobs:
        by_status[j['status']] = by_status.get(j['status'], 0) + 1
    print(f"  {arch['person']['name']:20} — {by_status}")
