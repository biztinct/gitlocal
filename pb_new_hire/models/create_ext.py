# -*- coding: utf-8 -*-
"""NEWHIRE P1 — the approved write of a studio hire (D2).

ONE create path. The studio proposes a values dict carrying `pb_nh: True`;
on approval `pb.newhire.proposal._apply_employee` replays
`pb.people.onboard.wizard.create_employee(values)` under NEWHIRE_WRITE, as it
always has. This file extends that replay BY INHERITANCE so the new keys are
honoured; a call without `pb_nh` goes straight to `super()` and nothing
changes for the Updates joiners sheet, the org chart or pay scales.

THE ORDER PROBLEM (handover §2.4) AND HOW IT IS SOLVED. `super().create_employee`
builds `hr.employee.create` and `create_contract` from fixed key lists, so the
new keys never reach either create. Both must see them AT create time:

  * the employee's Country of Work drives the time-zone calendar clone, which
    only happens inside `hr.employee.create` (NH2);
  * the contract's Country of Work drives its currency, and a Monetary wage is
    rounded to the currency in force when it is written (NH3).

So `super()` is still called — the parent's bank, return-shape and every
other module's override (pay scales, org chart) keep running in whatever MRO
order the registry built — but with the studio's extras in a context key
(`NH_CTX`). Two create overrides below read that key and add a WHITELISTED
set of fields to exactly one `hr.employee.create` (the one with the hire's
name) and one `hr.contract.create` (for that employee). Nothing a caller
types names a field.

THE CONTRACT. Created with the automatic fill-in deferred
(`pb_skip_fill_in`); then the answers the person CHANGED are written as
lines (sudo, behind the HR gate already passed — NH6: officers only read
lines), and only then `_pb_fill_in_defaults()` runs, so it fills the rest and
marks them `auto` while leaving the person's choices alone (E).

FAILURE. Anything that goes wrong after the employee exists raises, so the
engine's savepoint rolls the whole approved apply back and says why on the
request (safety rail §3). Only "it was deleted meanwhile" (NH8) is downgraded
to a note on the new employee.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, formatLang

from odoo.addons.pb_people_advanced.models.newhire_approval import (
    NEWHIRE_WRITE, require_hr,
)

_logger = logging.getLogger(__name__)

#: "These are a studio hire's extras, for this one create."
NH_CTX = 'pb_nh_hire'

#: The employee fields the studio may set at create (whitelist, §3).
EMPLOYEE_EXTRA = ('payroll_country', 'date_of_joining', 'private_email',
                  'private_phone', 'work_location_id',
                  # P2: the late and overtime rule group rides on the ONE create
                  # (FACTS_CORE §H: a category passed at create is respected)
                  'pb_attendance_category')


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class PbOnboardWizardNewHire(models.AbstractModel):
    _inherit = 'pb.people.onboard.wizard'

    @api.model
    def _pb_nh_replay(self, vals):
        """Re-validate a stored payload against the world NOW (NH8): a team,
        job, manager or site deleted since Send is dropped with a note, never
        a crash. Returns (values, notes)."""
        values = dict(vals)
        names = values.get('pb_nh_names') or {}
        notes = []
        checks = (('department_id', 'hr.department', _("The team %s was removed before approval.")),
                  ('job_id', 'hr.job', _("The job %s was removed before approval.")),
                  ('parent_id', 'hr.employee', _("The manager %s left before approval.")),
                  ('work_location_id', 'hr.work.location', _("The work site %s was removed before approval.")),
                  ('country_id', 'res.country', '%s'),
                  ('type_id', 'hr.contract.type', '%s'))
        for key, model, sentence in checks:
            if not values.get(key):
                continue
            record = self.env[model].sudo().browse(_int(values[key])).exists() \
                if model in self.env else None
            if record and (model != 'hr.employee' or record.active):
                continue
            values.pop(key, None)
            if key == 'job_id' and names.get('job_id'):
                values.setdefault('job_title', names['job_id'])
            if key not in ('country_id', 'type_id'):
                notes.append(sentence % (names.get(key) or ''))
        return values, notes

    @api.model
    def _pb_nh_extra(self, values):
        employee = {}
        for key in EMPLOYEE_EXTRA:
            if values.get(key) not in (None, '', False):
                employee[key] = values[key]
        return {
            'name': ' '.join(str(values.get('name') or '').split()),
            'employee': employee,
            'contract': {
                'payroll_country': values.get('payroll_country') or False,
                'usual': [{'code': str(u.get('code') or ''), 'amount': float(u.get('amount') or 0.0)}
                          for u in (values.get('usual') or []) if isinstance(u, dict)],
                'scheme_id': _int(values.get('pb_nh_scheme_id')),
                'contract_kind': values.get('contract_kind') or 'permanent',
                'pin_note': values.get('pb_scale_pin_note') or False,
                'type_id': _int(values.get('type_id')),
            },
        }

    @api.model
    def create_employee(self, vals):
        vals = vals or {}
        if not vals.get('pb_nh') or not self.env.context.get(NEWHIRE_WRITE):
            return super().create_employee(vals)
        require_hr(self.env)
        values, notes = self._pb_nh_replay(vals)
        extra = self._pb_nh_extra(values)
        res = super(PbOnboardWizardNewHire, self.with_context(**{NH_CTX: extra})) \
            .create_employee(values)
        if not res.get('employee_id'):
            raise UserError(res.get('error') or _("The employee could not be created."))
        if res.get('error') or (values.get('with_contract') and not res.get('contract_id')):
            # a half-made hire is never left behind: the engine rolls this back
            raise UserError(res.get('error') or _("The contract could not be created."))
        emp = self.env['hr.employee'].sudo().browse(int(res['employee_id']))
        trial_end = values.get('trial_date_end')
        if trial_end and hasattr(emp, 'pb_set_trial_end'):
            if not emp.pb_set_trial_end(fields.Date.to_date(trial_end)):
                raise UserError(_("The end of the trial period could not be set."))
        for note in notes:
            emp.message_post(body=note)
        # P2: the welcome legs — after the core, each in its own savepoint;
        # a failed leg never undoes the hire (handover §2.2).
        contract = self.env['hr.contract'].sudo().browse(_int(res.get('contract_id'))).exists()
        legs, summary = self.env['pb.new.hire.legs'].run(emp, contract, values)
        return dict(res, legs=legs, legs_summary=summary)


class PbContractWizardNewHire(models.AbstractModel):
    _inherit = 'pb.people.contract.wizard'

    @api.model
    def create_contract(self, vals):
        extra = self.env.context.get(NH_CTX)
        if not extra or not self.env.context.get(NEWHIRE_WRITE) or not (vals or {}).get('employee_id'):
            return super().create_contract(vals)
        cextra = extra.get('contract') or {}
        vals = dict(vals)
        employee_id = int(vals['employee_id'])
        if cextra.get('pin_note') and not vals.get('pb_scale_pin_note'):
            vals['pb_scale_pin_note'] = cextra['pin_note']
        # The Vietnam contract kind follows the choice on the screen.
        if cextra.get('payroll_country') == 'VN' and self._vn_kind_field() and 'vn_kind' not in vals:
            vals['vn_kind'] = 'definite' if cextra.get('contract_kind') == 'fixed' else 'indefinite'
        ctx = {'pb_skip_fill_in': True,
               NH_CTX: dict(extra, employee_id=employee_id)}
        res = super(PbContractWizardNewHire, self.with_context(**ctx)).create_contract(vals)
        if not isinstance(res, dict) or not res.get('contract_id') or res.get('error'):
            return res
        contract = self.env['hr.contract'].sudo().browse(int(res['contract_id']))
        self._pb_nh_lines(contract, cextra)
        self.env.flush_all()                    # NH4: the map reads teams with raw SQL
        contract._pb_fill_in_defaults()
        return res

    @api.model
    def _pb_nh_lines(self, contract, cextra):
        """One line per usual answer the person CHANGED (an "off" yes/no is a
        line of 0 — it blocks the automatic line). No `pb_fill` mark: a person
        chose these."""
        usual = cextra.get('usual') or []
        if not usual:
            return 0
        config = self.env['hr.formula.config'].sudo().browse(_int(cextra.get('scheme_id'))).exists()
        if not config:
            contract.employee_id.sudo().message_post(body=_(
                "The pay scheme chosen for the usual answers was removed before approval, "
                "so they were filled in as usual."))
            return 0
        rules = {(r.code or '').strip(): r for r in config._pb_usual_answer_rules()}
        Template = self.env['hr.contract.advantage.template'].sudo()
        Line = self.env['hr.contract.advantage'].sudo()
        Change = self.env['hr.contract.advantage.change'].sudo() \
            if 'hr.contract.advantage.change' in self.env else None
        have = {(line.advantage_template_id.code or '').strip()
                for line in contract.advantages_ids}
        made = 0
        for item in usual:
            rule = rules.get(item['code'])
            if not rule or item['code'] in have:
                continue
            template = Template.template_for_rule(rule)
            Line.create({'contract_id': contract.id, 'advantage_template_id': template.id,
                         'amount': item['amount']})
            have.add(item['code'])
            made += 1
            if Change is not None:
                try:
                    Change.log(contract, template, rule.default_value or 0.0, item['amount'],
                               'manual', notes=_("Chosen when the person was added"),
                               effective_date=contract.date_start)
                except Exception:       # noqa: BLE001 — the trail never undoes a line
                    _logger.warning('new hire: no trail row for line %s on contract %s',
                                    item['code'], contract.id, exc_info=True)
        return made


class HrEmployeeNewHire(models.Model):
    _inherit = 'hr.employee'

    @api.model_create_multi
    def create(self, vals_list):
        extra = self.env.context.get(NH_CTX)
        if not extra or len(vals_list) != 1 \
                or ' '.join(str(vals_list[0].get('name') or '').split()) != extra.get('name'):
            return super().create(vals_list)
        vals = dict(vals_list[0])
        for key, value in (extra.get('employee') or {}).items():
            if key in EMPLOYEE_EXTRA and key in self._fields and key not in vals:
                vals[key] = value
        # The extras belong to this one create, never to one nested inside it.
        return super(HrEmployeeNewHire, self.with_context(**{NH_CTX: False})).create([vals])


class HrContractNewHire(models.Model):
    _inherit = 'hr.contract'

    @api.model_create_multi
    def create(self, vals_list):
        extra = self.env.context.get(NH_CTX)
        if not extra or not extra.get('employee_id') or len(vals_list) != 1 \
                or _int(vals_list[0].get('employee_id')) != extra['employee_id']:
            return super().create(vals_list)
        vals = dict(vals_list[0])
        code = (extra.get('contract') or {}).get('payroll_country')
        field = self._fields.get('payroll_country')
        if code and field and code in dict(field._description_selection(self.env)):
            vals['payroll_country'] = code      # NH3: the currency is right when the wage is written
        type_id = _int((extra.get('contract') or {}).get('type_id'))
        if type_id and 'type_id' in self._fields \
                and self.env['hr.contract.type'].sudo().browse(type_id).exists():
            vals['type_id'] = type_id           # P2: the category chosen on screen
        employee = self.env['hr.employee'].sudo().browse(extra['employee_id']).exists()
        if employee and employee.resource_calendar_id:
            vals['resource_calendar_id'] = employee.resource_calendar_id.id   # NH2
        return super(HrContractNewHire, self.with_context(**{NH_CTX: False})).create([vals])


class PbNewHireProposalNH(models.Model):
    _inherit = 'pb.newhire.proposal'

    def _pb_nh_values(self):
        self.ensure_one()
        values = (self.payload() or {}).get('values') or {}
        return values if values.get('pb_nh') else None

    def _pb_nh_currency(self, values):
        names = values.get('pb_nh_names') or {}
        if not names.get('currency'):
            return self.env['res.currency']
        return self.env['res.currency'].sudo().with_context(active_test=False).search(
            [('name', '=', names['currency'])], limit=1)

    def _approval_context(self):
        """A studio hire is asked for in the money of its country of work:
        the request's amount carries the CONTRACT currency (the proposal's
        own currency field stays the company's — the mixin is unchanged)."""
        ctx = super()._approval_context()
        values = self._pb_nh_values()
        if values is not None:
            currency = self._pb_nh_currency(values)
            if currency:
                ctx['currency_id'] = currency.id
        return ctx

    def _proposal_rows(self):
        values = self._pb_nh_values()
        if values is None:
            return super()._proposal_rows()
        names = values.get('pb_nh_names') or {}
        rows = []

        def add(label, value):
            if value not in (None, '', False):
                rows.append((label, '', value))

        add(_('Name'), values.get('name'))
        add(_('Work email'), values.get('work_email'))
        add(_('Personal email'), values.get('private_email'))
        add(_('Personal phone'), values.get('private_phone'))
        day = lambda v: format_date(self.env, v) if v else v      # noqa: E731
        add(_('First day'), day(values.get('date_start')))
        add(_('Country of work'), names.get('country') or values.get('payroll_country'))
        add(_('Paid by'), names.get('scheme') or _('No pay scheme yet'))
        add(_('Team'), self._row_label('hr.department', values.get('department_id'),
                                       names.get('department_id') or ''))
        if values.get('job_id'):
            add(_('Job'), self._row_label('hr.job', values['job_id'], names.get('job_id') or ''))
        else:
            add(_('Job title'), values.get('job_title'))
        add(_('Manager'), self._row_label('hr.employee', values.get('parent_id'),
                                          names.get('parent_id') or ''))
        add(_('Work site'), self._row_label('hr.work.location', values.get('work_location_id'),
                                            names.get('work_location_id') or ''))
        add(_('Nationality'), self._row_label('res.country', values.get('country_id')))
        add(_('Kind of contract'), _('Fixed term') if values.get('contract_kind') == 'fixed'
            else _('Permanent'))
        add(_('Ends'), day(values.get('date_end')))
        add(_('Trial period ends'), day(values.get('trial_date_end')) or _('No trial period'))
        currency = self._pb_nh_currency(values)
        wage = values.get('wage')
        if wage not in (None, '', False):
            add(_('Monthly pay'), formatLang(self.env, float(wage), currency_obj=currency or None)
                if currency else formatLang(self.env, float(wage)))
        else:
            add(_('Monthly pay'), _('From the pay scale'))
        for item in values.get('usual') or []:
            if isinstance(item, dict):
                add(item.get('name') or item.get('code') or '', _('Changed to %s', item.get('text') or ''))
        add(_('Contract category'), self._row_label('hr.contract.type', values.get('type_id')))
        rows.extend(self._pb_nh_welcome_rows(values, names))
        return rows

    def _pb_nh_welcome_rows(self, values, names):
        """P2: steps 4 and 6 as the approver reads them."""
        rows = []

        def add(label, value):
            if value not in (None, '', False):
                rows.append((label, '', value))

        add(_('Working week'), names.get('week') or _("The company's usual hours"))
        if values.get('pb_attendance_category'):
            add(_('Late and overtime rule'), _('Manager') if values['pb_attendance_category'] == 'manager'
                else _('Worker'))
        add(_('Clock number'), values.get('pb_clock_code') or _('No clocking'))
        mode = values.get('login_mode') or 'none'
        add(_('Sign-in'), {'email': _('Email invitation'),
                           'code': _('Employee number')}.get(mode, _('Not yet')))
        if values.get('open_case', True):
            add(_('Joining checklist'), names.get('case') or _('None is set up'))
            add(_('Buddy'), names.get('buddy') or _('The manager chooses'))
            if values.get('equipment') is not None:
                add(_('Equipment'), ', '.join(names.get('equipment') or []) or _('None'))
        else:
            add(_('Joining checklist'), _('Not started for this person'))
        add(_('Contract letter'), names.get('letter') if values.get('letter') else _('Not prepared'))
        own = names.get('own') or {}
        for name in (values.get('own_fields') or {}):
            item = own.get(name) or {}
            add(item.get('label') or name, item.get('text'))
        return rows

    def _approval_withdraw(self, request, reason):
        """Withdrawn by the person who sent it (NEWHIRE D7): the studio hire
        is being prepared again, no longer waiting. Other new-hire proposals
        keep the engine's behaviour."""
        for proposal in self:
            if proposal._pb_nh_values() is not None and proposal.state == 'pending':
                proposal.sudo().write({'state': 'draft'})
        return True
