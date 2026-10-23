# -*- coding: utf-8 -*-
"""Shadow-run results importer (F6 · T6.3).

Reads a client's historical *results* workbook (employees × components) through
the same multisheet reader the formula importer uses (D6.4 — no new parser),
maps result columns to existing component codes, resolves employees by ref, and
materialises shadow periods/lines. Splitting a mapped column into the input side
vs the expected side is decided by the component's own type: input/constant
components feed the recompute; formula components are the expected results to
compare against.
"""
import base64
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _norm(s):
    return ''.join(ch for ch in (s or '').lower() if ch.isalnum())


class HrFormulaShadowImportWizard(models.TransientModel):
    _name = 'hr.formula.shadow.import.wizard'
    _description = 'Shadow Run Results Importer'

    config_id = fields.Many2one('hr.formula.config', string='Configuration', required=True)
    run_id = fields.Many2one('hr.formula.shadow.run', string='Shadow run')
    import_file = fields.Binary(string='Results workbook (.xlsx)', required=True)
    import_filename = fields.Char()
    sheet_name = fields.Char(string='Sheet')
    period_label = fields.Char(string='Period label', default=lambda s: _('History'))
    employee_ref_header = fields.Char(
        string='Employee-ref column',
        help="The workbook header that holds the employee code/id (e.g. MSNV, Employee Code).")
    sheet_options_json = fields.Text()      # [{name, headers:[...]}]
    mapping_json = fields.Text(
        help="{header: component_code} — auto-filled on analyze, editable before import.")
    state = fields.Selection([('upload', 'Upload'), ('map', 'Map'), ('done', 'Done')],
                             default='upload')
    unmatched_report = fields.Text(readonly=True)

    # ---- analyze --------------------------------------------------------
    def action_analyze(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_("Please choose a results workbook."))
        content = base64.b64decode(self.import_file)
        from ..integrations import ExcelConnector
        conn = ExcelConnector(None)
        wb = conn.load_workbook_multisheet(content, include_formulas=False)
        sheets = []
        for name in wb['sheet_names']:
            try:
                data = conn.load_sheet_with_detection(name)
                headers = [h['value'] for h in data.get('headers', []) if h.get('value')]
            except Exception as e:
                _logger.debug("shadow analyze sheet %s: %s", name, e)
                headers = []
            if headers:
                sheets.append({'name': name, 'headers': headers})
        if not sheets:
            raise UserError(_("No readable sheets with headers were found."))
        self.sheet_options_json = json.dumps(sheets)
        first = sheets[0]
        self.sheet_name = first['name']
        self._autofill_mapping(first['headers'])
        self.state = 'map'
        return self._reopen()

    def _autofill_mapping(self, headers):
        """Match each header to a component code by normalized code/name; guess
        the employee-ref column from common key headers."""
        rules = self.config_id.rule_ids
        by_norm = {}
        for r in rules:
            by_norm[_norm(r.code)] = r.code
            if r.name:
                by_norm.setdefault(_norm(r.name), r.code)
        mapping = {}
        ref_guess = None
        REF_HINTS = {'msnv', 'employeecode', 'empcode', 'employeeid', 'code', 'id',
                     'manv', 'staffid', 'barcode'}
        for h in headers:
            nh = _norm(h)
            if not ref_guess and nh in REF_HINTS:
                ref_guess = h
                continue
            code = by_norm.get(nh)
            if code:
                mapping[h] = code
        self.mapping_json = json.dumps(mapping)
        if ref_guess:
            self.employee_ref_header = ref_guess

    # ---- import ---------------------------------------------------------
    def action_import(self):
        self.ensure_one()
        if not self.employee_ref_header:
            raise UserError(_("Pick the column that identifies the employee."))
        try:
            mapping = json.loads(self.mapping_json or '{}')
        except Exception:
            mapping = {}
        if not mapping:
            raise UserError(_("No columns are mapped to components."))
        content = base64.b64decode(self.import_file)
        from ..integrations import ExcelConnector
        conn = ExcelConnector(None)
        conn.load_workbook_multisheet(content, include_formulas=False)
        data = conn.load_sheet_with_detection(self.sheet_name)
        rows = data.get('data_rows', [])
        if not rows:
            raise UserError(_("The selected sheet has no data rows."))

        # split mapped components into input side vs expected side by type
        rules_by_code = {r.code: r for r in self.config_id.rule_ids}
        input_headers, expected_headers = {}, {}
        for header, code in mapping.items():
            rule = rules_by_code.get(code)
            if not rule:
                continue
            (input_headers if rule.column_type in ('input', 'constant')
             else expected_headers)[header] = code

        run = self.run_id or self.env['hr.formula.shadow.run'].create({
            'name': _('Shadow · %s') % self.config_id.display_name,
            'config_id': self.config_id.id, 'state': 'importing'})
        period = self.env['hr.formula.shadow.period'].create({
            'run_id': run.id, 'period_label': self.period_label or 'History',
            'source_sheet_name': self.sheet_name})

        Line = self.env['hr.formula.shadow.line']
        unmatched = []
        vals = []
        for row in rows:
            ref = row.get(self.employee_ref_header)
            ref = ('' if ref is None else str(ref)).strip()
            if not ref:
                continue
            employee = self._resolve_employee(ref)
            if not employee:
                unmatched.append(ref)
            inputs = {code: row.get(h) for h, code in input_headers.items()}
            expected = {code: row.get(h) for h, code in expected_headers.items()}
            vals.append({
                'period_id': period.id, 'employee_ref': ref,
                'employee_id': employee.id if employee else False,
                'input_values_json': json.dumps(inputs, default=str),
                'expected_values_json': json.dumps(expected, default=str),
                'match_state': 'pending',
            })
        if vals:
            Line.create(vals)
        run.state = 'mapping'
        self.run_id = run.id
        self.unmatched_report = (
            _("%s of %s rows had no matching employee: %s") % (
                len(unmatched), len(rows), ', '.join(unmatched[:20]))
            if unmatched else _("All %s rows matched an employee.") % len(rows))
        self.state = 'done'
        return self._reopen()

    def _resolve_employee(self, ref):
        Emp = self.env['hr.employee']
        for domain in ([('barcode', '=', ref)],
                       [('identification_id', '=', ref)],
                       [('id', '=', int(ref))] if ref.isdigit() else None):
            if domain is None:
                continue
            emp = Emp.search(domain, limit=1)
            if emp:
                return emp
        return Emp.browse()

    def action_open_run(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client', 'tag': 'pb_shadow_run',
            'params': {'run_id': self.run_id.id},
            'name': _('Shadow Parallel Run'),
        }

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}
