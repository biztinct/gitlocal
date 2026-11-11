# -*- coding: utf-8 -*-
"""UPDATES P2c — when an update starts.

A change can carry a start date: today (the default), a past date, or a
future date. This file is everything Updates adds around that; the writing
itself stays the Records Desk's (`pb.records.desk.apply_changes`,
`start_now`, `cancel_apply`, and the hourly job in `pb_records`).

  * reading a start-date column: real spreadsheet dates, ISO `2026-12-01`,
    and day-first or month-first text according to the reader's language;
  * splitting a file's changes into one desk apply per start date (at most
    six dates), holding back only contract and pay-item values by default;
  * the home's "Coming up" list, "Start now" and "Cancel";
  * how many people were already paid for a period after a past date — the
    amber note on the apply step. Nothing is recalculated: no back pay, no
    proration (ledger U14, U15).

Loaded after `updates_desk` (models/__init__.py); constants are imported
FROM that file, never the other way round (ledger G21).
"""
import re
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, get_lang

from odoo.addons.pb_updates.models.updates_desk import (
    DATED_GROUPS, MAX_START_DATES)

ISO_RE = re.compile(r'^\s*(\d{4})-(\d{1,2})-(\d{1,2})')
WORD_FORMATS = ('%d %b %Y', '%d %B %Y', '%b %d %Y', '%B %d %Y',
                '%d %b, %Y', '%b %d, %Y', '%B %d, %Y', '%d-%b-%Y', '%d-%b-%y')


class PbUpdatesDates(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    # =================================================================
    # Reading a start date
    # =================================================================
    @api.model
    def _start_formats(self):
        """The text shapes a typed date is read in, the reader's own first.

        Day-first or month-first follows the language's date format, so
        "03/04/2026" is 3 April for a Vietnamese reader and 4 March for an
        American one — never a guess between the two."""
        fmt = get_lang(self.env).date_format or '%m/%d/%Y'
        day_first = '%d' in fmt and '%m' in fmt and fmt.index('%d') < fmt.index('%m')
        if day_first:
            numeric = ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d/%m/%y', '%d.%m.%y']
        else:
            numeric = ['%m/%d/%Y', '%m-%d-%Y', '%m.%d.%Y', '%m/%d/%y', '%m.%d.%y']
        out = [fmt] + [f for f in numeric if f != fmt] + list(WORD_FORMATS)
        return out

    @api.model
    def _parse_start(self, value):
        """`(date or None, why)` for one start-date cell. Blank is
        `(None, '')`: the row takes the file's default."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None, ''
        text = str(value).strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return None, _("'%s' is not a date. Use a date like 1 Dec 2026.") % text
        match = ISO_RE.match(text)
        if match:
            try:
                return datetime(int(match.group(1)), int(match.group(2)),
                                int(match.group(3))).date(), ''
            except ValueError:
                return None, _("'%s' is not a date. Use a date like 1 Dec 2026.") % text
        for fmt in self._start_formats():
            try:
                return datetime.strptime(text, fmt).date(), ''
            except ValueError:
                continue
        return None, _("'%s' is not a date. Use a date like 1 Dec 2026.") % text

    @api.model
    def _row_starts(self, desk, peek, column):
        """`({file row: start}, refusal)` for every row of a peek.

        `start` is `{'date': 'YYYY-MM-DD' or '', 'kind': 'past'|'today'|
        'future'|'', 'error': sentence or ''}`. A date further than a year
        away carries the desk's own refusal. More than six different dates
        in the file is refused before the review."""
        Apply = self.env['pb.records.apply']
        today = Apply._today_for()
        out, dates = {}, set()
        for entry in (peek.get('matched') or []) + (peek.get('unmatched') or []):
            raw = (entry.get('extra') or {}).get(column)
            day, why = self._parse_start(raw)
            start = {'date': '', 'kind': '', 'error': why, 'raw': str(raw or '')}
            if day:
                _same, reach = desk._start_date_of(day)
                if reach:
                    start['error'] = reach
                else:
                    start['date'] = fields.Date.to_string(day)
                    start['kind'] = 'today' if day == today else (
                        'past' if day < today else 'future')
                    if day != today:
                        dates.add(day)
            out[entry['row']] = start
        if len(dates) > MAX_START_DATES:
            return {}, _("This file has %(n)s different start dates. Split it "
                         "into files of at most %(max)s.") % {
                             'n': len(dates), 'max': MAX_START_DATES}
        return out, ''

    # =================================================================
    # Applying by start date
    # =================================================================
    @api.model
    def _split_by_start(self, desk, changes, default, hold_scope):
        """`({date or None: [change]}, refusal)`.

        Each change starts on its own date (`change['start']`), else on the
        default, else today. Today is `None` — the undated apply, exactly as
        before. With `hold_scope='pay'`, a FUTURE date holds back only the
        contract and pay-item values; the personal and bank values of those
        rows go in today's apply. A past date never splits (it is a record,
        written now)."""
        default_day, why = desk._start_date_of(default)
        if why:
            return {}, why
        Apply = self.env['pb.records.apply']
        today = Apply._today_for()
        _topics, by_id, _data = self._catalogue(desk)
        hold_all = hold_scope == 'all'
        buckets, memo = {}, {}
        for change in changes:
            raw = change.get('start')
            if raw:
                if raw not in memo:
                    memo[raw] = desk._start_date_of(raw)
                day, why = memo[raw]
                if why:
                    return {}, why
            else:
                day = default_day
            group = by_id.get(str(change.get('field_id') or ''), {}).get('group')
            if day and day > today and not hold_all and group not in DATED_GROUPS:
                day = None
            buckets.setdefault(day, []).append({
                'emp_id': change.get('emp_id'), 'field_id': change.get('field_id'),
                'value': change.get('value')})
        dated = [d for d in buckets if d]
        if len(dated) > MAX_START_DATES:
            return {}, _("This file has %(n)s different start dates. Split it "
                         "into files of at most %(max)s.") % {
                             'n': len(dated), 'max': MAX_START_DATES}
        return buckets, ''

    @api.model
    def _apply_by_start(self, desk, buckets, name, hold_scope):
        """One desk apply per start date, today's first, then the past dates,
        then the future ones; all in this one transaction. `(answer,
        [(date, desk answer)])` — `answer` sums them up for the screen."""
        Apply = self.env['pb.records.apply']
        today = Apply._today_for()
        order = sorted(buckets, key=lambda d: (d is not None, d or today))
        answers = []
        for day in order:
            res = desk.apply_changes(
                0, buckets[day], note=name, source='import',
                start_date=fields.Date.to_string(day) if day else None,
                hold_scope='all' if hold_scope == 'all' else 'pay')
            if res.get('ok') is False:
                # A start date the desk refuses (already checked above, so
                # this is a rail): raise, so the applies already made in
                # this transaction are rolled back with it — all or none.
                raise UserError(res.get('msg') or _(
                    "Nothing was changed: the update could not be sent."))
            answers.append((day, res))
        made = [(d, a) for d, a in answers if a.get('apply_id')]
        first = made[0][1] if made else (answers[0][1] if answers else {})
        now = [a for d, a in made if not a.get('pending') and not a.get('scheduled')]
        waiting = [a for d, a in made if a.get('pending')]
        answer = {
            'ok': True,
            'apply_id': first.get('apply_id') or 0,
            'apply_ids': [a['apply_id'] for _d, a in made],
            'written': sum(a.get('written') or 0 for a in now),
            'people': sum(a.get('people') or 0 for a in now),
            'items': [i for _d, a in answers for i in (a.get('items') or [])],
            'refused': [r for _d, a in answers for r in (a.get('refused') or [])],
            'skipped_same': sum(a.get('skipped_same') or 0 for _d, a in answers),
            'reference': ', '.join(a.get('reference') or '' for _d, a in made),
            'pending': bool(waiting),
            'request_id': (waiting[0].get('request_id') if waiting else 0) or 0,
            'with_whom': waiting[0].get('with_whom') if waiting else '',
            'route': waiting[0].get('route') if waiting else [],
            'state': first.get('state') or '',
            'block_note': '; '.join(a.get('block_note') or '' for _d, a in made
                                    if a.get('block_note')),
            'parts': [{
                'date': fields.Date.to_string(d) if d else '',
                'kind': '' if not d else ('past' if d < today else 'future'),
                'state': a.get('state') or '',
                'values': (a.get('counts') or {}).get('ok') or 0,
                'written': a.get('written') or 0,
                'people': (a.get('counts') or {}).get('people') or 0,
                'pending': bool(a.get('pending')),
                'scheduled': bool(a.get('scheduled')),
            } for d, a in made],
        }
        return answer, answers

    # =================================================================
    # Coming up, Start now, Cancel
    # =================================================================
    @api.model
    def _batch_of(self, apply_id):
        """`(apply, batch)` when the change belongs to a named update in the
        companies in use, else empty recordsets (a search, so a record rule
        answers "not yours" with nothing rather than an error)."""
        try:
            apply_id = int(apply_id or 0)
        except (TypeError, ValueError):
            apply_id = 0
        rec = self.env['pb.records.apply'].sudo().browse(apply_id).exists()
        if not rec or not rec.updates_batch_id:
            return self.env['pb.records.apply'], self.env['pb.updates.batch']
        batch = self.env['pb.updates.batch'].search(
            [('id', '=', rec.updates_batch_id.id),
             ('company_id', 'in', self.env.companies.ids)], limit=1)
        if not batch:
            return self.env['pb.records.apply'], batch
        return rec, batch

    @api.model
    def get_coming_up(self, limit=50):
        """Scheduled parts of named updates, soonest first."""
        desk = self._gate()
        may_write = self._can_write(desk)
        rows = self.env['pb.records.apply'].sudo().search([
            ('state', '=', 'scheduled'), ('applied', '=', False),
            ('updates_batch_id', '!=', False),
            ('updates_batch_id.company_id', 'in', self.env.companies.ids),
        ], order='start_date, id', limit=int(limit or 50))
        items = []
        for rec in rows:
            batch = rec.updates_batch_id
            items.append({
                'apply_id': rec.id, 'batch_id': batch.id,
                'name': batch.name or rec.name, 'reference': rec.name,
                'date': fields.Date.to_string(rec.start_date),
                'values': rec.values_count, 'people': rec.people_count,
                'user': rec.user_id.display_name or '',
                'note': rec.block_note or '',
                'can_start': may_write,
                'can_cancel': bool(may_write and rec.with_env(self.env)._may_cancel()),
            })
        return {'items': items}

    @api.model
    def start_now(self, apply_id=0):
        """Write one scheduled part today, through the desk's own Start now."""
        desk = self._gate()
        rec, batch = self._batch_of(apply_id)
        if not rec:
            return {'ok': False, 'msg': _(
                "That update is not on record in the companies you are "
                "working in.")}
        if not self._can_write(desk):
            return {'ok': False, 'msg': _(
                "Starting an update needs permission to change employee "
                "records. Ask an administrator for the HR or Payroll Officer "
                "role.")}
        answer = desk.start_now(rec.id)
        answer.update(batch_id=batch.id, name=batch.name)
        return answer

    @api.model
    def cancel(self, batch_id=0, apply_id=0):
        """Cancel what has not been written: one part (`apply_id`), or every
        part of a named update that is still waiting for approval or for its
        day (`batch_id`). What was already applied stays — that is Undo."""
        desk = self._gate()
        if not self._can_write(desk):
            return {'ok': False, 'msg': _(
                "Cancelling an update needs permission to change employee "
                "records. Ask an administrator for the HR or Payroll Officer "
                "role.")}
        if apply_id:
            rec, batch = self._batch_of(apply_id)
            parts = rec
        else:
            try:
                batch_id = int(batch_id or 0)
            except (TypeError, ValueError):
                batch_id = 0
            batch = self.env['pb.updates.batch'].search(
                [('id', '=', batch_id),
                 ('company_id', 'in', self.env.companies.ids)], limit=1)
            parts = batch.apply_ids.sudo().filtered(
                lambda a: not a.applied and a.state in ('pending', 'scheduled'))
        if not batch:
            return {'ok': False, 'msg': _(
                "That update is not on record in the companies you are "
                "working in.")}
        if not parts:
            return {'ok': False, 'msg': _(
                "Nothing in this update is waiting, so there is nothing to "
                "cancel.")}
        cancelled = values = 0
        refusals = []
        for part in parts:
            res = desk.cancel_apply(part.id)
            if res.get('ok'):
                cancelled += 1
                values += part.values_count
            else:
                refusals.append(res.get('msg') or '')
        if not cancelled:
            return {'ok': False, 'msg': refusals[0] if refusals else _(
                "Nothing could be cancelled.")}
        return {'ok': True, 'cancelled': cancelled, 'values': values,
                'batch_id': batch.id, 'name': batch.name,
                'msg': _("Cancelled before anything was changed.")}

    # =================================================================
    # The amber note on the apply step
    # =================================================================
    @api.model
    def paid_since(self, people=None):
        """How many of these people already have a finished payslip ending
        on or after the date their change is recorded as starting.

        `people` is `{employee id: 'YYYY-MM-DD'}`. One grouped query on
        finished payslips. A count only — nothing is recalculated."""
        desk = self._gate()
        wanted = {}
        for key, value in (people or {}).items():
            try:
                emp_id = int(key)
            except (TypeError, ValueError):
                continue
            day, _why = self._parse_start(value)
            if emp_id and day:
                wanted[emp_id] = day
        if not wanted:
            return {'count': 0}
        visible = set(desk._matching({'employee_ids': list(wanted)}, ctx={}).ids)
        ids = [i for i in wanted if i in visible]
        if not ids or 'hr.payslip' not in self.env:
            return {'count': 0}
        Payslip = self.env['hr.payslip'].sudo()
        known = dict(Payslip._fields['state']._description_selection(self.env))
        finished = [s for s in ('done', 'paid') if s in known] or ['done']
        groups = Payslip._read_group(
            [('employee_id', 'in', ids), ('state', 'in', finished)],
            ['employee_id'], ['date_to:max'])
        count = sum(1 for employee, last in groups
                    if last and employee.id in wanted and last >= wanted[employee.id])
        return {'count': count}

    @api.model
    def start_label(self, iso):
        """A start date in the reader's own short form (server sentences)."""
        day = fields.Date.to_date(iso) if iso else None
        return format_date(self.env, day) if day else ''
