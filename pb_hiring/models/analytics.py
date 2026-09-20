# -*- coding: utf-8 -*-
"""`pb.hiring.analytics` — the eight numbers a hiring process is judged on.

EVERY NUMBER HERE IS ABOUT ONE COHORT: the hiring requests that were OPENED
inside the range. That is a deliberate and slightly unusual choice, and it is
what makes the eight figures comparable to each other. The obvious alternative
— each metric over its own window — produces a screen where "we filled nine
roles" and "we made twelve offers" are about two different sets of roles, and
nobody can do arithmetic across them.

THREE RULES THIS FILE KEEPS.

  * **Nothing is guessed.** A role still open has no time-to-fill and is left
    out of the average rather than counted as "so far". A month with no
    requests says so in words (R27) instead of drawing eight zeros.
  * **The company boundary is in the DOMAIN.** `sudo()` is used to read people
    and candidates (R56), and the company clause is written out every time,
    because once the read is made as the system there is nothing else left to
    carry it (R89).
  * **A median, not only a mean.** One role that took eleven months moves a
    mean by weeks. Both are shown, side by side, because the gap between them
    is itself the interesting number.
"""

import base64
import io
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import (
    DELAY_KINDS, NO_SHOW_BY, REQUISITION_STATES, counted,
)

_logger = logging.getLogger(__name__)

#: How far back the screen opens on. Three months is one hiring cycle on this
#: product's own data and is short enough that the numbers are about now.
DEFAULT_DAYS = 90

#: A read cap for the screen. A cap that is right for a screen is a bug in a
#: job (R76) — nothing here is a job, and the export takes the same cap on
#: purpose so the spreadsheet and the screen can never disagree.
SCAN_LIMIT = 2000


def _median(values):
    """The middle one. Empty is None and never zero — "no answer" and "zero
    days" are different facts and a screen that conflates them lies."""
    rows = sorted(v for v in values if v is not None)
    if not rows:
        return None
    mid = len(rows) // 2
    if len(rows) % 2:
        return float(rows[mid])
    return (rows[mid - 1] + rows[mid]) / 2.0


def _mean(values):
    rows = [v for v in values if v is not None]
    return (sum(rows) / len(rows)) if rows else None


def _span(later, earlier):
    """Days between two moments, and NEVER a negative one.

    A DATE AND A DATETIME ARE NOT ON THE SAME CLOCK. `opened_on` and
    `filled_on` are written with `context_today` — the ACTING person's
    timezone — and `sent_on` is a UTC datetime, so a role agreed at half past
    five on a Vietnamese evening and offered the same evening reads as MINUS
    one day. Dropping those rows is what a `>= 0` guard does, and it drops
    exactly the fastest ones: "days to an offer" came back as "no answer"
    over two offers that had gone out the same day (found live 2026-09-15).
    A negative span across a timezone boundary is an artefact, not data, so
    it is floored at zero and counted.
    """
    if not later or not earlier:
        return None
    later = later.date() if hasattr(later, 'date') else later
    earlier = earlier.date() if hasattr(earlier, 'date') else earlier
    return max(0, (later - earlier).days)


class PbHiringAnalytics(models.AbstractModel):
    _name = 'pb.hiring.analytics'
    _description = 'Payobook Hiring numbers'

    # =====================================================================
    #  The range
    # =====================================================================
    @api.model
    def _window(self, date_from=None, date_to=None):
        """Two dates, whatever the caller sent. Bad input is answered with
        the default rather than with a traceback: this is read by a screen."""
        today = fields.Date.context_today(self)
        try:
            end = fields.Date.to_date(date_to) or today
        except (ValueError, TypeError):
            end = today
        try:
            start = fields.Date.to_date(date_from) \
                or (end - timedelta(days=DEFAULT_DAYS))
        except (ValueError, TypeError):
            start = end - timedelta(days=DEFAULT_DAYS)
        if start > end:
            start, end = end, start
        return start, end

    @api.model
    def _requests(self, start, end):
        co_ids = self.env.companies.ids or [self.env.company.id]
        return self.env['pb.hiring.requisition'].sudo().search([
            ('company_id', 'in', co_ids),
            ('opened_on', '!=', False),
            ('opened_on', '>=', start),
            ('opened_on', '<=', end),
        ], order='opened_on', limit=SCAN_LIMIT)

    # =====================================================================
    #  The board
    # =====================================================================
    @api.model
    def get_board(self, date_from=None, date_to=None):
        if not self.env['pb.hiring']._can_read():
            return {'allowed': False, 'empty': True, 'tiles': [], 'rows': {}}
        start, end = self._window(date_from, date_to)
        requests = self._requests(start, end)
        payload = {
            'allowed': True,
            'from': str(start),
            'to': str(end),
            'requests': len(requests),
            'empty': not requests,
            'headline': '',
            'tiles': [],
            'stages': [],
            'sources': [],
            'delays': [],
            'no_shows': [],
            'agency': [],
            'states': [{'key': k, 'label': v} for k, v in REQUISITION_STATES],
        }
        if not requests:
            payload['headline'] = _(
                "No requests were opened between %(from)s and %(to)s, so "
                "there is nothing to measure yet. Widen the dates, or come "
                "back once a role has been agreed.",
                **{'from': start, 'to': end})
            return payload

        fill = self._time_to_fill(requests)
        offer = self._time_to_offer(requests)
        acceptance = self._offer_acceptance(requests)
        payload.update({
            'stages': self._time_in_stage(requests),
            'sources': self._sources(requests),
            'delays': self._delays(requests),
            'no_shows': self._no_shows(requests),
            'agency': self._agency_split(requests),
        })
        payload['tiles'] = [
            {'key': 'requests', 'label': _('Roles agreed'),
             'value': len(requests), 'unit': '', 'icon': 'briefcase',
             'hint': _('Hiring requests that reached "open" in this range.')},
            {'key': 'filled', 'label': _('Roles filled'),
             'value': fill['filled'], 'unit': '', 'icon': 'checkCircle',
             'hint': _('Of those, the ones where everybody asked for has '
                       'joined.')},
            {'key': 'fill_median', 'label': _('Days to fill, typical'),
             'value': fill['median'], 'unit': _('days'), 'icon': 'clock',
             'hint': _('The middle role. Half took longer, half took less.')},
            {'key': 'fill_mean', 'label': _('Days to fill, average'),
             'value': fill['mean'], 'unit': _('days'), 'icon': 'gauge',
             'hint': _('The average. Well above the typical figure means a '
                       'few roles are dragging the rest.')},
            {'key': 'offer_median', 'label': _('Days to an offer'),
             'value': offer['median'], 'unit': _('days'), 'icon': 'send',
             'hint': _('From the role being agreed to the first offer going '
                       'out.')},
            {'key': 'offers', 'label': _('Offers sent'),
             'value': acceptance['sent'], 'unit': '', 'icon': 'mail',
             'hint': _('Offers that reached a candidate.')},
            {'key': 'acceptance', 'label': _('Offers accepted'),
             'value': acceptance['rate'], 'unit': '%', 'icon': 'userCheck',
             'hint': _('Of the offers that went out, the share the candidate '
                       'said yes to.')},
            {'key': 'delays', 'label': _('Interviews moved'),
             'value': sum(d['count'] for d in payload['delays']), 'unit': '',
             'icon': 'repeat',
             'hint': _('Every time an hour was moved, whichever side moved '
                       'it.')},
        ]
        payload['headline'] = self._headline(requests, fill, acceptance)
        return payload

    @api.model
    def _headline(self, requests, fill, acceptance):
        """The sentence at the top, in the words a person would use.

        BRANCHED WHOLE (R117): a frame with one word swapped produces "You
        does not have", and a translator handed the frame and the word
        separately cannot fix a verb they were never given.
        """
        n = len(requests)
        if not fill['filled']:
            return _(
                "%(n)s %(word)s agreed in this range and none of them is "
                "filled yet, so there is no time-to-fill to report.",
                n=n, word=counted(n, _('role was'), _('roles were')))
        if fill['median'] is None:
            return _("%(n)s %(word)s agreed in this range.", n=n,
                     word=counted(n, _('role was'), _('roles were')))
        return _(
            "%(n)s %(word)s agreed, %(filled)s filled, and the middle one "
            "took %(days)s days. %(rate)s%% of the offers that went out were "
            "accepted.",
            n=n, word=counted(n, _('role was'), _('roles were')),
            filled=fill['filled'], days=int(round(fill['median'])),
            rate=acceptance['rate'])

    # =====================================================================
    #  The numbers
    # =====================================================================
    @api.model
    def _time_to_fill(self, requests):
        """Agreed → filled, for the roles that actually filled."""
        spans = [_span(r.filled_on, r.opened_on) for r in requests
                 if r.filled_on and r.opened_on]
        return {
            'filled': len(spans),
            'median': _median(spans),
            'mean': round(_mean(spans), 1) if spans else None,
            'spans': spans,
        }

    @api.model
    def _time_to_offer(self, requests):
        """Agreed → the FIRST offer that reached a candidate.

        The first and not the last: "how long before we can make somebody an
        offer" is a question about the process, and a second offer on the same
        role is a question about the first candidate saying no.
        """
        spans = []
        offers = self.env['pb.hiring.offer'].sudo().search([
            ('requisition_id', 'in', requests.ids),
            ('sent_on', '!=', False),
        ], order='sent_on')
        first = {}
        for offer in offers:
            first.setdefault(offer.requisition_id.id, offer)
        for req in requests:
            offer = first.get(req.id)
            if not offer or not req.opened_on:
                continue
            spans.append(_span(offer.sent_on, req.opened_on))
        return {'count': len(spans), 'median': _median(spans),
                'mean': round(_mean(spans), 1) if spans else None}

    @api.model
    def _offer_acceptance(self, requests):
        """Accepted over sent. An offer still waiting is in neither figure —
        a candidate who has not answered is not a refusal."""
        offers = self.env['pb.hiring.offer'].sudo().search([
            ('requisition_id', 'in', requests.ids)])
        sent = offers.filtered(lambda o: o.sent_on)
        accepted = sent.filtered(
            lambda o: o.candidate_decision == 'accepted'
            or o.state in ('accepted', 'signed', 'closed'))
        declined = sent.filtered(lambda o: o.candidate_decision == 'declined')
        answered = len(accepted) + len(declined)
        return {
            'sent': len(sent),
            'accepted': len(accepted),
            'declined': len(declined),
            'waiting': len(sent) - answered,
            'rate': int(round(len(accepted) * 100.0 / answered))
            if answered else 0,
        }

    @api.model
    def _time_in_stage(self, requests):
        """How long candidates sat in each stage, from the move ledger.

        A candidate's time IN a stage is the gap between the move that put
        them there and the next move. The last stage anybody is sitting in has
        no next move and is deliberately not counted: it is still running, and
        an average that included it would fall every time somebody is hired.
        """
        rows = self.env['pb.hiring.stage.log'].sudo().search([
            ('requisition_id', 'in', requests.ids)], order='applicant_id, at')
        by_applicant = {}
        for row in rows:
            by_applicant.setdefault(row.applicant_id.id, []).append(row)
        buckets = {}
        for moves in by_applicant.values():
            for i, move in enumerate(moves[:-1]):
                stage = move.to_stage_id
                if not stage:
                    continue
                days = (moves[i + 1].at - move.at).total_seconds() / 86400.0
                if days < 0:
                    continue
                buckets.setdefault(stage.id,
                                   {'name': stage.name or '',
                                    'sequence': stage.sequence or 0,
                                    'days': []})['days'].append(days)
        out = []
        for stage_id, data in buckets.items():
            out.append({
                'id': stage_id,
                'name': data['name'],
                'sequence': data['sequence'],
                'moves': len(data['days']),
                'mean': round(_mean(data['days']) or 0.0, 1),
                'median': round(_median(data['days']) or 0.0, 1),
            })
        return sorted(out, key=lambda r: (r['sequence'], r['name']))

    @api.model
    def _sources(self, requests):
        """Where candidates came from, and how many of each became a hire.

        `utm.source` is the standard column and "Referral" is the row this
        module's own portal writes. Candidates with no source are reported as
        "Not recorded" rather than dropped — a channel nobody tagged is a real
        and common answer, and hiding it would flatter every other row.
        """
        jobs = requests.mapped('job_id')
        if not jobs:
            return []
        applicants = self.env['hr.applicant'].sudo().with_context(
            active_test=False).search([('job_id', 'in', jobs.ids)],
                                      limit=SCAN_LIMIT)
        hired = {o.applicant_id.id for o in self.env['pb.hiring.offer'].sudo()
                 .search([('requisition_id', 'in', requests.ids),
                          ('state', '=', 'closed')])}
        buckets = {}
        for app in applicants:
            key = app.source_id.id or 0
            name = app.source_id.name or _('Not recorded')
            row = buckets.setdefault(key, {'id': key, 'name': name,
                                           'applicants': 0, 'hires': 0})
            row['applicants'] += 1
            if app.id in hired:
                row['hires'] += 1
        out = list(buckets.values())
        for row in out:
            row['rate'] = int(round(row['hires'] * 100.0 / row['applicants'])) \
                if row['applicants'] else 0
        return sorted(out, key=lambda r: (-r['applicants'], r['name']))

    @api.model
    def _delays(self, requests):
        """Every time an hour moved, split by whose side moved it."""
        rows = self.env['pb.hiring.reschedule'].sudo().search([
            ('requisition_id', 'in', requests.ids)])
        labels = dict(DELAY_KINDS)
        buckets = {k: {'key': k, 'name': v, 'count': 0, 'late': 0}
                   for k, v in DELAY_KINDS}
        for row in rows:
            bucket = buckets.setdefault(
                row.delay_kind or 'internal',
                {'key': row.delay_kind or 'internal',
                 'name': labels.get(row.delay_kind, ''), 'count': 0,
                 'late': 0})
            bucket['count'] += 1
            if row.late_notice:
                bucket['late'] += 1
        return sorted(buckets.values(), key=lambda r: -r['count'])

    @api.model
    def _no_shows(self, requests):
        rows = self.env['pb.hiring.interview'].sudo().search([
            ('requisition_id', 'in', requests.ids),
            ('state', '=', 'no_show')])
        labels = dict(NO_SHOW_BY)
        buckets = {k: {'key': k, 'name': v, 'count': 0} for k, v in NO_SHOW_BY}
        for row in rows:
            bucket = buckets.setdefault(
                row.no_show_by or 'candidate',
                {'key': row.no_show_by or 'candidate',
                 'name': labels.get(row.no_show_by, ''), 'count': 0})
            bucket['count'] += 1
        return sorted(buckets.values(), key=lambda r: -r['count'])

    @api.model
    def _agency_split(self, requests):
        """An agency's roles against our own, on the one number that matters.

        Both sides are shown even when one of them is empty, because "we used
        no agency this quarter" is an answer somebody is looking for.
        """
        out = []
        for key, label, rows in (
            ('agency', _('With an agency'),
             requests.filtered(lambda r: r.agency_vendor_id)),
            ('inhouse', _('Our own team'),
             requests.filtered(lambda r: not r.agency_vendor_id)),
        ):
            spans = [_span(r.filled_on, r.opened_on) for r in rows
                     if r.filled_on and r.opened_on]
            out.append({
                'key': key, 'name': label, 'roles': len(rows),
                'filled': len(spans),
                'median': round(_median(spans), 1) if spans else None,
                'mean': round(_mean(spans), 1) if spans else None,
            })
        return out

    # =====================================================================
    #  The spreadsheet
    # =====================================================================
    @api.model
    def export_xlsx(self, date_from=None, date_to=None):
        """The same payload the screen draws, as a workbook.

        Built from `get_board` and never from a second query: a spreadsheet
        that disagrees with the screen it was exported from is worse than no
        spreadsheet at all. It comes back as base64 and the browser saves it
        without leaving the page — the idiom `pb_budget` uses.
        """
        if not self.env['pb.hiring']._can_read():
            raise UserError(_(
                "The hiring numbers are for the hiring team. Ask them, or ask "
                "the HR team to add you."))
        board = self.get_board(date_from, date_to)
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise UserError(_(
                "This system cannot build spreadsheets at the moment. Ask an "
                "administrator to look at it."))

        wb = openpyxl.Workbook()
        head = Font(bold=True, color='FFFFFF')
        fill = PatternFill('solid', fgColor='6355C7')
        bold = Font(bold=True)

        def sheet(title, columns, rows, first=False):
            ws = wb.active if first else wb.create_sheet()
            ws.title = title[:31]
            for i, label in enumerate(columns, start=1):
                cell = ws.cell(row=1, column=i, value=label)
                cell.font = head
                cell.fill = fill
                cell.alignment = Alignment(horizontal='center',
                                           wrap_text=True)
            for r, values in enumerate(rows, start=2):
                for i, value in enumerate(values, start=1):
                    ws.cell(row=r, column=i, value=value)
            ws.column_dimensions['A'].width = 34
            for i in range(2, len(columns) + 1):
                ws.column_dimensions[get_column_letter(i)].width = 16
            ws.freeze_panes = 'A2'
            return ws

        summary = sheet(_('Summary'), [_('What is measured'), _('Number'),
                                       _('Unit')],
                        [[t['label'],
                          '' if t['value'] is None else t['value'],
                          t['unit']] for t in board['tiles']], first=True)
        summary.cell(row=len(board['tiles']) + 3, column=1,
                     value=board['headline']).font = bold
        summary.cell(row=len(board['tiles']) + 4, column=1,
                     value=_('Roles agreed between %(from)s and %(to)s',
                             **{'from': board['from'], 'to': board['to']}))

        sheet(_('Time in stage'),
              [_('Stage'), _('Moves'), _('Average days'), _('Typical days')],
              [[r['name'], r['moves'], r['mean'], r['median']]
               for r in board['stages']])
        sheet(_('Where they came from'),
              [_('Source'), _('Candidates'), _('Joined'), _('Share %')],
              [[r['name'], r['applicants'], r['hires'], r['rate']]
               for r in board['sources']])
        sheet(_('Interviews moved'),
              [_('Whose side'), _('Times'), _('At short notice')],
              [[r['name'], r['count'], r['late']] for r in board['delays']])
        sheet(_('Nobody came'), [_('Who did not come'), _('Times')],
              [[r['name'], r['count']] for r in board['no_shows']])
        sheet(_('Agency or our own'),
              [_('Who filled it'), _('Roles'), _('Filled'),
               _('Typical days'), _('Average days')],
              [[r['name'], r['roles'], r['filled'], r['median'], r['mean']]
               for r in board['agency']])

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return {
            'ok': True,
            'file_b64': base64.b64encode(out.read()).decode(),
            'filename': _('Hiring %(from)s to %(to)s.xlsx',
                          **{'from': board['from'], 'to': board['to']}),
            'mimetype': ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'),
            'rows': board['requests'],
        }
