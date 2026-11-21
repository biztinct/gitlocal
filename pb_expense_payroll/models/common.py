# -*- coding: utf-8 -*-
"""Shared words and small helpers of "claims paid in pay" (WDGAP S6-C).

`pb_trip_advance` imports from here too (the unspent-advance deduction rides
the same appended-lines machinery), so the names below are a contract.
"""
from odoo import fields

#: How an approved claim is paid back (company setting and per-claim stamp).
PAY_ROUTES = [
    ('finance', 'By finance'),
    ('payrun', 'In the next pay run'),
]

#: The kinds of line this module family appends after a scheme's own lines.
EXTRA_KINDS = [
    ('claim', 'Claim paid back'),
    ('advance', 'Trip advance taken back'),
]

#: Line codes. Not a pay scheme's code (a scheme never declares them), and
#: deliberately clear of the full-and-final prefixes: a claim must never be
#: read as health insurance (MED*/HI*) or as an advance (ADV*/LOAN*/TAM*); the
#: unspent-advance deduction IS an advance, so it starts with ADV.
CLAIM_CODE = 'PBEXPBACK'
ADVANCE_CODE = 'ADVPBTRIP'

#: Appended lines come after every pay item of the scheme.
LINE_SEQUENCE = 9500

#: Payslip states while a payslip is still being worked out.
COMPUTING_STATES = ('draft', 'verify')
#: Payslip states that mean "this payslip has been paid".
DONE_STATES = ('done', 'paid')
#: A reservation that still counts (held by a payslip, or paid).
LIVE_STATES = ('reserved', 'paid')

#: Server-only sentinel for a sanctioned write of a reservation or a claim's
#: pay fields. A JSON-RPC call cannot put this OBJECT in a context, so the
#: guards that check it cannot be forged from a browser.
WRITE_TOKEN = object()
TOKEN_KEY = 'pb_expense_payroll_write'


def month_of(day):
    day = fields.Date.to_date(day) if day else None
    return day.replace(day=1) if day else None


def scheme_asks_file(env, config):
    """Does this pay scheme take a PAY DATA FILE?

    The same predicate the Run payroll screen uses to show its file step
    (S5-B `_file_schemes`): the spreadsheet lane is switched on and at least
    one pay item is bound to a column of the file. Those payslips are made
    by the file path, which this module does not change."""
    if not config:
        return False
    config = config.sudo()
    if not getattr(config, 'source_excel_enabled', True):
        return False
    if 'hr.formula.rule.source' not in env:
        return False
    sources = env['hr.formula.rule.source'].sudo().search(
        [('kind', '=', 'excel'), ('rule_id.config_id', '=', config.id)])
    return any((s.key or '').strip() for s in sources)


def scheme_pays(env, employee, config, on_date):
    """Is `config` the scheme this person is paid by on that day? Asked of
    the scheme map for the scheme's own kind of cycle; a map that names
    nobody answers yes (cloned from pb_loans `_pb_scheme_pays`)."""
    Map = env.get('pb.scheme.map')
    if Map is None:
        return True
    try:
        answer = Map.sudo().resolve(employee, config.cycle_type or 'any', on_date) or {}
    except Exception:       # noqa: BLE001 — a resolver never stops a payslip
        return True
    other = answer.get('config_id') or 0
    return not other or other == config.id
