# -*- coding: utf-8 -*-
"""Where the rows of a PDF come from — always the report's own table, read
AS THE PERSON PRINTING (DOCSTUDIO contract C1, `_pbxl_table`).

* A built report (`pb.report.definition`, pb_report_builder): its C1 table
  plus what the screen knows about groups and totals (`_pbrb_table`, the
  same call `_pbxl_table` makes, kept whole), so the PDF can print group
  headings, subtotals and the grand total exactly as on screen.
* A saved Explorer view (`pb.explorer.view`): its `_pbxl_table` lives in
  pb_excel_layout; when that module is absent the same wrapper is built here
  from the Explorer's own download rows (`pb.explorer._export_rows`).
* Any other model that implements `_pbxl_table` (the contract): its table,
  plain.

Nothing here reads with superuser rights: the table is the source's answer
for `self.env.user`.
"""
import logging

from odoo import api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

REPORT = 'pb.report.definition'
VIEW = 'pb.explorer.view'


class PbReportPdf(models.AbstractModel):
    _name = 'pb.report.pdf'
    _description = 'Report PDF designer'

    # ============================================================ the source
    @api.model
    def _pbrp_gone(self):
        return UserError(self.env._("This report is no longer available. It may have been "
                                    "deleted, or it is no longer shared with you."))

    @api.model
    def _pbrp_source(self, source_model, source_id):
        """The report record, checked for the reader. Refuses (in words) a
        model that cannot hand over a table, and anything the reader may not
        open."""
        if not isinstance(source_model, str) or source_model not in self.env:
            raise self._pbrp_gone()
        Model = self.env[source_model]
        if Model._abstract or Model._transient:
            raise self._pbrp_gone()
        if not (hasattr(Model, '_pbxl_table') or source_model == VIEW):
            raise UserError(self.env._("This screen cannot be printed as a PDF."))
        try:
            rec = Model.browse(int(source_id or 0)).exists()
        except (TypeError, ValueError):
            rec = Model.browse()
        if not rec:
            raise self._pbrp_gone()
        if hasattr(rec, '_pbxl_require'):
            rec._pbxl_require()              # the source's own gate (AccessError)
        elif source_model == VIEW:
            self.env['pb.explorer']._require()
        elif source_model == REPORT and 'pb.report.builder' in self.env:
            self.env['pb.report.builder']._require()
        try:
            rec.check_access('read')
        except AccessError:
            raise self._pbrp_gone() from None
        return rec

    @api.model
    def _pbrp_owner(self, rec):
        user = rec['user_id'] if 'user_id' in rec._fields else None
        return user if user and user._name == 'res.users' else self.env['res.users']

    @api.model
    def _pbrp_name(self, rec):
        return (rec.display_name or '').strip() or self.env._("Report")

    # ============================================================ the table
    @api.model
    def _pbrp_table(self, rec):
        """{title, columns, rows, truncated, note, groups, group_only,
        totals, summary, sub} — the C1 table plus what this module may know
        about groups and totals. Read as the reader."""
        if rec._name == REPORT and 'pb.report.builder' in self.env:
            return self._pbrp_table_report(rec)
        if hasattr(rec, '_pbxl_table'):
            table = rec._pbxl_table()
            out = self._pbrp_plain(table)
            if rec._name == VIEW:
                out['sub'] = self._pbrp_view_words(rec)
            return out
        if rec._name == VIEW:
            return self._pbrp_table_view(rec)
        raise UserError(self.env._("This screen cannot be printed as a PDF."))

    @api.model
    def _pbrp_plain(self, table):
        return {
            'title': str(table.get('title') or ''),
            'columns': list(table.get('columns') or []),
            'rows': list(table.get('rows') or []),
            'truncated': bool(table.get('truncated')),
            'note': str(table.get('note') or ''),
            'groups': [], 'group_only': [], 'totals': None, 'summary': False, 'sub': '',
        }

    @api.model
    def _pbrp_table_report(self, rec):
        builder = self.env['pb.report.builder']
        builder._require()
        rec.check_access('read')
        spec = dict(rec.spec or {}, subject=rec.subject)
        table = builder._pbrb_table(spec, title=rec.name, strict=False)
        out = self._pbrp_plain(table)
        try:
            clean, subject, cols, _notes = builder._clean_spec(spec, strict=False)
        except (UserError, AccessError):
            return out
        out['sub'] = self._pbrp_report_words(builder, clean, subject, cols)
        if table.get('_summary'):
            out['summary'] = True
            totals = {'__count': 'sum'}
            totals.update({k: how for k, how in clean['totals'].items()})
            out['totals'] = totals
            return out
        out['groups'] = [k for k in clean['group_by'] if k in (table.get('_keys') or [])]
        out['group_only'] = [k for k in clean['group_by'] if k not in clean['columns']]
        out['totals'] = dict(table.get('_totals') or {})
        return out

    @api.model
    def _pbrp_report_words(self, builder, clean, subject, cols):
        """The default second line: the period and the filters, in the
        builder's own words ("This year, by First day · Status is Approved")."""
        _ = self.env._
        words = []
        period = clean.get('period') or {}
        preset = period.get('preset') or 'any'
        if preset != 'any':
            if preset == 'custom':
                start = builder._display({'kind': 'date'}, period.get('from')) \
                    if period.get('from') else '…'
                end = builder._display({'kind': 'date'}, period.get('to')) \
                    if period.get('to') else '…'
                text = _("%(start)s to %(end)s", start=start, end=end)
            else:
                text = {p['key']: p['label'] for p in builder._presets()}.get(preset, '')
            date_label = next((lab for key, _path, lab, _x in subject.get('dates') or []
                               if key == period.get('date')), '')
            if text and date_label:
                text = _("%(period)s, by %(date)s", period=text, date=date_label)
            if text:
                words.append(text)
        try:
            words += builder._filter_words(clean, cols)
        except Exception:                                    # noqa: BLE001
            _logger.debug('pb_report_pdf: filter words skipped', exc_info=True)
        return ' · '.join(w for w in words if w)

    @api.model
    def _pbrp_view_words(self, view):
        try:
            return view._pbx_period_label() or ''
        except Exception:                                    # noqa: BLE001
            return ''

    @api.model
    def _pbrp_table_view(self, view):
        """The Explorer view's table when pb_excel_layout (which carries its
        `_pbxl_table`) is not installed: the same flat wrapper over the
        Explorer's own download rows, as the reader."""
        explorer = self.env['pb.explorer']
        explorer._require()
        view.check_access('read')
        ex = explorer._export_rows(view._pbx_spec_now())
        payload = ex['payload']
        _ = explorer.env._
        kind = 'money' if payload.get('measure_kind', 'money') == 'money' else 'number'
        blocks = ex['blocks']
        fallback_money = (payload.get('currency') or {}).get('name') or ''
        cats = []
        for block in blocks:
            for label in block['head'][1:-1]:
                if label not in cats:
                    cats.append(label)
        columns = [{'key': 'name', 'type': 'text',
                    'label': payload.get('dimension_label') or _("Name")}]
        if kind == 'money':
            columns.append({'key': 'currency', 'type': 'text', 'label': _("Currency")})
        columns += [{'key': 'c%d' % i, 'label': str(label), 'type': kind}
                    for i, label in enumerate(cats, start=1)]
        columns.append({'key': 'total', 'type': kind, 'label': _("Total")})
        rows = []
        for block in blocks:
            heads = block['head'][1:-1]
            for row in block['rows']:
                values = dict(zip(heads, row[1:-1]))
                line = [row[0]]
                if kind == 'money':
                    line.append(block.get('currency_name') or fallback_money)
                line += [_number(values.get(label)) for label in cats]
                line.append(_number(row[-1]))
                rows.append(line)
        note = ''
        if ex['truncated']:
            note = _("Only the largest rows are included; %(more)s more were left out.",
                     more='{:,}'.format(ex['truncated']))
        out = self._pbrp_plain({'title': view.name or '', 'columns': columns, 'rows': rows,
                                'truncated': bool(ex['truncated']), 'note': note})
        out['sub'] = self._pbrp_view_words(view)
        return out


def _number(value):
    if value is None or isinstance(value, bool):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return value
