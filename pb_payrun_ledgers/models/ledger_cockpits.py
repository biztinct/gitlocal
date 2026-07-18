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


class PbFullFinal(models.AbstractModel):
    _name = 'pb.fullfinal'
    _inherit = 'pb.ledger.mixin'
    _description = 'Full & Final cockpit data'

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
