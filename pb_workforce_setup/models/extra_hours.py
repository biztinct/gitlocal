# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Step 4 foot — "Built-in extra hours count: On / Off" (WFSETUP P10b, R12).

The stock attendance app counts its own "extra hours" for every attendance
row whenever the person's version has an overtime rule set, and runs that
set's rules (server `hr_attendance/models/hr_attendance.py:318-331`).
Archiving the rule set does NOTHING (a Many2one still returns an archived
record) and clearing it per person does not last (every new version gets the
default set again). What works — proposal WFSETUP_P10A §7 — is to remove the
rules of the rule sets this company's people use: with no rules the stock
code returns no extra-hours intervals, new hires included. The stock rules
are `forcecreate="0"` data, so an upgrade does not bring them back.

"Off" stores every removed rule (its fields and its data id) on the company,
"On" puts exactly those back. Overtime for PAY never came from these lines:
it comes from the late and overtime rules (`hr.overtime.request`).
"""

import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

#: The rule fields a restore writes back (everything a person can set).
_RULE_FIELDS = ('name', 'description', 'base_off', 'timing_type', 'timing_start', 'timing_stop',
                'expected_hours_from_contract', 'resource_calendar_id', 'expected_hours',
                'quantity_period', 'sequence', 'paid', 'amount_rate',
                'employee_tolerance', 'employer_tolerance')


class ResCompanyExtraHours(models.Model):
    _inherit = 'res.company'

    pb_wfs_extra_hours_saved = fields.Text(
        string='Built-in extra hours rules (saved while switched off)', readonly=True, copy=False,
        help='Written by Workforce setup when the built-in extra hours count is switched off, '
             'so switching it on again restores the same rules.')


class WorkforceSetupExtraHours(models.AbstractModel):
    _inherit = 'pb.workforce.setup'

    @api.model
    def _extra_rulesets(self):
        """The rule sets this company's people (and its new hires) use."""
        Ruleset = self.env.get('hr.attendance.overtime.ruleset')
        if Ruleset is None:
            return None
        Ruleset = Ruleset.sudo().with_context(active_test=False)
        company = self.env.company
        ids = set()
        Version = self.env['hr.version'].sudo()
        if 'ruleset_id' in Version._fields:
            ids |= set(Version.search([('employee_id.company_id', '=', company.id),
                                       ('ruleset_id', '!=', False)]).mapped('ruleset_id').ids)
        default = self.env.ref('hr_attendance.hr_attendance_default_ruleset', raise_if_not_found=False)
        if default:
            ids.add(default.id)
        return Ruleset.browse(sorted(ids)).exists()

    @api.model
    def _extra_hours_state(self):
        rulesets = self._extra_rulesets()
        if rulesets is None:
            return False
        rules = rulesets.mapped('rule_ids')
        saved = self.env.company.sudo().pb_wfs_extra_hours_saved
        return {'on': bool(rules), 'rules': len(rules), 'saved': bool(saved)}

    @api.model
    def _rules_payload(self, state, policy):
        payload = super()._rules_payload(state, policy)
        payload['extra_hours'] = self._extra_hours_state()
        return payload

    @api.model
    def _extra_rules_payload(self):
        state, policy, _active = self._rules_state()
        return self._rules_payload(state, policy)

    @api.model
    def extra_hours_off(self):
        """Remove the built-in extra-hours rules, keeping them for "On"."""
        self._gate_edit()
        rulesets = self._extra_rulesets()
        if rulesets is None:
            raise UserError(_("The attendance app's extra hours are not installed here."))
        rules = rulesets.mapped('rule_ids')
        company = self.env.company.sudo()
        if not rules:
            return {'summary': _("Built-in extra hours are already off."),
                    'rules': self._extra_rules_payload()}
        Data = self.env['ir.model.data'].sudo()
        saved = json.loads(company.pb_wfs_extra_hours_saved or '[]')
        for rule in rules:
            vals = {}
            for name in _RULE_FIELDS:
                if name not in rule._fields:
                    continue
                value = rule[name]
                vals[name] = value.id if hasattr(value, '_name') else value
            xmlid = Data.search([('model', '=', rule._name), ('res_id', '=', rule.id)], limit=1)
            saved.append({'ruleset_id': rule.ruleset_id.id, 'values': vals,
                          'xmlid': [xmlid.module, xmlid.name, bool(xmlid.noupdate)] if xmlid else None})
        company.write({'pb_wfs_extra_hours_saved': json.dumps(saved, default=str)})
        n = len(rules)
        rules.unlink()
        return {'summary': (_("Built-in extra hours are off: 1 rule removed. Overtime comes from your rules.")
                            if n == 1 else
                            _("Built-in extra hours are off: %s rules removed. Overtime comes from your rules.", n)),
                'removed': n, 'rules': self._extra_rules_payload()}

    @api.model
    def extra_hours_on(self):
        """Put back exactly the rules "Off" removed."""
        self._gate_edit()
        company = self.env.company.sudo()
        saved = json.loads(company.pb_wfs_extra_hours_saved or '[]')
        if not saved:
            raise UserError(_("There are no saved extra-hours rules to put back. Add them on the "
                              "attendance settings screen."))
        Rule = self.env['hr.attendance.overtime.rule'].sudo()
        Ruleset = self.env['hr.attendance.overtime.ruleset'].sudo().with_context(active_test=False)
        Data = self.env['ir.model.data'].sudo()
        made = 0
        with self.env.cr.savepoint():
            for row in saved:
                ruleset = Ruleset.browse(row.get('ruleset_id') or 0).exists()
                if not ruleset:
                    continue
                vals = dict(row.get('values') or {}, ruleset_id=ruleset.id)
                rule = Rule.create(vals)
                made += 1
                xmlid = row.get('xmlid')
                if xmlid and not Data.search_count([('module', '=', xmlid[0]), ('name', '=', xmlid[1])]):
                    Data.create({'module': xmlid[0], 'name': xmlid[1], 'model': rule._name,
                                 'res_id': rule.id, 'noupdate': bool(xmlid[2])})
            company.write({'pb_wfs_extra_hours_saved': False})
        return {'summary': (_("Built-in extra hours are on again: 1 rule put back.") if made == 1 else
                            _("Built-in extra hours are on again: %s rules put back.", made)),
                'restored': made, 'rules': self._extra_rules_payload()}
