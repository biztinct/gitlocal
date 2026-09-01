# -*- coding: utf-8 -*-
"""The anniversary engine — birthdays and work anniversaries, once.

=====================================================================
ONE READ, THREE SURFACES
=====================================================================
`upcoming_celebrations(days)` is the ONLY place this product works out who is
celebrating. The wall's side rail, the monthly mood board and the Monday
heads-up to managers all call it, so the three can never disagree about whose
week it is (the W62 shape: two surfaces answering the same question must read
the same source).

=====================================================================
NO DATE OF BIRTH IS EVER RETURNED
=====================================================================
A birthday is a day and a month. The YEAR is somebody's age, it lives on their
employee record behind the permissions that belong there, and it has no business
on a wall in an open-plan office. The payload carries `day_label` ("14
September") and nothing that can be turned back into a year. Work anniversaries
DO carry the number of years, because that is the whole point of one.

=====================================================================
THE CANDIDATE SEARCH IS SQL, THE READ IS THE ORM
=====================================================================
There are four and a half thousand employees and about four hundred of them are
celebrating in any thirty-day window. Asking the ORM which is a prefetch of
forty columns over the whole company; asking Postgres is one trivial scan of two
date columns. So SQL finds the ids and the ORM (as the system, R56) reads the
handful that matter. `first_contract_date` IS a real stored column on this build
— checked against the database, not assumed (R14 is about the fields that are
NOT, and those are read through the ORM here) — and the join date still falls
back through the contract table and then `create_date`, which is
`pb_people._join_date`'s ladder and must stay the same one.

=====================================================================
IDEMPOTENT BY A ROW, NOT BY A GUESS
=====================================================================
`pb.rnr.celebration.log` carries one row per (person, kind, stamp) with a unique
index on the three. A cron that runs twice in a day, or a job re-run by hand,
writes nothing the second time. R49's lesson is respected: the stamp is always
present and never empty, so the key can never quietly become "everybody whose
value is also blank".
"""

import logging

from odoo import _, api, fields, models

from .rnr_common import (
    CELEBRATION_KINDS, MAIL_CAP, P_ANNIV_MAIL, P_MANAGER_MAIL, counted,
    day_label, flag, initials,
)

_logger = logging.getLogger(__name__)

#: How many celebrations one payload may carry. The wall shows a strip, not a
#: register — four hundred names is a phone book.
CELEBRATION_CAP = 60

#: How many candidate rows Postgres may hand back. A ceiling somebody chose.
CANDIDATE_CAP = 4000


class PbRnrCelebrationLog(models.Model):
    _name = 'pb.rnr.celebration.log'
    _description = 'Celebration already sent'
    _order = 'sent_on desc, id desc'

    employee_id = fields.Many2one('hr.employee', string='Who', required=True,
                                  index=True, ondelete='cascade')
    kind = fields.Selection(CELEBRATION_KINDS, string='What', required=True)
    stamp = fields.Char(
        string='For', required=True, index=True,
        help='The year for a birthday or a work anniversary, the week for a '
             "manager's heads-up. It is what stops the same message going "
             'twice.')
    sent_on = fields.Date(string='Sent on', default=fields.Date.context_today)

    #: Odoo 19 SILENTLY IGNORES a `_sql_constraints` list. The Constraint
    #: attribute is the only spelling that reaches Postgres.
    _uniq_celebration = models.Constraint(
        'unique(employee_id, kind, stamp)',
        'That celebration has already been recorded for this person.')


class PbRnrCelebration(models.AbstractModel):
    _name = 'pb.rnr.celebration'
    _description = 'Celebrations engine'

    # ------------------------------------------------------------- the read
    @api.model
    def upcoming_celebrations(self, days=30, company_ids=None, offset=0):
        """Who is celebrating in the next `days` days, soonest first.

        `days=0` means today and only today. `offset` shifts the whole window
        forward — the monthly mood board asks for NEXT month by starting a month
        out, which is the same question asked from a different Monday and not a
        second implementation of it.

        Returns `[{employee_id, name, initials, avatar, kind, day, day_label,
        years, department}]`. No year of birth, ever.
        """
        span = 30 if days is None else max(0, int(days))
        start = fields.Date.add(fields.Date.context_today(self),
                                days=max(0, int(offset or 0)))
        ids = list(company_ids if company_ids is not None
                   else (self.env.companies.ids or []))
        rows = self._candidates(start, span, ids)
        if not rows:
            return []
        Emp = self.env['hr.employee'].sudo()
        people = {e.id: e for e in Emp.browse(
            sorted({r['employee_id'] for r in rows}))}
        out = []
        for row in rows:
            emp = people.get(row['employee_id'])
            if not emp or not emp.active:
                continue
            out.append({
                'employee_id': emp.id,
                'name': emp.name or '',
                'initials': initials(emp.name or ''),
                'avatar': '/web/image/hr.employee/%s/image_128' % emp.id,
                'kind': row['kind'],
                # A date string, so a caller can sort or compare. The LABEL is
                # what every screen prints, and for a birthday it carries the
                # day and the month and nothing else.
                'day': fields.Date.to_string(row['day']),
                'day_label': day_label(row['day']),
                'years': row['years'],
                'department': (emp.department_id.name
                               if emp.department_id else ''),
            })
        out.sort(key=lambda r: (r['day'], r['kind'], r['name']))
        return out[:CELEBRATION_CAP]

    @api.model
    def _candidates(self, start, span, company_ids):
        """The ids, from Postgres. See this module's header for why.

        The window is expressed as a SET OF (month, day) KEYS rather than as a
        date range, because a window that crosses New Year is otherwise a pair
        of ORed ranges that is easy to get wrong and impossible to read. At most
        thirty-one keys is a cheap `IN` list.
        """
        keyday = {}
        for step in range(span + 1):
            day = fields.Date.add(start, days=step)
            keyday.setdefault('%02d-%02d' % (day.month, day.day), day)
        if not keyday:
            return []
        keys = tuple(keyday)
        sql = """
            SELECT e.id,
                   to_char(e.birthday, 'MM-DD') AS bkey,
                   COALESCE(e.first_contract_date,
                            (SELECT min(c.date_start) FROM hr_contract c
                              WHERE c.employee_id = e.id),
                            e.create_date::date) AS joined
              FROM hr_employee e
             WHERE e.active = true
               AND (to_char(e.birthday, 'MM-DD') IN %s
                    OR to_char(COALESCE(e.first_contract_date,
                                        (SELECT min(c.date_start)
                                           FROM hr_contract c
                                          WHERE c.employee_id = e.id),
                                        e.create_date::date), 'MM-DD') IN %s)
        """
        params = [keys, keys]
        if company_ids:
            sql += ' AND e.company_id IN %s'
            params.append(tuple(company_ids))
        sql += ' LIMIT %s'
        params.append(CANDIDATE_CAP)
        self.env.cr.execute(sql, params)
        out = []
        for emp_id, bkey, joined in self.env.cr.fetchall():
            if bkey and bkey in keyday:
                out.append({'employee_id': emp_id, 'kind': 'birthday',
                            'day': keyday[bkey], 'years': 0})
            if joined:
                jkey = '%02d-%02d' % (joined.month, joined.day)
                if jkey in keyday:
                    when = keyday[jkey]
                    years = when.year - joined.year
                    # A first day is not an anniversary, and neither is a date
                    # in the future that some backfill invented.
                    if years >= 1:
                        out.append({'employee_id': emp_id,
                                    'kind': 'anniversary',
                                    'day': when, 'years': years})
        return out

    # -------------------------------------------------------------- the jobs
    @api.model
    def _cron_celebrations_today(self):
        return self.run_celebrations_today()

    @api.model
    def run_celebrations_today(self):
        """Congratulate the people celebrating TODAY. Idempotent by a row.

        This is the whole of what the night does — every piece of it (R53). A
        "run it now" button that does four of the job's five things reports a
        number that cannot be compared with the morning's log.

        SWITCHED OFF, it still counts what it WOULD have sent and logs the
        figure, so the first thing anybody reads about this job is a number
        rather than silence (R54).
        """
        on = flag(self.env, P_ANNIV_MAIL)
        rows = self.upcoming_celebrations(days=0)
        sent, skipped, would = 0, 0, 0
        Log = self.env['pb.rnr.celebration.log'].sudo()
        Emp = self.env['hr.employee'].sudo()
        for row in rows:
            stamp = str(fields.Date.to_date(row['day']).year)
            if Log.search_count([('employee_id', '=', row['employee_id']),
                                 ('kind', '=', row['kind']),
                                 ('stamp', '=', stamp)]):
                continue
            would += 1
            if not on:
                continue
            if sent >= MAIL_CAP:
                skipped += 1
                continue
            emp = Emp.browse(row['employee_id'])
            to = (emp.work_email or '').strip()
            if not to:
                skipped += 1
                continue
            try:
                self._send_celebration(emp, row, to)
            except Exception:               # noqa: BLE001 — one person, not all
                _logger.exception(
                    'pb_rnr: could not congratulate employee %s', emp.id)
                skipped += 1
                continue
            Log.create({'employee_id': emp.id, 'kind': row['kind'],
                        'stamp': stamp})
            sent += 1
        if on:
            _logger.info('pb_rnr: congratulated %s; %s skipped.',
                         counted(sent, 'person', 'people'), skipped)
        else:
            _logger.info(
                'pb_rnr: celebration emails are switched off. %s would have '
                'been congratulated today.', counted(would, 'person', 'people'))
        return {'sent': sent, 'skipped': skipped, 'would': would,
                'enabled': on, 'found': len(rows)}

    def _send_celebration(self, emp, row, to):
        """One queued message, addressed explicitly (R6).

        Rendered from an `ir.qweb` template rather than a `mail.template`,
        because the sentence needs the number of YEARS and that is not a field
        on anything — it is worked out by the window. A template that cannot see
        the one number it is about is a template pretending to be data.
        """
        is_bday = row['kind'] == 'birthday'
        body = self.env['ir.qweb']._render(
            'pb_rnr.mail_birthday' if is_bday else 'pb_rnr.mail_anniversary', {
                'person': emp.name or '',
                'years': row.get('years') or 0,
                'day': row.get('day_label') or '',
            })
        subject = (_("Happy birthday")
                   if is_bday
                   else _("%s years with us today", row.get('years') or 0))
        self.env['mail.mail'].sudo().create({
            'subject': subject,
            'email_to': to,
            'body_html': body,
            'auto_delete': True,
        })
        return True

    # -------------------------------------------------- the manager's Monday
    @api.model
    def _cron_manager_week(self):
        return self.run_manager_week()

    @api.model
    def run_manager_week(self, days=7):
        """One message per manager, listing their own team's week.

        Idempotent by ISO WEEK, which is why the stamp is a string: "2026-W36"
        is a different key from "2026" and both live in the same column without
        either pretending to be the other.
        """
        on = flag(self.env, P_MANAGER_MAIL)
        rows = self.upcoming_celebrations(days=int(days or 7))
        Emp = self.env['hr.employee'].sudo()
        by_manager = {}
        for row in rows:
            emp = Emp.browse(row['employee_id'])
            boss = emp.parent_id
            if not boss or boss.id == emp.id:
                continue
            by_manager.setdefault(boss.id, []).append(row)
        iso = fields.Date.context_today(self).isocalendar()
        stamp = '%s-W%02d' % (iso[0], iso[1])
        Log = self.env['pb.rnr.celebration.log'].sudo()
        sent, skipped, would = 0, 0, 0
        for boss_id, items in by_manager.items():
            if Log.search_count([('employee_id', '=', boss_id),
                                 ('kind', '=', 'manager_week'),
                                 ('stamp', '=', stamp)]):
                continue
            would += 1
            if not on:
                continue
            if sent >= MAIL_CAP:
                skipped += 1
                continue
            boss = Emp.browse(boss_id)
            to = (boss.work_email or '').strip()
            if not to:
                skipped += 1
                continue
            try:
                self._send_manager_week(boss, items, to)
            except Exception:               # noqa: BLE001 — one manager, not all
                _logger.exception(
                    'pb_rnr: could not send the week ahead to manager %s',
                    boss_id)
                skipped += 1
                continue
            Log.create({'employee_id': boss_id, 'kind': 'manager_week',
                        'stamp': stamp})
            sent += 1
        if on:
            _logger.info('pb_rnr: the week ahead went to %s.',
                         counted(sent, 'manager', 'managers'))
        else:
            _logger.info(
                'pb_rnr: the manager heads-up is switched off. %s would have '
                'been told about their team this week.',
                counted(would, 'manager', 'managers'))
        return {'sent': sent, 'skipped': skipped, 'would': would,
                'enabled': on, 'managers': len(by_manager)}

    def _send_manager_week(self, boss, items, to):
        body = self.env['ir.qweb']._render('pb_rnr.mail_manager_week', {
            'manager': boss.name or '',
            'rows': items,
            'count_line': counted(len(items), _('person'), _('people')),
        })
        self.env['mail.mail'].sudo().create({
            'subject': _("Your team's week ahead"),
            'email_to': to,
            'body_html': body,
            'auto_delete': True,
        })
        return True
