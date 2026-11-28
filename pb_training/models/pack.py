# -*- coding: utf-8 -*-
"""The training pack: the numbers, by email, every week or every month.

A DAILY JOB THAT REMEMBERS WHICH PERIOD IT HAS DONE, and never a weekly or
monthly `ir.cron`. A monthly cron that misses its tick misses the MONTH — the
server was down, the database was restoring, somebody deployed at midnight —
and nothing anywhere says so. A daily job that asks "have I sent the pack for
the period that has just ended" cannot miss one: the first tick after the turn
sends it, every tick after that does nothing, and a period the job slept
through goes out the next morning with the right dates on it. The precedent is
`pb_rnr/models/digest.py:222` and it is copied rather than re-invented.

IT SHIPS OFF, AND OFF IT SAYS SO (R54). The address is one nobody has typed
yet, so the first night after an install would otherwise post a spreadsheet of
the company's training figures to whatever the fallback happened to be. Off,
the job still runs, still builds the numbers and LOGS what it would have sent
and to whom — a thing that is off and does not say so is reported as broken.

THE PERIOD THAT HAS JUST FINISHED, never the one we are in. A pack about a
month with two days in it is a pack about nothing.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .training_common import (
    GROUP_MANAGER, P_PACK, P_PACK_EMAIL, P_PACK_PERIOD, P_PACK_STAMP, counted,
    flag, text,
)

_logger = logging.getLogger(__name__)

#: A safety rail, not a page size (R76). The pack goes to the people who asked
#: for it — a handful of addresses — and a misconfigured list must not be able
#: to post a spreadsheet to the whole company.
MAIL_CAP = 20


class PbTrainingPack(models.AbstractModel):
    """The report pack. An AbstractModel because it owns no rows."""
    _name = 'pb.training.pack'
    _description = 'Payobook Training — the report pack'

    # =====================================================================
    #  which period
    # =====================================================================
    @api.model
    def _period(self):
        return 'weekly' if text(self.env, P_PACK_PERIOD, 'monthly') \
            .lower().startswith('week') else 'monthly'

    @api.model
    def _window(self, today=None):
        """(from, to, stamp, label) for the period that has JUST ENDED.

        THE SERVER'S CLOCK (R154). The stamp is what makes the job idempotent
        and it is the period's own canonical key — `2026-W37` or `2026-09` —
        rather than the day it was sent, so a job that runs twice on different
        days inside one period still sends once.
        """
        today = today or fields.Date.today()
        if self._period() == 'weekly':
            # Last week: the Monday before this week's Monday, to the Sunday.
            this_monday = today - timedelta(days=today.weekday())
            start = this_monday - timedelta(days=7)
            end = this_monday - timedelta(days=1)
            iso = start.isocalendar()
            return start, end, '%s-W%02d' % (iso[0], iso[1]), \
                _("week of %s", start.strftime('%d %b %Y'))
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        start = end.replace(day=1)
        return start, end, start.strftime('%Y-%m'), start.strftime('%B %Y')

    @api.model
    def _recipients(self):
        """Whoever the pack was asked for. De-duplicated, one person one copy.

        NO FALLBACK TO A GROUP. An address nobody has typed means nobody has
        asked for this pack, and inventing a recipient list is how a
        spreadsheet of somebody's training record reaches a person who never
        wanted it.
        """
        raw = text(self.env, P_PACK_EMAIL, '')
        seen, out = set(), []
        for part in raw.replace(';', ',').split(','):
            address = part.strip()
            key = address.lower()
            if not address or '@' not in address or key in seen:
                continue
            seen.add(key)
            out.append(address)
        return out[:MAIL_CAP]

    # =====================================================================
    #  the job
    # =====================================================================
    @api.model
    def _cron_pack(self):
        return self.send_pack()

    @api.model
    def run_now(self):
        """The same job, by hand — and it does EXACTLY what the night does.

        R53: a "run it now" button that runs a subset of the job reports a
        number nobody can compare with the morning's log. It is `force=True`
        only in the sense that a manager pressing it means it: the stamp is
        still written, so pressing it twice sends once.
        """
        if not (self.env.user.has_group(GROUP_MANAGER)
                or self.env.user._is_admin()):
            raise AccessError(_(
                "Only a training manager can send the pack by hand."))
        return self.send_pack(force=True)

    @api.model
    def send_pack(self, force=False, today=None):
        """Build it, decide who gets it, and be honest about the answer.

        Returns `{ok, mode, sent, would, period, label, msg}`. `mode` is one of
        `off` / `nobody` / `already` / `sent`, and every screen that reports
        this prints the MODE rather than a bare number: a job that says "0
        sent" without saying why is the thing R54 is about.
        """
        start, end, stamp, label = self._window(today)
        people = self._recipients()
        on = flag(self.env, P_PACK)
        already = text(self.env, P_PACK_STAMP, '')

        if not on:
            _logger.info(
                'pb_training: the training pack is switched off '
                '(pb_training.report_pack). The %s pack would have gone to '
                '%s.', label,
                ', '.join(people) or _('nobody — no address is set'))
            return self._answer('off', 0, len(people), stamp, label, _(
                "The training pack is switched off. The %(label)s pack would "
                "have gone to %(who)s.", label=label,
                who=', '.join(people) or _("nobody — no address is set yet")))

        if not people:
            _logger.info('pb_training: the training pack is on but no address '
                         'is set (pb_training.report_pack_email)')
            return self._answer('nobody', 0, 0, stamp, label, _(
                "The training pack is switched on but nobody is set to "
                "receive it. Put an address in the training settings."))

        if already == stamp and not force:
            return self._answer('already', 0, len(people), stamp, label, _(
                "The %s pack has already gone out.", label))

        return self._deliver(start, end, stamp, label, people)

    @api.model
    def _answer(self, mode, sent, would, stamp, label, msg):
        return {'ok': mode == 'sent', 'mode': mode, 'sent': sent,
                'would': would, 'period': stamp, 'label': label, 'msg': msg}

    # =====================================================================
    #  what is in it
    # =====================================================================
    @api.model
    def _deliver(self, start, end, stamp, label, people):
        Analytics = self.env['pb.training.analytics']
        board = Analytics.get_numbers(fields.Date.to_string(start),
                                      fields.Date.to_string(end))
        body = self._body(board, label)
        attachment = self._sheet(board, label)
        Mail = self.env['mail.mail'].sudo()
        subject = _("Training — %s", label)
        sent, skipped = 0, 0
        for address in people:
            try:
                values = {
                    'subject': subject,
                    'email_to': address,
                    'body_html': body,
                    'auto_delete': False,
                }
                if attachment:
                    values['attachment_ids'] = [(4, attachment.id)]
                Mail.create(values)
                sent += 1
            except Exception:           # noqa: BLE001 — one address, not all
                _logger.exception('pb_training: the training pack could not be '
                                  'queued for %s', address)
                skipped += 1
        if sent:
            self.env['ir.config_parameter'].sudo().set_param(P_PACK_STAMP,
                                                             stamp)
        _logger.info('pb_training: the %s training pack went to %s%s', label,
                     counted(sent, _('1 address'), _('%s addresses') % sent),
                     ' (%s could not be queued)' % skipped if skipped else '')
        return self._answer('sent', sent, len(people), stamp, label, _(
            "The %(label)s pack went to %(n)s.", label=label,
            n=counted(sent, _('1 address'), _('%s addresses') % sent)))

    @api.model
    def _body(self, board, label):
        """A short summary, rendered from a template rather than built here.

        Server-side QWeb has NO `t-key` (R5) and no render key may be called
        `request` (R4); both are the template's business and both are checked
        there.
        """
        try:
            return self.env['ir.qweb']._render('pb_training.mail_pack', {
                'board': board, 'label': label,
            })
        except Exception:                   # noqa: BLE001 — never lose a send
            _logger.warning('pb_training: the pack body could not be rendered',
                            exc_info=True)
            return '<p>%s</p>' % (board.get('headline') or label)

    @api.model
    def _sheet(self, board, label):
        """The spreadsheet, as a real attachment so it can ride an email.

        THE ONE PLACE THIS PRODUCT LEAVES AN EXPORT BEHIND, and it is because
        a mail attachment has to be a row. It is bound to nothing (`res_model`
        empty) and named after the period, so it is findable and deletable —
        unlike the lens's own download, which never becomes a record at all.
        """
        try:
            export = self.env['pb.training.analytics'].export_xlsx(
                board['from'], board['to'])
            if not export or not export.get('file_b64'):
                return None
            return self.env['ir.attachment'].sudo().create({
                'name': _("Training %s.xlsx", label),
                'datas': export['file_b64'],
                'mimetype': export['mimetype'],
            })
        except Exception:                   # noqa: BLE001 — never lose a send
            _logger.warning('pb_training: the pack spreadsheet could not be '
                            'built', exc_info=True)
            return None

    # =====================================================================
    #  what the board shows about it
    # =====================================================================
    @api.model
    def status(self):
        """What the screen says about the pack. Never raises."""
        try:
            start, end, stamp, label = self._window()
            return {
                'on': flag(self.env, P_PACK),
                'period': self._period(),
                'to': self._recipients(),
                'next_label': label,
                'last': text(self.env, P_PACK_STAMP, ''),
                'sent_already': text(self.env, P_PACK_STAMP, '') == stamp,
            }
        except Exception:                   # noqa: BLE001
            _logger.warning('pb_training: the pack status could not be read',
                            exc_info=True)
            return {'on': False, 'period': 'monthly', 'to': [],
                    'next_label': '', 'last': '', 'sent_already': False}
