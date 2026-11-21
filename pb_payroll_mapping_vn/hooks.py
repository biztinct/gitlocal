# -*- coding: utf-8 -*-
"""Make sure the contract components exist before the first contract does.

`hr.contract.create` gives every new contract one line per advantage template.
A template that arrives AFTER a contract therefore leaves that contract without
a line, and the amount has nowhere to be typed — so the templates have to be on
the database from the moment this module is installed.

They used to be an XML data file. They are a hook instead because the list is
nineteen entries long and lives in `vn_profile.CONTRACT_COMPONENTS`, which is
also what the applier and the spreadsheet builder read: an XML copy of it would
be a second list to keep in step, and the first time the two disagreed nobody
would notice until an allowance stopped being paid.
"""

import logging

from .models.vn_profile import CONTRACT_COMPONENTS

_logger = logging.getLogger(__name__)


def ensure_advantage_templates(env):
    """One `hr.contract.advantage.template` per amount the profile names.

    Idempotent on the CODE, which is what the payroll engine matches on. An
    existing template is left exactly as it is — its bounds may have been
    widened by hand, and overwriting that on every upgrade would undo somebody's
    decision every time they upgraded.
    """
    Template = env['hr.contract.advantage.template'].sudo()
    made = 0
    for code, label, upper in CONTRACT_COMPONENTS:
        if Template.search_count([('code', '=', code)]):
            continue
        Template.create({
            'name': label, 'code': code,
            'lower_bound': 0.0, 'upper_bound': upper,
            # NEVER a non-zero default: a default here is applied to EVERYBODY,
            # and that is how one leaver's leave payout once became a
            # company-wide allowance.
            'default_value': 0.0,
            'value_type': 'amount',
        })
        made += 1
    if made:
        _logger.info("pb_payroll_mapping_vn: created %s contract component(s).",
                     made)
    return made


def post_init_hook(env):
    ensure_advantage_templates(env)
