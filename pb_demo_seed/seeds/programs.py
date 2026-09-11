# -*- coding: utf-8 -*-
"""What runs around the five people all year: pay, benefits, recognition, leave.

FOUR SECTIONS, ONE RULE BETWEEN THEM: each exists because a screen in this
product is empty without it, and each carries the smallest amount of data that
makes that screen mean something.

* **Compensation** — what each person was actually offered, broken down, so the
  employee's own "what am I paid" page has something to show. It is NOT a second
  copy of the payroll: the payroll is computed from the pay scheme, and this is
  the letter they signed.
* **Benefits** — three plans and who is on them, including the family cover that
  the pay scheme's expatriate branch charges a premium for. The two agree on
  purpose: the manager is enrolled here AND has the health premium on his
  contract, because in real life those are the same fact recorded twice and a
  demo that shows only one of them invites the question of where the other is.
* **Recognition** — a closed quarter with a winner, and an open one with
  nominations still coming in. A recognition wall with nothing on it is worse
  than no recognition wall.
* **Leave** — allocations and a few days taken, so that the "paid days" figure
  in a payslip has something behind it rather than being a number somebody typed.
"""

import json
import logging

from odoo import fields

_logger = logging.getLogger(__name__)

#: What each person's package is made of. `(what it is, kind, amount, period)`.
#:
#: The amounts are a share of the monthly salary rather than round numbers
#: pulled out of the air, so the package and the payslip do not contradict each
#: other in front of somebody who adds them up.
PACKAGES = {
    'joiner': [
        ('Monthly salary', 'earning', 18000000.0, 'monthly'),
        ('Uniform allowance', 'earning', 500000.0, 'monthly'),
        ('Social, health and unemployment insurance — employer',
         'statutory', 3915000.0, 'monthly'),
        ('Thirteenth-month salary', 'bonus', 18000000.0, 'yearly'),
    ],
    'probation': [
        ('Monthly salary', 'earning', 26000000.0, 'monthly'),
        ('Uniform allowance', 'earning', 500000.0, 'monthly'),
        ('Transport allowance', 'earning', 1200000.0, 'monthly'),
        ('Social, health and unemployment insurance — employer',
         'statutory', 5655000.0, 'monthly'),
        ('Thirteenth-month salary', 'bonus', 26000000.0, 'yearly'),
    ],
    'pip': [
        ('Monthly salary', 'earning', 32000000.0, 'monthly'),
        ('Private health cover — employee', 'benefit', 1200000.0, 'monthly'),
        ('Phone allowance', 'earning', 500000.0, 'monthly'),
        ('Social, health and unemployment insurance — employer',
         'statutory', 6960000.0, 'monthly'),
        ('Sales incentive — on target', 'bonus', 96000000.0, 'yearly'),
    ],
    'fixed_term': [
        ('Monthly salary', 'earning', 12000000.0, 'monthly'),
        ('Uniform allowance', 'earning', 500000.0, 'monthly'),
        ('Social, health and unemployment insurance — employer',
         'statutory', 2610000.0, 'monthly'),
    ],
    'manager': [
        ('Monthly salary', 'earning', 85000000.0, 'monthly'),
        ('Private insurance allowance — expatriate', 'benefit', 6000000.0,
         'monthly'),
        ('Private health cover — employee', 'benefit', 2500000.0, 'monthly'),
        ('Private health cover — dependants', 'benefit', 3500000.0, 'monthly'),
        ('Phone allowance', 'earning', 1000000.0, 'monthly'),
        ('Transport allowance', 'earning', 3000000.0, 'monthly'),
        ('Thirteenth-month salary', 'bonus', 85000000.0, 'yearly'),
        ('Annual performance bonus — on target', 'bonus', 170000000.0, 'yearly'),
    ],
}

#: Who is on which plan, and who their cover extends to.
ENROLMENTS = [
    ('manager', 'Demo Family Health Cover',
     ['Spouse', 'Child, 12', 'Child, 9']),
    ('manager', 'Demo Group Life Cover', []),
    ('pip', 'Demo Personal Health Cover', []),
    ('probation', 'Demo Group Life Cover', []),
]


def build(ctx):
    _compensation(ctx)
    _benefits(ctx)
    _recognition(ctx)
    _leave(ctx)


# ======================================================================
def _compensation(ctx):
    people = ctx.get('people', {})
    for key, lines in PACKAGES.items():
        employee = people.get(key)
        if not employee:
            continue
        package = ctx.create('pb.employee.comp', {
            'employee_id': employee.id,
            # In force from the start of the month they joined, unless that is
            # in the future for somebody who joined last week — a package
            # dated after today reads as "not yet agreed".
            'effective_date': min(ctx.month_start(0), ctx.today),
            'state': 'active',
            'currency_id': ctx.company.currency_id.id,
            'note': 'Demo package, as offered.',
        }, label='Package — %s' % employee.name)
        for sequence, (name, kind, amount, period) in enumerate(lines):
            ctx.create('pb.employee.comp.line', {
                'comp_id': package.id,
                'sequence': (sequence + 1) * 10,
                'name': name,
                'kind': kind,
                'amount': amount,
                'period': period,
                'checked': True,
            }, label='%s — %s' % (employee.name, name))


def _benefits(ctx):
    people = ctx.get('people', {})
    plans = ctx.get('benefit_plans', {})
    for index, (key, plan_name, dependants) in enumerate(ENROLMENTS):
        employee = people.get(key)
        plan = plans.get(plan_name)
        if not (employee and plan):
            continue
        ctx.create('pb.benefit.enrollment', {
            'plan_id': plan.id,
            'employee_id': employee.id,
            'member_ref': 'DEMO-MEM-%04d' % (1001 + index),
            'start_date': ctx.month_start(-6),
            'state': 'active',
            'dependants_json': json.dumps(
                [{'name': d} for d in dependants]) if dependants else False,
        }, label='%s on %s' % (employee.name, plan_name))


def _recognition(ctx):
    """A quarter that was decided, and one still collecting.

    The decided one carries a cash award and the incentive it turned into, so
    the demo can follow one nomination all the way from "somebody wrote this
    about a colleague" to "it is on the next pay run".
    """
    people = ctx.get('people', {})
    values = {v.name: v for v in ctx.env['pb.company.value'].sudo().search([])}
    if not values:
        return
    value_list = list(values.values())

    closed = ctx.create('pb.rnr.cycle', {
        'name': 'Demo recognition — last quarter',
        'date_from': ctx.months(-6).replace(day=1),
        'date_to': ctx.months(-3).replace(day=1),
        'state': 'closed',
        'notes': 'Demo quarter, decided.',
    }, label='Recognition quarter — closed')

    open_cycle = ctx.create('pb.rnr.cycle', {
        'name': 'Demo recognition — this quarter',
        'date_from': ctx.months(-2).replace(day=1),
        'date_to': ctx.months(1).replace(day=1),
        'state': 'open',
        'notes': 'Demo quarter, still collecting.',
    }, label='Recognition quarter — open')

    stories = [
        ('manager', 'pip', 0, closed, 'done', 'awarded', 5000000.0, True,
         'Drove eleven hours to a flooded site on a Sunday and had the crew '
         'back on their feet by Tuesday. Nobody asked him to.'),
        ('pip', 'manager', 1, open_cycle, 'submitted', False, 0.0, False,
         'Stayed with a customer through a failed delivery and told them the '
         'truth about what went wrong before they asked.'),
        ('probation', 'manager', 4, open_cycle, 'manager', False, 0.0, False,
         'Reorganised the morning briefing so the casual crews get the same '
         'safety walkthrough as everybody else.'),
        ('joiner', 'pip', 3, open_cycle, 'draft', False, 0.0, False,
         'Three days in and already spotted a mislabelled batch in the trial '
         'plot records.'),
    ]
    for (nominee_key, nominator_key, value_index, cycle, state, outcome,
         award, winner, story) in stories:
        nominee = people.get(nominee_key)
        nominator = people.get(nominator_key)
        if not (nominee and nominator):
            continue
        nomination = ctx.create('pb.rnr.nomination', {
            'nominee_id': nominee.id,
            'nominator_id': nominator.id,
            'value_id': value_list[value_index % len(value_list)].id,
            'story': story,
            'submitted_at': fields.Datetime.now(),
            'state': state,
            'outcome': outcome or False,
            'decided_at': fields.Datetime.now() if outcome else False,
            'award_amount': award,
            'currency_id': ctx.company.currency_id.id,
            'cycle_id': cycle.id,
            'is_winner': winner,
            'public': state != 'draft',
        }, label='Nomination — %s' % nominee.name)

        if outcome == 'awarded' and award:
            incentive = ctx.create('pb.incentive', {
                'employee_id': nominee.id,
                'kind': 'spot',
                'amount': award,
                'currency_id': ctx.company.currency_id.id,
                'period_month': ctx.month_start(0),
                'reason': 'Quarterly recognition award.',
                'state': 'approved',
                'fulfilment': 'queued',
                'source': 'rnr',
                'requested_by_user_id': ctx.env.user.id,
            }, label='Award — %s' % nominee.name)
            nomination.sudo().incentive_id = incentive.id

    # One ordinary incentive that has nothing to do with recognition, so the
    # incentive screen is not a recognition screen wearing a different hat.
    referrer = people.get('probation')
    if referrer:
        ctx.create('pb.incentive', {
            'employee_id': referrer.id,
            'kind': 'bonus',
            'amount': 3000000.0,
            'currency_id': ctx.company.currency_id.id,
            'period_month': ctx.month_start(0),
            'reason': 'Referral bonus — the referred agronomist has passed '
                      'thirty days.',
            'state': 'approved',
            'fulfilment': 'queued',
            'source': 'manual',
            'requested_by_user_id': ctx.env.user.id,
        }, label='Referral bonus — %s' % referrer.name)

    if ctx.get('cycle_set') is None:
        ctx.set('cycle_set', True)


def _leave(ctx):
    """Allocations, and a few days actually taken.

    `try_create` throughout: leave is validated against working calendars,
    public holidays and allocation balances that differ from one database to
    the next, and a demo must not fail to load because a Tuesday turned out to
    be a holiday.
    """
    people = ctx.get('people', {})
    leave_type = ctx.env['hr.leave.type'].sudo().search(
        [('requires_allocation', '=', True)], limit=1)
    if not leave_type:
        return

    taken = {
        'pip': (-45, 3, 'Family wedding.'),
        'manager': (-30, 5, 'Annual leave.'),
        'probation': (-20, 1, 'Medical appointment.'),
    }
    for key, employee in people.items():
        # CREATED WITHOUT A STATE, THEN APPROVED. Odoo refuses an allocation
        # that is born already approved — "Incorrect state for new allocation"
        # — because approving is an act with an approver on it, not a column.
        # So it goes through the same door a real one does.
        allocation = ctx.try_create('hr.leave.allocation', {
            'name': 'Demo annual entitlement',
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'number_of_days': 12.0,
            'allocation_type': 'regular',
            'date_from': ctx.today.replace(month=1, day=1),
        }, label='Leave entitlement — %s' % employee.name)
        if not allocation:
            continue
        _approve(ctx, allocation)
        if key not in taken:
            continue
        offset, days, reason = taken[key]
        start = _weekday_on_or_after(ctx.days(offset))
        leave = ctx.try_create('hr.leave', {
            'name': reason,
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': start,
            'request_date_to': _weekday_on_or_after(start, extra=days - 1),
        }, label='Leave — %s' % employee.name)
        if leave:
            _approve(ctx, leave)


def _approve(ctx, record):
    """Walk a time-off record to approved, through whatever doors it has.

    The button names differ between an allocation and a request, and between
    one validation setting and another, so this tries the ones that exist and
    stops at the first that works. Failing to approve a demo leave record is
    not worth stopping a load for — it simply shows as waiting.
    """
    for action in ('action_confirm', 'action_approve', 'action_validate'):
        method = getattr(record, action, None)
        if not method:
            continue
        try:
            with ctx.env.cr.savepoint():
                method()
        except Exception as exc:                   # noqa: BLE001
            _logger.info('pb_demo_seed: %s on %s — %s',
                         action, record._name, exc)


def _weekday_on_or_after(day, extra=0):
    from datetime import timedelta
    day = day + timedelta(days=extra)
    while day.weekday() >= 5:
        day = day + timedelta(days=1)
    return day
