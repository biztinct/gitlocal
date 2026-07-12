# -*- coding: utf-8 -*-
# W37 — Join-key health (WP-B). A MIXIN over the multi-sheet import wizard: it
# measures how well each SELECTED SECONDARY sheet joins to the MAIN sheet on the
# primary key, at the same moment the resolution preview is built. It never grows
# the 3,930-line base wizard (C6) and never mutates the source file (D-B3).
#
# CORRECTNESS: the base match at multisheet_import_wizard.py:2927-2961 keys rows by
# `str(pk_value).strip()` and skips falsy values. `_jh_base` mirrors that EXACTLY so
# health measures the REAL join, not an idealized one. Float-artifact / case folding
# is a strictly-optional layer (D-B3 normalize_keys) — never the base match.

import base64
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)

_JH_FLOAT = re.compile(r'^\d+\.0+$')   # '1023.0', '1023.00' — Excel numeric-as-float artifact


class MultisheetJoinHealth(models.TransientModel):
    _inherit = 'hr.formula.multisheet.import.wizard'

    # Per-secondary-sheet health dicts (D-B1 metrics + up to 20 sample missing keys).
    join_health_json = fields.Text(string='Join Key Health (JSON)', readonly=True)
    join_health_html = fields.Html(string='Join Key Health', readonly=True, sanitize=False)
    # Set by the normalize_keys fix (D-B3): re-scans with the fuzzy match layer.
    join_normalize_keys = fields.Boolean(string='Normalize join keys', default=False)

    # ---- key normalization (mirror of the base join + optional fuzzy layer) ----
    def _jh_base(self, v):
        """Base match key — EXACT mirror of the base wizard: `str(v).strip()`, with
        falsy / blank-after-strip collapsing to '' (the caller skips those, just as
        `if pk_value:` does at :2929)."""
        return '' if not v else str(v).strip()

    def _jh_float(self, k):
        """'1023.0' -> '1023' (Excel float artifact); other values unchanged."""
        return k[:k.index('.')] if _JH_FLOAT.match(k) else k

    def _jh_fuzzy(self, k):
        """Full fuzzy key: float-artifact stripped + casefolded."""
        return self._jh_float(k).casefold()

    def _jh_keys(self, connector, sheet_line):
        """Return (key_list, total_rows, pk_col) for a sheet, applying the base norm
        (or the fuzzy norm when join_normalize_keys is on). Lists/sets only — never
        materialize per-row records (C8; sheets can be huge)."""
        pk = self._resolve_primary_key_column(sheet_line)
        if not pk:
            return [], 0, None
        data = connector.load_sheet_with_detection(sheet_line.sheet_name)
        rows = data.get('data_rows', []) or []
        fuzzy = self.join_normalize_keys
        keys = []
        for row in rows:
            k = self._jh_base(row.get(pk))
            if k:
                keys.append(self._jh_fuzzy(k) if fuzzy else k)
        return keys, len(rows), pk

    # ---- the scan (D-B1) ----
    def _scan_join_health(self):
        self.ensure_one()
        selected = self.available_sheet_ids.filtered('is_selected')
        main = selected.filtered('is_main_sheet')[:1]
        if not self.import_file or not main:
            # M3: store FALSE, not '[]'. '[]' is truthy, which defeats the
            # `not self.join_health_json` fallback in _compute_confidence and
            # spuriously drops a clean keyed sheet's 15% term from 1.0 to 0.0.
            self.join_health_json = False
            self.join_health_html = False
            return []
        from ..integrations import ExcelConnector
        connector = ExcelConnector(None)
        connector.load_workbook_multisheet(base64.b64decode(self.import_file), include_formulas=False)

        main_keys, _mtot, main_pk = self._jh_keys(connector, main)
        main_set = set(main_keys)
        out = []
        for sheet in selected:
            if sheet.id == main.id:
                continue
            keys, total, pk = self._jh_keys(connector, sheet)
            if pk is None:
                # a selected secondary sheet with no primary key = the degenerate
                # 0.0 coverage case (preserves the old binary penalty; D-B2 gotcha).
                out.append({'sheet': sheet.sheet_name, 'has_key': False, 'coverage': 0.0,
                            'duplicates': 0, 'blank_keys': 0, 'type_mismatch': 0,
                            'fuzzy_only': 0, 'missing': 0, 'sample_missing': []})
                continue
            sset = set(keys)
            missing = main_set - sset
            # categorize the misses that WOULD match if normalized (fixable, D-B3)
            aux_float = {self._jh_float(k) for k in keys}
            aux_fold = {k.casefold() for k in keys}
            type_mismatch = fuzzy_only = 0
            for mk in missing:
                if self._jh_float(mk) != mk and self._jh_float(mk) in aux_float:
                    type_mismatch += 1
                elif mk.casefold() in aux_fold:
                    fuzzy_only += 1
            coverage = (len(main_set) - len(missing)) / len(main_set) if main_set else 0.0
            out.append({
                'sheet': sheet.sheet_name,
                'has_key': True,
                'coverage': round(coverage, 4),
                'duplicates': len(keys) - len(sset),
                'blank_keys': total - len(keys),
                'type_mismatch': type_mismatch,
                'fuzzy_only': fuzzy_only,
                'missing': len(missing),
                'sample_missing': sorted(missing)[:20],
            })
        # M3: an empty result (single sheet = main only, no secondaries) stores
        # FALSE too, so the clean-import fallback holds (see early-return above).
        self.join_health_json = json.dumps(out) if out else False
        self.join_health_html = self._build_join_health_html(out, main.sheet_name) if out else False
        return out

    # ---- primary_key_miss preview lines (D-B2) ----
    def _build_primary_key_miss_lines(self):
        """Surface the main-sheet keys that miss a selected secondary sheet as
        preview lines (issue_type already exists). Capped 200 total (C8); the full
        counts live in the health table."""
        health = json.loads(self.join_health_json or '[]')
        Line = self.env['hr.formula.import.preview.line']
        vals, cap = [], 200
        for h in health:
            fixable = bool(h.get('type_mismatch') or h.get('fuzzy_only'))
            for mk in h.get('sample_missing', []):
                if len(vals) >= cap:
                    break
                vals.append({
                    'wizard_id': self.id,
                    'sheet_name': h['sheet'],
                    'component_code': mk,
                    'component_name': _("Primary key not matched"),
                    'status': 'warning',
                    'issue_type': 'primary_key_miss',
                    'issue_detail': _("Key '%s' from the main sheet is not present in '%s'.")
                                    % (mk, h['sheet']),
                    'fix_action': 'normalize_keys' if fixable else False,
                })
        if vals:
            Line.create(vals)

    def _build_join_health_html(self, health, main_name):
        if not health:
            return False
        rows = []
        for h in health:
            cov = h.get('coverage', 0.0)
            pct = round(cov * 100, 1)
            tone = 'success' if cov >= 0.999 else ('warning' if cov >= 0.9 else 'danger')
            flags = []
            if h.get('duplicates'):
                flags.append(_("%d dup") % h['duplicates'])
            if h.get('blank_keys'):
                flags.append(_("%d blank") % h['blank_keys'])
            if h.get('type_mismatch'):
                flags.append(_("%d 123.0") % h['type_mismatch'])
            if h.get('fuzzy_only'):
                flags.append(_("%d case/space") % h['fuzzy_only'])
            if not h.get('has_key'):
                flags.append(_("no primary key"))
            rows.append(
                '<tr><td>%s</td><td class="text-%s"><b>%s%%</b></td><td>%s</td><td class="text-muted">%s</td></tr>'
                % (html_escape(h['sheet']), tone, pct, h.get('missing', 0),
                   html_escape(', '.join(flags) or '—')))
        return (
            '<div class="mt-2"><b>%s</b> <span class="text-muted">(vs main sheet &#8220;%s&#8221;)</span>'
            '<table class="table table-sm mt-1"><thead><tr>'
            '<th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table></div>'
            % (_("Join-key health"), html_escape(main_name),
               _("Sheet"), _("Coverage"), _("Missing"), _("Issues"), ''.join(rows)))

    # ---- hook into the preview build + fixes ----
    def _build_preview_lines(self, capture=None):
        # super() builds the formula preview lines + a first confidence pass; then we
        # scan health, add the primary_key_miss lines, and recompute so the 15% key
        # term reflects real coverage (D-B1/D-B2).
        super()._build_preview_lines(capture)
        self._scan_join_health()
        self._build_primary_key_miss_lines()
        self._compute_confidence()

    def action_apply_preview_fixes(self):
        # D-B3: a normalize_keys fix flips the fuzzy match layer on, re-scans health
        # (float-artifact / case-only keys now match → coverage rises) and rebuilds
        # the key-miss lines. The source file is never touched.
        norm = self.preview_line_ids.filtered(lambda l: l.fix_action == 'normalize_keys')
        if norm:
            self.join_normalize_keys = True
            norm.write({'fix_action': False})
            self.preview_line_ids.filtered(lambda l: l.issue_type == 'primary_key_miss').unlink()
            self._scan_join_health()
            self._build_primary_key_miss_lines()
        # super() applies the remaining per-line fixes and recomputes confidence,
        # which now reads the updated join_health_json.
        return super().action_apply_preview_fixes()


class HrFormulaImportPreviewLineJoin(models.TransientModel):
    _inherit = 'hr.formula.import.preview.line'

    fix_action = fields.Selection(
        selection_add=[('normalize_keys', 'Normalize keys (case / spaces / 123.0)')],
        ondelete={'normalize_keys': 'set null'})
