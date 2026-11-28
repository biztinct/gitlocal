# -*- coding: utf-8 -*-
"""People list › Table (FS-4): the columns, the page values, the Excel file.

The cards are untouched: the same `get_roster_page`, the same rows. Only when
the browser asks for the table (`context.pbfl_table`) does each row also
carry `pbfs` — the custom-field cells of that page, from the engine.
"""
from datetime import date

from odoo import api, models

from .list_columns import money_format, to_date

MODEL = 'hr.employee'
#: R23 — the field behind each standard column (its heading follows the
#: field's own label; `state` and `ready` are worked out, not one field).
COLUMN_FIELDS = {'name': 'name', 'dept': 'department_id', 'date_end': 'contract_date_end',
                 'wage': 'wage', 'job': 'job_id', 'manager': 'parent_id', 'email': 'work_email',
                 'join_date': 'date_of_joining', 'date_start': 'contract_date_start'}


class PbPeopleLists(models.AbstractModel):
    _inherit = 'pb.people'

    # ---------------------------------------------------------- columns
    def _pbf_columns(self):
        _ = self.env._
        cols = [
            # what the card shows today, in the card's order
            {'key': 'name', 'label': _('Name'), 'kind': 'person', 'pin': True, 'sub': 'job',
             'sort': {'asc': 'name', 'desc': 'name_desc'}},
            {'key': 'dept', 'label': _('Department'), 'kind': 'text'},
            {'key': 'state', 'label': _('Contract'), 'kind': 'badge', 'field': 'state_label'},
            {'key': 'date_end', 'label': _('Contract ends'), 'kind': 'date',
             'help': _('Marked when a running contract ends within 30 days.')},
            {'key': 'wage', 'label': _('Monthly wage'), 'kind': 'money', 'align': 'right'},
            {'key': 'ready', 'label': _('Payroll-ready'), 'kind': 'flag',
             'help': _('Ready means a running contract and bank details on file.')},
            # more, off until somebody switches them on
            {'key': 'job', 'label': _('Job'), 'kind': 'text', 'default': False},
            {'key': 'manager', 'label': _('Manager'), 'kind': 'text', 'default': False},
            {'key': 'email', 'label': _('Work email'), 'kind': 'text', 'default': False},
            {'key': 'join_date', 'label': _('Joined'), 'kind': 'date', 'default': False,
             'sort': {'asc': 'longest', 'desc': 'newest'}},
            {'key': 'date_start', 'label': _('Contract start'), 'kind': 'date', 'default': False},
        ]
        Lists = self.env['pb.form.studio.lists']
        return Lists._pbfl_std_columns(MODEL, cols, COLUMN_FIELDS) + Lists._pbfl_columns(MODEL)

    def _pbf_export_name(self):
        return self.env._('Employees')

    # ------------------------------------------------------------- page
    @api.model
    def get_roster_page(self, *args, **kwargs):
        res = super().get_roster_page(*args, **kwargs)
        if self.env.context.get('pbfl_table') and isinstance(res, dict):
            self.env['pb.form.studio.lists']._pbfl_attach(res.get('rows') or [], MODEL)
        return res

    # ------------------------------------------------------------ Excel
    @api.model
    def _pbfl_ready_text(self, row):
        _ = self.env._
        if row.get('ready'):
            return _('Ready')
        return _('No running contract') if row.get('bank') else _('No bank details')

    def _pbf_table_rows(self, records, keys):
        today = date.today()
        month_start = today.replace(day=1)
        pay_signs = {}
        custom = self.env['pb.form.studio.lists']._pbfl_cells(records, keys)
        out = {}
        for emp in records:
            try:
                row = self._roster_row(emp, today, month_start, pay_signs)
            except Exception:                           # noqa: BLE001 — as the cards do
                continue
            cells = {
                'name': row['name'],
                'dept': row['dept'],
                'state': row['state_label'],
                'date_end': to_date(row['date_end']),
                'wage': {'v': row['wage'], 'fmt': money_format(row['currency'])}
                if row['wage'] else None,
                'ready': self._pbfl_ready_text(row),
                'job': row['job'] if row['job'] != '—' else None,
                'manager': row['manager'] or None,
                'email': row['email'] or None,
                'join_date': to_date(row['join_date']),
                'date_start': to_date(row['date_start']),
            }
            cells.update(custom.get(emp.id) or {})
            out[emp.id] = cells
        return out
