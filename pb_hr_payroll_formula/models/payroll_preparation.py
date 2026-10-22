"""Durable, revisioned payroll preparation. Draft edits never mutate HR records.

Only signed revisions feed payroll. Source resolution and final approval use the
same overlay; pending operational approvals and paid-once checks remain upstream.
"""
import json
from decimal import Decimal, InvalidOperation

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .application_payroll_source import _json, _stamp

_TOKEN = object()
_CTX = 'payroll_preparation_token'
_NUMERIC = ('money', 'quantity', 'integer', 'rate')


def _cell_stamp(cell):
    # Coverage signing may turn absent into zero, but must not look like a new source.
    cell = dict(cell)
    if cell.get('status') == 'zero_confirmed':
        cell.update(status='missing', value=None, evidence={})
    return _stamp({k: cell.get(k) for k in ('value', 'status', 'source_ids', 'evidence')})


class PayrollPreparation(models.Model):
    _name = 'hr.payroll.preparation'
    _description = 'Saved payroll preparation'
    _order = 'id desc'

    config_id = fields.Many2one('hr.formula.config', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='config_id.company_id', store=True, index=True)
    owner_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    scope_key = fields.Char(required=True, index=True)
    employee_ids = fields.Many2many('hr.employee', string='People in this preparation')
    revision = fields.Integer(default=1, required=True)
    state = fields.Selection([('draft', 'Being prepared'), ('reviewed', 'Reviewed'),
                              ('sealed', 'Attached to payroll')], default='draft', required=True)
    edits_json = fields.Text(default='{}', required=True)
    review_json = fields.Text(default='{}', required=True)
    reviewed_hash = fields.Char()
    run_id = fields.Many2one('hr.payslip.run', ondelete='set null', index=True)
    event_ids = fields.One2many('hr.payroll.preparation.event', 'preparation_id')

    def init(self):
        self.env.cr.execute("""CREATE UNIQUE INDEX IF NOT EXISTS payroll_preparation_open_scope
            ON hr_payroll_preparation (scope_key) WHERE state != 'sealed'""")

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get(_CTX) is not _TOKEN:
            raise AccessError(_('Open the pay data worksheet to create a preparation.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get(_CTX) is not _TOKEN:
            raise AccessError(_('Use the pay data worksheet to change this preparation.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('Payroll preparations are retained for audit.'))

    def _store(self, vals):
        self.with_context(**{_CTX: _TOKEN}).write(vals)

    def _access(self, edit=False):
        self.ensure_one()
        self.sudo(False).check_access('read')
        self.config_id._application_require_access(certify=edit)
        if self.owner_id.id != self.env.uid:
            raise AccessError(_('This preparation belongs to another payroll preparer.'))

    def _lock(self, revision=None):
        self._access(edit=True)
        self.env.cr.execute('SELECT id FROM hr_payroll_preparation WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.state == 'sealed':
            raise UserError(_('This worksheet is attached to payroll and can no longer be edited.'))
        if revision is not None and self.revision != revision:
            raise UserError(_('This worksheet changed in another tab. Reload it before saving; your unsaved entry is still shown.'))

    def _event(self, kind, payload, mutation=''):
        self.env['hr.payroll.preparation.event'].sudo().with_context(**{_CTX: _TOKEN}).create({
            'preparation_id': self.id, 'user_id': self.env.uid, 'revision': self.revision,
            'kind': kind, 'payload_json': _json(payload), 'mutation': mutation})

    @api.model
    def _open(self, config, employee_ids, start, end):
        config._application_require_access()
        start, end = fields.Date.to_date(start), fields.Date.to_date(end)
        people = self.env['hr.employee'].browse(sorted(set(employee_ids))).exists()
        people.check_access('read')
        if not people or any(e.company_id != config.company_id for e in people) or not start or not end or end < start or (end-start).days > 366:
            raise ValidationError(_('Choose employees and a valid period in this payroll company.'))
        scope = _stamp([self.env.uid, config.id, people.ids, str(start), str(end)])
        # Serialize opening the same scope in two tabs before either row exists.
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s)', [int(scope[:15], 16)])
        draft = self.search([('scope_key', '=', scope), ('state', '!=', 'sealed')], limit=1)
        if not draft:
            draft = self.sudo().with_context(**{_CTX: _TOKEN}).create({
                'config_id': config.id, 'owner_id': self.env.uid, 'date_from': start,
                'date_to': end, 'employee_ids': [(6, 0, people.ids)], 'scope_key': scope}).with_env(self.env)
            draft._event('opened', {'employees': people.ids, 'period': [str(start), str(end)]})
        return draft

    def _rules(self):
        return self.config_id.rule_ids.filtered(lambda r: r.column_type == 'input' and r.application_source_key != 'application.mode')

    def _optional(self, rule):
        return (rule.application_source_key == 'period.input.' + rule.code
                and rule.application_zero_allowed and rule.value_kind in _NUMERIC
                and rule.application_settlement_kind == 'none' and not rule.is_contract_component)

    def _settlement_zero(self, rule):
        """Missing settlement amounts need a separate, explicit no-activity review."""
        return (rule.application_source_key == 'period.input.' + rule.code
                and rule.application_zero_allowed and rule.value_kind in _NUMERIC
                and rule.application_settlement_kind != 'none' and not rule.is_contract_component)

    def _cards(self, for_write=True):
        if 'pb.records.desk' not in self.env:
            return {}
        desk = self.env['pb.records.desk'].with_company(self.company_id)
        if for_write:
            try:
                desk._check_read()
            except (AccessError, UserError):
                return {}
        return {c['component']['id']: c for c in desk._cards(self.config_id.id).values()
                if c.get('component') and c.get('editable') and c.get('group') != 'bank'
                and c.get('ttype') in ('float', 'integer', 'monetary', 'amount', 'char', 'text', 'text_component', 'selection')
                and (not for_write or desk._may_write(c['model']))}

    def _capabilities(self, rule, cell, cards):
        key = rule.application_source_key or ''
        numeric = rule.value_kind in _NUMERIC
        # Pending/conflicting operational sources still require their owner.
        # A signed period review can correct clean time totals and record values
        # for this run without rewriting the underlying HR or attendance records.
        ordinary = key == 'period.input.' + rule.code and rule.application_settlement_kind == 'none'
        card = cards.get(rule.id, {})
        canonical = (key.startswith('employee.') and card.get('id') == 'f:hr.employee:' + key.split('.', 1)[1]
                     or key.startswith('contract.') and card.get('id') == 'f:hr.contract:' + key.split('.', 1)[1])
        stored = (not key and (rule.is_contract_component or rule.id in cards)) or canonical
        reviewable_time = key in ('period.paid_day_equivalents', 'period.standard_days') or (
            key.startswith('period.ot.') and key.endswith('.approved_hours'))
        supported_value = numeric or (rule.value_kind == 'text' and stored)
        editable = supported_value and cell['status'] in ('resolved', 'missing', 'zero_confirmed') and (
            ordinary or stored or (reviewable_time and cell['status'] == 'resolved'))
        future = editable and stored and rule.id in cards and card.get('ttype') != 'selection'
        return bool(editable), bool(future)

    def _raw(self, signed=False):
        if signed:
            review = json.loads(self.review_json)
            return self.config_id.application_preflight(self.employee_ids.ids, self.date_from, self.date_to,
                                                       review.get('certification') or {})
        # Provisional source values are useful before the manager signs coverage.
        # This private read does not certify anything and never feeds a payslip.
        # Actual pending approvals, conflicting time and missing records remain
        # validated by the same resolver. review() signs the real checklist later.
        self.config_id._application_require_access()
        cert = {'channels': {k: True for k in ('leave', 'overtime', 'adjustments', 'timesheets')},
                'employee_ids': sorted(self.employee_ids.ids), 'preview_only': True}
        rows = [self.config_id._application_employee_inputs(e, self.date_from, self.date_to, cert)
                for e in self.employee_ids]
        blockers = [dict(b, employee_id=r['employee_id'], employee=r['name']) for r in rows for b in r['blockers']]
        return {'employees': rows, 'blockers': blockers, 'ok': not blockers}

    def _apply_row(self, row, edits, strict=False):
        if not any(k.startswith(str(row['employee_id']) + ':') for k in edits):
            return row
        rules = {r.code: r for r in self._rules()}
        cards = self._cards(for_write=False)
        for cell in row['inputs']:
            edit = edits.get('%s:%s' % (row['employee_id'], cell['code']))
            if not edit:
                continue
            rule = rules.get(cell['code'])
            editable, future = self._capabilities(rule, cell, cards) if rule else (False, False)
            moved = _cell_stamp(cell) != edit['source_stamp']
            proposal_pending = False
            if edit.get('proposal_id'):
                proposal = self.env['pb.records.apply'].browse(edit['proposal_id']).exists()
                proposal_pending = not proposal or not proposal.applied
                # An approved proposal legitimately replaces the original source.
                if proposal and proposal.applied and cell.get('value') == edit['value']:
                    moved = False
            if not editable or moved or proposal_pending:
                why = (_('Saved record change is waiting for approval.') if proposal_pending else
                       _('The source changed. Restore the source value, or review and enter a new correction.') if moved else
                       _('Correct or approve the source record before overriding this value.'))
                cell.update(status='conflict', reason=why, edited=True)
                row['blockers'].append({'code': cell['code'], 'key': cell['key'], 'reason': why})
                row['ok'] = False
                continue
            evidence = dict(cell.get('evidence') or {})
            evidence['preparation'] = {'id': self.id, 'value': edit['value'], 'original': edit['original'],
                                      'reason': edit['reason'], 'scope': edit['scope'], 'source_stamp': edit['source_stamp']}
            cell.update(value=edit['value'], status='resolved', reason='', evidence=evidence, edited=True)
            row['values'][rule.code] = edit['value']
            row['provenance'][rule.code] = {'src': 'employee_field', 'via': 'application_snapshot',
                'key': cell['key'], 'status': 'resolved', 'evidence': evidence}
            row['blockers'] = [b for b in row['blockers'] if b['code'] != rule.code]
        paid = next((c for c in row['inputs'] if c.get('key') == 'period.paid_day_equivalents'
                     and c['status'] == 'resolved'), None)
        standard_cell = next((c for c in row['inputs'] if c.get('key') == 'period.standard_days'
                              and c['status'] == 'resolved'), None)
        if paid and (paid.get('edited') or standard_cell and standard_cell.get('edited')):
            for cell in row['inputs']:
                if cell.get('key') == 'period.nonpayable_day_equivalents' and cell['status'] in ('resolved', 'zero_confirmed'):
                    standard = standard_cell['value'] if standard_cell else cell.get('evidence', {}).get('standard_days')
                    if standard is not None:
                        evidence = dict(cell['evidence'], derived_from_preparation=self.id,
                                        paid_day_equivalents=paid['value'], standard_days=standard)
                        cell.update(value=round(standard-paid['value'],6), evidence=evidence)
                        row['values'][cell['code']] = cell['value']
                        row['provenance'][cell['code']] = {'src':'employee_field','via':'application_snapshot',
                            'key':cell['key'],'status':'resolved','evidence':evidence}
        row['ok'] = not row['blockers']
        return row

    def _resolved(self, signed=False):
        preview = self._raw(signed)
        edits = json.loads(self.edits_json)
        for row in preview['employees']:
            self._apply_row(row, edits)
        preview['blockers'] = [dict(b, employee_id=r['employee_id'], employee=r['name'])
                               for r in preview['employees'] for b in r['blockers']]
        preview['ok'] = not preview['blockers']
        return preview

    def _fingerprint(self, preview):
        return _stamp({'settings': self.config_id._application_settings_stamp(),
                       'people': preview['employees'], 'edits': json.loads(self.edits_json)})

    def workspace(self):
        self._access()
        preview = self._resolved(signed=self.state in ('reviewed', 'sealed'))
        rules = self._rules()
        cards = self._cards()
        edits = json.loads(self.edits_json)
        columns = []
        for rule in rules:
            key = rule.application_source_key or ''
            columns.append({'id': rule.id, 'code': rule.code, 'name': rule.name, 'kind': rule.value_kind,
                'group': 'adjustments' if key.startswith('period.input.') else 'time' if key.startswith('period.') else 'records',
                'optional': bool(self._optional(rule) or self._settlement_zero(rule)), 'future': rule.id in cards})
        results = self.config_id.rule_ids.filtered(lambda r: r.column_type == 'formula' and
                    (r.appears_on_payslip or r.column_role == 'payroll' and r.net_role != 'info'))
        for rule in results:
            columns.append({'id':rule.id,'code':rule.code,'name':rule.name,'kind':rule.value_kind,
                            'group':'results','optional':False,'future':False,'formula':rule.excel_formula or ''})
        by_code = {r.code: r for r in rules}
        for row in preview['employees']:
            row['cells'] = {}
            for cell in row['inputs']:
                rule = by_code.get(cell['code'])
                if not rule:
                    continue
                editable, future = self._capabilities(rule, cell, cards)
                optional = (self._optional(rule) or self._settlement_zero(rule)) and cell['status'] in ('missing', 'zero_confirmed')
                edit = edits.get('%s:%s' % (row['employee_id'], rule.code))
                issue = cell['status'] == 'conflict' or (cell['status'] == 'missing' and cell['required'] and not optional)
                cell.update(editable=editable, future=future, optional=bool(optional), issue=bool(issue),
                    settlement_zero=bool(optional and self._settlement_zero(rule)),
                    tone='amber' if cell['status'] == 'conflict' else 'red' if issue else 'edited' if edit else 'normal',
                    edit=edit or False, rule_id=rule.id)
                row['cells'][cell['code']] = cell
            preview_values = dict(row['values'])
            for code, cell in row['cells'].items():
                if cell['optional']:
                    preview_values[code] = 0
            calculated = {}
            if results and not any(c['issue'] for c in row['cells'].values()):
                # The payslip evaluator refreshes stored dependency diagnostics.
                # A worksheet preview must never write rules or invalidate its
                # own signed source fingerprint. Reuse the read-only evaluator.
                probe = self.env['hr.formula.sample.data'].new({'config_id': self.config_id.id})
                errors = {}
                calculated = probe._evaluate_rules_with_dependencies(preview_values, readonly=True, errors=errors)
                if errors:
                    calculated = {}
            for rule in results:
                row['cells'][rule.code] = {'code':rule.code,'label':rule.name,'rule_id':rule.id,
                    'value':calculated.get(rule.code),'status':'preview','editable':False,'future':False,
                    'optional':False,'issue':False,'tone':'normal','edit':False,'source_owner':'Payroll calculation',
                    'reason':'Preview only. Final payroll is computed after the signed period review.'}
            # Global period review is one checklist, never repeated for each person.
            row['issues'] = [b for b in row['blockers'] if b['code'] in row['cells'] and row['cells'][b['code']]['issue']]
        global_issues = list({b['reason']: b for b in preview['blockers'] if not b['code'] and
                             b.get('key') not in ('leave', 'overtime', 'adjustments', 'timesheets')}.values())
        issue_count = sum(c['issue'] for p in preview['employees'] for c in p['cells'].values())
        people = []
        for row in preview['employees']:
            cells = {code: {k: v for k, v in cell.items() if k not in ('evidence', 'source_ids')}
                     for code, cell in row['cells'].items()}
            people.append({'employee_id': row['employee_id'], 'name': row['name'], 'cells': cells, 'issues': row['issues']})
        return {'id': self.id, 'revision': self.revision, 'state': self.state, 'name': self.config_id.name,
                'period': [str(self.date_from), str(self.date_to)], 'currency': self.config_id.currency_id.name,
                'columns': columns, 'people': people, 'global_issues': global_issues,
                'issues': issue_count, 'affected': sum(any(c['issue'] for c in p['cells'].values()) for p in preview['employees']),
                'changes': len(edits), 'optional': sum(c['optional'] for p in preview['employees'] for c in p['cells'].values()),
                'settlement_zeros': sum(c.get('settlement_zero', False) for p in preview['employees'] for c in p['cells'].values()),
                'ready': self.state == 'reviewed' and preview['ok'] and self.reviewed_hash == self._fingerprint(self._resolved(True)),
                'review': json.loads(self.review_json), 'saved_at': str(self.write_date),
                'timesheets': self.config_id.payroll_basis == 'timesheet',
                'history': [{'kind': e.kind, 'at': str(e.create_date), 'user': e.user_id.name,
                             'revision': e.revision, 'data': json.loads(e.payload_json)} for e in self.event_ids.sorted('id', reverse=True)[:30]]}

    def save_cells(self, revision, mutation, changes):
        self._access(edit=True)
        if not isinstance(mutation, str) or not 8 <= len(mutation) <= 100 or not isinstance(changes, list) or len(changes) > 500:
            raise ValidationError(_('Save up to 500 cells at a time with a unique save reference.'))
        self._lock()
        prior = self.event_ids.filtered(lambda e: e.mutation == mutation)
        if prior:
            if json.loads(prior[0].payload_json).get('request_hash') != _stamp(changes):
                raise ValidationError(_('This save reference was already used for a different correction.'))
            return self.workspace()
        if revision != self.revision:
            raise UserError(_('This worksheet changed in another tab. Reload before saving.'))
        preview = self._raw()
        cells = {(p['employee_id'], c['code']): c for p in preview['employees'] for c in p['inputs']}
        rules = {r.code: r for r in self._rules()}
        cards = self._cards()
        edits = json.loads(self.edits_json)
        audit = []
        seen = set()
        for change in changes:
            if not isinstance(change, dict) or set(change) - {'employee_id', 'code', 'value', 'scope', 'reason', 'restore'}:
                raise ValidationError(_('Use the worksheet cell controls.'))
            pair = (int(change.get('employee_id') or 0), change.get('code'))
            if pair in seen or pair not in cells or pair[1] not in rules:
                raise ValidationError(_('Choose each cell once within this preparation.'))
            seen.add(pair)
            cell, rule = cells[pair], rules[pair[1]]
            key = '%s:%s' % pair
            old = edits.get(key)
            if old and old.get('proposal_id'):
                proposal = self.env['pb.records.apply'].browse(old['proposal_id']).exists()
                if proposal and proposal.state in ('draft', 'pending'):
                    raise UserError(_('This change is waiting for record approval. Review its proposal before replacing it.'))
            if change.get('restore'):
                edits.pop(key, None)
                audit.append(dict(change, before=old, after=None))
                continue
            editable, future = self._capabilities(rule, cell, cards)
            scope = change.get('scope', 'run')
            if not editable or scope not in ('run', 'future') or scope == 'future' and not future:
                raise AccessError(_('This source must be corrected in its own record.'))
            reason = (change.get('reason') or '').strip()
            if rule.value_kind == 'text':
                value = change.get('value')
                if not isinstance(value, str) or len(value) > 1000 or '\x00' in value:
                    raise ValidationError(_('Enter a text value of up to 1,000 characters.'))
                number = None
            else:
                try:
                    number = Decimal(str(change.get('value')))
                    if not number.is_finite() or abs(number) > Decimal('1e15') or rule.value_kind == 'integer' and number != number.to_integral_value():
                        raise InvalidOperation
                except (InvalidOperation, ValueError):
                    raise ValidationError(_('Enter a finite number using a decimal point, without thousands separators.'))
                if rule.application_source_key == 'period.standard_days' and not 0 < number <= max(31, (self.date_to-self.date_from).days+1):
                    raise ValidationError(_('Standard days must be positive and fit this payroll period.'))
                if rule.application_source_key.startswith('period.ot.') and not 0 <= number <= 24 * ((self.date_to-self.date_from).days+1):
                    raise ValidationError(_('Overtime hours must be nonnegative and fit this payroll period.'))
                value = int(number) if rule.value_kind == 'integer' else float(number)
            edit = {'value': value, 'decimal': str(number) if number is not None else None, 'scope': scope, 'reason': reason,
                    'original': cell.get('value'), 'source_stamp': _cell_stamp(cell),
                    'source_evidence': {k: cell.get(k) for k in ('source_ids', 'evidence', 'key', 'source_owner')},
                    'editor': self.env.uid, 'at': str(fields.Datetime.now()),
                    'field_id': cards[rule.id]['id'] if scope == 'future' else False}
            edits[key] = edit
            audit.append({'employee_id': pair[0], 'code': pair[1], 'before': old, 'after': edit})
        # Validate the final batch, so a pasted standard/paid-day pair is atomic
        # and independent of column order. Existing corrections count as well.
        for employee_id in {pair[0] for pair in seen}:
            time_values = {}
            for (eid, code), cell in cells.items():
                if eid == employee_id and cell.get('key') in ('period.standard_days', 'period.paid_day_equivalents'):
                    time_values[cell['key']] = edits.get('%s:%s' % (eid, code), {}).get('value', cell.get('value'))
            paid = time_values.get('period.paid_day_equivalents')
            standard = time_values.get('period.standard_days')
            if paid is not None and standard is None:
                employee = self.env['hr.employee'].browse(employee_id)
                contract, ambiguous = self.config_id._application_contract(employee, self.date_from, self.date_to)
                standard = self.config_id._application_time_values(employee, contract, self.date_from, self.date_to, {})['period.standard_days'].get('value')
            if paid is not None and (standard is None or paid < 0 or paid > standard):
                raise ValidationError(_('Paid days must be between zero and the standard days for this period.'))
        self._store({'edits_json': _json(edits), 'revision': self.revision+1, 'state': 'draft', 'reviewed_hash': False})
        self._event('cells_saved', {'request_hash': _stamp(changes), 'changes': audit}, mutation)
        return self.workspace()

    def submit_record_changes(self, revision):
        self._lock(revision)
        edits = json.loads(self.edits_json)
        future = {k: v for k, v in edits.items() if v['scope'] == 'future' and not v.get('proposal_id')}
        if not future:
            return self.workspace()
        if 'pb.records.desk' not in self.env:
            raise UserError(_('Records Desk is required to submit saved-record changes.'))
        current = self._raw()
        current_cells = {'%s:%s' % (p['employee_id'], c['code']): c for p in current['employees'] for c in p['inputs']}
        if any(_cell_stamp(current_cells[k]) != v['source_stamp'] for k, v in future.items()):
            raise UserError(_('A source changed since your edit. Review it before submitting record changes.'))
        desk = self.env['pb.records.desk'].with_company(self.company_id)
        probe = desk._probe(self.config_id.id)
        for key, edit in future.items():
            if edit['field_id'].startswith(('c:', 'f:hr.contract:')):
                employee = self.env['hr.employee'].browse(int(key.split(':')[0]))
                effective, ambiguous = self.config_id._application_contract(employee, self.date_from, self.date_to)
                if ambiguous or probe._get_latest_contract(employee) != effective:
                    raise UserError(_('The saved contract differs from this period’s contract. Open the contract record to make an effective-dated change.'))
        changes = [{'emp_id': int(k.split(':')[0]), 'field_id': v['field_id'], 'value': v['value']} for k, v in future.items()]
        result = self.env['pb.records.desk'].with_company(self.company_id).apply_changes(
            self.config_id.id, changes, _('Payroll preparation #%s: update saved records on approval', self.id))
        if result.get('refused') or not result.get('apply_id'):
            raise UserError(_('The record change was not accepted: %s', _json(result.get('refused') or result)))
        for edit in future.values():
            edit['proposal_id'] = result['apply_id']
        self._store({'edits_json': _json(edits), 'revision': self.revision+1, 'state': 'draft', 'reviewed_hash': False})
        self._event('record_changes_submitted', result)
        return self.workspace()

    def review(self, revision, channels, reason):
        self._lock(revision)
        required = ['leave', 'overtime', 'adjustments'] + (['timesheets'] if self.config_id.payroll_basis == 'timesheet' else [])
        if not isinstance(channels, dict) or any(channels.get(k) is not True for k in required) or not (reason or '').strip():
            raise ValidationError(_('Confirm the period checklist and add a review note.'))
        allowed_settlement_keys = {r.application_source_key for r in self._rules() if self._settlement_zero(r)}
        settlement_keys = sorted({cell['key'] for row in self._raw()['employees'] for cell in row['inputs']
                                  if cell.get('key') in allowed_settlement_keys and cell['status'] in ('missing', 'zero_confirmed')})
        if settlement_keys:
            if channels.get('settlements') is not True:
                raise ValidationError(_('Explicitly confirm no settlement activity for eligible empty settlement amounts.'))
        edits = json.loads(self.edits_json)
        if any(v['scope'] == 'future' and not v.get('proposal_id') for v in edits.values()):
            raise UserError(_('Submit your saved-record changes before completing the review.'))
        for edit in edits.values():
            if not edit['reason']:
                edit['reason'] = reason.strip()
        self._store({'edits_json': _json(edits)})
        zero_keys = [r.application_source_key for r in self._rules() if self._optional(r)] + settlement_keys
        cert = {'channels': {k: bool(channels.get(k)) for k in required}, 'zero_keys': sorted(zero_keys),
                'employee_ids': sorted(self.employee_ids.ids)}
        review = {'certification': cert, 'reason': reason.strip(), 'by': self.env.uid, 'at': str(fields.Datetime.now()),
                  'settlement_no_activity': bool(settlement_keys), 'settlement_zero_keys': settlement_keys}
        self._store({'review_json': _json(review)})
        preview = self._resolved(True)
        if not preview['ok']:
            raise UserError(_('Resolve the highlighted cells and period issues before completing review.'))
        review['zero_cells'] = [[p['employee_id'], c['code']] for p in preview['employees'] for c in p['inputs'] if c['status'] == 'zero_confirmed']
        self._store({'review_json': _json(review), 'reviewed_hash': self._fingerprint(preview), 'state': 'reviewed', 'revision': self.revision+1})
        self._event('reviewed', review)
        return self.workspace()

    def _assert_scope(self, config, ids, start, end):
        self._access(edit=True)
        if (config != self.config_id or sorted(ids) != sorted(self.employee_ids.ids)
                or fields.Date.to_date(start) != self.date_from or fields.Date.to_date(end) != self.date_to):
            raise AccessError(_('This worksheet belongs to a different payroll scope.'))
        self._lock()
        if self.state != 'reviewed' or self.reviewed_hash != self._fingerprint(self._resolved(True)):
            raise UserError(_('Open Review pay data and confirm the latest saved values before computing.'))

    def _attach(self, run):
        self._store({'state': 'sealed', 'run_id': run.id})
        run.with_context(**{_CTX: _TOKEN}).write({'payroll_preparation_id': self.id})
        self._event('attached_to_payroll', {'run_id': run.id, 'reviewed_hash': self.reviewed_hash})


class PayrollPreparationEvent(models.Model):
    _name = 'hr.payroll.preparation.event'
    _description = 'Payroll preparation audit event'
    _order = 'id desc'
    preparation_id = fields.Many2one('hr.payroll.preparation', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='preparation_id.company_id', store=True)
    user_id = fields.Many2one('res.users', required=True)
    revision = fields.Integer(required=True)
    kind = fields.Char(required=True)
    payload_json = fields.Text(required=True)
    mutation = fields.Char(index=True)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get(_CTX) is not _TOKEN:
            raise AccessError(_('Audit events are created by worksheet actions.'))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_('Payroll review history is immutable.'))

    def unlink(self):
        raise AccessError(_('Payroll review history is retained.'))


class PreparationRun(models.Model):
    _inherit = 'hr.payslip.run'
    payroll_preparation_id = fields.Many2one('hr.payroll.preparation', readonly=True, copy=False, ondelete='restrict')

    def write(self, vals):
        if 'payroll_preparation_id' in vals and self.env.context.get(_CTX) is not _TOKEN:
            raise AccessError(_('Only a reviewed worksheet can be attached to payroll.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('payroll_preparation_id') for v in vals_list):
            raise AccessError(_('Attach a reviewed worksheet after creating the run.'))
        return super().create(vals_list)


class PreparationSource(models.Model):
    _inherit = 'hr.formula.config'

    def _application_employee_inputs(self, employee, start, end, certification):
        row = super()._application_employee_inputs(employee, start, end, certification)
        run_id = (certification or {}).get('run_id')
        if run_id:
            run = self.env['hr.payslip.run'].browse(run_id).exists()
            prep = run.payroll_preparation_id
            if prep:
                if (prep.state != 'sealed' or prep.run_id != run or prep.config_id != self
                        or employee not in prep.employee_ids or start != prep.date_from or end != prep.date_to):
                    raise AccessError(_('Payroll preparation does not match this run.'))
                # Validate the signed run certificate; a client-supplied run ID is not authority.
                if certification != run._application_certification(employee.id):
                    raise AccessError(_('Use this run’s signed payroll review.'))
                prep._apply_row(row, json.loads(prep.edits_json), strict=True)
                row['preparation'] = {'id': prep.id, 'revision': prep.revision, 'reviewed_hash': prep.reviewed_hash}
        return row
