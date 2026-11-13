# -*- coding: utf-8 -*-
"""LEARNING L2 — the three facts a required-training rule reads off a person.

`pb_safety_group` is the Vietnam occupational-safety training group (Decree
44/2016/NĐ-CP Art 17, amended by Decree 140/2018): groups 1–6 decide the
hours a person must be trained for and how often. Empty for anybody outside
Vietnam, and empty until HR sets it — a rule for "group 3" never guesses.

`pb_posh_ic_member` marks a member of the Internal Committee under India's
harassment-at-work law (POSH Act 2013); their own orientation course is a
separate rule in the India pack.

`pb_sg_experienced` marks somebody with more than six years in their sector
in Singapore: their Safety Orientation Course stays valid for four years
instead of two (MOM's own rule).

All three are Payobook's: Zoho never writes them (RIZE_LEDGER D8, handover F9)
and they sit behind the HR user group like the trial-period field beside them.
"""

from odoo import fields, models

#: The six groups, in the words on the screen. The decree's wording lives in
#: the help text, never in the label.
SAFETY_GROUPS = [
    ('1', 'Group 1 — Managers'),
    ('2', 'Group 2 — Safety officers'),
    ('3', 'Group 3 — Strict-safety jobs'),
    ('4', 'Group 4 — Other workers'),
    ('5', 'Group 5 — Health staff'),
    ('6', 'Group 6 — Safety-hygiene officers'),
]
SAFETY_GROUP_LABEL = dict(SAFETY_GROUPS)

#: LEARNING L4 (owner decision LD11): in a company whose country is Vietnam
#: an employee with no safety group set counts as group 4 ("other workers")
#: for the matrix and the yearly refresher; HR may set another group per
#: person. Outside Vietnam an empty group stays empty.
DEFAULT_GROUP_VN = '4'


def effective_safety_group(group, company_country_code):
    """(group, by_default) — the group a person counts in, and whether it
    is the Vietnam default rather than one HR set."""
    if group:
        return group, False
    if (company_country_code or '').upper() == 'VN':
        return DEFAULT_GROUP_VN, True
    return '', False


class HrEmployeeTraining(models.Model):
    _inherit = 'hr.employee'

    pb_safety_group = fields.Selection(
        SAFETY_GROUPS, string='Safety training group', index=True,
        tracking=True, groups='hr.group_hr_user',
        help='Vietnam only. The occupational-safety training group this '
             'person belongs to (Decree 44/2016, amended by Decree 140/2018). '
             'It decides how many hours of safety training they need and how '
             'often. Leave it empty outside Vietnam.')
    pb_posh_ic_member = fields.Boolean(
        string='Internal Committee member', groups='hr.group_hr_user',
        help='India only. Sits on the committee that hears harassment '
             'complaints, so they need the committee orientation course.')
    pb_sg_experienced = fields.Boolean(
        string='More than six years in the sector',
        groups='hr.group_hr_user',
        help='Singapore only. Their Safety Orientation Course stays valid for '
             'four years instead of two.')
