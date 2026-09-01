# -*- coding: utf-8 -*-
"""The link from a check-in back to the plan that planned it.

THE FIELD LIVES HERE AND NOT IN `pb_lifecycle`, on purpose — the same call P5
made for `probation_review_id`. P0 has no idea what an improvement plan is and
must not learn: a module that knows about every phase that will ever extend it
is a module every phase has to be deployed with. An additive `_inherit` costs P0
nothing and means this phase deploys with a plain `-i pb_pip`.

`ondelete='cascade'` is deliberate and is the one difference from P5's shape. A
check-in exists BECAUSE a plan planned it, and a plan that is deleted (which
only an administrator can do) should not leave six orphaned conversations in
somebody's diary with no way to tell what they were about.

The `kind` value is P0's own `'pip'` — seeded in `CHECKIN_KINDS` since P0 —
except the first coaching conversation, which is `'other'`: it happens BEFORE
any plan exists, and labelling it "PIP check-in" in the diary would tell
everybody who can see a calendar something that has not been decided yet.
"""

from odoo import fields, models


class PbEmployeeCheckin(models.Model):
    _inherit = 'pb.employee.checkin'

    pip_case_id = fields.Many2one(
        'pb.pip.case', string='Improvement plan', index=True,
        ondelete='cascade')
