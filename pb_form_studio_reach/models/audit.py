# -*- coding: utf-8 -*-
"""Timeline (FS-5 item 7): changes to custom fields, old -> new.

* Watched: the field-change audit (`biz.audit.mixin`, wired onto the employee
  and the contract by pb_employee_vault) logs the fields its rules name
  (`biz.audit.rule._watched_fields`, ormcached per model). Every
  Form-builder field of the employee and the contract is added to that set
  here — read off the registry, cached the same way and cleared by every
  registry setup (adding or deleting a field runs one). So a field is on the
  timeline from the moment it exists, with no rule row to keep in step.
* Files: the entry says "File attached" / "File removed", never the content.
* Readers: the employee side panel's Timeline and the contract drawer's
  History hide changes to a custom field the reader may not see (label AND
  values), by the precedent of pb_job_change (a context flag read by
  `biz.audit.entry._search`).
"""
from odoo import api, models, tools
from odoo.fields import Domain

from .common import CON, EMP, PREFIX

HIDE_KEY = 'pbfr_hide_audit_fields'


class BizAuditRuleFormBuilder(models.Model):
    _inherit = 'biz.audit.rule'

    @api.model
    def _watched_fields(self, model_name):
        base = super()._watched_fields(model_name)
        extra = self._pbfr_watched(model_name)
        return (base | extra) if extra else base

    @api.model
    @tools.ormcache('model_name')
    def _pbfr_watched(self, model_name):
        if model_name not in (EMP, CON) or model_name not in self.env:
            return frozenset()
        return frozenset(n for n, f in self.env[model_name]._fields.items()
                         if n.startswith(PREFIX) and f.manual)


class BizAuditMixinFormBuilder(models.AbstractModel):
    _inherit = 'biz.audit.mixin'

    def _biz_audit_display(self, fname, value):
        field = self._fields.get(fname)
        if field is not None and field.type == 'binary' and fname.startswith(PREFIX):
            # Never the file itself in the trail — only that there is one.
            # Stored text, in English like the mixin's own "Yes" / "No".
            return 'File attached' if value else 'File removed'
        return super()._biz_audit_display(fname, value)


class BizAuditEntryFormBuilder(models.Model):
    _inherit = 'biz.audit.entry'

    @api.model
    def _search(self, domain, *args, **kwargs):
        hide = self.env.context.get(HIDE_KEY)
        if hide:
            parts = [Domain.AND([Domain('model_name', '=', model),
                                 Domain('field_name', 'in', list(names))])
                     for model, names in hide if names]
            if parts:
                domain = Domain.AND([Domain(domain), ~Domain.OR(parts)])
        return super()._search(domain, *args, **kwargs)


def _hide_context(env):
    Studio = env['pb.form.studio']
    hide = tuple((m, tuple(sorted(Studio._pbfr_hidden_names(m)))) for m in (EMP, CON))
    hide = tuple(h for h in hide if h[1])
    return {HIDE_KEY: hide} if hide else {}


class EmployeeTimelineFormBuilder(models.AbstractModel):
    _inherit = 'pb.employee.timeline'

    def _audit_items(self, emp, unmask_wage):
        ctx = _hide_context(self.env)
        if ctx:
            self = self.with_context(**ctx)
        return super()._audit_items(emp, unmask_wage)


class ContractHistoryFormBuilder(models.AbstractModel):
    _inherit = 'pb.contracts'

    @api.model
    def _cd_history_fields(self, contract, unmask, symbol=''):
        ctx = _hide_context(self.env)
        if ctx:
            self = self.with_context(**ctx)
        return super()._cd_history_fields(contract, unmask, symbol)
