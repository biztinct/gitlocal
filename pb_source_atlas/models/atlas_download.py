# -*- coding: utf-8 -*-
"""Per-lane spreadsheet downloads for the Source Atlas.

Same mechanism the payslip batch export has always used
(``om_hr_payroll/models/hr_payslip.py`` — build with ``xlsxwriter``, park it on
an ``ir.attachment``, return an ``ir.actions.act_url``): a controller would need
its own access story, and this one already ran through ``_atlas_gate``.

Every workbook says what it left out. A row or column cap that silences itself is
the same bug as a formula that silently returns zero (C7), so the caps land on a
"How to read this" sheet along with the run, the lane and when it was made.
"""

import base64
import io
import re
from collections import OrderedDict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pb_source_atlas import (
    LANE_BY_KEY, LANE_KEYS, _RAW_LANES, _XLSX_COL_CAP, _XLSX_ROW_CAP,
)

_ILLEGAL_SHEET = re.compile(r"[\[\]:*?/\\]")


def _sheet_name(raw, used):
    """A legal, unique worksheet name. Excel allows 31 chars and forbids []:*?/\\."""
    name = _ILLEGAL_SHEET.sub(' ', (raw or 'Sheet').strip()) or 'Sheet'
    name = name[:31]
    candidate, n = name, 1
    while candidate.lower() in used:
        suffix = ' (%d)' % n
        candidate = name[:31 - len(suffix)] + suffix
        n += 1
    used.add(candidate.lower())
    return candidate


class PbSourceAtlasDownload(models.AbstractModel):
    _inherit = 'pb.source.atlas'

    # ==================================================================
    @api.model
    def download_lane(self, run_id, lane='matrix'):
        """Build one lane's workbook and hand back a download action."""
        self._atlas_gate()
        run = self._atlas_run(run_id)
        lane = (lane or 'matrix').strip()
        if lane not in LANE_KEYS and lane not in ('matrix', 'all'):
            raise UserError(_("There is no '%s' source lane to download.", lane))
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_(
                "Spreadsheet export needs the 'xlsxwriter' library, which is "
                "not available on this server."))

        rows = self._atlas_slip_rows(run, with_values=True)
        if not rows:
            raise UserError(_(
                "This pay run has no payslips yet, so there is nothing to export."))

        components = self._atlas_components({row[2] for row in rows})
        employees = self.env['hr.employee'].browse(
            [row[1] for row in rows if row[1]])
        by_employee = {e.id: e for e in employees.exists()}

        notes = []
        capped_rows = rows
        if len(rows) > _XLSX_ROW_CAP:
            capped_rows = rows[:_XLSX_ROW_CAP]
            notes.append(_(
                "Only the first %(cap)s of %(total)s employees are included.",
                cap=_XLSX_ROW_CAP, total=len(rows)))

        cells = self._atlas_cells(capped_rows, components)
        wanted = self._atlas_lane_codes(cells, components, lane)
        if not wanted:
            raise UserError(_(
                "Nothing in this pay run came from %(lane)s, so there is nothing "
                "to export.", lane=self._atlas_lane_label(lane)))
        if len(wanted) > _XLSX_COL_CAP:
            notes.append(_(
                "Only the first %(cap)s of %(total)s components are included.",
                cap=_XLSX_COL_CAP, total=len(wanted)))
            wanted = wanted[:_XLSX_COL_CAP]

        output = io.BytesIO()
        book = xlsxwriter.Workbook(output, {'in_memory': True})
        fmt = {
            'head': book.add_format({'bold': True, 'bg_color': '#EDEAF8',
                                     'border': 1, 'valign': 'vcenter',
                                     'text_wrap': True}),
            'text': book.add_format({'border': 1}),
            'num': book.add_format({'border': 1, 'num_format': '#,##0.00'}),
            'title': book.add_format({'bold': True, 'font_size': 13}),
            'muted': book.add_format({'font_color': '#64748B'}),
        }
        used = set()

        self._atlas_sheet_values(book, fmt, used, capped_rows, by_employee,
                                 components, wanted, cells)
        self._atlas_sheet_sources(book, fmt, used, capped_rows, by_employee,
                                  wanted, cells)
        raw_lanes = _RAW_LANES if lane in ('matrix', 'all') else (
            (lane,) if lane in _RAW_LANES else ())
        for raw_lane in raw_lanes:
            self._atlas_sheet_raw(book, fmt, used, run, raw_lane, notes)
        self._atlas_sheet_notes(book, fmt, used, run, lane, wanted, capped_rows,
                                notes)
        book.close()
        output.seek(0)

        filename = '%s — %s.xlsx' % (run.name or _('Pay run'),
                                     self._atlas_lane_label(lane))
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(output.getvalue()),
            'type': 'binary',
            'res_model': 'hr.payslip.run',
            'res_id': run.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    # ==================================================================
    # shared shaping
    # ==================================================================
    @api.model
    def _atlas_lane_label(self, lane):
        if lane == 'matrix':
            return _('All sources')
        if lane == 'all':
            return _('Everything')
        return LANE_BY_KEY.get(lane, {}).get('label', lane)

    @api.model
    def _atlas_cells(self, rows, components):
        """``{slip_id: {CODE: (value, lane, key, via)}}`` — the same read the grid does."""
        out = OrderedDict()
        for slip_id, _emp, _cfg, raw_sources, raw_values, raw_computed in rows:
            sources = self._atlas_json(raw_sources)
            values = self._atlas_json(raw_values)
            computed = self._atlas_json(raw_computed)
            row = {}
            for key, component in components.items():
                code = component['code']
                entry = sources.get(code) or sources.get(key)
                if entry is not None:
                    lane = self._atlas_entry_lane(entry)
                    src_key = entry.get('key') if isinstance(entry, dict) else None
                    via = entry.get('via') if isinstance(entry, dict) else None
                else:
                    lane = self._atlas_declared_lane(component)
                    src_key, via = None, None
                    if not lane:
                        continue
                value = values.get(code, computed.get(code))
                if value is None and entry is None:
                    continue
                row[key] = (value, lane, src_key or '', via or '')
            out[slip_id] = row
        return out

    @api.model
    def _atlas_lane_codes(self, cells, components, lane):
        """The component keys this workbook covers, in scheme order."""
        present = set()
        for row in cells.values():
            for key, (_v, cell_lane, _k, _via) in row.items():
                if lane in ('matrix', 'all') or cell_lane == lane:
                    present.add(key)
        return [key for key, _c in sorted(
            components.items(), key=lambda kv: (kv[1]['sequence'], kv[1]['code']))
            if key in present]

    # ==================================================================
    # sheets
    # ==================================================================
    @api.model
    def _atlas_sheet_values(self, book, fmt, used, rows, by_employee, components,
                            wanted, cells):
        sheet = book.add_worksheet(_sheet_name(_('Values'), used))
        sheet.freeze_panes(1, 3)
        sheet.set_column(0, 0, 16)
        sheet.set_column(1, 1, 30)
        sheet.set_column(2, 2, 24)
        headers = [_('Employee code'), _('Employee'), _('Department')] + [
            '%s\n%s' % (components[key]['code'], components[key]['name'])
            for key in wanted]
        for col, head in enumerate(headers):
            sheet.write_string(0, col, head, fmt['head'])
        for index, (slip_id, employee_id, *_rest) in enumerate(rows, start=1):
            employee = by_employee.get(employee_id)
            sheet.write_string(index, 0, employee and employee.barcode or '', fmt['text'])
            sheet.write_string(index, 1, employee and employee.display_name or '', fmt['text'])
            sheet.write_string(index, 2,
                               employee and employee.department_id.display_name or '',
                               fmt['text'])
            row = cells.get(slip_id, {})
            for col, key in enumerate(wanted, start=3):
                cell = row.get(key)
                if not cell:
                    sheet.write_blank(index, col, None, fmt['text'])
                    continue
                self._atlas_write_value(sheet, index, col, cell[0], fmt,
                                        kind=components[key].get('kind'))

    @api.model
    def _atlas_sheet_sources(self, book, fmt, used, rows, by_employee, wanted,
                             cells):
        sheet = book.add_worksheet(_sheet_name(_('Sources'), used))
        sheet.freeze_panes(1, 2)
        sheet.set_column(0, 0, 16)
        sheet.set_column(1, 1, 30)
        headers = [_('Employee code'), _('Employee')] + list(wanted)
        for col, head in enumerate(headers):
            sheet.write_string(0, col, head, fmt['head'])
        for index, (slip_id, employee_id, *_rest) in enumerate(rows, start=1):
            employee = by_employee.get(employee_id)
            sheet.write_string(index, 0, employee and employee.barcode or '', fmt['text'])
            sheet.write_string(index, 1, employee and employee.display_name or '', fmt['text'])
            row = cells.get(slip_id, {})
            for col, key in enumerate(wanted, start=2):
                cell = row.get(key)
                if not cell:
                    sheet.write_blank(index, col, None, fmt['text'])
                    continue
                _value, lane, src_key, via = cell
                parts = [self._atlas_lane_label(lane)]
                if src_key:
                    parts.append(src_key)
                if via:
                    parts.append(via.replace('_', ' '))
                sheet.write_string(index, col, ' · '.join(parts), fmt['text'])

    @api.model
    def _atlas_sheet_raw(self, book, fmt, used, run, lane, notes):
        """The raw material itself — feed rows, or a workbook's imported rows."""
        batches = self._atlas_run_batches(run)
        if lane == 'excel':
            batches = batches.filtered(lambda b: b.source_type == 'excel')
        else:
            batches = batches.filtered(lambda b: b.source_type != 'excel')
        if not batches:
            notes.append(_(
                "No %(lane)s rows are attached to this pay run, so the raw sheet "
                "is not included.", lane=self._atlas_lane_label(lane)))
            return
        if lane == 'feed':
            self._atlas_sheet_feed_rows(book, fmt, used, batches, notes)
            return
        for batch in batches:
            lines = batch.import_line_ids.sorted(key=lambda l: (l.sequence, l.id))
            columns = []
            for line in lines:
                for key in (line.get_raw_data() or {}):
                    if key not in columns:
                        columns.append(key)
            if not columns:
                continue
            sheet = book.add_worksheet(_sheet_name(batch.name or _('Workbook'), used))
            sheet.set_column(0, 0, 10)
            sheet.set_column(1, 1, 30)
            for col, head in enumerate([_('Row'), _('Employee')] + columns):
                sheet.write_string(0, col, str(head), fmt['head'])
            for index, line in enumerate(lines[:_XLSX_ROW_CAP], start=1):
                raw = line.get_raw_data() or {}
                sheet.write_number(index, 0, line.sequence or index, fmt['num'])
                sheet.write_string(index, 1, line.employee_name or '', fmt['text'])
                for col, key in enumerate(columns, start=2):
                    self._atlas_write_value(sheet, index, col, raw.get(key), fmt)

    @api.model
    def _atlas_sheet_feed_rows(self, book, fmt, used, batches, notes):
        """One sheet per feed data type: the connected system's rows as delivered."""
        Store = self.env['hr.api.data.store'].sudo()
        records = Store.search([('import_batch_id', 'in', batches.ids)],
                               limit=_XLSX_ROW_CAP * 4)
        if not records:
            notes.append(_(
                "The connected system's own rows are no longer on file for this "
                "run, so only the imported values are exported."))
            return
        by_type = OrderedDict()
        for record in records:
            by_type.setdefault(record.data_type or 'data', []).append(record)
        for data_type, group in by_type.items():
            columns = []
            payloads = []
            for record in group[:_XLSX_ROW_CAP]:
                data = record.get_mappable_data() or {}
                payloads.append((record, data))
                for key in data:
                    if key not in columns:
                        columns.append(key)
            if len(columns) > _XLSX_COL_CAP:
                notes.append(_(
                    "The %(type)s feed carries %(n)s keys; the first %(cap)s are "
                    "exported.", type=data_type, n=len(columns), cap=_XLSX_COL_CAP))
                columns = columns[:_XLSX_COL_CAP]
            sheet = book.add_worksheet(
                _sheet_name(_('Feed · %s') % data_type, used))
            sheet.set_column(0, 0, 26)
            sheet.set_column(1, 1, 20)
            head = [_('External id'), _('Pulled'), _('Period'), _('State')] + columns
            for col, label in enumerate(head):
                sheet.write_string(0, col, str(label), fmt['head'])
            for index, (record, data) in enumerate(payloads, start=1):
                sheet.write_string(index, 0, record.employee_external_id or '', fmt['text'])
                sheet.write_string(index, 1, str(record.pull_date or ''), fmt['text'])
                sheet.write_string(index, 2, '%s – %s' % (
                    record.period_from or '', record.period_to or ''), fmt['text'])
                sheet.write_string(index, 3, record.state or '', fmt['text'])
                for col, key in enumerate(columns, start=4):
                    self._atlas_write_value(sheet, index, col, data.get(key), fmt)

    @api.model
    def _atlas_sheet_notes(self, book, fmt, used, run, lane, wanted, rows, notes):
        sheet = book.add_worksheet(_sheet_name(_('How to read this'), used))
        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 86)
        lines = [
            (_('Pay run'), run.name or ''),
            (_('Period'), '%s – %s' % (run.date_start or '', run.date_end or '')),
            (_('Source lane'), self._atlas_lane_label(lane)),
            (_('Employees'), str(len(rows))),
            (_('Components'), str(len(wanted))),
            (_('Prepared'), str(fields.Datetime.now())),
            ('', ''),
            (_('Values'), _("What each employee's component was worth in this run.")),
            (_('Sources'), _("The same grid, but each cell says where the value "
                             "came from: the lane, the key it arrived on, and why "
                             "that source won.")),
        ]
        for note in notes:
            lines.append((_('Note'), note))
        sheet.write_string(0, 0, _('Source Atlas export'), fmt['title'])
        for index, (label, value) in enumerate(lines, start=2):
            sheet.write_string(index, 0, str(label), fmt['head'] if label else fmt['muted'])
            sheet.write_string(index, 1, str(value), fmt['text'] if label else fmt['muted'])

    # ==================================================================
    @api.model
    def _atlas_run_batches(self, run):
        """The import batches behind this run.

        Two joins, because a batch may know its run (``payslip_run_id``) or only
        its payslips — the ABM June run is the second shape, and a lookup that
        only knew the first would have reported "no spreadsheet, no feed" about a
        run with 152 imported rows.
        """
        Batch = self.env['hr.payroll.import.batch'].sudo()
        Line = self.env['hr.payroll.import.line'].sudo()
        batches = Batch.search([('payslip_run_id', '=', run.id)])
        slip_ids = self.env['hr.payslip'].search(
            [('payslip_run_id', '=', run.id)]).ids
        if slip_ids:
            batches |= Line.search([('payslip_id', 'in', slip_ids)]).batch_id
        return batches

    @staticmethod
    def _atlas_write_value(sheet, row, col, value, fmt, kind=None):
        # VALUEKIND — an identifier goes in as a STRING even when it is all
        # digits, because `write_number` is how a bank account loses its leading
        # zeros the moment somebody opens the workbook. Same reason the grid
        # renders it verbatim.
        if kind in ('identifier', 'text', 'date', 'boolean') and \
                value is not None and value is not False:
            sheet.write_string(row, col, str(value)[:2000], fmt['text'])
            return
        if value is None or value is False:
            sheet.write_blank(row, col, None, fmt['text'])
        elif isinstance(value, bool):
            sheet.write_string(row, col, 'true' if value else 'false', fmt['text'])
        elif isinstance(value, (int, float)):
            sheet.write_number(row, col, float(value), fmt['num'])
        elif isinstance(value, (dict, list)):
            sheet.write_string(row, col, str(value)[:2000], fmt['text'])
        else:
            sheet.write_string(row, col, str(value)[:2000], fmt['text'])
