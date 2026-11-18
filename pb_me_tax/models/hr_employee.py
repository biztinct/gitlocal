# -*- coding: utf-8 -*-
"""Tax details kept on the employee record, and what My Payobook shows.

Existing fields are reused first (FACTS §D.1): Vietnam's personal tax code
(`vietnam_tax_code`) and Indonesia's NPWP and BPJS numbers
(`pb_npwp_number`, `pb_bpjs_*`). Only what is missing is added here, all
HR-only (`groups='hr.group_hr_user'`): an employee reads their own through
the /my/tax pages under sudo after the session check, never through the ORM.

NOTHING HERE CHANGES A PAYSLIP. These fields are written when HR approves a
request (or when HR edits the record). A pay scheme reads one only through a
registered application source that somebody maps (`formula_sources.py`).

THE VIETNAM "DOES NOT MATCH" NOTE (FACTS S2F-5). Two numbers can say how many
tax dependants a person has: the dependants HR confirmed for tax (the family
flow's tick, `vn_eligible_dependent_count`) and the "registered tax
dependants" component on the running contract (Rize: `VNREGISTER`). This
module never changes the contract component; it only tells HR, read-only,
when the two differ.
"""

import logging

from odoo import _, api, fields, models

from .tax_rules import (
    KINDS_BY_COUNTRY, NUMBER_FIELD, PTKP, REGIMES, SG_FUNDS, SG_RESIDENCY,
    SUPPORTED, TAX_KINDS, mask,
)

_logger = logging.getLogger(__name__)

#: System parameter: the contract component CODE(S) that hold the registered
#: tax dependants count, comma separated, in order of preference — the first
#: code the running contract carries is the one compared. Keyed on the code
#: (what formulas read), never on a label. Defaults: Rize's `VNREGISTER`, the
#: Vietnam starter scheme's / demo world's `DEPS`, the demo `NPT`. Sudima's
#: review scheme keeps no count (only a relief amount, `VNRELIEF`), so no
#: note is shown there. Read-only use; never written by this module.
VN_REGISTER_PARAM = 'pb_me_tax.vn_registered_dependants_codes'
VN_REGISTER_DEFAULT = 'VNREGISTER,DEPS,NPT'


class HrEmployeeTax(models.Model):
    _inherit = 'hr.employee'

    pb_id_ptkp_status = fields.Selection(
        PTKP, string='Indonesia PTKP status', groups='hr.group_hr_user',
        help='The tax-free allowance status the employee declared. Changed '
             'on My Payobook with HR approval, or by HR here.')
    pb_in_pan_number = fields.Char(
        string='India PAN', groups='hr.group_hr_user')
    pb_in_tax_regime = fields.Selection(
        REGIMES, string='India tax regime', groups='hr.group_hr_user',
        help='The income tax regime the employee chose for this tax year.')
    pb_in_uan_number = fields.Char(
        string='India UAN (provident fund)', groups='hr.group_hr_user')
    # Name probed first by the India ESI monthly file (S2-B2 fund_in.py).
    pb_in_esi_number = fields.Char(
        string='India ESI number', groups='hr.group_hr_user',
        help='Employee State Insurance (ESI) insurance number. Kept by HR; '
             'the employee sees it on My Payobook, masked.')
    pb_sg_tax_residency = fields.Selection(
        SG_RESIDENCY, string='Singapore tax residency',
        groups='hr.group_hr_user')
    pb_sg_shg_fund = fields.Selection(
        SG_FUNDS, string='Singapore self-help group fund',
        groups='hr.group_hr_user')

    pb_vn_dependants_check = fields.Char(
        string='Tax dependants check', compute='_compute_pb_vn_dependants_check',
        groups='hr.group_hr_user',
        help='Shown only when the tax dependants HR confirmed differ from the '
             'registered tax dependants on the running contract. Nothing is '
             'changed for you.')
    pb_tax_request_ids = fields.One2many(
        'pb.me.detail.request', 'employee_id', string='Tax detail changes',
        domain=[('kind', 'in', list(TAX_KINDS))], groups='hr.group_hr_user')

    # ============================================================ the check
    def _pbtx_vn_codes(self):
        """The codes, in order of preference (a list, not a set)."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            VN_REGISTER_PARAM, VN_REGISTER_DEFAULT) or ''
        codes = []
        for code in raw.split(','):
            code = code.strip().upper()
            if code and code not in codes:
                codes.append(code)
        return codes

    def _pbtx_running_contract(self):
        """The employee's CURRENT contract: running (state open), started,
        not ended. Never a closed or past contract. Empty when none."""
        self.ensure_one()
        Contract = self.env['hr.contract'].sudo()
        today = fields.Date.context_today(self)
        return Contract.search([
            ('employee_id', '=', self.id), ('state', '=', 'open'),
            ('date_start', '<=', today),
            '|', ('date_end', '=', False), ('date_end', '>=', today)],
            order='date_start desc, id desc', limit=1)

    def _pbtx_vn_counts(self):
        """`(confirmed, registered)` for one employee, or None when either
        number is not kept here (no dependants table, no running contract,
        no registered-dependants component on it)."""
        self.ensure_one()
        emp = self.sudo()
        if 'vn_eligible_dependent_count' not in emp._fields \
                or 'advantages_ids' not in self.env['hr.contract']._fields:
            return None
        contract = emp._pbtx_running_contract()
        if not contract:
            return None
        for code in self._pbtx_vn_codes():
            lines = contract.advantages_ids.filtered(
                lambda a, c=code: (a.advantage_template_id.code or '').upper() == c)
            if lines:
                registered = int(round(sum(lines.mapped('amount'))))
                return emp.vn_eligible_dependent_count, registered
        return None

    @api.depends_context('uid')
    def _compute_pb_vn_dependants_check(self):
        for emp in self:
            note = False
            try:
                counts = emp._pbtx_vn_counts() if emp.id else None
            except Exception:       # noqa: BLE001 — a note must never break a screen
                _logger.warning('pb_me_tax: dependants check failed for %s',
                                emp.id, exc_info=True)
                counts = None
            if counts and counts[0] != counts[1]:
                note = _("Does not match: %(confirmed)s confirmed by HR, "
                         "%(registered)s on the contract. Nothing was changed.",
                         confirmed=counts[0], registered=counts[1])
            emp.pb_vn_dependants_check = note

    # ======================================================= the country
    def _pbtx_country(self):
        """The country of the scheme that pays this person: the scheme map's
        answer first, then the scheme of their newest payslip. '' when
        neither says (the page shows a plain message)."""
        self.ensure_one()
        emp = self.sudo()
        Config = self.env['hr.formula.config'].sudo()
        try:
            schemes = Config.schemes_for_employee(emp)
        except Exception:           # noqa: BLE001 — never break the page
            _logger.warning('pb_me_tax: scheme lookup failed for %s', emp.id,
                            exc_info=True)
            schemes = Config.browse()
        for scheme in schemes:
            if scheme.country_code:
                return scheme.country_code
        slip = self.env['hr.payslip'].sudo().search([
            ('employee_id', '=', emp.id), ('formula_config_id', '!=', False),
            ('state', '!=', 'cancel')], order='date_to desc, id desc', limit=1)
        return slip.formula_config_id.country_code or ''

    def _pbtx_country_name(self, code):
        country = self.env['res.country'].sudo().search(
            [('code', '=', code)], limit=1) if code else None
        return country.name if country else (code or '')

    # ================================================ what /my/tax shows
    def _pbtx_sel(self, field, value):
        options = dict(self._fields[field]._description_selection(self.env))
        return options.get(value, '') if value else ''

    def _pbtx_number_label(self, country):
        _ = self.env._
        return {'VN': _('Personal tax code'), 'ID': _('NPWP (tax number)'),
                'IN': _('PAN (tax number)')}.get(country, _('Tax number'))

    def _pbtx_portal_data(self):
        """Everything the /my/tax page draws, for the caller's OWN employee
        (the controller resolved it from the session). Numbers are masked
        to the last four characters."""
        self.ensure_one()
        _ = self.env._
        emp = self.sudo()
        country = emp._pbtx_country()
        Req = self.env['pb.me.detail.request'].sudo()
        reqs = Req.search([('employee_id', '=', emp.id),
                           ('kind', 'in', list(TAX_KINDS))], limit=20)
        open_kinds = {r.kind for r in reqs if r.state == 'hr_review'}
        kinds = KINDS_BY_COUNTRY.get(country, ())
        rows = []

        def row(key, label, value, kind=None, shown=None, hint=''):
            rows.append({
                'key': key, 'label': label,
                'value': shown if shown is not None else (value or ''),
                'has': bool(value), 'kind': kind if kind in kinds else None,
                'waiting': bool(kind) and kind in open_kinds, 'hint': hint,
            })

        if country in NUMBER_FIELD:
            field = NUMBER_FIELD[country]
            value = emp[field] if field in emp._fields else False
            row('number', emp._pbtx_number_label(country), value,
                kind='tax_number', shown=mask(value))
        if country == 'ID':
            row('ptkp', _('PTKP status'), emp.pb_id_ptkp_status,
                kind='tax_status',
                shown=emp._pbtx_sel('pb_id_ptkp_status', emp.pb_id_ptkp_status))
            bpjs_work = _('BPJS employment number')
            bpjs_health = _('BPJS health number')
            for field, label in (('pb_bpjs_employment_number', bpjs_work),
                                 ('pb_bpjs_health_number', bpjs_health)):
                value = emp[field] if field in emp._fields else False
                row(field, label, value, shown=mask(value),
                    hint=_('Kept by HR'))
        elif country == 'IN':
            row('regime', _('Tax regime'), emp.pb_in_tax_regime,
                kind='tax_regime',
                shown=emp._pbtx_sel('pb_in_tax_regime', emp.pb_in_tax_regime))
            row('uan', _('UAN (provident fund)'), emp.pb_in_uan_number,
                shown=mask(emp.pb_in_uan_number), hint=_('Kept by HR'))
            row('esi', _('ESI number'), emp.pb_in_esi_number,
                shown=mask(emp.pb_in_esi_number), hint=_('Kept by HR'))
        elif country == 'SG':
            row('nric', _('NRIC or FIN'), emp.identification_id,
                shown=mask(emp.identification_id), hint=_('Kept by HR'))
            row('residency', _('Tax residency'), emp.pb_sg_tax_residency,
                shown=emp._pbtx_sel('pb_sg_tax_residency',
                                    emp.pb_sg_tax_residency),
                hint=_('Kept by HR'))
            row('fund', _('Self-help group fund'), emp.pb_sg_shg_fund,
                kind='tax_fund',
                shown=emp._pbtx_sel('pb_sg_shg_fund', emp.pb_sg_shg_fund))
        return {
            'country': country,
            'country_name': emp._pbtx_country_name(country),
            'supported': country in SUPPORTED,
            'rows': rows,
            'dependants': emp._pbtx_dependants() if country == 'VN' else [],
            'requests': [r._pbtx_portal_row() for r in reqs],
        }

    def _pbtx_dependants(self):
        """Vietnam: the registered tax dependants and their state, plus the
        family members waiting for the pay team's tax tick (the family flow
        of My details — read here, never duplicated)."""
        self.ensure_one()
        _ = self.env._
        emp = self.sudo()
        out = []
        if 'vn_dependent_ids' in emp._fields:
            today = fields.Date.context_today(self)
            for dep in emp.vn_dependent_ids.sorted(lambda d: (d.name or '')):
                ended = bool(dep.effective_to and dep.effective_to < today)
                if ended:
                    state, label = 'off', _('No longer counted')
                elif dep.status == 'eligible':
                    state, label = 'ok', _('Counted for tax')
                elif dep.status == 'pending':
                    state, label = 'wait', _('Being checked')
                else:
                    state, label = 'off', _('Not counted')
                out.append({'name': dep.name, 'state': state, 'label': label,
                            'since': dep.effective_from})
        if 'pb.employee.family' in self.env:
            waiting = self.env['pb.employee.family'].sudo().search([
                ('employee_id', '=', emp.id), ('tax_state', '=', 'waiting')])
            for member in waiting:
                out.append({'name': member.name, 'state': 'wait',
                            'label': _('Waiting for the pay team to confirm'),
                            'since': False})
        return out
