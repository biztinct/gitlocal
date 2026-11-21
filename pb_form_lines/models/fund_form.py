# -*- coding: utf-8 -*-
"""WDGAP S2-B2 — fund files on the S2-A engine: the few things a fund file
needs that a tax return does not.

Everything here EXTENDS the S2-A models by `_inherit` (handover WAVE 2 "File
ownership": `form.py`, `reader.py`, `filing.py` and the board JS belong to the
other wave-2 builder; this phase only adds files).

  * `pb.gov.form.filing_section` — where a form's tile sits on Compliance ›
    Filings: "Tax returns" (every S2-A form, the default), "Fund files" (this
    phase), or "Used by reports" (a form that is not a filing of its own: the
    pay items the Vietnamese social-insurance reports read, item 6). The
    Filings board groups its tiles by it.
  * `pb.gov.form.adviser_wording` — the G3 sentence a form's files and screens
    carry until the company marks it accepted. Default unchanged ("Check with
    your adviser before first filing"); fund files say "Check with the fund
    before the first upload" (the ONE new sentence the handover allows).
  * `pb.gov.form.employer_label` — what the company's own number is called on
    Form lines for this form (a fund file needs the company's fund number, not
    its tax number). The value is still kept in `employer_tax_id`.
  * `pb.gov.form.compare_line_codes` — the lines whose items are compared with
    Fund payments for the same month (item 5).

Identity for fund files goes through ONE dispatcher override
(`_pb_identity` → `_pb_fund_identity_<code>`), never through the per-country
hooks `_pb_identity_in` / `_pb_identity_sg` that the year-end builder adds: a
fund file needs member numbers, not tax numbers, and the two must not shadow
each other at merge time.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# WDGAP S2 merge (S2-B2 merge-time task 3): S2-B1's year-end forms sit under
# 'year_end'; this field is THE grouping of the Filings board (`tile_group`
# on form.py is kept in step with it in the data).
SECTIONS = [('tax', 'Tax returns'), ('year_end', 'Year-end'), ('fund', 'Fund files'),
            ('reports', 'Used by reports')]
WORDINGS = [('adviser', 'Check with your adviser before first filing'),
            ('fund', 'Check with the fund before the first upload')]


class PbGovFormFund(models.Model):
    _inherit = 'pb.gov.form'

    filing_section = fields.Selection(
        SECTIONS, string='Shown under', required=True, default='tax',
        help="Where the form's tile sits on Compliance › Filings.")
    adviser_wording = fields.Selection(
        WORDINGS, string='Note until accepted', required=True, default='adviser',
        help="The sentence every file and screen of this form carries until a "
             "payroll manager marks it accepted by the authority.")
    employer_label = fields.Char(
        string="Name of the company's number", translate=True,
        help="What the company's own number is called for this form on Form "
             "lines. Empty: the employer's tax number.")
    compare_line_codes = fields.Char(
        help="Comma-separated line codes compared with Fund payments.")

    def _pb_adviser_sentence(self):
        """The G3 sentence for this form, in the reader's language (one
        literal each so the terms export sees them)."""
        self.ensure_one()
        if self.adviser_wording == 'fund':
            return _("Check with the fund before the first upload")
        return _("Check with your adviser before first filing")

    def _pb_compare_codes(self):
        self.ensure_one()
        return [c.strip() for c in (self.compare_line_codes or '').split(',') if c.strip()]


class PbGovFilingFund(models.Model):
    _inherit = 'pb.gov.filing'

    @api.model
    def _pb_adviser_text(self):
        """The form's own sentence: the record's form, or — while `prepare`
        runs on the bare model — the form it was called for (context key set
        by `prepare` below)."""
        form = self.env['pb.gov.form']
        if len(self) == 1 and self.form_id:
            form = self.form_id
        elif self.env.context.get('pb_adviser_form_id'):
            form = form.sudo().browse(self.env.context['pb_adviser_form_id']).exists()
        if form and form.adviser_wording == 'fund':
            return form._pb_adviser_sentence()
        return super()._pb_adviser_text()

    @api.model
    def prepare(self, form, company, start, end, scheme_ids=None, currency_id=None):
        try:
            form_rec = self.env['pb.gov.form.reader']._pb_form(form)
        except Exception:    # noqa: BLE001 — the original refusal is said by super
            form_rec = None
        if form_rec and (form_rec.adviser_wording != 'adviser'
                         or form_rec.filing_section == 'fund'):
            record = super(PbGovFilingFund, self.with_context(
                pb_adviser_form_id=form_rec.id,
                pb_fund_period=(fields.Date.to_string(fields.Date.to_date(start)),
                                fields.Date.to_string(fields.Date.to_date(end))))).prepare(
                form, company, start, end, scheme_ids=scheme_ids, currency_id=currency_id)
            return record.with_env(self.env)
        return super().prepare(form, company, start, end, scheme_ids=scheme_ids,
                               currency_id=currency_id)


class PbGovFormReaderFund(models.AbstractModel):
    _inherit = 'pb.gov.form.reader'

    @api.model
    def _pb_identity(self, form, employee):
        """Fund files read MEMBER numbers (`_pb_fund_identity_<code>`); every
        other form keeps the per-country hooks."""
        if form.filing_section == 'fund':
            hook = getattr(self, '_pb_fund_identity_%s' % (form.code or '').lower(), None)
            if hook is not None:
                return hook(form, employee)
        return super()._pb_identity(form, employee)

    # ----------------------------------------------------------- probes
    @api.model
    def _pb_probe(self, employee, names, contract_names=()):
        """The first filled value of `names` on the employee, then of
        `contract_names` on their running contract (legacy country modules
        kept some member numbers there). Every name is read by probe: a field
        that does not exist on this database is skipped."""
        emp = employee.sudo()
        for name in names:
            if name in emp._fields and emp[name]:
                return str(emp[name]).strip()
        if contract_names and 'hr.contract' in self.env:
            Contract = self.env['hr.contract'].sudo()
            wanted = [n for n in contract_names if n in Contract._fields]
            if wanted:
                contract = Contract.search([('employee_id', '=', emp.id),
                                            ('state', 'in', ('open', 'close'))],
                                           order='date_start desc, id desc', limit=1)
                for name in wanted:
                    if contract and contract[name]:
                        return str(contract[name]).strip()
        return ''

    @api.model
    def _pb_fund_answer(self, employee, values, missing):
        """The identity answer of a fund file: `missing` are the member-number
        labels the reader warns about; `leave_out` the plain reasons the
        renderer prints beside the person it leaves out."""
        emp = employee.sudo()
        values = dict(values)
        values.setdefault('name', emp.name or '')
        values.setdefault('birthday', fields.Date.to_string(emp.birthday) if emp.birthday else '')
        values['leave_out'] = [_("No %s on the employee record", label) for label in missing]
        return {'values': values, 'resident': True, 'missing': list(missing)}


class PbGovFormBoardFund(models.AbstractModel):
    _inherit = 'pb.gov.form.board'

    @api.model
    def _form_card(self, form, company):
        card = super()._form_card(form, company)
        section = form.filing_section or 'tax'
        card.update({
            'section': section,
            'section_label': dict(form._fields['filing_section']._description_selection(
                self.env)).get(section, ''),
            'adviser_wording': form.adviser_wording or 'adviser',
            'adviser_text': form._pb_adviser_sentence(),
            'employer_label': form.employer_label or '',
            'can_prepare': section != 'reports',
            'needs_settings': section != 'reports',
        })
        return card

    @api.model
    def get_form(self, form_id):
        card = super().get_form(form_id)
        form = self._form(form_id)
        if form.filing_section not in ('tax', 'year_end'):
            # the place-of-business number is the Indonesian tax returns'
            # (monthly BPMP and year-end BPA1 — S2 merge)
            card['needs_place'] = False
        return card
