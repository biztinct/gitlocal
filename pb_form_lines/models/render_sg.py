# -*- coding: utf-8 -*-
"""Singapore — Form IR8A for the Auto-Inclusion Scheme (AIS), WDGAP S2-B.

WHAT IRAS ACCEPTS TODAY. From Year of Assessment 2026 the employment-income
records go to IRAS only through AIS-API 2.0 (a JSON payload sent by payroll
software) or the myTax Portal "Submit Employment Income Records" service,
which imports IRAS's own "IR8A Import Template" workbook (up to 200 records
per workbook). The older fixed-length text and XML files are withdrawn (the
specification link answers 404). So this form makes:

  1. `IR8A_AIS_<company>_<year>.json` — the AIS-API 2.0 payload: header
     `orgAndSubmissionInfo` (items A1-A14) + `employeePersonalParticulars`
     (B1-B14, each with `ir8a` C1-C31 and empty `appendix8A` / `appendix8B`),
     every key present (IRAS: "every key must be present").
  2. `IR8A_import_<company>_<year>[_n].xlsx` — the import template's "IR8A"
     sheet: "version 1.0" in A1, the 44 column headings on row 5, people from
     row 6, the template's own drop-down words ("NRIC", "Male", ...), at most
     200 people per workbook.
  3. `IR8A_summary_<company>_<year>.xlsx` — totals, people, points to check.
  4. One IR8A per person (PDF, item letters of the YA 2027 form).

SOURCES (read 18 November 2026): IRAS "AIS-API 2.0" interface specification
v2.6 (11 Sep 2026, https://file.go.gov.sg/aisapi2-specs.pdf); "Data Items and
Validation Rules" v2.5 (30 Jan 2026, https://go.gov.sg/aisapi2-dataitems);
"IR8A Import Template" version 1.0 (https://go.gov.sg/ir8a-import-template);
Form IR8A YA 2027 and its explanatory notes.

RULES KEPT (data items sheet): IR8A amounts are whole dollars, at most 9
digits; income items are rounded DOWN, deductions UP ("drop off cents ... round
up to the full dollar"); C21 others income = C9 + C10 + C11 + C14 + C16 + C17 +
C18 + C20 (C12 compensation and C19 are not in it — as the data items sheet
lists it); C22 total = C3 + C4 + C6 + C21; header A11 = number of IR8A
records (1-2000), A12 = the sum of C22, A13/A14 = 0 (no appendices made).
Appendix 8A (benefits in kind, C20) and 8B (share gains, C18/C19) are out of
scope: the check step warns when such items are on the form.

INFERRED (on the form record and in the report): softwareCompanyName left
empty (the sender's APEX organisation name); the authorised person is the
person who prepared the filing; dates of commencement / cessation from the
employment contracts; address type "L" only for a Singapore address with a
6-digit postal code, otherwise left blank (allowed); bank code blank.
"""
import io
import json
import math

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import cert_pdf
from .render_vn import XLSX

INCOME = ('a', 'b', 'c', 'd1', 'd2', 'd3', 'd3b', 'd4', 'd5', 'd6', 'd7a', 'd7b', 'd8', 'e')
DEDUCTIONS = ('CPF', 'DON', 'MBF', 'LIFE')
OTHERS = ('d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7a', 'd8')
ID_TYPE_WORDS = {'1': 'NRIC', '2': 'FIN', '4': 'Work Permit No', '11': 'Malaysian IC', '12': 'Passport No'}
IMPORT_HEADS = [
    '*Record No.', '*ID Type [Choose option]', '*ID No.', '*Full Name of Employee as per NRIC/FIN',
    '*Sex [Choose option]', '*Date of Birth (YYYY-MM-DD)', 'Designation',
    'Residential Address [Choose option]', 'Address Details', 'Postal Code', 'Country/ Region [Choose option]',
    'Date of Commencement (YYYY-MM-DD)', 'Date of Cessation/posted overseas (YYYY-MM-DD)',
    'Bank salary is credited to [Choose option]', 'a) Gross Salary', 'b) Bonus', 'Date of bonus paid (YYYY-MM-DD)',
    "c) Director's fee", "Date of director's fee approved (YYYY-MM-DD)",
    'Total of items d1 to d8 (excluding 3b & 7b) <Amount is automatically computed after record import to digital service>',
    'd1) Allowances', 'd2) Gross Commission',
    'd4.1(i) Gratuity/ Notice Pay/ Ex-gratia payment/ Others indicator <Indicator is automatically prefilled when applicable after record import to digital service>',
    'd3(a) Gratuity/ Notice Pay/ Ex-gratia payment/ Others',
    ' Compensation for loss of office indicator <Indicator is automatically prefilled when applicable after record import to digital service>',
    'd3(b) Compensation for loss of office',
    'd4(a) Retirement benefits including gratuities/ pension/ commutation of pension/ lump sum payments, etc from pension/ provident fund <Name of fund>',
    'd4(b) Amount accrued from 01/01/1993',
    'd5) Contributions made by employer to any Pension/Provident Fund constituted outside Singapore without tax concession',
    'd6) Excess / voluntary contribution to CPF by employer ',
    'd7(a) Gains & profits via share options for Sec.10(1)(b) [This item is computed automatically after record import into digital service]',
    'd7(b) Gains & profits via share options for Sec.10(1)(g) [This item is computed automatically after record import into digital service]',
    'd8) Value of benefits-in-kind <This item is computed automatically after record import into digital service>',
    'd9(ii) Appendix 8A indicator <This item to be entered after record import into digital service>',
    'e(i) Remission/ Overseas Posting/ Exempt Indicator [choose option]',
    'e(ii) Amount of income for the Remission/ Overseas Posting/ Exempt Indicator selected',
    "f) Employee's income tax borne by employer? [Choose option]",
    'f(i) Amount of income for which tax is borne by employer',
    'f(ii) Fixed amount of tax for which tax is borne by employee',
    'g) Section 45 (applicable to non-resident director) [Choose option]',
    "Employee's compulsory CPF contribution",
    'DONATIONS deducted from salaries for Yayasan Mendaki Fund/Community Chest of Singapore/SINDA/CDAC/ECF/Other tax exempt donations',
    'CONTRIBUTIONS deducted from salaries to Mosque Building Fund',
    'LIFE INSURANCE PREMIUMS deducted from salaries  ',
]
IMPORT_MAX = 200
#: The payload's IR8A object, in the data items sheet's order (C1-C31).
IR8A_KEYS = [
    'periodPaymentFromDate', 'periodPaymentToDate', 'salary', 'bonus', 'nonContractualBonusPaidDate',
    'directorFees', 'directorsFeesApprovalDate', 'section45Indicator', 'allowances', 'grossCommission',
    'gratuityNoticePayExGratiaPayment', 'compensationForLossOfOffice', 'compensationForLossOfOfficeIndicator',
    'pensionRetirementBenefitsAccruedFrom1993', 'designatedPensionOrProvidentFundName',
    'employerContributionToPensionOrProvidentFundOutsideSg', 'excessOrVoluntaryCpfContributionByEmployer',
    'gainsAndProfitsFromSOGS101b', 'gainsAndProfitsUnderS101g', 'valueOfBenefitsInKind', 'othersIncome',
    'totalIncome', 'exemptIncomeOrIncomeSubjectToTaxRemission', 'exemptOrRemissionIncomeIndicator',
    'incomeTaxBorneByEmployerIndicator', 'amountOfIncomeForTaxBorneByEmployer',
    'fixedAmountOfIncomeForTaxBorneByEmployee', 'cpfOrDesignatedFund', 'donationsDeductedThroughSalaries',
    'contributionsToMosqueBuildingFund', 'lifeInsurancePremiumThroughSalaries',
]
PERSON_KEYS = ['recordId', 'idType', 'idNumber', 'name', 'dateOfBirth', 'sex', 'addressType',
               'addressLine1', 'addressLine2', 'addressLine3', 'postalCode',
               'countryCodeForForeignAddress', 'designation', 'bankCode', 'commencementDate',
               'cessationDate']
HEADER_KEYS = ['validateOnly', 'bypassWarning', 'incomeYear', 'employerTaxRefNumber',
               'authorisedPersonName', 'contactNumber', 'emailAddress', 'submissionType',
               'softwareCompanyName', 'softwareName', 'totalNumberIR8A', 'amountTotalIncomeOfIR8A',
               'totalNumberOfApp8A', 'totalNumberOfApp8B']


def _down(value):
    return int(math.floor(float(value or 0.0) + 1e-9))


def _up(value):
    return int(math.ceil(float(value or 0.0) - 1e-9))


class PbGovFormReaderSG(models.AbstractModel):
    _inherit = 'pb.gov.form.reader'

    def _pb_checks_sg_ir8a(self, form, company, out):
        """Appendix 8A / 8B are not made: say so when their items carry
        figures (warn, never block)."""
        bik = [p['employee_id'] for p in out['employees']
               if float((p.get('lines') or {}).get('d8') or 0.0)]
        shares = [p['employee_id'] for p in out['employees']
                  if float((p.get('lines') or {}).get('d7a') or 0.0)
                  or float((p.get('lines') or {}).get('d7b') or 0.0)]
        if bik:
            self._pb_warn(out, 'appendix_8a', _(
                "%s people have benefits in kind: IRAS needs Appendix 8A with them, which Payobook does not make. Add it in the myTax Portal before you submit.",
                len(bik)), employee_ids=bik)
        if shares:
            self._pb_warn(out, 'appendix_8b', _(
                "%s people have gains from share options: IRAS needs Appendix 8B with them, which Payobook does not make. Add it in the myTax Portal before you submit.",
                len(shares)), employee_ids=shares)
        return out


class PbGovFilingSG(models.Model):
    _inherit = 'pb.gov.filing'

    # ------------------------------------------------------------ the rows
    @api.model
    def _pb_sg_dates(self, employee, year_start, year_end):
        """(commencement, cessation) inside the income year, from the
        employment contracts ('' when outside it)."""
        Contract = self.env['hr.contract'].sudo().with_context(active_test=False)
        contracts = Contract.search([('employee_id', '=', employee.id),
                                     ('state', '!=', 'cancel')], order='date_start')
        if not contracts:
            return '', ''
        first = min(c.date_start for c in contracts if c.date_start) if any(
            c.date_start for c in contracts) else None
        ends = [c.date_end for c in contracts]
        last = None if any(not e for e in ends) else max(ends)
        start = fields.Date.to_string(first) if first and year_start <= first <= year_end else ''
        end = fields.Date.to_string(last) if last and year_start <= last <= year_end else ''
        return start, end

    @api.model
    def _pb_sg_people(self, data):
        """Every person as the payload needs them: whole dollars (income
        down, deductions up), others / total income added up from the
        rounded parts so the header total is their sum."""
        year_start = fields.Date.to_date(data['period_start'])
        year_end = fields.Date.to_date(data['period_end'])
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        people = []
        for n, person in enumerate(data.get('employees') or [], start=1):
            ident = person.get('identity') or {}
            lines = person.get('lines') or {}
            amt = {k: _down(lines.get(k)) for k in INCOME}
            amt.update({k: _up(lines.get(k)) for k in DEDUCTIONS})
            others = sum(amt[k] for k in OTHERS)
            total = amt['a'] + amt['b'] + amt['c'] + others
            emp = Emp.browse(person['employee_id'])
            commence, cease = self._pb_sg_dates(emp, year_start, year_end)
            local = (ident.get('postal_code') or '').isdigit() and len(ident.get('postal_code') or '') == 6 \
                and (emp.private_country_id.code if 'private_country_id' in emp._fields else '') == 'SG'
            reasons = []
            if not ident.get('id_number'):
                reasons.append(_("no NRIC, FIN, work permit or passport number"))
            if not ident.get('birthday'):
                reasons.append(_("no date of birth"))
            if not ident.get('sex'):
                reasons.append(_("no sex on the employee record"))
            if ident.get('id_type') == '12' and not ident.get('position'):
                reasons.append(_("no position (needed with a passport)"))
            if any(v < 0 for v in amt.values()) or total < 0:
                reasons.append(_("an amount below zero"))
            for key, value in amt.items():
                if value > 999999999:
                    reasons.append(_("an amount longer than 9 digits"))
                    break
            people.append({
                'employee_id': person['employee_id'], 'name': person.get('name') or '',
                'ident': ident, 'amt': amt, 'others': others, 'total': total,
                'from': commence or fields.Date.to_string(year_start),
                'to': cease or fields.Date.to_string(year_end),
                'commence': commence, 'cease': cease, 'local': local,
                'reasons': reasons, 'checks': list(person.get('checks') or []),
            })
        return people

    @api.model
    def _pb_sg_contact(self, data):
        user = self.env.user
        company = self.env['res.company'].browse(data['company_id'])
        phone = ''.join(ch for ch in (company.phone or '') if ch.isdigit())[-12:]
        return {'name': (user.name or '')[:100], 'email': (user.email or company.email or '')[:320],
                'phone': int(phone) if phone else None}

    @api.model
    def _pb_sg_payload(self, data, people):
        year = fields.Date.to_date(data['period_start']).year
        settings = data.get('settings') or {}
        contact = self._pb_sg_contact(data)
        records = []
        for n, p in enumerate(people, start=1):
            ident, amt = p['ident'], p['amt']
            person = {
                'recordId': n, 'idType': ident.get('id_type') or '', 'idNumber': ident.get('id_number') or '',
                'name': (p['name'] or '')[:100], 'dateOfBirth': ident.get('birthday') or '',
                'sex': ident.get('sex') or '',
                'addressType': 'L' if p['local'] else '',
                'addressLine1': (ident.get('address') or '')[:40] if p['local'] else '',
                'addressLine2': '', 'addressLine3': '',
                'postalCode': ident.get('postal_code') if p['local'] else '',
                'countryCodeForForeignAddress': '',
                'designation': (ident.get('position') or '')[:30], 'bankCode': '',
                'commencementDate': p['commence'], 'cessationDate': p['cease'],
            }
            ir8a = {
                'periodPaymentFromDate': p['from'], 'periodPaymentToDate': p['to'],
                'salary': amt['a'], 'bonus': amt['b'], 'nonContractualBonusPaidDate': '',
                'directorFees': amt['c'], 'directorsFeesApprovalDate': '', 'section45Indicator': '',
                'allowances': amt['d1'], 'grossCommission': amt['d2'],
                'gratuityNoticePayExGratiaPayment': amt['d3'],
                'compensationForLossOfOffice': amt['d3b'],
                'compensationForLossOfOfficeIndicator': 'Y' if amt['d3b'] else '',
                'pensionRetirementBenefitsAccruedFrom1993': amt['d4'],
                'designatedPensionOrProvidentFundName': '',
                'employerContributionToPensionOrProvidentFundOutsideSg': amt['d5'],
                'excessOrVoluntaryCpfContributionByEmployer': amt['d6'],
                'gainsAndProfitsFromSOGS101b': amt['d7a'], 'gainsAndProfitsUnderS101g': amt['d7b'],
                'valueOfBenefitsInKind': amt['d8'], 'othersIncome': p['others'], 'totalIncome': p['total'],
                'exemptIncomeOrIncomeSubjectToTaxRemission': amt['e'], 'exemptOrRemissionIncomeIndicator': '',
                'incomeTaxBorneByEmployerIndicator': '', 'amountOfIncomeForTaxBorneByEmployer': 0,
                'fixedAmountOfIncomeForTaxBorneByEmployee': 0,
                'cpfOrDesignatedFund': amt['CPF'], 'donationsDeductedThroughSalaries': amt['DON'],
                'contributionsToMosqueBuildingFund': amt['MBF'],
                'lifeInsurancePremiumThroughSalaries': amt['LIFE'],
            }
            person = {k: person[k] for k in PERSON_KEYS}
            person['ir8a'] = {k: ir8a[k] for k in IR8A_KEYS}
            person['appendix8A'] = {}
            person['appendix8B'] = {}
            records.append(person)
        header = {
            'validateOnly': True, 'bypassWarning': False, 'incomeYear': year,
            'employerTaxRefNumber': (settings.get('employer_tax_id') or '')[:25],
            'authorisedPersonName': contact['name'], 'contactNumber': contact['phone'],
            'emailAddress': contact['email'], 'submissionType': 'O',
            'softwareCompanyName': '', 'softwareName': 'Payobook',
            'totalNumberIR8A': len(records),
            'amountTotalIncomeOfIR8A': sum(r['ir8a']['totalIncome'] for r in records),
            'totalNumberOfApp8A': 0, 'totalNumberOfApp8B': 0,
        }
        payload = {'orgAndSubmissionInfo': {k: header[k] for k in HEADER_KEYS},
                   'employeePersonalParticulars': records}
        if data.get('adviser_mark'):
            # JSON has no comments: the adviser sentence is a top-level note
            # the sender removes before sending (said in the summary too)
            payload = {'_note': data.get('adviser_text') or '', **payload}
        return payload

    # ------------------------------------------------------------- the files
    def _pb_render_sg_ir8a(self, data):
        self.ensure_one()
        settings = data.get('settings') or {}
        if not (settings.get('employer_tax_id') or '').strip():
            raise UserError(_("Fill in the employer's tax reference number (UEN) for this form on Form lines first."))
        people = self._pb_sg_people(data)
        good = [p for p in people if not p['reasons']]
        if not good:
            raise UserError(_("Nobody in this filing can go into the submission file: %s.",
                              '; '.join(sorted({x for p in people for x in p['reasons']}))))
        if len(good) > 2000:
            raise UserError(_("IRAS takes at most 2,000 people in one submission. Prepare one filing per pay scheme."))
        payload = self._pb_sg_payload(data, good)
        files = [(self._pb_filename(data, 'IR8A_AIS', 'json'),
                  json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8'),
                  'application/json')]
        chunks = [good[i:i + IMPORT_MAX] for i in range(0, len(good), IMPORT_MAX)]
        for i, chunk in enumerate(chunks, start=1):
            stem = 'IR8A_import' if len(chunks) == 1 else 'IR8A_import_%d' % i
            files.append((self._pb_filename(data, stem, 'xlsx'),
                          self._pb_sg_import_xlsx(data, chunk), XLSX))
        files.append((self._pb_filename(data, 'IR8A_summary', 'xlsx'),
                      self._pb_sg_summary_xlsx(data, people, payload), XLSX))
        return files

    @api.model
    def _pb_sg_import_xlsx(self, data, people):
        buf, book = self._pb_workbook('IR8A')
        ws = book.add_worksheet('IR8A')
        head = book.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'bg_color': '#DDEBDA'})
        note = book.add_format({'italic': True, 'font_color': '#B45309'})
        ws.write_string(0, 0, 'version 1.0')
        for r in (1, 2, 3):
            ws.write_string(r, 0, '-')
        if data.get('adviser_mark'):
            ws.write_string(1, 1, data.get('adviser_text') or '', note)
        for c, text in enumerate(IMPORT_HEADS):
            ws.write_string(4, c, text, head)
        ws.set_row(4, 90)
        for i, p in enumerate(people):
            r = 5 + i
            ident, amt = p['ident'], p['amt']
            values = [
                i + 1, ID_TYPE_WORDS.get(ident.get('id_type') or '', ''), ident.get('id_number') or '',
                p['name'], {'M': 'Male', 'F': 'Female'}.get(ident.get('sex') or '', ''),
                ident.get('birthday') or '', (ident.get('position') or '')[:30],
                'Local Address' if p['local'] else '', (ident.get('address') or '') if p['local'] else '',
                (ident.get('postal_code') or '') if p['local'] else '', '',
                p['commence'], p['cease'], '', amt['a'], amt['b'], '', amt['c'], '', None,
                amt['d1'], amt['d2'], None, amt['d3'], None, amt['d3b'], '', amt['d4'], amt['d5'],
                amt['d6'], None, None, None, None, '', amt['e'] or '', '', '', '', '',
                amt['CPF'], amt['DON'], amt['MBF'], amt['LIFE'],
            ]
            for c, value in enumerate(values):
                if value is None:
                    continue        # a column the digital service fills itself
                if isinstance(value, (int, float)):
                    ws.write_number(r, c, value)
                else:
                    ws.write_string(r, c, value)
        ws.set_column(0, len(IMPORT_HEADS), 16)
        book.close()
        return buf.getvalue()

    @api.model
    def _pb_sg_summary_xlsx(self, data, people, payload):
        buf, book = self._pb_workbook(_("IR8A summary"))
        bold = book.add_format({'bold': True})
        h1 = book.add_format({'bold': True, 'font_size': 14})
        note = book.add_format({'italic': True, 'font_color': '#B45309', 'bold': True})
        money = book.add_format({'num_format': '#,##0'})
        ws = book.add_worksheet(_("Summary"))
        r = 0
        if data.get('adviser_mark'):
            ws.write_string(r, 0, data.get('adviser_text') or '', note)
            r += 1
            ws.write_string(r, 0, _("The submission file starts with this sentence as a note: take it out before sending."), note)
            r += 1
        ws.write_string(r, 0, _("Employee income for the year — Form IR8A"), h1)
        r += 1
        header = payload['orgAndSubmissionInfo']
        for label, value in ((_("Company"), data.get('company_name') or ''),
                             (_("Income year"), str(header['incomeYear'])),
                             (_("People in the submission"), str(header['totalNumberIR8A'])),
                             (_("Total income (whole dollars)"), '{:,}'.format(header['amountTotalIncomeOfIR8A'])),
                             (_("Before sending"), _("Fill in the software company name and check the contact person, number and e-mail. The file asks IRAS to check it only (validateOnly true): change that to false to submit."))):
            ws.write_string(r, 0, label, bold)
            ws.write_string(r, 1, value)
            r += 1
        r += 1
        for warn in data.get('warnings') or []:
            ws.write_string(r, 0, warn.get('message') or '')
            r += 1
        ws.set_column(0, 0, 40)
        ws.set_column(1, 1, 70)
        ws2 = book.add_worksheet(_("People"))
        heads = [_("Name"), _("ID number"), _("Total income"), _("CPF"), _("In the submission"), _("Check")]
        for c, head in enumerate(heads):
            ws2.write_string(0, c, head, bold)
        for i, p in enumerate(people, start=1):
            ws2.write_string(i, 0, p['name'])
            ws2.write_string(i, 1, p['ident'].get('id_number') or '')
            ws2.write_number(i, 2, p['total'], money)
            ws2.write_number(i, 3, p['amt']['CPF'], money)
            ws2.write_string(i, 4, _("No") if p['reasons'] else _("Yes"))
            ws2.write_string(i, 5, '; '.join(p['reasons'] + p['checks']))
        ws2.set_column(0, 0, 28)
        ws2.set_column(1, 4, 16)
        ws2.set_column(5, 5, 60)
        book.close()
        return buf.getvalue()

    # ------------------------------------------------------------- the PDF
    def _pb_certificate_sg_ir8a(self, data, person):
        self.ensure_one()
        p = self._pb_sg_people(dict(data, employees=[person]))[0]
        ident, amt = p['ident'], p['amt']
        out = self._pb_cert_base(data, person, _("Employee income for the year — Form IR8A"),
                                 "Form IR8A — Return of Employee's Remuneration")
        out['file_stem'] = 'IR8A'
        span = '%s – %s' % (p['from'], p['to'])
        out['blocks'].append({'title': _("Employee"), 'rows': [
            (_("Name"), p['name']),
            (_("NRIC, FIN or other ID"), ident.get('id_number') or ''),
            (_("Date of birth"), ident.get('birthday') or ''),
            (_("Position"), ident.get('position') or ''),
            (_("Period of payment"), span),
        ]})
        rec = self.sudo()
        rows = []
        for line in rec.form_id._pb_ordered_lines():
            if line.scope != 'employee':
                continue
            if line.code == 'OTHERS':
                value = p['others']
            elif line.code == 'TOTAL':
                value = p['total']
            else:
                value = amt.get(line.code, 0)
            rows.append((line.code if len(line.code) <= 3 else '',
                         cert_pdf.row_label(line.label, line.official_label),
                         '{:,}'.format(int(value)), 'total' if line.code == 'TOTAL' else ''))
        out['tables'].append({'title': _("Income and deductions (whole dollars)"),
                              'head': [_("Item"), _("What it is"), data.get('currency') or ''],
                              'rows': rows})
        if p['reasons']:
            out['notes'].insert(0, _("Not in the submission file yet: %s.", '; '.join(p['reasons'])))
        return out
