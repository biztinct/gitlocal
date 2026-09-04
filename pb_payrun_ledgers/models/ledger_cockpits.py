# -*- coding: utf-8 -*-
"""Data RPCs for the three pay-run ledger cockpits (Full & Final, Proration
Audit, Retro Adjustments). Each returns ONE generic descriptor the shared OWL
component renders — KPI strip, facet chips/selects, and rich rows — cloning the
pb.people roster pattern. Read with the caller's own rights (no sudo): if the
user can open the underlying list, they can open the cockpit."""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

LIMIT = 400


def _initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?') + (parts[-1][0] if len(parts) > 1 else '')).upper()


def _emp_avatar(emp):
    return ('/web/image/hr.employee/%s/avatar_128' % emp.id) if emp else ''


def _sel_facet(Model, key, label, field):
    """Facet from a Selection field — chips keyed by the technical value; matched
    against the row's technical value in `_f[key]`."""
    sel = dict(Model._fields[field].selection or [])
    return {'key': key, 'label': label, 'kind': 'chips',
            'chips': [{'id': k, 'label': v} for k, v in sel.items()]}


def _rows_facet(rows, key, label, chip_max=8):
    """Facet built from the loaded rows: distinct `_f[key]` display values. Values
    ARE the labels, so chips always match rows (same-named items — e.g. each
    config's own 'Basic Salary' component — collapse to one chip). Rendered as a
    dropdown once it grows past chip_max; the shared template hides it entirely
    when there is 0/1 distinct value."""
    vals = sorted({(r['_f'].get(key) or '') for r in rows} - {''})
    return {'key': key, 'label': label, 'kind': 'chips' if len(vals) <= chip_max else 'select',
            'chips': [{'id': v, 'label': v} for v in vals]}


def _d(v):
    """A date/datetime as a plain ISO string, or '' — never a Python object."""
    return str(v) if v else ''


def _m2o(rec):
    return rec.display_name if rec else ''


class LedgerMixin(models.AbstractModel):
    _name = 'pb.ledger.mixin'
    _description = 'Pay-run ledger cockpit shared helpers'

    @api.model
    def _co_dom(self):
        return [('company_id', 'in', self.env.companies.ids or [self.env.company.id])]

    @api.model
    def _distinct(self, Model, dom, field):
        try:
            return len(Model.read_group(dom, [field], [field]))
        except Exception:
            return 0

    # ------------------------------------------------------------------ detail
    # The hub's Adjust/Settle lenses replace the row's NAVIGATION with a drawer,
    # so the drawer has to carry the whole story the native form used to. It is
    # a per-click RPC rather than a payload on every row: `get_data` already
    # ships up to 400 rows, and folding twenty more fields into each of them
    # would multiply a list read by the cost of a detail nobody has asked for
    # yet.
    #
    # Read with the CALLER's own rights, exactly like `get_data` — no sudo. The
    # cockpit is not a wider door than the list it replaces (W12), and a row the
    # user could not read is one `get_data` never handed them in the first
    # place. `_detail_model` names the record's model so a forged id cannot be
    # pointed at another table.
    _detail_model = None

    @api.model
    def get_detail(self, rec_id):
        """One row's full story, as sections of labelled fields.

        Returns `{}` for an id that no longer exists: the drawer is opened from
        a row the user is looking at, so the honest answer to "this was deleted
        while you read the grid" is an empty panel, not a traceback.

        An id the caller may NOT read is a different question and it raises —
        `check_access` is the ORM's own refusal and swallowing it would be W40's
        catch that quietly narrows a feature.
        """
        if not self._detail_model:
            return {}
        rec = self.env[self._detail_model].browse(int(rec_id))
        if not rec.exists():
            return {}
        rec.check_access('read')
        d = self._build_detail(rec)
        d['currency'] = self.env.company.currency_id.symbol or ''
        d['id'] = rec.id
        d['res_model'] = self._detail_model
        return d

    def _build_detail(self, rec):
        raise NotImplementedError

    @api.model
    def _section(self, label, fields_):
        """A drawer section; entries whose value is empty are dropped.

        A key with nothing behind it is noise in a 320px panel — and worse, it
        reads as "this record has no batch" when the truth is "this ledger does
        not carry one". Money entries are kept at 0.0 on purpose: a zero
        deduction IS a fact about the settlement.

        The emptiness test is written out by TYPE rather than as
        `value not in ('', None, False)`, because `in` compares with `==` and
        `0.0 == False` — so the tidy one-liner silently dropped every zero
        number as well, which is the opposite of the money rule two lines above.
        """
        keep = []
        for f in fields_:
            v = f.get('value')
            if f.get('money'):
                keep.append(f)
            elif isinstance(v, str) and v.strip():
                keep.append(f)
            elif isinstance(v, (int, float)) and not isinstance(v, bool) and v:
                keep.append(f)
        return {'label': label, 'fields': keep} if keep else None


class PbFullFinal(models.AbstractModel):
    _name = 'pb.fullfinal'
    _inherit = 'pb.ledger.mixin'
    _description = 'Full & Final cockpit data'
    _detail_model = 'hr.full.final.settlement'

    def _build_detail(self, r):
        src = dict(self.env[self._detail_model]._fields['source'].selection or {})
        e = r.employee_id
        return {
            'title': (e.name if e else r.name) or '—',
            'subtitle': r.name or '',
            'sections': [s for s in [
                self._section('Who', [
                    {'label': 'Employee', 'value': e.name if e else ''},
                    {'label': 'Employee ID', 'value': r.employee_code or ''},
                    {'label': 'Department', 'value': _m2o(r.department_id)},
                    {'label': 'Job position', 'value': _m2o(r.job_id)},
                    {'label': 'Contract', 'value': _m2o(r.contract_id)},
                ]),
                self._section('Settlement', [
                    {'label': 'Settlement date', 'value': _d(r.settlement_date)},
                    {'label': 'Month', 'value': r.settlement_month or ''},
                    {'label': 'Period', 'value': ' → '.join(
                        [x for x in [_d(r.date_from), _d(r.date_to)] if x])},
                    {'label': 'Source', 'value': src.get(r.source, r.source or '')},
                ]),
                self._section('Money', [
                    {'label': 'Earnings', 'value': r.total_earnings, 'money': True},
                    {'label': 'Deductions', 'value': r.total_deductions, 'money': True},
                    {'label': 'Net payable', 'value': r.net_payable, 'money': True,
                     'strong': True, 'tone': 'ok'},
                ]),
                self._section('Breakdown', [
                    {'label': 'Basic salary', 'value': r.c_basic, 'money': True},
                    {'label': 'Allowances', 'value': r.c_allow, 'money': True},
                    {'label': 'Overtime', 'value': r.c_ot, 'money': True},
                    {'label': 'Bonus', 'value': r.c_bonus, 'money': True},
                    {'label': 'Unused leave', 'value': r.c_leave, 'money': True},
                    {'label': 'Other earnings', 'value': r.c_other_earn, 'money': True},
                    {'label': 'Personal income tax', 'value': r.c_pit, 'money': True},
                    {'label': 'Social insurance', 'value': r.c_si, 'money': True},
                    {'label': 'Health insurance', 'value': r.c_hi, 'money': True},
                    {'label': 'Unemployment insurance', 'value': r.c_ui, 'money': True},
                    {'label': 'Loan / advance', 'value': r.c_loan, 'money': True},
                    {'label': 'Other deductions', 'value': r.c_other_ded, 'money': True},
                ]),
                self._section('Trace', [
                    {'label': 'Salary structure', 'value': _m2o(r.formula_config_id)},
                    {'label': 'Payroll batch', 'value': _m2o(r.import_batch_id)},
                    {'label': 'Company', 'value': _m2o(r.company_id)},
                ]),
            ] if s],
        }

    @api.model
    def get_data(self):
        FF = self.env['hr.full.final.settlement']
        dom = self._co_dom()
        cur = self.env.company.currency_id
        total = FF.search_count(dom)
        recs = FF.search(dom, order='settlement_date desc, id desc', limit=LIMIT)

        agg = FF.read_group(dom, ['net_payable:sum', 'total_earnings:sum', 'total_deductions:sum'], [])
        a = agg[0] if agg else {}
        kpis = [
            {'icon': 'fileText', 'value': total, 'label': 'Settlements'},
            {'icon': 'receipt', 'ic_tone': 'green', 'money': True, 'value': a.get('net_payable') or 0.0, 'label': 'Net payable'},
            {'icon': 'sigma', 'ic_tone': 'blue', 'money': True, 'value': a.get('total_earnings') or 0.0, 'label': 'Earnings'},
            {'icon': 'sigma', 'ic_tone': 'amber', 'money': True, 'value': a.get('total_deductions') or 0.0, 'label': 'Deductions'},
            {'icon': 'user', 'value': FF.search_count(dom + [('source', '=', 'manual')]), 'label': 'Manual'},
        ]
        src_lbl = dict(FF._fields['source'].selection or [])
        rows = []
        for r in recs:
            e = r.employee_id
            sub = ' · '.join([x for x in [r.department_id.name if r.department_id else '',
                                          r.job_id.name if r.job_id else ''] if x]) or '—'
            rows.append({
                'id': r.id, 'res_model': 'hr.full.final.settlement',
                'avatar': _emp_avatar(e), 'initials': _initials(e.name if e else r.name),
                'title': (e.name if e else r.name) or '—', 'subtitle': sub,
                'badges': [{'label': src_lbl.get(r.source, r.source or '—'),
                            'tone': 'info' if r.source == 'auto' else 'muted'}],
                'metrics': [{'label': 'Net payable', 'value': r.net_payable, 'money': True, 'strong': True, 'tone': 'ok'}],
                'action': {'label': 'Download', 'icon': 'download', 'method': 'action_download_full_and_final'},
                '_f': {'source': r.source or '',
                       'dept': r.department_id.name if r.department_id else '',
                       'config': r.formula_config_id.name if r.formula_config_id else ''},
                '_s': ' '.join([x for x in [e.name if e else '', r.employee_code or '',
                                            r.department_id.name if r.department_id else ''] if x]),
                '_d': str(r.settlement_date) if r.settlement_date else '',
            })
        facets = [
            _sel_facet(FF, 'source', 'Source', 'source'),
            _rows_facet(rows, 'dept', 'Department'),
            _rows_facet(rows, 'config', 'Salary structure'),
        ]
        return {
            'title': 'Full & Final', 'subtitle': 'Every settlement, its components and net payable at a glance.',
            'search_ph': 'Search employee, ID, department…', 'empty': 'No settlements match these filters.',
            'currency': cur.symbol or '', 'date': True, 'kpis': kpis, 'facets': facets,
            'rows': rows, 'total': total,
            'list_action': 'pb_hr_fullandfinal.action_full_and_final_employees',
        }


class PbProration(models.AbstractModel):
    _name = 'pb.proration'
    _inherit = 'pb.ledger.mixin'
    _description = 'Proration Audit cockpit data'
    _detail_model = 'hr.payroll.proration.line'

    def _build_detail(self, r):
        F = self.env[self._detail_model]._fields
        basis = dict(F['proration_basis'].selection or {})
        state = dict(F['state'].selection or {})
        e = r.employee_id
        return {
            'title': e.name if e else '—',
            'subtitle': r.component_id.name if r.component_id else '',
            'sections': [s for s in [
                self._section('Who', [
                    {'label': 'Employee', 'value': e.name if e else ''},
                    {'label': 'Contract', 'value': _m2o(r.contract_id)},
                    {'label': 'Status', 'value': state.get(r.state, r.state or '')},
                ]),
                self._section('Component', [
                    {'label': 'Component', 'value': _m2o(r.component_id)},
                    {'label': 'Code', 'value': r.component_code or ''},
                    {'label': 'Configuration', 'value': _m2o(r.formula_config_id)},
                ]),
                self._section('Period', [
                    {'label': 'Effective date', 'value': _d(r.effective_date)},
                    {'label': 'Period', 'value': ' → '.join(
                        [x for x in [_d(r.date_from), _d(r.date_to)] if x])},
                    {'label': 'Basis', 'value': basis.get(r.proration_basis,
                                                          r.proration_basis or '')},
                    {'label': 'Period days', 'value': r.period_days},
                    {'label': 'Old days', 'value': r.old_days},
                    {'label': 'New days', 'value': r.new_days},
                ]),
                self._section('Money', [
                    {'label': 'Old amount', 'value': r.old_amount, 'money': True},
                    {'label': 'New amount', 'value': r.new_amount, 'money': True},
                    {'label': 'Prorated', 'value': r.prorated_amount, 'money': True,
                     'strong': True, 'tone': 'ok'},
                ]),
                self._section('Trace', [
                    {'label': 'Import batch', 'value': _m2o(r.import_batch_id)},
                    {'label': 'Change reference', 'value': _m2o(r.advantage_change_id)},
                    {'label': 'Segments', 'value': r.segment_summary or '', 'wrap': True},
                ]),
            ] if s],
        }

    @api.model
    def get_data(self):
        PL = self.env['hr.payroll.proration.line']
        dom = self._co_dom()
        cur = self.env.company.currency_id
        total = PL.search_count(dom)
        recs = PL.search(dom, order='date_from desc, id desc', limit=LIMIT)
        agg = PL.read_group(dom, ['prorated_amount:sum'], [])
        pro = (agg[0].get('prorated_amount') if agg else 0.0) or 0.0
        kpis = [
            {'icon': 'sigma', 'value': total, 'label': 'Proration lines'},
            {'icon': 'users', 'ic_tone': 'blue', 'value': self._distinct(PL, dom, 'employee_id'), 'label': 'Employees'},
            {'icon': 'receipt', 'ic_tone': 'green', 'money': True, 'value': pro, 'label': 'Total prorated'},
            {'icon': 'layers', 'ic_tone': 'amber', 'value': self._distinct(PL, dom, 'import_batch_id'), 'label': 'Batches'},
        ]
        rows = []
        for r in recs:
            e = r.employee_id
            rows.append({
                'id': r.id, 'res_model': 'hr.payroll.proration.line',
                'avatar': _emp_avatar(e), 'initials': _initials(e.name if e else ''),
                'title': e.name if e else '—',
                'subtitle': r.component_id.name if r.component_id else '—',
                'code': r.component_code or (r.component_id.code if r.component_id else ''),
                'badges': [{'label': (r.state or '').title(), 'tone': 'ok' if r.state == 'posted' else 'muted'}],
                'metrics': [
                    {'label': 'Old', 'value': r.old_amount, 'money': True},
                    {'label': 'New', 'value': r.new_amount, 'money': True},
                    {'label': 'Prorated', 'value': r.prorated_amount, 'money': True, 'strong': True, 'tone': 'ok'},
                ],
                '_f': {'state': r.state or '',
                       'component': r.component_id.name if r.component_id else '',
                       'config': r.formula_config_id.name if r.formula_config_id else '',
                       'batch': r.import_batch_id.name if r.import_batch_id else ''},
                '_s': ' '.join([x for x in [e.name if e else '', r.component_id.name if r.component_id else '',
                                            r.component_code or ''] if x]),
                '_d': str(r.effective_date) if r.effective_date else '',
            })
        facets = [
            _sel_facet(PL, 'state', 'Status', 'state'),
            _rows_facet(rows, 'component', 'Component'),
            _rows_facet(rows, 'config', 'Configuration'),
            _rows_facet(rows, 'batch', 'Batch'),
        ]
        return {
            'title': 'Proration Audit', 'subtitle': 'Every prorated component, old → new → prorated, per employee.',
            'search_ph': 'Search employee or component…', 'empty': 'No proration lines match these filters.',
            'currency': cur.symbol or '', 'date': True, 'kpis': kpis, 'facets': facets,
            'rows': rows, 'total': total,
            'list_action': 'pb_hr_payroll_formula.action_payroll_proration_line',
        }


class PbRetro(models.AbstractModel):
    _name = 'pb.retro'
    _inherit = 'pb.ledger.mixin'
    _description = 'Retro Adjustments cockpit data'
    _detail_model = 'hr.payroll.retro.adjustment'

    def _build_detail(self, r):
        state = dict(self.env[self._detail_model]._fields['state'].selection or {})
        e = r.employee_id
        delta = r.delta_amount or 0.0
        return {
            'title': e.name if e else '—',
            'subtitle': r.component_id.name if r.component_id else '',
            'sections': [s for s in [
                self._section('Who', [
                    {'label': 'Employee', 'value': e.name if e else ''},
                    {'label': 'Contract', 'value': _m2o(r.contract_id)},
                    {'label': 'Status', 'value': state.get(r.state, r.state or '')},
                ]),
                self._section('Component', [
                    {'label': 'Component', 'value': _m2o(r.component_id)},
                    {'label': 'Code', 'value': r.component_code or ''},
                    {'label': 'Configuration', 'value': _m2o(r.formula_config_id)},
                ]),
                self._section('Period', [
                    {'label': 'Retro period', 'value': ' → '.join(
                        [x for x in [_d(r.period_from), _d(r.period_to)] if x])},
                    {'label': 'Change effective', 'value': _d(r.change_effective_date)},
                ]),
                self._section('Money', [
                    {'label': 'Old amount', 'value': r.old_amount, 'money': True},
                    {'label': 'New amount', 'value': r.new_amount, 'money': True},
                    {'label': 'Delta', 'value': delta, 'money': True, 'strong': True,
                     'tone': 'ok' if delta >= 0 else 'warn'},
                ]),
                self._section('Trace', [
                    {'label': 'Applied in batch', 'value': _m2o(r.applied_in_batch_id)},
                    {'label': 'Applied in payslip', 'value': _m2o(r.applied_in_payslip_id)},
                    {'label': 'Original payslip', 'value': _m2o(r.original_payslip_id)},
                    {'label': 'Change reference', 'value': _m2o(r.advantage_change_id)},
                ]),
            ] if s],
        }

    @api.model
    def get_data(self):
        RA = self.env['hr.payroll.retro.adjustment']
        dom = self._co_dom()
        cur = self.env.company.currency_id
        total = RA.search_count(dom)
        recs = RA.search(dom, order='period_from desc, id desc', limit=LIMIT)
        agg = RA.read_group(dom, ['delta_amount:sum'], [])
        delta = (agg[0].get('delta_amount') if agg else 0.0) or 0.0
        kpis = [
            {'icon': 'sigma', 'value': total, 'label': 'Retro lines'},
            {'icon': 'users', 'ic_tone': 'blue', 'value': self._distinct(RA, dom, 'employee_id'), 'label': 'Employees'},
            {'icon': 'receipt', 'ic_tone': 'green' if delta >= 0 else 'amber', 'money': True, 'value': delta, 'label': 'Total delta'},
            {'icon': 'layers', 'ic_tone': 'amber', 'value': self._distinct(RA, dom, 'applied_in_batch_id'), 'label': 'Batches'},
        ]
        rows = []
        for r in recs:
            e = r.employee_id
            rows.append({
                'id': r.id, 'res_model': 'hr.payroll.retro.adjustment',
                'avatar': _emp_avatar(e), 'initials': _initials(e.name if e else ''),
                'title': e.name if e else '—',
                'subtitle': r.component_id.name if r.component_id else '—',
                'code': r.component_code or (r.component_id.code if r.component_id else ''),
                'badges': [{'label': (r.state or '').title(),
                            'tone': 'ok' if r.state == 'posted' else ('warn' if r.state == 'cancelled' else 'muted')}],
                'metrics': [
                    {'label': 'Old', 'value': r.old_amount, 'money': True},
                    {'label': 'New', 'value': r.new_amount, 'money': True},
                    {'label': 'Delta', 'value': r.delta_amount, 'money': True, 'strong': True,
                     'tone': 'ok' if (r.delta_amount or 0) >= 0 else 'warn'},
                ],
                '_f': {'state': r.state or '',
                       'component': r.component_id.name if r.component_id else '',
                       'config': r.formula_config_id.name if r.formula_config_id else '',
                       'batch': r.applied_in_batch_id.name if r.applied_in_batch_id else ''},
                '_s': ' '.join([x for x in [e.name if e else '', r.component_id.name if r.component_id else '',
                                            r.component_code or ''] if x]),
                '_d': str(r.period_from) if r.period_from else '',
            })
        facets = [
            _sel_facet(RA, 'state', 'Status', 'state'),
            _rows_facet(rows, 'component', 'Component'),
            _rows_facet(rows, 'config', 'Configuration'),
            _rows_facet(rows, 'batch', 'Applied batch'),
        ]
        return {
            'title': 'Retro Adjustments', 'subtitle': 'Retroactive deltas, old → new → delta, per employee.',
            'search_ph': 'Search employee or component…', 'empty': 'No retro adjustments match these filters.',
            'currency': cur.symbol or '', 'date': True, 'kpis': kpis, 'facets': facets,
            'rows': rows, 'total': total,
            'list_action': 'pb_hr_payroll_formula.action_payroll_retro_adjustment',
        }
