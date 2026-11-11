# -*- coding: utf-8 -*-
"""WF2 P3b (D10) — a talent lead adds a stage of their own, add-only.

Hiring's stages are rows made special by a fixed key (`pb_key`, 17 of them,
journey.py). Every list in Hiring — the board, set-up, presets, rules, the
filter panel, Workflow Studio's contract — reads "every row that has a key".
A row WITHOUT a key is invisible to all of them, so a company-made stage
needs a key too.

THE SMALLEST ADD-ONLY WAY: a pool of spare keys (`own_1` … `own_12`) is added
to the key list. A company stage takes the next free one. Its family is
"open" (an ordinary working column), so it sits in the working band, can be
dragged and renamed with the existing verbs, is never "always on", and is
untouched by `_ensure_journey_stages()` (which only walks the 17 product
rows) and by the stock-stage retirement (which only walks stock xmlids). No
existing row, key, name, order or behaviour changes.

`stage_add` puts it straight after the stage it follows (the existing
reorder verb renumbers the order, bands kept), and shows it wherever that
stage shows: on every role whose board already shows the stage before it,
and in every preset that already holds it. Removing such a stage is not a
door here (Hiring set-up hides columns per role and per preset, as it does
for any stage).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import as_id

#: The spare keys, in the order they are handed out.
OWN_KEYS = [('own_%d' % i, 'Your own stage %d' % i) for i in range(1, 13)]
OWN = {key for key, _label in OWN_KEYS}


class HiringStageOwnKeys(models.Model):
    _inherit = 'hr.recruitment.stage'

    pb_key = fields.Selection(selection_add=OWN_KEYS, ondelete={k: 'set null' for k in OWN})

    @api.depends('pb_key')
    def _compute_pb_family(self):
        super()._compute_pb_family()
        for rec in self:
            if rec.pb_key in OWN:
                # A company stage is an ordinary working column.
                rec.pb_family = 'open'
                rec.pb_always_on = False


class PbHiringStageAdd(models.AbstractModel):
    _inherit = 'pb.hiring'

    def _act_stage_add(self, payload):
        """payload: {name, after_stage_id}. Returns {id, key, note}.

        The talent lead's door (Hiring's own write permission), as for every
        other stage verb."""
        self._require_write()
        Stage = self.env['hr.recruitment.stage'].sudo().with_context(active_test=False)
        name = (payload.get('name') or '').strip()
        if not name:
            raise UserError(_("A stage needs a name."))
        if len(name) > 60:
            raise UserError(_("Keep a stage name under 60 characters — it has to fit on a column."))
        after = Stage.browse(as_id(payload.get('after_stage_id'))).exists()
        if not after or not after.pb_key:
            raise UserError(_("Choose the stage the new one comes after."))
        if after.pb_family != 'open':
            raise UserError(_("A new stage goes among the working stages, before Joined. "
                              "Choose one of those to put it after."))
        every = Stage.search([('pb_key', '!=', False)], order='sequence,id')
        if any((s.name or '').strip().lower() == name.lower() for s in every):
            raise UserError(_("There is already a stage called “%s”.", name))
        used = set(every.mapped('pb_key'))
        free = next((key for key, _label in OWN_KEYS if key not in used), None)
        if not free:
            raise UserError(_("Hiring takes up to %s stages of your own. Rename one you no longer use.",
                              len(OWN_KEYS)))
        stage = Stage.create({'name': name, 'pb_key': free, 'sequence': after.sequence + 1,
                              'fold': False, 'hired_stage': False})
        # The order: straight after `after`, through the existing reorder
        # verb (it keeps each family in its own band).
        ids = [s.id for s in every]
        ids.insert(ids.index(after.id) + 1, stage.id)
        self._act_stage_reorder({'ids': ids})
        # Shown wherever the stage before it shows.
        Preset = self.env['pb.hiring.stage.preset'].sudo().with_context(active_test=False)
        for preset in Preset.search([('stage_ids', 'in', after.ids)]):
            preset.write({'stage_ids': [(4, stage.id)]})
        Role = self.env['pb.hiring.requisition'].sudo().with_context(active_test=False)
        roles = Role.search([]) if after.pb_always_on else Role.search([('pb_visible_stage_ids', 'in', after.ids)])
        for role in roles:
            role.write({'pb_visible_stage_ids': [(4, stage.id)]})
        return {'id': stage.id, 'key': stage.pb_key,
                'note': _("“%(name)s” added after %(after)s.", name=stage.name, after=after.name)}
