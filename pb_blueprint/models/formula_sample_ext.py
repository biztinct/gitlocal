# -*- coding: utf-8 -*-
"""Where a scenario came from, remembered on the scenario itself.

The Test step tells a person which checks are the starter's certification
scenarios, which are boundary cases, which they made themselves and which are a
real person they kept — and the difference changes what each row offers to do.

The engine already records two of the four: a generated row is a boundary case
(``source_type``) and one made from a payslip carries ``source_payslip_id``. The
other two it cannot know, because a certification scenario and a sample somebody
typed are both an ordinary manual row with values in it. So the guided setup
stamps what IT knows, at the moment it knows it — one short field, written once,
never guessed.

Everything created before this field existed still reads correctly: the kind is
worked out from the facts the engine does record, with "it arrived with expected
values" standing in for "the starter brought it".
"""
from odoo import fields, models


class HrFormulaSampleDataBlueprint(models.Model):
    _inherit = 'hr.formula.sample.data'

    bp_origin = fields.Char(
        string='Scenario Origin', index=True, copy=False,
        help="Where this scenario came from — the starting point, a boundary "
             "case, a real person, or somebody's own. Empty on anything created "
             "outside the guided setup, which is worked out instead.")
