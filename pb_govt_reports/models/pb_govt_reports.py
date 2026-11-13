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
    'SG': {'wizard_model': 'cpf.submission.wizard', 'groups': [
        {'label': 'Social Security', 'icon': 'checkCircle', 'reports': [
            {'key': 'cpf', 'en': 'CPF Submission', 'vi': 'CPF Submission'}]}]},
    'TH': {'wizard_model': 'social.security.wizard', 'groups': [
        {'label': 'Social Security', 'icon': 'checkCircle', 'reports': [
            {'key': 'ssf', 'en': 'SSF Submission', 'vi': 'SSF Submission'}]}]},
    'KH': {'wizard_model': 'nssf.wizard', 'groups': [
        {'label': 'Social Security', 'icon': 'checkCircle', 'reports': [
            {'key': 'nssf', 'en': 'NSSF Submission', 'vi': 'NSSF Submission'}]}]},
    'MY': {'wizard_model': 'epf.wizard', 'groups': [
        {'label': 'Social Security', 'icon': 'checkCircle', 'reports': [
            {'key': 'epf', 'en': 'EPF / SOCSO / EIS', 'vi': 'EPF / SOCSO / EIS'}]}]},
}


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
            cfgs = self.env['hr.formula.config'].with_context(active_test=False).search(
                [('company_id', '=', company.id)])
            present |= {(c.country_code or '').upper() for c in cfgs if c.country_code}
        except Exception:
            pass
        present.discard('')

        sel = (country_code or home_cc or 'VN').upper()
        cat = _CATALOG.get(sel, {})
        wizard_model = cat.get('wizard_model')
        available = bool(wizard_model) and wizard_model in self.env
        return {
            'company': company.name,
            'country_code': sel,
            'country_label': _COUNTRY_NAMES.get(sel, sel),
            'wizard_model': wizard_model or '',
            'available': available,
            'groups': cat.get('groups', []) if available else [],
            'period': self._default_period(company),
            'countries': sorted(
                ({'code': c, 'label': _COUNTRY_NAMES.get(c, c)} for c in present),
                key=lambda x: x['code']),
            'multi_country': len(present) > 1,
        }
