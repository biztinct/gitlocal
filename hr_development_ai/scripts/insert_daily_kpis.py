#!/usr/bin/env python3
"""
Insert DAILY KPI data for the current month to populate forecast chart.
Also adds weekly data for last 2 months for sparkline trends.
Run via: odoo shell < insert_daily_kpis.py
"""
import random
from datetime import date, timedelta

branch = env['bfsi.branch'].search([], limit=1)
if not branch:
    print("ERROR: No branch found"); exit()

print(f"Branch: {branch.name}")

employees = env['hr.employee'].search([
    ('branch_id', '=', branch.id),
    ('banker_type', 'not in', ['branch_manager', 'regional_manager']),
])
print(f"Found {len(employees)} bankers")

# Performance profiles per banker
profiles = {
    0: {'daily_rev': (15e6, 45e6), 'conv': (0, 3), 'meet': (1, 5), 'score': (80, 98)},  # star
    1: {'daily_rev': (8e6, 30e6),  'conv': (0, 2), 'meet': (0, 4), 'score': (60, 80)},  # solid
    2: {'daily_rev': (2e6, 15e6),  'conv': (0, 1), 'meet': (0, 2), 'score': (25, 50)},  # needs help
    3: {'daily_rev': (5e6, 25e6),  'conv': (0, 2), 'meet': (0, 3), 'score': (45, 70)},  # improving
    4: {'daily_rev': (6e6, 20e6),  'conv': (0, 2), 'meet': (0, 3), 'score': (50, 68)},  # average
}

today = date.today()
month_start = today.replace(day=1)

# Generate daily data for current month (up to today)
created = 0
KPI = env['bfsi.performance.kpi']

for idx, emp in enumerate(employees):
    p = profiles[idx % len(profiles)]
    print(f"\n  {emp.name}:")

    # --- DAILY data for current month ---
    d = month_start
    while d <= today:
        # Skip weekends
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue

        existing = KPI.search([
            ('employee_id', '=', emp.id),
            ('period_date', '=', d.strftime('%Y-%m-%d')),
        ], limit=1)

        if existing:
            d += timedelta(days=1)
            continue

        rev = random.uniform(*p['daily_rev'])
        conv = random.randint(*p['conv'])
        meet = random.randint(*p['meet'])
        score = random.uniform(*p['score'])
        dials = random.randint(15, 50)

        vals = {
            'employee_id': emp.id,
            'branch_id': branch.id,
            'period_date': d.strftime('%Y-%m-%d'),
            'period_type': 'daily',
            'overall_score': round(score, 1),
            'revenue': round(rev),
            'conversions': conv,
            'meetings_conducted': meet,
            'total_dials': dials,
            'connects': random.randint(5, int(dials * 0.4)),
            'conversion_rate': round(conv / max(1, meet) * 100, 1) if meet else 0,
        }

        try:
            KPI.create(vals)
            created += 1
        except Exception as e:
            print(f"    {d}: ERROR - {e}")

        d += timedelta(days=1)

    print(f"    Daily records created for current month")

    # --- WEEKLY data for prev 2 months (for sparkline) ---
    for weeks_ago in range(1, 9):
        wd = today - timedelta(weeks=weeks_ago)
        # Use Monday of that week
        wd = wd - timedelta(days=wd.weekday())

        existing = KPI.search([
            ('employee_id', '=', emp.id),
            ('period_date', '=', wd.strftime('%Y-%m-%d')),
        ], limit=1)

        if existing:
            continue

        # Weekly aggregated data
        rev = random.uniform(*p['daily_rev']) * 5  # ~5 working days
        conv = random.randint(*p['conv']) * 5
        meet = random.randint(*p['meet']) * 5
        score = random.uniform(*p['score'])

        vals = {
            'employee_id': emp.id,
            'branch_id': branch.id,
            'period_date': wd.strftime('%Y-%m-%d'),
            'period_type': 'weekly',
            'overall_score': round(score, 1),
            'revenue': round(rev),
            'conversions': conv,
            'meetings_conducted': meet,
            'total_dials': random.randint(80, 200),
            'connects': random.randint(20, 60),
            'conversion_rate': round(conv / max(1, meet) * 100, 1),
        }

        try:
            KPI.create(vals)
            created += 1
        except Exception as e:
            print(f"    week {wd}: ERROR - {e}")

    print(f"    Weekly records created for past 2 months")

env.cr.commit()
print(f"\n✅ Created {created} KPI records total!")
