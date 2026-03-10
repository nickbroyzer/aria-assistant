"""
Generate realistic vendor invoices for all job cost records.
Each invoice is linked to a cost_id and looks like a real vendor document.
"""
import json, uuid, random
from datetime import date, timedelta

with open('jobcosts.json') as f:
    costs = json.load(f)

# Vendor profiles: name → address, phone, email, website
VENDOR_PROFILES = {
    'Home Depot Pro':          ('2601 Utah Ave S, Seattle, WA 98134',       '(206) 762-4400', 'proservices@homedepot.com',     'www.homedepot.com/c/pro'),
    'Fastenal':                ('315 E Meeker St, Kent, WA 98030',          '(253) 854-9100', 'kent.wa@fastenal.com',          'www.fastenal.com'),
    'Pacific Steel & Recycling':('1050 S 146th St, Burien, WA 98168',       '(206) 243-3400', 'burien@pacificsteel.com',       'www.pacificsteel.com'),
    'ABC Supply Co':           ('3400 E Valley Rd, Renton, WA 98057',       '(425) 251-8800', 'renton@abcsupply.com',          'www.abcsupply.com'),
    'Grainger Industrial':     ('18000 Andover Park W, Tukwila, WA 98188',  '(206) 575-3800', 'tukwila@grainger.com',          'www.grainger.com'),
    'Uline':                   ('PO Box 88741, Seattle, WA 98138',          '(800) 295-5510', 'custserv@uline.com',            'www.uline.com'),
    'MSC Industrial':          ('22010 SE 56th St, Issaquah, WA 98029',     '(425) 392-0555', 'issaquah@mscdirect.com',        'www.mscdirect.com'),
    'Graybar Electric':        ('3600 E Marginal Way S, Seattle, WA 98134', '(206) 682-3100', 'seattle@graybar.com',           'www.graybar.com'),
    'Ferguson Enterprises':    ('1880 Andover Park E, Tukwila, WA 98188',   '(206) 575-4440', 'tukwila@ferguson.com',          'www.ferguson.com'),
    'HD Supply':               ('17900 Southcenter Pkwy, Tukwila, WA 98188','(206) 575-2200', 'orders@hdsupply.com',           'www.hdsupply.com'),
    'Interline Brands':        ('PO Box 1110, Seattle, WA 98111',           '(800) 340-6699', 'billing@interlinebrands.com',   'www.interlinebrands.com'),
    'Wesco International':     ('4700 Airport Way S, Seattle, WA 98108',    '(206) 763-1700', 'seattle@wesco.com',             'www.wesco.com'),
    'Pacific Electric LLC':    ('824 Industry Dr, Tukwila, WA 98188',       '(206) 575-8820', 'billing@pacificelectricllc.com',''),
    'Northwest Concrete Inc':  ('3100 S 116th St, Tukwila, WA 98168',       '(206) 244-5500', 'ap@nwconcreteinc.com',          ''),
    'Cascade Welding Co':      ('1400 Monster Rd SW, Renton, WA 98057',     '(425) 271-3300', 'invoices@cascadewelding.com',   ''),
    'Puget Sound Plumbing':    ('5309 Shilshole Ave NW, Seattle, WA 98107', '(206) 783-3000', 'billing@pugetsoundplumbing.com','www.pugetsoundplumbing.com'),
    'Olympic Painting & Coating':('8601 S 212th St, Kent, WA 98031',        '(253) 872-7100', 'ap@olympiccoating.com',         ''),
    'Summit Flooring Co':      ('1901 Raymond Ave SW, Renton, WA 98057',    '(425) 204-9900', 'billing@summitflooring.net',    ''),
    'Rainier Mechanical':      ('22020 70th Ave S, Kent, WA 98032',         '(253) 395-7700', 'ap@rainiermech.com',            ''),
    'Sound Drywall & Framing': ('6500 S 144th St, Tukwila, WA 98168',       '(206) 246-1800', 'billing@sounddrywall.com',      ''),
    'Tacoma Steel Erectors':   ('3801 Portland Ave E, Tacoma, WA 98404',    '(253) 627-5500', 'ap@tacomasteel.com',            ''),
    'Auburn Roofing Specialists':('1302 Auburn Way N, Auburn, WA 98002',    '(253) 931-6600', 'billing@auburnroofing.com',     ''),
    'United Rentals':          ('17201 Southcenter Pkwy, Tukwila, WA 98188','(206) 575-7700', 'invoicing@unitedrentals.com',   'www.unitedrentals.com'),
    'Sunbelt Rentals':         ('19204 Des Moines Memorial Dr, SeaTac, WA 98148','(206) 824-4400','invoices@sunbeltrentals.com','www.sunbeltrentals.com'),
    'H&E Equipment Services':  ('18800 Orillia Rd S, Tukwila, WA 98188',   '(206) 575-5300', 'ap@he-equipment.com',           'www.he-equipment.com'),
    'Herc Rentals':            ('3600 E Marginal Way S, Seattle, WA 98134', '(206) 622-5400', 'billing@hercrentals.com',       'www.hercrentals.com'),
    'RSC Equipment Rental':    ('21400 84th Ave S, Kent, WA 98032',         '(253) 872-4100', 'invoices@rscequipment.com',     ''),
    'Neff Rental':             ('17200 Southcenter Pkwy, Tukwila, WA 98188','(206) 575-8800', 'billing@neffrental.com',        ''),
    'City of Kent Building Dept':('220 4th Ave S, Kent, WA 98032',          '(253) 856-5200', 'permits@kentwa.gov',            'www.kentwa.gov/permits'),
    'City of Auburn Permits':  ('25 W Main St, Auburn, WA 98001',           '(253) 931-3020', 'permits@auburnwa.gov',          'www.auburnwa.gov'),
    'City of Tacoma Development Services':('747 Market St, Tacoma, WA 98402','(253) 591-5030','permits@cityoftacoma.org',     'www.cityoftacoma.org'),
    'King County DPER':        ('35030 SE Douglas St, Snoqualmie, WA 98065','(206) 296-6600', 'dper@kingcounty.gov',           'www.kingcounty.gov'),
    'Pierce County Planning':  ('2401 S 35th St, Tacoma, WA 98409',         '(253) 798-7037', 'planning@piercecountywa.gov',   'www.piercecountywa.gov'),
    'City of Renton Planning Dept':('1055 S Grady Way, Renton, WA 98057',   '(425) 430-7200', 'planningdept@rentonwa.gov',     'www.rentonwa.gov'),
    'City of Federal Way Permits':('33325 8th Ave S, Federal Way, WA 98003','(253) 835-2607', 'permits@cityoffederalway.com',  'www.cityoffederalway.com'),
    'WA Labor & Industries':   ('7273 Linderson Way SW, Tumwater, WA 98501','(360) 902-5800', 'lni@lni.wa.gov',               'www.lni.wa.gov'),
    'Pacific Waste Services':  ('1200 Monster Rd SW, Renton, WA 98057',     '(425) 228-2424', 'billing@pacificwaste.com',      ''),
    'Shred-it':                ('PO Box 101007, Pasadena, CA 91189',         '(800) 697-4733', 'billing@shredit.com',           'www.shredit.com'),
    'Aramark Uniforms':        ('PO Box 101005, Pasadena, CA 91189',         '(800) 272-6275', 'billing@aramark.com',           'www.aramark.com'),
    'Cintas Corporation':      ('PO Box 625737, Cincinnati, OH 45262',       '(800) 246-8271', 'billing@cintas.com',            'www.cintas.com'),
    'Office Depot':            ('1903 Auburn Way N, Auburn, WA 98002',       '(253) 735-5500', 'businessservices@officedepot.com','www.officedepot.com'),
    'NAPA Auto Parts':         ('1102 Central Ave N, Kent, WA 98032',        '(253) 852-8880', 'billing@napaonline.com',         'www.napaonline.com'),
    'Verizon Business':        ('PO Box 660794, Dallas, TX 75266',           '(800) 837-4966', 'vzbusiness@verizon.com',         'www.verizon.com/business'),
    'Amazon Business':         ('PO Box 81226, Seattle, WA 98108',           '(888) 281-3847', 'business@amazon.com',            'business.amazon.com'),
}

DEFAULT_PROFILE = ('PO Box 1000, Seattle, WA 98101', '(206) 555-0100', 'billing@vendor.com', '')

# Line item templates by category + description keywords
def build_line_items(cost, total_amount):
    random.seed(hash(cost['cost_id']) % (2**32))
    desc  = cost['description']
    cat   = cost['category']

    # Split into 1–4 line items
    if total_amount < 500:
        n = 1
    elif total_amount < 2000:
        n = random.randint(1, 2)
    elif total_amount < 8000:
        n = random.randint(2, 3)
    else:
        n = random.randint(2, 4)

    base_descs = [desc]

    # Add supporting line items based on category
    extras = {
        'Materials':    ['Delivery & handling', 'Cut/fab charges', 'Small tools & consumables', 'Freight surcharge'],
        'Labor & Subs': ['Mobilization', 'Supervision', 'Cleanup & debris removal', 'Equipment operation'],
        'Equipment':    ['Fuel surcharge', 'Damage waiver', 'Transportation fee', 'Extended rental day'],
        'Permits':      ['State surcharge', 'Plan check fee', 'Inspection fee', 'Records processing fee'],
        'Other':        ['Service charge', 'Administrative fee', 'Handling fee'],
    }
    pool = extras.get(cat, ['Miscellaneous charges'])
    extra_count = n - 1
    if extra_count > 0:
        base_descs += random.sample(pool, min(extra_count, len(pool)))

    # Distribute amount across line items
    splits = sorted([random.uniform(0.1, 1.0) for _ in range(n)])
    total_split = sum(splits)
    amounts = [round(total_amount * s / total_split, 2) for s in splits]
    # Fix rounding so it adds up exactly
    diff = round(total_amount - sum(amounts), 2)
    amounts[-1] = round(amounts[-1] + diff, 2)

    items = []
    for i, (d, a) in enumerate(zip(base_descs, amounts)):
        qty  = 1
        unit = 'LS'  # Lump Sum default
        if cat == 'Materials':
            qty  = random.randint(1, 20)
            unit = random.choice(['EA', 'LF', 'SF', 'Box', 'Pallet', 'EA'])
        elif cat == 'Equipment':
            qty  = random.randint(1, 5)
            unit = random.choice(['Day', 'Week', 'Day'])
        elif cat == 'Labor & Subs':
            qty  = random.randint(4, 40)
            unit = 'HR'
        unit_price = round(a / qty, 2)
        items.append({'description': d, 'qty': qty, 'unit': unit, 'unit_price': unit_price, 'amount': a})
    return items

invoices = []
for cost in costs:
    vendor = cost.get('vendor', 'Unknown Vendor')
    profile = VENDOR_PROFILES.get(vendor, DEFAULT_PROFILE)
    addr, phone, email, website = profile

    cost_date = cost.get('date', '2026-01-15')
    try:
        inv_date = date.fromisoformat(cost_date)
    except:
        inv_date = date(2026, 1, 15)

    due_date = inv_date + timedelta(days=random.choice([15, 30, 30, 30, 45]))
    terms    = {15: 'Net 15', 30: 'Net 30', 45: 'Net 45'}[( due_date - inv_date).days]

    line_items = build_line_items(cost, cost['amount'])
    subtotal   = sum(i['amount'] for i in line_items)

    # Gov/permit vendors don't charge tax; equipment rentals sometimes do; materials usually do
    taxable = cost['category'] in ('Materials', 'Equipment') and 'City of' not in vendor and 'County' not in vendor and 'WA Labor' not in vendor
    tax_rate = 0.102 if taxable else 0.0
    tax      = round(subtotal * tax_rate, 2)
    total    = round(subtotal + tax, 2)

    inv = {
        'vinvoice_id':   str(uuid.uuid4()),
        'cost_id':       cost['cost_id'],
        'invoice_number': cost.get('invoice_ref', f'INV-{random.randint(10000,99999)}'),
        'invoice_date':  inv_date.isoformat(),
        'due_date':      due_date.isoformat(),
        'terms':         terms,
        'vendor_name':   vendor,
        'vendor_address':addr,
        'vendor_phone':  phone,
        'vendor_email':  email,
        'vendor_website':website,
        'bill_to_name':  'Pacific Construction',
        'bill_to_address':'1574 Thornton Ave SW, Pacific, WA 98047',
        'bill_to_attn':  cost.get('client_name', ''),
        'job_number':    cost.get('job_number', ''),
        'job_ref':       f"Re: Job {cost.get('job_number','')} — {cost.get('description','')}",
        'line_items':    line_items,
        'subtotal':      round(subtotal, 2),
        'tax_rate':      tax_rate,
        'tax':           tax,
        'total':         total,
        'notes':         f"Please reference invoice # {cost.get('invoice_ref','')} with payment. " +
                         ("Thank you for your business." if cost['category'] not in ('Permits',) else "This is an official government fee receipt."),
        'status':        cost.get('status', 'pending'),
    }
    invoices.append(inv)

with open('vendorinvoices.json', 'w') as f:
    json.dump(invoices, f, indent=2)

print(f"Generated {len(invoices)} vendor invoices")
taxable_count = sum(1 for i in invoices if i['tax'] > 0)
print(f"  {taxable_count} with tax, {len(invoices)-taxable_count} tax-exempt")
print(f"  Total billed: ${sum(i['total'] for i in invoices):,.2f}")
