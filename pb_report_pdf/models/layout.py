# -*- coding: utf-8 -*-
"""From a report's table and a look to the printed page.

`_pbrp_doc(info, look)` turns the C1 table (python values) into what the
QWeb templates draw: the visible columns with their widths, every cell
already written in the READER's language and number format, group headings,
subtotals and the grand total (money per currency — never added across two
currencies), the heading, the footer words and an estimate of the pages.

The same document draws the on-screen first page and the true PDF, so the
preview is what prints.
"""
import logging
import math
from collections import Counter, OrderedDict
from datetime import date, datetime

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools.misc import format_date, format_datetime, formatLang

from .look import COLORS

_logger = logging.getLogger(__name__)

ROW_CAP = 5000
#: Report PDFs print in fonts INSTALLED on the server (DejaVu carries every
#: Vietnamese letter), never in web fonts: wkhtmltopdf 0.12.6 drops the text
#: of the first pages of a long document in any web font, and draws every
#: weight of a carried-in font with one face (ledger DS-B8). So the page
#: offers the two C3 fonts that differ on paper: "Clean" (sans) and
#: "Classic serif"; the other C3 keys print as Clean.
PDF_FONTS = ('clean', 'classic')
SYSTEM_STACKS = {
    'classic': "'DejaVu Serif', Georgia, 'Times New Roman', serif",
}
SYSTEM_STACK = "'DejaVu Sans', Arial, Helvetica, sans-serif"
#: "Fit" turns the page sideways past this many printed columns.
FIT_COLUMNS = {'A4': 7, 'A3': 11}
PAPER_MM = {'A4': (210, 297), 'A3': (297, 420)}
MARGIN_SIDE = 12
MARGIN_BOTTOM = 22
MARGIN_TOP = 16
MARGIN_TOP_LETTERHEAD = 40
HEADER_SPACING = 8
HEADER_SPACING_LETTERHEAD = 35
PX_MM = 0.2646
NUMERIC = ('number', 'money')
_SENTINEL = object()


class PbReportPdfLayout(models.AbstractModel):
    _inherit = 'pb.report.pdf'

    # ============================================================ columns
    @api.model
    def _pbrp_columns(self, info, look):
        """Every column of the table with its position, its currency column
        (money) and whether it prints. A currency column prints its codes in
        the money cells instead, so it is hidden unless asked for; a column
        that is only there for grouping is hidden while groups print."""
        columns = info['columns']
        keys = [c.get('key') for c in columns]
        groups_on = bool(look.get('groups')) and bool(info.get('groups')) \
            and not info.get('summary')
        out = []
        currency_cols = set()
        for idx, col in enumerate(columns):
            if col.get('type') == 'money':
                cur_key = col['key'] + '__currency'
                if cur_key in keys:
                    currency_cols.add(cur_key)
                elif 'currency' in keys:
                    currency_cols.add('currency')
        for idx, col in enumerate(columns):
            key = col.get('key') or 'c%d' % idx
            cur_idx = None
            if col.get('type') == 'money':
                cur_key = key + '__currency'
                if cur_key in keys:
                    cur_idx = keys.index(cur_key)
                elif 'currency' in keys:
                    cur_idx = keys.index('currency')
            default_hide = key in currency_cols or (groups_on and key in info.get('group_only', []))
            choice = (look.get('columns') or {}).get(key) or {}
            hide = choice['hide'] if 'hide' in choice else default_hide
            out.append({
                'key': key, 'label': str(col.get('label') or ''), 'type': col.get('type') or 'text',
                'idx': idx, 'cur_idx': cur_idx, 'hide': bool(hide),
                'default_hide': bool(default_hide), 'w': choice.get('w'),
                'is_currency': key in currency_cols,
            })
        return out

    # ============================================================ cells
    @api.model
    def _pbrp_currencies(self, info, cols):
        codes = set()
        for col in cols:
            if col['cur_idx'] is not None:
                for row in info['rows']:
                    val = row[col['cur_idx']] if col['cur_idx'] < len(row) else None
                    if isinstance(val, str) and val:
                        codes.add(val)
        if not codes:
            return {}
        Currency = self.env['res.currency'].sudo().with_context(active_test=False)
        return {c.name: c for c in Currency.search([('name', 'in', sorted(codes))])}

    @api.model
    def _pbrp_num(self, value, digits=None):
        if digits is None:
            digits = 0
            if isinstance(value, float) and abs(value - round(value)) > 1e-9:
                digits = 1 if abs(value * 10 - round(value * 10)) < 1e-9 else 2
        return formatLang(self.env, value, digits=digits)

    @api.model
    def _pbrp_money(self, value, code, currencies):
        cur = currencies.get(code) if code else None
        if cur:
            return formatLang(self.env, value, currency_obj=cur)
        text = formatLang(self.env, value, digits=2)
        return '%s %s' % (text, code) if code else text

    @api.model
    def _pbrp_cell(self, col, value, code=None, currencies=None):
        """One cell, written for the reader: numbers in their number format,
        dates in their language, Yes/No in words."""
        kind = col['type']
        if kind == 'bool':
            if value is None:
                return ''
            return self.env._("Yes") if value else self.env._("No")
        if value is None or value is False or value == '':
            return ''
        if kind == 'money' and isinstance(value, (int, float)):
            return self._pbrp_money(value, code, currencies or {})
        if kind == 'number' and isinstance(value, (int, float)):
            return self._pbrp_num(value)
        if kind == 'datetime' and isinstance(value, datetime):
            # C1 datetimes are naive and already in the reader's time zone.
            return format_datetime(self.env, value, tz='UTC', dt_format='short')
        if kind in ('date', 'datetime') and isinstance(value, (date, datetime)):
            return format_date(self.env, value)
        if isinstance(value, float):
            return self._pbrp_num(value)
        return str(value)

    @api.model
    def _pbrp_group_label(self, col, value, currencies):
        text = self._pbrp_cell(col, value, None, currencies)
        return text or self.env._("Not set")

    # ============================================================ totals
    @api.model
    def _pbrp_total(self, rows, col, how, currencies, summary=False):
        """A total cell as lines: one line per currency for money (never one
        sum across two currencies)."""
        idx = col['idx']
        values = [row[idx] for row in rows if idx < len(row)]
        if how == 'count':
            n = sum(1 for v in values if v) if col['type'] == 'bool' else \
                sum(1 for v in values if v not in (None, '', False))
            return [self._pbrp_num(n, 0)]
        if how not in ('sum', 'avg') or (summary and how == 'avg'):
            return []
        if col['type'] == 'money' and col['cur_idx'] is not None:
            per = OrderedDict()
            for row in rows:
                val = row[idx] if idx < len(row) else None
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    continue
                code = row[col['cur_idx']] if col['cur_idx'] < len(row) else None
                per.setdefault(code or '', []).append(val)
            lines = []
            for code in sorted(per, key=lambda c: c or ''):
                nums = per[code]
                amount = sum(nums) if how == 'sum' else sum(nums) / len(nums)
                lines.append(self._pbrp_money(amount, code, currencies))
            return lines
        nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if not nums:
            return []
        amount = sum(nums) if how == 'sum' else round(sum(nums) / len(nums), 2)
        if col['type'] == 'money':
            return [self._pbrp_money(amount, None, currencies)]
        return [self._pbrp_num(amount)]

    @api.model
    def _pbrp_totals_map(self, info, cols):
        """{key: how} of the totals this report shows. A built report shows
        the totals chosen on screen; a source that does not say sums every
        number and money column."""
        totals = info.get('totals')
        if totals is None:
            return {c['key']: 'sum' for c in cols
                    if c['type'] in NUMERIC and not c['hide']}
        return {k: how for k, how in totals.items()}

    # ============================================================ widths
    @api.model
    def _pbrp_widths(self, visible, texts):
        """Percent widths: the ones the person dragged, the rest from the
        length of what they hold (heading and a sample of the cells)."""
        weights = []
        for pos, col in enumerate(visible):
            sample = sorted(len(t) for t in texts[pos][:400]) if texts[pos] else [0]
            p90 = sample[min(len(sample) - 1, int(len(sample) * 0.9))]
            label = len(col['label'])
            weight = max(min(label, 18) * 0.85, p90)
            weight = min(max(weight, 6 if col['type'] in NUMERIC else 4), 42)
            weights.append(weight)
        auto_total = sum(weights) or 1.0
        fixed = {pos: col['w'] for pos, col in enumerate(visible) if col.get('w')}
        fixed_sum = sum(fixed.values())
        if fixed_sum > 96 and len(fixed) < len(visible):
            scale = 80.0 / fixed_sum
            fixed = {p: w * scale for p, w in fixed.items()}
            fixed_sum = sum(fixed.values())
        rest = max(100.0 - fixed_sum, 0.0)
        auto_sum = sum(w for p, w in enumerate(weights) if p not in fixed) or auto_total
        out = []
        for pos, _col in enumerate(visible):
            out.append(fixed[pos] if pos in fixed else rest * weights[pos] / auto_sum)
        total = sum(out) or 1.0
        return [round(w * 100.0 / total, 2) for w in out]

    # ============================================================ the page
    @api.model
    def _pbrp_turn(self, look, n_visible):
        if look['turn'] == 'sideways':
            return True
        if look['turn'] == 'upright':
            return False
        return n_visible > FIT_COLUMNS.get(look['paper'], 7)

    @api.model
    def _pbrp_paper(self, look, sideways):
        w, h = PAPER_MM[look['paper']]
        return (h, w) if sideways else (w, h)

    @api.model
    def _pbrp_color(self, key):
        for k, bg, fg in COLORS:
            if k == key:
                return bg, fg
        return COLORS[0][1], COLORS[0][2]

    @api.model
    def _pbrp_css(self, look):
        bg, fg = self._pbrp_color(look['color'])
        size = look['size']
        return Markup(TABLE_CSS % {
            'font': self._pbrp_font_stack(look['font']),
            'bg': bg, 'fg': fg,
            'title': round(size * 1.75, 1), 'sub': round(size * 1.05, 1),
            'small': round(size * 0.9, 1),
        })

    @api.model
    def _pbrp_font_stack(self, font):
        return SYSTEM_STACKS.get(font, SYSTEM_STACK)

    @api.model
    def _pbrp_printed(self):
        user = self.env.user
        when = format_datetime(self.env, fields.Datetime.now(), tz=user.tz or 'UTC',
                               dt_format='d MMM y, HH:mm')
        return self.env._("Printed on %(when)s by %(who)s", when=when, who=user.name or '')

    @api.model
    def _pbrp_doc(self, info, look, preview=False):
        """Everything the templates draw. `preview` keeps only the entries
        that fit on the first page."""
        _ = self.env._
        cols = self._pbrp_columns(info, look)
        visible = [c for c in cols if not c['hide']]
        currencies = self._pbrp_currencies(info, cols)
        rows_all = info['rows']
        total_rows = len(rows_all)
        capped = total_rows > ROW_CAP
        rows = rows_all[:ROW_CAP]
        summary = bool(info.get('summary'))
        totals = self._pbrp_totals_map(info, cols) if look['total'] or look['groups'] else {}
        by_key = {c['key']: c for c in cols}

        def cells_of(row):
            out = []
            for col in visible:
                val = row[col['idx']] if col['idx'] < len(row) else None
                code = row[col['cur_idx']] if col['cur_idx'] is not None \
                    and col['cur_idx'] < len(row) else None
                out.append(self._pbrp_cell(col, val, code, currencies))
            return out

        def total_cells(bucket, label):
            lines = []
            for col in visible:
                how = totals.get(col['key'])
                lines.append(self._pbrp_total(bucket, col, how, currencies, summary)
                             if how else [])
            # The label opens the row, in the first printed column; a total
            # of that column follows it on the same line.
            if lines:
                first = lines[0]
                lines[0] = ['%s · %s' % (label, first[0])] + first[1:] if first else [label]
            return lines

        entries = []
        group_cols = [by_key[k] for k in (info.get('groups') or []) if k in by_key]
        grouped = bool(look['groups']) and bool(group_cols) and not summary and bool(visible)
        has_totals = bool(totals) and any(c['key'] in totals for c in visible)
        if grouped:
            g1 = group_cols[0]
            g2 = group_cols[1] if len(group_cols) > 1 else None
            count1 = Counter(r[g1['idx']] for r in rows)
            count2 = Counter((r[g1['idx']], r[g2['idx']]) for r in rows) if g2 else {}
            cur1 = cur2 = _SENTINEL
            bucket1, bucket2 = [], []
            odd = False

            def close(bucket, value, col, level):
                if bucket and has_totals:
                    entries.append({'t': 's', 'level': level, 'cells': total_cells(
                        bucket, _("Total %(group)s",
                                  group=self._pbrp_group_label(col, value, currencies)))})

            def heading(col, value, n, level):
                entries.append({'t': 'g', 'level': level,
                                'label': '%s: %s' % (col['label'],
                                                     self._pbrp_group_label(col, value, currencies)),
                                'count': _("1 row") if n == 1 else _("%(count)s rows",
                                                                    count=self._pbrp_num(n, 0))})

            for row in rows:
                k1 = row[g1['idx']]
                k2 = row[g2['idx']] if g2 else None
                if k1 != cur1:
                    if cur1 is not _SENTINEL:
                        if g2:
                            close(bucket2, cur2, g2, 2)
                        close(bucket1, cur1, g1, 1)
                    heading(g1, k1, count1[k1], 1)
                    cur1, cur2, bucket1, bucket2 = k1, _SENTINEL, [], []
                    odd = False
                if g2 and k2 != cur2:
                    if cur2 is not _SENTINEL:
                        close(bucket2, cur2, g2, 2)
                    heading(g2, k2, count2[(k1, k2)], 2)
                    cur2, bucket2 = k2, []
                    odd = False
                entries.append({'t': 'r', 'cells': cells_of(row), 'odd': odd})
                odd = not odd
                bucket1.append(row)
                bucket2.append(row)
            if cur1 is not _SENTINEL:
                if g2:
                    close(bucket2, cur2, g2, 2)
                close(bucket1, cur1, g1, 1)
        elif visible:
            odd = False
            for row in rows:
                entries.append({'t': 'r', 'cells': cells_of(row), 'odd': odd})
                odd = not odd
        if look['total'] and has_totals and rows and visible:
            entries.append({'t': 't', 'level': 0,
                            'cells': total_cells(rows, _("Grand total"))})

        # widths from what the columns hold
        texts = [[] for _c in visible]
        for entry in entries[:600]:
            if entry['t'] == 'r':
                for pos, text in enumerate(entry['cells']):
                    texts[pos].append(text)
        widths = self._pbrp_widths(visible, texts)
        sideways = self._pbrp_turn(look, len(visible))
        paper_w, paper_h = self._pbrp_paper(look, sideways)

        notes = []
        cap_note = ''
        if capped:
            cap_note = _("Only the first %(cap)s of %(total)s rows are printed. Add a filter "
                         "to print fewer rows.", cap=self._pbrp_num(ROW_CAP, 0),
                         total=self._pbrp_num(total_rows, 0))
        elif info.get('truncated'):
            cap_note = info.get('note') or ''
        if info.get('note') and info.get('note') != cap_note:
            notes.append(info['note'])

        title = look['title'] or info.get('title') or ''
        sub = ''
        if look['sub_on']:
            sub = look['sub'] or info.get('sub') or ''
        aligns = ['r' if c['type'] in NUMERIC else 'l' for c in visible]
        doc = {
            'title': title,
            'subtitle': sub,
            'cap_note': cap_note,
            'source_note': ' '.join(notes),
            'closing': look['note'],
            'columns': [{'key': c['key'], 'label': c['label'], 'align': aligns[i],
                         'w': widths[i]} for i, c in enumerate(visible)],
            'aligns': aligns,
            'ncols': max(len(visible), 1),
            'entries': entries,
            'stripes': bool(look['stripes']),
            'css': self._pbrp_css(look),
            'empty': '' if rows else _("This report has no rows to print."),
            'printed': self._pbrp_printed() if look['printed'] else '',
            # Page numbers always print, exactly once: the company's own footer
            # carries them with the letterhead, our footer without it
            # (orchestrator ruling 2026-11-22). `look['pages']` is kept, unused.
            'pages_on': True,
            'sideways': sideways,
            'paper': look['paper'],
            'paper_mm': (paper_w, paper_h),
            'letterhead': bool(look['letterhead']),
            'rows': len(rows),
            'total_rows': total_rows,
            'capped': capped,
            'visible': len(visible),
        }
        pages, first_page = self._pbrp_estimate(doc, look)
        doc['pages'] = pages
        if preview:
            doc['entries'] = entries[:first_page + 2]
        return doc

    # ============================================================ pages
    @api.model
    def _pbrp_estimate(self, doc, look):
        """(pages, entries on the first page) — worked out from the paper,
        the margins, the text size and how much each row wraps."""
        size = look['size']
        paper_w, paper_h = doc['paper_mm']
        top = MARGIN_TOP_LETTERHEAD if doc['letterhead'] else MARGIN_TOP
        usable_h = paper_h - top - MARGIN_BOTTOM
        usable_w = paper_w - 2 * MARGIN_SIDE
        line = size * 1.4 * PX_MM
        pad = 2.0
        char = size * 0.5 * PX_MM
        widths_mm = [max(usable_w * c['w'] / 100.0 - 2.2, 3.0) for c in doc['columns']]

        def lines_of(texts):
            most = 1
            for pos, text in enumerate(texts[:len(widths_mm)]):
                if isinstance(text, list):
                    n = sum(max(1, math.ceil(len(t) * char / widths_mm[pos])) for t in text) \
                        if text else 1
                else:
                    n = max(1, math.ceil(len(text) * char / widths_mm[pos])) if text else 1
                most = max(most, n)
            return most

        head_h = lines_of([c['label'] for c in doc['columns']]) * line + pad + 0.6
        first_extra = size * 1.75 * 1.25 * PX_MM + 3.0
        if doc['subtitle']:
            first_extra += size * 1.05 * 1.4 * PX_MM + 1.5
        if doc['cap_note']:
            first_extra += size * 0.9 * 1.4 * PX_MM * 2 + 1.0
        pages = 1
        room = usable_h - first_extra - head_h
        first_page = 0
        on_first = True
        for entry in doc['entries']:
            if entry['t'] == 'g':
                h = line + pad + 0.8
            else:
                h = lines_of(entry['cells']) * line + pad
            if h > room and room < usable_h - head_h:
                pages += 1
                on_first = False
                room = usable_h - head_h
            room -= h
            if on_first:
                first_page += 1
        return pages, first_page


#: Plain CSS the PDF engine (an old WebKit) understands. `table-layout:
#: fixed` + the column widths make long words wrap inside their cell.
TABLE_CSS = """
.pbds-page, .pbds-page .pbrp, .pbds-page .pbrp th, .pbds-page .pbrp td, .pbds-page .pbrp h1 { font-family: %(font)s !important; }
.pbrp { color: #1f2430; }
.pbrp-head { margin: 0 0 3mm; }
.pbrp .pbrp-title { font-size: %(title)spx; font-weight: 700; margin: 0 0 1mm; color: #1b1733; line-height: 1.25; }
.pbrp .pbrp-sub { font-size: %(sub)spx; color: #64748b; margin: 0; line-height: 1.4; }
.pbrp .pbrp-cap { font-size: %(small)spx; color: #92400e; background: #fef3c7; border: 1px solid #fcd34d; border-radius: 4px; padding: 1mm 2mm; margin-top: 1.5mm; display: inline-block; }
.pbrp table.pbrp-t { width: 100%%; border-collapse: collapse; table-layout: fixed; margin: 0; }
.pbrp table.pbrp-t thead { display: table-header-group; }
.pbrp table.pbrp-t tfoot { display: table-row-group; }
.pbrp table.pbrp-t tr { page-break-inside: avoid; }
.pbrp table.pbrp-t th, .pbrp table.pbrp-t td { border: 0; border-bottom: 1px solid #e2e4ee; padding: 3px 5px; vertical-align: top; text-align: left; word-wrap: break-word; overflow-wrap: break-word; line-height: 1.4; }
.pbrp table.pbrp-t thead th { background: %(bg)s !important; color: %(fg)s !important; font-weight: 700; border-bottom: 0; }
.pbrp table.pbrp-t .r { text-align: right; }
.pbrp table.pbrp-t.pbrp-striped tr.pbrp-odd td { background: #f6f5fb; }
.pbrp table.pbrp-t tr.pbrp-g td { font-weight: 700; color: #241f52; background: #edeaf8; border-bottom: 1px solid #cbc2ee; }
.pbrp table.pbrp-t tr.pbrp-g2 td { background: #f5f3fc; padding-left: 12px; font-weight: 600; }
.pbrp table.pbrp-t tr.pbrp-g .pbrp-gc { font-weight: 400; color: #64748b; padding-left: 6px; }
.pbrp table.pbrp-t tr.pbrp-s td { font-weight: 700; background: #fafafc; border-bottom: 1px solid #cbd5e1; }
.pbrp table.pbrp-t tr.pbrp-gt td { font-weight: 700; border-top: 2px solid #241f52; border-bottom: 2px solid #241f52; background: #ffffff; }
.pbrp .pbrp-empty { color: #64748b; margin: 4mm 0; }
.pbrp .pbrp-note { color: #64748b; font-size: %(small)spx; margin: 3mm 0 0; }
.pbrp .pbrp-closing { margin: 5mm 0 0; white-space: pre-wrap; word-wrap: break-word; }
"""
