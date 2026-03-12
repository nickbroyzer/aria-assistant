"""Seed 10 demo orders per supplier (280 total). Skips suppliers that already have orders."""

import random
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.suppliers_db import init_db, load_suppliers, get_orders, create_order

CATEGORY_ITEMS = {
    "racking": [
        ("Uprights 48x192", "ea", 12, 30, 180, 320),
        ("Step beams 96in", "ea", 20, 80, 45, 85),
        ("Wire decking 42x46", "ea", 24, 100, 30, 55),
        ("Footplates", "ea", 12, 60, 8, 18),
        ("Row spacers 36in", "ea", 10, 40, 12, 25),
    ],
    "mezzanine": [
        ("Mezzanine deck panels 4x8", "ea", 8, 40, 280, 520),
        ("Support columns 12ft", "ea", 6, 20, 350, 600),
        ("IBC stairway kit", "ea", 1, 3, 2800, 4500),
        ("Handrail kit 20ft", "ea", 2, 8, 320, 550),
        ("Bar grating panels", "ea", 10, 30, 85, 160),
    ],
    "crane": [
        ("Jib crane 1-ton 12ft", "ea", 1, 3, 3200, 5500),
        ("Bridge crane 5-ton 40ft", "ea", 1, 2, 12000, 22000),
        ("End truck assembly", "ea", 1, 4, 1800, 3200),
        ("Electric chain hoist 2-ton", "ea", 1, 4, 1400, 2800),
        ("Runway beam W12x26 20ft", "ea", 2, 8, 650, 1100),
    ],
    "dock": [
        ("Hydraulic dock leveler 6x8", "ea", 1, 4, 4500, 7500),
        ("Dock seal compression", "ea", 2, 6, 800, 1400),
        ("Vehicle restraint RHB", "ea", 1, 4, 2200, 3800),
        ("Dock bumpers molded 24in", "ea", 4, 12, 120, 250),
        ("Dock shelter retractable", "ea", 1, 3, 3500, 5800),
    ],
    "modular": [
        ("Wall panels 4x8 insulated", "ea", 10, 40, 180, 320),
        ("Vinyl flooring panels", "sqft", 200, 800, 4, 9),
        ("Steel door frame 36in", "ea", 2, 6, 280, 450),
        ("Drop ceiling tiles 2x4", "ea", 40, 120, 6, 14),
        ("Electrical package 20A", "ea", 1, 4, 1200, 2200),
    ],
    "safety": [
        ("Rack end guards double", "ea", 4, 16, 85, 160),
        ("Column protectors 12in", "ea", 8, 30, 45, 90),
        ("Safety netting 20x10", "ea", 2, 6, 350, 600),
        ("Floor marking tape 3in yellow", "roll", 6, 20, 18, 35),
        ("Steel bollards 42in", "ea", 2, 8, 180, 320),
    ],
    "rental": [
        ("Forklift 5,000 lb rental", "week", 1, 8, 450, 750),
        ("Scissor lift 26ft rental", "week", 1, 6, 380, 620),
        ("Boom lift 60ft rental", "week", 1, 4, 900, 1500),
        ("Telehandler 8k rental", "week", 1, 4, 650, 1100),
        ("Electric pallet jack rental", "week", 1, 12, 150, 280),
    ],
}

STATUSES = ["delivered", "delivered", "delivered", "ordered", "ordered", "pending", "pending", "partial", "partial", "cancelled"]

NOTES_POOL = [
    "", "", "", "", "", "",  # 60% no notes
    "Rush order — needed on-site ASAP",
    "Partial delivery accepted, remainder backordered",
    "Backordered — ETA pushed 2 weeks",
    "Freight prepaid by supplier",
    "Confirm dimensions before shipping",
    "Site contact: foreman Mike",
    "Deliver to loading dock B",
    "Hold for inspection before install",
    "Price includes delivery",
    "Net 30 terms approved",
    "Matched to original PO specs",
    "Replacement for damaged units",
    "Quote valid 30 days",
    "Coordinating with GC on delivery window",
]

JOB_IDS = [f"JOB-{i:03d}" for i in range(1, 13)]

NOW = datetime.now(timezone.utc)


def random_date_last_18_months():
    days_ago = random.randint(1, 540)
    return NOW - timedelta(days=days_ago)


def seed():
    init_db()
    suppliers = load_suppliers()
    total = 0
    skipped = 0

    for s in suppliers:
        existing = get_orders(s["id"])
        if existing:
            print(f"  Skip {s['name']} — already has {len(existing)} orders")
            skipped += 1
            continue

        items = CATEGORY_ITEMS.get(s["category"], CATEGORY_ITEMS["safety"])
        statuses = STATUSES[:]
        random.shuffle(statuses)

        for i in range(10):
            desc, unit, qty_lo, qty_hi, price_lo, price_hi = items[i % len(items)]
            status = statuses[i % len(statuses)]
            qty = random.randint(qty_lo, qty_hi)
            unit_price = round(random.uniform(price_lo, price_hi), 2)
            order_date = random_date_last_18_months()
            delivery_offset = timedelta(weeks=random.randint(2, 6))
            expected = order_date + delivery_offset

            delivered_date = None
            if status == "delivered":
                delivered_date = (expected + timedelta(days=random.randint(-3, 5))).strftime("%Y-%m-%d")
            elif status == "partial":
                delivered_date = (expected + timedelta(days=random.randint(0, 10))).strftime("%Y-%m-%d")

            job_id = random.choice(JOB_IDS) if random.random() > 0.3 else None

            create_order(s["id"], {
                "description": desc,
                "quantity": qty,
                "unit": unit,
                "unit_price": unit_price,
                "order_date": order_date.strftime("%Y-%m-%d"),
                "expected_delivery": expected.strftime("%Y-%m-%d"),
                "delivered_date": delivered_date,
                "status": status,
                "job_id": job_id,
                "notes": random.choice(NOTES_POOL),
            })
            total += 1

        print(f"  Seeded 10 orders for {s['name']}")

    print(f"\nDone — {total} orders created, {skipped} suppliers skipped.")


if __name__ == "__main__":
    seed()
