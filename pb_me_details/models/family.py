# -*- coding: utf-8 -*-
"""A person's family members — one list per employee.

Before this there was no family list at all (FACTS §2.1): Vietnam tax
dependants lived in their own payroll table, benefit cover kept its own
"family covered" text. This list is what the employee sees and proposes
changes to on My Payobook; HR keeps it from the backend.

TAX NEVER MOVES BY ITSELF (owner ruling E1). A member who counts for tax in a
Vietnam company does not reach the tax dependants pay reads
(`vietnam.employee.dependent`) when the change is approved. It waits as
"Waiting for HR to confirm for tax", and only HR's one tick
(`action_confirm_tax`) writes — or ends — the dependant. Outside Vietnam the
flag is kept as information; nothing reads it for pay.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

RELATIONSHIPS = [
    ('spouse', 'Husband or wife'),
    ('child', 'Child'),
    ('parent', 'Parent'),
    ('sibling', 'Brother or sister'),
    ('other', 'Other'),
]

TAX_STATES = [
    ('none', 'Not counted for tax'),
    ('waiting', 'Waiting for HR to confirm for tax'),
    ('confirmed', 'Confirmed for tax'),
]

#: Who may press the tax tick: it changes take-home, so the pay team.
TAX_GROUPS = ('om_hr_payroll.group_hr_payroll_user',)
HR_GROUPS = ('hr.group_hr_user',) + TAX_GROUPS


def is_vietnam(company):
    return bool(company) and (company.country_id.code or '') == 'VN'


class PbEmployeeFamily(models.Model):
    _name = 'pb.employee.family'
    _description = 'Family member'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'employee_id, birthdate, id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  index=True, ondelete='cascade', tracking=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id',
                                 store=True, index=True, readonly=True)
    name = fields.Char(string='Name', required=True, tracking=True)
    relationship = fields.Selection(RELATIONSHIPS, string='Relationship',
                                    required=True, default='child', tracking=True)
    birthdate = fields.Date(string='Date of birth', tracking=True)
    id_number = fields.Char(string='ID or birth certificate number', tracking=True)
    counts_for_tax = fields.Boolean(
        string='Counts for tax', tracking=True,
        help='The employee says this person depends on them for tax. In a '
             'Vietnam company HR confirms it before pay uses it.')
    insured = fields.Boolean(string='Covered by insurance', tracking=True)
    active = fields.Boolean(default=True)

    tax_state = fields.Selection(TAX_STATES, string='Tax', default='none',
                                 required=True, readonly=True, tracking=True,
                                 copy=False, index=True)
    tax_action = fields.Selection([('add', 'Start counting'),
                                   ('end', 'Stop counting')],
                                  string='When HR confirms', readonly=True,
                                  copy=False)
    tax_confirmed_by = fields.Many2one('res.users', string='Confirmed by',
                                       readonly=True, copy=False)
    tax_confirmed_on = fields.Datetime(string='Confirmed on', readonly=True,
                                       copy=False)
    vn_dependent_id = fields.Many2one('vietnam.employee.dependent',
                                      string='Tax dependant', readonly=True,
                                      copy=False, ondelete='set null')

    # ------------------------------------------------------------- rules
    @api.model
    def _pb_is(self, groups):
        user = self.env.user
        return self.env.su or user._is_admin() or any(
            user.has_group(g) for g in groups)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._pb_is(HR_GROUPS):
            raise AccessError(_("Family members are changed through My "
                                "Payobook or by HR."))
        for vals in vals_list:
            for f in ('tax_state', 'tax_action', 'tax_confirmed_by',
                      'tax_confirmed_on', 'vn_dependent_id'):
                if not self.env.context.get('pb_family_sys'):
                    vals.pop(f, None)
        return super().create(vals_list)

    def write(self, vals):
        guarded = {'tax_state', 'tax_action', 'tax_confirmed_by',
                   'tax_confirmed_on', 'vn_dependent_id'}.intersection(vals)
        if guarded and not self.env.context.get('pb_family_sys'):
            raise AccessError(_("The tax status of a family member is set by "
                                "the Confirm for tax button only."))
        return super().write(vals)

    def _pb_sys(self):
        return self.with_context(pb_family_sys=True)

    # ------------------------------------------------- the waiting state
    def _pb_mark_for_tax(self, action, approver=None):
        """After an approved change: wait for HR's tick (Vietnam only).
        Elsewhere nothing waits and nothing reaches pay."""
        for rec in self:
            if not (is_vietnam(rec.company_id)
                    and 'vietnam.employee.dependent' in self.env):
                continue
            if action == 'end' and not rec.vn_dependent_id \
                    and rec.tax_state != 'confirmed':
                rec._pb_sys().write({'tax_state': 'none', 'tax_action': False})
                continue
            rec._pb_sys().write({'tax_state': 'waiting', 'tax_action': action})
            rec._pb_todo_for(approver)

    def _pb_todo_for(self, user):
        """A to-do on the member for the person who approved the change, so
        the tick is not forgotten (it shows in their activities)."""
        self.ensure_one()
        user = user or self.env.user
        if not user or user.share or user._is_public():
            return
        activity_type = self.env.ref('mail.mail_activity_data_todo',
                                     raise_if_not_found=False)
        try:
            with self.env.cr.savepoint():
                self.sudo().activity_schedule(
                    activity_type_id=activity_type.id if activity_type else False,
                    summary=_("Confirm for tax"),
                    note=_("Check this family member's papers, then press "
                           "Confirm for tax. Pay changes only after that."),
                    user_id=user.id)
        except Exception:                   # noqa: BLE001 — a reminder only
            pass

    # -------------------------------------------------------- the tick
    def _pb_dependent_relationship(self):
        mapping = {'spouse': 'spouse', 'child': 'child', 'parent': 'parent',
                   'sibling': 'sibling'}
        return mapping.get(self.relationship, 'other')

    def action_confirm_tax(self):
        """HR's one tick: the ONLY thing that changes what pay reads."""
        if not self._pb_is(TAX_GROUPS):
            raise AccessError(_("Only the pay team can confirm a family member "
                                "for tax."))
        Dependent = self.env['vietnam.employee.dependent'].sudo() \
            if 'vietnam.employee.dependent' in self.env else None
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.tax_state != 'waiting':
                raise UserError(_("%s is not waiting for a tax decision.",
                                  rec.name))
            if Dependent is None:
                raise UserError(_("Tax dependants are not kept in this "
                                  "database."))
            dep = rec.vn_dependent_id.sudo()
            if rec.tax_action == 'end':
                if dep and (not dep.effective_to or dep.effective_to > today):
                    dep.write({'effective_to': today})
                vals = {'tax_state': 'none'}
            else:
                dep_vals = {
                    'employee_id': rec.employee_id.id,
                    'name': rec.name,
                    'relationship': rec._pb_dependent_relationship(),
                    'date_of_birth': rec.birthdate or False,
                    'identification_number': rec.id_number or False,
                    'status': 'eligible',
                }
                if dep:
                    if dep.effective_to and dep.effective_to <= today:
                        dep_vals['effective_to'] = False
                    dep.write(dep_vals)
                else:
                    dep_vals['effective_from'] = today
                    dep = Dependent.create(dep_vals)
                vals = {'tax_state': 'confirmed', 'vn_dependent_id': dep.id}
            vals.update({'tax_action': False, 'tax_confirmed_by': self.env.uid,
                         'tax_confirmed_on': fields.Datetime.now()})
            rec._pb_sys().write(vals)
            rec.activity_ids.filtered(
                lambda a: a.summary == _("Confirm for tax")).sudo().action_done()
            rec.message_post(body=_("Confirmed for tax by %s.",
                                    self.env.user.name))
        return True

    def action_not_for_tax(self):
        """HR decides the member does not count for tax (nothing is written
        to pay; a dependant already counted is left exactly as it is)."""
        if not self._pb_is(TAX_GROUPS):
            raise AccessError(_("Only the pay team can decide this."))
        for rec in self:
            if rec.tax_state != 'waiting':
                continue
            rec._pb_sys().write({
                'tax_state': 'confirmed' if rec.vn_dependent_id
                and rec.tax_action == 'end' else 'none',
                'tax_action': False,
                'tax_confirmed_by': self.env.uid,
                'tax_confirmed_on': fields.Datetime.now(),
            })
            rec.activity_ids.filtered(
                lambda a: a.summary == _("Confirm for tax")).sudo().action_done()
            rec.message_post(body=_("Not counted for tax, decided by %s.",
                                    self.env.user.name))
        return True
