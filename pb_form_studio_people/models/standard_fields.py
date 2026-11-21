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
* FS-10 (architect ruling): anything that REALLY reads the field on THIS
  database — a pay scheme component bound to it (`employee.<field>`, a
  related source, a `tax.*` source of `pb_me_tax`) in a scheme that is not
  archived, or a pay data file column that fills it — locked with a reason
  that names it ("Used by pay formula: <scheme>"). A field a formula merely
  COULD read stays hideable until one does; at that save the field is shown
  again with a history line and a notice (`_pbfs_std_readers_changed`, called
  from the readers' save points in `pb_form_studio_reach`). Bank layouts,
  government form lines and approval routing read only fields that are
  locked above anyway (`FS10_REPORT.md` §1).
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
#: the Indonesian family card, the two Vietnamese demo flags) stay hideable
#: unless something on this database really reads them (FS-10).
STD_COUNTRY_PREFIXES = ('vn_', 'pb_vn_', 'pb_in_', 'pb_id_', 'pb_bpjs_')
STD_COUNTRY_STATUTORY = ('pb_npwp_number', 'subject_to_pit', 'insurance_code', 'tham_gia_bhxh',
                         'pb_sg_tax_residency', 'pb_sg_shg_fund')
#: Not offered: status widgets, summaries and helpers the form draws as boxes.
STD_EXCLUDE = ('hr_icon_display', 'show_hr_icon_display', 'employee_properties', 'version_id',
               'pb_profile_contract_pay', 'pb_work_timezone_note', 'image_1920', 'active',
               'pbfs_country_of_work_id')

#: Side panel tab keys -> the panel's own tab names.
PANEL_TABS = ('personal', 'job', 'pay')

# R31 (FS-15) — boxes TIDY-E took off the screens that must NOT come back
# (`_pbfs_std_comeback`). Bank: R12 / FS-9, the approved account is the truth.
COMEBACK_BANK = ('account_number', 'bank_name')
#: the platform's version-record boxes (Payroll tab); the contract holds them.
COMEBACK_CONTRACT = ('contract_type_id', 'structure_type_id')
# FS-16: the 15 old Vietnam boxes that also stayed off (6 worked-out figures,
# 9 inputs of a section never drawn for Vietnam staff) were deleted from
# pb_hr_payroll_vietnam after a re-proof on the five sites (0 values, 0 readers).
#: removed boxes that are not Vietnam's: "Show again" proposes all countries.
PROPOSE_ALL = ('pb_position_reference', 'pb_emergency_relationship')


class PbFormStudioPeopleStandard(models.AbstractModel):
    _inherit = 'pb.form.studio'

    # ------------------------------------------------------------- locked
    @api.model
    def _pbfs_std_readers(self, model):
        """Employee fields really read on this database (FS-10): pay scheme
        components bound to them (live schemes only: an archived scheme reads
        nothing) and pay data file columns that fill them."""
        out = list(super()._pbfs_std_readers(model) or [])
        if model != MODEL or MODEL not in self.env:
            return out
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
            Rule = self.env['hr.formula.rule'].sudo()
            rules = Rule.search(['|', ('application_source_key', '=like', 'employee.%'),
                                 ('application_source_key', 'in', list(tax) or ['-']),
                                 ('config_id.active', '=', True)])
            for rule in rules:
                key = (rule.application_source_key or '').strip()
                field = related.get(key) or tax.get(key) or key.split('.', 1)[-1]
                if field in self.env[MODEL]._fields:
                    out.append((field, 'formula', rule.config_id.display_name or ''))
        out += self._pbfs_std_datafile_readers(MODEL)
        return out

    @api.model
    def _pbfs_people_pay_reads(self):
        """`{field: reason}` — what really reads each employee field (FS-10)."""
        return self._pbfs_std_used_reasons(MODEL)

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
        for name, reason in self._pbfs_std_used_reasons(MODEL).items():
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

    # ------------------------------------------------------ R31 (FS-15)
    @api.model
    def _pbfs_std_comeback(self, model):
        """The boxes TIDY-E took off the screens that must stay off, with the
        reason (decided per box from TIDY_E_REPORT §2–3, FIELD_AUDIT_FACTS
        §2/§3/§7 and the Full details arch): a live source took their place,
        their old section is never drawn for the people they belong to, or
        they are worked-out figures nobody types. Every other one can be
        shown again (FS15_REPORT.md has the table)."""
        out = dict(super()._pbfs_std_comeback(model) or {})
        if model != MODEL:
            return out
        _ = self.env._
        rows = [
            (COMEBACK_BANK, _('The bank account people are paid to is the approved one under '
                              'Bank details. This old box is no longer read, so showing it would '
                              'invite a second account that nothing uses.')),
            (COMEBACK_CONTRACT, _('The contract holds this now (contract type and pay structure). '
                                  'This box belongs to an older record and is not used.')),
        ]
        Model = self.env[MODEL]
        tidy = self._pbfs_people_tidy_rules()
        for names, reason in rows:
            for name in names:
                if name in Model._fields and tidy.get(name) == 'remove':
                    out[name] = reason
        return out

    # ------------------------------------------------------ FS-16 (owner)
    @api.model
    def _pbfs_std_all(self, model):
        """The Form builder lists only boxes that can come back: the ones that
        must stay off (`_pbfs_std_comeback`) are not listed at all — no greyed
        row, not counted in "Taken off the screens" (owner 2026-11-22: "causes
        confusion"). The server still refuses them (`update_standard`)."""
        out = super()._pbfs_std_all(model)
        stay = self._pbfs_std_comeback(model) if model == MODEL else {}
        if not stay:
            return out
        return {name: desc for name, desc in out.items() if name not in stay}

    @api.model
    def _pbfs_std_propose(self, model, name):
        """Show again: a Vietnamese box proposes Vietnam (the audit's removed
        boxes are all Vietnam's, except the two general Employment profile
        ones, which propose all countries)."""
        if model == MODEL and name not in PROPOSE_ALL:
            from odoo.addons.pb_form_studio.models.form_standard import show_only
            vn = self.env['res.country'].sudo().search([('code', '=', 'VN')], limit=1)
            if vn:
                return show_only([vn.id])
        return super()._pbfs_std_propose(model, name)

    @api.model
    def _pbfs_countries_in_use(self):
        """The People list's Country of Work figures: active people of the
        companies the reader works in, by Country of Work, most first; and how
        many have none ("Not recorded")."""
        rows, none = super()._pbfs_countries_in_use()
        if rows or MODEL not in self.env or 'payroll_country' not in self.env[MODEL]._fields:
            return rows, none
        if 'pb.people' in self.env and hasattr(self.env['pb.people'], '_pbf_base_domain'):
            domain = self.env['pb.people']._pbf_base_domain()
        else:
            domain = [('company_id', 'in', self.env.companies.ids), ('active', '=', True)]
        counts = {}
        for code, n in self.env[MODEL].sudo()._read_group(domain, ['payroll_country'], ['__count']):
            counts[str(code).upper() if code else ''] = n
        none = counts.pop('', 0)
        by_code = {(c.code or '').upper(): c for c in self.env['res.country'].search(
            [('code', 'in', list(counts))])}
        for code, n in counts.items():
            country = by_code.get(code)
            if country:
                rows.append({'id': country.id, 'name': country.name, 'code': country.code, 'n': n})
        rows.sort(key=lambda r: (-r['n'], r['name']))
        return rows, none

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
