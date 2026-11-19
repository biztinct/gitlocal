# -*- coding: utf-8 -*-
"""Custom-field columns for the People list and the Contracts board (FS-4).

The ONLY way a Form-builder value reaches a table cell or the Excel file is
the engine's list helper (FS1_REPORT.md, THE HOST CONTRACT §6):
`pb.form.studio.fields_for(model, 'list')` decides WHICH fields (marked "Show
in lists", and only those the reader may see — the engine's own visibility,
not a plain `read`), and `_pbfs_values_for(records, 'list')` gives the
values, blank where a field does not apply to the record's Country of Work.
"""
from datetime import date

from odoo import api, fields, models

NUMERIC = ('integer', 'float', 'monetary')


class PbFormStudioLists(models.AbstractModel):
    _name = 'pb.form.studio.lists'
    _description = 'Form builder: list columns'

    @api.model
    def _pbfl_specs(self, model):
        return self.env['pb.form.studio'].fields_for(model, 'list')

    @api.model
    def _pbfl_columns(self, model):
        """Board columns for the custom fields of `model` the reader may see,
        marked "Show in lists" — shown by default, after the standard ones."""
        out = []
        for spec in self._pbfl_specs(model):
            out.append({
                'key': spec['name'],
                'label': spec['label'],
                'help': spec.get('help') or '',
                'kind': 'custom',
                'type': spec['type'],
                'custom': True,
                'default': True,
                'align': 'right' if spec['type'] in NUMERIC else 'left',
            })
        return out

    @api.model
    def _pbfl_prefetch(self, records, specs):
        """Read every custom column of `records` in ONE query.

        The ORM never prefetches manual fields (core `fields.py`, "prefetch
        only stored, column, non-manual fields"), so the engine's per-record
        read would cost one query per column per page. `fetch` loads them all
        at once into the cache the engine then reads from. Only names the
        engine already handed this reader (`fields_for`) are fetched."""
        names = [s['name'] for s in specs if s['name'] in records._fields
                 and records._fields[s['name']].column_type]
        if names and records:
            records.fetch(names)

    @api.model
    def _pbfl_attach(self, rows, model):
        """Add `pbfs: {field: display}` to each page row (one dict per id)."""
        specs = self._pbfl_specs(model) if rows else []
        if not specs:
            return rows
        records = self.env[model].browse([r['id'] for r in rows if r.get('id')])
        self._pbfl_prefetch(records, specs)
        values = self.env['pb.form.studio']._pbfs_values_for(records, 'list')
        for row in rows:
            cells = values.get(row.get('id')) or {}
            row['pbfs'] = {name: cell['display'] for name, cell in cells.items()}
        return rows

    @api.model
    def _pbfl_cells(self, records, keys):
        """`{id: {field: excel cell}}` for the custom keys asked for."""
        every = self._pbfl_specs(records._name)
        specs = {s['name']: s for s in every if s['name'] in keys}
        if not specs or not records:
            return {}
        # the engine reads every list field, so all of them come in one query
        self._pbfl_prefetch(records, every)
        values = self.env['pb.form.studio']._pbfs_values_for(records, 'list')
        out = {}
        for rec in records:
            row = {}
            for name, spec in specs.items():
                cell = (values.get(rec.id) or {}).get(name) or {}
                row[name] = self._pbfl_excel(spec, cell)
            out[rec.id] = row
        return out

    @api.model
    def _pbfl_excel(self, spec, cell):
        display = cell.get('display')
        if display in (None, ''):
            return None             # empty, or not for this record's country
        value = cell.get('value')
        t = spec['type']
        if t in NUMERIC and isinstance(value, (int, float)) and not isinstance(value, bool):
            return {'v': value, 'fmt': '#,##0' if t == 'integer' else '#,##0.##'}
        if t == 'boolean':
            return bool(value)
        if t == 'date' and value:
            try:
                return fields.Date.to_date(value)
            except (TypeError, ValueError):
                return display
        return display


def money_format(symbol):
    """An Excel number format that shows `symbol` before the amount."""
    sym = (symbol or '').replace('"', '')
    return ('"%s"#,##0' % sym) if sym else '#,##0'


def to_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return fields.Date.to_date(value)
    except (TypeError, ValueError):
        return None
