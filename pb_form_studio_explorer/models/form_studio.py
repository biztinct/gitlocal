# -*- coding: utf-8 -*-
"""FS-8 — a saved report view that splits or filters by a field is a USE of
that field: it shows under "Used by" and stops the delete until it is taken
off (the engine's own rule for every finder, FS8_FACTS §6; the same as the
People and Contracts saved views)."""
from odoo import api, models

from .explorer import make_key


def view_uses(spec, base):
    """Does a stored question split or filter by `base` (any date grain)?"""
    if not isinstance(spec, dict):
        return False

    def hit(key):
        return isinstance(key, str) and (key == base or key.startswith(base + ':'))
    if hit(spec.get('dimension')):
        return True
    filters = spec.get('filters')
    return isinstance(filters, dict) and any(hit(k) for k in filters)


class PbFormStudioReports(models.AbstractModel):
    _inherit = 'pb.form.studio'

    @api.model
    def _pbfs_reference_finders(self):
        return super()._pbfs_reference_finders() + ['_pbfx_refs_report_views']

    @api.model
    def _pbfx_refs_report_views(self, model, name):
        """Saved report views (anybody's — the administrator needs to know of
        a private one too) whose question uses the field."""
        if 'pb.explorer.view' not in self.env:
            return []
        base = make_key(model, name)
        # A cheap text pre-filter, then the real test on the parsed question:
        # `_` is a LIKE wildcard, so the pre-filter may over-match, never miss.
        self.env.cr.execute(
            "SELECT id, spec FROM pb_explorer_view WHERE spec::text LIKE %s",
            ['%' + base + '%'])
        ids = [vid for vid, spec in self.env.cr.fetchall() if view_uses(spec, base)]
        if not ids:
            return []
        views = self.env['pb.explorer.view'].sudo().browse(ids)
        names = ['%s (%s)' % (v.name, v.user_id.name or '') for v in views]
        return [self._pbfs_ref('report_view', self.env._('Saved report views'), names,
                               count=len(ids))]
