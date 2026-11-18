# -*- coding: utf-8 -*-
"""Government Reports cockpit data provider.

A thin, country-aware FRONT DOOR over the existing statutory report wizards — it
does NOT compute anything itself. The active company's country decides which
report set to show; each tile launches the existing wizard (VN: pb.govt.report.
wizard with a report_type; other countries: their own contribution wizard),
pre-filled with the company + the selected period. No engine change.
"""
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

_COUNTRY_NAMES = {
    'VN': 'Vietnam', 'SG': 'Singapore', 'TH': 'Thailand', 'KH': 'Cambodia',
    'MY': 'Malaysia', 'ID': 'Indonesia', 'IN': 'India', 'PH': 'Philippines',
}

# Country -> report catalog. VN uses pb.govt.report.wizard (report_type per tile);
# other countries open their own contribution wizard. Tiles are only shown when
# the backing wizard model is actually installed (else "coming soon").
_CATALOG = {
    'VN': {
        'wizard_model': 'pb.govt.report.wizard',
        'groups': [
            {'label': 'Social Insurance (BHXH)', 'icon': 'checkCircle', 'reports': [
                {'key': 'bhxh630', 'en': 'Sickness & Maternity', 'vi': 'BHXH630 · Ốm đau / Thai sản'},
                {'key': 'bhxhdstk01', 'en': 'Participant Schedule', 'vi': 'BHXHDSTK01-DV_595 · Mẫu 595'},
                {'key': 'bangke_d01', 'en': 'Dossier Cover Sheet', 'vi': 'Bảng kê hồ sơ D01-TS'},
            ]},
            {'label': 'Labour Changes', 'icon': 'users', 'reports': [
                {'key': 'tang_ld', 'en': 'Headcount Increase', 'vi': 'Báo tăng lao động'},
                {'key': 'giam_ld', 'en': 'Headcount Decrease', 'vi': 'Báo giảm lao động'},
            ]},
        ],
    },
    # WDGAP S2-A (S2F-4): the Singapore CPF, Thailand SSF, Cambodia NSSF and
    # Malaysia EPF tiles are RETIRED. Their wizards wrote no file and said
    # they had; a country's filings now come from the form catalogue
    # (pb_form_lines, `forms` below) once its forms are built.
}


def _forms_for(env, company, country):
    """The government forms of `country` (pb_form_lines, by probe — this
    module does not depend on it), as the board's tiles. Empty for a person
    without the payroll officer right: the same right that prepares them."""
    if 'pb.gov.form' not in env or 'pb.gov.form.board' not in env:
        return []
    Rights = env['pb.gov.form.rights']
    if not Rights._pb_is_officer():
        return []
    Board = env['pb.gov.form.board']
    forms = env['pb.gov.form'].sudo().search([('country_code', '=', country)])
    cards = [Board._form_card(form, company) for form in forms]
    # WDGAP S2-B2: a form that is no filing of its own (the pay items the
    # VN social-insurance reports read) gets no tile
    return [c for c in cards if c.get('section', 'tax') != 'reports']


#: WDGAP S2-B2 — the order of the tile groups; a section this list does not
#: name comes after these, in the order its forms come.
_SECTION_ORDER = ('tax', 'year_end', 'fund')
_SECTION_ICON = {'tax': 'landmark', 'year_end': 'calendarClock', 'fund': 'wallet'}


def _form_groups(forms):
    """The form tiles grouped by where they sit (`section` of each card,
    pb_form_lines): Tax returns, Fund files, … — each group with its label
    from the card."""
    groups = {}
    for card in forms:
        key = card.get('section') or 'tax'
        group = groups.setdefault(key, {'key': key, 'label': card.get('section_label') or '',
                                        'icon': _SECTION_ICON.get(key, 'fileCheck'),
                                        'forms': []})
        group['forms'].append(card)
    order = {key: i for i, key in enumerate(_SECTION_ORDER)}
    return sorted(groups.values(), key=lambda g: order.get(g['key'], len(order)))


class PbGovtReports(models.AbstractModel):
    _name = 'pb.govt.reports'
    _description = 'Payobook Government Reports cockpit data'

    def _default_period(self, company):
        """Default to the company's latest payslip month (else this month).
        hr.payslip.run has no company_id in this build, so scope via hr.payslip."""
        self.env.cr.execute(
            "SELECT max(date_to) FROM hr_payslip WHERE company_id = %s", (company.id,))
        ref = (self.env.cr.fetchone() or [None])[0] or fields.Date.context_today(self)
        first = ref.replace(day=1)
        last = first + relativedelta(months=1, days=-1)
        return {'from': fields.Date.to_string(first), 'to': fields.Date.to_string(last),
                'month': first.strftime('%Y-%m'), 'label': first.strftime('%B %Y')}

    @api.model
    def get_govt_reports_data(self, country_code=None):
        company = self.env.company
        home_cc = (company.country_id.code or '').upper()

        # countries actually present in this company (its formula configs) — drives
        # the country chip row for a multi-country group.
        present = set()
        if home_cc:
            present.add(home_cc)
        try:
            # sudo: only the country codes of this company's own schemes are read
            # (a payroll officer without formula rights saw no country — S2-B2)
            cfgs = self.env['hr.formula.config'].sudo().with_context(active_test=False).search(
                [('company_id', '=', company.id)])
            present |= {(c.country_code or '').upper() for c in cfgs if c.country_code}
        except Exception:
            pass
        present.discard('')

        # WDGAP S2-B2: a company with no country of its own opens on its pay
        # schemes' country (it used to open on Vietnam whatever it paid)
        sel = (country_code or home_cc or (sorted(present)[0] if present else 'VN')).upper()
        cat = _CATALOG.get(sel, {})
        wizard_model = cat.get('wizard_model')
        available = bool(wizard_model) and wizard_model in self.env
        forms = _forms_for(self.env, company, sel)
        return {
            'company': company.name,
            'country_code': sel,
            'country_label': _COUNTRY_NAMES.get(sel, sel),
            'wizard_model': wizard_model or '',
            'available': available or bool(forms),
            'wizards_available': available,
            # WDGAP S2-A: the tax returns of the form catalogue, as tiles
            # (S2-B2: still the tax returns only — the S2-A meaning)
            'forms': [c for c in forms if (c.get('section') or 'tax') == 'tax'],
            # WDGAP S2-B2: every form tile, grouped (Tax returns, Fund files)
            'form_groups': _form_groups(forms),
            'form_lines': 'pb.gov.form' in self.env,
            'groups': cat.get('groups', []) if available else [],
            'period': self._default_period(company),
            'countries': sorted(
                ({'code': c, 'label': _COUNTRY_NAMES.get(c, c)} for c in present),
                key=lambda x: x['code']),
            'multi_country': len(present) > 1,
        }
