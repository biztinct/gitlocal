# -*- coding: utf-8 -*-
"""RECRUIT P1 (RC-D2): the middle hiring tier is the Talent lead.

`ensure_catalogue` is create-only for rows that already exist, so a rename
has to be done here, once, on the role AND on the ability that shares its
words — and only where the row still carries the words this catalogue wrote
(an administrator's own rename is theirs). The Vietnamese is written with it,
because `apply_catalogue_vi` leaves a row alone once it holds Vietnamese, and
these rows hold the old sentence's.

Safe to run again: a second run finds nothing still carrying the old words.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

OLD = {
    'hiring-manager': (
        'Hiring manager',
        'Everything a recruiter does, plus agreeing a hiring request and an '
        'advert, closing a role and marking one filled.'),
    'hiring-head': (
        'Head of hiring',
        'Everything a hiring manager does, plus the hiring rules — who '
        'recruits for which company and country — and the hiring switches.'),
}


def rename_hiring_tiers(env):
    from odoo.addons.pb_vendor_access.hooks import CATALOGUE
    from odoo.addons.pb_vendor_access.catalogue_vi import LANG, VI
    new = {keys[0]: (name, description)
           for keys, _area, _seq, name, description, _vis in CATALOGUE
           if keys[0] in OLD}
    vi_on = bool(env['res.lang'].sudo().search_count(
        [('code', '=', LANG), ('active', '=', True)]))
    changed = 0
    for key, (old_name, old_desc) in OLD.items():
        name, description = new[key]
        rows = env['pb.role.ability'].sudo().with_context(
            active_test=False).search([('technical_key', '=', key)])
        abilities = rows
        profiles = env['pb.role.profile'].sudo().with_context(
            active_test=False).search([('ability_ids', 'in', abilities.ids)]) \
            if abilities else env['pb.role.profile'].browse()
        # Only the single-ability role IS this row (a wider bundle that
        # merely contains it is somebody else's role).
        profiles = profiles.filtered(lambda p: p.ability_ids == abilities)
        for rec in list(abilities) + list(profiles):
            rec = rec.with_context(lang='en_US')
            vals = {}
            if rec.name == old_name and name != old_name:
                vals['name'] = name
            if (rec.description or '') == old_desc:
                vals['description'] = description
            if not vals:
                continue
            rec.write(vals)
            changed += 1
            if vi_on:
                if 'name' in vals and VI.get(name):
                    rec.update_field_translations('name', {LANG: VI[name]})
                if 'description' in vals and VI.get(description):
                    rec.update_field_translations(
                        'description', {LANG: VI[description]})
    return changed


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    changed = rename_hiring_tiers(env)
    _logger.info('pb_vendor_access 1.11.0: hiring tiers renamed on %s rows',
                 changed)
