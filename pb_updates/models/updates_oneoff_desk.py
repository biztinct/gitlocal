# -*- coding: utf-8 -*-
"""UPDATES P2d — the Updates screens for one-off pay items for a pay month.

The same four steps as a lasting change (Start → Match columns → Review →
Apply), on a second kind of sheet: one column per one-off pay item (a bonus,
a one-time deduction, an overtime amount) of the people's own pay schemes,
one pay month for the whole sheet. What this file adds is only what that
sheet needs; the person matching, the file reading and the approval route
are the Records Desk's own (`pb.records.desk._io_*`, `biz.approval.engine`).

A cell's verdict (one place, `_oneoff_cell`; review, recheck and apply all
ask it, so the screen and the server never disagree):

  * new / replaces <old>     — an amount above zero for a pay item of the
                               person's scheme;
  * same                     — the amount already waiting for that month;
  * cleared                  — CLEAR takes back the amount waiting;
  * not in their pay scheme  — greyed and skipped (decision D5);
  * refused                  — not a number, a minus sign (the item says
                               whether it adds or takes), already in a pay
                               run, or the person is in no pay scheme that
                               month.

Loaded after `updates_desk` (models/__init__.py); constants come FROM that
file and from the store, never the other way round (ledger G21).
"""
import base64
import difflib
import io
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.tools.misc import format_date

from odoo.addons.pb_records.models.pb_records_io import (
    _norm, XLSX_MIME, IDENTITY_COLS, ID_RE, META_SHEET, MAX_ROWS)
from odoo.addons.pb_updates.models.updates_desk import (
    GUESS_RATIO, IDENTITY_KEYS, product_label)
from odoo.addons.pb_updates.models.updates_batch import heading_fingerprint
from odoo.addons.pb_updates.models.updates_oneoff import (
    DONE_SLIP_STATES, LIVE_STATES, month_options)

_logger = logging.getLogger(__name__)

#: Card ids of one-off pay items: `o:<CODE>`, the rule code the engine uses.
PREFIX = 'o:'
GROUP = 'oneoff'
#: The hidden sheet's cell that says which pay month a sheet is for.
MONTH_KEY = 'period_month'
#: How far a pay month can be: 2 months back, 12 ahead (handover §5.4).
MONTHS_BACK, MONTHS_AHEAD = 2, 12
#: Money symbols a typed amount may carry.
MONEY_MARKS = re.compile(r'(₫|đ|vnd|\$|usd|rp|idr|rm|myr|s\$|sgd|฿|thb|₹|inr|៛|khr)',
                         re.I)


class PbUpdatesOneoffDesk(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    # =================================================================
    # The pay month
    # =================================================================
    @api.model
    def _oneoff_today(self):
        return self.env['pb.records.apply']._today_for()

    @api.model
    def _oneoff_month(self, month):
        """`(first-of-month date or None, refusal)`."""
        Oneoff = self.env['pb.updates.oneoff']
        try:
            day = fields.Date.to_date(month) if month else None
        except (TypeError, ValueError):
            day = None
        if not day:
            return None, _("Pick the pay month these one-off pay items are for.")
        day = day.replace(day=1)
        options = [o['value'] for o in month_options(
            self.env, self._oneoff_today(), MONTHS_BACK, MONTHS_AHEAD)]
        if fields.Date.to_string(day) not in options:
            return None, _("Pick a pay month from 2 months back to 12 months "
                           "ahead. %s is outside that.") % Oneoff._month_label(day)
        return day, ''

    # =================================================================
    # The catalogue: one-off pay items of the visible pay schemes (U24)
    # =================================================================
    @api.model
    def _oneoff_catalogue(self, desk, extra_ids=()):
        """`{'codes': {CODE: card}, 'schemes': {config id: {name, codes,
        cycle, currency}}}` for every active pay scheme this person can see,
        plus any scheme somebody in the file is paid under."""
        Oneoff = self.env['pb.updates.oneoff'].sudo()
        ids = set(desk._configs(0).ids) | {int(i) for i in extra_ids if i}
        configs = self.env['hr.formula.config'].sudo().browse(sorted(ids)).exists()
        codes, schemes = {}, {}
        for cfg in configs.sorted(lambda c: ((c.name or '').lower(), c.id)):
            if cfg.state != 'active':
                continue
            items = Oneoff._items_of(cfg)
            schemes[cfg.id] = {'name': cfg.name or cfg.display_name or '',
                               'codes': set(items), 'cycle': cfg.cycle_type or '',
                               'currency': cfg.currency_id or cfg.company_id.currency_id}
            for code, item in items.items():
                card = codes.setdefault(code, {
                    'id': PREFIX + code, 'code': code, 'label': item['label'],
                    'role': item['role'], 'group': GROUP, 'ttype': 'monetary',
                    'editable': True, 'locked': False, 'schemes': []})
                card['schemes'].append({'id': cfg.id, 'name': schemes[cfg.id]['name']})
        return {'codes': codes, 'schemes': schemes}

    @api.model
    def _oneoff_topics(self, cat):
        fields_ = sorted(cat['codes'].values(),
                         key=lambda c: (c['role'] != 'earning', c['label'].lower()))
        if not fields_:
            return []
        return [{
            'key': GROUP, 'label': _("One-off pay items"), 'icon': 'coins',
            'count': len(fields_), 'field_ids': [f['id'] for f in fields_],
            'fields': [dict(f) for f in fields_],
            'examples': [f['label'] for f in fields_][:3], 'locked': False,
        }]

    @api.model
    def _oneoff_ctx(self, desk, emp_ids, month, cat=None):
        """The scheme context of P2b, for the pay month and one-off items."""
        people = self._people_schemes(emp_ids, on_date=month)
        extra = {cid for p in people.values() for cid in p['ids']}
        cat = cat or self._oneoff_catalogue(desk, extra)
        missing = extra - set(cat['schemes'])
        if missing:
            more = self._oneoff_catalogue(desk, missing)
            cat['schemes'].update(more['schemes'])
            for code, card in more['codes'].items():
                cat['codes'].setdefault(code, card)
        items = {cid: {'name': s['name'], 'codes': s['codes']}
                 for cid, s in cat['schemes'].items()}
        return {'people': people, 'items': items, 'held': set(), 'cat': cat}

    @api.model
    def _oneoff_live(self, emp_ids, month):
        """`{(emp_id, CODE): row}` — what is waiting for (or in) that month."""
        rows = self.env['pb.updates.oneoff'].sudo().search([
            ('employee_id', 'in', list(emp_ids or [])), ('period_month', '=', month),
            ('state', 'in', LIVE_STATES), ('action', '=', 'set')])
        return {(r.employee_id.id, r.code): r for r in rows}

    @api.model
    def _oneoff_paid_month(self, emp_ids, month, ctx):
        """People who already have a FINISHED payslip of one of their pay
        schemes ending in that month."""
        if not emp_ids or 'hr.payslip' not in self.env:
            return set()
        end = month + relativedelta_month()
        slips = self.env['hr.payslip'].sudo().search_read([
            ('employee_id', 'in', list(emp_ids)), ('state', 'in', list(DONE_SLIP_STATES)),
            ('date_to', '>=', month), ('date_to', '<', end)],
            ['employee_id', 'formula_config_id'])
        out = set()
        for slip in slips:
            emp = slip['employee_id'][0] if slip['employee_id'] else 0
            cfg = slip['formula_config_id'][0] if slip.get('formula_config_id') else 0
            person = ctx['people'].get(emp) or {}
            if emp and (not person.get('ids') or cfg in person['ids']):
                out.add(emp)
        return out

    @api.model
    def _oneoff_scheme_for(self, ctx, emp_id, code):
        """The scheme a one-off is entered under: one of the person's schemes
        that has the item, an end-of-month or any-time one first."""
        person = ctx['people'].get(emp_id) or {}
        schemes = ctx['cat']['schemes']
        found = [cid for cid in sorted(person.get('ids') or ())
                 if code in (schemes.get(cid) or {}).get('codes', ())]
        found.sort(key=lambda cid: schemes[cid]['cycle'] == 'mid_cycle')
        return found[0] if found else 0

    # =================================================================
    # One cell's verdict
    # =================================================================
    @api.model
    def _oneoff_amount(self, raw):
        """`(amount or None)` — a typed amount, read like a pay data file."""
        if isinstance(raw, bool):
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        text = MONEY_MARKS.sub('', str(raw or '')).strip()
        if not text or '%' in text:
            return None
        negative = text.startswith('(') and text.endswith(')')
        text = text.strip('()').strip()
        try:
            number = self.env['hr.payroll.import.batch']._coerce_numeric_string(text)
        except Exception:  # noqa: BLE001
            number = None
        if number is None:
            return None
        return -abs(number) if negative else number

    @api.model
    def _oneoff_cell(self, ctx, month, emp_id, emp_name, code, raw, live, clear_words):
        Oneoff = self.env['pb.updates.oneoff']
        card = ctx['cat']['codes'].get(code) or {}
        label = card.get('label') or code
        role = card.get('role') or ''
        text = '' if raw is None else (str(int(raw)) if isinstance(raw, float)
                                       and raw.is_integer() else str(raw))
        out = {'status': 'ok', 'old': '', 'new': text, 'value': raw, 'why': '',
               'amount': 0.0, 'role': role, 'cleared': False}
        row = live.get((emp_id, code))
        if row:
            out['old'] = row._amount_label()
        person = ctx['people'].get(emp_id) or {'ids': set()}
        who = emp_name or _("This person")
        month_label = Oneoff._month_label(month)
        if not person['ids']:
            out.update(status='refused', why=_(
                "%(who)s is not in any pay scheme for %(month)s, so a one-off pay "
                "item cannot be paid to them.", who=who, month=month_label))
            return out
        items = ctx['items']
        if not any(code in (items.get(cid) or {}).get('codes', ()) for cid in person['ids']):
            out.update(status='off_scheme', why=self._off_scheme_why(ctx, emp_id, emp_name, label))
            return out
        if row and (row.state != 'approved' or row.clash_run_id):
            out.update(status='refused', why=_(
                "%(item)s for %(month)s is already in pay run %(run)s. Change it "
                "there.", item=label, month=month_label,
                run=row._slip_label() or row.clash_run_id.name or ''))
            return out
        if isinstance(raw, str) and raw.strip().lower() in clear_words:
            out.update(cleared=True, value='', new='')
            if not row:
                out['status'] = 'same'
            return out
        amount = self._oneoff_amount(raw)
        if amount is None:
            out.update(status='refused', why=_(
                "'%s' is not an amount. Type a number, like 1,500,000.") % text)
            return out
        if amount < 0:
            out.update(status='refused', why=_(
                "A one-off amount cannot be negative. %(item)s already %(way)s: "
                "type the amount without a minus sign.", item=label,
                way=_("takes it from pay") if role == 'deduction' else _("adds it to pay")))
            return out
        currency = (ctx['cat']['schemes'].get(self._oneoff_scheme_for(ctx, emp_id, code))
                    or {}).get('currency')
        out['amount'] = amount
        out['new'] = Oneoff._money(amount, currency)
        if amount == 0:
            if row:
                out.update(status='refused', why=_(
                    "To take back the %s waiting for this month, type CLEAR.")
                    % row._amount_label())
            else:
                out['status'] = 'same'
            return out
        if row and round(row.amount, 2) == round(amount, 2):
            out['status'] = 'same'
            out['new'] = out['old']
        return out

    # =================================================================
    # Download the sheet
    # =================================================================
    @api.model
    def download_oneoff_sheet(self, month=None, filters=None):
        """People × the one-off pay items of THEIR schemes for one pay month,
        today's amounts for that month filled in, grey where an item is not
        in the person's scheme, and a "Read me" sheet."""
        desk = self._gate()
        if not desk._may_export():
            return {'ok': False, 'msg': _(
                "Downloading a sheet needs permission to export employee "
                "records. Ask an administrator, or upload a file of your own.")}
        month, refusal = self._oneoff_month(month)
        if refusal:
            return {'ok': False, 'msg': refusal}
        import openpyxl
        from openpyxl.comments import Comment
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        people = desk._matching(filters or {}, ctx={})
        total = len(people)
        people = people[:MAX_ROWS]
        ctx = self._oneoff_ctx(desk, people.ids, month)
        cat = ctx['cat']
        wanted = set()
        for p in ctx['people'].values():
            for cid in p['ids']:
                wanted |= (ctx['items'].get(cid) or {}).get('codes', set())
        cards = [c for c in cat['codes'].values() if c['code'] in wanted] or \
            list(cat['codes'].values())
        cards.sort(key=lambda c: (c['role'] != 'earning', c['label'].lower()))
        if not cards:
            return {'ok': False, 'msg': _(
                "None of your pay schemes has a one-off pay item yet (an amount "
                "entered for one month, like a bonus). Add one to a pay scheme "
                "first.")}
        live = self._oneoff_live(people.ids, month)
        Oneoff = self.env['pb.updates.oneoff']
        month_label = Oneoff._month_label(month)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Records'
        bold = Font(bold=True, color='241F52')
        id_fill = PatternFill('solid', fgColor='EEF2F6')
        head_fill = PatternFill('solid', fgColor='EAF1FB')
        grey = PatternFill('solid', fgColor='EEEEF2')
        for idx, (_key, head) in enumerate(IDENTITY_COLS, start=1):
            cell = ws.cell(row=1, column=idx, value=_(head))
            cell.font, cell.fill = bold, id_fill
            cell.comment = Comment(_("Identity — used to match the row to a person. "
                                     "It is never imported."), product_label(self.env))
            ws.column_dimensions[get_column_letter(idx)].width = max(16, len(head) + 6)
        first = len(IDENTITY_COLS) + 1
        for offset, card in enumerate(cards):
            col = first + offset
            cell = ws.cell(row=1, column=col, value=card['label'])
            cell.font, cell.fill = bold, head_fill
            cell.alignment = Alignment(vertical='center')
            cell.comment = Comment('id: %s\n%s · %s' % (
                card['id'], _("Adds to pay") if card['role'] == 'earning'
                else _("Takes from pay"), month_label), product_label(self.env))
            ws.column_dimensions[get_column_letter(col)].width = max(14, min(40, len(card['label']) + 6))
        for r, emp in enumerate(people, start=2):
            ws.cell(row=r, column=1, value=emp.barcode or emp.employee_id or '')
            ws.cell(row=r, column=2, value=emp.display_name or emp.name or '')
            ws.cell(row=r, column=3, value=emp.work_email or '')
            person = ctx['people'].get(emp.id) or {'ids': set()}
            mine = set()
            for cid in person['ids']:
                mine |= (ctx['items'].get(cid) or {}).get('codes', set())
            for offset, card in enumerate(cards):
                cell = ws.cell(row=r, column=first + offset)
                if person['ids'] and card['code'] not in mine:
                    cell.fill = grey
                    continue
                row = live.get((emp.id, card['code']))
                if row:
                    cell.value = row.amount
                    cell.number_format = '#,##0.##'
        ws.freeze_panes = 'D2'
        meta = wb.create_sheet(title=META_SHEET)
        meta['A1'], meta['B1'] = 'config_id', 0
        meta['D1'], meta['E1'] = MONTH_KEY, fields.Date.to_string(month)
        meta['A2'], meta['B2'], meta['C2'] = 'column_index', 'field_id', 'label'
        for offset, card in enumerate(cards):
            meta.cell(row=3 + offset, column=1, value=first + offset)
            meta.cell(row=3 + offset, column=2, value=card['id'])
            meta.cell(row=3 + offset, column=3, value=card['label'])
        meta.sheet_state = 'hidden'
        guide = wb.create_sheet(title=_("Read me")[:31])
        guide.column_dimensions['A'].width = 110
        for idx, line in enumerate([
                _("One-off pay items for %s") % month_label,
                _("Every amount in this sheet is paid once, in the %s pay run of "
                  "the person's pay scheme.") % month_label,
                _("Type amounts without a minus sign. Each pay item already says "
                  "whether it adds to pay or takes from pay."),
                _("An amount already in the sheet is waiting for that pay run. "
                  "Change it to replace it, or type CLEAR to take it back. A blank "
                  "cell changes nothing."),
                _("Grey cells are pay items that are not in that person's pay "
                  "scheme. Anything typed there is left out."),
        ], start=1):
            cell = guide.cell(row=idx, column=1, value=line)
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if idx == 1:
                cell.font = bold
        out = io.BytesIO()
        wb.save(out)
        return {'ok': True, 'file_b64': base64.b64encode(out.getvalue()).decode(),
                'filename': _("%(product)s one-off pay items %(month)s.xlsx") % {
                    'product': product_label(self.env), 'month': month_label},
                'mimetype': XLSX_MIME, 'rows': len(people), 'total': total,
                'columns': len(cards), 'truncated': total > MAX_ROWS}

    # =================================================================
    # Match columns
    # =================================================================
    @api.model
    def _oneoff_sheet_month(self, file_b64, filename):
        """The pay month a downloaded sheet says it is for, or ''."""
        if not (filename or '').lower().endswith(('.xlsx', '.xlsm')):
            return ''
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(file_b64 or '')),
                                        read_only=True, data_only=True)
            if META_SHEET not in wb.sheetnames:
                return ''
            ms = wb[META_SHEET]
            if str(ms['D1'].value or '') != MONTH_KEY:
                return ''
            day = fields.Date.to_date(str(ms['E1'].value or '')[:10])
            return fields.Date.to_string(day.replace(day=1)) if day else ''
        except Exception:  # noqa: BLE001 — a hint, never a gate
            return ''

    @api.model
    def _oneoff_read_columns(self, file_b64='', filename='', month=None):
        desk = self._gate()
        refusal, header, rows, comments, meta, name = desk._io_open(file_b64, filename)
        if refusal:
            return refusal
        body = rows[1:]
        if not body:
            return {'ok': False, 'empty': True, 'filename': name,
                    'msg': _("This file has headings only — fill it in and drop it again.")}
        sheet_month = self._oneoff_sheet_month(file_b64, filename)
        # The desk's own identity placement (its three headings and looser
        # spellings), with no catalogue: value columns are placed below.
        _used, identity_cols, _ignored, how = desk._io_columns(
            header, comments, {'config_id': 0, 'by_index': {}}, {}, with_how=True)
        identity_at = {idx: key for key, idx in identity_cols.items()}
        cat = self._oneoff_catalogue(desk)
        topics = self._oneoff_topics(cat)
        offered = {c['id']: c for c in cat['codes'].values()}
        by_label = {}
        for card in offered.values():
            by_label.setdefault(_norm(card['label']), card['id'])
            by_label.setdefault(_norm(card['code']), card['id'])
        heads = [str(h if h is not None else '').strip() for h in header]
        fingerprint = 'oneoff:' + heading_fingerprint(heads)
        Layout = self.env['pb.updates.layout']
        layouts = Layout.search([('company_id', '=', self.env.company.id),
                                 ('kind', '=', 'oneoff')],
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
                    for cid, card in offered.items():
                        if cid in taken:
                            continue
                        r = difflib.SequenceMatcher(None, key, _norm(card['label'])).ratio()
                        if r > ratio:
                            best, ratio = cid, r
                    if best and ratio >= GUESS_RATIO:
                        col.update(how='guess', field_id=best, target=best)
            if col['field_id']:
                taken.add(col['field_id'])
            columns.append(col)
        placed_by_id = [c for c in columns if c['how'] == 'id']
        answer = {
            'ok': True, 'kind': GROUP, 'filename': name, 'rows': len(body),
            'truncated': len(body) > MAX_ROWS, 'columns': columns, 'fields': topics,
            'layout_known': bool(exact), 'sheet_month': sheet_month,
            'from_sheet': bool(placed_by_id) and all(c['how'] in ('id', 'identity')
                                                    for c in columns),
            'schemes': [], 'no_scheme': 0,
        }
        day = fields.Date.to_date(sheet_month or month) if (sheet_month or month) else None
        ids = self._file_people(desk, columns, body)
        if ids and day:
            ctx = self._oneoff_ctx(desk, ids, day.replace(day=1), cat)
            answer.update(self._strip(ctx, ids))
        return answer

    @api.model
    def oneoff_file_schemes(self, file_b64='', filename='', identity=None, month=None):
        """The match screen's head-counts again, after the column that finds
        the person was picked by hand (reads only)."""
        desk = self._gate()
        res, body = desk._import_columns(0, file_b64, filename)
        out = {'ok': bool(res.get('ok')), 'schemes': [], 'no_scheme': 0}
        day, _why = self._oneoff_month(month)
        if not res.get('ok') or not day:
            return out
        columns = []
        for key, idx in (identity or {}).items():
            try:
                idx = int(idx or 0)
            except (TypeError, ValueError):
                idx = 0
            if key in IDENTITY_KEYS and idx > 0:
                columns.append({'idx': idx, 'target': 'identity:%s' % key})
        ids = self._file_people(desk, columns, body)
        if ids:
            out.update(self._strip(self._oneoff_ctx(desk, ids, day), ids))
        return out

    # =================================================================
    # Review
    # =================================================================
    @api.model
    def _oneoff_review(self, file_b64='', filename='', columns=None, month=None):
        desk = self._gate()
        month, refusal = self._oneoff_month(month)
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
        cat = self._oneoff_catalogue(desk)
        used = {idx: fid for idx, fid in cols['used'].items()
                if fid.startswith(PREFIX) and fid[len(PREFIX):] in cat['codes']
                and idx not in cols['identity'].values()}
        if not used:
            return {'ok': False, 'msg': _(
                "Pick at least one column that goes to a one-off pay item.")}
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
            emp_id, method, why = desk._io_match(index, code, person, email)
            if not emp_id:
                unmatched.append({'row': offset, 'code': code, 'name': person,
                                  'email': email, 'why': why,
                                  'values': {k: str(v) for k, v in values.items()}})
                continue
            methods[method] = methods.get(method, 0) + 1
            matched.append({'row': offset, 'emp_id': emp_id, 'method': method,
                            'values': values})
        emp_ids = sorted({m['emp_id'] for m in matched})
        info = self._people_info(desk, emp_ids)
        ctx = self._oneoff_ctx(desk, emp_ids, month, cat)
        live = self._oneoff_live(emp_ids, month)
        paid = self._oneoff_paid_month(emp_ids, month, ctx)
        Oneoff = self.env['pb.updates.oneoff']
        month_label = Oneoff._month_label(month)
        last_row, twice = {}, {}
        for pos, m in enumerate(matched):
            twice[m['emp_id']] = twice.get(m['emp_id'], 0) + 1
            for fid in m['values']:
                last_row[(m['emp_id'], fid)] = pos
        out_rows, changes = [], []
        for pos, m in enumerate(matched):
            person = info.get(m['emp_id']) or {}
            cells = {}
            for fid, raw in m['values'].items():
                cell = self._oneoff_cell(ctx, month, m['emp_id'], person.get('name'),
                                         fid[len(PREFIX):], raw, live, clear_words)
                if last_row.get((m['emp_id'], fid)) != pos:
                    cell.update(status='dup', why=_(
                        "This person is in the file again further down, and that "
                        "row's value is the one used."))
                cells[fid] = cell
                if cell['status'] == 'ok':
                    changes.append({'emp_id': m['emp_id'], 'field_id': fid,
                                    'value': '' if cell['cleared'] else cell['amount']})
            row = {'row': m['row'], 'emp_id': m['emp_id'], 'method': m['method'],
                   'name': person.get('name') or '', 'code': person.get('code') or '',
                   'department': person.get('department') or '',
                   'twice': twice.get(m['emp_id'], 0) > 1, 'cells': cells,
                   'paid_month': m['emp_id'] in paid}
            if row['paid_month']:
                row['paid_note'] = _(
                    "Already paid for %s; this will wait for another pay run in "
                    "that month, or never be paid.") % month_label
            row.update(self._person_scheme(ctx, m['emp_id']))
            out_rows.append(row)
        out_columns = []
        for idx in sorted(used):
            card = cat['codes'][used[idx][len(PREFIX):]]
            if any(c['field_id'] == card['id'] for c in out_columns):
                continue
            out_columns.append({'field_id': card['id'], 'label': card['label'],
                                'group': GROUP, 'idx': idx, 'role': card['role'],
                                'head': cols['heads'].get(idx, '')})
        used_heads = {cols['heads'].get(i, '') for i in list(used) + list(cols['identity'].values())}
        ignored = [h for h in (str(x if x is not None else '').strip() for x in header)
                   if h and h not in used_heads]
        answer = {
            'ok': True, 'kind': GROUP, 'oneoff': True, 'filename': name,
            'month': fields.Date.to_string(month), 'month_label': month_label,
            'summary': {'rows': len(body), 'columns_ignored': ignored},
            'identity': max(methods, key=methods.get) if methods else '',
            'truncated': truncated, 'columns': out_columns, 'pay_items': True,
            'dated': False, 'today': fields.Date.to_string(self._oneoff_today()),
            'rows': out_rows, 'unmatched': unmatched, 'changes': changes,
            'paid_month': len(paid),
            'currency': self._currency_payload(self._oneoff_currency(ctx, emp_ids)),
        }
        answer.update(self._strip(ctx, emp_ids))
        return answer

    @api.model
    def _oneoff_currency(self, ctx, emp_ids):
        """The money a sheet's totals are shown in: the pay scheme most of
        its people are paid under, else the company's."""
        counts = {}
        for emp_id in emp_ids:
            for cid in (ctx['people'].get(emp_id) or {}).get('ids') or ():
                currency = (ctx['cat']['schemes'].get(cid) or {}).get('currency')
                if currency:
                    counts[currency] = counts.get(currency, 0) + 1
        if counts:
            return max(counts, key=counts.get)
        return self.env.company.currency_id

    @api.model
    def _currency_payload(self, currency):
        currency = currency or self.env.company.currency_id
        return {'symbol': currency.symbol or currency.name or '',
                'position': currency.position or 'after',
                'digits': int(currency.decimal_places or 0)}

    @api.model
    def _oneoff_recheck(self, changes=None, month=None):
        """An on-screen fix or a row bound by hand, judged like the file."""
        desk = self._gate()
        month, refusal = self._oneoff_month(month)
        items = []
        if refusal:
            return {'items': [], 'msg': refusal}
        changes = [c for c in (changes or []) if isinstance(c, dict)]
        emp_ids = sorted({int(c.get('emp_id') or 0) for c in changes} - {0})
        ctx = self._oneoff_ctx(desk, emp_ids, month)
        live = self._oneoff_live(emp_ids, month)
        names = {i: p['name'] for i, p in self._people_info(desk, emp_ids).items()}
        clear_words = desk._io_clear_words()
        for change in changes:
            emp_id = int(change.get('emp_id') or 0)
            fid = str(change.get('field_id') or '')
            code = fid[len(PREFIX):] if fid.startswith(PREFIX) else ''
            raw = change.get('value')
            card = ctx['cat']['codes'].get(code) or {}
            cell = self._oneoff_cell(ctx, month, emp_id, names.get(emp_id), code,
                                     raw, live, clear_words) if code else \
                {'status': 'refused', 'why': _("This value could not be checked. Try again."),
                 'old': '', 'new': str(raw or ''), 'amount': 0.0, 'cleared': False, 'role': ''}
            items.append({'emp_id': emp_id, 'field_id': fid, 'status': cell['status'],
                          'old_label': cell['old'], 'new_label': cell['new'],
                          'why': cell['why'], 'cleared': cell['cleared'],
                          'amount': cell['amount'], 'role': cell['role'],
                          'field_label': card.get('label') or ''})
        return {'items': items, 'people': {str(i): self._person_scheme(ctx, i)
                                           for i in emp_ids}}

    # =================================================================
    # Apply
    # =================================================================
    @api.model
    def _oneoff_apply(self, name='', file_b64='', filename='', columns=None,
                      changes=None, stats=None, month=None):
        """Name it, keep the file, and send ONE approval for every one-off in
        it. Every value is judged again here; the browser's list is trusted
        no more than the desk trusts it."""
        desk = self._gate()
        name = (name or '').strip()
        if not name:
            return {'ok': False, 'msg': _(
                "Give this update a name first, so you can find it later in "
                "Past updates.")}
        if not self._can_write(desk):
            return {'ok': False, 'msg': _(
                "You can look through these amounts, but you do not have "
                "permission to change employee records. Ask an administrator "
                "for the HR or Payroll Officer role.")}
        month, refusal = self._oneoff_month(month)
        if refusal:
            return {'ok': False, 'msg': refusal}
        clean = []
        seen = set()
        for change in reversed([c for c in (changes or []) if isinstance(c, dict)]):
            try:
                emp_id = int(change.get('emp_id') or 0)
            except (TypeError, ValueError):
                continue
            fid = str(change.get('field_id') or '')
            if not emp_id or not fid.startswith(PREFIX) or (emp_id, fid) in seen:
                continue
            seen.add((emp_id, fid))
            clean.append({'emp_id': emp_id, 'field_id': fid, 'value': change.get('value')})
        clean.reverse()
        if not clean:
            return {'ok': False, 'msg': _(
                "There is nothing to send: no amount in this file would change "
                "anything.")}
        emp_ids = sorted({c['emp_id'] for c in clean})
        visible = set(desk._matching({'employee_ids': emp_ids}, ctx={}).ids)
        ctx = self._oneoff_ctx(desk, emp_ids, month)
        live = self._oneoff_live(emp_ids, month)
        names = {i: p['name'] for i, p in self._people_info(desk, emp_ids).items()}
        clear_words = desk._io_clear_words() | {''}
        stats = stats if isinstance(stats, dict) else {}
        ok, refused, off = [], [], 0
        for change in clean:
            code = change['field_id'][len(PREFIX):]
            if change['emp_id'] not in visible:
                continue
            raw = change['value']
            if raw is None or raw is False:
                raw = ''
            cell = self._oneoff_cell(ctx, month, change['emp_id'], names.get(change['emp_id']),
                                     code, raw, live, clear_words)
            if cell['status'] == 'ok':
                ok.append((change, cell))
            elif cell['status'] == 'off_scheme':
                off += 1
            elif cell['status'] == 'refused':
                refused.append({'emp_id': change['emp_id'],
                                'emp_name': names.get(change['emp_id']) or '',
                                'field_id': change['field_id'],
                                'field_label': (ctx['cat']['codes'].get(code) or {}).get('label') or code,
                                'why': cell['why']})
        self._remember_oneoff_layout(desk, file_b64, filename, columns)
        Oneoff = self.env['pb.updates.oneoff']
        month_label = Oneoff._month_label(month)
        if not ok:
            return {'ok': True, 'nothing': True, 'batch_id': 0, 'apply_id': 0,
                    'written': 0, 'people': 0, 'refused': refused, 'pending': False,
                    'off_scheme': off, 'month_label': month_label,
                    'msg': _("Nothing was sent: every amount in this file is already "
                             "waiting for %s, or could not be used.") % month_label}

        def count(key):
            try:
                return max(0, int(stats.get(key) or 0))
            except (TypeError, ValueError):
                return 0

        batch = self.env['pb.updates.batch'].create({
            'name': name[:200], 'kind': GROUP, 'period_month': month,
            'filename': (filename or '').strip() or False,
            'rows_total': count('rows'), 'rows_unmatched': count('unmatched'),
            'values_refused': count('left_out') + len(refused),
            'values_off_scheme': count('off_scheme') + off,
        })
        if file_b64:
            batch.attachment_id = self.env['ir.attachment'].create({
                'name': (filename or '').strip() or _("Update file"),
                'datas': file_b64, 'res_model': 'pb.updates.batch', 'res_id': batch.id,
                'mimetype': 'text/csv' if (filename or '').lower().endswith('.csv') else XLSX_MIME,
            })
        Apply = self.env['pb.records.apply'].sudo()
        apply_rec = Apply.create({
            'name': '/', 'note': name, 'source': 'import', 'updates_oneoff': True,
            'count_people': 0, 'count_values': 0, 'plan_json': '[]',
            'changes_json': json.dumps(clean, default=str),
            'people_count': len({c['emp_id'] for c, _cell in ok}), 'values_count': len(ok),
            'touches_bank': False, 'touches_salary': True,
            'company_id': self.env.company.id, 'updates_batch_id': batch.id,
        })
        apply_rec.name = 'RD%05d' % apply_rec.id
        employees = self.env['hr.employee'].sudo().browse(sorted({c['emp_id'] for c, _x in ok}))
        companies = {e.id: e.company_id for e in employees}
        vals_list = []
        for change, cell in ok:
            code = change['field_id'][len(PREFIX):]
            card = ctx['cat']['codes'][code]
            cid = self._oneoff_scheme_for(ctx, change['emp_id'], code)
            scheme = ctx['cat']['schemes'].get(cid) or {}
            existing = live.get((change['emp_id'], code))
            company = companies.get(change['emp_id']) or self.env.company
            vals_list.append({
                'employee_id': change['emp_id'], 'company_id': company.id,
                'code': code, 'label': card['label'], 'period_month': month,
                'action': 'clear' if cell['cleared'] else 'set',
                'amount': existing.amount if cell['cleared'] else cell['amount'],
                'currency_id': (scheme.get('currency') or company.currency_id).id,
                'net_role': card['role'], 'config_id': cid or False,
                'config_name': scheme.get('name') or '', 'batch_id': batch.id,
                'apply_id': apply_rec.id, 'state': 'pending',
                'replaces_id': existing.id if existing else False,
            })
        rows = Oneoff.sudo().create(vals_list)
        rows._log(_("Sent in “%s”.") % batch.name)
        apply_rec.plan_json = json.dumps([r._plan_row() for r in rows])
        payload = self.env['biz.approval.engine'].submit(apply_rec)
        apply_rec.invalidate_recordset()
        rows.invalidate_recordset()
        earn = sum(r.amount for r in rows if r.action == 'set' and r.net_role == 'earning')
        take = sum(r.amount for r in rows if r.action == 'set' and r.net_role == 'deduction')
        currency = rows[:1].currency_id
        return {
            'ok': True, 'kind': GROUP, 'batch_id': batch.id, 'batch_name': batch.name,
            'apply_id': apply_rec.id, 'reference': apply_rec.name,
            'pending': not apply_rec.applied, 'approved': bool(apply_rec.applied),
            'request_id': (payload or {}).get('id') or 0,
            'with_whom': apply_rec._waiting_for(), 'route': desk._route_labels(apply_rec),
            'written': apply_rec.count_values if apply_rec.applied else 0,
            'values': len(rows), 'people': len(rows.mapped('employee_id')),
            'refused': refused, 'off_scheme': off, 'skipped_off_scheme': off,
            'month': fields.Date.to_string(month), 'month_label': month_label,
            'earn': Oneoff._money(earn, currency) if earn else '',
            'take': Oneoff._money(take, currency) if take else '',
            'block_note': apply_rec.block_note or '',
            'not_used': len(rows.filtered(lambda r: r.state == 'cancelled')),
        }

    @api.model
    def _remember_oneoff_layout(self, desk, file_b64, filename, columns):
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
        self.env['pb.updates.layout'].remember(pairs, kind='oneoff')

    # =================================================================
    # Home: "Waiting for a pay run", history rows, cancel
    # =================================================================
    @api.model
    def _oneoff_state(self, rows):
        """`(state, label, note)` of a named update of one-off pay items,
        read off its rows every time (never stored)."""
        Oneoff = self.env['pb.updates.oneoff']
        rows = rows.sudo()
        if not rows:
            return 'cancelled', _("Cancelled"), ''
        apply_rec = rows.mapped('apply_id')[:1]
        reason = apply_rec._blocked_reason() if apply_rec else ''
        if reason:
            return 'blocked', _("Could not be made"), _(
                "Approved, but it could not be made: %s") % reason
        if rows.filtered(lambda r: r.state == 'pending'):
            return 'pending', _("Waiting for approval"), ''
        if rows.filtered(lambda r: r.state == 'approved' and r.clash_run_id
                         and not r.clash_choice):
            return 'clash', _("Two amounts: choose one"), ''
        reserved = rows.filtered(lambda r: r.state == 'reserved')
        if reserved:
            return 'in_run', _("In pay run %s") % reserved[:1]._slip_label(), ''
        if rows.filtered(lambda r: r.state == 'approved'):
            return 'waiting_run', _("Waiting for a pay run"), _(
                "These will be included in the %s pay run.") % Oneoff._month_label(
                    rows[:1].period_month)
        paid = rows.filtered(lambda r: r.state == 'paid')
        if paid:
            return 'paid', _("Paid"), _("Paid in pay run %s.") % paid[:1]._slip_label()
        states = set(rows.mapped('state'))
        if states <= {'rejected'}:
            return 'rejected', _("Turned down"), ''
        if states <= {'returned'}:
            return 'returned', _("Sent back"), ''
        if states <= {'replaced', 'cleared'}:
            return 'replaced', _("Replaced by a later update"), ''
        return 'cancelled', _("Cancelled"), ''

    @api.model
    def _oneoff_batch_row(self, batch, may_write):
        rows = batch.oneoff_ids.sudo()
        state, label, note = self._oneoff_state(rows)
        apply_rec = rows.mapped('apply_id')[:1]
        Oneoff = self.env['pb.updates.oneoff']
        live = rows.filtered(lambda r: r.state in ('pending', 'approved', 'reserved', 'paid'))
        takeable = rows.filtered(lambda r: r.state == 'approved' and not r.clash_run_id
                                 or r.state == 'pending')
        cancelled = rows.filtered(lambda r: r.state == 'cancelled')
        return {
            'id': batch.id, 'kind': GROUP, 'name': batch.name or '',
            'user': batch.user_id.display_name or '',
            'date': batch.date and batch.date.strftime('%Y-%m-%d %H:%M:%S') or '',
            'filename': batch.filename or '', 'file_id': batch.attachment_id.id or 0,
            'people': len(live.mapped('employee_id')) or len(rows.mapped('employee_id')),
            'values': len(live) or len(rows),
            'rows_unmatched': batch.rows_unmatched, 'values_refused': batch.values_refused,
            'values_off_scheme': batch.values_off_scheme,
            'state': state, 'state_label': label, 'state_note': note,
            'state_reason': note if state == 'blocked' else '',
            'month': fields.Date.to_string(batch.period_month) if batch.period_month else '',
            'month_label': Oneoff._month_label(batch.period_month),
            'with_whom': apply_rec._waiting_for() if apply_rec and state == 'pending' else '',
            'can_undo': False, 'has_open': False,
            'can_cancel': bool(may_write and takeable),
            'open_values': len(takeable), 'scheduled': [], 'recorded': [],
            'cancelled_values': len(cancelled),
            'cancelled_by': '', 'cancelled_date': '',
            'paid_values': len(rows.filtered(lambda r: r.state == 'paid')),
        }

    @api.model
    def get_waiting(self):
        """The home's "Waiting for a pay run": per pay month, people, items
        and totals, the named updates in it, and the questions pay runs asked."""
        desk = self._gate()
        may_write = self._can_write(desk)
        Oneoff = self.env['pb.updates.oneoff']
        rows = Oneoff.sudo().search([
            ('company_id', 'in', self.env.companies.ids), ('action', '=', 'set'),
            ('state', 'in', ('pending', 'approved', 'reserved'))],
            order='period_month, batch_id desc, id')
        months = {}
        for row in rows:
            slot = months.setdefault(row.period_month, {
                'month': fields.Date.to_string(row.period_month),
                'label': Oneoff._month_label(row.period_month),
                'people': set(), 'items': 0, 'earn': 0.0, 'take': 0.0,
                'pending': 0, 'in_run': 0, 'currency': row.currency_id,
                'batches': {}, 'rows': []})
            slot['people'].add(row.employee_id.id)
            slot['items'] += 1
            slot['earn' if row.net_role == 'earning' else 'take'] += row.amount
            if row.state == 'pending':
                slot['pending'] += 1
            if row.state == 'reserved':
                slot['in_run'] += 1
            b = slot['batches'].setdefault(row.batch_id.id, {
                'id': row.batch_id.id, 'name': row.batch_id.name or '', 'items': 0,
                'can_cancel': False})
            b['items'] += 1
            if may_write and (row.state == 'pending' or
                              (row.state == 'approved' and not row.clash_run_id)):
                b['can_cancel'] = True
            if len(slot['rows']) < 200:
                slot['rows'].append({
                    'id': row.id, 'emp': row.employee_id.name or '', 'item': row.label or row.code,
                    'amount': row._amount_label(), 'role': row.net_role or '',
                    'state': row.state, 'state_label': dict(
                        row._fields['state']._description_selection(self.env)).get(row.state, ''),
                    'run': row._slip_label() if row.state == 'reserved' else '',
                    'batch': row.batch_id.name or ''})
        out = []
        for month in sorted(months):
            slot = months[month]
            cur = slot.pop('currency')
            out.append(dict(
                slot, people=len(slot['people']),
                earn_label=Oneoff._money(slot['earn'], cur) if slot['earn'] else '',
                take_label=Oneoff._money(slot['take'], cur) if slot['take'] else '',
                batches=list(slot['batches'].values())))
        clashes = Oneoff.sudo()._clash_rows(company_ids=self.env.companies.ids)
        return {'months': out, 'clashes': clashes._clash_payload(),
                'can_choose': Oneoff._may_choose()}

    @api.model
    def get_home(self):
        answer = super().get_home()
        desk = self._desk()
        cat = self._oneoff_catalogue(desk)
        today = self._oneoff_today()
        answer['oneoff'] = {
            'available': bool(cat['codes']),
            'items': len(cat['codes']),
            'months': month_options(self.env, today, MONTHS_BACK, MONTHS_AHEAD),
            'this_month': fields.Date.to_string(today.replace(day=1)),
        }
        answer['waiting'] = self.get_waiting()
        return answer

    @api.model
    def _oneoff_cancel_rows(self, rows, apply_rec=None):
        """Take back every one-off a pay run has not taken. Waiting for
        approval: the request is withdrawn. Waiting for a pay run: cancelled.
        In a pay run or paid: kept, and said."""
        desk = self._desk()
        rows = rows.sudo()
        pending = rows.filtered(lambda r: r.state == 'pending')
        waiting = rows.filtered(lambda r: r.state == 'approved' and not r.clash_run_id)
        kept = rows.filtered(lambda r: r.state in ('reserved', 'paid')
                             or (r.state == 'approved' and r.clash_run_id))
        cancelled = 0
        refusals = []
        for part in pending.mapped('apply_id'):
            res = desk.cancel_apply(part.id)
            if res.get('ok'):
                cancelled += len(pending.filtered(lambda r: r.apply_id == part))
            elif res.get('msg'):
                refusals.append(res['msg'])
        if waiting:
            waiting.write({'state': 'cancelled'})
            waiting._log(_("Cancelled before a pay run took it."))
            cancelled += len(waiting)
        source = apply_rec or rows.mapped('apply_id')[:1]
        if source and source.applied and not source.undone and not rows.filtered(
                lambda r: r.state in LIVE_STATES):
            source.sudo().write({'undone': True, 'undone_date': fields.Datetime.now(),
                                 'undone_by_id': self.env.uid})
        if not cancelled:
            if refusals:
                return {'ok': False, 'msg': refusals[0]}
            return {'ok': False, 'msg': _(
                "Nothing here can be cancelled: a pay run has already taken it. "
                "Change it in that pay run.") if kept else _(
                "Nothing in this update is waiting, so there is nothing to cancel.")}
        msg = _("%s one-off pay items cancelled before a pay run took them.") % cancelled \
            if cancelled != 1 else _("1 one-off pay item cancelled before a pay run took it.")
        if kept:
            msg += ' ' + (_("%s are already in a pay run and stay there.") % len(kept)
                          if len(kept) != 1 else _("1 is already in a pay run and stays there."))
        return {'ok': True, 'cancelled': 1, 'values': cancelled, 'kept': len(kept),
                'restored': cancelled, 'skipped_changed_since': len(kept),
                'skipped_missing': 0, 'msg': msg}

    @api.model
    def cancel(self, batch_id=0, apply_id=0):
        if batch_id and not apply_id:
            try:
                bid = int(batch_id or 0)
            except (TypeError, ValueError):
                bid = 0
            batch = self.env['pb.updates.batch'].search(
                [('id', '=', bid), ('company_id', 'in', self.env.companies.ids)], limit=1)
            if batch and batch.kind == GROUP:
                desk = self._gate()
                if not self._can_write(desk):
                    return {'ok': False, 'msg': _(
                        "Cancelling an update needs permission to change employee "
                        "records. Ask an administrator for the HR or Payroll Officer "
                        "role.")}
                answer = self._oneoff_cancel_rows(batch.oneoff_ids)
                answer.update(batch_id=batch.id, name=batch.name)
                return answer
        return super().cancel(batch_id=batch_id, apply_id=apply_id)

    @api.model
    def undo(self, batch_id=0):
        try:
            bid = int(batch_id or 0)
        except (TypeError, ValueError):
            bid = 0
        batch = self.env['pb.updates.batch'].search(
            [('id', '=', bid), ('company_id', 'in', self.env.companies.ids)], limit=1)
        if batch and batch.kind == GROUP:
            return {'ok': False, 'msg': _(
                "One-off pay items are cancelled, not undone: use Cancel. What a "
                "pay run has already taken stays in that pay run.")}
        return super().undo(batch_id=batch_id)


def relativedelta_month():
    from dateutil.relativedelta import relativedelta
    return relativedelta(months=1)
