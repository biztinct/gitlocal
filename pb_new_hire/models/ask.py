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

from odoo import _, api, fields, models

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

#: The joining checklist step the asks finish (pb_onboarding's template).
DETAILS_STEP = 'pb_onboarding.step_rize_data'

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
    def _open_requests(self, employees):
        """`{employee id: {profile, detail:set(kinds), bank}}` — the open
        requests of these people in the product's own flows, ONE search per
        flow for all of them (P3b: the New joiners board reads many people)."""
        env = self.env
        ids = employees.ids
        out = {i: {'profile': False, 'detail': set(), 'bank': False} for i in ids}
        if not ids:
            return out
        if 'pb.profile.change.request' in env:
            for row in env['pb.profile.change.request'].sudo().search_read(
                    [('employee_id', 'in', ids), ('state', '=', 'hr_review')], ['employee_id']):
                out[row['employee_id'][0]]['profile'] = True
        if 'pb.me.detail.request' in env:
            for row in env['pb.me.detail.request'].sudo().search_read(
                    [('employee_id', 'in', ids), ('state', '=', 'hr_review')], ['employee_id', 'kind']):
                out[row['employee_id'][0]]['detail'].add(row['kind'])
        if 'pb.bank.change.request' in env:
            for row in env['pb.bank.change.request'].sudo().search_read(
                    [('employee_id', 'in', ids),
                     ('state', 'in', ('hr_review', 'finance_review'))], ['employee_id']):
                out[row['employee_id'][0]]['bank'] = True
        return out

    def _papers(self, employees, categories):
        """`{(employee id, category id)}` of the papers these people have."""
        if not employees or not categories:
            return set()
        rows = self.env['pb.employee.document'].sudo().search_read(
            [('employee_id', 'in', employees.ids), ('category_id', 'in', categories.ids)],
            ['employee_id', 'category_id'])
        return {(r['employee_id'][0], r['category_id'][0]) for r in rows}

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

    def _state_of(self, row, employee, open_req, tax_fields, papers):
        emp = employee
        key = row.key

        def filled(*names):
            return all(n in emp._fields and emp[n] for n in names)

        def has_paper(category):
            return (emp.id, category.id) in papers

        if key in ('personal', 'emergency'):
            if filled(*FIELD_DONE[key]):
                return 'done'
            return 'waiting' if open_req['profile'] else 'open'
        if key == 'id_number':
            done = filled('identification_id')
            if done and row.category_id:
                done = has_paper(row.category_id)
            if done:
                return 'done'
            return 'waiting' if 'id_paper' in open_req['detail'] else 'open'
        if key in TAX_KEYS:
            field = tax_fields.get(key)
            done = bool(field) and filled(field)
            if done and row.category_id:
                done = has_paper(row.category_id)
            if done:
                return 'done'
            return 'waiting' if key in open_req['detail'] else 'open'
        if key == 'bank':
            if 'pb_bank_on_record' in emp._fields and emp.pb_bank_on_record:
                return 'done'
            return 'waiting' if open_req['bank'] else 'open'
        if row.category_id:                     # a paper
            return 'done' if has_paper(row.category_id) else 'open'
        return row.state or 'open'

    def refresh(self):
        """Work out each row's state from the product's data. Cheap,
        idempotent and batched: a fixed number of reads whatever the number
        of people; writes only rows whose state moved (one write per new
        state)."""
        rows = self.sudo()
        employees = rows.mapped('employee_id')
        if not employees:
            return True
        # computed, unstored answers (bank on record) are read fresh (NH35)
        employees.invalidate_recordset()
        open_req = self._open_requests(employees)
        papers = self._papers(employees, rows.mapped('category_id'))
        moved = {}
        for employee in employees:
            tax_fields = self._tax_field(employee)
            for row in rows.filtered(lambda r: r.employee_id == employee):
                state = self._state_of(row, employee, open_req[employee.id], tax_fields, papers)
                if state != row.state:
                    moved.setdefault(state, self.browse())
                    moved[state] |= row
        now = fields.Datetime.now()
        for state, changed in moved.items():
            changed.sudo().write({'state': state, 'done_on': now if state == 'done' else False})
        return True

    # ================================================================ the reader
    @api.model
    def _shape(self, rows):
        items = [{'key': r.key, 'label': r.label, 'state': r.state, 'need': r.need,
                  'url': r.url or ''} for r in rows]
        count = {s: sum(1 for i in items if i['state'] == s) for s, _l in STATES}
        return {'total': len(items), 'done': count['done'], 'waiting': count['waiting'],
                'open': count['open'], 'items': items}

    @api.model
    def summaries(self, employees):
        """`{employee id: summary}` for many people at once (one refresh)."""
        employees = employees.sudo()
        rows = self.sudo().search([('employee_id', 'in', employees.ids)])
        rows.refresh()
        out = {}
        for employee in employees:
            mine = rows.filtered(lambda r: r.employee_id == employee)
            out[employee.id] = self._shape(mine)
            if mine and not out[employee.id]['open'] and not out[employee.id]['waiting']:
                self._tick_details_step(employee)
        return out

    @api.model
    def summary(self, employee):
        """THE reader of what a new person was asked (P3b's page, home row,
        board chip and reminders): `{total, done, waiting, open, items:[{key,
        label, state, need, url}]}`, refreshed first. When everything is done
        the joining checklist's "Finish your own details" step ticks itself."""
        employee = employee if hasattr(employee, '_name') else \
            self.env['hr.employee'].browse(int(employee or 0))
        return self.summaries(employee)[employee.id] if employee else self._shape(self.browse())

    # ================================================================ the checklist
    @api.model
    def _tick_details_step(self, employee):
        """Tick "Finish your own details" (`pb_onboarding.step_rize_data`) on
        this person's running joining checklist — once (`nh_details_ticked`),
        and only a step still open."""
        emp = employee.sudo()
        if 'nh_details_ticked' not in emp._fields or emp.nh_details_ticked \
                or 'pb.journey.task' not in self.env:
            return False
        step = self.env.ref(DETAILS_STEP, raise_if_not_found=False)
        if not step:
            return False
        tasks = self.env['pb.journey.task'].sudo().search([
            ('employee_id', '=', emp.id), ('step_id', '=', step.id),
            ('state', 'in', ('pending', 'in_progress', 'blocked')),
            ('case_id.state', 'not in', ('cancelled', 'done'))])
        if not tasks:
            return False
        tasks.action_done(payload={'note': _("Ticked when the joining details were finished.")})
        emp.write({'nh_details_ticked': True})
        return True
