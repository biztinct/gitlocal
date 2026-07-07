# -*- coding: utf-8 -*-
# Import Confidence (Feature 3) — a MIXIN over the multi-sheet import wizard.
# T3.1: scaffold (fields + preview-line model). T3.2: resolution capture (S2).
# Everything lives here so the 3,814-line base wizard is never grown.
#
# Why wrapping is required (verified against the base file):
#  * action_process_with_resolution (line 1029) loops components calling
#    _resolve_same_sheet_formula (1361) then _resolve_cross_sheet_formula (1255),
#    whose inner handlers return "0" for unresolved refs with only _logger.debug.
#  * Line 1240 then sets component['excel_formula'] = resolved AND line 1238 sets
#    resolved_formula = resolved — the ORIGINAL formula is gone from BOTH fields
#    before preview records are created. Only these wrappers ever see it.

import json
import re

from odoo import _, fields, models

# Any remaining sheet-qualified ref (e.g. 'TimeTB 2'!A1 or Sheet!A1) that survived
# resolution — the Excel→Python converter would choke on or zero it.
SHEET_REF_RE = re.compile(r"(?:'[^']+'|\w+)\s*!")


class MultisheetImportPreview(models.TransientModel):
    _inherit = 'hr.formula.multisheet.import.wizard'

    # Side-by-side original→resolved preview built after the resolution step.
    preview_line_ids = fields.One2many(
        'hr.formula.import.preview.line', 'wizard_id',
        string='Resolution Preview')
    # Raw JSON kept for the client gauge / AI review (populated in T3.2/T3.3).
    resolution_preview_json = fields.Text(string='Resolution Preview (JSON)')
    confidence_score = fields.Float(string='Confidence', readonly=True)
    confidence_breakdown_json = fields.Text(string='Confidence Breakdown', readonly=True)

    # ---- resolution capture (T3.2, skeleton S2 adapted) -----------------------
    # The capture list is carried in the CONTEXT, not as an instance attribute:
    # Odoo 19 recordsets use __slots__, so `self._capture = []` raises. A mutable
    # list placed in context is a shared object — super() and the resolve wrappers
    # (all running on the same context-bound `self`) mutate the same list.

    def action_process_with_resolution(self):
        capture = []                # [{'original','after_same','resolved','sheet'}]
        wiz = self.with_context(_import_capture=capture)
        res = super(MultisheetImportPreview, wiz).action_process_with_resolution()
        # super() succeeded → component_preview_ids exist, state == 'review_components'
        wiz._build_preview_lines(capture)
        return res

    def _resolve_same_sheet_formula(self, formula, sheet_name, column_mapping):
        # Called FIRST for each formula component, with the ORIGINAL formula — the
        # only point where the pre-resolution text is still visible (before 1240).
        resolved = super()._resolve_same_sheet_formula(formula, sheet_name, column_mapping)
        cap = self.env.context.get('_import_capture')
        if cap is not None and formula:
            cap.append({'original': formula, 'after_same': resolved,
                        'resolved': None, 'sheet': sheet_name})
        return resolved

    def _resolve_cross_sheet_formula(self, formula, column_mapping):
        resolved = super()._resolve_cross_sheet_formula(formula, column_mapping)
        cap = self.env.context.get('_import_capture')
        # completes the most recent event: same-sheet ran immediately before this,
        # so cap[-1]['after_same'] == the formula we were just handed.
        if cap and cap[-1]['resolved'] is None and cap[-1]['after_same'] == formula:
            cap[-1]['resolved'] = resolved
        return resolved

    # ---- pairing + diagnosis --------------------------------------------------
    @staticmethod
    def _event_resolved(ev):
        return ev['resolved'] if ev.get('resolved') is not None else ev.get('after_same')

    def _build_preview_lines(self, capture=None):
        self.preview_line_ids.unlink()
        Line = self.env['hr.formula.import.preview.line']
        if capture is None:
            capture = self.env.context.get('_import_capture') or []
        events = list(capture)
        # Only formula components have a resolved_formula; both lists are built in
        # the same deterministic order by the base loop → sequence-zip is primary.
        previews = self.component_preview_ids.filtered(lambda p: p.resolved_formula)
        aligned = (len(events) == len(previews))
        vals_list = []
        for i, preview in enumerate(previews):
            if aligned:
                event = events[i]
            else:
                # counts disagree → content-match on resolved text before giving up
                event = next((e for e in events
                              if self._event_resolved(e) == (preview.resolved_formula or '')), None)
            original = (event['original'] if event else preview.excel_formula) or ''
            resolved = preview.resolved_formula or ''
            status, issue_type, detail = self._diagnose(original, resolved)
            if not aligned and event is None and status == 'ok':
                # visible degradation over silent misattribution (see S2 rationale)
                status, issue_type, detail = 'warning', False, _("Pairing uncertain")
            vals_list.append({
                'wizard_id': self.id,
                'sheet_name': preview.source_sheet,
                'component_code': preview.generated_code,
                'component_name': preview.generated_name,
                'original_excel_formula': original,
                'resolved_formula': resolved,
                'status': status, 'issue_type': issue_type or False, 'issue_detail': detail or False,
            })
        if vals_list:
            Line.create(vals_list)
        self._compute_confidence()

    # ---- confidence score (T3.3) — weighted 40/25/20/15 --------------------
    def _compute_confidence(self):
        lines = self.preview_line_ids
        total = len(lines) or 1
        # 40% — formulas that resolved cleanly (status ok)
        resolved_ratio = len(lines.filtered(lambda l: l.status == 'ok')) / total
        # 25% — absence of references that silently became 0
        no_zero_ratio = 1.0 - len(lines.filtered(lambda l: l.issue_type == 'becomes_zero')) / total
        # 20% — selected columns that produced a mapped component
        selected_cols = self.column_selection_ids.filtered('is_selected')
        if selected_cols:
            preview_keys = {(p.source_sheet, p.column_letter) for p in self.component_preview_ids}
            mapped = sum(1 for c in selected_cols if (c.sheet_name, c.column_letter) in preview_keys)
            column_ratio = mapped / len(selected_cols)
        else:
            column_ratio = 1.0
        # 15% — selected sheets whose primary key was matched
        selected_sheets = self.available_sheet_ids.filtered('is_selected')
        if selected_sheets:
            key_ratio = len(selected_sheets.filtered('primary_key_column_name')) / len(selected_sheets)
        else:
            key_ratio = 1.0

        score = (0.40 * resolved_ratio + 0.25 * no_zero_ratio
                 + 0.20 * column_ratio + 0.15 * key_ratio)
        breakdown = {
            'resolved': round(resolved_ratio, 3),
            'no_zeros': round(no_zero_ratio, 3),
            'columns': round(column_ratio, 3),
            'keys': round(key_ratio, 3),
            'weights': {'resolved': 0.40, 'no_zeros': 0.25, 'columns': 0.20, 'keys': 0.15},
        }
        self.write({
            'confidence_score': round(score, 3),
            'confidence_breakdown_json': json.dumps(breakdown),
        })

    # ---- fix actions (T3.5) ---------------------------------------------------
    def _fix_target_col(self, code):
        """Column letter of the component the user wants to map a broken ref to —
        prefer a component from THIS import, fall back to an existing config rule."""
        if not code:
            return None
        comp = self.component_preview_ids.filtered(lambda c: c.generated_code == code)[:1]
        if comp and comp.column_letter:
            return comp.column_letter
        rule = self.config_id.rule_ids.filtered(lambda r: r.code == code)[:1]
        if rule and rule.column_letter:
            return rule.column_letter
        return None

    @staticmethod
    def _rewrite_zero_to_ref(formula, col):
        """Replace the bare `0` (the substituted, lost reference) with a reference
        to `col`. Row digit is arbitrary — the engine strips rows — but a digit is
        needed for the ref to be recognised."""
        ref = col + '2'
        f = (formula or '').strip()
        if f in ('', '0', '=0', '0.0', '=0.0'):
            return '=' + ref
        return re.sub(r'(?<![\w.])0(?![\w.])', ref, formula, count=1)

    def action_apply_preview_fixes(self):
        """Apply each preview line's chosen fix_action to the matching component
        preview, then recompute confidence. Nothing is imported here — the
        corrected component_preview.excel_formula is what action_execute_import
        later turns into a rule."""
        self.ensure_one()
        by_key = {(c.source_sheet, c.generated_code): c for c in self.component_preview_ids}
        for line in self.preview_line_ids.filtered('fix_action'):
            comp = by_key.get((line.sheet_name, line.component_code))
            action = line.fix_action
            if action == 'map_component':
                col = self._fix_target_col(line.fix_target_rule_code)
                if not col:
                    line.issue_detail = _("Unknown target component: %s") % (line.fix_target_rule_code or '—')
                    continue
                new_formula = self._rewrite_zero_to_ref(
                    line.resolved_formula or (comp.excel_formula if comp else ''), col)
                if comp:
                    comp.write({'excel_formula': new_formula, 'resolved_formula': new_formula})
                line.write({'resolved_formula': new_formula, 'status': 'ok',
                            'issue_type': False, 'issue_detail': _("Mapped to %s") % line.fix_target_rule_code})
            elif action == 'convert_to_input':
                if comp:
                    comp.write({'excel_formula': '', 'resolved_formula': '', 'column_type': 'input'})
                line.write({'status': 'ok', 'issue_type': False,
                            'issue_detail': _("Converted to input — value comes from the data source")})
            elif action == 'acknowledge_zero':
                line.write({'status': 'ok', 'issue_detail': _("Zero acknowledged as intentional")})
            elif action == 'skip':
                if comp:
                    comp.write({'include_in_import': False})
                line.write({'status': 'warning', 'issue_type': False,
                            'issue_detail': _("Skipped — this component will not be imported")})
        self._compute_confidence()
        return self._return_wizard_action()

    def _diagnose(self, original, resolved):
        """Classify one original→resolved pair. Deterministic, no LLM."""
        o = (original or '').strip()
        r = (resolved or '').strip()
        # 1) A sheet-qualified ref survived resolution → converter will choke or zero it.
        if SHEET_REF_RE.search(r):
            return 'broken', 'unresolved_xref', _("Sheet reference not resolved: %s") % r
        o_up = o.upper()
        had_lookup = (bool(SHEET_REF_RE.search(o))
                      or any(fn in o_up for fn in ('VLOOKUP', 'HLOOKUP', 'SUMIF', 'INDEX', 'MATCH', 'LOOKUP')))
        r_body = r.lstrip('=').strip()
        # 2) The whole formula collapsed to 0 — the base handlers replace an
        #    unresolved lookup with "0" (this is the common cross-sheet loss).
        if had_lookup and r_body in ('0', '0.0'):
            return 'broken', 'becomes_zero', _(
                "A reference in %s could not be mapped and became 0") % o
        # 3) A lookup was partially replaced by a bare 0 that wasn't there before.
        if had_lookup and 'VLOOKUP' not in r.upper():
            zeros_before = len(re.findall(r'(?<![\w.])0(?![\w.])', o))
            zeros_after = len(re.findall(r'(?<![\w.])0(?![\w.])', r))
            if zeros_after > zeros_before:
                return 'broken', 'becomes_zero', _(
                    "A reference in %s could not be mapped and became 0") % o
        # 4) otherwise ok (unknown_column / primary_key_miss handled in later tasks)
        return 'ok', False, False


class HrFormulaImportPreviewLine(models.TransientModel):
    _name = 'hr.formula.import.preview.line'
    _description = 'Import resolution preview line (original vs resolved formula)'
    _order = 'sheet_name, component_code'

    wizard_id = fields.Many2one(
        'hr.formula.multisheet.import.wizard',
        string='Wizard', required=True, ondelete='cascade', index=True)

    sheet_name = fields.Char(string='Sheet')
    component_code = fields.Char(string='Component Code')
    component_name = fields.Char(string='Component Name')

    original_excel_formula = fields.Text(string='Original Formula')
    resolved_formula = fields.Text(string='Resolved Formula')

    status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Warning'),
        ('broken', 'Broken'),
    ], string='Status', default='ok')

    # Why a line is not OK. Empty for OK lines.
    issue_type = fields.Selection([
        ('unresolved_xref', 'Unresolved cross-sheet reference'),
        ('unknown_column', 'Unknown column'),
        ('becomes_zero', 'Reference became 0'),
        ('circular', 'Circular reference'),
        ('primary_key_miss', 'Primary key not matched'),
    ], string='Issue Type')
    issue_detail = fields.Text(string='Issue Detail')

    # The remediation the user chose for a problem line (applied in T3.5).
    fix_action = fields.Selection([
        ('map_component', 'Map to component'),
        ('convert_to_input', 'Convert to input'),
        ('acknowledge_zero', 'Acknowledge zero'),
        ('skip', 'Skip this component'),
    ], string='Fix Action')
    fix_target_rule_code = fields.Char(string='Fix Target Component Code')
