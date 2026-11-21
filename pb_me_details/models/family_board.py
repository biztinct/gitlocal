# -*- coding: utf-8 -*-
"""People > Family — family members waiting for the pay team's tax tick, and
what employees changed on My Payobook lately.

The one coloured thing on the board is "waiting for HR to confirm for tax":
it is the only place where an approved family change can reach pay, and it
reaches pay only through the tick here (owner ruling E1).
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .family import HR_GROUPS, TAX_GROUPS

RECENT_DAYS = 30


class PbFamilyBoard(models.AbstractModel):
    _name = 'pb.family.board'
    _description = 'Family and details board'

    @api.model
    def _pb_allowed(self):
        return self.env['pb.employee.family']._pb_is(HR_GROUPS)

    @api.model
    def get_board(self, view='waiting', search=''):
        if not self._pb_allowed():
            return {'allowed': False,
                    'why': _("Only HR and the pay team can see this.")}
        Family = self.env['pb.employee.family'].sudo().with_context(
            active_test=False)
        companies = self.env.companies.ids
        base = [('company_id', 'in', companies)]
        needle = (search or '').strip()
        waiting_dom = base + [('tax_state', '=', 'waiting')]
        since = fields.Datetime.now() - timedelta(days=RECENT_DAYS)
        Req = self.env['pb.me.detail.request'].sudo()
        recent_dom = [('company_id', 'in', companies),
                      ('state', 'in', ('approved', 'refused')),
                      ('decided_on', '>=', since)]
        open_dom = [('company_id', 'in', companies), ('state', '=', 'hr_review')]
        counts = {
            'waiting': Family.search_count(waiting_dom),
            'open': Req.search_count(open_dom),
            'recent': Req.search_count(recent_dom),
            'members': Family.with_context(active_test=True).search_count(base),
        }
        rows = []
        if view == 'waiting':
            dom = list(waiting_dom)
            if needle:
                dom += ['|', ('name', 'ilike', needle),
                        ('employee_id.name', 'ilike', needle)]
            for m in Family.search(dom, order='write_date desc, id desc', limit=200):
                rows.append({
                    'id': m.id, 'member': m.name or '',
                    'relationship': dict(m._fields['relationship']
                                         ._description_selection(self.env)).get(
                                             m.relationship, ''),
                    'employee': m.employee_id.name or '',
                    'company': m.company_id.name or '',
                    'birthdate': fields.Date.to_string(m.birthdate) if m.birthdate else '',
                    'id_number': m.id_number or '',
                    'action': m.tax_action or 'add',
                    'removed': not m.active,
                })
        else:
            dom = list(open_dom if view == 'open' else recent_dom)
            if needle:
                dom += [('employee_id.name', 'ilike', needle)]
            for r in Req.search(dom, order='write_date desc, id desc', limit=200):
                rows.append({
                    'id': r.id, 'title': r.pb_label(),
                    'employee': r.employee_id.name or '',
                    'company': r.company_id.name or '',
                    'state': r.state,
                    'when': fields.Datetime.to_string(r.decided_on or r.submitted_on
                                                      or r.create_date),
                })
        return {'allowed': True, 'view': view, 'counts': counts, 'rows': rows,
                'can_tick': self.env['pb.employee.family']._pb_is(TAX_GROUPS)}

    @api.model
    def confirm_tax(self, member_id):
        member = self._pb_member(member_id)
        member.with_env(self.env).action_confirm_tax()
        return True

    @api.model
    def leave_tax(self, member_id):
        member = self._pb_member(member_id)
        member.with_env(self.env).action_not_for_tax()
        return True

    @api.model
    def open_member(self, member_id):
        member = self._pb_member(member_id)
        return {
            'type': 'ir.actions.act_window', 'res_model': 'pb.employee.family',
            'res_id': member.id, 'view_mode': 'form',
            'views': [(False, 'form')], 'target': 'new',
            'name': member.name,
        }

    @api.model
    def open_requests(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': 'pb.me.detail.request',
            'view_mode': 'list,form', 'views': [(False, 'list'), (False, 'form')],
            'name': _("Changes to details"), 'target': 'current',
        }

    @api.model
    def _pb_member(self, member_id):
        if not self._pb_allowed():
            raise AccessError(_("Only HR and the pay team can see this."))
        member = self.env['pb.employee.family'].with_context(
            active_test=False).browse(int(member_id)).exists()
        if not member or member.company_id.id not in self.env.user.company_ids.ids:
            raise AccessError(_("That family member could not be found."))
        return member
