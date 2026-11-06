# -*- coding: utf-8 -*-
"""What the company owns, who has it, and what is waiting to come back.

THE REQUIREMENT THIS ANSWERS is the one on the asset sheet: physical things and
digital things in ONE register, every item with its own code and its own
history, cost in the local currency and in dollars, and a mandatory return
before anybody's last day is signed off.

SO THE SPREAD IS DELIBERATE. There is a spare laptop nobody has, one out for
repair, a laptop that was passed on rather than bought, two digital accounts
that will have to be switched off at exit, and one laptop still in the hands of
somebody who is leaving in six weeks. Every state in the register is occupied by
something a person can point at.

THE PROCUREMENT REQUEST IS NOT MADE HERE, and that is deliberate. Opening the
joiner's checklist raises it, because the checklist has a step that says to —
which is how a real joiner gets one. This file only makes sure the SPARE is
sitting there when that happens, so the request can propose it; the joining
builder then stops it half way, with the spare found and nothing handed over.
"""

#: `(code suffix, category code, what it is, model, cost VND, cost USD, state,
#:   who has it, bought months ago, reused)`
ASSETS = [
    ('LT-0001', 'LT', 'Laptop — Country Manager', 'Dell Latitude 7450',
     34000000.0, 1360.0, 'assigned', 'manager', -22, False),
    ('LT-0002', 'LT', 'Laptop — Field Operations', 'Lenovo ThinkPad T14',
     28000000.0, 1120.0, 'assigned', 'probation', -14, True),
    ('LT-0003', 'LT', 'Laptop — Commercial', 'HP ProBook 450',
     22000000.0, 880.0, 'assigned', 'pip', -30, False),
    ('LT-0004', 'LT', 'Laptop — fixed-term field technician',
     'Lenovo ThinkPad E14', 18000000.0, 720.0, 'assigned', 'fixed_term',
     -11, True),
    ('LT-0005', 'LT', 'Laptop — spare, Ho Chi Minh City office',
     'Lenovo ThinkPad E14', 18000000.0, 720.0, 'spare', None, -8, False),
    ('LT-0006', 'LT', 'Laptop — screen fault, with the supplier',
     'HP ProBook 450', 22000000.0, 880.0, 'repair', None, -26, False),
    ('PH-0001', 'PH', 'Mobile phone — Country Manager', 'Samsung Galaxy A55',
     9500000.0, 380.0, 'assigned', 'manager', -9, False),
    ('CC-0001', 'CC', 'Corporate card — Country Manager',
     'Techcombank Visa Business', 0.0, 0.0, 'assigned', 'manager', -20, False),
    ('SM-0001', 'SM', 'SIM card — field supervisor', 'Viettel postpaid',
     0.0, 0.0, 'assigned', 'probation', -14, False),
    ('EM-0001', 'EM', 'Email account — Country Manager', 'Workspace mailbox',
     0.0, 0.0, 'assigned', 'manager', -52, False),
    ('EM-0002', 'EM', 'Email account — fixed-term field technician',
     'Workspace mailbox', 0.0, 0.0, 'assigned', 'fixed_term', -11, False),
    ('LG-0001', 'LG', 'System login — fixed-term field technician',
     'Payobook account', 0.0, 0.0, 'assigned', 'fixed_term', -11, False),
    ('LG-0002', 'LG', 'System login — Country Manager', 'Payobook account',
     0.0, 0.0, 'assigned', 'manager', -52, False),
    ('SW-0001', 'SW', 'Design software licence — unassigned',
     'Annual single seat', 12000000.0, 480.0, 'spare', None, -4, False),
]


def build(ctx):
    categories = {c.code: c for c in ctx.env['pb.asset.category'].sudo()
                  .with_context(active_test=False).search([])}
    people = ctx.get('people', {})
    assets = {}

    for (code, category_code, name, model_name, cost, usd, state, owner_key,
         bought, reused) in ASSETS:
        category = categories.get(category_code)
        if not category:
            continue
        owner = people.get(owner_key) if owner_key else None
        bought_on = ctx.months(bought)
        asset = ctx.create('pb.asset', {
            'code': 'DEMO-%s' % code,
            'name': name,
            'category_id': category.id,
            'country_id': ctx.company.country_id.id,
            'state': state,
            'serial': _serial(category_code, code),
            'model_name': model_name,
            'is_reused': reused,
            'purchase_date': bought_on,
            'delivery_date': bought_on,
            # A warranty date only means anything on something physical, and
            # putting one on a mailbox is the kind of detail that makes a
            # demo look like it was filled in by a script.
            'warranty_end': (ctx.months(bought + 36)
                             if category.kind == 'tangible' and cost else False),
            'currency_id': ctx.company.currency_id.id,
            'cost': cost,
            'cost_usd': usd,
            'invoice_ref': 'DEMO-INV-%s' % code if cost else False,
            'supplier_note': 'Demo Workplace Supplies' if cost else False,
            'movable_note': 'Stays in Vietnam' if cost else False,
            'current_employee_id': owner.id if owner else False,
        }, label='%s (DEMO-%s)' % (name, code))
        assets[code] = asset

        if owner is not None and state == 'assigned':
            ctx.create('pb.asset.assignment', {
                'asset_id': asset.id,
                'employee_id': owner.id,
                'assigned_date': bought_on,
                'condition_out': 'Good' if not reused else 'Good, previously used',
                'receipt_confirmed': True,
                'state': 'open',
                'notes': 'Demo handover.',
            }, label='DEMO-%s → %s' % (code, owner.name))

    ctx.set('assets', assets)


def _serial(category_code, code):
    if category_code in ('EM', 'LG', 'PN', 'SW'):
        return 'demo.%s@example.com' % code.lower().replace('-', '.')
    return 'DMO%s' % code.replace('-', '')
