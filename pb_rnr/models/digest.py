# -*- coding: utf-8 -*-
"""`pb.rnr.digest` — the monthly mood board.

ONE EMAIL A MONTH, and it is the only thing this module sends to everybody. It
carries the praise that was agreed, who joined, who is celebrating next month,
and the quarter's winners while they are still news. It is designed rather than
listed: an email that reads like a report is an email nobody opens twice.

=====================================================================
THREE GATES, AND THEY ARE NOT THE SAME GATE
=====================================================================
  1. `pb_rnr.digest_mail` — ships '0'. Off, the job still BUILDS the whole
     digest and logs how many people would have received it (R54), so the first
     thing anybody reads about it is a real number.
  2. `pb_rnr.digest_test_email` — one address. Set, the digest goes THERE and
     nowhere else, whatever the gate says. That is the order things happen in:
     read it yourself, then let four and a half thousand people read it.
  3. `pb_rnr.digest_last_month` — the month already sent. A second run in the
     same month writes nothing and says so.

The stamp is written ONLY on a broadcast. A test send does not consume the
month, because otherwise reading your own draft would cancel the real one.

=====================================================================
NO EMOJI. ANYWHERE. INCLUDING HERE.
=====================================================================
There is not a single emoji in any message this module sends. A cheerful email
full of them is the fastest way to make a company's own newsletter look like
somebody's group chat, and half of them do not render in Outlook anyway.

There are no icons either, and that is a considered choice rather than the same
one: Gmail strips inline SVG and Outlook renders it as a broken image, so the
mood board carries its structure in TYPE and COLOUR — a coloured value chip, a
rule, a photograph — with every colour written out as a literal hex
(`rnr_common.VALUE_HEX`), because an email has no stylesheet and no custom
properties. On screen the token is always used and that map is never touched.
"""

import logging

from odoo import _, api, fields, models

from .rnr_common import (
    MAIL_CAP, MONTHS, P_DIGEST_MAIL, P_DIGEST_STAMP, P_DIGEST_TEST, counted,
    excerpt, flag, initials, param, set_param, value_hex,
)

_logger = logging.getLogger(__name__)

#: How much of each thing goes in. A digest is a taste, not an archive.
STORY_CAP = 8
JOINER_CAP = 12
CELEBRATION_CAP = 14


class PbRnrDigest(models.AbstractModel):
    _name = 'pb.rnr.digest'
    _description = 'Recognition monthly digest'

    # ------------------------------------------------------------ the month
    @api.model
    def _month_bounds(self, month=None):
        day = fields.Date.to_date(month) if month else \
            fields.Date.context_today(self)
        first = day.replace(day=1)
        nxt = (first.replace(year=first.year + 1, month=1)
               if first.month == 12 else first.replace(month=first.month + 1))
        return first, nxt

    @api.model
    def month_stamp(self, month=None):
        first, _nxt = self._month_bounds(month)
        return '%04d-%02d' % (first.year, first.month)

    # ------------------------------------------------------------ the content
    @api.model
    def build(self, month=None, company_ids=None):
        """Everything the digest is about. Reads only.

        The lens's preview and the job that sends it call THIS — one build, one
        set of words, so what somebody read before pressing send is what went
        out.
        """
        first, nxt = self._month_bounds(month)
        ids = list(company_ids if company_ids is not None
                   else (self.env.companies.ids or []))
        return {
            'month_label': '%s %s' % (MONTHS[first.month - 1], first.year),
            'month_stamp': self.month_stamp(first),
            'stories': self._stories(first, nxt, ids),
            'joiners': self._joiners(first, nxt, ids),
            'celebrations': self._celebrations(nxt, ids),
            'next_month_label': '%s %s' % (MONTHS[nxt.month - 1], nxt.year),
            'winners': self._winners(ids),
            'base_url': (self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url') or '').rstrip('/'),
        }

    @api.model
    def _stories(self, first, nxt, ids):
        """The praise that was AGREED this month, and only what may be public.

        `_public_domain()` is the single definition — the wall, the portal page
        and this all call it, so a declined or private story cannot reach an
        inbox through a clause somebody forgot here.
        """
        Nom = self.env['pb.rnr.nomination'].sudo()
        domain = Nom._public_domain(company_ids=ids) + [
            ('decided_at', '>=', fields.Datetime.to_datetime(first)),
            ('decided_at', '<', fields.Datetime.to_datetime(nxt)),
        ]
        recs = Nom.search(domain, order='decided_at desc, id desc',
                          limit=STORY_CAP)
        out = []
        for rec in recs:
            nominee = Nom._person(rec.nominee_id)
            val = rec.value_id.sudo()
            out.append({
                'id': rec.id,
                'nominee': nominee.name or '',
                'initials': initials(nominee.name or ''),
                'avatar': '/web/image/hr.employee/%s/avatar_128' % nominee.id,
                'nominator': Nom._person(rec.nominator_id).name or '',
                'value': val.name or '',
                'color': val.color or 'primary',
                'ink': value_hex(val.color)[0],
                'wash': value_hex(val.color)[1],
                'story': excerpt(rec.story, 260),
                'awarded': rec.outcome == 'awarded',
            })
        return out

    @api.model
    def _joiners(self, first, nxt, ids):
        """Who arrived this month. Read as the system (R56) after a narrow SQL
        pass, for the same reason the celebrations are (four and a half thousand
        employees, a dozen answers)."""
        sql = """
            SELECT e.id
              FROM hr_employee e
             WHERE e.active = true
               AND COALESCE(e.first_contract_date,
                            (SELECT min(c.date_start) FROM hr_contract c
                              WHERE c.employee_id = e.id),
                            e.create_date::date) >= %s
               AND COALESCE(e.first_contract_date,
                            (SELECT min(c.date_start) FROM hr_contract c
                              WHERE c.employee_id = e.id),
                            e.create_date::date) < %s
        """
        params = [first, nxt]
        if ids:
            sql += ' AND e.company_id IN %s'
            params.append(tuple(ids))
        sql += ' LIMIT %s'
        params.append(JOINER_CAP)
        self.env.cr.execute(sql, params)
        emp_ids = [row[0] for row in self.env.cr.fetchall()]
        if not emp_ids:
            return []
        Emp = self.env['hr.employee'].sudo()
        out = []
        for emp in Emp.browse(emp_ids):
            out.append({
                'employee_id': emp.id,
                'name': emp.name or '',
                'initials': initials(emp.name or ''),
                'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id,
                'job': emp.job_title or (emp.job_id.name if emp.job_id else ''),
                'department': (emp.department_id.name
                               if emp.department_id else ''),
            })
        return out

    @api.model
    def _celebrations(self, nxt, ids):
        """NEXT month's birthdays and work anniversaries.

        Asked of the SAME method the wall's side rail asks — a month out, for a
        month — rather than derived a second time here.
        """
        today = fields.Date.context_today(self)
        offset = max(0, (nxt - today).days)
        after = (nxt.replace(year=nxt.year + 1, month=1)
                 if nxt.month == 12 else nxt.replace(month=nxt.month + 1))
        span = (after - nxt).days - 1
        rows = self.env['pb.rnr.celebration'].upcoming_celebrations(
            days=span, company_ids=ids, offset=offset)
        return rows[:CELEBRATION_CAP]

    @api.model
    def _winners(self, ids):
        cycle = self.env['pb.rnr.cycle'].fresh_winners(company_ids=ids)
        if not cycle:
            return {}
        Nom = self.env['pb.rnr.nomination'].sudo()
        rows = []
        for rec in cycle.top_ids:
            if rec.outcome not in ('recognised', 'awarded'):
                continue
            emp = Nom._person(rec.nominee_id)
            rows.append({
                'name': emp.name or '',
                'initials': initials(emp.name or ''),
                'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id,
                'value': rec.value_id.sudo().name or '',
                'color': rec.value_id.sudo().color or 'primary',
                'ink': value_hex(rec.value_id.sudo().color)[0],
                'wash': value_hex(rec.value_id.sudo().color)[1],
            })
        return {'name': cycle.name or '', 'rows': rows} if rows else {}

    # ------------------------------------------------------------- rendering
    @api.model
    def render(self, month=None, company_ids=None, payload=None):
        """The digest as HTML. The preview and the send use the same call."""
        data = payload or self.build(month=month, company_ids=company_ids)
        return self.env['ir.qweb']._render('pb_rnr.mail_digest', data)

    # ---------------------------------------------------------- the sending
    @api.model
    def _cron_monthly_digest(self):
        """The month that has JUST FINISHED, not the one we are in.

        A mood board about a month with two days in it is a mood board about
        nothing, so the job runs daily and always asks for last month — and the
        month stamp means the first tick after the turn of the month is the only
        one that sends anything. A monthly `interval_type` that misses its tick
        misses the month; a daily job that remembers which month it has done
        cannot.
        """
        today = fields.Date.context_today(self)
        last = fields.Date.subtract(today.replace(day=1), days=1)
        return self.send_digest(month=last)

    @api.model
    def send_digest(self, month=None, force=False, company_ids=None):
        """Build it, decide who gets it, and be honest about the answer.

        Returns `{ok, sent, would, recipients, mode, month, msg, skipped}`.
        `mode` is one of `off` / `test` / `broadcast` / `already`, and every
        screen that reports this prints the mode rather than a bare number: a
        job that says "0 sent" without saying WHY is the thing R54 is about.
        """
        stamp = self.month_stamp(month)
        payload = self.build(month=month, company_ids=company_ids)
        test_to = (param(self.env, P_DIGEST_TEST) or '').strip()
        on = flag(self.env, P_DIGEST_MAIL)
        already = (param(self.env, P_DIGEST_STAMP) or '').strip()

        # A TEST SEND NEVER CONSUMES THE MONTH. Reading your own draft must not
        # be able to cancel the real thing.
        if test_to:
            return self._deliver(payload, [test_to], stamp, mode='test')

        if not on:
            people = self._recipients(company_ids)
            _logger.info(
                'pb_rnr: the monthly digest is switched off. %s would have '
                'received the %s mood board.',
                counted(len(people), 'person', 'people'),
                payload['month_label'])
            return {
                'ok': False, 'mode': 'off', 'sent': 0, 'would': len(people),
                'recipients': 0, 'month': payload['month_label'],
                'skipped': 0,
                'msg': _(
                    "The monthly email is switched off. %(n)s would have "
                    "received the %(month)s mood board.",
                    n=counted(len(people), _('person'), _('people')),
                    month=payload['month_label']),
            }

        if already == stamp and not force:
            _logger.info('pb_rnr: the %s mood board has already gone out.',
                         payload['month_label'])
            return {
                'ok': False, 'mode': 'already', 'sent': 0, 'would': 0,
                'recipients': 0, 'month': payload['month_label'], 'skipped': 0,
                'msg': _("The %s mood board has already gone out this month.",
                         payload['month_label']),
            }

        return self._deliver(payload, self._recipients(company_ids), stamp,
                             mode='broadcast')

    @api.model
    def _recipients(self, company_ids=None):
        """Work email addresses, de-duplicated. One person, one message."""
        ids = list(company_ids if company_ids is not None
                   else (self.env.companies.ids or []))
        domain = [('active', '=', True), ('work_email', '!=', False)]
        if ids:
            domain.append(('company_id', 'in', ids))
        rows = self.env['hr.employee'].sudo().search_read(
            domain, ['work_email'])
        seen, out = set(), []
        for row in rows:
            mail = (row.get('work_email') or '').strip().lower()
            if not mail or mail in seen:
                continue
            seen.add(mail)
            out.append(mail)
        return out

    def _deliver(self, payload, addresses, stamp, mode='broadcast'):
        """Queue the messages. Best-effort per address, capped, honest counts."""
        body = self.render(payload=payload)
        subject = _("The %s mood board", payload['month_label'])
        Mail = self.env['mail.mail'].sudo()
        sent, skipped, capped = 0, 0, False
        for address in addresses:
            if sent >= MAIL_CAP:
                capped = True
                break
            try:
                Mail.create({
                    'subject': subject,
                    'email_to': address,
                    'body_html': body,
                    'auto_delete': True,
                })
                sent += 1
            except Exception:               # noqa: BLE001 — one address, not all
                _logger.exception('pb_rnr: the mood board could not be queued '
                                  'for %s', address)
                skipped += 1
        if mode == 'broadcast' and sent:
            set_param(self.env, P_DIGEST_STAMP, stamp)
        _logger.info('pb_rnr: the %s mood board went to %s (%s).',
                     payload['month_label'],
                     counted(sent, 'address', 'addresses'), mode)
        msg = (_("The %(month)s mood board was sent to %(to)s, and to nobody "
                 "else.", month=payload['month_label'], to=addresses[0])
               if mode == 'test' and addresses else
               _("The %(month)s mood board went to %(n)s.",
                 month=payload['month_label'],
                 n=counted(sent, _('person'), _('people'))))
        return {
            'ok': bool(sent), 'mode': mode, 'sent': sent,
            'would': len(addresses), 'recipients': len(addresses),
            'month': payload['month_label'], 'skipped': skipped,
            'capped': capped, 'msg': msg,
        }
