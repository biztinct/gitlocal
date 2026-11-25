# -*- coding: utf-8 -*-
"""NEWHIRE P3a — what the new person was asked for (handover §2.6).

One row per item HR chose "Ask <first name>" for in step 5, created when the
hire is APPROVED (the `asks` welcome leg). P3a sends nothing: P3b's welcome
email, `/my/welcome` page, reminders and the New joiners chip read these rows
through ONE reader, `summary(employee)`.

The state is never set by a click. `refresh()` works it out from the
product's own data, every time it is asked:

    done     the value is on the record (or the paper is in the documents)
    waiting  the person sent it and it waits for HR (an open request of the
             product's own approval flows: profile change, detail / tax
             request, bank change)
    open     nothing yet

`refresh()` only READS the product; the one thing it writes is the ask row's
own `state` / `done_on` (sudo, so a reader with read-only rights may call it).
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

STATES = [
    ('open', 'Waiting for them'),
    ('waiting', 'Sent, waiting for HR'),
    ('done', 'Done'),
]

#: key → the hr.employee fields that make it "done" (all of them set).
FIELD_DONE = {
    'personal': ('private_phone', 'private_street'),
    'emergency': ('emergency_contact', 'emergency_phone'),
    'id_number': ('identification_id',),
}

#: The tax kinds a new person may be asked for (pb_me_tax KINDS_BY_COUNTRY).
TAX_KEYS = ('tax_number', 'tax_status', 'tax_regime', 'tax_fund')


class PbNewHireAsk(models.Model):
    _name = 'pb.new.hire.ask'
    _description = 'What a new person was asked to give'
    _order = 'employee_id, sequence, id'

    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade', index=True)
    key = fields.Char(required=True)
    label = fields.Char(required=True)
    need = fields.Selection([('first_pay', 'Needed before first pay'),
                             ('joining', 'Asked at joining'),
                             ('optional', 'Optional')], default='optional', required=True)
    url = fields.Char(string='Where they give it')
    sequence = fields.Integer(default=10)
    state = fields.Selection(STATES, default='open', required=True, index=True)
    done_on = fields.Datetime(readonly=True)
    category_id = fields.Many2one('pb.employee.document.category', string='Paper',
                                  ondelete='set null')
    company_id = fields.Many2one('res.company', index=True)
    proposal_id = fields.Many2one('pb.newhire.proposal', string='New hire request',
                                  ondelete='set null')

    _one_ask = models.UniqueIndex('(employee_id, key)', 'Each thing is asked for once.')

    # ================================================================ refresh
    def _open_requests(self, employee):
        """The open requests of this person in the product's own flows,
        read once for every row of that person."""
        env = self.env
        out = {'profile': False, 'detail': set(), 'bank': False}
        if 'pb.profile.change.request' in env:
            out['profile'] = bool(env['pb.profile.change.request'].sudo().search_count(
                [('employee_id', '=', employee.id), ('state', '=', 'hr_review')], limit=1))
        if 'pb.me.detail.request' in env:
            rows = env['pb.me.detail.request'].sudo().search(
                [('employee_id', '=', employee.id), ('state', '=', 'hr_review')])
            out['detail'] = set(rows.mapped('kind'))
        if 'pb.bank.change.request' in env:
            out['bank'] = bool(env['pb.bank.change.request'].sudo().search_count(
                [('employee_id', '=', employee.id),
                 ('state', 'in', ('hr_review', 'finance_review'))], limit=1))
        return out

    def _has_paper(self, employee, category):
        return bool(self.env['pb.employee.document'].sudo().search_count(
            [('employee_id', '=', employee.id), ('category_id', '=', category.id)], limit=1))

    def _tax_field(self, employee):
        """The employee field a tax kind of this person is kept in."""
        try:
            from odoo.addons.pb_me_tax.models.tax_rules import CHOICE_FIELD, NUMBER_FIELD
        except ImportError:
            return {}
        code = employee.payroll_country or ''
        return {
            'tax_number': NUMBER_FIELD.get(code),
            'tax_status': CHOICE_FIELD.get(('tax_status', code)),
            'tax_regime': CHOICE_FIELD.get(('tax_regime', code)),
            'tax_fund': CHOICE_FIELD.get(('tax_fund', code)),
        }

    def _state_of(self, row, employee, open_req, tax_fields):
        emp = employee
        key = row.key

        def filled(*names):
            return all(n in emp._fields and emp[n] for n in names)

        if key in ('personal', 'emergency'):
            if filled(*FIELD_DONE[key]):
                return 'done'
            return 'waiting' if open_req['profile'] else 'open'
        if key == 'id_number':
            done = filled('identification_id')
            if done and row.category_id:
                done = self._has_paper(emp, row.category_id)
            if done:
                return 'done'
            return 'waiting' if 'id_paper' in open_req['detail'] else 'open'
        if key in TAX_KEYS:
            field = tax_fields.get(key)
            done = bool(field) and filled(field)
            if done and row.category_id:
                done = self._has_paper(emp, row.category_id)
            if done:
                return 'done'
            return 'waiting' if key in open_req['detail'] else 'open'
        if key == 'bank':
            if 'pb_bank_on_record' in emp._fields and emp.pb_bank_on_record:
                return 'done'
            return 'waiting' if open_req['bank'] else 'open'
        if row.category_id:                     # a paper
            return 'done' if self._has_paper(emp, row.category_id) else 'open'
        return row.state or 'open'

    def refresh(self):
        """Work out each row's state from the product's data. Cheap and
        idempotent; writes only rows whose state moved."""
        now = fields.Datetime.now()
        for employee in self.mapped('employee_id'):
            emp = employee.sudo()
            # computed, unstored answers (bank on record) are read fresh
            emp.invalidate_recordset()
            open_req = self._open_requests(emp)
            tax_fields = self._tax_field(emp)
            for row in self.filtered(lambda r: r.employee_id == employee):
                state = self._state_of(row, emp, open_req, tax_fields)
                if state != row.state:
                    row.sudo().write({'state': state,
                                      'done_on': now if state == 'done' else False})
        return True

    # ================================================================ the reader
    @api.model
    def summary(self, employee):
        """THE reader of what a new person was asked (P3b's page, home row,
        board chip and reminders): `{total, done, waiting, open, items:[{key,
        label, state, need, url}]}`, refreshed first."""
        employee = employee if hasattr(employee, '_name') else \
            self.env['hr.employee'].browse(int(employee or 0))
        rows = self.sudo().search([('employee_id', '=', employee.id)])
        rows.refresh()
        items = [{'key': r.key, 'label': r.label, 'state': r.state, 'need': r.need,
                  'url': r.url or ''} for r in rows]
        count = {s: sum(1 for i in items if i['state'] == s) for s, _l in STATES}
        return {'total': len(items), 'done': count['done'], 'waiting': count['waiting'],
                'open': count['open'], 'items': items}
