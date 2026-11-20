# -*- coding: utf-8 -*-
"""R23 (FS-7) — the employee's standard fields: which can be hidden, and how
the side panel and Full details follow the administrator's screen rule.

THE LOCKED LIST (`_pbfs_standard_locked`, the engine's one hook). Derived
from the code at origin/19.1 (FS7_REPORT.md §3 has the plain-words table):

* required to save the record — the engine's own part (model + form);
* identity — name, company, Country of Work: label locked too;
* the contract and pay set-up the employee record carries
  (`PORTAL_CONTRACT` of R14, the wage, hourly cost, overtime ruleset, leave
  policy, working schedule);
* approvals and access — manager, department, job, the approvers and the
  login/badge/clock boxes (`pb_timeoff`, expenses, attendance, `biz_access`);
* government forms and statutory files — what `pb_form_lines/models/
  reader.py`, `pb_hr_govt/models/report_base.py` and the fund/tax readers
  print (birthday, gender, nationality, ID / passport / permit numbers, home
  address, social security number, badge number, ethnicity), the tax boxes
  (`PORTAL_TAX`, Tax details), and the statutory ones among the boxes TIDY-E
  shows by Country of Work (`pb_employee_form_tidy/models/form_rules.py`;
  `STD_COUNTRY_*` below) — the others can be hidden, and the product's
  country rule and the administrator's combine (rule 6);
* bank — every bank box (`pb_pay_delivery` / `pb_bank_ocr` read them);
* anything a pay formula can read — FS-10: the SAME answer as the My
  Payobook lock's "A pay formula reads it" (`_pbfs_people_pay_reads`): every
  field the formula catalogue offers, plus what a formula of this database is
  bound to (`employee.<field>`, related and `tax.*` sources) and what a pay
  data file fills (`hr.payslip.import.mapping.target_field_id`). FS-7 locked
  catalogue fields only once a formula was bound, so Place of Birth showed
  "A pay formula reads it" and could still be hidden. A rule saved on a field
  before it became locked is cleared on upgrade with a history line
  (`migrations/19.0.1.4.0`).
"""
import logging

from odoo import api, models

from .form_studio import (MODEL, PORTAL_ACCESS, PORTAL_CONTRACT, PORTAL_COUNTRY, PORTAL_TAX)

_logger = logging.getLogger(__name__)

#: name, company and Country of Work — their LABEL is locked too.
STD_IDENTITY = ('name', 'company_id', 'payroll_country', 'pbfs_country_of_work_id')
#: approvals, access and the pay set-up follow them.
STD_ORG = ('department_id', 'job_id', 'job_title', 'parent_id', 'address_id',
           'work_location_id')
STD_ACCESS = tuple(n for n in PORTAL_ACCESS if n != 'badge_ids')
STD_PAY = PORTAL_CONTRACT + ('wage', 'hourly_cost', 'currency_id', 'resource_calendar_id',
                             'contract_wage')
#: printed by government forms and statutory files (readers in the module doc).
STD_STATUTORY = ('birthday', 'sex', 'gender', 'country_id', 'identification_id', 'passport_id',
                 'permit_no', 'ssnid', 'barcode', 'ethnicity_id', 'private_street',
                 'private_street2', 'private_city', 'private_state_id', 'private_zip',
                 'private_country_id', 'vn_dependent_ids', 'pb_sg_nric',
                 # the Vietnamese identity numbers the social-insurance and
                 # tax readers use (FIELD_AUDIT_FACTS §0: side panel only)
                 'vietnam_social_insurance_number', 'vietnam_passport_number')
#: Of TIDY-E's one-country boxes, the statutory ones: Vietnamese insurance,
#: tax and payroll facts (VN social-insurance files, tax returns), Indonesian
#: NPWP / BPJS / PTKP, Indian PAN / UAN / ESI / regime, Singapore residency /
#: SHG (`pb_form_lines` readers, fund files). The others (training facts,
#: the Internal Committee box, the two Vietnamese demo flags) stay hideable
#: unless a pay formula can read them (FS-10: the Indonesian family card is
#: in the formula catalogue, so it is locked now).
STD_COUNTRY_PREFIXES = ('vn_', 'pb_vn_', 'pb_in_', 'pb_id_', 'pb_bpjs_')
STD_COUNTRY_STATUTORY = ('pb_npwp_number', 'subject_to_pit', 'insurance_code', 'tham_gia_bhxh',
                         'pb_sg_tax_residency', 'pb_sg_shg_fund')
#: Not offered: status widgets, summaries and helpers the form draws as boxes.
STD_EXCLUDE = ('hr_icon_display', 'show_hr_icon_display', 'employee_properties', 'version_id',
               'pb_profile_contract_pay', 'pb_work_timezone_note', 'image_1920', 'active',
               'pbfs_country_of_work_id')

#: Side panel tab keys -> the panel's own tab names.
PANEL_TABS = ('personal', 'job', 'pay')


class PbFormStudioPeopleStandard(models.AbstractModel):
    _inherit = 'pb.form.studio'

    # ------------------------------------------------------------- locked
    @api.model
    def _pbfs_people_pay_reads(self):
        """Employee fields pay depends on — `{field: reason}`. ONE answer for
        "does a pay formula read it", shared with the My Payobook lock (R14,
        `_pbfs_portal_locked`), so the Form builder never says "A pay formula
        reads it" about a field it still lets the administrator hide (FS-10):

        * every field the pay formula catalogue offers
          (`_pbfs_people_formula_names`: `application_domain_sources.
          EMPLOYEE_FIELDS` minus what payroll never reads, the first hop of
          each related source, `pb_me_tax`'s tax sources) — a formula author
          can bind any of them at any time, outside the Form builder;
        * what a formula of THIS database is bound to (`employee.<field>`, a
          related source, a `tax.*` source — FS-7 missed the last kind);
        * what a pay data file fills (`hr.payslip.import.mapping`)."""
        _ = self.env._
        reads = _('A pay formula reads it, so pay depends on this field.')
        out = {name: reads for name in self._pbfs_people_formula_names()}
        if 'hr.formula.rule' in self.env and \
                'application_source_key' in self.env['hr.formula.rule']._fields:
            related = {}
            try:
                from odoo.addons.pb_hr_payroll_formula.models import application_domain_sources as ads
                related = {k: hops[0] for k, hops in ads.RELATED_FIELDS.items()}
            except ImportError:
                pass
            tax = {}
            try:
                from odoo.addons.pb_me_tax.models.formula_sources import TAX_SOURCES
                tax = {k: spec[2] for k, spec in TAX_SOURCES.items() if len(spec) > 2}
            except ImportError:
                pass
            Rule = self.env['hr.formula.rule'].sudo().with_context(active_test=False)
            keys = {k.strip() for k in Rule.search([
                '|', ('application_source_key', '=like', 'employee.%'),
                ('application_source_key', 'in', list(tax) or ['-'])]).mapped(
                    'application_source_key') if k}
            for key in keys:
                name = related.get(key) or tax.get(key) or key.split('.', 1)[1]
                out.setdefault(name, reads)
        if 'hr.payslip.import.mapping' in self.env:
            Mapping = self.env['hr.payslip.import.mapping'].sudo().with_context(active_test=False)
            for name in Mapping.search([('target_field_id.model', '=', MODEL)]).mapped(
                    'target_field_id.name'):
                out.setdefault(name, _('A pay data file fills it, so pay depends on this field.'))
        return out

    @api.model
    def _pbfs_standard_locked(self, model):
        out = dict(super()._pbfs_standard_locked(model) or {})
        if model != MODEL or MODEL not in self.env:
            return out
        _ = self.env._
        Model = self.env[MODEL]
        pay = _('Pay or statutory files depend on this field.')
        rows = [
            (('name',), _('It names the person on every payslip and file.'), True),
            (STD_IDENTITY, _('Pay rules, statutory files and the fields each person sees follow '
                             'this field.'), True),
            (STD_PAY, pay, False),
            (STD_ORG, _('Approvals, access and the pay set-up follow this field.'), False),
            (STD_ACCESS, _('Logins, approvals and the time clock follow this field.'), False),
            (STD_STATUTORY, _('Government forms and statutory files print this field.'), False),
            (PORTAL_TAX + PORTAL_COUNTRY, _('Tax and social insurance files depend on this field.'),
             False),
            (tuple(n for n in Model._fields if 'bank' in n or n in ('account_number',
                                                                    'pb_other_name_holder')),
             _('Bank files depend on this field.'), False),
        ]
        rule_reason = _('Pay or statutory files of that country depend on this field.')
        tidy = self._pbfs_people_tidy_rules()
        rows.append((tuple(n for n, r in tidy.items()
                           if r and r != 'remove' and (n.startswith(STD_COUNTRY_PREFIXES)
                                                       or n in STD_COUNTRY_STATUTORY)),
                     rule_reason, False))
        for names, reason, label in rows:
            for name in names:
                if name in Model._fields:
                    cur = out.get(name)
                    if cur is None:
                        out[name] = {'reason': reason, 'label': label}
                    elif label:
                        cur['label'] = True
        for name, reason in self._pbfs_people_pay_reads().items():
            if name in Model._fields:
                out.setdefault(name, {'reason': reason, 'label': False})
        return out

    # ------------------------------------------------------------- catalogue
    @api.model
    def _pbfs_people_tidy_rules(self):
        """TIDY-E's per-box table, when that module is installed here."""
        if not hasattr(self.env[MODEL], '_pb_tidy_tab_names'):
            return {}
        try:
            from odoo.addons.pb_employee_form_tidy.models.form_rules import FORM_RULES
        except ImportError:
            return {}
        return FORM_RULES

    @api.model
    def _pbfs_std_builtin_rule(self, model, name):
        if model == MODEL:
            rule = self._pbfs_people_tidy_rules().get(name)
            if rule:
                return rule
        return super()._pbfs_std_builtin_rule(model, name)

    @api.model
    def _pbfs_std_exclude(self, model):
        out = set(super()._pbfs_std_exclude(model) or ())
        if model == MODEL:
            out |= set(STD_EXCLUDE)
        return out

    @api.model
    def _pbfs_std_panel_boxes(self, model):
        out = list(super()._pbfs_std_panel_boxes(model) or [])
        if model != MODEL:
            return out
        try:
            from odoo.addons.pb_employee_vault.models.employee_details import _SPEC
        except ImportError:
            return out
        _ = self.env._
        titles = {'personal': _('Side panel: Personal'), 'job': _('Side panel: Job'),
                  'pay': _('Side panel: Pay & tax')}
        for tab, _key, _title, _icon, _gate, rows in _SPEC:
            for name, label, _opt in rows:
                if not name.startswith('_'):
                    out.append((name, str(label), titles.get(tab, tab)))
        return out


class PbPeopleStandard(models.AbstractModel):
    _inherit = 'pb.people'

    @api.model
    def _e360_details(self, emp, unmask, vietnam=None):
        """R23: the side panel follows the administrator's screen rule — a
        hidden field leaves its group (the group goes when nothing is left),
        an own label replaces the panel's. Never raises: a rule must not cost
        anybody the panel."""
        tabs = super()._e360_details(emp, unmask, vietnam=vietnam)
        try:
            Studio = self.env['pb.form.studio']
            rules = Studio._pbfs_std_rules(MODEL)
            if not rules:
                return tabs
            country = Studio._pbfs_record_countries(emp).get(emp.id)
            for key in PANEL_TABS:
                groups = []
                for group in tabs.get(key) or []:
                    rows = []
                    for row in group.get('rows') or []:
                        rule = rules.get(row.get('key'))
                        if Studio._pbfs_std_hidden(rule, country):
                            continue
                        if rule and rule.get('label'):
                            row = dict(row, label=rule['label'])
                        rows.append(row)
                    if not rows:
                        continue
                    groups.append(dict(group, rows=rows,
                                       filled=sum(1 for r in rows if not r.get('empty'))))
                tabs[key] = groups
        except Exception:                               # noqa: BLE001
            _logger.warning('Form builder: the side panel screen rule could not be applied to '
                            'employee %s', emp.id, exc_info=True)
        return tabs
