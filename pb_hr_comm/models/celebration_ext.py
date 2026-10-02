# -*- coding: utf-8 -*-
"""The birthday and anniversary cards, made into cards.

THE ENGINE ALREADY EXISTS AND IS NOT BEING REBUILT. `pb_rnr`'s celebration
engine has found the birthdays and the work anniversaries on this database
since the first wave: it reads the day and month off the employee record,
keeps one row per person per year so nobody is congratulated twice, and sends
one message with the address on it. All of that stays exactly as it is. What
it did NOT have was a card — the two messages were four lines of plain text —
and a designed card in the day-one email is the owner's own ruling about what
a poster is (D7).

WHY THIS IS A PYTHON SWAP AND NOT A VIEW INHERIT. The obvious way is to xpath
into `pb_rnr.mail_birthday` and replace it. Two things are wrong with that: an
xpath that misses aborts the WHOLE module load with the real error only in the
server log (R213), and a card is not a modification of four lines of prose —
it is a different document. So this module ships its own two templates and
swaps them in at the one seam that decides which template is rendered, which
is the precedent P10 set when it borrowed P5's machine and had to change its
words (R103). `pb_rnr`'s own seeds are untouched, no `noupdate` dance is
needed, and a database without this module keeps the plain version.

AND IT STAYS SWITCHED OFF. `pb_rnr.anniv_mail` is 0 on this database and this
phase does not change it (owner ruling D17) — one switch covers both kinds,
which was verified in the engine rather than assumed. The calendar says so on
screen, with the name of the switch, so a thing that is off cannot be reported
as broken (R54).

THE SUBJECT LINE WAS UNGRAMMATICAL AT ONE YEAR. "1 years with us today" is how
a screen announces it was written by a programme (R46). The engine builds that
subject in the same method this one replaces, so it is fixed here for both
kinds rather than reached for in another module's seeded data.
"""

import logging

from odoo import _, models

from .comm_common import counted

_logger = logging.getLogger(__name__)

#: The two cards this module renders instead of the plain text.
CARD_BIRTHDAY = 'pb_hr_comm.card_birthday'
CARD_ANNIVERSARY = 'pb_hr_comm.card_anniversary'


class PbRnrCelebrationCards(models.AbstractModel):
    _inherit = 'pb.rnr.celebration'

    def _send_celebration(self, emp, row, to):
        """One queued message, addressed explicitly (R6), inside a card.

        Everything about WHO is congratulated, WHEN and HOW OFTEN is the
        engine's and is untouched — this method is only what the message looks
        like. If either template is missing for any reason the original is
        used, because a company that cannot render a card should still get its
        birthday email.
        """
        is_birthday = row.get('kind') == 'birthday'
        template = CARD_BIRTHDAY if is_birthday else CARD_ANNIVERSARY
        if not self.env.ref(template, raise_if_not_found=False):
            return super()._send_celebration(emp, row, to)
        years = int(row.get('years') or 0)
        try:
            body = self.env['ir.qweb']._render(template, {
                'person': emp.name or '',
                'first_name': (emp.name or '').split(' ')[-1],
                'years': years,
                'years_label': counted(years, _('year'), _('years')),
                'day': row.get('day_label') or '',
                'company': emp.sudo().company_id.name or '',
            })
        except Exception:               # noqa: BLE001 — a card is a courtesy
            _logger.warning('pb_hr_comm: the celebration card could not be '
                            'drawn for employee %s', emp.id, exc_info=True)
            return super()._send_celebration(emp, row, to)
        subject = _("Happy birthday") if is_birthday else _(
            "%(n)s %(years)s with us today", n=years,
            years=counted(years, _('year'), _('years')))
        self.env['mail.mail'].sudo().create({
            'subject': subject,
            'email_to': to,
            'body_html': body,
            'auto_delete': True,
        })
        return True
