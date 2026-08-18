# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Publishing a roster, and telling the people in it.

TWO CHANNELS, THREE COUNTS
--------------------------
An employee reaches a published shift either through the portal (they have a
login) or through a mailed token link (they have a work email). Some have
neither, and a publish flow that does not SAY so is the reason a roster gets
published into silence — so ``publish_shifts_notified`` returns three numbers
and the cockpit toast reads "published N · notified M · no channel K".

WHY `publish_shifts` ITSELF IS UNTOUCHED
----------------------------------------
`pb_schedule`'s module docstring freezes the seven base-facade methods'
payload SHAPES, and `publish_shifts` is one of them: it returns an int and it
keeps returning an int. This is a NEW method beside it (the same reasoning P2
used for `get_schedule_data` beside `get_grid_data`), so a caller that wants
counts asks for counts and every existing caller is unaffected. Both go through
`hr.shift.planning.action_publish`, which is where the tokens are minted — the
model is the seam, not the facade, so a shift published from a form view, from
`pb_demo` or from a future surface is acknowledgeable too (W31's shape).

MAIL IS OFF BY DEFAULT, ON PURPOSE
-----------------------------------
`pb_ess_workforce.publish_mail` (an ir.config_parameter) gates the email, and
it defaults to '0'. Publishing a fortnight on this tenant is ~1 500 shifts; a
module that mails on install would have discovered that at 4 500 messages, and
C18.48's discipline is that a demo world never gets to find out. A real tenant
sets the parameter to '1'. The count is honest either way: when mail is off,
`notified` counts only the portal channel and the payload says `mail_enabled:
False`, so the toast can never claim an email that was not sent.

AND IT IS BEST-EFFORT, ALWAYS
------------------------------
Every send is inside its own try/except and a failure only increments the
skipped count. A publish that half-worked because an SMTP server was down would
be the worst possible outcome: the roster is the source of truth, the email is a
courtesy, and the courtesy must never be able to hold the truth hostage.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

_MAIL_PARAM = 'pb_ess_workforce.publish_mail'

# A ceiling on one publish's mail burst. Past it the emails are skipped and
# REPORTED rather than queued: 200 messages is a notification, 2 000 is an
# incident, and the difference has to be a number somebody chose.
_MAIL_CAP = 200


class ShiftPlanningGridNotify(models.TransientModel):
    _inherit = 'hr.shift.planning.grid'

    # ------------------------------------------------------------- channels
    @api.model
    def _ess_mail_enabled(self):
        return (self.env['ir.config_parameter'].sudo().get_param(
            _MAIL_PARAM, '0') or '0').strip() in ('1', 'true', 'True')

    @api.model
    def _ess_base_url(self):
        return (self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url') or '').rstrip('/')

    # -------------------------------------------------------------- publish
    @api.model
    def publish_shifts_notified(self, week_start_str, department_id=False,
                                num_days=7):
        """Publish the window and report what reached whom.

        Returns ``{published, notified, portal, emailed, no_channel,
        mail_enabled, capped}``. `notified` is the union — a person with both
        channels is one person, not two.
        """
        self._require_officer()
        # `publish_shifts` re-runs the same search and returns only the count;
        # this needs the RECORDS, so the window is resolved once here and the
        # base method's domain is reproduced rather than called and re-queried.
        # The shared thing is `action_publish`, which is the part that matters.
        week_start = fields.Date.from_string(week_start_str)
        week_end = week_start + timedelta(days=int(num_days or 7) - 1)
        domain = [('date', '>=', week_start), ('date', '<=', week_end),
                  ('state', '=', 'draft')]
        if department_id:
            domain.append(('department_id', '=', int(department_id)))
        shifts = self.env['hr.shift.planning'].search(domain)
        shifts.action_publish()
        res = self.env['hr.shift.planning'].sudo().browse(
            shifts.ids)._ess_notify_published()
        res['published'] = len(shifts)
        return res


class HrShiftPlanningNotify(models.Model):
    _inherit = 'hr.shift.planning'

    def _ess_notify_published(self):
        """Tell each employee in `self` that they have a shift. Never raises."""
        Grid = self.env['hr.shift.planning.grid']
        mail_on = Grid._ess_mail_enabled()
        base = Grid._ess_base_url()

        portal = set()          # employees who can see it in the portal
        mailed = set()          # employees a link actually went out to
        no_channel = set()      # employees with neither
        emailed = 0
        capped = False

        by_emp = {}
        for shift in self:
            if shift.employee_id:
                by_emp.setdefault(shift.employee_id, []).append(shift)

        for emp, emp_shifts in by_emp.items():
            has_portal = bool(emp.user_id and emp.user_id.active)
            has_mail = bool((emp.work_email or '').strip())
            if has_portal:
                portal.add(emp.id)
            if not (has_portal or has_mail):
                # The number this whole method exists for. A person with no
                # channel is not "notified 0 times", they are a hole in the
                # roster's delivery, and the toast has to say so.
                no_channel.add(emp.id)
            if not (mail_on and has_mail):
                continue
            for shift in emp_shifts:
                if emailed >= _MAIL_CAP:
                    capped = True
                    break
                if shift._ess_queue_ack_mail(base):
                    emailed += 1
                    mailed.add(emp.id)
            if capped:
                break

        return {
            # the UNION: somebody with a login and an email is one person
            'notified': len(portal | mailed),
            'portal': len(portal),
            'emailed': emailed,
            'no_channel': len(no_channel),
            'mail_enabled': mail_on,
            'capped': capped,
        }

    def _ess_queue_ack_mail(self, base_url):
        """One shift, one queued mail.mail. Best-effort; returns True if queued.

        The message is QUEUED, not sent: `mail.mail.create` without `send()`
        leaves it for the outgoing cron, which is the same discipline every
        other mail path in this codebase follows and the only one that lets a
        test count messages without an SMTP server anywhere near it.
        """
        self.ensure_one()
        emp = self.employee_id
        email = (emp.work_email or '').strip()
        token = self.sudo().ack_token
        if not (email and token):
            return False
        try:
            tz = self.env['pb.ess.workforce'].sudo()._tzinfo(emp)
            Ess = self.env['pb.ess.workforce'].sudo()
            body = self.env['ir.qweb']._render(
                'pb_ess_workforce.ack_mail_body', {
                    'who': (emp.name or '').split(' ')[-1],
                    'day': self.date.strftime('%A %d %B %Y') if self.date else '',
                    'start': Ess._hhmm(self.start_datetime, tz),
                    'end': Ess._hhmm(self.end_datetime, tz),
                    'name': self.shift_template_id.name or '',
                    'url': '%s/work/ack/%s' % (base_url, token),
                })
            self.env['mail.mail'].sudo().create({
                'subject': _("Your shift on %s", self.date.strftime('%d %b')
                             if self.date else ''),
                'email_to': email,
                'body_html': body,
                'auto_delete': True,
            })
        except Exception as e:                                # pragma: no cover
            # Best-effort by contract (§3.2). The publish has already happened
            # and is committed; a mail failure is logged and counted, never
            # raised, and never rolled back onto the roster.
            _logger.warning('pb_ess_workforce: ack mail for shift %s skipped: %s',
                            self.id, e)
            return False
        return True
