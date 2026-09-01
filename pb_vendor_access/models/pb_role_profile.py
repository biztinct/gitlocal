# -*- coding: utf-8 -*-
"""`pb.role.profile` — permission groups, in words a person can act on.

THIS IS A PRESENTATION LAYER, NOT A SECOND ACL. There is exactly one place
access is decided on this database and it is `res.groups` plus the record rules;
this model adds no primitive, invents no tier and grants nothing on its own. It
is a CURATED CATALOGUE: a plain-English name, one sentence saying what it lets
somebody do, an area, and a pointer at the group that actually carries it.

WHY A CATALOGUE AND NOT A LIST OF EVERY GROUP. This database has some hundreds
of `res.groups` rows, most of them technical, several of them named "User". A
screen that dumps them is a screen nobody can use safely, and "grant" on a row
called "User" is how somebody gets given something nobody intended. So the
catalogue is DATA — seeded with the tiers this product actually has, editable by
an administrator, and every row carries the sentence that says what it means.

THE ABSOLUTE, RESTATED AT THE MODEL. A profile may never point at
`base.group_system` or `base.group_erp_manager`. The seed does not contain them,
this model refuses to be created or written pointing at one, and both facades
check again before they apply anything. Three refusals for one rule, on purpose:
this is the only rule in the module whose failure cannot be undone by a person
who is still allowed to log in.

WHO SEES WHICH PROFILE. `visible_group_id` is optional and is the answer to the
handover's "growth-plan profiles are visible only to the heads of HR": a profile
that names a group is only listed to people who hold that group. It hides a ROW
FROM A CATALOGUE; it is not a permission, and the record rule below is what
enforces it.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .vendor_common import PROFILE_AREAS, forbidden_group_ids

_logger = logging.getLogger(__name__)


class PbRoleProfile(models.Model):
    _name = 'pb.role.profile'
    _description = 'Role profile'
    _order = 'area, sequence, name'

    name = fields.Char(
        string='What it is called', required=True, translate=True,
        help='The words somebody would use out loud — "Payroll approver, '
             'final", not the name of a permission group.')
    group_id = fields.Many2one(
        'res.groups', string='Permission group', required=True, index=True,
        ondelete='cascade',
        help='The group this profile hands out. Granting the profile puts '
             'somebody into exactly this group and nothing else.')
    description = fields.Text(
        string='What this lets someone do', translate=True,
        help='One or two sentences, in plain English. It is what the person '
             'granting it reads before they press the button.')
    area = fields.Selection(
        PROFILE_AREAS, string='Area', required=True, default='people',
        index=True)
    sequence = fields.Integer(string='Order', default=10)
    active = fields.Boolean(default=True)
    visible_group_id = fields.Many2one(
        'res.groups', string='Only shown to', ondelete='set null',
        help='Leave empty and everybody who can open this board sees the '
             'profile. Set it and only people in that group do — for the '
             'roles that are nobody else\'s business.')

    #: Not stored, and deliberately so: a count of holders that is written down
    #: is a count that is wrong the moment somebody is granted the group by any
    #: other route, and there are several other routes.
    holder_count = fields.Integer(
        string='People who hold it', compute='_compute_holders')

    _group_uniq = models.Constraint(
        'unique(group_id)',
        'There is already a profile for that permission group. Edit that one '
        'rather than adding a second name for the same thing.')

    # ---------------------------------------------------------------- computes
    def _compute_holders(self):
        """`res.groups.all_user_ids` is the TRANSITIVE set (R7).

        `res.users.group_ids` is direct membership only and misses everyone who
        holds a group through `implied_ids` — which on a ladder like the
        payroll one is most of the people who actually hold it, including every
        administrator. A board that counted direct membership would tell a
        person their manager does not hold a group their manager plainly does.
        """
        for rec in self:
            group = rec.group_id
            if not group:
                rec.holder_count = 0
                continue
            try:
                rec.holder_count = len(group.sudo().all_user_ids)
            except Exception:                   # noqa: BLE001
                _logger.warning(
                    'pb.role.profile: could not count holders of %s',
                    group.id, exc_info=True)
                rec.holder_count = 0

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or ''

    # ------------------------------------------------------------------- rails
    @api.constrains('group_id')
    def _check_group_is_not_the_keys_to_the_building(self):
        """The absolute, at the model.

        A profile pointing at the system group would make "grant this person
        the profile" a two-click way to hand over the whole database, and the
        board's own copy is written in language that makes it sound routine.
        Refused here so that it is refused however the row was created — a data
        file, an import, the shell, or a facade somebody adds later.
        """
        forbidden = forbidden_group_ids(self.env)
        for rec in self:
            if rec.group_id and rec.group_id.id in forbidden:
                raise ValidationError(_(
                    "\"%s\" is the administrator permission for the whole "
                    "system. It is not something this board can hand out, and "
                    "it cannot be put on a profile. An administrator changes "
                    "it on the user record itself, deliberately.",
                    rec.group_id.display_name or rec.group_id.name or ''))

    # ------------------------------------------------------------------ lookup
    @api.model
    def visible(self, limit=None):
        """Every profile this reader may be offered.

        The record rule already does this; asking again here is what lets the
        facades build a list without a sudo and still be readable — and it
        means a caller that DOES need sudo for another reason cannot
        accidentally widen the catalogue by borrowing it.
        """
        return self.search([('active', '=', True)], limit=limit or None)

    def holders(self, cap=None):
        """The people who hold this profile's group, transitively.

        Sorted by name in Python: `res.users` orders by login, which is not the
        order anybody reads a list of colleagues in.
        """
        self.ensure_one()
        if not self.group_id:
            return self.env['res.users']
        users = self.group_id.sudo().all_user_ids.filtered(
            lambda u: u.active)
        users = users.sorted(lambda u: (u.name or '').lower())
        return users[:cap] if cap else users
