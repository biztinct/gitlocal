from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.addons.pb_scheme_map.models.pb_scheme_map import MAX_EMPLOYEES


class PayBuilderSwitch(models.AbstractModel):
    _inherit = 'pb.pay.builder'

    @api.model
    def switch_preview(self, rule_id, to_per_person):
        studio = self.env['pb.formula.studio']
        if not studio._pbpb_manager():
            return {'ok': False, 'msg': _("Only a pay scheme manager can change this.")}
        rule = self.env['hr.formula.rule'].browse(int(rule_id)).exists()
        if not rule or (rule.config_id.company_id and rule.config_id.company_id not in self.env.companies):
            return {'ok': False, 'msg': _("This pay scheme is not available.")}
        rule.check_access('read')
        if rule.column_type != 'input' or not isinstance(to_per_person, bool):
            return {'ok': False, 'msg': _("Worked out by its formula — nobody types it.")}
        cfg = rule.config_id
        result = {'ok': True, 'count': 0, 'names': [], 'warning': False}
        if cfg.state != 'active' or rule.is_contract_component == to_per_person:
            return result
        today = fields.Date.context_today(self)
        contracts = self.env['hr.contract'].sudo().search([
            ('company_id', 'in', cfg.company_id.ids or self.env.companies.ids), ('state', '=', 'open'),
            ('date_start', '<=', today), '|', ('date_end', '=', False), ('date_end', '>=', today)])
        people = contracts.employee_id.ids
        paid = set()
        mapping = self.env['pb.scheme.map'].sudo()
        for start in range(0, len(people), MAX_EMPLOYEES):
            answers = mapping.resolve_many(people[start:start + MAX_EMPLOYEES], cfg.cycle_type, on_date=today)
            paid.update(person_id for person_id, answer in answers.items() if answer.get('config_id') == cfg.id)
        contracts = contracts.filtered(lambda c: c.employee_id.id in paid)
        lines = self.env['hr.contract.advantage'].sudo().search([
            ('contract_id', 'in', contracts.ids), ('advantage_template_id.code', '=', rule.code)])
        having = lines.contract_id
        affected = ((contracts - having) if to_per_person else having).employee_id
        if not affected:
            return result
        try:
            readable = self.env['hr.employee'].search([('id', 'in', affected.ids)], order='name, id', limit=20)
            result['names'] = readable.mapped('name')
        except AccessError:
            pass
        n = len(affected)
        if to_per_person:
            if n == 1:
                warning = _("From now on Payobook reads this amount from each person's contract. One person paid by this scheme has no amount there yet, so they get 0 for this line until someone types one.")
            else:
                warning = _("From now on Payobook reads this amount from each person's contract. %s people paid by this scheme have no amount there yet, so they get 0 for this line until someone types one.", n)
        else:
            kinds = [source['kind'] for source in rule.declared_sources() if source['kind'] != 'contract_component']
            first = kinds[0] if kinds else ''
            source = {'excel': _('the pay data file'), 'rule': _('the connected system'),
                      'feed': _('the connected system'), 'pay_run': _('the timesheet')}.get(first, _('the monthly pay data'))
            if n == 1:
                warning = _("One person has this amount on their contract. It stays there but pay stops reading it; the amount will come from %s each month.", source)
            else:
                warning = _("%(count)s people have this amount on their contract. It stays there but pay stops reading it; the amount will come from %(source)s each month.", count=n, source=source)
        return dict(result, count=n, warning=warning)


class PayBuilderStudio(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    @api.model
    def _pbpb_manager(self):
        return self.env.user.has_group('base.group_system') or self.env.user.has_group('pb_hr_payroll_formula.group_formula_manager')

    @property
    def _EDIT_FIELDS(self):
        return super()._EDIT_FIELDS + ('pbpb_period',)

    @property
    def _CFG_FIELDS(self):
        return super()._CFG_FIELDS + ('pbpb_main_rule_id',)

    @property
    def _CFG_M2O(self):
        return super()._CFG_M2O + ('pbpb_main_rule_id',)

    @api.model
    def get_component_edit(self, rule_id):
        data = super().get_component_edit(rule_id)
        if data.get('ok'):
            rule = self.env['hr.formula.rule'].browse(rule_id)
            data.update(pbpb_period=rule.pbpb_period or False, pbpb_guess=rule._pbpb_period_guess())
        return data

    @api.model
    def save_component(self, rule_id, vals):
        if not self._pbpb_manager():
            return {'ok': False, 'msg': _("Only a pay scheme manager can change this.")}
        rule = self.env['hr.formula.rule'].browse(int(rule_id)).exists()
        vals = dict(vals or {})
        if not rule:
            return super().save_component(rule_id, vals)
        cfg = rule.config_id
        if cfg.company_id and cfg.company_id not in self.env.companies:
            return {'ok': False, 'msg': _("This pay scheme is not available.")}
        kind = vals.get('column_type', rule.column_type)
        person = vals.get('is_contract_component', rule.is_contract_component)
        if kind != 'input' and person and 'is_contract_component' in vals:
            return {'ok': False, 'msg': _("Worked out by its formula — nobody types it.")}
        if rule.column_type == kind == 'input':
            # The editor posts its whole draft. Submitting an unchanged formula
            # or type would incorrectly send an ordinary source choice through
            # the live formula approval gate. Actual changes stay in the draft.
            for key in ('column_type', 'constant_value', 'excel_formula'):
                if key in vals and (vals[key] or False) == (rule[key] or False):
                    vals.pop(key)
        with self.env.cr.savepoint() as savepoint:
            if rule == cfg.pbpb_main_rule_id and (kind != 'input' or not person):
                cfg.pbpb_main_rule_id = False
            result = super().save_component(rule_id, vals)
            if not result.get('ok'):
                savepoint.rollback()
            return result

    @api.model
    def get_config_settings(self, config_id):
        result = super().get_config_settings(config_id)
        if result.get('ok'):
            cfg = self.env['hr.formula.config'].browse(config_id)
            result['pbpb_choices'] = [{'id': r.id, 'name': r._pbpb_name()}
                                      for r in cfg._pbpb_person_rules() if r.value_kind == 'money']
        return result

    @api.model
    def save_config_settings(self, config_id, vals):
        if 'pbpb_main_rule_id' in (vals or {}):
            if not self._pbpb_manager():
                return {'ok': False, 'msg': _("Only a pay scheme manager can change this.")}
            cfg = self.env['hr.formula.config'].browse(int(config_id)).exists()
            if not cfg or (cfg.company_id and cfg.company_id not in self.env.companies):
                return {'ok': False, 'msg': _("This pay scheme is not available.")}
            selected = int(vals.get('pbpb_main_rule_id') or 0)
            if selected and selected not in cfg._pbpb_person_rules().filtered(lambda r: r.value_kind == 'money').ids:
                return {'ok': False, 'msg': _("Choose a per-person money amount from this pay scheme.")}
        return super().save_config_settings(config_id, vals)
