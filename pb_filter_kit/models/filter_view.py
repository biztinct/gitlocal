# -*- coding: utf-8 -*-
"""Views people save on a filtered list ("Hanoi plant, ending soon").

Private by default; "Share with everyone" puts the view in every user's
tab row for that screen (owner ruling 2026-10-30). The record rules in
security/filter_view_rules.xml enforce that, not this file.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

NAME_MAX = 60


class PbFilterView(models.Model):
    _name = 'pb.filter.view'
    _description = 'Saved filter view'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    screen = fields.Char(required=True, index=True,
                         help='Which list this view belongs to, e.g. "employees".')
    user_id = fields.Many2one('res.users', string='Saved by', required=True, index=True,
                              default=lambda self: self.env.user, ondelete='cascade')
    shared = fields.Boolean(string='Share with everyone')
    filters = fields.Json(default=dict)
    # NOT `search`: a field by that name hides the ORM's search() method.
    search_text = fields.Char(string='Search')
    sequence = fields.Integer(default=10)

    # ------------------------------------------------------------------ api
    @api.model
    def _pbf_clean_name(self, name):
        name = ' '.join((name or '').split())[:NAME_MAX]
        if not name:
            raise UserError(_('Give the view a name.'))
        return name

    @api.model
    def pbf_save(self, screen, name, filters=None, search=None, shared=False):
        """Create a view owned by the current user; returns its payload."""
        if not screen:
            raise UserError(_('This list cannot save views.'))
        view = self.create({
            'screen': screen,
            'name': self._pbf_clean_name(name),
            'filters': filters if isinstance(filters, dict) else {},
            'search_text': (search or '')[:200],
            'shared': bool(shared),
            'user_id': self.env.uid,
        })
        return view._pbf_payload()

    def pbf_update(self, vals):
        """Rename, re-share or overwrite the filters of one of your views."""
        self.ensure_one()
        clean = {}
        if 'name' in vals:
            clean['name'] = self._pbf_clean_name(vals['name'])
        if 'shared' in vals:
            clean['shared'] = bool(vals['shared'])
        if 'filters' in vals:
            clean['filters'] = vals['filters'] if isinstance(vals['filters'], dict) else {}
        if 'search' in vals:
            clean['search_text'] = (vals['search'] or '')[:200]
        if clean:
            self.write(clean)
        return self._pbf_payload()

    def pbf_delete(self):
        self.ensure_one()
        self.unlink()
        return True

    def _pbf_payload(self):
        self.ensure_one()
        mine = self.user_id.id == self.env.uid
        return {
            'key': 'v%d' % self.id,
            'id': self.id,
            'label': self.name,
            'filters': self.filters or {},
            'search': self.search_text or '',
            'shared': self.shared,
            'mine': mine,
            'owner': '' if mine else (self.user_id.name or ''),
            'builtin': False,
        }
