"""A server-owned, editable input sheet with a calendar-month comparison.

Comparison values never feed the current month. Drafts belong to one user,
company, scheme and month; confirmation revalidates every resolved source.
"""
import copy
import json
import re
from datetime import date, datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .templates import LIMIT, plain, salary_inputs
from odoo.addons.pb_hr_payroll_formula.models.pay_period import default_standard_work_days

NUMBERS = ('money', 'decimal', 'integer', 'quantity', 'rate')
REQUIRED_TIME = re.compile(r'paid.?days|working.?days|standard.*days|period.?days|days.?worked|ngày công', re.I)


class PayrollInputReview(models.AbstractModel):
    _inherit = 'pb.payroll.templates'

    def _review_catalog(self, cfg):
        catalog = self._catalog(cfg)
        cards = self._cards(cfg)
        layout = self._layout(cfg, catalog)
        by_id = {c['id']: c for c in catalog}
        result = []
        salary_keys = {'rule:%s' % r.id for r in salary_inputs(cfg)}
        for lane in ('time', 'adjustments', 'records', 'available'):
            for fid in layout[lane]:
                if not fid.startswith('rule:'):
                    continue
                c = dict(by_id[fid], tab={'time': 'Time', 'adjustments': 'Monthly adjustments', 'records': 'Employee records', 'available': 'Other inputs'}[lane])
                card = cards.get(c.get('record_id'), {})
                # Legacy schemas may call job titles, dates and selections money.
                ttype = card.get('ttype')
                if c.get('readonly') and ttype in ('char', 'text', 'selection', 'many2one', 'date', 'datetime', 'boolean'):
                    c['kind'] = 'date' if ttype in ('date', 'datetime') else 'boolean' if ttype == 'boolean' else 'text'
                c['required'] = c['id'] in salary_keys or bool(not c.get('readonly') and REQUIRED_TIME.search(c['label']))
                c['positive'] = bool(not c.get('readonly') and REQUIRED_TIME.search(c['label']) and re.search(r'standard|period|working', c['label'], re.I))
                result.append(c)
        return result

    def _resolved_month(self, cfg, period, people, catalog):
        current = self._current(cfg, period, people)
        cards = self._cards(cfg)
        records = self._record_values(cfg, people, cards)
        rows = self.env['pb.payroll.month.inputs'].sudo().search([
            ('config_id', '=', cfg.id), ('company_id', '=', self.env.company.id),
            ('period', '=', period), ('employee_id', 'in', people.ids)])
        saved = {r.employee_id.id: r for r in rows}
        start, end = self._period(period)
        result = {}
        for emp in people:
            row = saved.get(emp.id)
            overrides = row.record_overrides or {} if row else {}
            origins = row.origins or {} if row else {}
            values = {}
            for c in catalog:
                fid = c['id']
                source, detail = 'system', _('Saved monthly inputs')
                if c.get('readonly'):
                    value = records[emp.id].get(c.get('record_id'))
                    record_fid = c.get('record_id') or ''
                    card = cards.get(record_fid, {})
                    origin = _('Contract record') if record_fid.startswith(('f:hr.contract:', 'c:')) else _('Employee record') if record_fid.startswith('f:hr.employee:') else _('Bank account record') if record_fid.startswith('b:') else _('Saved record')
                    detail = '%s · %s' % (origin, card.get('label') or c['label'])
                    if fid in overrides:
                        value, source, detail = overrides[fid], 'edited', _('Saved edit for this month only')
                else:
                    value = current[emp.id].get(fid)
                    if value is None and re.search(r'standard.*days|standard working days', c['label'], re.I):
                        value, source, detail = default_standard_work_days(start, end), 'default', _('Working days for the selected period')
                    elif value is None and c['kind'] in NUMBERS and not REQUIRED_TIME.search(c['label']):
                        value, source, detail = 0, 'default', _('No monthly amount supplied · zero for this month')
                    if fid in origins and value is not None:
                        detail = _('Saved %s input for this month') % origins[fid]
                values[fid] = {'value': plain(value), 'source': source, 'detail': detail,
                               'stored': current[emp.id].get(fid), 'override': fid in overrides}
            result[emp.id] = values
        return result

    def _previous_inputs(self, cfg, period, people, catalog):
        start, _end = self._period(period)
        previous_end = start - timedelta(days=1)
        previous_start = previous_end.replace(day=1)
        previous_period = previous_start.strftime('%Y-%m')
        result = {e.id: {} for e in people}
        # Saved exact-month inputs are a truthful fallback. Never use today's
        # employee/contract values as if they were last month's records.
        prior = self._current(cfg, previous_period, people)
        for eid, values in prior.items():
            for c in catalog:
                if c['id'] in values and not c.get('readonly'):
                    result[eid][c['id']] = {'value': values[c['id']], 'kind': 'saved_inputs'}
        rows = self.env['pb.payroll.month.inputs'].sudo().search([
            ('config_id', '=', cfg.id), ('company_id', '=', self.env.company.id),
            ('period', '=', previous_period), ('employee_id', 'in', people.ids)])
        for row in rows:
            for fid, value in (row.review_snapshot or {}).items():
                result[row.employee_id.id][fid] = {'value': value, 'kind': 'reviewed_inputs'}
        slips = self.env['hr.payslip'].sudo().search([
            ('company_id', '=', self.env.company.id), ('formula_config_id', '=', cfg.id),
            ('employee_id', 'in', people.ids), ('date_from', '>=', previous_start),
            ('date_to', '<=', previous_end), ('state', '!=', 'cancel'),
            ('credit_note', '=', False), ('formula_input_values', '!=', False)], order='id desc')
        # Finalized payroll wins over a newer draft; latest id breaks ties.
        ranked = sorted(slips, key=lambda s: (s.state in ('done', 'paid'), s.id), reverse=True)
        chosen = set()
        for slip in ranked:
            eid = slip.employee_id.id
            if eid in chosen:
                continue
            try:
                inputs = json.loads(slip.formula_input_values or '{}')
            except (ValueError, TypeError):
                continue
            if not isinstance(inputs, dict) or not inputs:
                continue
            chosen.add(eid)
            for c in catalog:
                if c['code'] in inputs:
                    result[eid][c['id']] = {'value': inputs[c['code']],
                        'kind': 'finalized_payroll' if slip.state in ('done', 'paid') else 'computed_payroll'}
        for values in result.values():
            for c in catalog:
                if c['id'] in values:
                    try:
                        values[c['id']]['value'] = self._input_value(values[c['id']]['value'], c['kind'])
                    except (ValueError, TypeError, AttributeError):
                        pass
        return previous_period, result

    def _input_value(self, value, kind):
        if value is None or value == '':
            return None
        if isinstance(value, str) and value.lstrip().startswith(('=', '@')):
            raise ValueError(_('Enter a value, not a formula.'))
        if kind in NUMBERS:
            try:
                return self._numeric(value, kind)
            except (ValueError, TypeError):
                raise ValueError(_('Enter a whole number.') if kind == 'integer' else _('Enter a valid number.')) from None
        if kind == 'date':
            if isinstance(value, datetime):
                return value.date().isoformat()
            try:
                return fields.Date.to_date(value).isoformat()
            except (ValueError, TypeError, AttributeError):
                raise ValueError(_('Use a valid date in YYYY-MM-DD format.')) from None
        if kind == 'boolean':
            if isinstance(value, bool):
                return value
            if str(value).strip().lower() in ('yes', 'true', '1'):
                return True
            if str(value).strip().lower() in ('no', 'false', '0'):
                return False
            raise ValueError(_('Enter Yes or No.'))
        if len(str(value)) > 2000:
            raise ValueError(_('Use 2,000 characters or fewer.'))
        return str(value)

    def _evaluate_grid(self, data):
        changes, issues = [], list(data.get('structural_issues', []))
        stats = dict(changed=0, people_changed=0, excel=0, system=0, edited=0, missing_prior=0, missing=0, issues=0)
        for row in data['grid']['rows']:
            moved = False
            for c in data['grid']['columns']:
                cell = row['cells'][c['id']]
                cell['issue'] = ''
                try:
                    # Inline blanks follow the workbook's keep-current rule.
                    # The grid and materialized payroll must agree after save.
                    raw = cell['current'] if cell['source'] == 'edited' and cell['value'] in (None, '') else cell['value']
                    value = self._input_value(raw, c['kind'])
                    if c.get('positive') and value is not None and value <= 0:
                        raise ValueError(_('Enter a number greater than zero.'))
                    cell['value'] = value
                except (ValueError, TypeError, AttributeError) as err:
                    cell['issue'] = str(err) or _('Enter a valid value.')
                    issues.append('%s · %s: %s' % (row['name'], c['label'], cell['issue']))
                cell['missing'] = bool(c['required'] and (cell['value'] is None or cell['value'] == ''))
                stats['missing'] += int(cell['missing'])
                cell['changed'] = cell['has_prior'] and plain(cell['value']) != cell['prior']
                moved = moved or cell['changed']
                stats['changed'] += int(cell['changed'])
                stats['missing_prior'] += int(not cell['has_prior'])
                stats['issues'] += int(bool(cell['issue']))
                source = cell['source'] if cell['source'] in ('excel', 'edited') else 'system'
                stats[source] += 1
                # This technical write delta is deliberately separate from the
                # calendar-month comparison shown to the payroll reviewer.
                if cell['source'] in ('excel', 'edited') and not cell['issue'] and (
                        cell['value'] != cell['current'] or (c.get('readonly') and not cell['was_override'])):
                    changes.append({'key': '%s:%s' % (row['emp_id'], c['id']), 'emp_id': row['emp_id'],
                        'emp_name': row['name'], 'field_id': c['id'], 'field_label': c['label'],
                        'tab': c['tab'], 'old': cell['stored'], 'value': cell['value']})
            stats['people_changed'] += int(moved)
        data.update(changes=changes, issues=issues, stats=stats)
        return data

    def _review_monthly(self, cfg, period, file_b64, filename):
        wb = self._read(file_b64)
        if '_Payobook' not in wb:
            raise UserError(_('Use a workbook downloaded from Configure Templates.'))
        snapshot = self._get_exchange(cfg, wb['_Payobook']['B1'].value, 'export', shared_export=True).payload
        identity_columns = self._workbook_identity(snapshot)
        code_header = identity_columns[0]['label']
        if snapshot['mode'] != 'monthly' or (not snapshot.get('reusable') and snapshot['period'] != period):
            raise UserError(_('This workbook belongs to a different workflow or pay month.'))
        base_catalog = self._catalog(cfg)
        fingerprint = self._fingerprint(self._layout(cfg, base_catalog), base_catalog)
        layout_changed = snapshot['layout'] != fingerprint
        if layout_changed:
            # Server-owned download columns carry stable input IDs. Cosmetic
            # metadata, order and worksheet placement need no data re-entry.
            # Never drop an old column or silently change its record source.
            current_fields = {c['id']: c for c in base_catalog}
            incompatible = [c['label'] for sheet, cols in snapshot['columns'].items()
                if sheet not in snapshot.get('readonly_sheets', []) for c in cols
                if c['id'] not in current_fields or any(c.get(k) != current_fields[c['id']].get(k)
                    for k in ('readonly', 'record_id'))]
            if incompatible:
                raise UserError(_('These workbook fields were removed or their saved-record source changed: %s. Download the current template and copy your entries into it.') % ', '.join(incompatible[:10]))
        people = self._roster(cfg, period)
        catalog = self._review_catalog(cfg)
        resolved = self._resolved_month(cfg, period, people, catalog)
        previous_period, previous = self._previous_inputs(cfg, period, people, catalog)
        by_row = {v['row']: (int(k), v) for k, v in snapshot['employees'].items()}
        uploads, structural, warnings, seen_tabs = {}, [], [], {}
        reference_only = set()
        if layout_changed:
            warnings.append(_('Template settings changed since download. Your workbook values have been matched to the current input fields. Review all fields below before continuing.'))
        for sheet_name, cols in snapshot['columns'].items():
            # A master snapshot is informational. Ignore the entire sheet,
            # including edited cells, formulas, missing rows or a removed tab.
            # Read current records from the database for payroll instead.
            if sheet_name in snapshot.get('readonly_sheets', []):
                continue
            if sheet_name not in wb:
                structural.append(_('Missing worksheet: %s') % sheet_name)
                continue
            ws = wb[sheet_name]
            if ws.max_row > LIMIT + 1 or ws.max_column > 1000:
                raise UserError(_('The worksheet exceeds the supported size.'))
            headers = [c.value for c in ws[1]]
            ids = {}
            for ci, cell in enumerate(ws[1]):
                if cell.comment and cell.comment.text.startswith('field: '):
                    fid = cell.comment.text.splitlines()[0][7:]
                    if fid in ids:
                        structural.append(_('Duplicate field column: %s') % fid)
                    ids[fid] = ci
            if set(ids) != {c['id'] for c in cols} or not self._validate_identity_headers(headers, identity_columns):
                structural.append(_('The columns in %s changed. Start with a fresh download.') % sheet_name)
                continue
            seen = set()
            for rn, cells in enumerate(ws.iter_rows(min_row=2), 2):
                vals = [c.value for c in cells]
                if all(v is None or v == '' for v in vals):
                    continue
                entry = by_row.get(vals[headers.index('_row')])
                if entry and entry[0] not in resolved and entry[0] not in seen:
                    # A reusable workbook may have been downloaded while a
                    # person was on a review roster. Keep their blank row as
                    # reference when they are no longer eligible. Only the
                    # server-owned export receipt grants this exception;
                    # entered zero/amounts, changed IDs and unknown rows still
                    # require the normal population refusal below.
                    eid, old = entry
                    employee = self.env['hr.employee'].browse(eid).exists()
                    blank = all(c.get('readonly') or vals[ids[c['id']]] in (None, '') for c in cols)
                    if (employee and employee.company_id == self.env.company and blank
                            and self._workbook_code_unchanged(employee, old, identity_columns[0],
                                vals[headers.index(code_header)])):
                        seen.add(eid)
                        reference_only.add(old.get('identity_values', {}).get('code', old['code']))
                        continue
                if not entry or entry[0] not in resolved:
                    structural.append(_('%s row %s: employee is unknown or outside this payroll population.') % (sheet_name, rn))
                    continue
                eid, old = entry
                if eid in seen:
                    structural.append(_('%s row %s: duplicate Employee ID.') % (sheet_name, rn))
                    continue
                seen.add(eid)
                if not self._workbook_code_unchanged(people.browse(eid), old, identity_columns[0], vals[headers.index(code_header)]):
                    structural.append(_('%s row %s: Employee ID cannot be changed.') % (sheet_name, rn))
                for c in cols:
                    value = cells[ids[c['id']]].value
                    if value is None or value == '':
                        continue
                    if c.get('readonly'):
                        if plain(value) != resolved[eid][c['id']]['value']:
                            warnings.append(_('%s · %s: saved records refreshed; workbook context was ignored.') % (people.browse(eid).name, c['label']))
                        continue
                    old_value = old['monthly'].get(c['id'])
                    current = resolved[eid][c['id']]['stored']
                    if not snapshot.get('reusable') and current != old_value and plain(value) != current:
                        warnings.append(_('%s · %s: this month’s saved input changed since download. Your uploaded value is shown for review; confirming replaces only this month’s input.') % (people.browse(eid).name, c['label']))
                    uploads[(eid, c['id'])] = plain(value)
            seen_tabs[sheet_name] = seen
        if reference_only:
            warnings.append(_('Blank rows for %s are reference only because these employees are outside the current payroll population. No payroll inputs were taken from those rows.') % ', '.join(sorted(reference_only)))
        if not seen_tabs.get('Monthly adjustments', set()).issubset(seen_tabs.get('Time', set())):
            structural.append(_('Every adjustment employee must also appear on the Time tab.'))
        rows = []
        for emp in people:
            cells = {}
            for c in catalog:
                fid = c['id']
                base = resolved[emp.id][fid]
                prior = previous[emp.id].get(fid)
                uploaded = (emp.id, fid) in uploads
                cells[fid] = dict(value=uploads[(emp.id, fid)] if uploaded else base['value'],
                    current=base['value'], stored=base['stored'], was_override=base['override'],
                    source='excel' if uploaded else base['source'], detail=filename if uploaded else base['detail'],
                    prior=prior['value'] if prior else None, has_prior=bool(prior),
                    baseline_kind=prior['kind'] if prior else '', system_value=base['value'])
            rows.append({'emp_id': emp.id, 'code': self._code(emp), 'name': emp.name, 'cells': cells})
        payload = self._evaluate_grid({'mode': 'monthly', 'period': period, 'previous_period': previous_period,
            'filename': filename, 'currency': cfg.currency_id.name, 'config_name': cfg.name, 'layout': fingerprint, 'structural_issues': structural,
            'warnings': warnings, 'blanks': 0, 'unchanged': 0,
            'grid': {'columns': catalog, 'rows': rows}})
        receipt = self._exchange(cfg, 'review', payload)
        return dict(payload, token=receipt.token)

    @api.model
    def reopen_monthly_review(self, config_id, token):
        cfg = self._config(config_id, write=True)
        applied = self._get_exchange(cfg, token, 'applied')
        data = copy.deepcopy(applied.payload)
        if not data.get('grid') or data['mode'] != 'monthly':
            raise UserError(_('Choose a confirmed monthly review.'))
        people = self._roster(cfg, data['period'])
        catalog = self._review_catalog(cfg)
        resolved = self._resolved_month(cfg, data['period'], people, catalog)
        previous_period, previous = self._previous_inputs(cfg, data['period'], people, catalog)
        rows = []
        for emp in people:
            cells = {}
            for c in catalog:
                base = resolved[emp.id][c['id']]
                prior = previous[emp.id].get(c['id'])
                cells[c['id']] = dict(value=base['value'], current=base['value'], stored=base['stored'],
                    was_override=base['override'], source=base['source'], detail=base['detail'],
                    prior=prior['value'] if prior else None, has_prior=bool(prior),
                    baseline_kind=prior['kind'] if prior else '', system_value=base['value'])
            rows.append(dict(emp_id=emp.id, code=self._code(emp), name=emp.name, cells=cells))
        data.update(grid=dict(columns=catalog, rows=rows), structural_issues=[], warnings=[], previous_period=previous_period,
            layout=self._fingerprint(self._layout(cfg, self._catalog(cfg)), self._catalog(cfg)))
        self._evaluate_grid(data)
        receipt = self._exchange(cfg, 'review', data)
        return dict(data, token=receipt.token)

    @api.model
    def confirm_monthly_review(self, config_id, token, edits=None):
        cfg = self._config(config_id, write=True)
        self._lock(cfg)
        receipt = self._get_exchange(cfg, token, 'review')
        return self._confirm_monthly(cfg, receipt, edits or [])

    def _confirm_monthly(self, cfg, receipt, edits):
        self.env['pb.payrun.wizard']._require_runner()
        data = copy.deepcopy(receipt.payload)
        if data.get('mode') != 'monthly' or not data.get('grid'):
            raise UserError(_('Open a monthly input review first.'))
        cells = {(r['emp_id'], c['id']): r['cells'][c['id']] for r in data['grid']['rows'] for c in data['grid']['columns']}
        if not isinstance(edits, list) or len(edits) > len(cells):
            raise UserError(_('The edited input list is invalid.'))
        seen = set()
        for edit in edits:
            key = (edit.get('emp_id'), edit.get('field_id'))
            if key not in cells or key in seen:
                raise UserError(_('An edited field is unknown or duplicated.'))
            seen.add(key)
            cell = cells[key]
            if edit.get('restore'):
                cell.update(value=cell['system_value'], source='system', detail=_('Restored saved value'))
            else:
                cell.update(value=edit.get('value'), source='edited', detail=_('Edited in review · this month only'))
        self._evaluate_grid(data)
        if data['issues']:
            raise UserError(_('Resolve the review issues before confirming:\n%s') % '\n'.join(data['issues'][:20]))
        catalog = self._review_catalog(cfg)
        if data['layout'] != self._fingerprint(self._layout(cfg, self._catalog(cfg)), self._catalog(cfg)):
            raise UserError(_('The layout changed. Review a fresh workbook.'))
        people = self._roster(cfg, data['period'])
        if set(people.ids) != {r['emp_id'] for r in data['grid']['rows']}:
            raise UserError(_('The payroll population changed. Review this import again.'))
        resolved = self._resolved_month(cfg, data['period'], people, catalog)
        for row in data['grid']['rows']:
            for c in catalog:
                cell, now = row['cells'][c['id']], resolved[row['emp_id']][c['id']]
                if cell['current'] != now['value'] or cell['stored'] != now['stored'] or cell['was_override'] != now['override']:
                    raise UserError(_('%s · %s changed after review. Review the file again; nothing was applied.') % (row['name'], c['label']))
        Model = self.env['pb.payroll.month.inputs'].sudo()
        for row in data['grid']['rows']:
            saved = Model.search([('config_id', '=', cfg.id), ('company_id', '=', self.env.company.id),
                ('period', '=', data['period']), ('employee_id', '=', row['emp_id'])], limit=1)
            payload = dict(saved.payload or {}) if saved else {}
            overrides = dict(saved.record_overrides or {}) if saved else {}
            origins = dict(saved.origins or {}) if saved else {}
            snapshot = {}
            for c in catalog:
                cell = row['cells'][c['id']]
                snapshot[c['id']] = cell['value']
                if c.get('readonly'):
                    if cell['source'] == 'edited':
                        overrides[c['id']] = cell['value']
                elif cell['value'] is not None:
                    payload[c['id']] = cell['value']
                    origins[c['id']] = cell['source']
            vals = dict(payload=payload, record_overrides=overrides, origins=origins, review_snapshot=snapshot)
            if saved:
                saved.write(vals)
            else:
                Model.create(dict(vals, config_id=cfg.id, company_id=self.env.company.id,
                    employee_id=row['emp_id'], period=data['period']))
        result = {'ok': True, 'written': len(data['changes']), 'pending': False,
                  'reviewed': len(cells), 'changed_since_previous': data['stats']['changed'], 'review_token': receipt.token}
        receipt.write({'kind': 'applied', 'payload': dict(data, result=result, selected=[c['key'] for c in data['changes']])})
        return result
