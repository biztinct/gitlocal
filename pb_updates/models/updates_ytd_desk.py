# -*- coding: utf-8 -*-
"""UPDATES P5 (D20) — the Updates screens for year-to-date figures.

  * the fourth kind of sheet, "Year-to-date figures before Payobook": the
    same four steps as every other sheet, drafts, Past updates, approval on
    the pay route, undo; one "Figures cover up to" date for the whole sheet
    (its year is the tax year);
  * the year-to-date view: per person and figure, Before Payobook + Paid in
    Payobook = Total, months missing shown, a download;
  * "Download for the pay run": the mapped pay items of one pay scheme, with
    the values a payslip of a chosen month would receive — the way into a
    run from application data, whose inputs are certified and never fed from
    here;
  * the set-up a payroll manager does: which pay items "paid in Payobook"
    adds up, pay items named as figures, and which input pay item of which
    scheme receives which figure (nothing reaches a pay run without it).

A cell's verdict lives in ONE place, `_ytd_cell`; review, an on-screen fix and
Apply all ask it. Loaded after `updates_ytd` (constants come from there,
ledger G21).
"""
import base64
import difflib
import io
import json
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.pb_records.models.pb_records_io import (
    _norm, XLSX_MIME, IDENTITY_COLS, ID_RE, META_SHEET, MAX_ROWS)
from odoo.addons.pb_records.models.records_approval import RECORDS_PROCESS_KEY
from odoo.addons.pb_updates.models.updates_desk import GUESS_RATIO, IDENTITY_KEYS, product_label
from odoo.addons.pb_updates.models.updates_batch import heading_fingerprint
from odoo.addons.pb_updates.models.updates_ytd import (
    AHEAD_DAYS, BASES, COUNT_FIGURES, DONE_SLIP_STATES, FIGURES, GROUP, LIVE, PREFIX,
    READ_GROUPS, SETUP_GROUPS, SOURCE_ID, card_id, day_label, key_of, last_of_year,
    first_of_year, may, month_floor, months_between, number_text, parse_amount)

#: The hidden sheet's cell that says which date a sheet's figures cover up to.
DATE_KEY = 'ytd_covers_to'
#: People on one page of the year-to-date view.
VIEW_PAGE = 50


class PbUpdatesYtdDesk(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    # =================================================================
    # Gates, date, words
    # =================================================================
    @api.model
    def _ytd_may_read(self):
        return may(self.env, READ_GROUPS)

    @api.model
    def _ytd_may_send(self, desk=None):
        return self._ytd_may_read() and self._can_write(desk)

    @api.model
    def _ytd_may_setup(self):
        return may(self.env, SETUP_GROUPS)

    @api.model
    def _ytd_gate(self):
        desk = self._gate()
        if not self._ytd_may_read():
            raise AccessError(_("Year-to-date figures are pay data: seeing them needs a payroll "
                                "role. Ask an administrator."))
        return desk

    @api.model
    def _ytd_today(self):
        return self.env['pb.records.apply']._today_for()

    @api.model
    def _ytd_cover(self, value):
        """`(date or None, refusal)` — "Figures cover up to": in this tax year
        or last year, and not more than two months ahead."""
        try:
            day = fields.Date.to_date(value) if value else None
        except (TypeError, ValueError):
            day = None
        if not day:
            return None, _("Pick the date these figures cover up to: the last day before your "
                           "first pay period on Payobook.")
        today = self._ytd_today()
        if day.year not in (today.year, today.year - 1):
            return None, _("Figures can be for this tax year (%(this)s) or last year (%(last)s). "
                           "%(date)s is outside both.", this=today.year, last=today.year - 1,
                           date=day_label(self.env, day))
        if day > today + timedelta(days=AHEAD_DAYS):
            return None, _("%s is too far ahead. Pick the last day before your first pay period "
                           "on Payobook.") % day_label(self.env, day)
        return day, ''

    # =================================================================
    # The figures of the companies in use
    # =================================================================
    @api.model
    def _ytd_figures(self, company_ids=None):
        """`{key: {key, label, count, item, company_id}}` in sheet order: the
        six fixed figures, then the pay items a company named as figures."""
        Line = self.env['pb.updates.ytd.line']
        out = {}
        for key in FIGURES:
            out[key] = {'key': key, 'label': Line._figure_label(key), 'count': key in COUNT_FIGURES,
                        'item': False, 'company_id': 0}
        company_ids = list(company_ids or self.env.companies.ids)
        for row in self.env['pb.updates.ytd.figure'].sudo().search(
                [('company_id', 'in', company_ids), ('item', '=', True)], order='sequence, id'):
            out.setdefault(row.key, {'key': row.key, 'label': row.label or row.key, 'count': False,
                                     'item': True, 'company_id': row.company_id.id})
        return out

    @api.model
    def _ytd_value_label(self, key, value, currency=None):
        return self.env['pb.updates.ytd.line']._value_label(key, value, currency)

    # =================================================================
    # One cell's verdict
    # =================================================================
    @api.model
    def _ytd_people(self, emp_ids):
        emps = self.env['hr.employee'].sudo().browse(sorted(set(emp_ids or []))).exists()
        has_doj = 'date_of_joining' in emps._fields
        out = {}
        for emp in emps:
            joined = emp.date_of_joining if has_doj else False
            out[emp.id] = {'id': emp.id, 'name': emp.name or '', 'company_id': emp.company_id.id,
                           'company': emp.company_id.name or '', 'joined': joined or None,
                           'currency': emp.company_id.currency_id}
        return out

    @api.model
    def _ytd_ctx(self, emp_ids, covers_to, skip_line_ids=()):
        people = self._ytd_people(emp_ids)
        companies = sorted({p['company_id'] for p in people.values()} | set(self.env.companies.ids))
        figures = self._ytd_figures(companies)
        year = covers_to.year
        Line = self.env['pb.updates.ytd.line'].sudo()
        current, waiting, used = {}, {}, {}
        if people:
            for line in Line.search([('employee_id', 'in', list(people)), ('tax_year', '=', year),
                                     ('state', 'in', LIVE),
                                     ('id', 'not in', list(skip_line_ids or []))], order='id'):
                key = (line.employee_id.id, line.figure)
                if line.state == 'waiting':
                    waiting[key] = line
                else:
                    current[key] = line
            if current:
                ids = [l.id for l in current.values()]
                for use in self.env['pb.updates.ytd.use'].sudo().search(
                        [('line_id', 'in', ids), ('state', '=', 'used')]):
                    used.setdefault(use.line_id.id, use.run_name or '')
        return {'people': people, 'figures': figures, 'covers_to': covers_to, 'year': year,
                'current': current, 'waiting': waiting, 'used': used}

    @api.model
    def _ytd_cell(self, ctx, emp_id, key, raw, clear_words=frozenset()):
        """The verdict of one cell — the only one there is."""
        person = ctx['people'].get(emp_id)
        fig = ctx['figures'].get(key)
        text = '' if raw is None else (number_text(raw) if isinstance(raw, (int, float))
                                       and not isinstance(raw, bool) else str(raw))
        out = {'status': 'ok', 'old': '', 'new': text, 'value': raw, 'why': '', 'amount': 0.0,
               'role': key, 'cleared': False, 'action': 'set'}

        def refuse(why):
            out.update(status='refused', why=why)
            return out

        if not person:
            return refuse(_("This person could not be found any more."))
        who = person['name'] or _("This person")
        if not fig:
            return refuse(_("This is not a year-to-date figure here."))
        if fig['company_id'] and fig['company_id'] != person['company_id']:
            return refuse(_("%(figure)s is not a year-to-date figure in %(company)s, where %(who)s "
                            "works.", figure=fig['label'], company=person['company'], who=who))
        cur = person['currency']
        k = (emp_id, key)
        line = ctx['waiting'].get(k)
        if line:
            return refuse(_("%(who)s's %(figure)s is already waiting for approval in "
                            "“%(batch)s”.", who=who, figure=fig['label'],
                            batch=line.batch_id.name or ''))
        existing = ctx['current'].get(k)
        if existing:
            out['old'] = self._ytd_value_label(key, existing.amount, cur)
        run = ctx['used'].get(existing.id) if existing else ''
        if isinstance(raw, str) and raw.strip().lower() in clear_words:
            if not existing:
                out.update(status='same', cleared=True, new='')
                return out
            if run is not None and existing.id in ctx['used']:
                return refuse(_("%(figure)s for %(who)s was used in pay run %(run)s. It can no "
                                "longer be changed here.", figure=fig['label'], who=who, run=run))
            out.update(cleared=True, new='', action='clear', value='')
            return out
        n = parse_amount(raw)
        if n is None:
            return refuse(_("'%s' is not a number. Type the amount without a currency, like "
                            "125000000.") % text if not fig['count'] else
                          _("'%s' is not a number of months. Type a whole number from 0 to 12.")
                          % text)
        if n < 0:
            return refuse(_("A year-to-date figure cannot be negative."))
        if fig['count']:
            if abs(n - round(n)) > 1e-9 or n > 12:
                return refuse(_("Months counted must be a whole number from 0 to 12."))
            n = float(round(n))
        elif abs(n * 100 - round(n * 100)) > 1e-6:
            return refuse(_("Use at most two decimals."))
        out['amount'] = n
        out['new'] = self._ytd_value_label(key, n, cur)
        if existing and round(existing.amount, 2) == round(n, 2):
            out.update(status='same', new=out['old'])
            return out
        if existing and existing.id in ctx['used']:
            return refuse(_("%(figure)s for %(who)s was used in pay run %(run)s. It can no longer "
                            "be changed here.", figure=fig['label'], who=who, run=run))
        return out

    @api.model
    def _ytd_late(self, ctx, emp_id):
        """'' or the amber note: the person joined after the date the figures
        cover up to (allowed — somebody may have typed a wrong date)."""
        person = ctx['people'].get(emp_id) or {}
        joined = person.get('joined')
        if joined and joined > ctx['covers_to']:
            return _("Joined on %(joined)s, after %(date)s. Are you sure there are figures before "
                     "Payobook?", joined=day_label(self.env, joined),
                     date=day_label(self.env, ctx['covers_to']))
        return ''

    # =================================================================
    # Home
    # =================================================================
    @api.model
    def _ytd_home(self):
        today = self._ytd_today()
        readable = self._ytd_may_read()
        figures = self._ytd_figures()
        last_month_end = month_floor(today) - timedelta(days=1)
        default = last_month_end if last_month_end.year == today.year else today
        people = 0
        if readable:
            self.env['pb.updates.ytd.line'].flush_model()
            self.env.cr.execute(
                "SELECT count(DISTINCT employee_id) FROM pb_updates_ytd_line "
                "WHERE state = 'set' AND tax_year = %s AND company_id = ANY(%s)",
                [today.year, self.env.companies.ids])
            people = self.env.cr.fetchone()[0] or 0
        maps = self.env['pb.updates.ytd.map'].sudo().search_count(
            [('company_id', 'in', self.env.companies.ids)]) if readable else 0
        return {
            'available': readable, 'may_send': self._ytd_may_send(), 'may_setup': self._ytd_may_setup(),
            'figures': [{'key': f['key'], 'label': f['label'], 'count': f['count'], 'item': f['item']}
                        for f in figures.values()],
            'this_year': today.year, 'last_year': today.year - 1,
            'today': fields.Date.to_string(today), 'default': fields.Date.to_string(default),
            'max': fields.Date.to_string(min(today + timedelta(days=AHEAD_DAYS),
                                             last_of_year(today.year))),
            'min': fields.Date.to_string(first_of_year(today.year - 1)),
            'people': people, 'maps': maps,
        }

    @api.model
    def get_home(self):
        answer = super().get_home()
        try:
            answer['ytd'] = self._ytd_home()
        except Exception:   # noqa: BLE001 — a tile never blocks the home
            answer['ytd'] = {'available': False, 'may_send': False, 'figures': []}
        return answer

    # =================================================================
    # Download the sheet
    # =================================================================
    @api.model
    def download_ytd_sheet(self, covers_to=None, filters=None):
        """People × the company's figures, figures already set filled in and
        shaded, an optional Source column, a "Read me"."""
        desk = self._ytd_gate()
        if not desk._may_export():
            return {'ok': False, 'msg': _(
                "Downloading a sheet needs permission to export employee "
                "records. Ask an administrator, or upload a file of your own.")}
        covers_to, refusal = self._ytd_cover(covers_to)
        if refusal:
            return {'ok': False, 'msg': refusal}
        import openpyxl
        from openpyxl.comments import Comment
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        people = desk._matching(filters or {}, ctx={})
        total = len(people)
        people = people[:MAX_ROWS]
        ctx = self._ytd_ctx(people.ids, covers_to)
        figures = [f for f in ctx['figures'].values()]
        when = day_label(self.env, covers_to)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Records'
        bold = Font(bold=True, color='241F52')
        id_fill = PatternFill('solid', fgColor='EEF2F6')
        head_fill = PatternFill('solid', fgColor='EEEBFA')
        grey = PatternFill('solid', fgColor='EEEEF2')
        set_fill = PatternFill('solid', fgColor='E4E1F2')
        set_font = Font(color='6B6890')
        for idx, (_key, head) in enumerate(IDENTITY_COLS, start=1):
            cell = ws.cell(row=1, column=idx, value=_(head))
            cell.font, cell.fill = bold, id_fill
            cell.comment = Comment(_("Identity — used to match the row to a person. "
                                     "It is never imported."), product_label(self.env))
            ws.column_dimensions[get_column_letter(idx)].width = max(16, len(head) + 6)
        first = len(IDENTITY_COLS) + 1
        cards = [{'id': card_id(f['key']), 'label': f['label'], 'fig': f} for f in figures]
        cards.append({'id': SOURCE_ID, 'label': _("Source"), 'fig': None})
        for offset, card in enumerate(cards):
            col = first + offset
            cell = ws.cell(row=1, column=col, value=card['label'])
            cell.font, cell.fill = bold, head_fill
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            note = _("Before Payobook, up to %s") % when if card['fig'] else _(
                "Optional: where these figures come from (the previous payroll's report, a "
                "certificate number). Kept with the figures.")
            cell.comment = Comment('id: %s\n%s' % (card['id'], note), product_label(self.env))
            ws.column_dimensions[get_column_letter(col)].width = max(16, min(40, len(card['label']) + 6))
        for r, emp in enumerate(people, start=2):
            ws.cell(row=r, column=1, value=emp.barcode or emp.employee_id or '')
            ws.cell(row=r, column=2, value=emp.display_name or emp.name or '')
            ws.cell(row=r, column=3, value=emp.work_email or '')
            p = ctx['people'].get(emp.id)
            for offset, card in enumerate(cards):
                cell = ws.cell(row=r, column=first + offset)
                f = card['fig']
                if not f:
                    continue
                if not p or (f['company_id'] and f['company_id'] != p['company_id']):
                    cell.fill = grey
                    continue
                line = ctx['current'].get((emp.id, f['key']))
                if line:
                    cell.value = int(line.amount) if f['count'] else line.amount
                    cell.number_format = '0' if f['count'] else '#,##0.##'
                    cell.fill, cell.font = set_fill, set_font
        ws.freeze_panes = 'D2'
        meta = wb.create_sheet(title=META_SHEET)
        meta['A1'], meta['B1'] = 'config_id', 0
        meta['D1'], meta['E1'] = DATE_KEY, fields.Date.to_string(covers_to)
        meta['A2'], meta['B2'], meta['C2'] = 'column_index', 'field_id', 'label'
        for offset, card in enumerate(cards):
            meta.cell(row=3 + offset, column=1, value=first + offset)
            meta.cell(row=3 + offset, column=2, value=card['id'])
            meta.cell(row=3 + offset, column=3, value=card['label'])
        meta.sheet_state = 'hidden'
        guide = wb.create_sheet(title=_("Read me")[:31])
        guide.column_dimensions['A'].width = 110
        lines = [
            _("Year-to-date figures before %(product)s, tax year %(year)s, up to %(date)s",
              product=product_label(self.env), year=covers_to.year, date=when),
            _("Each number is what the person was paid, or had taken off, from 1 January %(year)s "
              "up to %(date)s — before your company ran payroll on %(product)s. Take them from "
              "the previous payroll's year-to-date report.", year=covers_to.year, date=when,
              product=product_label(self.env)),
            _("Nothing here changes how tax is calculated. The figures are kept beside the "
              "payslips: they show on each person's tax summary, and a pay run receives one only "
              "where a payroll manager has chosen which pay item gets it."),
            _("A blank cell changes nothing. Type amounts without a currency or a minus sign. "
              "Months counted is a whole number from 0 to 12."),
            _("Shaded cells with a number are already set: send them back as they are, type a "
              "new number to replace one, or type CLEAR to remove one. A figure a finished pay "
              "run has used can no longer be changed here."),
            _("Source is optional: where the figures come from, kept with them."),
        ]
        for idx, line in enumerate(lines, start=1):
            cell = guide.cell(row=idx, column=1, value=line)
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if idx == 1:
                cell.font = bold
        out = io.BytesIO()
        wb.save(out)
        return {'ok': True, 'file_b64': base64.b64encode(out.getvalue()).decode(),
                'filename': _("%(product)s year-to-date figures %(year)s.xlsx") % {
                    'product': product_label(self.env), 'year': covers_to.year},
                'mimetype': XLSX_MIME, 'rows': len(people), 'total': total,
                'columns': len(cards), 'truncated': total > MAX_ROWS}

    # =================================================================
    # Match columns
    # =================================================================
    @api.model
    def _ytd_sheet_date(self, file_b64, filename):
        if not (filename or '').lower().endswith(('.xlsx', '.xlsm')):
            return ''
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(file_b64 or '')),
                                        read_only=True, data_only=True)
            if META_SHEET not in wb.sheetnames:
                return ''
            ms = wb[META_SHEET]
            if str(ms['D1'].value or '') != DATE_KEY:
                return ''
            day = fields.Date.to_date(str(ms['E1'].value or '')[:10])
            return fields.Date.to_string(day) if day else ''
        except Exception:  # noqa: BLE001 — a hint, never a gate
            return ''

    @api.model
    def _ytd_topics(self, figures):
        cards = [{'id': card_id(f['key']), 'label': f['label'], 'group': GROUP,
                  'ttype': 'float', 'editable': True, 'locked': False} for f in figures.values()]
        cards.append({'id': SOURCE_ID, 'label': _("Source (kept with the figures)"),
                      'group': GROUP + '_source', 'ttype': 'char', 'editable': True,
                      'locked': False})
        return [{'key': GROUP, 'label': _("Year-to-date figures"), 'icon': 'history',
                 'count': len(cards) - 1, 'field_ids': [c['id'] for c in cards[:-1]],
                 'fields': cards[:-1], 'examples': [c['label'] for c in cards][:3], 'locked': False},
                {'key': GROUP + '_source', 'label': _("Kept with the figures"), 'icon': 'fileText',
                 'count': 1, 'field_ids': [SOURCE_ID], 'fields': cards[-1:],
                 'examples': [cards[-1]['label']], 'locked': False}]

    @api.model
    def _ytd_read_columns(self, file_b64='', filename='', covers_to=None):
        desk = self._ytd_gate()
        refusal, header, rows, comments, meta, name = desk._io_open(file_b64, filename)
        if refusal:
            return refusal
        body = rows[1:]
        if not body:
            return {'ok': False, 'empty': True, 'filename': name,
                    'msg': _("This file has headings only — fill it in and drop it again.")}
        _used, identity_cols, _ignored, _how = desk._io_columns(
            header, comments, {'config_id': 0, 'by_index': {}}, {}, with_how=True)
        identity_at = {idx: key for key, idx in identity_cols.items()}
        figures = self._ytd_figures()
        offered = {card_id(k): f['label'] for k, f in figures.items()}
        offered[SOURCE_ID] = _("Source")
        by_label = {}
        for cid, label in offered.items():
            by_label.setdefault(_norm(label), cid)
        for word in ('source', 'evidence', 'reference', 'nguồn', 'sumber'):
            by_label.setdefault(_norm(word), SOURCE_ID)
        heads = [str(h if h is not None else '').strip() for h in header]
        fingerprint = GROUP + ':' + heading_fingerprint(heads)
        Layout = self.env['pb.updates.layout']
        layouts = Layout.search([('company_id', '=', self.env.company.id), ('kind', '=', GROUP)],
                                order='last_used desc, id desc', limit=50)
        exact = layouts.filtered(lambda l: l.fingerprint == fingerprint)[:1]
        maps = ([exact.get_map()] if exact else []) + [l.get_map() for l in layouts if l != exact]
        columns, taken, taken_identity = [], set(), set(identity_at.values())
        for idx, head in enumerate(heads, start=1):
            if not head:
                continue
            samples = []
            for _offset, row in body:
                text = desk._io_text(desk._io_cell(row, idx))
                if text:
                    samples.append(text)
                    if len(samples) >= 3:
                        break
            col = {'idx': idx, 'head': head, 'samples': samples, 'field_id': '',
                   'identity': identity_at.get(idx, ''), 'how': '', 'target': ''}
            if col['identity']:
                col.update(how='identity', target='identity:%s' % col['identity'])
                columns.append(col)
                continue
            match = ID_RE.search(comments.get(idx) or '')
            fid = match.group(1).strip() if match else ''
            if not fid:
                fid = (meta.get('by_index') or {}).get(idx) or ''
            if fid in offered and fid not in taken:
                col.update(how='id', field_id=fid, target=fid)
            else:
                key = _norm(head)
                remembered = next((m[key] for m in maps if key in m), '')
                if remembered == 'ignore':
                    col.update(how='memory', target='ignore')
                elif remembered.startswith('identity:'):
                    ident = remembered.split(':', 1)[1]
                    if ident in IDENTITY_KEYS and ident not in taken_identity:
                        taken_identity.add(ident)
                        col.update(how='memory', identity=ident, target=remembered)
                elif remembered in offered and remembered not in taken:
                    col.update(how='memory', field_id=remembered, target=remembered)
                elif by_label.get(key) and by_label[key] not in taken:
                    col.update(how='label', field_id=by_label[key], target=by_label[key])
                else:
                    best, ratio = '', 0.0
                    for cid, label in offered.items():
                        if cid in taken:
                            continue
                        r = difflib.SequenceMatcher(None, key, _norm(label)).ratio()
                        if r > ratio:
                            best, ratio = cid, r
                    if best and ratio >= GUESS_RATIO:
                        col.update(how='guess', field_id=best, target=best)
            if col['field_id']:
                taken.add(col['field_id'])
            columns.append(col)
        placed_by_id = [c for c in columns if c['how'] == 'id']
        return {
            'ok': True, 'kind': GROUP, 'filename': name, 'rows': len(body),
            'truncated': len(body) > MAX_ROWS, 'columns': columns,
            'fields': self._ytd_topics(figures), 'layout_known': bool(exact),
            'sheet_date': self._ytd_sheet_date(file_b64, filename),
            'from_sheet': bool(placed_by_id) and all(c['how'] in ('id', 'identity')
                                                    for c in columns),
            'schemes': [], 'no_scheme': 0,
        }

    @api.model
    def _remember_ytd_layout(self, columns):
        cols = self._clean_columns(columns)
        heads = dict(cols['heads'])
        if not heads:
            return
        identity_at = {idx: key for key, idx in cols['identity'].items()}
        pairs = []
        for idx in sorted(heads):
            if not _norm(heads[idx]):
                continue
            if idx in identity_at:
                target = 'identity:%s' % identity_at[idx]
            elif idx in cols['used']:
                target = cols['used'][idx]
            else:
                target = 'ignore'
            pairs.append((heads[idx], target))
        self.env['pb.updates.layout'].remember(pairs, kind=GROUP)

    # =================================================================
    # Review
    # =================================================================
    @api.model
    def _ytd_review(self, file_b64='', filename='', columns=None, covers_to=None):
        desk = self._ytd_gate()
        covers_to, refusal = self._ytd_cover(covers_to)
        if refusal:
            return {'ok': False, 'msg': refusal}
        cols = self._clean_columns(columns)
        if not cols['identity']:
            return {'ok': False, 'msg': _(
                "Pick the column that finds the person: an employee code, a "
                "name or a work email.")}
        refusal, header, rows, _comments, _meta, name = desk._io_open(file_b64, filename)
        if refusal:
            return refusal
        figures = self._ytd_figures()
        offered = {card_id(k) for k in figures}
        used = {idx: fid for idx, fid in cols['used'].items()
                if fid in offered and idx not in cols['identity'].values()}
        source_col = next((idx for idx, fid in cols['used'].items() if fid == SOURCE_ID), 0)
        if not used:
            return {'ok': False, 'msg': _(
                "Pick at least one column that goes to a year-to-date figure.")}
        body = rows[1:]
        truncated = len(body) > MAX_ROWS
        body = body[:MAX_ROWS]
        index = desk._io_index(desk._matching({}, ctx={}))
        clear_words = desk._io_clear_words()
        matched, unmatched, methods = [], [], {}
        for offset, row in body:
            code = desk._io_text(desk._io_cell(row, cols['identity'].get('code')))
            person = desk._io_text(desk._io_cell(row, cols['identity'].get('name')))
            email = desk._io_text(desk._io_cell(row, cols['identity'].get('email')))
            values = {}
            for idx, fid in used.items():
                raw = desk._io_cell(row, idx)
                if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                    raw = desk._io_text(raw)
                if raw in (None, ''):
                    continue
                values[fid] = raw
            source = desk._io_text(desk._io_cell(row, source_col)) if source_col else ''
            emp_id, method, why = desk._io_match(index, code, person, email)
            if not emp_id:
                unmatched.append({'row': offset, 'code': code, 'name': person, 'email': email,
                                  'why': why, 'values': {k: str(v) for k, v in values.items()}})
                continue
            methods[method] = methods.get(method, 0) + 1
            matched.append({'row': offset, 'emp_id': emp_id, 'method': method, 'values': values,
                            'source': source})
        emp_ids = sorted({m['emp_id'] for m in matched})
        info = self._people_info(desk, emp_ids)
        ctx = self._ytd_ctx(emp_ids, covers_to)
        last_row, twice = {}, {}
        for pos, m in enumerate(matched):
            twice[m['emp_id']] = twice.get(m['emp_id'], 0) + 1
            for fid in m['values']:
                last_row[(m['emp_id'], fid)] = pos
        out_rows, changes = [], []
        for pos, m in enumerate(matched):
            p_info = info.get(m['emp_id']) or {}
            cells = {}
            for fid, raw in m['values'].items():
                cell = self._ytd_cell(ctx, m['emp_id'], key_of(fid), raw, clear_words)
                if last_row.get((m['emp_id'], fid)) != pos:
                    cell.update(status='dup', why=_(
                        "This person is in the file again further down, and that "
                        "row's value is the one used."))
                cells[fid] = cell
                if cell['status'] == 'ok':
                    change = {'emp_id': m['emp_id'], 'field_id': fid,
                              'value': '' if cell['cleared'] else cell['amount']}
                    if m['source']:
                        change['source'] = m['source'][:200]
                    changes.append(change)
            late = self._ytd_late(ctx, m['emp_id'])
            out_rows.append({'row': m['row'], 'emp_id': m['emp_id'], 'method': m['method'],
                             'name': p_info.get('name') or '', 'code': p_info.get('code') or '',
                             'department': p_info.get('department') or '',
                             'twice': twice.get(m['emp_id'], 0) > 1, 'cells': cells,
                             'late': bool(late), 'late_note': late, 'source': m['source']})
        out_columns = []
        for idx in sorted(used):
            fid = used[idx]
            if any(c['field_id'] == fid for c in out_columns):
                continue
            fig = figures[key_of(fid)]
            out_columns.append({'field_id': fid, 'label': fig['label'], 'group': GROUP, 'idx': idx,
                                'role': fig['key'], 'count': fig['count'],
                                'head': cols['heads'].get(idx, '')})
        used_heads = {cols['heads'].get(i, '') for i in list(used) + list(cols['identity'].values())
                      + ([source_col] if source_col else [])}
        ignored = [h for h in (str(x if x is not None else '').strip() for x in header)
                   if h and h not in used_heads]
        currency = self.env.company.currency_id
        return {
            'ok': True, 'kind': GROUP, 'ytd': True, 'filename': name,
            'covers_to': fields.Date.to_string(covers_to),
            'covers_label': day_label(self.env, covers_to), 'tax_year': covers_to.year,
            'summary': {'rows': len(body), 'columns_ignored': ignored},
            'identity': max(methods, key=methods.get) if methods else '',
            'truncated': truncated, 'columns': out_columns, 'pay_items': False,
            'dated': False, 'today': fields.Date.to_string(self._ytd_today()),
            'rows': out_rows, 'unmatched': unmatched, 'changes': changes,
            'has_source': bool(source_col), 'late': sum(1 for r in out_rows if r['late']),
            'currency': self._currency_payload(currency) if hasattr(self, '_currency_payload')
            else None,
            'schemes': [], 'no_scheme': 0,
        }

    @api.model
    def _ytd_recheck(self, changes=None, covers_to=None):
        self._ytd_gate()
        covers_to, refusal = self._ytd_cover(covers_to)
        if refusal:
            return {'items': [], 'msg': refusal}
        changes = [c for c in (changes or []) if isinstance(c, dict)]
        emp_ids = sorted({int(c.get('emp_id') or 0) for c in changes} - {0})
        ctx = self._ytd_ctx(emp_ids, covers_to)
        clear_words = self._desk()._io_clear_words()
        items = []
        for change in changes:
            emp_id = int(change.get('emp_id') or 0)
            fid = str(change.get('field_id') or '')
            key = key_of(fid)
            cell = self._ytd_cell(ctx, emp_id, key, change.get('value'), clear_words) if key else {
                'status': 'refused', 'why': _("This value could not be checked. Try again."),
                'old': '', 'new': str(change.get('value') or ''), 'amount': 0.0,
                'cleared': False, 'role': ''}
            items.append({'emp_id': emp_id, 'field_id': fid, 'status': cell['status'],
                          'old_label': cell['old'], 'new_label': cell['new'], 'why': cell['why'],
                          'cleared': cell['cleared'], 'amount': cell['amount'], 'role': cell['role'],
                          'field_label': (ctx['figures'].get(key) or {}).get('label') or ''})
        return {'items': items, 'people': {}}

    # =================================================================
    # Apply
    # =================================================================
    @api.model
    def ytd_outlook(self, changes=None):
        """Before sending: who approves, in names — or "set now". Read only."""
        self._ytd_gate()
        rows = [c for c in (changes or []) if isinstance(c, dict)]
        probe = self._probe_apply('pay', rows)
        kind, names, sentence = self._first_step_people(probe, RECORDS_PROCESS_KEY)
        if kind == 'fast':
            return {'outcome': 'now', 'names': [], 'line': _("Set now: your company needs no "
                                                              "approval for these.")}
        if kind == 'route' and names:
            return {'outcome': 'approval', 'names': names,
                    'line': _("Go to %s for approval") % self._names_line(names)}
        return {'outcome': 'approval', 'names': [], 'line': sentence or _("Go for approval")}

    @api.model
    def _ytd_apply(self, name='', file_b64='', filename='', columns=None, changes=None,
                   stats=None, covers_to=None, draft_id=0):
        """Name it, keep the file, and send ONE approval for every figure in
        it. Every value is judged again here."""
        desk = self._ytd_gate()
        name = (name or '').strip()
        if not name:
            return {'ok': False, 'msg': _(
                "Give this update a name first, so you can find it later in "
                "Past updates.")}
        if not self._ytd_may_send(desk):
            return {'ok': False, 'msg': _(
                "You can look through these figures, but sending them needs permission to "
                "change employee records. Ask an administrator for the Payroll Officer role.")}
        covers_to, refusal = self._ytd_cover(covers_to)
        if refusal:
            return {'ok': False, 'msg': refusal}
        clean, seen = [], set()
        for change in reversed([c for c in (changes or []) if isinstance(c, dict)]):
            try:
                emp_id = int(change.get('emp_id') or 0)
            except (TypeError, ValueError):
                continue
            fid = str(change.get('field_id') or '')
            if not emp_id or not key_of(fid) or (emp_id, fid) in seen:
                continue
            seen.add((emp_id, fid))
            clean.append({'emp_id': emp_id, 'field_id': fid, 'value': change.get('value'),
                          'source': str(change.get('source') or '')[:200]})
        clean.reverse()
        if not clean:
            return {'ok': False, 'msg': _(
                "There is nothing to send: no figure in this file would change anything.")}
        emp_ids = sorted({c['emp_id'] for c in clean})
        visible = set(desk._matching({'employee_ids': emp_ids}, ctx={}).ids)
        ctx = self._ytd_ctx(emp_ids, covers_to)
        clear_words = desk._io_clear_words() | {''}
        refused, lines = [], []
        for change in clean:
            if change['emp_id'] not in visible:
                continue
            key = key_of(change['field_id'])
            raw = change['value']
            if raw is None or raw is False:
                raw = ''
            cell = self._ytd_cell(ctx, change['emp_id'], key, raw, clear_words)
            person = ctx['people'].get(change['emp_id']) or {}
            if cell['status'] == 'refused':
                refused.append({'emp_id': change['emp_id'], 'emp_name': person.get('name') or '',
                                'field_id': change['field_id'],
                                'field_label': (ctx['figures'].get(key) or {}).get('label') or key,
                                'why': cell['why']})
                continue
            if cell['status'] != 'ok':
                continue
            fig = ctx['figures'][key]
            lines.append({
                'employee_id': change['emp_id'], 'company_id': person['company_id'],
                'tax_year': covers_to.year, 'figure': key, 'label': fig['label'],
                'amount': cell['amount'] if cell['action'] == 'set' else 0.0,
                'covers_to': covers_to, 'action': cell['action'],
                'source_note': change['source'] or False,
            })
        self._remember_ytd_layout(columns)
        when = day_label(self.env, covers_to)
        if not lines:
            return {'ok': True, 'kind': GROUP, 'nothing': True, 'batch_id': 0, 'apply_id': 0,
                    'written': 0, 'people': 0, 'refused': refused, 'pending': False,
                    'off_scheme': 0, 'covers_label': when,
                    'msg': _("Nothing was sent: every figure in this file is already set, or "
                             "could not be used.")}
        stats = stats if isinstance(stats, dict) else {}

        def count(key):
            try:
                return max(0, int(stats.get(key) or 0))
            except (TypeError, ValueError):
                return 0

        batch = self._new_batch({
            'name': name[:200], 'kind': GROUP, 'ytd_covers_to': covers_to,
            'filename': (filename or '').strip() or False,
            'rows_total': count('rows'), 'rows_unmatched': count('unmatched'),
            'values_refused': count('left_out') + len(refused), 'values_off_scheme': 0,
        }, file_b64, filename, draft_id)
        Apply = self.env['pb.records.apply'].sudo()
        apply_rec = Apply.create({
            'name': '/', 'note': name, 'source': 'import', 'updates_ytd': True,
            'count_people': 0, 'count_values': 0, 'plan_json': '[]',
            'changes_json': json.dumps([{k: c[k] for k in ('emp_id', 'field_id', 'value')}
                                        for c in clean], default=str),
            'people_count': len({l['employee_id'] for l in lines}), 'values_count': len(lines),
            'touches_bank': False, 'touches_salary': True,
            'company_id': self.env.company.id, 'updates_batch_id': batch.id,
        })
        apply_rec.name = 'RD%05d' % apply_rec.id
        Line = self.env['pb.updates.ytd.line'].sudo()
        rows = Line.create([dict(l, batch_id=batch.id, apply_id=apply_rec.id) for l in lines])
        for row in rows:
            current = ctx['current'].get((row.employee_id.id, row.figure))
            if current:
                row.replaces_id = current.id
        rows._log(_("Sent in “%s”.") % batch.name)
        apply_rec.plan_json = json.dumps([r._plan_row() for r in rows])
        payload = self.env['biz.approval.engine'].submit(apply_rec)
        apply_rec.invalidate_recordset()
        rows.invalidate_recordset()
        late = rows.filtered(lambda r: r.state == 'refused')
        for r in late:
            refused.append({'emp_id': r.employee_id.id, 'emp_name': r.employee_id.name or '',
                            'field_id': card_id(r.figure), 'field_label': r.label or r.figure,
                            'why': r.reason or ''})
        return {
            'ok': True, 'kind': GROUP, 'batch_id': batch.id, 'batch_name': batch.name,
            'apply_id': apply_rec.id, 'reference': apply_rec.name,
            'pending': not apply_rec.applied, 'approved': bool(apply_rec.applied),
            'request_id': (payload or {}).get('id') or 0,
            'with_whom': apply_rec._waiting_for(), 'route': desk._route_labels(apply_rec),
            'written': len(rows.filtered(lambda r: r.state in ('set', 'cleared'))),
            'values': len(rows), 'people': len(rows.mapped('employee_id')),
            'refused': refused, 'off_scheme': 0, 'skipped_off_scheme': 0, 'not_set': len(late),
            'covers_to': fields.Date.to_string(covers_to), 'covers_label': when,
            'tax_year': covers_to.year,
            'cleared': len(rows.filtered(lambda r: r.action == 'clear')),
            'replaced': len(rows.filtered(lambda r: r.replaces_id and r.action == 'set')),
        }

    # =================================================================
    # Past updates, undo, cancel
    # =================================================================
    @api.model
    def _ytd_state(self, batch):
        rows = batch.ytd_line_ids.sudo()
        apply_rec = rows.mapped('apply_id')[:1]
        if not rows:
            return 'cancelled', _("Cancelled"), ''
        reason = apply_rec._blocked_reason() if apply_rec else ''
        if reason:
            return 'blocked', _("Could not be made"), _("Approved, but it could not be made: %s") % reason
        states = set(rows.mapped('state'))
        if 'waiting' in states:
            return 'pending', _("Waiting for approval"), ''
        n_set = len(rows.filtered(lambda r: r.state in ('set', 'cleared')))
        n_ref = len(rows.filtered(lambda r: r.state == 'refused'))
        n_und = len(rows.filtered(lambda r: r.state == 'undone'))
        n_rep = len(rows.filtered(lambda r: r.state == 'replaced'))
        if n_set and n_und:
            return 'mixed', _("Partly undone"), ''
        if n_set and n_ref:
            return 'applied', _("Set, %s could not be set") % n_ref, ''
        if n_set:
            return 'applied', _("Set"), ''
        if n_rep and not n_und:
            return 'replaced', _("Replaced by a later update"), ''
        if n_und:
            return 'undone', _("Undone"), ''
        if states <= {'refused'}:
            return 'blocked', _("Could not be set"), ''
        if states <= {'rejected'}:
            return 'rejected', _("Turned down"), ''
        if states <= {'returned'}:
            return 'returned', _("Sent back"), ''
        return 'cancelled', _("Cancelled"), ''

    @api.model
    def _ytd_batch_row(self, batch, may_write):
        rows = batch.ytd_line_ids.sudo()
        state, label, note = self._ytd_state(batch)
        apply_rec = rows.mapped('apply_id')[:1]
        standing = rows.filtered(lambda r: r.state in ('set', 'cleared'))
        undone = rows.filtered(lambda r: r.state == 'undone').sorted('undone_at')
        used = standing.filtered(lambda r: r.state == 'set' and r._used_in())
        return {
            'id': batch.id, 'kind': GROUP, 'name': batch.name or '',
            'user': batch.user_id.display_name or '',
            'date': batch.date and batch.date.strftime('%Y-%m-%d %H:%M:%S') or '',
            'filename': batch.filename or '', 'file_id': batch.attachment_id.id or 0,
            'people': len(rows.mapped('employee_id')), 'values': len(rows),
            'rows_unmatched': batch.rows_unmatched, 'values_refused': batch.values_refused,
            'values_off_scheme': 0,
            'state': state, 'state_label': label, 'state_note': note,
            'state_reason': note if state == 'blocked' else '',
            'covers_to': fields.Date.to_string(batch.ytd_covers_to) if batch.ytd_covers_to else '',
            'covers_label': day_label(self.env, batch.ytd_covers_to) if batch.ytd_covers_to else '',
            'tax_year': batch.ytd_covers_to.year if batch.ytd_covers_to else 0,
            'with_whom': apply_rec._waiting_for() if apply_rec and state == 'pending' else '',
            'can_undo': bool(may_write and self._ytd_may_read() and (standing - used)),
            'can_cancel': bool(may_write and apply_rec and apply_rec.state == 'pending'
                               and not apply_rec.applied
                               and apply_rec.with_env(self.env)._may_cancel()),
            'has_open': False, 'scheduled': [], 'recorded': [],
            'set_values': len(standing), 'used_values': len(used),
            'not_set': len(rows.filtered(lambda r: r.state == 'refused')),
            'not_set_lines': [{'who': r.employee_id.name or '', 'type': r.label or '',
                               'why': r.reason or ''}
                              for r in rows.filtered(lambda r: r.state == 'refused')[:20]],
            'undone_values': len(undone),
            'undone_by': undone[-1:].undone_by_id.display_name or '' if undone else '',
            'undone_date': undone[-1:].undone_at.strftime('%Y-%m-%d %H:%M:%S')
            if undone and undone[-1:].undone_at else '',
            'cancelled_values': len(rows.filtered(lambda r: r.state == 'cancelled')),
            'cancelled_by': '', 'cancelled_date': '',
        }

    @api.model
    def _batch_row(self, batch, may_write):
        if batch.kind == GROUP:
            return self._ytd_batch_row(batch, may_write)
        return super()._batch_row(batch, may_write)

    @api.model
    def _ytd_batch(self, batch_id):
        try:
            bid = int(batch_id or 0)
        except (TypeError, ValueError):
            bid = 0
        return self.env['pb.updates.batch'].search(
            [('id', '=', bid), ('company_id', 'in', self.env.companies.ids),
             ('state', '!=', 'draft'), ('kind', '=', GROUP)], limit=1)

    @api.model
    def _ytd_undo_rows(self, rows, apply_rec=None):
        rows = rows.sudo()
        undone, kept = rows._undo_rows()
        source = apply_rec or rows.mapped('apply_id')[:1]
        if source and source.applied and not source.undone and undone and not \
                source.ytd_line_ids.filtered(lambda r: r.state in ('set', 'cleared')):
            source.sudo().write({'undone': True, 'undone_date': fields.Datetime.now(),
                                 'undone_by_id': self.env.uid})
        bits = []
        if undone:
            bits.append(_("1 figure was taken back.") if undone == 1 else
                        _("%s figures were taken back.") % undone)
        if len(kept) == 1:
            bits.append(_("1 stays: %s") % kept[0])
        elif kept:
            bits.append(_("%(n)s stay. %(first)s", n=len(kept), first=kept[0]))
        if not undone:
            return {'ok': False, 'msg': ' '.join(bits) or _(
                "Nothing in this update can be undone."), 'kept': kept}
        return {'ok': True, 'restored': undone, 'skipped_changed_since': len(kept),
                'skipped_missing': 0, 'kept': kept, 'msg': ' '.join(bits)}

    @api.model
    def undo(self, batch_id=0, apply_id=0):
        if batch_id and not apply_id:
            batch = self._ytd_batch(batch_id)
            if batch:
                desk = self._ytd_gate()
                if not self._ytd_may_send(desk):
                    return {'ok': False, 'msg': _(
                        "Undoing year-to-date figures needs permission to change employee "
                        "records.")}
                rows = batch.ytd_line_ids
                if rows.filtered(lambda r: r.state == 'waiting'):
                    return {'ok': False, 'msg': _(
                        "This update is still waiting for approval, so there is nothing to "
                        "undo yet.")}
                answer = self._ytd_undo_rows(rows)
                answer.update(batch_id=batch.id, name=batch.name)
                return answer
        return super().undo(batch_id=batch_id, apply_id=apply_id)

    @api.model
    def cancel(self, batch_id=0, apply_id=0):
        if batch_id and not apply_id:
            batch = self._ytd_batch(batch_id)
            if batch:
                desk = self._ytd_gate()
                if not self._can_write(desk):
                    return {'ok': False, 'msg': _(
                        "Cancelling an update needs permission to change employee records.")}
                apply_rec = batch.ytd_line_ids.mapped('apply_id')[:1]
                if not apply_rec or apply_rec.applied or apply_rec.state != 'pending':
                    return {'ok': False, 'msg': _(
                        "Nothing in this update is waiting for approval, so there is nothing "
                        "to cancel.")}
                waiting = len(batch.ytd_line_ids.filtered(lambda r: r.state == 'waiting'))
                res = desk.cancel_apply(apply_rec.id)
                if not res.get('ok'):
                    return res
                return {'ok': True, 'cancelled': 1, 'values': waiting, 'batch_id': batch.id,
                        'name': batch.name,
                        'msg': _("1 figure cancelled before it was set.") if waiting == 1 else
                        _("%s figures cancelled before they were set.") % waiting}
        return super().cancel(batch_id=batch_id, apply_id=apply_id)

    # =================================================================
    # The dispatchers: kind='ytd'
    # =================================================================
    @api.model
    def read_columns(self, file_b64='', filename='', kind='lasting', month=None, cutover=None):
        if kind == GROUP:
            return self._ytd_read_columns(file_b64, filename, cutover)
        return super().read_columns(file_b64, filename, kind, month, cutover)

    @api.model
    def review(self, file_b64='', filename='', columns=None, kind='lasting', month=None,
               cutover=None):
        if kind == GROUP:
            return self._ytd_review(file_b64, filename, columns, cutover)
        return super().review(file_b64, filename, columns, kind, month, cutover)

    @api.model
    def recheck(self, changes=None, kind='lasting', month=None, cutover=None):
        if kind == GROUP:
            return self._ytd_recheck(changes, cutover)
        return super().recheck(changes, kind, month, cutover)

    @api.model
    def apply(self, name='', file_b64='', filename='', columns=None, changes=None, stats=None,
              start_date=None, hold_scope='pay', kind='lasting', month=None, draft_id=0,
              joiners=None, cutover=None):
        if kind == GROUP:
            return self._ytd_apply(name, file_b64, filename, columns, changes, stats,
                                   cutover, draft_id=draft_id)
        answer = super().apply(name=name, file_b64=file_b64, filename=filename, columns=columns,
                               changes=changes, stats=stats, start_date=start_date,
                               hold_scope=hold_scope, kind=kind, month=month,
                               draft_id=draft_id, joiners=joiners, cutover=cutover)
        # UPDATES P5 (P6 deviation 1) — a bank part nobody else can approve
        # yet carries the way out on the Done screen too.
        for lane in (answer.get('lanes') or []) if isinstance(answer, dict) else []:
            if lane.get('lane') == 'bank' and lane.get('pending') and not lane.get('with_whom'):
                rec = self.env['pb.records.apply'].sudo().browse(
                    int(lane.get('apply_id') or 0)).exists()
                if rec and rec.approval_request_id:
                    lane['fix'] = self._way_out(request=rec.approval_request_id)
        return answer

    @api.model
    def save_draft(self, draft_id=0, kind='lasting', month=None, filename='',
                   file_b64='', columns=None, choices=None, step=''):
        if kind != GROUP:
            return super().save_draft(draft_id=draft_id, kind=kind, month=month,
                                      filename=filename, file_b64=file_b64, columns=columns,
                                      choices=choices, step=step)
        if not self._ytd_may_read():
            return {'ok': False, 'quiet': True}
        answer = super().save_draft(draft_id=draft_id, kind='lasting', month=None,
                                    filename=filename, file_b64=file_b64, columns=columns,
                                    choices=choices, step=step)
        if answer.get('ok'):
            draft = self._own_draft(answer['draft_id'])
            day, _why = self._ytd_cover(month) if month else (None, '')
            if draft:
                draft.write({'kind': GROUP, 'ytd_covers_to': day or False})
        return answer

    @api.model
    def _draft_row(self, draft):
        row = super()._draft_row(draft)
        if draft.kind == GROUP:
            row.update(kind=GROUP,
                       covers_to=fields.Date.to_string(draft.ytd_covers_to) if draft.ytd_covers_to else '',
                       covers_label=day_label(self.env, draft.ytd_covers_to) if draft.ytd_covers_to else '')
        return row

    # =================================================================
    # The year-to-date view
    # =================================================================
    @api.model
    def _ytd_view_people(self, year, search=''):
        """Ids of everyone visible with a figure before Payobook in `year`, or a
        finished payslip in it — the view's rows, in name order."""
        desk = self._desk()
        visible = desk._matching({}, ctx={})
        if not visible:
            return []
        self.env['pb.updates.ytd.line']._flush_for_sql()
        cr = self.env.cr
        cr.execute("""
            SELECT employee_id FROM pb_updates_ytd_line
             WHERE state = 'set' AND tax_year = %s AND employee_id = ANY(%s)
            UNION
            SELECT employee_id FROM hr_payslip
             WHERE state IN %s AND date_to >= %s AND date_to <= %s AND employee_id = ANY(%s)
        """, [year, visible.ids, DONE_SLIP_STATES, first_of_year(year), last_of_year(year),
              visible.ids])
        ids = {r[0] for r in cr.fetchall()}
        emps = self.env['hr.employee'].sudo().browse(sorted(ids))
        search = (search or '').strip().lower()
        if search:
            emps = emps.filtered(lambda e: search in (e.name or '').lower()
                                 or search in str(e.barcode or e.employee_id or '').lower())
        self.env.cr.execute(
            "SELECT DISTINCT employee_id FROM pb_updates_ytd_line WHERE state = 'set' AND tax_year = %s "
            "AND employee_id = ANY(%s)", [year, emps.ids or [0]])
        before = {r[0] for r in self.env.cr.fetchall()}
        # People with figures before Payobook first, then everyone by name.
        return emps.sorted(lambda e: (e.id not in before, (e.name or '').lower(), e.id)).ids

    @api.model
    def _ytd_rows(self, year, emp_ids, detail=None):
        """Per person and figure: before / paid / total, the date the figures
        cover up to, and the months with no finished month-end payslip.

        "Paid in Payobook" is `pb.updates.ytd.line`'s one computation
        (`_ledger` › `_person_window` › `_figure_paid`, UPDATES P5c): a total
        only when every finished payslip that should carry the figure does,
        signs as the pay engine stores them, and each month counted once
        (a mid-month advance is never added to its month-end payslip).
        `detail` = `(emp_id, key)` keeps the payslip list of that one cell for
        "How this number was worked out"."""
        Line = self.env['pb.updates.ytd.line'].sudo()
        Month = self.env['pb.updates.oneoff']
        emps = self.env['hr.employee'].sudo().browse(emp_ids)
        figures = self._ytd_figures(sorted(set(emps.mapped('company_id').ids)))
        # Words are worked out once per call (a whole-roster download formats
        # tens of thousands of cells; G14's lesson).
        labels = self.env.context.get('pb_ytd_labels')
        if labels is None:
            labels = {}
            self = self.with_context(pb_ytd_labels=labels)
        lines = Line.search([('employee_id', 'in', emps.ids), ('tax_year', '=', year),
                             ('state', '=', 'set')])
        by = {}
        for line in lines:
            by.setdefault(line.employee_id.id, {})[line.figure] = line
        codes_by_company = {}
        for company in emps.mapped('company_id'):
            codes_by_company[company.id] = {k: ([] if f['count'] else Line._figure_codes(company, k))
                                            for k, f in figures.items()}
        all_codes = sorted({c for d in codes_by_company.values() for cs in d.values() for c in cs})
        ledger = Line._ledger(emps.ids, first_of_year(year), last_of_year(year), all_codes)
        has_doj = 'date_of_joining' in emps._fields
        rows, kept = [], None
        for emp in emps:
            mine = by.get(emp.id, {})
            covers = max((l.covers_to for l in mine.values()), default=None)
            cur = emp.company_id.currency_id
            codes = codes_by_company.get(emp.company_id.id) or {}
            windows = {}

            def window_for(day):
                if day not in windows:
                    windows[day] = Line._person_window(ledger, emp.id, day)
                return windows[day]

            row_window = window_for(covers)
            counted_months = sorted(row_window['months'])
            latest = counted_months[-1] if counted_months else None
            # Where the year is covered from: the day after the figures before
            # Payobook end; without figures, 1 January (or the month the person
            # joined, when the employee record says so).
            joined = emp.date_of_joining if has_doj else False
            if covers:
                cover_from = month_floor(covers + timedelta(days=1))
            else:
                cover_from = first_of_year(year)
                if joined and joined.year == year:
                    cover_from = month_floor(joined)
            start_missing = []
            if not covers and counted_months and counted_months[0] > cover_from:
                start_missing = months_between(cover_from, counted_months[0] - timedelta(days=1))
            first_month = cover_from if covers else (counted_months[0] if counted_months else None)
            missing = [m for m in months_between(first_month, latest)
                       if m not in row_window['months']] if first_month and latest else []
            row_open = bool(missing or start_missing)
            twice = sorted({r['month'] for r in row_window['twice']})
            row_bits = self._ytd_row_bits(missing, start_missing, twice)
            cells = {}
            for key, f in figures.items():
                if f['company_id'] and f['company_id'] != emp.company_id.id:
                    continue
                line = mine.get(key)
                own_covers = line.covers_to if line else covers
                window = window_for(own_covers)
                before = float(line.amount) if line else 0.0
                if f['count']:
                    months = Line._months_paid(window, own_covers)
                    res = {'state': 'none' if not window['counted'] else 'complete',
                           'paid': float(len(months)), 'have': 0, 'expected': 0,
                           'below_zero': [], 'advance': 0.0, 'amounts': {}}
                    if window['overlap']:
                        res['state'] = 'overlap'
                else:
                    res = Line._figure_paid(ledger, window, codes.get(key) or [])
                paid = res['paid']
                state = res['state']
                counted = state != 'unknown'
                total = before + paid
                year_total = state in ('complete', 'none') and not row_open
                if state == 'none' and not line:
                    year_total = False
                note = self._ytd_cell_note(f, res, own_covers, row_bits, cur) \
                    if (line or window['counted']) else ''
                cells[key] = {
                    'before': before, 'paid': paid, 'total': total, 'has_before': bool(line),
                    'before_label': Line._value_label(key, before, cur) if line else '',
                    'paid_label': Line._value_label(key, paid, cur) if counted and (
                        paid or window['counted']) else '',
                    'total_label': Line._value_label(key, total, cur) if (
                        line or (counted and window['counted'])) else '',
                    'counted': counted,
                    'source': line.source_note or '' if line else '',
                    # UPDATES P5c
                    'state': state, 'have': res['have'], 'expected': res['expected'],
                    'year_total': bool(year_total), 'note': note,
                    'chip': self._ytd_cell_chip(dict(res, before_set=bool(line))),
                    'below_zero': bool(res['below_zero']),
                    'below_note': self._ytd_below_note(res['below_zero']),
                    'advance': res['advance'],
                    'advance_label': Line._value_label(key, res['advance'], cur)
                    if state == 'split' and res['advance'] else '',
                    'detail': state != 'unknown' and bool(window['rows']),
                }
                if detail and detail == (emp.id, key):
                    kept = {'window': window, 'res': res, 'figure': f, 'line': line,
                            'covers': own_covers, 'currency': cur, 'emp': emp,
                            'codes': codes.get(key) or [], 'cell': cells[key]}
            rows.append({
                'emp_id': emp.id, 'name': emp.name or '', 'code': emp.barcode or emp.employee_id or '',
                'company': emp.company_id.name or '',
                'covers_to': fields.Date.to_string(covers) if covers else '',
                'covers_label': day_label(self.env, covers) if covers else '',
                'missing': len(missing),
                'missing_labels': [self._ytd_month(m) for m in missing][:12],
                'start_missing': len(start_missing),
                'start_label': self._ytd_span_label(start_missing),
                'twice_labels': [self._ytd_month(m) for m in twice][:6],
                'latest': self._ytd_month(latest) if latest else '',
                'cells': cells,
            })
        if detail is not None:
            return figures, rows, kept
        return figures, rows

    @api.model
    def _ytd_memo(self, key, make):
        labels = self.env.context.get('pb_ytd_labels')
        if labels is None:
            return make()
        if key not in labels:
            labels[key] = make()
        return labels[key]

    @api.model
    def _ytd_month(self, month):
        return self._ytd_memo(('m', month),
                              lambda: self.env['pb.updates.oneoff']._month_label(month))

    @api.model
    def _ytd_span_label(self, months):
        """"January to March 2026", "June 2026" or ''."""
        if not months:
            return ''
        if len(months) == 1:
            return self._ytd_month(months[0])
        return self._ytd_memo(('span', months[0], months[-1]), lambda: _(
            "%(first)s to %(last)s", first=self._ytd_month(months[0]),
            last=self._ytd_month(months[-1])))

    @api.model
    def _ytd_row_bits(self, missing, start_missing, twice):
        """The parts of a cell's sentence that belong to the whole row, worked
        out once per person: `(start, missing, twice)`."""
        start = self._ytd_memo(('start', tuple(start_missing)), lambda: _(
            "Incomplete: no figures before Payobook for %s") % self._ytd_span_label(
                start_missing)) if start_missing else ''
        gaps = self._ytd_memo(('gap', tuple(missing[:4])), lambda: _(
            "Incomplete: no finished payslip for %s") % ', '.join(
                self._ytd_month(m) for m in missing[:4])) if missing else ''
        both = self._ytd_memo(('twice', tuple(twice[:3])), lambda: _(
            "Two finished payslips of the same pay scheme and pay period in %s, both "
            "counted") % ', '.join(self._ytd_month(m) for m in twice[:3])) if twice else ''
        return start, gaps, both

    @api.model
    def _ytd_cell_chip(self, res):
        """The amber chip on a cell whose sum is not a total, or ''."""
        state = res['state']
        if state == 'partial':
            return _("%(have)s of %(n)s payslips have this figure", have=res['have'],
                     n=res['expected'])
        if state == 'overlap':
            return _("A payslip overlaps the figures before Payobook")
        if state == 'split':
            return _("Mid-month advance shown apart")
        if state == 'unknown' and res.get('before_set'):
            return _("Paid in Payobook not known")
        return ''

    @api.model
    def _ytd_below_note(self, months):
        if not months:
            return ''
        return self._ytd_memo(('below', tuple(months[:3])), lambda: _(
            "Includes a month below zero (%s)") % ', '.join(
                self._ytd_month(m) for m in months[:3]))

    @api.model
    def _ytd_cell_note(self, fig, res, covers, row_bits, currency):
        """One plain sentence for the cell and the download's check column:
        "Complete", or why the amount is not a year total."""
        Line = self.env['pb.updates.ytd.line']
        bits = []
        state = res['state']
        if state == 'unknown':
            bits.append(self._ytd_memo('unknown', lambda: _(
                "Not known: none of the finished payslips has the pay items that make up this "
                "figure, or none is chosen in Set up")))
        elif state == 'partial':
            bits.append(_("Incomplete: %(have)s of %(n)s payslips have this figure",
                          have=res['have'], n=res['expected']))
        elif state == 'overlap':
            bits.append(_("Incomplete: a payslip overlaps the figures before Payobook (up to "
                          "%s)") % day_label(self.env, covers))
        elif state == 'split':
            bits.append(_("Incomplete: a mid-month advance could not be matched to its "
                          "month-end payslip (shown apart: %s)") % Line._value_label(
                              fig['key'], res['advance'], currency))
        start, gaps, both = row_bits
        bits += [b for b in (start, gaps) if b]
        if res['below_zero']:
            bits.append(self._ytd_below_note(res['below_zero']))
        if both and not fig['count']:
            bits.append(both)
        if not bits:
            return self._ytd_memo('complete', lambda: _("Complete"))
        return ' · '.join(bits)

    @api.model
    def get_ytd_view(self, year=None, search='', offset=0, limit=VIEW_PAGE):
        self._ytd_gate()
        today = self._ytd_today()
        try:
            year = int(year or today.year)
        except (TypeError, ValueError):
            year = today.year
        if year not in (today.year, today.year - 1):
            year = today.year
        ids = self._ytd_view_people(year, search)
        try:
            offset, limit = max(0, int(offset or 0)), max(1, min(200, int(limit or VIEW_PAGE)))
        except (TypeError, ValueError):
            offset, limit = 0, VIEW_PAGE
        page = ids[offset:offset + limit]
        figures, rows = self._ytd_rows(year, page)
        Line = self.env['pb.updates.ytd.line'].sudo()
        with_before = Line.search_count([('employee_id', 'in', ids), ('tax_year', '=', year),
                                         ('state', '=', 'set')]) if ids else 0
        self.env.cr.execute(
            "SELECT count(DISTINCT employee_id) FROM pb_updates_ytd_line WHERE state='set' "
            "AND tax_year=%s AND employee_id = ANY(%s)", [year, ids or [0]])
        people_before = self.env.cr.fetchone()[0] or 0
        schemes = []
        for config in self.env['pb.updates.ytd.map'].sudo().search(
                [('company_id', 'in', self.env.companies.ids)]).mapped('config_id'):
            schemes.append({'id': config.id, 'name': config.name or '',
                            'application': bool(getattr(config, 'application_data_enabled', False))})
        uncounted = [f['label'] for k, f in figures.items()
                     if not f['count'] and not Line._figure_codes(self.env.company, k)]
        return {
            'ok': True, 'year': year, 'this_year': today.year, 'last_year': today.year - 1,
            'search': search or '', 'offset': offset, 'limit': limit, 'total': len(ids),
            'figures': [{'key': f['key'], 'label': f['label'], 'count': f['count'],
                         'item': f['item']} for f in figures.values()],
            'rows': rows, 'people_before': people_before, 'figures_before': with_before,
            'missing_people': sum(1 for r in rows if r['missing']),
            # UPDATES P5c — people on this page with a figure that is not a
            # year total yet (incomplete, overlapping, an advance shown apart).
            'open_people': sum(1 for r in rows if any(
                c.get('total_label') and not c.get('year_total') and c.get('state') not in
                ('complete', 'none') for c in r['cells'].values())),
            'schemes': schemes, 'uncounted': uncounted,
            'may_setup': self._ytd_may_setup(),
            'months': self._ytd_months(today),
        }

    @api.model
    def get_ytd_cell_detail(self, year=None, emp_id=0, key=''):
        """UPDATES P5c — "How this number was worked out": the payslips one
        "paid in Payobook" cell counted (pay run, pay period, amount) and the
        ones it did not count, with why. Asked for one cell at a time, so the
        view itself stays one fast page."""
        self._ytd_gate()
        today = self._ytd_today()
        try:
            year = int(year or today.year)
            emp_id = int(emp_id or 0)
        except (TypeError, ValueError):
            return {'ok': False, 'msg': _("This figure could not be read. Try again.")}
        if year not in (today.year, today.year - 1) or not emp_id or not \
                self._desk()._matching({'employee_ids': [emp_id]}, ctx={}):
            return {'ok': False, 'msg': _("This figure could not be read. Try again.")}
        figures, rows, kept = self._ytd_rows(year, [emp_id], detail=(emp_id, str(key or '')))
        if not kept:
            return {'ok': False, 'msg': _("This figure could not be read. Try again.")}
        Line = self.env['pb.updates.ytd.line']
        Month = self.env['pb.updates.oneoff']
        f, res, window, cur = kept['figure'], kept['res'], kept['window'], kept['currency']
        why = {
            'before': _("Already in the figures before Payobook (up to %s)")
            % day_label(self.env, kept['covers']),
            'advance': _("Mid-month advance: the month-end payslip carries the whole month and "
                         "takes the advance back off, so it is not added"),
            'advance_only': _("Mid-month advance: the month-end payslip is not finished yet, so "
                              "the month is not counted"),
            'split': _("Mid-month advance that could not be matched to its month-end payslip: "
                       "shown apart, not added"),
            'overlap': _("Overlaps the figures before Payobook (up to %s), so it is not added")
            % day_label(self.env, kept['covers']),
        }
        counted, left = [], []
        months_floor = month_floor(kept['covers']) if kept['covers'] else None
        for r in window['rows']:
            amount = res['amounts'].get(r['id'])
            item = {
                'id': r['id'], 'run': r['run'] or '',
                'period': _("%(start)s to %(end)s", start=day_label(self.env, r['date_from']),
                            end=day_label(self.env, r['date_to'])),
                'month': Month._month_label(r['month']),
                'amount': '' if f['count'] else (
                    Line._value_label(f['key'], amount, cur) if amount is not None else ''),
                'below': bool(amount is not None and amount < 0),
            }
            if r['state'] == 'counted':
                if f['count']:
                    in_months = not months_floor or r['month'] > months_floor
                    item['why'] = '' if in_months else _(
                        "Its month is already in the figures before Payobook")
                elif amount is None:
                    item['why'] = _("Does not have this figure")
                    item['missing'] = True
                else:
                    item['why'] = ''
                counted.append(item)
            else:
                item['why'] = why.get(r['state'], '')
                left.append(item)
        cell = kept['cell']
        names = {}
        if kept['codes']:
            for rec in self.env['hr.formula.rule'].sudo().search_read(
                    [('code', 'in', kept['codes']),
                     ('config_id.company_id', '=', kept['emp'].company_id.id)], ['code', 'name']):
                names.setdefault(rec['code'], rec['name'] or rec['code'])
        return {
            'ok': True, 'emp': kept['emp'].name or '', 'figure': f['label'], 'count': f['count'],
            'year': year, 'before_label': cell['before_label'], 'paid_label': cell['paid_label'],
            'total_label': cell['total_label'], 'year_total': cell['year_total'],
            'note': cell['note'], 'state': cell['state'],
            'items': [names.get(c) or c for c in kept['codes']], 'counted': counted, 'left': left,
            'covers_label': day_label(self.env, kept['covers']) if kept['covers'] else '',
        }

    @api.model
    def _ytd_months(self, today):
        out = []
        first = month_floor(today)
        for offset in range(-3, 3):
            month = first
            if offset < 0:
                for _i in range(-offset):
                    month = month_floor(month - timedelta(days=1))
            else:
                for _i in range(offset):
                    month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
            out.append({'value': fields.Date.to_string(month),
                        'label': self.env['pb.updates.oneoff']._month_label(month),
                        'current': offset == 0})
        return out

    @api.model
    def download_ytd_view(self, year=None, search=''):
        """The view as a sheet: one row per person, three columns per figure."""
        self._ytd_gate()
        desk = self._desk()
        if not desk._may_export():
            return {'ok': False, 'msg': _(
                "Downloading needs permission to export employee records. Ask an administrator.")}
        today = self._ytd_today()
        year = int(year or today.year)
        ids = self._ytd_view_people(year, search)[:MAX_ROWS]
        figures, rows = self._ytd_rows(year, ids)
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = _("Year to date")[:31]
        bold = Font(bold=True, color='241F52')
        fill = PatternFill('solid', fgColor='EEEBFA')
        heads = [_("Employee code"), _("Employee name"), _("Figures before Payobook cover up to"),
                 _("Months with no finished payslip")]
        for f in figures.values():
            # UPDATES P5c — a fourth column per figure says whether the total
            # is complete; an incomplete one is never written as a bare total.
            heads += [_("%s · before Payobook") % f['label'], _("%s · paid in Payobook") % f['label'],
                      _("%s · total") % f['label'], _("%s · complete?") % f['label']]
        ws.append(heads)
        for cell in ws[1]:
            cell.font, cell.fill = bold, fill
            cell.alignment = Alignment(wrap_text=True, vertical='center')
        for r in rows:
            values = [r['code'], r['name'], r['covers_label'], r['missing'] or '']
            for key in figures:
                c = r['cells'].get(key)
                if not c:
                    values += ['', '', '', '']
                    continue
                values += [c['before'] if c['has_before'] else '',
                           c['paid'] if c['counted'] else '',
                           c['total'] if c['year_total'] else '',
                           c['note'] or '']
            ws.append(values)
        ws.freeze_panes = 'C2'
        out = io.BytesIO()
        wb.save(out)
        return {'ok': True, 'file_b64': base64.b64encode(out.getvalue()).decode(),
                'filename': _("%(product)s year to date %(year)s.xlsx") % {
                    'product': product_label(self.env), 'year': year},
                'mimetype': XLSX_MIME, 'rows': len(rows)}

    @api.model
    def download_for_payrun(self, config_id=0, month=None):
        """The mapped pay items of one scheme, with what a payslip of `month`
        would receive, per person. For a run from application data this is the
        way in: its inputs are certified there and never fed from here."""
        self._ytd_gate()
        desk = self._desk()
        if not desk._may_export():
            return {'ok': False, 'msg': _(
                "Downloading needs permission to export employee records. Ask an administrator.")}
        config = self.env['hr.formula.config'].sudo().search(
            [('id', '=', int(config_id or 0)), ('company_id', 'in', self.env.companies.ids)], limit=1)
        if not config:
            return {'ok': False, 'msg': _("Pick a pay scheme.")}
        maps = self.env['pb.updates.ytd.map'].sudo().search([('config_id', '=', config.id)])
        if not maps:
            return {'ok': False, 'msg': _(
                "No pay item of %s receives a year-to-date figure yet. Choose one in Set up "
                "first.") % (config.name or '')}
        try:
            start = month_floor(fields.Date.to_date(month)) if month else month_floor(self._ytd_today())
        except (TypeError, ValueError):
            start = month_floor(self._ytd_today())
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        Line = self.env['pb.updates.ytd.line'].sudo()
        with_figures = Line.search([('tax_year', '=', end.year), ('state', '=', 'set'),
                                    ('company_id', '=', config.company_id.id)]).mapped('employee_id')
        # UPDATES P5c — everyone the scheme pays this month is listed, people
        # without figures before Payobook too (with a sentence instead of a
        # value), so nobody is left out of the sheet without a word.
        everyone = desk._matching({}, ctx={}).filtered(
            lambda e: e.company_id == config.company_id)
        visible = set(everyone.ids) | set(desk._matching(
            {'employee_ids': with_figures.ids}, ctx={}).ids)
        cycle = config.cycle_type if config.cycle_type in ('mid_cycle', 'end_cycle') else 'any'
        answers = self.env['pb.scheme.map'].sudo().resolve_many(
            sorted(visible), cycle, on_date=fields.Date.to_string(start)) if visible else {}
        people = self.env['hr.employee'].sudo().browse(sorted(visible)).filtered(
            lambda e: (answers.get(e.id) or {}).get('config_id') == config.id).sorted(
            lambda e: (e.id not in with_figures.ids, (e.name or '').lower(), e.id))
        has_figures = set(with_figures.ids)
        names = {r.code: r.name for r in config.rule_ids if r.code}
        items = list(dict.fromkeys(maps.mapped('code')))
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = _("For the pay run")[:31]
        bold = Font(bold=True, color='241F52')
        fill = PatternFill('solid', fgColor='EEEBFA')
        ws.append([_("Employee code"), _("Employee name")] +
                  ['%s (%s)' % (names.get(c) or c, c) for c in items] + [_("Check")])
        adj = wb.create_sheet(title=_("Monthly adjustments")[:31])
        adj.append(['employee_id/.id', 'config_id/.id', 'component_id/.id', 'date_from', 'date_to',
                    'value_decimal', 'unit', 'reason', 'evidence_reference',
                    _("Employee name"), _("Pay item")])
        rule_ids = {r.code: r for r in config.rule_ids if r.code}
        gaps = 0
        for emp in people:
            plan = Line._plan_for_slip(emp, config, start, end) if emp.id in has_figures else {}
            row = [emp.barcode or emp.employee_id or '', emp.name or '']
            notes = []
            if emp.id not in has_figures:
                notes.append(_("No figures before Payobook for %s, so nothing is worked out. If "
                               "this person joined this year, load 0 for each figure so paid in "
                               "Payobook can be counted.") % end.year)
            for code in items:
                info = plan.get(code)
                if not info:
                    row.append('')
                    continue
                item = names.get(code) or code
                blocked = Line._plan_blocked(info)
                if info['gap']:
                    notes.append(_("%s: months with no finished payslip") % item)
                elif info.get('incomplete') == 'overlap':
                    notes.append(_("%s: a payslip overlaps the figures before Payobook") % item)
                elif info.get('incomplete') == 'split':
                    notes.append(_("%s: a mid-month advance could not be matched to its month-end "
                                   "payslip") % item)
                elif info.get('unknown'):
                    notes.append(_("%s: paid in Payobook cannot be worked out — choose its pay items in "
                                   "Set up") % item)
                elif info.get('incomplete') == 'partial':
                    notes.append(_("%(item)s: only %(have)s of %(n)s finished payslips have this "
                                   "figure, so the sum would be too low", item=item,
                                   have=info.get('have', 0), n=info.get('expected', 0)))
                if info.get('twice') and not blocked and not self.env[
                        'pb.updates.ytd.line']._is_count(info['figure']):
                    notes.append(_("%(item)s: two finished payslips of the same pay scheme and pay "
                                   "period in %(months)s, both counted — check one is not a test",
                                   item=item, months=', '.join(
                                       self.env['pb.updates.oneoff']._month_label(
                                           fields.Date.to_date(m)) for m in info['twice'][:3])))
                if info.get('below_zero') and not blocked:
                    notes.append(_("%(item)s: includes a month below zero (%(months)s)", item=item,
                                   months=', '.join(self.env['pb.updates.oneoff']._month_label(
                                       fields.Date.to_date(m)) for m in info['below_zero'][:3])))
                # A value that cannot be worked out is left blank — never a
                # number that looks like a total (P5c).
                row.append('' if blocked else info['value'])
                rule = rule_ids.get(code)
                if rule and not blocked:
                    kind = rule.value_kind or 'money'
                    adj.append([emp.id, config.id, rule.id, fields.Date.to_string(start),
                                fields.Date.to_string(end), number_text(info['value']),
                                'money' if kind == 'money' else 'number',
                                _("Year-to-date figures from Updates: %(before)s before Payobook "
                                  "(up to %(date)s) + %(paid)s paid in Payobook.",
                                  before=number_text(info['before']),
                                  date=day_label(self.env, fields.Date.to_date(info['covers_to'])),
                                  paid=number_text(info['paid'])),
                                _("Updates year-to-date figures"), emp.name or '',
                                names.get(code) or code])
            if any(Line._plan_blocked(i) for i in plan.values()) or emp.id not in has_figures:
                gaps += 1
            row.append(' · '.join(notes) or _("Ready"))
            ws.append(row)
        for sheet in (ws, adj):
            for cell in sheet[1]:
                cell.font, cell.fill = bold, fill
                cell.alignment = Alignment(wrap_text=True, vertical='center')
        guide = wb.create_sheet(title=_("Read me")[:31])
        guide.column_dimensions['A'].width = 110
        app = bool(getattr(config, 'application_data_enabled', False))
        for idx, text in enumerate([
                _("%(scheme)s · pay period %(from)s to %(to)s", scheme=config.name or '',
                  **{'from': day_label(self.env, start), 'to': day_label(self.env, end)}),
                _("“For the pay run”: one column per pay item that receives a year-to-date "
                  "figure, with the value a payslip of this pay period receives (before Payobook "
                  "plus paid in Payobook, as chosen in Set up)."),
                _("A run from application data takes these pay items from Monthly adjustments. "
                  "The “Monthly adjustments” sheet has one row per person and pay item, in the "
                  "columns the Monthly adjustments list imports; each one still needs approving "
                  "there, as today.") if app else
                _("A run with a pay data file: copy these columns into the file, or leave them "
                  "out — the pay run fills them by itself, and stops and asks when the file has a "
                  "different number."),
                _("“Check” says “Ready”, or why a pay item cannot be worked out: a month with no "
                  "finished payslip, payslips that do not all have the figure, a payslip that "
                  "overlaps the figures before Payobook, or a mid-month advance that cannot be "
                  "matched. Those values are left blank and out of “Monthly adjustments”."),
                _("Nothing here changes how tax is calculated.")], start=1):
            cell = guide.cell(row=idx, column=1, value=text)
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if idx == 1:
                cell.font = bold
        out = io.BytesIO()
        wb.save(out)
        return {'ok': True, 'file_b64': base64.b64encode(out.getvalue()).decode(),
                'filename': _("%(product)s year to date for %(scheme)s %(month)s.xlsx") % {
                    'product': product_label(self.env), 'scheme': config.name or '',
                    'month': start.strftime('%Y-%m')},
                'mimetype': XLSX_MIME, 'rows': len(people), 'gaps': gaps,
                'application': app}

    # =================================================================
    # Set up (payroll manager)
    # =================================================================
    @api.model
    def _ytd_setup_gate(self):
        self._ytd_gate()
        if not self._ytd_may_setup():
            raise AccessError(_("Setting up year-to-date figures needs a payroll manager role."))

    @api.model
    def get_ytd_setup(self):
        self._ytd_gate()
        company = self.env.company
        Line = self.env['pb.updates.ytd.line'].sudo()
        configs = self.env['hr.formula.config'].sudo().search(
            [('company_id', 'in', self.env.companies.ids), ('state', '=', 'active')], order='name')
        items, inputs = {}, {}
        for config in configs:
            for rule in config.rule_ids.sorted('sequence'):
                code = (rule.code or '').strip()
                if not code:
                    continue
                kind = rule.value_kind or 'money'
                if kind in ('money', 'quantity', 'integer') and code not in items:
                    items[code] = {'code': code, 'label': rule.name or code}
                if rule.column_type == 'input' and kind in ('money', 'integer', 'quantity'):
                    inputs.setdefault(config.id, []).append(
                        {'code': code, 'label': rule.name or code, 'kind': kind})
        figures = []
        for key, f in self._ytd_figures([company.id]).items():
            codes = Line._figure_codes(company, key) if not f['count'] else []
            figures.append({'key': key, 'label': f['label'], 'count': f['count'], 'item': f['item'],
                            'codes': [{'code': c, 'label': (items.get(c) or {}).get('label') or c}
                                      for c in codes]})
        maps = self.env['pb.updates.ytd.map'].sudo().search(
            [('company_id', 'in', self.env.companies.ids)])
        basis = dict(self.env['pb.updates.ytd.map']._fields['basis']._description_selection(self.env))
        schemes = []
        for config in configs:
            mine = maps.filtered(lambda m: m.config_id == config)
            if not inputs.get(config.id) and not mine:
                continue
            schemes.append({
                'id': config.id, 'name': config.name or '',
                'application': bool(getattr(config, 'application_data_enabled', False)),
                'inputs': inputs.get(config.id, []),
                'maps': [{'id': m.id, 'code': m.code, 'figure': m.figure, 'basis': m.basis,
                          'basis_label': basis.get(m.basis, m.basis),
                          'item_label': next((i['label'] for i in inputs.get(config.id, [])
                                              if i['code'] == m.code), m.code),
                          'figure_label': Line._figure_label(m.figure, config.company_id),
                          'by': m.set_by_id.name or ''} for m in mine],
            })
        return {'ok': True, 'may_setup': self._ytd_may_setup(), 'figures': figures,
                'items': sorted(items.values(), key=lambda i: i['label'].lower()),
                'schemes': schemes,
                'bases': [{'value': b, 'label': basis.get(b, b)} for b in BASES]}

    @api.model
    def save_ytd_figure(self, key='', codes=None, add_item='', remove=False):
        """A fixed figure's pay items ("paid in Payobook" adds them up), or a
        pay item named as a figure (`add_item`), or one taken off (`remove`)."""
        self._ytd_setup_gate()
        company = self.env.company
        Figure = self.env['pb.updates.ytd.figure'].sudo().with_context(active_test=False)
        if add_item:
            code = str(add_item).strip()
            rule = self.env['hr.formula.rule'].sudo().search(
                [('code', '=', code), ('config_id.company_id', '=', company.id)], limit=1)
            if not rule or code in FIGURES:
                return {'ok': False, 'msg': _("Pick a pay item of one of your pay schemes.")}
            row = Figure.search([('company_id', '=', company.id), ('key', '=', code)], limit=1)
            vals = {'item': True, 'label': rule.name or code, 'codes': code, 'active': True}
            if row:
                row.write(vals)
            else:
                Figure.create(dict(vals, company_id=company.id, key=code))
            return dict(self.get_ytd_setup(), ok=True)
        key = str(key or '').strip()
        row = Figure.search([('company_id', '=', company.id), ('key', '=', key)], limit=1)
        if remove:
            if key in FIGURES or not row:
                return {'ok': False, 'msg': _("The six standard figures always stay.")}
            if self.env['pb.updates.ytd.line'].sudo().search_count(
                    [('figure', '=', key), ('company_id', '=', company.id),
                     ('state', 'in', LIVE)]):
                return {'ok': False, 'msg': _("Some people have this figure, so it stays. Clear "
                                              "it from a sheet first.")}
            if self.env['pb.updates.ytd.map'].sudo().search_count(
                    [('figure', '=', key), ('company_id', '=', company.id)]):
                return {'ok': False, 'msg': _("A pay item receives this figure. Take that off "
                                              "first.")}
            row.write({'active': False})
            return dict(self.get_ytd_setup(), ok=True)
        if key not in FIGURES or key in ('months',):
            return {'ok': False, 'msg': _("Pick one of the figures.")}
        clean = []
        for code in codes or []:
            code = str(code or '').strip()
            if code and code not in clean:
                clean.append(code)
        vals = {'codes': ','.join(clean), 'item': False, 'active': True}
        if row:
            row.write(vals)
        else:
            Figure.create(dict(vals, company_id=company.id, key=key))
        self.env.cr.cache.pop('pb_updates_ytd_known', None)
        return dict(self.get_ytd_setup(), ok=True)

    @api.model
    def save_ytd_map(self, config_id=0, code='', figure='', basis='before_period'):
        """D20: a payroll manager chooses which input pay item of a scheme
        receives which figure. Nothing reaches any pay run without it."""
        self._ytd_setup_gate()
        config = self.env['hr.formula.config'].sudo().search(
            [('id', '=', int(config_id or 0)), ('company_id', 'in', self.env.companies.ids)], limit=1)
        if not config:
            return {'ok': False, 'msg': _("Pick a pay scheme.")}
        rule = config.rule_ids.filtered(lambda r: r.code == code and r.column_type == 'input')[:1]
        if not rule:
            return {'ok': False, 'msg': _("Pick a pay item the pay run fills in (an input of %s).")
                    % (config.name or '')}
        figures = self._ytd_figures([config.company_id.id])
        if figure not in figures:
            return {'ok': False, 'msg': _("Pick one of the figures.")}
        if basis not in BASES:
            basis = 'before_period'
        if basis == 'with_period' and figure not in COUNT_FIGURES:
            return {'ok': False, 'msg': _("“Including this pay period” is for months counted only.")}
        Map = self.env['pb.updates.ytd.map'].sudo()
        row = Map.search([('config_id', '=', config.id), ('code', '=', code)], limit=1)
        vals = {'figure': figure, 'basis': basis, 'set_by_id': self.env.uid,
                'set_at': fields.Datetime.now()}
        if row:
            row.write(vals)
        else:
            Map.create(dict(vals, config_id=config.id, code=code, company_id=config.company_id.id))
        return dict(self.get_ytd_setup(), ok=True)

    @api.model
    def remove_ytd_map(self, map_id=0):
        self._ytd_setup_gate()
        row = self.env['pb.updates.ytd.map'].sudo().search(
            [('id', '=', int(map_id or 0)), ('company_id', 'in', self.env.companies.ids)], limit=1)
        if row:
            row.unlink()
        return dict(self.get_ytd_setup(), ok=True)

    # =================================================================
    # The home's questions (D11) include year-to-date ones
    # =================================================================
    @api.model
    def get_waiting(self):
        answer = super().get_waiting()
        asks = self.env['pb.updates.ytd.ask'].sudo().search(
            [('company_id', 'in', self.env.companies.ids), ('clash_choice', '=', False)])
        if asks:
            answer['clashes'] = list(answer.get('clashes') or []) + asks._payload()
            answer['can_choose'] = self.env['pb.updates.oneoff']._may_choose()
        return answer


class PbRecordsDeskYtd(models.AbstractModel):
    """The Records screen's History lists a year-to-date update too: its own
    words, and its Undo takes back only what no finished pay run used."""
    _inherit = 'pb.records.desk'

    @api.model
    def get_history(self, limit=20):
        answer = super().get_history(limit)
        rows = answer.get('applies') or []
        if not rows:
            return answer
        Apply = self.env['pb.records.apply'].sudo()
        recs = {r.id: r for r in Apply.browse([h['id'] for h in rows]).exists()}
        for h in rows:
            rec = recs.get(h['id'])
            if not rec or not rec.updates_ytd or not rec.updates_batch_id:
                continue
            state, label, note = self.env['pb.updates.desk']._ytd_state(rec.updates_batch_id)
            h['ytd'] = True
            if state != 'blocked' or not h.get('block_note'):
                h['block_note'] = ' · '.join(x for x in (rec._headline(), label, note) if x)
            if rec.applied and not rec.ytd_line_ids.filtered(
                    lambda r: r.state in ('set', 'cleared')):
                h['undone'] = True
        return answer

    @api.model
    def undo_apply(self, apply_id):
        source = self.env['pb.records.apply'].sudo().browse(int(apply_id or 0)).exists()
        if source and source.updates_ytd and source.applied:
            Updates = self.env['pb.updates.desk']
            if not Updates._ytd_may_read():
                return {'ok': False, 'msg': _(
                    "Undoing year-to-date figures needs a payroll role.")}
            return Updates._ytd_undo_rows(source.ytd_line_ids, source)
        return super().undo_apply(apply_id)
