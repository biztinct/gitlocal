# -*- coding: utf-8 -*-
"""`pb.role.ability` — one thing somebody is allowed to do, named the way they
would name it.

WHY THIS MODEL EXISTS. A role used to be one permission group with a nicer name.
That works right up until a real job needs two permissions — "manage the
workforce plan" is two of them, "administer the formula engine" is three — and
at that point the catalogue has to either invent a role per permission (which
puts the technical shape of the system back on the screen) or hand out a group
that carries more than the sentence promised. Neither is honest.

So a role is now a BUNDLE. It is made of abilities, and an ability is the small
unit somebody can actually recognise: a plain sentence, an area, and the one or
more permissions that sentence really costs. Roles are assembled from abilities;
nobody assembles a role out of raw permissions any more, because the raw
permissions are not offered — an odd permission that deserves handing out
becomes an ability first, and an ability is DATA, so that costs nobody a deploy.

THIS IS STILL NOT A SECOND ACL. Access is decided in exactly one place on this
database — `res.groups` and the record rules — and this model adds no primitive.
It is the vocabulary layer, and its whole job is that the sentence a person reads
before they press the button is the truth about what they are about to hand over.

THE ABSOLUTE, RESTATED HERE TOO. An ability may never carry the administrator
permission for the whole system, and — new in this layer — it may never carry a
permission that QUIETLY IMPLIES one. A group that implies the master key IS the
master key; checking only the group named on the row would let the one rule this
module cannot afford to lose be walked around by one level of indirection.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .access_common import default_area, forbidden_in_closure, profile_areas

_logger = logging.getLogger(__name__)


class PbRoleAbility(models.Model):
    _name = 'pb.role.ability'
    _description = 'Role ability'
    _order = 'area, sequence, name'

    name = fields.Char(
        string='What it lets someone do', required=True, translate=True,
        help='The words somebody would use out loud — "Approve a pay run", '
             'not the name of a permission group.')
    description = fields.Char(
        string='The honest sentence', translate=True,
        help='One sentence saying what this lets somebody do AND what it '
             'stops short of. It is what the person building a role reads '
             'before they tick the box.')
    area = fields.Selection(
        selection=lambda self: profile_areas(), string='Area',
        required=True, default=lambda self: default_area(),
        index=True)
    sequence = fields.Integer(string='Order', default=10)

    group_ids = fields.Many2many(
        'res.groups', 'pb_role_ability_group_rel', 'ability_id', 'group_id',
        string='Permissions it carries', required=True,
        help='What this ability actually grants. One is the usual case; a job '
             'that genuinely needs two is why this is a list.')

    #: The stable name a seed or a migration refers to. Names get reworded by
    #: administrators — and should be able to be — so the thing the code holds
    #: on to has to be something no screen invites anybody to edit.
    technical_key = fields.Char(
        string='Key', required=True, index=True, copy=False,
        help='The fixed name this ability is known by underneath. It never '
             'changes, so renaming the ability is always safe.')
    active = fields.Boolean(default=True)

    profile_ids = fields.Many2many(
        'pb.role.profile', 'pb_role_profile_ability_rel',
        'ability_id', 'profile_id', string='Roles that include it')

    _key_uniq = models.Constraint(
        'unique(technical_key)',
        'There is already an ability with that key. Edit that one rather than '
        'adding a second version of the same thing.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or ''

    # ------------------------------------------------------------------- rails
    @api.constrains('group_ids')
    def _check_it_is_not_the_keys_to_the_building(self):
        """The absolute, and this time over the WHOLE closure.

        `pb.role.profile` has always refused to point straight at the
        administrator permission. An ability has to refuse one step further out:
        a permission that implies the administrator permission hands over the
        same database, and it does it while the row on the screen says something
        else entirely.
        """
        for rec in self:
            bad = forbidden_in_closure(rec.group_ids, self.env)
            if bad:
                raise ValidationError(_(
                    "\"%(what)s\" would carry %(bad)s — the administrator "
                    "permission for the whole system. That is never something "
                    "a role can hand out. An administrator changes it on the "
                    "person's own record, deliberately.",
                    what=rec.name or '',
                    bad=', '.join(
                        '"%s"' % (g.display_name or g.name or '')
                        for g in bad)))

    # ------------------------------------------------------------------ lookup
    @api.model
    def by_keys(self, keys):
        """The abilities behind a list of keys, in the order they were asked
        for, silently skipping any this database has never heard of."""
        keys = [k for k in (keys or []) if k]
        if not keys:
            return self.browse()
        found = self.sudo().with_context(active_test=False).search(
            [('technical_key', 'in', keys)])
        by_key = {a.technical_key: a for a in found}
        ids = [by_key[k].id for k in keys if k in by_key]
        return self.browse(ids)
