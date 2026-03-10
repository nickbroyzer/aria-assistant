"""
Seed weekly pay records and quarterly project assignments for office staff.
Ashley Farmer (7 yrs back) and Jen Koller (5 yrs back), both weekly salary.
"""
import json, uuid, random
from datetime import date, timedelta

with open('people.json')  as f: people  = json.load(f)
with open('jobs.json')    as f: jobs    = json.load(f)
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

TODAY  = date(2026, 3, 8)

CLIENTS = [
    ("Amazon Distribution Center",  "Amazon DC"),
    ("Pacific Distribution LLC",    "Pacific Distribution"),
    ("Cascade Logistics Inc",       "Cascade Logistics"),
    ("Rainier Cold Storage",        "Rainier Cold Storage"),
    ("Puget Sound Manufacturing",   "PSM Industries"),
    ("Kent Valley Freight",         "KV Freight"),
    ("Tukwila Industrial Park",     "TIP Management"),
    ("Renton Metalworks",           "Renton Metalworks"),
    ("Tacoma Container Services",   "Tacoma Container"),
    ("Federal Way Distribution",    "FWD Corp"),
    ("Woodinville Beverage Co",     "Woodinville Bev"),
    ("Sumner Pallet & Storage",     "Sumner Storage"),
    ("Fife Distribution Center",    "Fife DC"),
    ("Burien Industrial Group",     "Burien Industrial"),
    ("SeaTac Air Cargo Services",   "SeaTac Cargo"),
    ("Everett Marine Supply",       "Everett Marine"),
    ("Mukilteo Fabrication Inc",    "Mukilteo Fab"),
    ("Kirkland Commerce Park",      "Kirkland Commerce"),
    ("DHL Supply Chain",            "DHL"),
    ("Boeing Facilities Group",     "Boeing"),
]

CITIES = ['Auburn', 'Kent', 'Tacoma', 'Tukwila', 'Renton', 'Woodinville',
          'Fife', 'Sumner', 'Puyallup', 'Federal Way', 'SeaTac', 'Burien',
          'Everett', 'Kirkland', 'Bellevue', 'Bothell', 'Shoreline']

OFFICE_JOB_TYPES = [
    'Project Administration',
    'Accounts Payable / Receivable',
    'Job Costing & Billing',
    'Permit Coordination',
    'Warranty & Service Admin',
    'Vendor Management',
    'Payroll Administration',
    'Customer Communications',
    'Contract Management',
    'Office Operations',
]

START_DATES = {
    'Ashley Farmer': date(2019, 3, 4),   # ~7 years
    'Jen Koller':    date(2021, 1, 11),  # ~5 years
}

office_staff = [p for p in people if p['department'] == 'Office & Admin' and p['type'] == 'employee']

new_jobs = []
new_pay  = []

for emp in office_staff:
    pid   = emp['person_id']
    name  = emp['name']
    rate  = float(emp['pay_rate'])      # annual salary
    start = START_DATES[name]

    random.seed(hash(name) % (2**32))

    # Weekly gross = annual / 52
    weekly_gross = round(rate / 52, 2)

    # Generate all weekly Fridays from start to today
    pay_day      = start + timedelta(days=(4 - start.weekday()) % 7)  # first Friday
    period_start = start

    # Bucket into quarters
    quarters = {}
    while pay_day <= TODAY:
        yr = pay_day.year
        q  = (pay_day.month - 1) // 3 + 1
        key = (yr, q)
        if key not in quarters:
            quarters[key] = []
        quarters[key].append((period_start, pay_day))
        period_start = pay_day + timedelta(days=1)
        pay_day += timedelta(weeks=1)

    # Create one project job per quarter, weekly pay records linked to it
    for (yr, q), periods in sorted(quarters.items()):
        random.seed(hash(f"{name}{yr}{q}") % (2**32))

        client_full, client_short = random.choice(CLIENTS)
        city      = random.choice(CITIES)
        job_type  = random.choice(OFFICE_JOB_TYPES)
        q_label   = ['Q1','Q2','Q3','Q4'][q-1]

        q_start = periods[0][0]
        q_end   = periods[-1][1]
        q_gross = sum(weekly_gross for _ in periods)

        job_id     = str(uuid.uuid4())
        job_number = next_job_number(yr)
        job_status = 'active' if q_end >= TODAY else 'complete'

        job = {
            "job_id":         job_id,
            "job_number":     job_number,
            "client_name":    client_short,
            "client_company": client_full,
            "client_phone":   "",
            "client_email":   "",
            "job_type":       job_type,
            "status":         job_status,
            "value":          round(q_gross, 2),
            "start_date":     q_start.isoformat(),
            "end_date":       q_end.isoformat(),
            "address":        f"{city}, WA",
            "description":    f"{q_label} {yr} — {job_type}",
            "workers":        name,
            "subcontractors": "",
            "notes":          f"Quarterly admin block for {name} — {len(periods)} weekly pay periods",
        }
        new_jobs.append(job)

        # Weekly pay records
        for ps, pe in periods:
            pay_type_str = emp.get('pay_type', 'salary')
            desc = f"Weekly Payroll: {ps.strftime('%b %d')} – {pe.strftime('%b %d, %Y')} (${rate:,.0f}/yr ÷ 52)"

            is_past    = pe < TODAY - timedelta(days=7)
            pay_status = 'paid' if is_past else 'pending'

            rec = {
                "pay_id":       str(uuid.uuid4()),
                "person_id":    pid,
                "job_id":       job_id,
                "job_number":   job_number,
                "description":  desc,
                "pay_date":     pe.isoformat(),
                "period_start": ps.isoformat(),
                "period_end":   pe.isoformat(),
                "amount_due":   weekly_gross,
                "amount_paid":  weekly_gross if pay_status == 'paid' else 0.0,
                "status":       pay_status,
            }
            new_pay.append(rec)

    emp_pay   = [r for r in new_pay if r['person_id'] == pid]
    emp_jobs  = [j for j in new_jobs if name in j.get('workers', '')]
    print(f"{name:20} — {len(emp_pay):4} weekly records | {len(emp_jobs):3} quarterly jobs | ${weekly_gross:,.2f}/week")

# ── Save ──────────────────────────────────────────────────────────────────────
with open('jobs.json',    'w') as f: json.dump(jobs    + new_jobs, f, indent=2)
with open('payroll.json', 'w') as f: json.dump(payroll + new_pay,  f, indent=2)

print(f"\nTotal new jobs:      {len(new_jobs)}")
print(f"Total new pay recs:  {len(new_pay)}")
print(f"Grand total jobs:    {len(jobs) + len(new_jobs)}")
print(f"Grand total pay:     {len(payroll) + len(new_pay)}")
