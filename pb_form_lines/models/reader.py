# -*- coding: utf-8 -*-
"""THE READER — the figures of a government form for a period.

This is the contract later forms (year-end certificates, fund files) build on.
It is binding (WDGAP S2 handover §S2-A.3)::

    env['pb.gov.form.reader'].read(form, company, period_start, period_end,
                                   scheme_ids=None, currency_id=None)
    -> {
        'lines':       {line_code: amount},          # totals (text lines absent)
        'employees':   [{'employee_id', 'name', 'lines': {code: value},
                         'identity': {...}, 'resident': bool,
                         'payslip_ids': [...], 'scheme_ids': [...]}],
        'payslip_ids': [...],
        'warnings':    [{'code', 'level', 'message', 'employee_ids'}],
        # extras (stable keys, may grow):
        'form', 'company_id', 'period_start', 'period_end', 'currency',
        'currency_id', 'currencies', 'schemes', 'tax_years', 'unfinished_count',
    }

The rules it keeps, each from an earlier phase:

  * FINISHED PAYSLIPS ONLY (`done` / `paid`) — never draft or waiting
    (WDGAP S2F-3). Unfinished ones in the period are counted in a warning.
  * PAY MONTH = the month the payslip's period ENDS in (fund payments' rule):
    a payslip is in the period when `period_start <= date_to <= period_end`.
  * LINES BY (scheme, code), one SQL read, as fund payments reads them
    (`pb_fund_payments/models/fund_payment.py` `_pb_read`).
  * ONE PAY-BAND RULE for signs: money taken off pay and employer cost are
    counted by size (`abs()`), a back-pay line of those roles by what it does
    to its total (`pb_backpay_band_amount`, pb_retro, read by probe — ledger
    W2D2-2); everything else as the payslip has it. A map row may then take
    an item away or take a share of it.
  * WORKED-OUT VALUES (`hr.payslip.formula_computed_values`, then the input
    values) for items that are not printed (S2F-6).
  * TAX YEAR from the scheme (`tax_year_start_month`, ledger W2A-4): reported
    per scheme; a period that crosses the start of a tax year is warned.
  * NEVER TWO CURRENCIES: with schemes in two currencies and no currency
    chosen, nothing is added up — the answer lists the currencies and says so.
  * MULTI-COMPANY: payslips of `company` only (`hr.payslip.run` has no company,
    ledger IDB1-1, so the payslip's own company is read).
  * IDENTITY from the employee record through per-country hooks
    (`_pb_identity_<cc>`); a missing number is a warning, never a crash, and
    no warning text ever contains a tax number.

Reads run under sudo AFTER the caller's door: `read` itself asks for the
payroll officer right, so the model cannot be used as a back door over RPC.
"""
import json
import logging
from collections import OrderedDict, defaultdict
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_hr_payroll_formula.models import tax_year as TY

_logger = logging.getLogger(__name__)

DONE_STATES = ('done', 'paid')
UNFINISHED_STATES = ('draft', 'verify', 'level1', 'level2')
#: Category codes a pre-stamp line is "taken off" by (the band fallback).
DEDUCTION_CATEGORIES = ('DED', 'DEDUCTION', 'COMP')
SIZE_ROLES = ('deduction', 'employer_cost')


def _num(value):
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(',', '').strip())
    except (TypeError, ValueError):
        return None


def month_bounds(day):
    day = fields.Date.to_date(day)
    first = day.replace(day=1)
    nxt = date(first.year + (first.month // 12), first.month % 12 + 1, 1)
    return first, nxt - timedelta(days=1)


class PbGovFormReader(models.AbstractModel):
    _name = 'pb.gov.form.reader'
    _description = 'Government form figures from finished payslips'

    # ================================================================ periods
    @api.model
    def period_bounds(self, form, day, config=None):
        """(start, end) of the form's period containing `day`: the calendar
        month; a quarter / tax year of the SCHEME's tax year (January when
        no scheme is given)."""
        form = self._pb_form(form)
        day = fields.Date.to_date(day)
        # the scheme's tax year when one is given, else the authority's own
        # (WDGAP S2-B: India's April year on a form, January otherwise)
        month = TY.month_of(config) if config else TY.month_of(form.year_start_month or 1)
        if form.period_kind == 'month':
            return month_bounds(day)
        if form.period_kind == 'quarter':
            return TY.tax_quarter_bounds(month, day)
        return TY.tax_year_bounds(month, day)

    # ================================================================ helpers
    @api.model
    def _pb_form(self, form):
        if isinstance(form, models.BaseModel):
            return form.sudo()
        if isinstance(form, str):
            found = self.env['pb.gov.form'].sudo().search([('code', '=', form)], limit=1)
        else:
            found = self.env['pb.gov.form'].sudo().browse(int(form or 0)).exists()
        if not found:
            raise UserError(_("That government form is not available here."))
        return found

    @api.model
    def _pb_company_rec(self, company):
        if isinstance(company, models.BaseModel):
            return company
        if not company:
            return self.env.company
        return self.env['res.company'].browse(int(company))

    @api.model
    def _pb_currency_of(self, config):
        return config.currency_id or config.company_id.currency_id or self.env.company.currency_id

    @api.model
    def _pb_warn(self, out, code, message, level='warn', employee_ids=None):
        out['warnings'].append({'code': code, 'level': level, 'message': message,
                                'employee_ids': sorted(set(employee_ids or []))})

    # ============================================================== identity
    @api.model
    def _pb_field(self, emp, name):
        if name not in emp._fields:
            return False
        return emp[name]

    @api.model
    def _pb_identity(self, form, employee):
        """{'values': {...}, 'resident': bool, 'missing': [labels]} for one
        person, per country (`_pb_identity_<cc>`); the base answer knows only
        the name and the national ID."""
        hook = getattr(self, '_pb_identity_%s' % (form.country_code or '').lower(), None)
        if hook is None:
            return {'values': {'name': employee.name or '',
                               'national_id': employee.identification_id or ''},
                    'resident': True, 'missing': []}
        return hook(form, employee)

    @api.model
    def _pb_identity_id(self, form, employee):
        """Indonesia: NIK (the national ID, also the tax number of a resident
        since 2024), NPWP, passport for a foreign employee, tax status (PTKP)
        and the position. `pb_npwp_number` is read by probe (pb_employee_vault);
        a tax-status field on the employee record (Step 2 phase S2-D) is read
        by probe too — until then the status comes from a mapped pay item."""
        emp = employee.sudo()
        nik = ''.join(ch for ch in (emp.identification_id or '') if ch.isdigit())
        npwp = ''.join(ch for ch in (self._pb_field(emp, 'pb_npwp_number') or '') if ch.isdigit())
        passport = (emp.passport_id or '').strip()
        ptkp = ''
        # `pb_id_ptkp_status` is pb_me_tax's field (WDGAP S2-D, approved by
        # HR); the others are older names kept for safety
        for name in ('pb_id_ptkp_status', 'pb_ptkp_status', 'pb_tax_ptkp_status',
                     'ptkp_status'):
            value = self._pb_field(emp, name)
            if value:
                ptkp = str(value)
                break
        tin = nik if len(nik) == 16 else (npwp if len(npwp) in (15, 16) else '')
        resident = bool(tin) or not passport
        missing = []
        if not tin and not passport:
            missing.append(_("NIK or tax number"))
        return {
            'values': {'name': emp.name or '', 'tin': tin, 'passport': passport,
                       'ptkp': ptkp,
                       'position': (emp.job_title or emp.job_id.name or '').strip()},
            'resident': resident,
            'missing': missing,
        }

    @api.model
    def _pb_identity_vn(self, form, employee):
        """Vietnam: personal tax code and tax residency. `pb_vn_tax_resident`
        (pb_payroll_mapping_vn) wins over the older `vn_residency_status`;
        both read by probe, resident when neither exists."""
        emp = employee.sudo()
        tax_code = (self._pb_field(emp, 'vietnam_tax_code') or '').strip()
        if 'pb_vn_tax_resident' in emp._fields:
            resident = bool(emp.pb_vn_tax_resident)
        elif 'vn_residency_status' in emp._fields:
            resident = (emp.vn_residency_status or 'resident') != 'non_resident'
        else:
            resident = True
        missing = [] if tax_code else [_("personal tax code")]
        return {'values': {'name': emp.name or '', 'tax_code': tax_code,
                           'national_id': emp.identification_id or '',
                           'passport': (emp.passport_id or '').strip(),
                           'nationality': emp.country_id.name or '',
                           'address': self._pb_home_address(emp)},
                'resident': resident, 'missing': missing}

    @api.model
    def _pb_home_address(self, emp):
        """The person's private address on one line (empty when none)."""
        parts = []
        for name in ('private_street', 'private_street2', 'private_city'):
            value = self._pb_field(emp, name)
            if value:
                parts.append(str(value).strip())
        state = self._pb_field(emp, 'private_state_id')
        if state:
            parts.append(state.name or '')
        return ', '.join(p for p in parts if p)

    @api.model
    def _pb_identity_in(self, form, employee):
        """India: PAN and the tax regime the person chose. Both are kept by
        pb_me_tax on the employee record (WDGAP S2-D: `pb_in_pan_number`,
        `pb_in_tax_regime`) and read by probe; the older contract copy of the
        PAN (`pan_number`, legacy India module) is read when the employee has
        none. A missing PAN is a warning, never a crash."""
        emp = employee.sudo()
        pan = (self._pb_field(emp, 'pb_in_pan_number') or '').strip().upper()
        if not pan:
            Contract = self.env['hr.contract'].sudo()
            if 'pan_number' in Contract._fields:
                contract = Contract.search([('employee_id', '=', emp.id)],
                                           order='date_start desc, id desc', limit=1)
                pan = (contract.pan_number or '').strip().upper()
        regime = self._pb_field(emp, 'pb_in_tax_regime') or ''
        return {
            'values': {'name': emp.name or '', 'pan': pan, 'regime': regime,
                       'employee_number': self._pb_field(emp, 'registration_number') or '',
                       'position': (emp.job_title or emp.job_id.name or '').strip(),
                       'address': self._pb_home_address(emp)},
            'resident': True,
            'missing': [] if pan else [_("PAN")],
        }

    @api.model
    def _pb_identity_sg(self, form, employee):
        """Singapore: the tax reference (NRIC or FIN, kept in the national ID
        box, as pb_me_tax shows it), its kind for IRAS (1 NRIC: S/T…, 2 FIN:
        F/G/M…, 4 work permit, 12 passport), date of birth, sex, tax
        residency (`pb_sg_tax_residency`, pb_me_tax, by probe). Never a
        made-up number: a person with none of them is missing it."""
        emp = employee.sudo()
        ident = (emp.identification_id or '').strip().upper().replace(' ', '')
        permit = (self._pb_field(emp, 'permit_no') or '').strip().upper()
        passport = (emp.passport_id or '').strip().upper()
        id_type, number = '', ''
        if ident and ident[0] in 'ST':
            id_type, number = '1', ident
        elif ident and ident[0] in 'FGM':
            id_type, number = '2', ident
        elif permit:
            id_type, number = '4', permit
        elif passport:
            id_type, number = '12', passport
        residency = self._pb_field(emp, 'pb_sg_tax_residency') or ''
        gender = self._pb_field(emp, 'sex') or self._pb_field(emp, 'gender') or ''
        birthday = self._pb_field(emp, 'birthday')
        missing = []
        if not number:
            missing.append(_("NRIC or FIN"))
        return {
            'values': {'name': emp.name or '', 'id_type': id_type, 'id_number': number,
                       'birthday': fields.Date.to_string(birthday) if birthday else '',
                       'sex': {'male': 'M', 'female': 'F'}.get(gender, ''),
                       'position': (emp.job_title or emp.job_id.name or '').strip(),
                       'residency': residency,
                       'nationality': emp.country_id.name or '',
                       'address': self._pb_home_address(emp),
                       'postal_code': (self._pb_field(emp, 'private_zip') or '').strip()},
            'resident': residency != 'non_resident',
            'missing': missing,
        }

    # ================================================================ reading
    @api.model
    def read(self, form, company=None, period_start=None, period_end=None,
             scheme_ids=None, currency_id=None):
        """The binding contract — see the module docstring."""
        self.env['pb.gov.form.rights']._pb_require_officer()
        return self._pb_read(form, company, period_start, period_end,
                             scheme_ids=scheme_ids, currency_id=currency_id)

    @api.model
    def read_form(self, *args, **kwargs):
        """The same reading under a name that cannot be confused with the
        ORM's own `read` (callers may use either)."""
        return self.read(*args, **kwargs)

    @api.model
    def _pb_read(self, form, company, period_start, period_end,
                 scheme_ids=None, currency_id=None):
        form = self._pb_form(form)
        company = self._pb_company_rec(company)
        start = fields.Date.to_date(period_start)
        end = fields.Date.to_date(period_end)
        if not start or not end or end < start:
            raise UserError(_("Pick the period first."))
        out = {
            'form': form.code, 'company_id': company.id,
            'period_start': fields.Date.to_string(start),
            'period_end': fields.Date.to_string(end),
            'lines': OrderedDict(), 'employees': [], 'payslip_ids': [],
            'warnings': [], 'currency': '', 'currency_id': False,
            'currencies': [], 'schemes': [], 'tax_years': {},
            'unfinished_count': 0,
        }
        Map = self.env['pb.gov.form.map'].sudo()
        maps = Map.search([('form_id', '=', form.id), ('company_id', '=', company.id)])
        if scheme_ids:
            wanted = set(int(s) for s in scheme_ids)
            maps = maps.filtered(lambda m: m.config_id.id in wanted)
        configs = maps.mapped('config_id')
        if not configs:
            self._pb_warn(out, 'nothing_mapped', _(
                "No pay item is on any line of this form yet. Open Form lines and say which pay items go where."),
                level='block')
            return out

        # ---- currencies (never two)
        by_currency = defaultdict(lambda: self.env['hr.formula.config'].sudo())
        for config in configs:
            by_currency[self._pb_currency_of(config)] |= config
        out['currencies'] = sorted(c.name for c in by_currency)
        if currency_id:
            currency = self.env['res.currency'].browse(int(currency_id))
            if currency not in by_currency:
                self._pb_warn(out, 'currency_not_used', _(
                    "None of the pay schemes on this form pays in %s.", currency.name), level='block')
                return out
        elif len(by_currency) > 1:
            self._pb_warn(out, 'two_currencies', _(
                "The pay schemes on this form pay in %s. Two currencies are never added together: choose one currency and make one filing for each.",
                ', '.join(out['currencies'])), level='block')
            return out
        else:
            currency = next(iter(by_currency))
        configs = by_currency[currency]
        maps = maps.filtered(lambda m: m.config_id in configs)
        out['currency'] = currency.name
        out['currency_id'] = currency.id
        out['schemes'] = [{'id': c.id, 'name': c.name or ''} for c in configs]

        # ---- tax years per scheme
        for config in configs:
            key = TY.tax_year_key(config, start)
            first, last = TY.tax_year_bounds_for_key(config, key)
            out['tax_years'][config.id] = {
                'key': key, 'label': TY.tax_year_label_for_key(config, key),
                'start': fields.Date.to_string(first), 'end': fields.Date.to_string(last)}
            if end > last:
                self._pb_warn(out, 'crosses_tax_year', _(
                    "This period crosses the start of the tax year of “%s”. Make one filing for each tax year.",
                    config.name or ''))

        # ---- the payslips
        Slip = self.env['hr.payslip'].sudo()
        Slip.flush_model(['state', 'date_to', 'company_id', 'formula_config_id',
                          'employee_id', 'formula_computed_values',
                          'formula_input_values'])
        slips = Slip.search([
            ('company_id', '=', company.id), ('formula_config_id', 'in', configs.ids),
            ('state', 'in', list(DONE_STATES)),
            ('date_to', '>=', start), ('date_to', '<=', end)], order='employee_id, id')
        out['unfinished_count'] = Slip.search_count([
            ('company_id', '=', company.id), ('formula_config_id', 'in', configs.ids),
            ('state', 'in', list(UNFINISHED_STATES)),
            ('date_to', '>=', start), ('date_to', '<=', end)])
        if out['unfinished_count']:
            self._pb_warn(out, 'unfinished', _(
                "%s payslips in this period are not finished yet and are left out.",
                out['unfinished_count']), level='info')
        # schemes of the same country with finished payslips and nothing mapped
        others = self.env['hr.formula.config'].sudo().with_context(active_test=False).search([
            ('company_id', '=', company.id), ('id', 'not in', configs.ids)]).filtered(
            lambda c: (c.country_code or '').upper() == (form.country_code or '').upper()
            and self._pb_currency_of(c) == currency)
        if others and not scheme_ids:
            loose = Slip.search_count([
                ('company_id', '=', company.id), ('formula_config_id', 'in', others.ids),
                ('state', 'in', list(DONE_STATES)),
                ('date_to', '>=', start), ('date_to', '<=', end)])
            if loose:
                self._pb_warn(out, 'scheme_not_mapped', _(
                    "%(n)s finished payslips of %(schemes)s are not counted: none of that scheme's pay items is on this form.",
                    n=loose, schemes=', '.join(others.mapped('name'))))
        if not slips:
            self._pb_warn(out, 'no_payslips', _(
                "There are no finished payslips in this period."), level='block')
            self._pb_compute(form, out, {}, {}, currency)
            return out
        out['payslip_ids'] = slips.ids

        # ---- raw item amounts per (employee, line)
        per_emp = defaultdict(lambda: defaultdict(float))
        texts = defaultdict(dict)
        slips_of = defaultdict(list)
        schemes_of = defaultdict(set)
        # WDGAP S2-B: the first and last day each person was paid for in the
        # period, and the pay months (year-end slips need a leaver's months)
        span_of = {}
        months_of = defaultdict(set)
        for slip in slips:
            emp_id = slip.employee_id.id
            slips_of[emp_id].append(slip.id)
            schemes_of[emp_id].add(slip.formula_config_id.id)
            first, last = span_of.get(emp_id, (slip.date_from, slip.date_to))
            span_of[emp_id] = (min(first, slip.date_from or first),
                               max(last, slip.date_to or last))
            months_of[emp_id].add('%04d-%02d' % (slip.date_to.year, slip.date_to.month))
        line_maps = maps.filtered(lambda m: m.source == 'payslip_line')
        value_maps = maps - line_maps
        self._pb_read_lines(slips, line_maps, per_emp)
        self._pb_read_values(slips, value_maps, per_emp, texts)

        # ---- per person
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        residency = {}
        missing_by_label = defaultdict(list)
        people = {}
        for emp in Emp.browse(sorted(slips_of)):
            ident = self._pb_identity(form, emp)
            residency[emp.id] = bool(ident.get('resident', True))
            for label in ident.get('missing') or []:
                missing_by_label[label].append(emp.id)
            people[emp.id] = {
                'employee_id': emp.id, 'name': emp.name or '',
                'identity': ident.get('values') or {},
                'resident': residency[emp.id],
                'payslip_ids': slips_of[emp.id],
                'scheme_ids': sorted(schemes_of[emp.id]),
                'lines': {}, 'checks': [],
                'date_from': fields.Date.to_string(span_of[emp.id][0]),
                'date_to': fields.Date.to_string(span_of[emp.id][1]),
                'months': sorted(months_of[emp.id]),
            }
        for label, emp_ids in missing_by_label.items():
            if len(emp_ids) == 1:
                text = _("1 person has no %s on their employee record.", label)
            else:
                text = _("%(n)s people have no %(what)s on their employee record.",
                         n=len(emp_ids), what=label)
            self._pb_warn(out, 'identity_missing', text, employee_ids=emp_ids)
            for emp_id in emp_ids:
                people[emp_id]['checks'].append(_("No %s on the employee record", label))
        self._pb_compute(form, out, people, {'amounts': per_emp, 'texts': texts}, currency)
        # required lines with nothing mapped in a scheme that is in the filing
        for line in form._pb_ordered_lines():
            if not line.required or line.base_line_id:
                continue
            mapped_schemes = set(maps.filtered(lambda m, l=line: m.line_id == l).mapped('config_id').ids)
            bare = configs.filtered(lambda c: c.id not in mapped_schemes)
            if bare:
                self._pb_warn(out, 'line_not_mapped', _(
                    "Line %(code)s “%(label)s” has no pay item from %(schemes)s.",
                    code=line.code, label=line.label, schemes=', '.join(bare.mapped('name'))))
        # WDGAP S2-B: a form's own points to check (`_pb_checks_<code>`),
        # e.g. Vietnam's dependants "to check" rows — they warn, never block
        hook = getattr(self, '_pb_checks_%s' % (form.code or '').lower(), None)
        if hook is not None:
            hook(form, company, out)
        return out

    # ------------------------------------------------------------ the SQL
    @api.model
    def _pb_read_lines(self, slips, maps, per_emp):
        """Payslip lines of the mapped items, by (scheme, code)."""
        if not maps:
            return
        by_key = defaultdict(list)
        for row in maps:
            by_key[(row.config_id.id, row.code)].append(row)
        codes = sorted({row.code for row in maps if row.code})
        Line = self.env['hr.payslip.line']
        has_backpay = 'pb_backpay' in Line._fields and 'pb_backpay_band_amount' in Line._fields \
            and Line._fields['pb_backpay'].store
        fields_to_flush = ['slip_id', 'code', 'total', 'pay_role', 'category_id']
        if has_backpay:
            fields_to_flush += ['pb_backpay', 'pb_backpay_band_amount']
        Line.flush_model(fields_to_flush)
        extra = ', l.pb_backpay, l.pb_backpay_band_amount' if has_backpay else ', NULL, NULL'
        self.env.cr.execute("""
            SELECT s.id, s.employee_id, s.formula_config_id, l.code,
                   COALESCE(l.total, 0), l.pay_role, c.code %s
              FROM hr_payslip_line l
              JOIN hr_payslip s ON s.id = l.slip_id
         LEFT JOIN hr_salary_rule_category c ON c.id = l.category_id
             WHERE s.id IN %%s AND l.code IN %%s
        """ % extra, (tuple(slips.ids), tuple(codes)))
        for _slip, emp_id, config_id, code, total, role, category, backpay, band in self.env.cr.fetchall():
            rows = by_key.get((config_id, code))
            if not rows:
                continue
            by_size = role in SIZE_ROLES or (
                not role and (category or '').upper() in DEDUCTION_CATEGORIES)
            if by_size:
                amount = (band or 0.0) if backpay else abs(total or 0.0)
            else:
                amount = total or 0.0
            for row in rows:
                per_emp[emp_id][row.line_id.id] += amount * row._pb_factor()

    @api.model
    def _pb_read_values(self, slips, maps, per_emp, texts):
        """The scheme's own worked-out values (then its input values) for
        items that are not printed on the payslip."""
        if not maps:
            return
        by_config = defaultdict(list)
        for row in maps:
            by_config[row.config_id.id].append(row)
        for slip in slips:
            rows = by_config.get(slip.formula_config_id.id)
            if not rows:
                continue
            values = {}
            for blob in (slip.formula_input_values, slip.formula_computed_values):
                try:
                    data = json.loads(blob or '{}')
                except (TypeError, ValueError):
                    data = {}
                if isinstance(data, dict):
                    values.update(data)
            emp_id = slip.employee_id.id
            for row in rows:
                if row.code not in values:
                    continue
                raw = values.get(row.code)
                if row.line_id.kind == 'text':
                    if raw not in (None, False, ''):
                        texts[emp_id][row.line_id.id] = str(raw).strip()
                    continue
                number = _num(raw)
                if number is None:
                    continue
                rule = row.rule_id
                if (rule.net_role or '') in SIZE_ROLES:
                    number = abs(number)
                per_emp[emp_id][row.line_id.id] += number * row._pb_factor()

    # ------------------------------------------------------------ the lines
    @api.model
    def _pb_round(self, line, currency, value):
        if line.kind == 'count':
            return int(round(value or 0))
        if line.round_digits is not None and line.round_digits >= 0:
            return round(value or 0.0, line.round_digits)
        return currency.round(value or 0.0)

    @api.model
    def _pb_compute(self, form, out, people, raw, currency):
        """Every line, in order: per person first, then the totals."""
        amounts = raw.get('amounts') or {}
        texts = raw.get('texts') or {}
        ordered = form._pb_ordered_lines()
        lines = self._pb_dependency_order(ordered)
        mapped_line_ids = set()
        for emp_amounts in amounts.values():
            mapped_line_ids |= set(emp_amounts)
        mapped_line_ids |= {lid for t in texts.values() for lid in t}
        totals = OrderedDict()
        by_code = {}

        def pop_ok(line, emp):
            if line.population == 'all':
                return True
            return emp['resident'] == (line.population == 'resident')

        for line in lines:
            by_code[line.code] = line
            total = 0.0
            if line.kind == 'text':
                for emp_id, emp in people.items():
                    value = texts.get(emp_id, {}).get(line.id, '')
                    emp['lines'][line.code] = value
                continue
            if line.kind == 'count':
                n = 0
                for emp in people.values():
                    if not pop_ok(line, emp):
                        continue
                    gate = line.only_if_line_id
                    if gate and not (emp['lines'].get(gate.code) or 0):
                        continue
                    n += 1
                totals[line.code] = n
                continue
            computed = line.kind == 'computed' and line.id not in mapped_line_ids
            for emp_id, emp in people.items():
                if line.base_line_id:
                    value = emp['lines'].get(line.base_line_id.code) or 0.0
                    if not pop_ok(line, emp):
                        value = 0.0
                elif computed:
                    value = self._pb_compute_op(line, emp['lines'])
                    if not pop_ok(line, emp):
                        value = 0.0
                else:
                    value = amounts.get(emp_id, {}).get(line.id, 0.0) if pop_ok(line, emp) else 0.0
                gate = line.only_if_line_id
                if gate and not (emp['lines'].get(gate.code) or 0):
                    value = 0.0
                if line.sign_rule == 'never_negative' and value < 0:
                    emp['checks'].append(_("Line %s was below zero and is shown as zero", line.code))
                    value = 0.0
                elif line.sign_rule == 'positive_part' and value < 0:
                    value = 0.0
                value = self._pb_round(line, currency, value)
                if line.scope == 'employee':
                    emp['lines'][line.code] = value
                total += value
            if computed and line.compute_op in ('ratio', 'percent') or (computed and not people):
                # a ratio or a percentage of the totals, not a sum of people's
                total = self._pb_compute_op(line, totals)
            totals[line.code] = self._pb_round(line, currency, total)
        out['lines'] = OrderedDict((l.code, totals[l.code]) for l in ordered if l.code in totals)
        for emp in people.values():
            emp['lines'] = OrderedDict((l.code, emp['lines'][l.code])
                                       for l in ordered if l.code in emp['lines'])
        out['employees'] = sorted(people.values(), key=lambda e: (e['name'].lower(), e['employee_id']))

    @api.model
    def _pb_dependency_order(self, lines):
        """Lines in an order where every line comes after the lines it reads
        (its base line, its "only if" line, its operands); otherwise the
        form's own order. A loop in the data falls back to the form order."""
        by_code = {l.code: l for l in lines}
        done, seen, out = set(), set(), []

        def deps(line):
            codes = [c.lstrip('-') for c in line._pb_operands()] if line.kind == 'computed' else []
            for rel in (line.base_line_id, line.only_if_line_id):
                if rel:
                    codes.append(rel.code)
            return [by_code[c] for c in codes if c in by_code and c != line.code]

        def visit(line):
            if line.id in done:
                return
            if line.id in seen:
                return          # a loop: leave the rest to the form order
            seen.add(line.id)
            for dep in deps(line):
                visit(dep)
            done.add(line.id)
            out.append(line)

        for line in lines:
            visit(line)
        return out

    @api.model
    def _pb_compute_op(self, line, values):
        ops = line._pb_operands()
        if line.compute_op == 'sum':
            # "-2i" takes line 2i away (WDGAP S2-B)
            total = 0.0
            for code in ops:
                if code.startswith('-'):
                    total -= values.get(code[1:]) or 0.0
                else:
                    total += values.get(code) or 0.0
            return total * (line.factor or 1.0)
        nums = [values.get(c) or 0.0 for c in ops]
        if line.compute_op == 'ratio':
            if len(nums) < 2 or not nums[1]:
                return 0.0
            return nums[0] / nums[1] * (line.factor or 1.0)
        if line.compute_op == 'percent':
            return (nums[0] if nums else 0.0) * (line.factor or 0.0)
        return 0.0
