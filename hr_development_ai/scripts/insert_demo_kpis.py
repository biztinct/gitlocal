#!/usr/bin/env python3
"""
Insert demo KPI data for the AI Performance Dashboard.
Run via: odoo shell < insert_demo_kpis.py
"""
import random
from datetime import date
from dateutil.relativedelta import relativedelta

branch = env['bfsi.branch'].search([], limit=1)
if not branch:
    print("ERROR: No branch found"); exit()

print(f"Branch: {branch.name} (ID: {branch.id})")

employees = env['hr.employee'].search([
    ('branch_id', '=', branch.id),
    ('banker_type', 'not in', ['branch_manager', 'regional_manager']),
])
print(f"Found {len(employees)} bankers")
if not employees:
    print("ERROR: No employees found"); exit()

# Target defaults
REV = 500000000  # 500M VND
CONV = 20
MEET = 40
DIALS = 200

target = env['bfsi.kpi.target'].search([('branch_id', '=', branch.id)], limit=1)
if target:
    REV = target.target_revenue or REV
    CONV = target.target_conversions or CONV
    MEET = target.target_meetings_conducted or MEET
    print(f"Using target: {target.name}")

# 4 months of data
today = date.today()
months = sorted([date(today.year, today.month, 1) - relativedelta(months=i) for i in range(4)])

profiles = [
    {'name': 'star',       'score': (80, 98), 'pct': (0.7, 1.2)},
    {'name': 'solid',      'score': (60, 82), 'pct': (0.4, 0.8)},
    {'name': 'needs_help', 'score': (25, 55), 'pct': (0.1, 0.4)},
    {'name': 'improving',  'score': (45, 75), 'pct': (0.3, 0.7)},
    {'name': 'average',    'score': (50, 70), 'pct': (0.35, 0.65)},
]

created = 0
for idx, emp in enumerate(employees):
    p = profiles[idx % len(profiles)]
    print(f"\n  {emp.name} -> {p['name']}")

    for mi, md in enumerate(months):
        if env['bfsi.performance.kpi'].search([
            ('employee_id', '=', emp.id),
            ('period_date', '=', md.strftime('%Y-%m-%d')),
        ], limit=1):
            print(f"    {md}: exists, skipping")
            continue

        score = min(100, random.uniform(*p['score']) + mi * 2.5)
        pct = random.uniform(*p['pct'])

        vals = {
            'employee_id': emp.id,
            'branch_id': branch.id,
            'period_date': md.strftime('%Y-%m-%d'),
            'period_type': 'monthly',
            'overall_score': round(score, 1),
            'revenue': round(REV * pct),
            'conversions': max(1, int(CONV * pct)),
            'meetings_conducted': max(1, int(MEET * pct)),
            'total_dials': max(10, int(DIALS * pct)),
            'connects': max(5, int(DIALS * pct * 0.3)),
            'conversion_rate': round(pct * 100, 1),
            'connect_rate': round(pct * 30, 1),
        }

        try:
            env['bfsi.performance.kpi'].create(vals)
            print(f"    {md}: score={score:.0f} rev={vals['revenue']:,} conv={vals['conversions']}")
            created += 1
        except Exception as e:
            print(f"    {md}: ERROR - {e}")

env.cr.commit()
print(f"\n✅ Created {created} KPI records!")
