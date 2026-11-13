# -*- coding: utf-8 -*-
"""ORG CHART P2 — the two fields the chart writes (ledger D2, D3).

Both are tracked, so every change lands in `mail.tracking.value` — that is
the side panel's History tab (D6) and, in P3, the time machine's past. No
migration: Many2one / Selection columns with no data to carry.

`coach_id` is deliberately NOT the dotted line: it is computed from the
manager and follows them (`hr_employee.py` `_compute_coach`), so a dotted
line kept there would be overwritten by the next move.
"""
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pb_dotted_manager_id = fields.Many2one(
        'hr.employee', string="Also reports to", tracking=True,
        index='btree_not_null', ondelete='set null',
        help="A second manager this person also works for, for example on a "
             "project or in a matrix team. Their main manager stays the one "
             "they report to. Shown as a dotted line on the org chart.")


class HrJob(models.Model):
    _inherit = 'hr.job'

    pb_manager_id = fields.Many2one(
        'hr.employee', string="Reports to on the org chart", tracking=True,
        index='btree_not_null', ondelete='set null',
        help="Who this open role will report to. The org chart shows the "
             "role under this person. When empty, the role sits under the "
             "manager of its department.")
    pb_reason = fields.Selection(
        [('growth', "Growth — new position"),
         ('backfill', "Backfill — someone is leaving"),
         ('cover', "Cover for leave")],
        string="Why this role is open", tracking=True,
        help="Why the role was opened: a new position, someone leaving, or "
             "cover while someone is away.")
