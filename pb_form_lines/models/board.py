# -*- coding: utf-8 -*-
"""The screens' one server door: Form lines and the filing flow.

Every public method starts with the payroll officer check
(`pb.gov.form.rights._pb_require_officer`); reads then run under sudo,
limited to the switcher's current company. Nothing here is reachable by a
person without the payroll officer or manager right — not the screen, not the
RPC, not the download address (`controllers/download.py`).
"""
import logging
import re
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, format_datetime

from odoo.addons.pb_hr_payroll_formula.models import tax_year as TY

from .reader import month_bounds

_logger = logging.getLogger(__name__)


class PbGovFormBoard(models.AbstractModel):
    _name = 'pb.gov.form.board'
    _description = 'Government forms: screens'

    # ------------------------------------------------------------- helpers
    @api.model
    def _door(self):
        self.env['pb.gov.form.rights']._pb_require_officer()
        return self.env.company

    @api.model
    def _form(self, form_id):
        form = self.env['pb.gov.form'].sudo().browse(int(form_id or 0)).exists()
        if not form or not form.active:
            raise UserError(_("That government form is not available here."))
        return form

    @api.model
    def _role_label(self, role):
        mapping = {
            'earning': _('Adds to pay'), 'deduction': _('Taken off pay'),
            'net': _('Take-home pay'), 'employer_cost': _('Employer cost'),
            'info': _('Information only'), 'mixed': _('Both added and taken off'),
        }
        return mapping.get(role or '', '')

    @api.model
    def _country_label(self, code):
        mapping = {'VN': _('Vietnam'), 'ID': _('Indonesia'), 'IN': _('India'),
                   'SG': _('Singapore'), 'MY': _('Malaysia'), 'TH': _('Thailand'),
                   'KH': _('Cambodia'), 'PH': _('Philippines')}
        return mapping.get(code, code)

    @api.model
    def _when(self, value):
        return format_datetime(self.env, value, dt_format='d MMM y, HH:mm') if value else ''

    @api.model
    def _countries(self, company):
        present = set()
        if company.country_id.code:
            present.add(company.country_id.code.upper())
        configs = self.env['hr.formula.config'].sudo().with_context(active_test=False).search(
            [('company_id', '=', company.id)])
        present |= {(c.country_code or '').upper() for c in configs if c.country_code}
        present.discard('')
        return present

    @api.model
    def _schemes(self, company, form):
        configs = self.env['hr.formula.config'].sudo().with_context(active_test=False).search(
            [('company_id', '=', company.id)], order='name, id')
        configs = configs.filtered(
            lambda c: (c.country_code or '').upper() == (form.country_code or '').upper())
        Reader = self.env['pb.gov.form.reader']
        return [{'id': c.id, 'name': c.name or '', 'active': c.state == 'active',
                 'currency': Reader._pb_currency_of(c).name or ''} for c in configs]

    @api.model
    def _rule_row(self, rule):
        Map = self.env['pb.gov.form.map']
        return {
            'rule_id': rule.id, 'label': rule.name or rule.code, 'code': rule.code or '',
            'scheme': rule.config_id.name or '', 'role': rule.net_role or '',
            'role_label': self._role_label(rule.net_role),
            'source': Map._pb_default_source(rule),
            'printed': Map._pb_default_source(rule) == 'payslip_line',
        }

    # ============================================================ the forms
    @api.model
    def get_forms(self, country_code=None):
        """The forms of the company's countries, with how far each is set up."""
        company = self._door()
        countries = self._countries(company)
        Form = self.env['pb.gov.form'].sudo()
        forms = Form.search([('country_code', 'in', sorted(countries))]) if countries else Form
        selected = (country_code or '').upper()
        rows = []
        for form in forms:
            rows.append(self._form_card(form, company))
        return {
            'company': company.name,
            'countries': [{'code': c, 'label': self._country_label(c)}
                          for c in sorted(countries)],
            'selected': selected,
            'forms': [r for r in rows if not selected or r['country_code'] == selected],
            'can_edit': True,
            'is_manager': self.env['pb.gov.form.rights']._pb_is_manager(),
        }

    @api.model
    def _form_card(self, form, company):
        Map = self.env['pb.gov.form.map'].sudo()
        maps = Map.search([('form_id', '=', form.id), ('company_id', '=', company.id)])
        mapped = set(maps.mapped('line_id').ids)
        mappable = form.line_ids.filtered(lambda l: l.mappable and not l.base_line_id)
        required = form.line_ids.filtered(lambda l: l.required)
        settings = self.env['pb.gov.form.company'].sudo().search(
            [('company_id', '=', company.id), ('form_id', '=', form.id)], limit=1)
        latest = self.env['pb.gov.filing'].sudo().search(
            [('form_id', '=', form.id), ('company_id', '=', company.id),
             ('state', '!=', 'superseded')], order='id desc', limit=1)
        valid = ''
        if form.valid_from and form.valid_to:
            valid = _("For periods %(a)s to %(b)s", a=form.valid_from, b=form.valid_to)
        elif form.valid_from:
            valid = _("For periods from %s", fields.Date.to_string(form.valid_from))
        elif form.valid_to:
            valid = _("For periods up to %s", fields.Date.to_string(form.valid_to))
        return {
            'id': form.id, 'code': form.code, 'name': form.name,
            'official_name': form.official_name or '', 'country_code': form.country_code,
            'country_label': self._country_label(form.country_code),
            'authority': form.authority or '',
            'period_kind': form.period_kind, 'quarter_allowed': form.quarter_allowed,
            'inferred': form.inferred, 'inferred_note': form.inferred_note or '',
            'source_note': form.source_note or '', 'source_url': form.source_url or '',
            'valid': valid,
            'lines_mappable': len(mappable), 'lines_mapped': len(mapped & set(mappable.ids)),
            'required_missing': [l.code for l in required if l.id not in mapped],
            'items': len(maps),
            'accepted': bool(settings.accepted),
            'accepted_by': settings.accepted_by.name or '',
            'accepted_on': self._when(settings.accepted_on),
            'latest_state': latest.state or '',
            'latest_state_label': latest._state_label() if latest else '',
            'latest_period': latest.period_label or '',
            # WDGAP S2-B
            'tile_group': form.tile_group or 'tax_return',
            'screen_note': form.screen_note or '',
            'employee_certificates': bool(form.employee_certificates),
            'year_start_month': form.year_start_month or 1,
        }

    @api.model
    def get_form(self, form_id):
        """One form's lines, each with its pay items, the loose items and the
        company's settings for it."""
        company = self._door()
        form = self._form(form_id)
        Map = self.env['pb.gov.form.map'].sudo()
        maps = Map.search([('form_id', '=', form.id), ('company_id', '=', company.id)])
        lines = []
        for line in form._pb_ordered_lines():
            mine = maps.filtered(lambda m, l=line: m.line_id == l)
            items = []
            for m in mine:
                row = self._rule_row(m.rule_id)
                row.update({'map_id': m.id, 'source': m.source, 'sign': m.sign,
                            'share_pct': m.share_pct,
                            'warning': Map._pb_item_warning(m.rule_id, m.source)})
                items.append(row)
            how = ''
            if line.base_line_id:
                how = _("Worked out from line %s", line.base_line_id.code)
            elif line.kind == 'count':
                how = _("Counted from the people in the filing")
            elif line.kind == 'computed':
                how = _("Worked out from lines %s unless a pay item is put here",
                        ', '.join(line._pb_operands()))
            lines.append({
                'id': line.id, 'code': line.code, 'label': line.label,
                'official_label': line.official_label or '', 'kind': line.kind,
                'kind_label': line._pb_kind_label(),
                'mappable': bool(line.mappable and not line.base_line_id),
                'required': line.required, 'note': line.note or '', 'how': how,
                'population': line.population,
                'inferred': line.inferred, 'items': items,
            })
        used = set(maps.mapped('rule_id').ids)
        tray = []
        for rule in Map._pb_candidate_rules(company, form):
            if rule.id in used or rule.net_role_detail:
                continue
            if (rule.net_role or '') not in ('earning', 'deduction', 'employer_cost', 'info'):
                continue
            if (rule.value_kind or 'money') not in ('money', 'decimal', 'integer'):
                continue
            tray.append(self._rule_row(rule))
            if len(tray) >= 200:
                break
        settings = self.env['pb.gov.form.company'].sudo().search(
            [('company_id', '=', company.id), ('form_id', '=', form.id)], limit=1)
        card = self._form_card(form, company)
        card.update({
            'lines': lines, 'tray': tray, 'schemes': self._schemes(company, form),
            'settings': {'employer_tax_id': settings.employer_tax_id or '',
                         'place_of_business': settings.place_of_business or ''},
            'needs_place': form.country_code == 'ID',
            'is_manager': self.env['pb.gov.form.rights']._pb_is_manager(),
        })
        return card

    @api.model
    def item_options(self, form_id, term=''):
        company = self._door()
        form = self._form(form_id)
        rules = self.env['pb.gov.form.map']._pb_candidate_rules(company, form)
        term = (term or '').strip().lower()
        if term:
            rules = rules.filtered(lambda r: term in (r.name or '').lower()
                                   or term in (r.code or '').lower())
        return [self._rule_row(r) for r in rules[:40]]

    @api.model
    def save_line(self, form_id, line_id, items):
        """Replace this company's pay items on one line."""
        company = self._door()
        form = self._form(form_id)
        line = form.line_ids.filtered(lambda l: l.id == int(line_id or 0))
        if not line:
            raise UserError(_("That line belongs to another form."))
        if not line.mappable or line.base_line_id:
            raise UserError(_("“%s” is worked out from other lines, so no pay item can be put on it.", line.label))
        Map = self.env['pb.gov.form.map'].sudo()
        clean = Map._pb_clean(form, company, [dict(r, line_id=line.id) for r in (items or [])])
        existing = Map.search([('line_id', '=', line.id), ('company_id', '=', company.id)])
        keep = {}
        for row in clean:
            keep[row['rule_id']] = row
        for m in existing:
            if m.rule_id.id in keep:
                row = keep.pop(m.rule_id.id)
                m.write({'source': row['source'], 'sign': row['sign'],
                         'share_pct': row['share_pct']})
            else:
                m.unlink()
        for row in keep.values():
            Map.create(row)
        return self.get_form(form.id)

    @api.model
    def suggest(self, form_id):
        company = self._door()
        form = self._form(form_id)
        return self.env['pb.gov.form.map']._pb_suggest(form, company)

    @api.model
    def accept_suggestions(self, form_id, rows):
        company = self._door()
        form = self._form(form_id)
        Map = self.env['pb.gov.form.map'].sudo()
        made = 0
        for row in Map._pb_clean(form, company, [r for r in (rows or []) if r.get('on')]):
            if Map.search_count([('line_id', '=', row['line_id']), ('rule_id', '=', row['rule_id'])]):
                continue
            line = self.env['pb.gov.form.line'].sudo().browse(row['line_id'])
            if not line.mappable or line.base_line_id:
                continue
            Map.create(row)
            made += 1
        return {'made': made, 'form': self.get_form(form.id)}

    @api.model
    def save_settings(self, form_id, vals):
        company = self._door()
        form = self._form(form_id)
        row = self.env['pb.gov.form.company']._pb_for(form, company)
        clean = {}
        for key in ('employer_tax_id', 'place_of_business'):
            if key in (vals or {}):
                clean[key] = re.sub(r'\s+', '', str(vals.get(key) or ''))[:40]
        if clean:
            row.write(clean)
        return self.get_form(form.id)

    @api.model
    def set_accepted(self, form_id, value):
        company = self._door()
        form = self._form(form_id)
        row = self.env['pb.gov.form.company']._pb_for(form, company)
        row.with_env(self.env)._pb_set_accepted(value)
        return self._form_card(form, company)

    # ========================================================= the filing flow
    @api.model
    def _bounds(self, form, key):
        """'2026-03' (a month), '2026-Q3' (a quarter) or '2026' (a tax year).
        Quarters and tax years follow the authority's tax year
        (`form.year_start_month`): for India '2026-Q1' is April - June 2026
        and '2026' is April 2026 - March 2027 (WDGAP S2-B)."""
        key = (key or '').strip().upper()
        start_month = TY.month_of(form.year_start_month or 1)
        m = re.fullmatch(r'(\d{4})-(\d{2})', key)
        if m:
            start, end = month_bounds(date(int(m.group(1)), int(m.group(2)), 1))
            if form.period_kind == 'quarter':
                raise UserError(_("This form is filed per quarter: pick a quarter."))
            if form.period_kind == 'tax_year':
                raise UserError(_("This form is filed per tax year: pick a year."))
            return start, end
        m = re.fullmatch(r'(\d{4})-Q([1-4])', key)
        if m:
            if form.period_kind == 'month' and not form.quarter_allowed:
                raise UserError(_("This form is filed per month: pick a month."))
            if form.period_kind == 'tax_year':
                raise UserError(_("This form is filed per tax year: pick a year."))
            first_of_year, _last = TY.tax_year_bounds_for_key(start_month, int(m.group(1)))
            first = TY._add_months(first_of_year, (int(m.group(2)) - 1) * 3)
            return TY.tax_quarter_bounds(start_month, first)
        m = re.fullmatch(r'(\d{4})', key)
        if m:
            if form.period_kind != 'tax_year':
                raise UserError(_("Pick the period first."))
            return TY.tax_year_bounds_for_key(start_month, int(m.group(1)))
        raise UserError(_("Pick the period first."))

    @api.model
    def _period_choices(self, form, ref):
        """The years (tax-year forms) and the quarter names (quarterly
        forms) the period step offers, in the authority's tax year."""
        start_month = TY.month_of(form.year_start_month or 1)
        key = TY.tax_year_key(start_month, ref)
        years = [{'key': str(k), 'label': TY.tax_year_label_for_key(start_month, k)}
                 for k in range(key - 3, key + 2)]
        quarters = []
        for q in range(4):
            first, _l = TY.tax_year_bounds_for_key(start_month, 2001)
            a = TY._add_months(first, q * 3)
            b = TY._add_months(first, q * 3 + 2)
            quarters.append(format_date(self.env, a, date_format='MMMM') + ' – '
                            + format_date(self.env, b, date_format='MMMM'))
        return years, quarters

    @api.model
    def flow_start(self, form_id):
        company = self._door()
        if not form_id:
            # a reload or a deep link carries no form: the company's first one
            countries = sorted(self._countries(company))
            first = self.env['pb.gov.form'].sudo().search(
                [('country_code', 'in', countries)], limit=1) if countries else None
            if not first:
                raise UserError(_("That government form is not available here."))
            form_id = first.id
        form = self._form(form_id)
        card = self._form_card(form, company)
        self.env.cr.execute("""
            SELECT max(date_to) FROM hr_payslip
             WHERE company_id = %s AND state IN ('done', 'paid')""", (company.id,))
        ref = (self.env.cr.fetchone() or [None])[0] or fields.Date.context_today(self)
        if form.valid_to and ref > form.valid_to:
            ref = form.valid_to
        if form.valid_from and ref < form.valid_from:
            ref = form.valid_from
        start_month = TY.month_of(form.year_start_month or 1)
        if form.period_kind == 'quarter':
            first, _last = TY.tax_quarter_bounds(start_month, ref)
            year_first, _y = TY.tax_year_bounds(start_month, ref)
            n = ((first.year * 12 + first.month) - (year_first.year * 12 + year_first.month)) // 3 + 1
            default = '%d-Q%d' % (year_first.year, n)
        elif form.period_kind == 'tax_year':
            default = str(TY.tax_year_key(start_month, ref))
        else:
            default = '%d-%02d' % (ref.year, ref.month)
        years, quarters = self._period_choices(form, ref)
        history = []
        for f in self.env['pb.gov.filing'].sudo().search(
                [('form_id', '=', form.id), ('company_id', '=', company.id)],
                order='id desc', limit=12):
            history.append(self._filing_row(f))
        card.update({'default_period': default, 'schemes': self._schemes(company, form),
                     'history': history, 'year_options': years, 'quarter_labels': quarters})
        return card

    @api.model
    def flow_check(self, form_id, period, scheme_ids=None, currency_id=None):
        company = self._door()
        form = self._form(form_id)
        start, end = self._bounds(form, period)
        if not form._pb_valid_for(start) or not form._pb_valid_for(end):
            return {'period_start': fields.Date.to_string(start),
                    'period_end': fields.Date.to_string(end),
                    'lines': [], 'people': 0, 'warnings': [{
                        'code': 'layout_period', 'level': 'block',
                        'message': _("This layout is not the one for that period. Pick the other version of the form.")}],
                    'currencies': [], 'currency': '', 'people_checks': []}
        data = self.env['pb.gov.form.reader']._pb_read(
            form, company, start, end, scheme_ids=scheme_ids or None,
            currency_id=currency_id or None)
        lines = []
        for line in form._pb_ordered_lines():
            if line.code not in data['lines']:
                continue
            lines.append({'code': line.code, 'label': line.label, 'kind': line.kind,
                          'official_label': line.official_label or '',
                          'value': data['lines'][line.code]})
        checks = [{'name': e['name'], 'checks': e['checks']}
                  for e in data['employees'] if e.get('checks')][:60]
        return {
            'period_start': data['period_start'], 'period_end': data['period_end'],
            'period_label': self.env['pb.gov.filing']._pb_period_label(form, start, end),
            'lines': lines, 'people': len(data['employees']),
            'payslips': len(data['payslip_ids']), 'warnings': data['warnings'],
            'currencies': data['currencies'], 'currency': data['currency'],
            'currency_id': data['currency_id'],
            'people_checks': checks,
            'blocked': any(w.get('level') == 'block' for w in data['warnings']),
        }

    @api.model
    def flow_prepare(self, form_id, period, scheme_ids=None, currency_id=None):
        """Prepare the files and send them in for approval (a click)."""
        company = self._door()
        form = self._form(form_id)
        start, end = self._bounds(form, period)
        filing = self.env['pb.gov.filing'].prepare(
            form, company, start, end, scheme_ids=scheme_ids or None,
            currency_id=currency_id or None)
        self.env['biz.approval.engine'].submit(filing)
        filing.invalidate_recordset()
        return self.get_filing(filing.id)

    @api.model
    def flow_submit(self, filing_id):
        self._door()
        filing = self._filing(filing_id)
        if filing.state not in ('draft', 'returned'):
            raise UserError(_("This filing is not waiting to be sent in."))
        if filing.state == 'returned':
            filing.sudo().write({'state': 'draft'})
        self.env['biz.approval.engine'].submit(filing)
        filing.invalidate_recordset()
        return self.get_filing(filing.id)

    @api.model
    def _filing(self, filing_id):
        company = self.env.company
        filing = self.env['pb.gov.filing'].browse(int(filing_id or 0)).exists()
        if not filing or filing.sudo().company_id != company:
            raise UserError(_("That filing is not available here."))
        return filing

    @api.model
    def download_check(self, filing_id, file_id):
        """The download's refusals as a plain sentence, before the browser
        asks for the bytes (nothing is logged here)."""
        self._door()
        rec = self._filing(filing_id).sudo()
        if rec.state == 'superseded':
            raise UserError(_("A newer filing has replaced this one. Download that one instead."))
        if rec.state != 'approved' or not rec.approved_hash:
            raise UserError(_("This filing has not been approved yet, so it cannot be downloaded."))
        if rec._live_hash() != rec.approved_hash:
            raise UserError(_("This is not the approved filing — what is stored no longer matches what was signed off. Prepare it again."))
        if not rec.file_ids.filtered(lambda x: x.id == int(file_id or 0)):
            raise UserError(_("That file is not part of this filing."))
        return True

    @api.model
    def _filing_row(self, f):
        f = f.sudo()
        return {'id': f.id, 'name': f.name, 'period': f.period_label or '',
                'state': f.state, 'state_label': f._state_label(),
                'people': f.row_count, 'prepared_by': f.generated_by.name or '',
                'prepared_on': self._when(f.generated_at),
                'adviser_mark': f.adviser_mark}

    @api.model
    def get_filing(self, filing_id):
        self._door()
        filing = self._filing(filing_id)
        rec = filing.sudo()
        waiting = ''
        request = rec.approval_request_id
        if request and rec.state == 'pending':
            step = request.step_ids.filtered(lambda s: s.key == request.current_step_key)[:1]
            waiting = ', '.join(sorted({s.acting_user_id.name or '' for s in step.seat_ids
                                        if s.status == 'open'} - {''}))
        totals = rec._pb_totals()
        lines = []
        for line in rec.form_id._pb_ordered_lines():
            if line.code in totals:
                lines.append({'code': line.code, 'label': line.label, 'kind': line.kind,
                              'value': totals[line.code]})
        row = self._filing_row(rec)
        row.update({
            'form_id': rec.form_id.id, 'currency': rec.currency_id.name or '',
            'files': [{'id': x.id, 'name': x.name, 'size': x.size} for x in rec.file_ids],
            'downloadable': rec.state == 'approved' and bool(rec.approved_hash),
            'waiting_for': waiting, 'request_id': request.id if request else False,
            'lines': lines, 'warnings': rec._pb_warnings(),
            'downloaded_by': rec.downloaded_by.name or '',
            'downloaded_on': self._when(rec.downloaded_at),
            'can_resend': rec.state in ('draft', 'returned'),
        })
        # WDGAP S2-B: the per-person certificates and their release
        certs = rec.certificate_ids if 'certificate_ids' in rec._fields else []
        is_manager = self.env['pb.gov.form.rights']._pb_is_manager()
        row.update({
            'certificates': len(certs),
            'released': bool(certs and rec.pb_released),
            'released_by': rec.pb_released_by.name or '' if certs else '',
            'released_on': self._when(rec.pb_released_at) if certs else '',
            'can_release': bool(certs) and is_manager and row['downloadable'],
            'is_manager': is_manager,
        })
        return row

    @api.model
    def set_released(self, filing_id, value):
        """"Release to employees" / "Take back" (payroll manager, approved
        filings only — the model says why not)."""
        self._door()
        filing = self._filing(filing_id)
        filing._pb_release(bool(value))
        filing.invalidate_recordset()
        return self.get_filing(filing.id)
