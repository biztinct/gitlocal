# -*- coding: utf-8 -*-
"""R25 / R26 (owner, 2026-11-20) — My Payobook ticks already saved on a database.

* R25: the two spouse boxes can no longer be changed by the employee. A box
  that still has "Employee can change it" ticked is unticked (it stays shown
  if it was shown), with a Form builder history line.
* R26: blood type and religion always wait for HR. A box set to "Saves at
  once" is set back to "HR approves", with a history line.

Counts only in the log. Idempotent: a second run finds nothing to change. A
database where nobody ticked these boxes (expected on all five) writes
nothing at all.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODEL = 'hr.employee'


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Meta = env['pb.form.field.meta'].sudo()
    Studio = env['pb.form.studio']
    from odoo.addons.pb_form_studio_people.models.form_studio import PORTAL_SENSITIVE, PORTAL_SPOUSE
    unticked = Meta.search([('model', '=', MODEL), ('name', 'in', PORTAL_SPOUSE),
                            ('portal_edit', '=', True)])
    for meta in unticked:
        meta.portal_edit = False
        Studio._pbfs_audit('update_field', None, MODEL, meta.name,
                           'R25: %s - "Employee can change it" unticked (changed through '
                           'My details, Family).' % meta.name, detail={'ruling': 'R25'})
    moved = Meta.search([('model', '=', MODEL), ('name', 'in', PORTAL_SENSITIVE),
                         ('portal_mode', '=', 'instant')])
    for meta in moved:
        meta.portal_mode = 'approve'
        Studio._pbfs_audit('update_field', None, MODEL, meta.name,
                           'R26: %s - "Saves at once" set back to "HR approves" (sensitive '
                           'detail).' % meta.name, detail={'ruling': 'R26'})
    shown = Meta.search_count([('model', '=', MODEL), ('name', 'in', PORTAL_SPOUSE + PORTAL_SENSITIVE),
                               ('portal_show', '=', True)])
    _logger.info('pb_form_studio_people R25/R26: spouse boxes unticked %s, sensitive boxes set to '
                 '"HR approves" %s; spouse/sensitive boxes shown on My Payobook %s',
                 len(unticked), len(moved), shown)
