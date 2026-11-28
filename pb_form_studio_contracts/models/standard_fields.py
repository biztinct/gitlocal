# -*- coding: utf-8 -*-
"""R23 (FS-7) — the contract's standard fields: which can be hidden, and how
the contract panel and the full contract form follow the administrator's
screen rule.

THE LOCKED LIST for the contract (the engine's one hook,
`_pbfs_standard_locked`), derived from the code at origin/19.1:

* required to save — the engine's part (model + form);
* identity — contract reference, company, Country of Work (label locked
  too) and the person on it;
* every term the payslip or the contract approval reads: the panel's
  "The money", "Dates" and "Payroll rules" groups (`pb_contracts/models/
  pb_contract_360.py` `_TERMS`), the approval's held terms (`contract_approval.
  MONEY_TERMS`), the pay components list, the pay classification boxes the
  formula catalogue offers (`application_domain_sources.CONTRACT_FIELDS`:
  salary basis, payroll contract type, nationality status, trial start),
  the accounting boxes (journal, analytic distribution);
* department and job — approvals and access follow them;
* anything that REALLY reads the field on this database (FS-10): a pay
  scheme component bound to `contract.<field>` in a scheme that is not
  archived, or a pay data file column — the reason names the scheme; a field
  that becomes used is shown again at that save (`_pbfs_std_readers_changed`).

Free to hide: HR responsible, location and cost centre, notes, signed date
(unless something really reads them).
"""
import logging

from odoo import api, models

from odoo.addons.pb_contracts.models.contract_approval import MONEY_TERMS
from odoo.addons.pb_contracts.models.pb_contract_360 import _TERMS, term_group_label
from odoo.addons.pb_form_studio.models.form_standard import STD_RAW

from .form_studio_host import MODEL

_logger = logging.getLogger(__name__)

STD_IDENTITY = ('name', 'company_id', 'pb_country_of_work_id')
STD_PERSON = ('employee_id',)
STD_PAY = ('wage', 'struct_id', 'structure_type_id', 'type_id', 'schedule_pay', 'pb_band_id',
           'pb_position_pct', 'journal_id', 'date_start', 'date_end', 'trial_date_end',
           'pb_trial_date_start', 'resource_calendar_id', 'state', 'currency_id',
           'advantages_ids', 'hirestatus', 'tupart', 'shuipart', 'dependents',
           'tax_identification_number', 'pb_salary_basis', 'pb_payroll_contract_type',
           'pb_payroll_nationality_status', 'analytic_distribution', 'contract_type_id',
           'payroll_country')
STD_ORG = ('department_id', 'job_id')
STD_EXCLUDE = ('kanban_state', 'active', 'company_country_id', 'country_code',
               'calendar_mismatch', 'pb_country_of_work_id')
#: The panel groups a payslip reads in full.
PAY_GROUPS = ('money', 'dates', 'rules')


class PbFormStudioContractStandard(models.AbstractModel):
    _inherit = 'pb.form.studio'

    @api.model
    def _pbfs_std_readers(self, model):
        """Contract fields really read on this database (FS-10): pay scheme
        components bound to `contract.<field>` in schemes that are not
        archived, and pay data file columns that fill them."""
        out = list(super()._pbfs_std_readers(model) or [])
        if model != MODEL or MODEL not in self.env:
            return out
        if 'hr.formula.rule' in self.env and \
                'application_source_key' in self.env['hr.formula.rule']._fields:
            Rule = self.env['hr.formula.rule'].sudo()
            for rule in Rule.search([('application_source_key', '=like', 'contract.%'),
                                     ('config_id.active', '=', True)]):
                field = (rule.application_source_key or '').strip().split('.', 1)[-1]
                if field in self.env[MODEL]._fields:
                    out.append((field, 'formula', rule.config_id.display_name or ''))
        out += self._pbfs_std_datafile_readers(MODEL)
        return out

    @api.model
    def _pbfs_contract_formula_used(self):
        """`{field: reason}` — what really reads each contract field (FS-10)."""
        return self._pbfs_std_used_reasons(MODEL)

    @api.model
    def _pbfs_standard_locked(self, model):
        out = dict(super()._pbfs_standard_locked(model) or {})
        if model != MODEL or MODEL not in self.env:
            return out
        _ = self.env._
        Model = self.env[MODEL]
        pay = _('Pay or statutory files depend on this field.')
        panel_pay = tuple(name for group, name, *_rest in _TERMS if group in PAY_GROUPS)
        rows = [
            (STD_IDENTITY, _('It names the contract on every payslip and file.'), True),
            (STD_PERSON, _('It says whose contract this is.'), False),
            (STD_PAY + tuple(MONEY_TERMS) + panel_pay, pay, False),
            (STD_ORG, _('Approvals, access and the pay set-up follow this field.'), False),
        ]
        for names, reason, label in rows:
            for name in names:
                if name in Model._fields:
                    cur = out.get(name)
                    if cur is None:
                        out[name] = {'reason': reason, 'label': label}
                    elif label:
                        cur['label'] = True
        for name, field in Model._fields.items():
            if field.type == 'monetary':
                out.setdefault(name, {'reason': pay, 'label': False})
        for name, reason in self._pbfs_contract_formula_used().items():
            if name in Model._fields:
                out.setdefault(name, {'reason': reason, 'label': False})
        return out

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
        _ = self.env._
        for group, name, label, *_rest in _TERMS:
            out.append((name, self.env._(label),
                        _('Contract panel: %s', term_group_label(self.env, group))))
        return out


class HrContractStandard(models.Model):
    _inherit = 'hr.contract'

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (bool(self.env.context.get(STD_RAW)),)

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """The full contract form follows the administrator's screen rule for
        standard fields (R23) — see the employee's twin in
        pb_form_studio_people/models/hr_employee.py."""
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != 'form':
            return arch, view
        if (self.env.lang or 'en_US') != 'en_US':
            # FS-7 addition: the rize-only "Payroll facts" tab
            # (pb_payroll_mapping_vn) has no Vietnamese or Indonesian text; the
            # employee's twin is pb_employee_form_tidy `_pb_tidy_tab_names`.
            self.env['pb.form.studio']._pbfs_translate_pages(
                arch, {'Payroll facts': self.env._("Payroll facts")})
        if self.env.context.get(STD_RAW):
            return arch, view
        try:
            self.env['pb.form.studio']._pbfs_std_apply_arch(arch, self._name, 'pb_country_of_work_id')
        except Exception:                               # noqa: BLE001
            _logger.exception('Form builder: the screen rule of standard fields could not be '
                              'applied to the contract form; it is shown as the modules draw it.')
            arch, view = super()._get_view(view_id, view_type, **options)
        return arch, view


class PbContractsStandard(models.AbstractModel):
    _inherit = 'pb.contracts'

    @api.model
    def _cd_terms(self, contract, symbol, can_write, unmask):
        """R23: the contract panel's Terms follow the screen rule — a hidden
        field leaves its group (and so the panel's write list, which is built
        from these groups), an own label replaces the panel's."""
        groups = super()._cd_terms(contract, symbol, can_write, unmask)
        try:
            Studio = self.env['pb.form.studio']
            rules = Studio._pbfs_std_rules(MODEL)
            if not rules:
                return groups
            country = Studio._pbfs_record_countries(contract).get(contract.id)
            out = []
            for group in groups:
                if group.get('pbfs'):
                    out.append(group)
                    continue
                entries = []
                for entry in group.get('fields') or []:
                    rule = rules.get(entry.get('name'))
                    if Studio._pbfs_std_hidden(rule, country):
                        continue
                    if rule and rule.get('label'):
                        entry = dict(entry, label=rule['label'])
                    entries.append(entry)
                out.append(dict(group, fields=entries))
            return out
        except Exception:                               # noqa: BLE001
            _logger.warning('Form builder: the contract panel screen rule could not be applied '
                            'to contract %s', contract.id, exc_info=True)
            return groups
