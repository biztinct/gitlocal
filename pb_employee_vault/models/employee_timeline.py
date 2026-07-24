# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Employee 360 timeline — one merged, newest-first employment history (Phase H §3).

Merges four kinds of already-existing evidence into presentation-ready items:
  1. biz.audit.entry rows for the employee + their contracts (dept / job / manager
     / company / active, and contract wage / state / dates / structure),
  2. pb.employee.bank.history rows (bank master changes),
  3. biz.approval.step.log rows for the employee's bank-change / business-trip /
     attendance-correction records (soft-hooked per model existence),
  4. contract lifecycle (created).

The service is HR-gated (Phase H); the own-employee variant arrives in Phase I.
Wage VALUES are masked unless the caller is a payroll manager — a two-tier
serialization decided server-side, never CSS hiding (safety rail 4). Nothing
raw leaks beyond what the (HR) caller may already read; account numbers are
always masked to the last four digits.
"""

from odoo import api, fields, models

# consumer models whose approval trail belongs on an employee's timeline
_APPROVAL_SOURCES = [
    ('pb.bank.change.request', 'Bank change', 'creditCard'),
    ('pb.business.trip', 'Business trip', 'briefcase'),
    ('hr.attendance.correction', 'Attendance correction', 'clock'),
]

# per-field presentation for audit entries
_FIELD_ICON = {
    'department_id': 'building', 'job_title': 'briefcase', 'parent_id': 'user',
    'company_id': 'building', 'active': 'user',
    'wage': 'banknote', 'state': 'briefcase',
    'date_start': 'calendar', 'date_end': 'calendar',
    'struct_id': 'fileText', 'structure_type_id': 'fileText',
}


class PbEmployeeTimeline(models.AbstractModel):
    _name = 'pb.employee.timeline'
    _description = 'Employee 360 Timeline'

    # ------------------------------------------------------------ mask helpers
    def _mask_account(self, number):
        digits = ''.join(ch for ch in (number or '') if ch.isdigit())
        return ('•••• ' + digits[-4:]) if len(digits) >= 4 else (digits or '—')

    def _actor(self, user):
        return {
            'actor': user.name if user else '',
            'actor_avatar': ('/web/image/res.users/%s/avatar_128' % user.id)
            if user else '',
        }

    def _humanize_state(self, key):
        return (key or '').replace('_', ' ').strip().capitalize() or '—'

    # --------------------------------------------------------------- gather
    def _collect(self, employee, unmask_wage):
        """Return every timeline item for ``employee``, newest-first. Private —
        the caller (an HR-gated facade) resolves the record and the wage-mask
        flag first; call_kw cannot reach it."""
        emp = employee.sudo()
        items = []
        items += self._audit_items(emp, unmask_wage)
        items += self._bank_items(emp)
        items += self._approval_items(emp)
        items += self._contract_items(emp)
        # newest-first; missing stamps sort last
        items.sort(key=lambda it: it.get('_dt') or fields.Datetime.now(),
                   reverse=True)
        for it in items:
            it.pop('_dt', None)
        return items

    def _audit_items(self, emp, unmask_wage):
        Entry = self.env['biz.audit.entry'].sudo()
        contract_ids = emp.contract_ids.ids
        # position changes (department / job) live on hr.version — resolve the
        # employee's versions and fold their entries into the employee timeline.
        version_ids = []
        if 'hr.version' in self.env:
            version_ids = self.env['hr.version'].sudo().search(
                [('employee_id', '=', emp.id)]).ids
        domain = ['|', '|',
                  '&', ('model_name', '=', 'hr.employee'), ('res_id', '=', emp.id),
                  '&', ('model_name', '=', 'hr.contract'),
                  ('res_id', 'in', contract_ids or [0]),
                  '&', ('model_name', '=', 'hr.version'),
                  ('res_id', 'in', version_ids or [0])]
        out = []
        for e in Entry.search(domain):
            is_wage = e.field_name == 'wage'
            icon = _FIELD_ICON.get(e.field_name, 'edit')
            if is_wage and not unmask_wage:
                title = 'Wage updated'
                detail = ''
            else:
                title = '%s updated' % (e.field_label or e.field_name)
                old = e.old_value or '—'
                new = e.new_value or '—'
                detail = '%s → %s' % (old, new)
            out.append({
                '_dt': e.stamp,
                'stamp': fields.Datetime.to_string(e.stamp),
                'kind': 'contract' if e.model_name == 'hr.contract' else 'employee',
                'icon': icon,
                'title': title,
                'detail': detail,
                **self._actor(e.user_id),
            })
        return out

    def _bank_items(self, emp):
        if 'pb.employee.bank.history' not in self.env:
            return []
        Hist = self.env['pb.employee.bank.history'].sudo()
        out = []
        for h in Hist.search([('employee_id', '=', emp.id)]):
            old = self._mask_account(h.old_account_number)
            new = self._mask_account(h.new_account_number)
            detail = '%s → %s' % (old, new)
            if h.new_bank_name and h.new_bank_name != h.old_bank_name:
                detail += '  ·  %s' % h.new_bank_name
            out.append({
                '_dt': h.changed_at,
                'stamp': fields.Datetime.to_string(h.changed_at),
                'kind': 'bank',
                'icon': 'creditCard',
                'title': 'Bank account updated',
                'detail': detail,
                **self._actor(h.changed_by),
            })
        return out

    def _approval_items(self, emp):
        if 'biz.approval.step.log' not in self.env:
            return []
        Log = self.env['biz.approval.step.log'].sudo()
        out = []
        for model_name, label, icon in _APPROVAL_SOURCES:
            if model_name not in self.env:
                continue
            Model = self.env[model_name].sudo()
            if 'employee_id' not in Model._fields:
                continue
            rec_ids = Model.search([('employee_id', '=', emp.id)]).ids
            if not rec_ids:
                continue
            for log in Log.search([('res_model', '=', model_name),
                                   ('res_id', 'in', rec_ids)]):
                out.append({
                    '_dt': log.stamp,
                    'stamp': fields.Datetime.to_string(log.stamp),
                    'kind': 'approval',
                    'icon': icon,
                    'title': '%s: %s' % (
                        label, self._humanize_state(log.to_state)),
                    'detail': (log.note or '') or (
                        '%s → %s' % (self._humanize_state(log.from_state),
                                     self._humanize_state(log.to_state))),
                    **self._actor(log.user_id),
                })
        return out

    def _contract_items(self, emp):
        out = []
        for c in emp.contract_ids.sudo():
            if not c.create_date:
                continue
            out.append({
                '_dt': c.create_date,
                'stamp': fields.Datetime.to_string(c.create_date),
                'kind': 'contract',
                'icon': 'briefcase',
                'title': 'Contract created',
                'detail': c.name or '',
                **self._actor(c.create_uid),
            })
        return out
