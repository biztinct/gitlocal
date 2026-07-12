# -*- coding: utf-8 -*-
# W40 — Diff re-import (WP-B). A MIXIN over the multi-sheet import wizard. When the
# target config already has rules, the review step shows a config diff (Added /
# Changed / Unchanged / Missing-from-file) and the commit is guarded: an auto
# milestone is recorded first, updated rules are versioned reason='import' with the
# filename as note, and ONLY explicitly-ticked Missing rules are archived (hidden,
# never deleted). This is a preview + guard layer over the EXISTING update_existing
# commit path (multisheet_import_wizard.py:2758-2818) — no second import pipeline.

import json
import logging
import re

from odoo import _, fields, models
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class MultisheetReimportDiff(models.TransientModel):
    _inherit = 'hr.formula.multisheet.import.wizard'

    reimport_diff_json = fields.Text(string='Re-import Diff (JSON)', readonly=True)
    reimport_diff_html = fields.Html(string='Re-import Diff', readonly=True, sanitize=False)
    reimport_missing_line_ids = fields.One2many(
        'hr.formula.reimport.missing.line', 'wizard_id',
        string='Rules missing from the file')

    # ---- normalization ----
    def _rd_norm_code(self, code):
        # Mirror the base update match (r.code == comp.generated_code) — exact code,
        # just trimmed. Codes are canonical identities (C5); never fuzzed here.
        return (code or '').strip()

    def _rd_norm_formula(self, f):
        # Whitespace-insensitive compare of the RESOLVED import formula vs the live
        # excel_formula (both are already in the same letterized/resolved space).
        return re.sub(r'\s+', '', f or '')

    # ---- diff builder (D-B4) ----
    def _build_reimport_diff(self):
        self.ensure_one()
        self.reimport_missing_line_ids.unlink()
        config = self.config_id
        if not config or not config.rule_ids:
            self.reimport_diff_json = json.dumps({'has_rules': False})
            self.reimport_diff_html = False
            return
        imports = {}
        for p in self.component_preview_ids.filtered('include_in_import'):
            imports[self._rd_norm_code(p.generated_code)] = p
        live = {}
        for r in config.rule_ids:
            live[self._rd_norm_code(r.code)] = r

        added, changed, unchanged = [], [], []
        for code, p in imports.items():
            r = live.get(code)
            if not r:
                added.append({'code': p.generated_code, 'name': p.generated_name})
            elif self._rd_norm_formula(p.resolved_formula or p.excel_formula or '') == \
                    self._rd_norm_formula(r.excel_formula or ''):
                unchanged.append(r.code)
            else:
                changed.append({'code': r.code, 'name': r.name, 'old': r.excel_formula or '',
                                'new': p.resolved_formula or p.excel_formula or ''})

        Missing = self.env['hr.formula.reimport.missing.line']
        missing, mvals = [], []
        for code, r in live.items():
            if code not in imports:
                missing.append({'code': r.code, 'name': r.name})
                mvals.append({'wizard_id': self.id, 'rule_id': r.id, 'code': r.code,
                              'name': r.name, 'live_formula': r.excel_formula or '', 'archive': False})
        if mvals:
            Missing.create(mvals)

        diff = {'has_rules': True, 'added': added, 'changed': changed,
                'unchanged_count': len(unchanged), 'missing': missing}
        self.reimport_diff_json = json.dumps(diff)
        self.reimport_diff_html = self._build_reimport_diff_html(diff)

    def _build_reimport_diff_html(self, diff):
        a, c, u, m = diff['added'], diff['changed'], diff['unchanged_count'], diff['missing']
        parts = [
            '<div class="mt-2"><b>%s</b> ' % _("Re-import diff vs current configuration"),
            '<span class="badge text-bg-success">%d %s</span> ' % (len(a), _("added")),
            '<span class="badge text-bg-warning">%d %s</span> ' % (len(c), _("changed")),
            '<span class="badge text-bg-light">%d %s</span> ' % (u, _("unchanged")),
            '<span class="badge text-bg-secondary">%d %s</span>' % (len(m), _("missing from file")),
        ]
        if c:
            parts.append('<table class="table table-sm mt-2"><thead><tr><th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>'
                         % (_("Component"), _("Current formula"), _("New formula")))
            for ch in c[:100]:
                parts.append('<tr><td><b>%s</b></td><td class="text-muted"><code>%s</code></td><td class="text-warning"><code>%s</code></td></tr>'
                             % (html_escape(ch['code']), html_escape(ch['old'] or '—'), html_escape(ch['new'] or '—')))
            parts.append('</tbody></table>')
        if a:
            parts.append('<div class="text-success mt-1">%s %s</div>'
                         % (_("Added:"), html_escape(', '.join(x['code'] for x in a[:50]))))
        parts.append('</div>')
        return ''.join(parts)

    # ---- hooks ----
    def _build_preview_lines(self, capture=None):
        super()._build_preview_lines(capture)
        self._build_reimport_diff()

    def action_execute_import(self):
        diff = {}
        try:
            diff = json.loads(self.reimport_diff_json or '{}')
        except Exception:
            diff = {}
        if not diff.get('has_rules'):
            return super().action_execute_import()

        fname = self.import_filename or _('re-import')
        # D-B5: auto milestone BEFORE the commit → instantly comparable/rollbackable.
        self.env['hr.formula.config.milestone'].sudo().record(
            self.config_id, _('Before re-import %s') % fname)

        # Archive only the explicitly-ticked Missing rules. hr.formula.rule has no
        # `active` field, so "archive" = hide from the grid; never deleted (D-B4).
        to_archive = self.reimport_missing_line_ids.filtered('archive').mapped('rule_id')
        if to_archive:
            to_archive.with_context(
                formula_version_reason='import',
                formula_version_note=_('Hidden on re-import %s') % fname,
            ).write({'is_visible_in_grid': False})

        # Run the base commit with the filename stamped on every 'import' version row
        # (the base's update path already sets reason='import' at :2817; our note
        # rides along in context and the write override reads it).
        wiz = self.with_context(formula_version_note=fname)
        res = super(MultisheetReimportDiff, wiz).action_execute_import()

        # Chatter summary on the config (audit trail beside the version history).
        if hasattr(self.config_id, 'message_post'):
            self.config_id.message_post(body=(
                _("Re-imported <b>%s</b>: %d added, %d changed, %d unchanged, %d missing (%d hidden).")
                % (html_escape(fname), len(diff.get('added', [])), len(diff.get('changed', [])),
                   diff.get('unchanged_count', 0), len(diff.get('missing', [])), len(to_archive))))
        return res


class HrFormulaReimportMissingLine(models.TransientModel):
    _name = 'hr.formula.reimport.missing.line'
    _description = 'Re-import Missing Rule (in config, not in file)'

    wizard_id = fields.Many2one('hr.formula.multisheet.import.wizard', ondelete='cascade')
    rule_id = fields.Many2one('hr.formula.rule', ondelete='cascade')
    code = fields.Char(string='Code', readonly=True)
    name = fields.Char(string='Component', readonly=True)
    live_formula = fields.Char(string='Current formula', readonly=True)
    archive = fields.Boolean(string='Hide on import', default=False,
                             help="Tick to hide this rule from the grid on import "
                                  "(it is never deleted; only manual deletion removes it).")
