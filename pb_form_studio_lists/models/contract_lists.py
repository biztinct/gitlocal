# -*- coding: utf-8 -*-
"""Contracts board › Table (FS-4): the columns, the page values, the Excel file.

Same pattern as People: the board's own page call, plus the custom-field
cells of the page when the browser asks for the table.
"""
from datetime import date

from odoo import api, models

from .list_columns import money_format, to_date

MODEL = 'hr.contract'


class PbContractsLists(models.AbstractModel):
    _inherit = 'pb.contracts'

    # ---------------------------------------------------------- columns
    def _pbf_columns(self):
        _ = self.env._
        cols = [
            # what the card shows today, in the card's order
            {'key': 'employee', 'label': _('Person'), 'kind': 'person', 'pin': True, 'sub': 'name',
             'sort': {'asc': 'person'}},
            {'key': 'structure', 'label': _('Pay structure'), 'kind': 'text'},
            {'key': 'date_start', 'label': _('Starts'), 'kind': 'date',
             'sort': {'asc': 'oldest', 'desc': 'newest'}},
            {'key': 'date_end', 'label': _('Ends'), 'kind': 'date', 'sort': {'asc': 'ending'},
             'help': _('Marked when a contract ends within 30 days.')},
            {'key': 'state', 'label': _('Status'), 'kind': 'badge', 'field': 'state_label'},
            {'key': 'wage', 'label': _('Monthly wage'), 'kind': 'money', 'align': 'right',
             'sort': {'desc': 'wage'}},
        ]
        if self._safe(self._fillin_ready, default=False):
            cols.append({'key': 'fillin', 'label': _('Answers to check'), 'kind': 'count',
                         'help': _('Answers Payobook filled in by itself that nobody has '
                                   'checked yet.')})
        cols.append({'key': 'name', 'label': _('Contract reference'), 'kind': 'text',
                     'default': False})
        return cols + self.env['pb.form.studio.lists']._pbfl_columns(MODEL)

    def _pbf_export_name(self):
        return self.env._('Contracts')

    # ------------------------------------------------------------- page
    @api.model
    def get_contracts_page(self, *args, **kwargs):
        res = super().get_contracts_page(*args, **kwargs)
        if self.env.context.get('pbfl_table') and isinstance(res, dict):
            self.env['pb.form.studio.lists']._pbfl_attach(res.get('rows') or [], MODEL)
        return res

    # ------------------------------------------------------------ Excel
    def _pbf_table_rows(self, records, keys):
        today = date.today()
        pay_signs = {}
        fillin = {}
        if 'fillin' in keys:
            fillin = self._safe(lambda: self._fillin_rows(records), default={}) or {}
        custom = self.env['pb.form.studio.lists']._pbfl_cells(records, keys)
        company_sign = self.env.company.currency_id.symbol or ''
        out = {}
        for con in records:
            try:
                row = self._contract_row(con, today, pay_signs)
            except Exception:                           # noqa: BLE001 — as the cards do
                continue
            n = (fillin.get(con.id) or {}).get('n') or 0
            cells = {
                'employee': row['employee'],
                'structure': row['structure'] or None,
                'date_start': to_date(row['date_start']),
                'date_end': to_date(row['date_end']),
                'state': row['state_label'],
                'wage': {'v': row['wage'],
                         'fmt': money_format(row['currency'] or company_sign)}
                if row['wage'] else None,
                'fillin': n or None,
                'name': row['name'] if row['name'] != '—' else None,
            }
            cells.update(custom.get(con.id) or {})
            out[con.id] = cells
        return out
