"""
Seed historical completed jobs from historical pay records.
Creates one job per pay record (for subs) or one per pay period (for employees),
then links each pay record to its new job.
"""
import json, uuid, random
from datetime import datetime, timedelta

with open('jobs.json') as f:
    jobs = json.load(f)
with open('payroll.json') as f:
    payroll = json.load(f)
with open('people.json') as f:
    people = json.load(f)

people_by_id = {p['person_id']: p for p in people}

# Counters per year for job numbers
year_counters = {}
for j in jobs:
    yr = j['job_number'].split('-')[1]
    num = int(j['job_number'].split('-')[2])
    year_counters[yr] = max(year_counters.get(yr, 0), num)

def next_job_number(year):
    yr = str(year)
    year_counters[yr] = year_counters.get(yr, 0) + 1
    return f"JOB-{yr}-{year_counters[yr]:03d}"

# Seattle-area industrial/warehouse clients
CLIENTS = [
    ("Pacific Distribution LLC", "Pacific Distribution"),
    ("Cascade Logistics Inc", "Cascade Logistics"),
    ("Sound Warehousing Co", "Sound Warehousing"),
    ("Olympic Industrial Supply", "Olympic Supply"),
    ("Rainier Cold Storage", "Rainier Cold Storage"),
    ("Puget Sound Manufacturing", "PSM Industries"),
    ("Northwest Auto Parts", "NW Auto Parts"),
    ("Auburn Commerce Center", "Auburn Commerce"),
    ("Kent Valley Freight", "KV Freight"),
    ("Tukwila Industrial Park", "TIP Management"),
    ("Renton Metalworks", "Renton Metalworks"),
    ("Tacoma Container Services", "Tacoma Container"),
    ("Woodinville Beverage Co", "Woodinville Bev"),
    ("Bellevue Tech Campus", "Bellevue Tech"),
    ("Federal Way Distribution", "FWD Corp"),
    ("Sumner Pallet & Storage", "Sumner Storage"),
    ("Puyallup Cold Logistics", "PCL Group"),
    ("SeaTac Air Cargo Services", "SeaTac Cargo"),
    ("Everett Marine Supply", "Everett Marine"),
    ("Lynnwood Fleet Services", "Lynnwood Fleet"),
    ("Burien Industrial Group", "Burien Industrial"),
    ("Des Moines Warehouse Co", "DM Warehouse"),
    ("Mukilteo Fabrication Inc", "Mukilteo Fab"),
    ("Fife Distribution Center", "Fife DC"),
    ("Puyallup Building Supply", "Puyallup Supply"),
    ("Kirkland Commerce Park", "Kirkland Commerce"),
    ("Redmond Tech Facility", "Redmond TechPark"),
    ("Issaquah Cold Storage", "Issaquah Cold"),
    ("Marysville Sheet Metal", "Marysville Metal"),
    ("Shoreline Auto Salvage", "Shoreline Auto"),
]

# Job types per trade
JOB_TYPES = {
    'employee': ['Overhead Door', 'Dock Equipment', 'Mezzanine', 'Racking System', 'Warehouse TI'],
    'subcontractor_electrical': ['Electrical TI', 'Electrical Upgrade', 'Panel Install', 'Conduit & Wiring'],
    'subcontractor_welding': ['Structural Welding', 'Mezzanine Fabrication', 'Racking Anchors', 'Steel Fabrication'],
    'subcontractor_concrete': ['Concrete Prep', 'Slab Work', 'Anchor Drilling', 'Epoxy Anchors'],
    'subcontractor_crane': ['Crane Inspection', 'Load Testing & Cert', 'Crane Maintenance', 'Lift Equipment Cert'],
    'subcontractor_door': ['Overhead Door', 'Roll-Up Door Install', 'Dock Door System', 'Commercial Doors'],
}

def get_job_type(person):
    if person['type'] == 'employee':
        return random.choice(JOB_TYPES['employee'])
    role = (person.get('role') or '').lower()
    company = (person.get('company') or '').lower()
    if 'electric' in role or 'electric' in company:
        return random.choice(JOB_TYPES['subcontractor_electrical'])
    if 'weld' in role or 'weld' in company:
        return random.choice(JOB_TYPES['subcontractor_welding'])
    if 'concrete' in role or 'concrete' in company:
        return random.choice(JOB_TYPES['subcontractor_concrete'])
    if 'crane' in role or 'crane' in company:
        return random.choice(JOB_TYPES['subcontractor_crane'])
    if 'door' in role or 'door' in company:
        return random.choice(JOB_TYPES['subcontractor_door'])
    return 'Commercial Construction'

def get_field_for_person(person, name_val):
    """Returns (field_name, value) - workers for employees, subcontractors for subs"""
    if person['type'] == 'employee':
        return 'workers', name_val
    else:
        return 'subcontractors', name_val

# Extract a rough location from description
def extract_location(desc):
    cities = ['Auburn', 'Kent', 'Tacoma', 'Tukwila', 'Renton', 'Woodinville',
              'Bellevue', 'Federal Way', 'Sumner', 'Puyallup', 'Fife', 'Everett',
              'SeaTac', 'Burien', 'Des Moines', 'Kirkland', 'Redmond', 'Lynnwood']
    for c in cities:
        if c.lower() in desc.lower():
            return c
    return random.choice(cities)

# Get historical pay records (no job_id)
hist_records = [r for r in payroll if not r.get('job_id')]
print(f"Processing {len(hist_records)} historical pay records...")

new_jobs = []
updated = 0

# Use a fixed seed per record description so reruns are idempotent-ish
for rec in hist_records:
    person = people_by_id.get(rec['person_id'])
    if not person:
        continue

    pay_date = rec.get('pay_date', '2020-01-01')
    year = int(pay_date[:4])
    desc = rec.get('description', '')

    # Pick a deterministic client based on description hash
    random.seed(hash(desc) % (2**32))
    client_full, client_short = random.choice(CLIENTS)
    job_type = get_job_type(person)
    location = extract_location(desc)

    # Estimate start date ~30-90 days before pay date
    random.seed(hash(desc + 'dates') % (2**32))
    pay_dt = datetime.strptime(pay_date, '%Y-%m-%d')
    offset_days = random.randint(30, 90)
    start_dt = pay_dt - timedelta(days=offset_days)
    end_dt = pay_dt - timedelta(days=random.randint(1, 14))

    job_number = next_job_number(year)
    job_id = str(uuid.uuid4())

    person_display = person.get('company') or person['name']
    field_name, field_val = get_field_for_person(person, person_display)

    job = {
        "job_id": job_id,
        "job_number": job_number,
        "client_name": client_short,
        "client_company": client_full,
        "client_phone": "",
        "client_email": "",
        "job_type": job_type,
        "status": "complete",
        "value": rec.get('amount_due', 0),
        "start_date": start_dt.strftime('%Y-%m-%d'),
        "end_date": end_dt.strftime('%Y-%m-%d'),
        "address": f"{location}, WA",
        "description": desc,
        "workers": field_val if field_name == 'workers' else "",
        "subcontractors": field_val if field_name == 'subcontractors' else "",
        "notes": f"Historical — linked from pay record {rec['pay_id'][:8]}",
    }
    new_jobs.append(job)

    # Link pay record
    rec['job_id'] = job_id
    rec['job_number'] = job_number
    updated += 1

# Save
all_jobs = jobs + new_jobs
with open('jobs.json', 'w') as f:
    json.dump(all_jobs, f, indent=2)

with open('payroll.json', 'w') as f:
    json.dump(payroll, f, indent=2)

print(f"Created {len(new_jobs)} historical jobs")
print(f"Updated {updated} pay records with job links")
print(f"Total jobs now: {len(all_jobs)}")
