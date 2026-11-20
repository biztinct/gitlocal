# -*- coding: utf-8 -*-
"""FS-8 — saved report views and the Form builder's delete.

Owner default (FS-8 follow-on, 2026-11-20): a saved report that splits or
filters by a field must NOT stop the administrator deleting the field. So the
report use is NOT one of the engine's reference finders (a finder blocks).
Instead:

* the Studio and the Field library payloads carry `report_uses` per own field
  (`{count, lines, warn, label}`): shared reports and the administrator's own
  are NAMED, other people's private reports only COUNTED — never their names
  or owners;
* the delete warns with that, and when it goes through, every affected saved
  report has the field taken off its stored question and remembers the
  field's name under `_lost`, so it opens without the split / filter and says
  so once (`pb.explorer.open_view`).
"""
from odoo import api, models

from .explorer import MODELS, make_key


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


def strip_spec(spec, base):
    """The stored question without the field: no split ("Total"), no filter."""
    spec = dict(spec or {})

    def hit(key):
        return isinstance(key, str) and (key == base or key.startswith(base + ':'))
    if hit(spec.get('dimension')):
        spec['dimension'] = 'none'
    if isinstance(spec.get('filters'), dict):
        spec['filters'] = {k: v for k, v in spec['filters'].items() if not hit(k)}
    return spec


class PbFormStudioReports(models.AbstractModel):
    _inherit = 'pb.form.studio'

    # ------------------------------------------------------------ finding
    @api.model
    def _pbfx_report_views(self, model, name):
        """Every saved report view (anybody's) whose question uses the field.
        Read with elevated rights: the administrator must know a private one
        exists — and is then told only how many."""
        if 'pb.explorer.view' not in self.env:
            return []
        if model not in MODELS:
            return self.env['pb.explorer.view']
        base = make_key(model, name)
        # A cheap text pre-filter, then the real test on the parsed question:
        # `_` is a LIKE wildcard, so the pre-filter may over-match, never miss.
        self.env.cr.execute(
            "SELECT id, spec FROM pb_explorer_view WHERE spec::text LIKE %s",
            ['%' + base + '%'])
        ids = [vid for vid, spec in self.env.cr.fetchall() if view_uses(spec, base)]
        return self.env['pb.explorer.view'].sudo().with_context(active_test=False).browse(ids)

    @api.model
    def _pbfx_report_uses(self, model, name):
        """`{count, label, lines, warn}` for the screens — or `{}` when no
        saved report uses the field."""
        views = self._pbfx_report_views(model, name)
        if not views:
            return {}
        _ = self.env._
        uid = self.env.uid
        named = [v.name for v in views if v.shared or v.user_id.id == uid]
        hidden = len([v for v in views if not v.shared and v.user_id.id != uid])
        lines = list(dict.fromkeys(named))
        if hidden:
            lines.append(_("Private reports of other people: %s", hidden))
        return {
            'count': len(views),
            'label': _("Saved reports"),
            'lines': lines,
            'warn': _("Saved reports that use this field: %s. Deleting it takes it off them: "
                      "they open without this split or filter and say so once.", len(views)),
        }

    # ------------------------------------------------------------ payloads
    @api.model
    def get_studio(self, host_key):
        out = super().get_studio(host_key)
        model = (out.get('host') or {}).get('model')
        if model in MODELS:
            for name, desc in (out.get('fields') or {}).items():
                if isinstance(desc, dict) and desc.get('custom'):
                    desc['report_uses'] = self._pbfx_report_uses(model, name)
        return out

    @api.model
    def library(self):
        out = super().library()
        for row in (out.get('fields') or []) if isinstance(out, dict) else []:
            if isinstance(row, dict) and row.get('custom') and row.get('model') in MODELS:
                row['report_uses'] = self._pbfx_report_uses(row['model'], row['name'])
        return out

    # ------------------------------------------------------------ delete
    @api.model
    def delete_field(self, model, name, confirm=''):
        """Delete as the engine does (its own checks and blockers first), then
        take the field off every saved report that used it."""
        views = self._pbfx_report_views(model, name) if model in MODELS else []
        row = self._pbfs_field_row(model, name)
        labels = row.with_context(lang=self.env.lang).field_description if row else name
        res = super().delete_field(model, name, confirm)
        base = make_key(model, name)
        for view in views:
            spec = strip_spec(view.spec, base)
            lost = [l for l in (spec.get('_lost') or []) if isinstance(l, str)]
            spec['_lost'] = list(dict.fromkeys(lost + [labels]))[:10]
            view.write({'spec': spec})
        return res
