# -*- coding: utf-8 -*-
"""FLEET P5 — every judgement about money, a month, and a customer's standing.

WHY THIS FILE EXISTS AND WHAT IS DELIBERATELY NOT IN IT (rail R6). Everything
below is a pure function over plain values: no records, no cursor, no clock of
its own. That is not tidiness — it is the only way the arithmetic that decides
what a customer is charged can be TESTED at all, because the counts it works
from live on somebody else's database and the invoice it produces is a PDF.
`billing_service.py` next door does the reading, the writing and the sending;
this file makes the decisions and can be run in a shell.

THE THREE PRICE STRUCTURES ARE THE OWNER'S RULING, not a guess: a plan charges
per active employee per month, or per payslip produced in the month, or a flat
monthly price by employee band. Every customer is MEASURED for both counts
whatever their plan says, because a plan can change and last month's reading
cannot be taken again.

MONEY IS ROUNDED BY THE CURRENCY, NEVER BY PYTHON. Vietnamese dong has no
decimal places at all, so `round(x, 2)` on a dong figure produces a number no
bank statement will ever show and a total that does not equal the sum of its
lines. Every amount here goes through `round_money`, which is handed the
currency's own rounding step.
"""
from datetime import date, timedelta

# =============================================================================
# The vocabulary
# =============================================================================

#: The three price structures, in the words the owner used.
PRICING = ('per_employee', 'per_payslip', 'flat_tier')

PRICING_LABEL = {
    'per_employee': "Per employee, each month",
    'per_payslip': "Per payslip produced, each month",
    'flat_tier': "One monthly price, by company size",
}

#: What an invoice can be. `overdue` is a state and not a computed flag on
#: purpose: the day it turned overdue is what the reminders count from.
INVOICE_STATES = ('draft', 'sent', 'paid', 'overdue', 'void')

#: A customer's standing. The first five are the platform's own lifecycle
#: (P0–P2); the last three are what this phase adds.
TENANT_STATES = ('draft', 'provisioning', 'live', 'error', 'decommissioned',
                 'trial', 'suspended', 'pending_deletion')

#: THE STATES IN WHICH A CUSTOMER IS STILL A CUSTOMER — has a database, is
#: backed up, is kept in step, is measured and is billed. A suspended customer
#: is very much in this list: their people cannot get in, and that is exactly
#: when losing their backups would be unforgivable.
SERVING_STATES = ('live', 'trial', 'suspended', 'pending_deletion')

#: Which moves are allowed, and every one of them is a person pressing
#: something. The pairs left out are the point: nothing goes straight from
#: `suspended` to `decommissioned`, and nothing at all comes back from
#: `decommissioned`, because that database is gone.
STATE_MOVES = {
    ('trial', 'live'),               # "Convert to a paying customer"
    ('trial', 'suspended'),          # the trial ran out and nobody converted
    ('trial', 'pending_deletion'),
    ('live', 'suspended'),
    ('live', 'pending_deletion'),
    ('suspended', 'live'),           # "Resume"
    ('suspended', 'trial'),          # resumed a customer who was still trialling
    ('suspended', 'pending_deletion'),
    ('pending_deletion', 'live'),    # "Do not delete after all"
    ('pending_deletion', 'suspended'),
}

#: How long a customer's data is kept after somebody schedules its deletion.
#: Nothing deletes it when the clock runs out — the clock is a promise to the
#: customer and a reminder to the owner; the deletion itself is still the
#: offboard button with a typed confirmation.
DEFAULT_RETENTION_DAYS = 30

#: The billing calendar, all overridable as settings.
DEFAULT_DUE_DAYS = 14
DEFAULT_REMINDER_DAYS = (3, 10)
DEFAULT_SUSPEND_AFTER_DAYS = 14
DEFAULT_TRIAL_DAYS = 14
#: How many days after a trial ends before the customer becomes a suspend
#: candidate. Somebody who forgot to press "Convert" on a Friday should not
#: come back to a locked door on Monday.
TRIAL_GRACE_DAYS = 3
#: A trial customer sees the countdown bar for this many days at the end.
TRIAL_WARN_DAYS = 7
#: The share of the employee limit at which the customer is warned.
SEAT_NEAR_PCT = 0.9

#: The settings a customer's own database is told about their standing. Kept
#: here — beside the payload that fills them — rather than in the service, so
#: the provisioning step and the push cannot drift apart on a spelling.
T_ACCESS = 'pb_tenancy.access'
T_ACCESS_TEXT = 'pb_tenancy.access_text'
T_TRIAL_ENDS = 'pb_tenancy.trial_ends'
T_PLAN_NAME = 'pb_tenancy.plan_name'
T_SEAT_LIMIT = 'pb_tenancy.seat_limit'
T_INVOICES = 'pb_tenancy.invoices'


# =============================================================================
# Money
# =============================================================================

def round_money(amount, rounding=0.01):
    """Round to the currency's own step. 1.0 for dong, 0.01 for dollars.

    Not `round(x, 2)`: a dong amount with two decimal places is a number that
    cannot be paid, and a subtotal rounded differently from its lines is a
    total that does not add up on the customer's screen.
    """
    try:
        step = float(rounding or 0.01)
    except (TypeError, ValueError):
        step = 0.01
    if step <= 0:
        step = 0.01
    try:
        value = float(amount or 0.0)
    except (TypeError, ValueError):
        return 0.0
    # +1e-9 defeats the classic binary-floating-point near-miss (2.675/0.01)
    # without moving any figure a person could notice.
    return round(round(value / step + 1e-9) * step, 10)


def decimals_for(rounding=0.01):
    """How many decimal places that rounding step implies. 1.0 -> 0."""
    try:
        step = float(rounding or 0.01)
    except (TypeError, ValueError):
        step = 0.01
    if step >= 1:
        return 0
    places = 0
    while step < 1 and places < 6:
        step *= 10
        places += 1
    return places


def money(amount, symbol='', rounding=0.01, position='after'):
    """"12,400,000 ₫" — a figure a person can read out loud.

    Thousands separators always, the currency symbol always, and the number of
    decimal places the CURRENCY says rather than the number Python defaults to.
    """
    places = decimals_for(rounding)
    value = round_money(amount, rounding)
    text = '{:,.{p}f}'.format(value, p=places)
    sym = (symbol or '').strip()
    if not sym:
        return text
    return ('%s%s' % (sym, text)) if position == 'before' else ('%s %s' % (text, sym))


def qty_text(qty):
    """A quantity without a pointless ".0" behind it."""
    try:
        value = float(qty or 0)
    except (TypeError, ValueError):
        return '0'
    if abs(value - round(value)) < 1e-9:
        return '{:,}'.format(int(round(value)))
    return '{:,.2f}'.format(value)


# =============================================================================
# Periods
# =============================================================================

def month_start(day):
    """The first of the month `day` falls in."""
    return date(day.year, day.month, 1)


def month_end(period):
    """The last day of the month that starts at `period`."""
    if period.month == 12:
        nxt = date(period.year + 1, 1, 1)
    else:
        nxt = date(period.year, period.month + 1, 1)
    return nxt - timedelta(days=1)


def next_month(period):
    if period.month == 12:
        return date(period.year + 1, 1, 1)
    return date(period.year, period.month + 1, 1)


def prev_month(period):
    if period.month == 1:
        return date(period.year - 1, 12, 1)
    return date(period.year, period.month - 1, 1)


MONTH_NAMES = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
               'August', 'September', 'October', 'November', 'December')


def period_label(period):
    """"September 2026"."""
    if not period:
        return ''
    return '%s %d' % (MONTH_NAMES[period.month - 1], period.year)


def month_closed(period, today):
    """Is the month that starts at `period` over?

    An invoice raised mid-month is an invoice for a month that has not finished
    happening, and the counts on it will be wrong by whatever comes next. It is
    allowed — the owner may genuinely want to bill early — but it is allowed on
    purpose, with a warning, rather than by accident.
    """
    return bool(period and today and today > month_end(period))


# =============================================================================
# What a plan charges
# =============================================================================

def pick_tier(tiers, employees):
    """The band a company of this size falls in, or None.

    Bands are "up to N employees". The LAST band is open-ended however small
    its number is, because a plan whose top band is "up to 200" must still be
    able to invoice the customer who hired their 201st person — silently
    charging nothing would be worse than charging the top band.
    """
    rows = sorted([t for t in (tiers or []) if t is not None],
                  key=lambda t: (t.get('up_to') or 0))
    if not rows:
        return None
    for tier in rows:
        if employees <= (tier.get('up_to') or 0):
            return tier
    return rows[-1]


def price_for(plan, employees, payslips):
    """The lines one customer's invoice carries this month.

    Returns `{'lines': [...], 'problem': '', 'nothing_to_bill': bool}`.
    A `problem` is a sentence for the person looking at the preview — a plan
    with no price bands, an unknown price structure — and it is never an
    exception, because one broken plan must not stop the other eleven invoices
    from being previewed.
    """
    plan = plan or {}
    pricing = plan.get('pricing')
    name = (plan.get('name') or 'Payobook').strip()
    rounding = plan.get('rounding') or 0.01
    price = float(plan.get('price') or 0.0)
    employees = max(0, int(employees or 0))
    payslips = max(0, int(payslips or 0))

    if pricing == 'per_employee':
        lines = [{
            'label': '%s plan — employees' % name,
            'detail': 'Employees on Payobook at the end of the month',
            'qty': employees, 'unit_price': price,
            'amount': round_money(employees * price, rounding),
        }]
        return {'lines': lines, 'problem': '',
                'nothing_to_bill': employees == 0}

    if pricing == 'per_payslip':
        lines = [{
            'label': '%s plan — payslips produced' % name,
            'detail': 'Payslips produced during the month',
            'qty': payslips, 'unit_price': price,
            'amount': round_money(payslips * price, rounding),
        }]
        return {'lines': lines, 'problem': '',
                'nothing_to_bill': payslips == 0}

    if pricing == 'flat_tier':
        tier = pick_tier(plan.get('tiers'), employees)
        if not tier:
            return {'lines': [], 'nothing_to_bill': True, 'problem': (
                "The %s plan charges one price by company size, but it has no "
                "size bands yet. Add at least one band on the Plans tab."
                % name)}
        up_to = int(tier.get('up_to') or 0)
        band = ('up to %s employees' % qty_text(up_to)) if up_to else 'any size'
        lines = [{
            'label': '%s plan — monthly price (%s)' % (name, band),
            'detail': '%s employees on Payobook at the end of the month'
                      % qty_text(employees),
            'qty': 1, 'unit_price': float(tier.get('price') or 0.0),
            'amount': round_money(tier.get('price') or 0.0, rounding),
        }]
        return {'lines': lines, 'problem': '', 'nothing_to_bill': False}

    return {'lines': [], 'nothing_to_bill': True, 'problem': (
        "The %s plan does not say how it charges. Pick a price structure on "
        "the Plans tab." % name)}


def invoice_totals(lines, vat_pct=0.0, rounding=0.01):
    """Subtotal, tax and total — each rounded by the currency, in that order.

    The subtotal is rounded BEFORE the tax is worked out, so the tax on the
    invoice is the tax on the number printed above it. Doing it the other way
    round produces a total that is off by one dong and an argument nobody can
    win.
    """
    subtotal = round_money(sum(float(l.get('amount') or 0.0)
                               for l in (lines or [])), rounding)
    try:
        pct = float(vat_pct or 0.0)
    except (TypeError, ValueError):
        pct = 0.0
    vat_amount = round_money(subtotal * pct / 100.0, rounding)
    return {
        'subtotal': subtotal,
        'vat_pct': pct,
        'vat_amount': vat_amount,
        'total': round_money(subtotal + vat_amount, rounding),
    }


# =============================================================================
# What happens to an invoice as the days pass
# =============================================================================

def next_state(invoice, today, due_days=DEFAULT_DUE_DAYS,
               reminder_days=DEFAULT_REMINDER_DAYS,
               suspend_after=DEFAULT_SUSPEND_AFTER_DAYS):
    """One invoice, one day, one decision.

    Returns `{'state', 'changed', 'days_overdue', 'remind', 'reminder_no',
    'suspend_candidate'}`.

    THE REMINDERS ARE COUNTED, NOT TIMED. `reminder_count` on the record is
    what decides whether the +3 note has already gone, so a cron that runs
    twice on the same morning — or a box that was switched off for a week —
    sends each reminder exactly once rather than one per run or none at all.
    """
    inv = invoice or {}
    state = inv.get('state') or 'draft'
    out = {'state': state, 'changed': False, 'days_overdue': 0,
           'remind': False, 'reminder_no': 0, 'suspend_candidate': False}
    if state in ('paid', 'void', 'draft'):
        return out
    due = inv.get('due_date')
    if not due or not today:
        return out
    days = (today - due).days
    if days <= 0:
        return out
    out['days_overdue'] = days
    if state == 'sent':
        out['state'] = 'overdue'
        out['changed'] = True
    sent_count = int(inv.get('reminder_count') or 0)
    steps = sorted(int(d) for d in (reminder_days or ()))
    due_now = [i + 1 for i, d in enumerate(steps) if days >= d]
    if due_now and sent_count < due_now[-1]:
        out['remind'] = True
        out['reminder_no'] = sent_count + 1
    if suspend_after and days >= int(suspend_after):
        out['suspend_candidate'] = True
    return out


def due_date_for(issued_on, due_days=DEFAULT_DUE_DAYS):
    if not issued_on:
        return None
    return issued_on + timedelta(days=int(due_days or DEFAULT_DUE_DAYS))


def invoice_number(prefix, period, seq):
    """"PB-2026-09-0001" — readable, sortable, and unique inside a year."""
    pre = (prefix or 'PB').strip() or 'PB'
    if not period:
        return '%s-%04d' % (pre, int(seq or 1))
    return '%s-%d-%02d-%04d' % (pre, period.year, period.month, int(seq or 1))


# =============================================================================
# Trials and seats
# =============================================================================

def trial_phase(trial_ends, today, warn_days=TRIAL_WARN_DAYS):
    """Where a trial stands: `none`, `ok`, `ending` or `ended`.

    An unset date reads as `False` on this framework rather than `None`
    (ledger F23), so the test is falsiness and never identity.
    """
    if not trial_ends or not today:
        return {'phase': 'none', 'days_left': 0}
    days = (trial_ends - today).days
    if days < 0:
        return {'phase': 'ended', 'days_left': days}
    if days <= int(warn_days or TRIAL_WARN_DAYS):
        return {'phase': 'ending', 'days_left': days}
    return {'phase': 'ok', 'days_left': days}


def trial_sentence(days_left):
    """The countdown, in the words a customer reads on their own screen."""
    if days_left is None:
        return ''
    if days_left <= 0:
        return "Your Payobook trial ends today."
    if days_left == 1:
        return "Your Payobook trial ends tomorrow."
    return "Your Payobook trial ends in %d days." % int(days_left)


def seat_verdict(limit, count, near_pct=SEAT_NEAR_PCT):
    """`ok`, `near` or `full` — and a limit of nought means no limit at all."""
    try:
        limit = int(limit or 0)
    except (TypeError, ValueError):
        limit = 0
    try:
        count = int(count or 0)
    except (TypeError, ValueError):
        count = 0
    if limit <= 0:
        return {'verdict': 'ok', 'limit': 0, 'count': count, 'left': -1,
                'pct': 0}
    left = limit - count
    pct = int(round(min(count, limit) * 100.0 / limit)) if limit else 0
    if count >= limit:
        return {'verdict': 'full', 'limit': limit, 'count': count, 'left': 0,
                'pct': 100}
    if count >= limit * float(near_pct or SEAT_NEAR_PCT):
        return {'verdict': 'near', 'limit': limit, 'count': count,
                'left': left, 'pct': pct}
    return {'verdict': 'ok', 'limit': limit, 'count': count, 'left': left,
            'pct': pct}


def seat_refusal(limit, count):
    """Why the employee was not added, and what to do about it.

    ZERO DEAD ENDS: the sentence names the number, the plan and the person who
    can change it. "Limit reached" on its own is a wall.
    """
    return ("Your plan allows %s employees and you already have %s. "
            "Ask your Payobook administrator to move you to a larger plan, "
            "or archive an employee who has left."
            % (qty_text(limit), qty_text(count)))


# =============================================================================
# Moving a customer from one standing to another
# =============================================================================

def state_transition(frm, to):
    """Is this move allowed? Returns `(ok, reason)`."""
    if frm == to:
        return False, "They are already %s." % to.replace('_', ' ')
    if to not in TENANT_STATES:
        return False, "There is no such standing."
    if frm == 'decommissioned':
        return False, ("That customer has been decommissioned — there is no "
                       "database left to change.")
    if (frm, to) in STATE_MOVES:
        return True, ''
    return False, ("A customer cannot go from %s to %s."
                   % (frm.replace('_', ' '), to.replace('_', ' ')))


def access_payload(state, reason='', trial_ends=None, plan_name='',
                   seat_limit=0):
    """What a customer's own database is told about their standing.

    Four settings and nothing else, and every one of them is a STRING, because
    that is all `ir.config_parameter` holds. `open` and `suspended` are the only
    two answers to "may these people in": a trial customer is open, a customer
    scheduled for deletion is open, and there is deliberately no third door.
    """
    access = 'suspended' if state == 'suspended' else 'open'
    text = (reason or '').strip()
    if access == 'suspended' and not text:
        text = ("Your Payobook access is paused. Please contact your "
                "administrator.")
    return {
        'access': access,
        'access_text': text if access == 'suspended' else '',
        'trial_ends': trial_ends.isoformat() if trial_ends else '',
        'plan_name': plan_name or '',
        'seat_limit': str(int(seat_limit or 0)),
    }
