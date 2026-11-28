# -*- coding: utf-8 -*-
"""PSCHEME P1 F.1 — the person's "Pay scheme" block on the employee side panel.

The panel (`pb_employee_vault`) draws groups of rows. The old read-only rows
"Paid by" / "Advance paid by" leave the "Pay setup" group; a group of its own
kind (`pb_scheme`) takes their place, carrying the `person_scheme` payload the
block and the "Change pay scheme" dialog draw from — the same way the Bank
block is a group of kind `pb_bank` (`pb_employee_bank_panel/models/
bank_panel.py`). `rows` stay what the generic renderer would have drawn, so
the Form builder's screen rules still see the same field names.

Who sees it: exactly whoever saw the "Paid by" rows — the panel is HR-only
(`_vault_is_hr`, F.5). The label "Payroll country" becomes "Country of work".
"""

import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

GROUP = 'pb_scheme'
OLD_ROWS = ('pb_paid_by_id', 'pb_paid_by_advance_id')


class PbPeoplePersonScheme(models.AbstractModel):
    _inherit = 'pb.people'

    @api.model
    def _e360_details(self, emp, unmask, vietnam=None):
        tabs = super()._e360_details(emp, unmask, vietnam=vietnam)
        pay = list(tabs.get('pay') or [])
        for group in pay:
            if group.get('key') != 'setup':
                continue
            rows = []
            for row in group.get('rows') or []:
                if row.get('key') in OLD_ROWS:
                    continue
                if row.get('key') == 'payroll_country':
                    row = dict(row, label=_("Country of work"))
                rows.append(row)
            group['rows'] = rows
            group['filled'] = sum(1 for r in rows if not r.get('empty'))
        pay = [g for g in pay if g.get('key') != 'setup' or g.get('rows')]
        block = None
        try:
            block = self.env['pb.scheme.board'].person_scheme(emp.id)
        except Exception:                           # noqa: BLE001
            # a pay scheme block must never cost anybody the side panel
            _logger.warning('Side panel: the pay scheme block could not be '
                            'built for employee %s', emp.id, exc_info=True)
        if block and block.get('found'):
            main = block.get('main') or {}
            advance = block.get('advance') or {}
            rows = [
                {'key': 'pb_paid_by_id', 'label': _("Pay scheme"),
                 'value': main.get('name') or None, 'empty': not main},
                {'key': 'pb_paid_by_advance_id', 'label': _("Mid-month advance"),
                 'value': advance.get('name') or None, 'empty': not advance},
            ]
            group = {
                'key': GROUP, 'kind': GROUP, 'title': _("Pay scheme"),
                'icon': 'banknote', 'rows': rows,
                'filled': sum(1 for r in rows if not r['empty']),
                'pb_scheme': block,
            }
            # first in the tab when the drawer leads with the Vietnamese
            # groups; right after "Pay setup" otherwise
            at = next((i + 1 for i, g in enumerate(pay) if g.get('key') == 'setup'), 0)
            pay.insert(at, group)
        tabs['pay'] = pay
        return tabs
