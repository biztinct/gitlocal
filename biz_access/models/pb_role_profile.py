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

A ROLE IS NOW A BUNDLE. It used to be exactly one permission group, which is
true of every role this product happens to have today and false of the next one
somebody asks for: "plan and approve the workforce" is two permissions, and a
catalogue that can only name one either splits the job into two rows nobody
recognises or hands out more than the sentence promised. So a role holds
ABILITIES (`pb.role.ability`), each ability carries its own permissions, and
`group_ids` is the union — worked out, stored, and never typed.

`group_id` IS FROZEN, NOT GONE. Every role on this database was one group before
bundles existed, and the column still says which. Nothing reads it to decide
anything any more; it stays because deleting the answer to "what was this before"
is how an upgrade becomes impossible to check afterwards, and because the unique
constraint on it is still the thing stopping two rows quietly meaning the same.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .access_common import (default_area, forbidden_group_ids,
                            forbidden_in_closure, profile_areas)

_logger = logging.getLogger(__name__)


class PbRoleProfile(models.Model):
    _name = 'pb.role.profile'
    _description = 'Role profile'
    _order = 'area, sequence, name'

    name = fields.Char(
        string='What it is called', required=True, translate=True,
        help='The words somebody would use out loud — "Payroll approver, '
             'final", not the name of a permission group.')
    ability_ids = fields.Many2many(
        'pb.role.ability', 'pb_role_profile_ability_rel',
        'profile_id', 'ability_id', string='What it lets someone do',
        help='The things somebody with this role can do. Tick them and the '
             'permissions underneath are worked out for you.')
    group_ids = fields.Many2many(
        'res.groups', 'pb_role_profile_group_rel', 'profile_id', 'group_id',
        string='Permissions it carries', compute='_compute_group_ids',
        store=True, readonly=True,
        help='Everything the abilities above add up to. It is worked out, '
             'never typed, so it can never disagree with them.')
    group_id = fields.Many2one(
        'res.groups', string='Permission group (before bundles)',
        index=True, ondelete='cascade',
        help='The single group this role handed out before roles were made of '
             'abilities. It is kept as a record of what was, and nothing '
             'decides anything from it any more.')
    description = fields.Text(
        string='What this lets someone do', translate=True,
        help='One or two sentences, in plain English. It is what the person '
             'granting it reads before they press the button.')
    area = fields.Selection(
        selection=lambda self: profile_areas(), string='Area',
        required=True, default=lambda self: default_area(),
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
        string='People who hold it', compute='_compute_holders',
        search='_search_holder_count')

    _group_uniq = models.Constraint(
        'unique(group_id)',
        'There is already a profile for that permission group. Edit that one '
        'rather than adding a second name for the same thing.')

    # ---------------------------------------------------------------- computes
    @api.depends('ability_ids', 'ability_ids.group_ids')
    def _compute_group_ids(self):
        """What the ticked abilities add up to — stored, so it can be searched
        and joined on, and read-only, so it can never drift from them."""
        for rec in self:
            rec.group_ids = rec.ability_ids.group_ids

    def _compute_holders(self):
        """`res.groups.all_user_ids` is the TRANSITIVE set (R7).

        `res.users.group_ids` is direct membership only and misses everyone who
        holds a group through `implied_ids` — which on a ladder like the
        payroll one is most of the people who actually hold it, including every
        administrator. A board that counted direct membership would tell a
        person their manager does not hold a group their manager plainly does.

        HOLDING A BUNDLE MEANS HOLDING ALL OF IT. Somebody with three of a
        role's four permissions cannot do the job the sentence describes, so
        counting them as a holder would make the board's "who has this" answer
        a list of people some of whom do not. The count is the INTERSECTION.
        """
        for rec in self:
            rec.holder_count = len(rec._holder_users())

    def _search_holder_count(self, operator, value):
        """Make "nobody holds this" a filter you can actually press.

        The count is computed, not stored, on purpose (see above) — so there is
        no column to compare against and the ORM cannot search it for us. The
        honest way is to work the count out for every profile once and hand
        back a plain id domain; there are a couple of dozen profiles, not a
        couple of million, so one pass is cheaper than the machinery that would
        avoid it. `sudo()` is confined to the COUNTING (group membership is not
        the reader's business); which profiles the reader may see is still
        decided by the record rules on the search this domain feeds.
        """
        try:
            records = self.sudo().search([])
            matching = records.filtered_domain(
                [('holder_count', operator, value)])
            return [('id', 'in', matching.ids)]
        except Exception:                           # noqa: BLE001
            _logger.warning(
                'pb.role.profile: holder-count search failed for %s %s',
                operator, value, exc_info=True)
            # A filter that cannot be worked out must not silently show
            # everything — that reads as "every role is unheld".
            return [('id', 'in', [])]

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or ''

    def _holder_users(self):
        """Everybody who holds EVERY permission in the bundle, transitively.

        A role with nothing in it yet is held by nobody — never by everybody,
        which is what an empty intersection would otherwise be and what an
        unguarded `reduce` would produce.
        """
        self.ensure_one()
        groups = self.group_ids
        if not groups:
            return self.env['res.users'].browse()
        try:
            users = None
            for group in groups.sudo():
                current = group.all_user_ids
                users = current if users is None else (users & current)
                if not users:
                    break
            return users if users is not None else self.env['res.users'].browse()
        except Exception:                       # noqa: BLE001
            _logger.warning(
                'pb.role.profile: could not count holders of %s',
                groups.ids, exc_info=True)
            return self.env['res.users'].browse()

    # ------------------------------------------------------------------- rails
    @api.constrains('group_ids')
    def _check_the_bundle_is_not_the_keys_to_the_building(self):
        """The absolute again, over everything the whole bundle reaches.

        `pb.role.ability` already refuses this for each ability on its own. A
        role is assembled from abilities, so in ordinary use this can never
        fire — which is exactly why it is here: the routes that get past the
        ability check (a data file, an import, raw SQL followed by a recompute)
        are the routes nobody is watching.
        """
        for rec in self:
            bad = forbidden_in_closure(rec.group_ids, self.env)
            if bad:
                raise ValidationError(_(
                    "\"%(what)s\" would carry %(bad)s — the administrator "
                    "permission for the whole system. It is not something this "
                    "board can hand out, and it cannot be put on a role. An "
                    "administrator changes it on the person's own record, "
                    "deliberately.",
                    what=rec.name or '',
                    bad=', '.join('"%s"' % (g.display_name or g.name or '')
                                  for g in bad)))

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
        """The people who hold everything in this role, transitively.

        Sorted by name in Python: `res.users` orders by login, which is not the
        order anybody reads a list of colleagues in.
        """
        self.ensure_one()
        users = self._holder_users().filtered(lambda u: u.active)
        users = users.sorted(lambda u: (u.name or '').lower())
        return users[:cap] if cap else users
