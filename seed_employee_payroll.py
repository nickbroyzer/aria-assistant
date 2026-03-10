"""
Re-seed all employee pay records with correct bi-weekly frequency.
- Deletes old employee annual/semi-annual lump sum records
- Deletes historical jobs that were linked to those records
- Creates quarterly project jobs per employee
- Creates bi-weekly pay records linked to each quarterly job
"""
import json, uuid, random
from datetime import datetime, date, timedelta

with open('people.json') as f: people = json.load(f)
with open('payroll.json') as f: payroll = json.load(f)
with open('jobs.json') as f: jobs = json.load(f)

employees = {p['person_id']: p for p in people if p['type'] == 'employee'}

# ── Employee start dates ─────────────────────────────────────────────────────
START_DATES = {
    'Dave Kowalski':  date(2016, 7, 5),
    'Tyler Brooks':   date(2019, 1, 7),
    'Emilio Santos':  date(2020, 7, 6),
    'Ray Tran':       date(2023, 1, 9),
    'Maria Gonzalez': date(2018, 4, 2),
}

# ── Remove old employee pay records and their linked historical jobs ──────────
old_emp_pay_ids = {r['pay_id'] for r in payroll if r['person_id'] in employees}
old_emp_job_ids = {r['job_id'] for r in payroll
                   if r['person_id'] in employees and r.get('job_id')
                   and 'JOB-2026' not in r.get('job_number', '')}

payroll_subs  = [r for r in payroll if r['person_id'] not in employees]
jobs_retained = [j for j in jobs if j['job_id'] not in old_emp_job_ids]

print(f"Removed {len(old_emp_pay_ids)} old employee pay records")
print(f"Removed {len(old_emp_job_ids)} old employee historical jobs")

# ── Client pool for project jobs ─────────────────────────────────────────────
CLIENTS = [
    ("Pacific Distribution LLC",    "Pacific Distribution"),
    ("Cascade Logistics Inc",       "Cascade Logistics"),
    ("Sound Warehousing Co",        "Sound Warehousing"),
    ("Rainier Cold Storage",        "Rainier Cold Storage"),
    ("Puget Sound Manufacturing",   "PSM Industries"),
    ("Northwest Auto Parts",        "NW Auto Parts"),
    ("Kent Valley Freight",         "KV Freight"),
    ("Tukwila Industrial Park",     "TIP Management"),
    ("Renton Metalworks",           "Renton Metalworks"),
    ("Tacoma Container Services",   "Tacoma Container"),
    ("Woodinville Beverage Co",     "Woodinville Bev"),
    ("Federal Way Distribution",    "FWD Corp"),
    ("Sumner Pallet & Storage",     "Sumner Storage"),
    ("Puyallup Cold Logistics",     "PCL Group"),
    ("Fife Distribution Center",    "Fife DC"),
    ("Burien Industrial Group",     "Burien Industrial"),
    ("Marysville Sheet Metal",      "Marysville Metal"),
    ("SeaTac Air Cargo Services",   "SeaTac Cargo"),
    ("Everett Marine Supply",       "Everett Marine"),
    ("Mukilteo Fabrication Inc",    "Mukilteo Fab"),
]

CITIES = ['Auburn', 'Kent', 'Tacoma', 'Tukwila', 'Renton', 'Woodinville',
          'Fife', 'Sumner', 'Puyallup', 'Federal Way', 'SeaTac', 'Burien',
          'Everett', 'Marysville', 'Mukilteo', 'Lynnwood']

EMP_JOB_TYPES = {
    'Dave Kowalski':  ['Dock Equipment Install', 'Mezzanine Fabrication', 'Racking System', 'Structural Install'],
    'Tyler Brooks':   ['Structural Install', 'Dock Equipment Install', 'Mezzanine Fabrication', 'Warehouse TI'],
    'Emilio Santos':  ['Service & Repair', 'Door Maintenance', 'Dock Equipment Service', 'Safety Inspection'],
    'Ray Tran':       ['Overhead Door Install', 'Dock Door System', 'Warehouse TI', 'Roll-Up Door Install'],
    'Maria Gonzalez': ['Project Management', 'Commercial Construction PM', 'Warehouse TI', 'Multi-Site Coordination'],
}

# ── Year counters (keep existing job numbers) ─────────────────────────────────
year_counters = {}
for j in jobs_retained:
    parts = j['job_number'].split('-')
    yr, num = parts[1], int(parts[2])
    year_counters[yr] = max(year_counters.get(yr, 0), num)

def next_job_number(year):
    yr = str(year)
    year_counters[yr] = year_counters.get(yr, 0) + 1
    return f"JOB-{yr}-{year_counters[yr]:03d}"

def next_friday(d):
    """Advance to next Friday from date d."""
    days_ahead = 4 - d.weekday()  # Friday = 4
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)

def calc_gross(person, hours=80):
    pay_type = person.get('pay_type', 'hourly')
    rate = float(person.get('pay_rate', 0))
    if pay_type == 'salary':
        return round(rate / 26, 2)          # bi-weekly salary
    else:
        return round(rate * hours, 2)        # hourly × 80 hrs per period

TODAY = date(2026, 3, 8)
new_jobs = []
new_pay  = []

for emp_id, emp in employees.items():
    name = emp['name']
    start = START_DATES.get(name)
    if not start:
        continue

    random.seed(hash(name) % (2**32))

    # Group bi-weekly pay periods into quarterly project jobs
    # A quarter = ~6 bi-weekly periods (13 weeks)
    # Generate all bi-weekly Fridays from start to today
    pay_day = next_friday(start)
    period_start = start

    # We'll bucket periods into quarters
    quarters = {}   # key = (year, quarter_num) → list of period tuples

    while pay_day <= TODAY:
        period_end = pay_day
        yr = pay_day.year
        q  = (pay_day.month - 1) // 3 + 1
        key = (yr, q)
        if key not in quarters:
            quarters[key] = []
        quarters[key].append((period_start, period_end))
        period_start = period_end + timedelta(days=1)
        pay_day += timedelta(weeks=2)

    # For each quarter create one project job, then bi-weekly pay records
    for (yr, q), periods in sorted(quarters.items()):
        # Pick a client deterministically
        random.seed(hash(f"{name}{yr}{q}") % (2**32))
        client_full, client_short = random.choice(CLIENTS)
        city = random.choice(CITIES)
        job_type = random.choice(EMP_JOB_TYPES.get(name, ['Commercial Construction']))
        q_label = ['Q1','Q2','Q3','Q4'][q-1]

        q_start = periods[0][0]
        q_end   = periods[-1][1]

        job_id     = str(uuid.uuid4())
        job_number = next_job_number(yr)

        # Value = total pay for this quarter
        q_gross = sum(calc_gross(emp) for _ in periods)

        job_status = 'complete' if q_end < TODAY else 'active'

        job = {
            "job_id":        job_id,
            "job_number":    job_number,
            "client_name":   client_short,
            "client_company": client_full,
            "client_phone":  "",
            "client_email":  "",
            "job_type":      job_type,
            "status":        job_status,
            "value":         round(q_gross, 2),
            "start_date":    q_start.isoformat(),
            "end_date":      q_end.isoformat(),
            "address":       f"{city}, WA",
            "description":   f"{q_label} {yr} — {job_type} project",
            "workers":       name,
            "subcontractors": "",
            "notes":         f"Quarterly project block for {name} — {len(periods)} pay periods",
        }
        new_jobs.append(job)

        # Create bi-weekly pay records for each period in this quarter
        for i, (ps, pe) in enumerate(periods):
            gross = calc_gross(emp)
            pay_type = emp.get('pay_type', 'hourly')
            rate     = float(emp.get('pay_rate', 0))

            if pay_type == 'salary':
                desc = f"Bi-Weekly Payroll: {ps.strftime('%b %d')} – {pe.strftime('%b %d, %Y')}"
            else:
                desc = f"Bi-Weekly Payroll: {ps.strftime('%b %d')} – {pe.strftime('%b %d, %Y')} (80 hrs @ ${rate}/hr)"

            status = 'paid' if pe < TODAY - timedelta(days=14) else ('pending' if pe >= TODAY else 'paid')

            rec = {
                "pay_id":      str(uuid.uuid4()),
                "person_id":   emp_id,
                "job_id":      job_id,
                "job_number":  job_number,
                "description": desc,
                "pay_date":    pe.isoformat(),
                "period_start": ps.isoformat(),
                "period_end":   pe.isoformat(),
                "amount_due":  gross,
                "amount_paid": gross if status == 'paid' else 0.0,
                "status":      status,
            }
            new_pay.append(rec)

# ── Save ──────────────────────────────────────────────────────────────────────
all_pay  = payroll_subs + new_pay
all_jobs = jobs_retained + new_jobs

with open('payroll.json', 'w') as f: json.dump(all_pay, f, indent=2)
with open('jobs.json',   'w') as f: json.dump(all_jobs, f, indent=2)

# Summary
print(f"\nNew employee pay records: {len(new_pay)}")
print(f"New quarterly project jobs: {len(new_jobs)}")
print(f"Total pay records: {len(all_pay)}")
print(f"Total jobs: {len(all_jobs)}")
print("\nPer employee:")
for emp_id, emp in employees.items():
    recs = [r for r in new_pay if r['person_id'] == emp_id]
    emp_jobs = [j for j in new_jobs if emp['name'] in j.get('workers','')]
    if recs:
        gross_per = recs[0]['amount_due']
        print(f"  {emp['name']:20} {len(recs):4} pay records | {len(emp_jobs):3} quarterly jobs | ${gross_per:,.2f}/period")
