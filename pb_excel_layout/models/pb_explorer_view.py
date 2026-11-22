# -*- coding: utf-8 -*-
"""Contract C1 on the saved Explorer view: "a table of results".

The table is the Explorer's own download (`pb.explorer._export_rows`, the
rows the CSV and the Excel file are made of) for the view's stored question,
run as the CALLING user — so it carries only the companies and divisions that
person may see (rail R2). Where the Explorer's file has one block per
currency, this is ONE flat table: a layout has one table.

X-b (owner, 2026-11-22):
* EVERY row of the view, not the chart's largest 24 — up to the Explorer's
  own export cap (20,000), with a plain note when that is hit. Asked for
  through `pb.explorer._pbx_series_cap` with the context key
  `pbxl_every_row`, so the chart and the standard downloads are unchanged.
* A money report ALWAYS has a `Currency` column, second, in either money
  mode, so the columns never move; a count (headcount…) has none.
"""
from odoo import api, models

from odoo.addons.pb_explorer.models.pb_explorer import _EXPORT_CAP

EVERY_ROW = 'pbxl_every_row'


class PbExplorerView(models.Model):
    _inherit = 'pb.explorer.view'

    def _pbxl_require(self):
        """The source's own gate (the Explorer's), asked before anything."""
        self.env['pb.explorer']._require()

    def _pbxl_table(self):
        self.ensure_one()
        explorer = self.env['pb.explorer']
        explorer._require()
        self.check_access('read')
        return self._pbxl_table_for(explorer, self._pbx_spec_now())

    def _pbxl_table_for(self, explorer, spec):
        """The flat table for `spec`, read through `explorer` — the facade as
        the reader (a scheduled send passes the recipient's)."""
        self.ensure_one()
        explorer = explorer.with_context(**{EVERY_ROW: True})
        cap = explorer._pbx_series_cap()
        spec = dict(spec or {}, limit=cap)
        ex = explorer._export_rows(spec)
        payload = ex['payload']
        kind = 'money' if payload.get('measure_kind', 'money') == 'money' \
            else 'number'
        blocks = ex['blocks']
        # Every money report carries the Currency column, in the same place
        # in both money modes (owner, X-b); a count has none.
        with_currency = kind == 'money'
        fallback_money = (payload.get('currency') or {}).get('name') or ''
        # The time buckets of every block, in the order they first appear.
        cats = []
        for block in blocks:
            for label in block['head'][1:-1]:
                if label not in cats:
                    cats.append(label)
        env = explorer.env
        columns = [{'key': 'name', 'type': 'text',
                    'label': payload.get('dimension_label') or env._("Name")}]
        if with_currency:
            columns.append({'key': 'currency', 'type': 'text',
                            'label': env._("Currency")})
        columns += [{'key': 'c%d' % i, 'label': str(label), 'type': kind}
                    for i, label in enumerate(cats, start=1)]
        columns.append({'key': 'total', 'type': kind, 'label': env._("Total")})
        rows = []
        for block in blocks:
            heads = block['head'][1:-1]
            for row in block['rows']:
                values = dict(zip(heads, row[1:-1]))
                out = [row[0]]
                if with_currency:
                    out.append(block.get('currency_name') or fallback_money)
                out += [_num(values.get(label)) for label in cats]
                out.append(_num(row[-1]))
                rows.append(out)
        notes = []
        if ex['truncated']:
            notes.append(env._(
                "Only the largest %(shown)s rows are in the file; %(more)s "
                "more were left out.", shown='{:,}'.format(cap),
                more='{:,}'.format(ex['truncated'])))
        if ex['unconverted']:
            notes.append(env._(
                "%s amounts could not be converted (no exchange rate on file) "
                "and are not in the table.", len(ex['unconverted'])))
        return {
            'title': self.name or '',
            'columns': columns,
            'rows': rows,
            'truncated': bool(ex['truncated']),
            'note': ' '.join(notes),
        }

    def _pbxl_standard(self):
        """(filename, bytes) — the Explorer's own Excel for this view, as
        the caller: what "Download Excel" gives."""
        self.ensure_one()
        explorer = self.env['pb.explorer']
        explorer._require()
        self.check_access('read')
        data, ex = explorer._xlsx_bytes(self._pbx_spec_now(), title=self.name,
                                        period_note=self._pbx_period_label())
        return explorer._export_name(ex['payload'], 'xlsx'), data


def _num(value):
    if value is None or isinstance(value, bool):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


class PbExplorerEveryRow(models.AbstractModel):
    """A filled layout asks the Explorer for every row (X-b). Only when the
    caller sets `pbxl_every_row`; the chart and its downloads never do."""
    _inherit = 'pb.explorer'

    @api.model
    def _pbx_series_cap(self):
        if self.env.context.get(EVERY_ROW):
            return _EXPORT_CAP
        return super()._pbx_series_cap()
