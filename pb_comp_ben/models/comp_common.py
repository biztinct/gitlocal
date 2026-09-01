# -*- coding: utf-8 -*-
"""Shared vocabulary for pb_comp_ben — groups, switches, labels, small helpers.

One file so that the facade, the models, the cron and the portal controller all
read the SAME constant rather than three spellings of it (MF31, and the reason
`pip_common` exists in P6).

THE WORDS ON SCREEN ARE HERE TOO. "Package", "Award", "Cut-off" — never
"snapshot", "batch", "config parameter" or "component code". The screens this
module ships are read by an HR lead and by the employee whose money it is.
"""

import logging

from odoo import _

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- the ladder
GROUP_USER = 'pb_comp_ben.group_comp_user'
GROUP_HEAD = 'pb_comp_ben.group_comp_head'

# ---------------------------------------------------------------- the dials
#: Every switch defaults IN CODE. A `noupdate="1"` record for a switch freezes
#: whatever a test run left behind, because the next upgrade never corrects it
#: (P5/P6 wrote the same thing down).
P_LETTER_SEND = 'pb_comp_ben.letter_send'        # email an award letter
P_REMINDERS = 'pb_comp_ben.calendar_reminders'   # cut-off reminder mail
P_FINANCE_PACK = 'pb_comp_ben.finance_pack'      # build the pack on approval
P_FINANCE_EMAIL = 'pb_comp_ben.finance_email'    # where the pack is sent
P_INCENTIVE_CODE = 'pb_comp_ben.incentive_code'  # the pay component to feed
P_BANK_FORMAT = 'pb_comp_ben.bank_format'        # which bank layout to build
P_EMPLOYEE_VIEW = 'pb_comp_ben.employee_view'    # /my/compensation

#: Defaults. The three that SEND or WRITE ship OFF — the first night after an
#: install must not email a finance team a pack nobody asked for (R54: a switch
#: that is off and does not say so is reported as broken, so every screen that
#: depends on one says which way it is set).
DEFAULTS = {
    P_LETTER_SEND: '0',
    P_REMINDERS: '0',
    P_FINANCE_PACK: '0',
    P_FINANCE_EMAIL: '',
    P_INCENTIVE_CODE: 'INCENTV',
    P_BANK_FORMAT: '',
    P_EMPLOYEE_VIEW: '1',
}


def param(env, key):
    """The raw string of a switch, with this module's default behind it."""
    val = env['ir.config_parameter'].sudo().get_param(key, DEFAULTS.get(key, ''))
    return '' if val is False else str(val)


def flag(env, key):
    """A switch as a boolean. '0', '', 'false' and 'no' are all off."""
    return param(env, key).strip().lower() not in ('', '0', 'false', 'no', 'off')


# ------------------------------------------------------------------- labels
COMP_STATE_LABEL = {
    'draft': _('Being prepared'),
    'active': _('Current'),
    'superseded': _('Replaced'),
}

#: What a package line IS. The order is the order the portal prints them in,
#: because a person reads their pay before their perks.
COMP_KINDS = [
    ('earning', 'Pay'),
    ('statutory', 'Statutory contribution'),
    ('benefit', 'Benefit'),
    ('perquisite', 'Perk'),
    ('bonus', 'Variable'),
]
COMP_KIND_LABEL = dict(COMP_KINDS)
COMP_KIND_ORDER = [k for k, _lbl in COMP_KINDS]

#: How often a package line is paid, and what one year of it is worth.
COMP_PERIODS = [
    ('monthly', 'Every month'),
    ('yearly', 'Once a year'),
    ('one_time', 'One-off'),
]
PERIOD_MULTIPLIER = {'monthly': 12.0, 'yearly': 1.0, 'one_time': 0.0}

INCENTIVE_KINDS = [
    ('bonus', 'Bonus'),
    ('incentive', 'Incentive'),
    ('spot', 'Spot award'),
]
INCENTIVE_KIND_LABEL = dict(INCENTIVE_KINDS)

#: The approval ladder. `refused` is the dead end the mixin already knows about.
INCENTIVE_STATES = [
    ('draft', 'Being prepared'),
    ('submitted', 'Waiting for approval'),
    ('approved', 'Approved'),
    ('refused', 'Not approved'),
]
INCENTIVE_STATE_LABEL = dict(INCENTIVE_STATES)

#: What has HAPPENED to an approved award. Deliberately a second column and not
#: more states on the chain: the chain answers "was it agreed", this answers
#: "has the money moved", and one field trying to say both is how a board ends
#: up unable to show an approved award that has not been paid.
FULFILMENT = [
    ('pending', 'Approved'),
    ('letter', 'Letter sent'),
    ('queued', 'In the next pay run'),
    ('paid', 'Paid'),
]
FULFILMENT_LABEL = dict(FULFILMENT)

BENEFIT_KINDS = [
    ('health', 'Health insurance'),
    ('life', 'Life insurance'),
    ('wellness', 'Wellness'),
    ('other', 'Other'),
]
BENEFIT_KIND_LABEL = dict(BENEFIT_KINDS)

#: The letter type P0 already seeds a template for
#: (`pb_lifecycle/data/letter_template_data.xml:64`). Nothing new is minted.
LETTER_TYPE = 'incentive'

#: A run may only be fed while it is still being built. Past this it is in
#: somebody's approval queue and a new payslip line is a number that changed
#: under an approver — the money rail this phase is most careful about.
FEEDABLE_RUN_STATES = ('draft', 'level0')


def counted(n, one, many):
    """"1 award" / "3 awards" — never "3 award(s)" (R46)."""
    return '%s %s' % (n, one if n == 1 else many)


def money(amount, currency=None):
    """A number a person reads. No currency conversion happens anywhere in this
    module: on this database every rate is 1.0, so `_convert` is a silent no-op
    and would print 32,000,000 ₫ as "32,000,000 USD" (R23). Amounts are always
    shown in the currency they were recorded in."""
    try:
        val = float(amount or 0.0)
    except (TypeError, ValueError):
        val = 0.0
    sym = getattr(currency, 'symbol', '') or ''
    return ('{:,.0f} {}'.format(val, sym)).strip()
