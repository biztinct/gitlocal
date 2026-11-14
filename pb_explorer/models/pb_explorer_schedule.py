# -*- coding: utf-8 -*-
"""Send a saved Explorer view regularly by email (WDGAP QF2 C).

Doctrine
--------
* **Each recipient gets THEIR OWN numbers.** The query runs
  `with_user(recipient)` with NO company in the context, so `env.companies`
  falls back to that person's own companies and `who sees what` narrows the
  divisions (FACTS §1, R2). A recipient who may no longer open the Explorer
  is skipped and the skip is written down.
* **No email on this database is normal** (rize, sudima, p0clone — ledger
  convention 9). Without an active outgoing mail server nothing is queued and
  each recipient's line says "Not sent — email is switched off". Never an
  error, never a retry.
* **No double send.** The cron stamps `next_due` forward BEFORE it builds
  anything, and commits that stamp outside tests, so a crash half way cannot
  make the next tick send the same thing again. "Send now" never moves it.
* **Queued, never forced.** One `mail.mail` per recipient with the Excel file
  attached; the platform's mail queue sends it (precedent
  `pb_rnr/models/digest.py`, `pb_demo_portal/models/signup_report.py`).
* **The pay-run hook only marks due** (`hr_payslip_run.py`); the cron sends.
"""
import base64
import logging
import threading
from datetime import datetime, time as dtime, timedelta

import pytz
from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import formataddr
from odoo.tools.misc import formatLang

from .pb_explorer import WORDS_LANG

try:  # WHITELABEL — the tenant's own name for the product
    from odoo.addons.biz_debrand.models.brand import product_label
except Exception:  # pragma: no cover — biz_debrand absent on this build
    def product_label(env, default='Payobook'):
        return default

_logger = logging.getLogger(__name__)

SEND_HOUR = 7                      # 07:00 in the company's own time
FALLBACK_TZ = 'Asia/Ho_Chi_Minh'   # UTC+7 when the company names no zone
RECIPIENT_CAP = 25
SCHEDULE_CAP = 20
HISTORY = 10
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

CADENCES = [('weekly', 'Every week'), ('monthly', 'Every month'),
            ('payrun', 'After each pay run is finished')]
WEEKDAYS = [('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
            ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'),
            ('6', 'Sunday')]
LOG_STATES = [('queued', 'Sent'), ('email_off', 'Email is switched off'),
              ('no_access', 'Can no longer open the Explorer'),
              ('no_email', 'No email address'), ('failed', 'Could not be made')]
TRIGGERS = [('schedule', 'On schedule'), ('now', 'Send now'),
            ('payrun', 'After a pay run')]


def _testing():
    """Inside a test the cursor may not be committed (the transaction is the
    test's); Odoo 19 says so through `module.current_test`, not the thread."""
    from odoo.modules import module as odoo_module
    return bool(getattr(odoo_module, 'current_test', False)
                or getattr(threading.current_thread(), 'testing', False))


def _weekday_words(env):
    """Through `env._` HERE, never only in the selection list: a literal in a
    module-level list is invisible to the string extractor (T24 / GR58), and a
    bare `_()` in a module-level function cannot see the recipient's language
    from a scheduled job."""
    return {'0': env._("Monday"), '1': env._("Tuesday"),
            '2': env._("Wednesday"), '3': env._("Thursday"),
            '4': env._("Friday"), '5': env._("Saturday"),
            '6': env._("Sunday")}


def _state_words(env):
    return {
        'queued': env._("Sent"),
        'email_off': env._("Not sent — email is switched off"),
        'no_access': env._("Skipped — can no longer open the Explorer"),
        'no_email': env._("Skipped — no email address"),
        'failed': env._("Not sent — the file could not be made"),
    }


def _trigger_words(env):
    return {'schedule': env._("On schedule"), 'now': env._("Sent now"),
            'payrun': env._("After a pay run")}


class PbExplorerSchedule(models.Model):
    _name = 'pb.explorer.schedule'
    _description = 'Explorer view sent regularly'
    _order = 'id'

    view_id = fields.Many2one('pb.explorer.view', string='Saved view',
                              required=True, index=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Set up by', required=True,
                              index=True, ondelete='cascade',
                              default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    cadence = fields.Selection(CADENCES, string='How often', required=True,
                               default='weekly')
    weekday = fields.Selection(WEEKDAYS, string='Day of the week', default='0')
    monthday = fields.Integer(string='Day of the month', default=1)
    recipient_ids = fields.Many2many(
        'res.users', 'pb_explorer_schedule_user_rel', 'schedule_id', 'user_id',
        string='Sent to')
    active = fields.Boolean(default=True)
    next_due = fields.Datetime(string='Next send', index=True)
    last_run = fields.Datetime(string='Last send')
    send_count = fields.Integer(string='Sends so far', default=0)
    log_ids = fields.One2many('pb.explorer.schedule.log', 'schedule_id',
                              string='History')

    # ------------------------------------------------------------- timing
    def _pbx_tz(self):
        """The company's own time zone: its address, then its working hours
        (when they say something other than UTC), then UTC+7."""
        self.ensure_one()
        company = self.company_id.sudo()
        for name in (company.partner_id.tz,
                     company.resource_calendar_id.tz
                     if company.resource_calendar_id.tz != 'UTC' else False):
            if name:
                try:
                    return pytz.timezone(name)
                except pytz.UnknownTimeZoneError:
                    continue
        return pytz.timezone(FALLBACK_TZ)

    def _pbx_today(self):
        """Today in the company's own time — what "last month" is about."""
        self.ensure_one()
        return pytz.utc.localize(fields.Datetime.now()).astimezone(
            self._pbx_tz()).date()

    def _next_after(self, after):
        """The next send strictly after `after` (naive UTC), as naive UTC.
        After-each-pay-run has no clock time: it is marked due by the run."""
        self.ensure_one()
        if self.cadence == 'payrun':
            return False
        tz = self._pbx_tz()
        here = pytz.utc.localize(after).astimezone(tz)

        def at(day):
            return tz.localize(datetime.combine(day, dtime(SEND_HOUR)))

        if self.cadence == 'weekly':
            wd = int(self.weekday or 0)
            day = here.date() + timedelta(days=(wd - here.weekday()) % 7)
            when = at(day)
            if when <= here:
                when = at(day + timedelta(days=7))
        else:
            md = min(max(int(self.monthday or 1), 1), 28)
            day = here.date().replace(day=md)
            when = at(day)
            if when <= here:
                when = at(day + relativedelta(months=1))
        return when.astimezone(pytz.utc).replace(tzinfo=None)

    # ------------------------------------------------------------- words
    def _pbx_sentence(self):
        """"Every Monday morning, to 3 people, as an Excel file with a link"."""
        self.ensure_one()
        n = len(self.recipient_ids)
        if n == 1 and self.recipient_ids == self.user_id:
            who = _("you")
        elif n == 1:
            who = _("1 person")
        else:
            who = _("%s people", n)
        if self.cadence == 'weekly':
            return _("Every %(day)s morning, to %(who)s, as an Excel file "
                     "with a link",
                     day=_weekday_words(self.env).get(self.weekday or '0'), who=who)
        if self.cadence == 'monthly':
            return _("On day %(day)s of every month, in the morning, to "
                     "%(who)s, as an Excel file with a link",
                     day=self.monthday or 1, who=who)
        return _("After each pay run is finished, to %(who)s, as an Excel "
                 "file with a link", who=who)

    def _pbx_when(self, value):
        """A stored UTC moment in the company's own time, in plain words."""
        if not value:
            return ''
        local = pytz.utc.localize(value).astimezone(self._pbx_tz())
        return local.strftime('%Y-%m-%d %H:%M')

    def _pbx_history(self):
        self.ensure_one()
        Log = self.env['pb.explorer.schedule.log'].sudo()
        logs = Log.search([('schedule_id', '=', self.id)],
                          order='batch desc, id', limit=HISTORY * RECIPIENT_CAP)
        words, triggers = _state_words(self.env), _trigger_words(self.env)
        out, index = [], {}
        for log in logs:
            if log.batch not in index:
                if len(out) >= HISTORY:
                    continue
                index[log.batch] = {
                    'batch': log.batch,
                    'when': self._pbx_when(log.create_date),
                    'trigger': triggers.get(log.trigger, ''),
                    'lines': [], 'sent': 0,
                }
                out.append(index[log.batch])
            entry = index[log.batch]
            entry['lines'].append({
                'name': log.user_id.name or _("Someone"),
                'state': log.state,
                'label': words.get(log.state, ''),
            })
            if log.state == 'queued':
                entry['sent'] += 1
        for entry in out:
            total = len(entry['lines'])
            entry['summary'] = (
                _("Sent to %(sent)s of %(total)s", sent=entry['sent'],
                  total=total) if entry['sent']
                else _("Nothing sent"))
        return out

    def _pbx_payload(self):
        self.ensure_one()
        return {
            'id': self.id,
            'view_id': self.view_id.id,
            'cadence': self.cadence,
            'weekday': self.weekday or '0',
            'monthday': self.monthday or 1,
            'recipients': [{'id': u.id, 'name': u.name}
                           for u in self.recipient_ids.sudo()],
            'active': bool(self.active),
            'sentence': self._pbx_sentence(),
            'next_due': self._pbx_when(self.next_due) if self.active else '',
            'last_run': self._pbx_when(self.last_run),
            'history': self._pbx_history(),
        }

    # ---------------------------------------------------- who may receive
    @api.model
    def _pbx_can_open(self, user):
        try:
            self.env['pb.explorer'].with_user(user)._require()
            return True
        except AccessError:
            return False

    @api.model
    def _pbx_offer(self):
        """Logins that may receive a view: active, internal, with an email,
        able to open the Explorer, and in one of your companies."""
        me = self.env.user
        users = self.env['res.users'].sudo().search([
            ('share', '=', False), ('active', '=', True),
            ('email', '!=', False),
            ('company_ids', 'in', me.company_ids.ids)], limit=500,
            order='name')
        return users.filtered(self._pbx_can_open)

    @api.model
    def _pbx_mail_on(self):
        """Is outgoing email switched on HERE? An active outgoing mail server
        record (precedent `pb_hiring/models/connections.py:129`)."""
        return bool(self.env['ir.mail_server'].sudo().search_count(
            [('active', '=', True)]))

    # ------------------------------------------------------------- sending
    @api.model
    def _cron_send_due(self):
        """The ONE hourly job: send every schedule that is due, once."""
        now = fields.Datetime.now()
        due = self.sudo().search([('active', '=', True),
                                  ('next_due', '!=', False),
                                  ('next_due', '<=', now)],
                                 order='next_due, id', limit=200)
        for sched in due:
            trigger = 'payrun' if sched.cadence == 'payrun' else 'schedule'
            try:
                with self.env.cr.savepoint():
                    sched.write({'next_due': sched._next_after(now),
                                 'last_run': now})
            except Exception:                            # noqa: BLE001
                _logger.exception('pb_explorer: schedule %s could not be '
                                  'moved on; it is left alone', sched.id)
                continue
            if not _testing():
                # The stamp is durable before anything is built (R5).
                self.env.cr.commit()
            try:
                with self.env.cr.savepoint():
                    sched._send_one(trigger)
            except Exception:                            # noqa: BLE001
                _logger.exception('pb_explorer: schedule %s failed; the '
                                  'others carry on', sched.id)
            if not _testing():
                self.env.cr.commit()
        return True

    def _send_one(self, trigger='schedule'):
        """One send to every recipient. Returns a small summary dict."""
        self.ensure_one()
        sched = self.sudo()
        batch = sched.send_count + 1
        sched.send_count = batch
        Log = self.env['pb.explorer.schedule.log'].sudo()
        recipients = sched.with_context(active_test=False).recipient_ids
        summary = {'sent': 0, 'skipped': 0, 'email_off': False}

        def log(user, state, mail=False):
            Log.create({'schedule_id': sched.id, 'batch': batch,
                        'trigger': trigger, 'user_id': user.id,
                        'state': state, 'mail_id': mail.id if mail else False})

        if not sched._pbx_mail_on():
            summary['email_off'] = True
            for user in recipients:
                log(user, 'email_off')
                summary['skipped'] += 1
            return summary
        for user in recipients:
            if not user.active or user.share:
                log(user, 'no_access')
                summary['skipped'] += 1
                continue
            if not user.email:
                log(user, 'no_email')
                summary['skipped'] += 1
                continue
            token = WORDS_LANG.set(user.lang or 'en_US')
            try:
                with self.env.cr.savepoint():
                    mail = sched._pbx_mail_for(user)
            except AccessError as exc:
                _logger.info('pb_explorer: schedule %s skipped user %s: %s',
                             sched.id, user.id, exc)
                log(user, 'no_access')
                summary['skipped'] += 1
                continue
            except Exception:                            # noqa: BLE001
                _logger.exception('pb_explorer: schedule %s could not be '
                                  'made for user %s', sched.id, user.id)
                log(user, 'failed')
                summary['skipped'] += 1
                continue
            finally:
                WORDS_LANG.reset(token)
            log(user, 'queued', mail)
            summary['sent'] += 1
        return summary

    def _pbx_link(self):
        """A link that opens the saved view in the Explorer. The app path is
        the product's own (`/bizapp` where the address is debranded)."""
        self.ensure_one()
        base = (self.env['ir.config_parameter'].sudo()
                .get_param('web.base.url') or '').rstrip('/')
        Module = self.env['ir.module.module'].sudo()
        prefix = '/bizapp' if Module.search_count(
            [('name', '=', 'biz_deroute'), ('state', '=', 'installed')]) \
            else '/odoo'
        return '%s%s/action-pb_explorer.action_pb_explorer#pbxv=%d' % (
            base, prefix, self.view_id.id)

    def _pbx_mail_for(self, user):
        """Build and QUEUE one recipient's email. Raises AccessError when the
        recipient may no longer open the Explorer."""
        self.ensure_one()
        ctx = dict(self.env.context)
        # THIS person's own companies, their default first — exactly what
        # env.companies falls back to with no company in the context
        # (odoo/orm/environments.py:266-282). Set explicitly because
        # `with_context(dict)` carries an existing `allowed_company_ids` over
        # when the new context leaves it out, and a job's or a caller's
        # companies must never become the recipient's (R2).
        own = user.sudo().company_ids.ids
        default = user.sudo().company_id.id
        ctx['allowed_company_ids'] = ([default] if default in own else []) + [
            c for c in own if c != default]
        ctx.update(lang=user.lang or 'en_US', tz=user.tz or False)
        explorer = self.env['pb.explorer'].with_user(user).with_context(ctx)
        explorer._require()
        env = explorer.env
        view = self.view_id.sudo()
        spec = view.with_context(ctx)._pbx_spec_now(self._pbx_today())
        lang = ctx['lang']
        period_note = view.with_context(lang=lang)._pbx_period_label()
        data, ex = explorer._xlsx_bytes(spec, title=view.name,
                                        period_note=period_note)
        payload = ex['payload']
        period = (payload.get('period') or {}).get('label') or env._("Everything")
        lines = self._pbx_headlines(env, payload)
        link = self._pbx_link()
        owner = self.user_id.sudo().name or ''
        subject = env._("%(view)s — %(period)s", view=view.name, period=period)
        body = Markup(
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
            'color:#1B1733;line-height:1.5;max-width:560px">'
            '<p style="margin:0 0 12px">{intro}</p>'
            '<ul style="margin:0 0 14px;padding-left:18px">{items}</ul>'
            '<p style="margin:0 0 14px">'
            '<a href="{link}" style="display:inline-block;padding:9px 16px;'
            'border-radius:8px;background:#5A4BB0;color:#ffffff;'
            'text-decoration:none;font-weight:600">{open}</a></p>'
            '<p style="margin:0 0 6px;color:#64748B;font-size:12.5px">{file}</p>'
            '<p style="margin:0;color:#64748B;font-size:12.5px">{why}</p>'
            '</div>').format(
                intro=env._("Here is “%(view)s” for %(period)s, with the "
                            "figures you are allowed to see.",
                            view=view.name, period=period),
                items=Markup('').join(Markup('<li>%s</li>') % escape(line)
                                      for line in lines),
                link=link,
                open=env._("Open this view in the Explorer"),
                file=env._("The full table is in the attached Excel file."),
                why=env._("You get this because %(owner)s set it up: "
                          "%(sentence)s. Ask them if you no longer need it.",
                          owner=owner,
                          sentence=self.with_context(lang=lang)
                          ._pbx_sentence()))
        company = self.company_id.sudo()
        sender = (self.env['ir.mail_server'].sudo()._get_default_from_address()
                  or company.email_formatted
                  or self.user_id.sudo().email_formatted)
        filename = '%s_%s_%s.xlsx' % (
            product_label(self.env).lower(),
            ''.join(c if c.isalnum() else '_' for c in view.name)[:40].strip('_')
            or 'view',
            self._pbx_today().isoformat())
        vals = {
            'subject': subject,
            'email_to': formataddr((user.name or '', user.email)),
            'body_html': body,
            'auto_delete': True,
            'attachment_ids': [(0, 0, {
                'name': filename,
                'datas': base64.b64encode(data),
                'mimetype': XLSX,
            })],
        }
        if sender:
            vals['email_from'] = sender
        return self.env['mail.mail'].sudo().create(vals)

    @api.model
    def _pbx_headlines(self, env, payload):
        """Two or three lines from the answer: one total per money, then the
        largest row, then the people behind it. Never a sum across monies."""
        lines = []
        measure = payload.get('measure_label') or ''
        parts = payload.get('parts') or [payload]
        for part in parts[:2]:
            cur = part.get('currency') or {}
            currency = env['res.currency'].sudo().browse(
                cur.get('id') or 0).exists() if cur else None
            total = part.get('grand_total') or 0.0
            if payload.get('measure_kind', 'money') == 'money' and currency:
                amount = formatLang(env, total, currency_obj=currency)
            else:
                amount = formatLang(env, total, digits=0)
            lines.append(env._("%(measure)s: %(amount)s",
                               measure=measure, amount=amount))
        first = parts[0] if parts else {}
        series = first.get('series') or []
        if series and len(series) > 1:
            lines.append(env._("Largest: %(name)s",
                               name=series[0].get('label') or ''))
        heads = (payload.get('heads') or {}).get('people') or 0
        if heads and len(lines) < 3:
            lines.append(env._("People behind these figures: %s", heads))
        if not series:
            lines = [env._("Nothing was paid in this period yet.")]
        return lines[:3]

    # ----------------------------------------------------- after a pay run
    @api.model
    def _mark_due_after_run(self, company_ids):
        """A pay run of these companies was finished: every after-each-run
        schedule of theirs becomes due now. Marks only; the cron sends."""
        if not company_ids:
            return 0
        now = fields.Datetime.now()
        scheds = self.sudo().search([('cadence', '=', 'payrun'),
                                     ('active', '=', True),
                                     ('company_id', 'in', list(company_ids))])
        todo = scheds.filtered(lambda s: not s.next_due or s.next_due > now)
        if todo:
            todo.write({'next_due': now})
        return len(scheds)


class PbExplorerScheduleLog(models.Model):
    _name = 'pb.explorer.schedule.log'
    _description = 'Explorer regular send, one line per person'
    _order = 'batch desc, id'

    schedule_id = fields.Many2one('pb.explorer.schedule', string='Schedule',
                                  required=True, index=True, ondelete='cascade')
    batch = fields.Integer(string='Send number', index=True)
    trigger = fields.Selection(TRIGGERS, string='How it was sent',
                               default='schedule')
    user_id = fields.Many2one('res.users', string='Person', ondelete='cascade')
    state = fields.Selection(LOG_STATES, string='Result', required=True)
    mail_id = fields.Many2one('mail.mail', string='Email', ondelete='set null')


class PbExplorerScheduleFacade(models.AbstractModel):
    """The drawer's entry points on the Explorer facade. Every one passes the
    Explorer gate first (R1)."""
    _inherit = 'pb.explorer'

    def _pbx_own_view(self, view_id):
        view = self.env['pb.explorer.view'].browse(int(view_id or 0)).exists()
        if not view or view.user_id.id != self.env.uid:
            raise UserError(_("Only the person who saved this view can send it "
                              "regularly. Save it as your own first."))
        return view

    def _pbx_own_schedule(self, schedule_id):
        sched = self.env['pb.explorer.schedule'].with_context(
            active_test=False).browse(int(schedule_id or 0)).exists()
        if not sched or sched.user_id.id != self.env.uid:
            raise UserError(_("That schedule is no longer here."))
        return sched

    @api.model
    def schedule_drawer(self, view_id):
        self._require()
        view = self._pbx_own_view(view_id)
        Sched = self.env['pb.explorer.schedule']
        scheds = Sched.with_context(active_test=False).search(
            [('view_id', '=', view.id), ('user_id', '=', self.env.uid)])
        return {
            'view': view._pbx_payload(),
            'mail_on': Sched._pbx_mail_on(),
            'people': [{'id': u.id, 'name': u.name, 'email': u.email or ''}
                       for u in Sched._pbx_offer()],
            'me': self.env.uid,
            'schedules': [s._pbx_payload() for s in scheds],
            'caps': {'recipients': RECIPIENT_CAP, 'schedules': SCHEDULE_CAP},
        }

    @api.model
    def schedule_save(self, view_id, vals, schedule_id=False):
        """Create or change one of your schedules on one of your views."""
        self._require()
        view = self._pbx_own_view(view_id)
        Sched = self.env['pb.explorer.schedule']
        vals = vals if isinstance(vals, dict) else {}
        cadence = vals.get('cadence')
        if cadence not in dict(CADENCES):
            raise UserError(_("Choose how often to send it."))
        weekday = str(vals.get('weekday') or '0')
        if weekday not in dict(WEEKDAYS):
            weekday = '0'
        try:
            monthday = int(vals.get('monthday') or 1)
        except (TypeError, ValueError):
            monthday = 1
        if not 1 <= monthday <= 28:
            raise UserError(_("Pick a day from 1 to 28, so every month has it."))
        ids = []
        for raw in vals.get('recipient_ids') or []:
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        ids = list(dict.fromkeys(ids))
        if not ids:
            raise UserError(_("Choose at least one person to send it to."))
        if len(ids) > RECIPIENT_CAP:
            raise UserError(_("A view can go to at most %s people.",
                              RECIPIENT_CAP))
        offered = set(Sched._pbx_offer().ids)
        refused = [i for i in ids if i not in offered]
        if refused:
            names = ', '.join(self.env['res.users'].sudo().browse(refused)
                              .exists().mapped('name')) or _("someone")
            raise UserError(_("%s cannot receive it: only people with an email "
                              "address who can open the Explorer can.", names))
        record_vals = {'cadence': cadence, 'weekday': weekday,
                       'monthday': monthday,
                       'recipient_ids': [(6, 0, ids)]}
        if schedule_id:
            sched = self._pbx_own_schedule(schedule_id)
            sched.write(record_vals)
        else:
            count = Sched.with_context(active_test=False).search_count(
                [('user_id', '=', self.env.uid)])
            if count >= SCHEDULE_CAP:
                raise UserError(_("You already send %s views regularly. Delete "
                                  "one you no longer need first.",
                                  SCHEDULE_CAP))
            record_vals.update({'view_id': view.id, 'user_id': self.env.uid,
                                'company_id': self.env.company.id})
            sched = Sched.create(record_vals)
        sched.next_due = sched._next_after(fields.Datetime.now()) \
            if sched.active else False
        return sched._pbx_payload()

    @api.model
    def schedule_pause(self, schedule_id, active):
        self._require()
        sched = self._pbx_own_schedule(schedule_id)
        sched.write({'active': bool(active)})
        sched.next_due = sched._next_after(fields.Datetime.now()) \
            if sched.active else False
        return sched._pbx_payload()

    @api.model
    def schedule_delete(self, schedule_id):
        self._require()
        self._pbx_own_schedule(schedule_id).unlink()
        return True

    @api.model
    def schedule_send_now(self, schedule_id):
        """Send it now, to everyone on it. Does not move the next send (R5)."""
        self._require()
        sched = self._pbx_own_schedule(schedule_id)
        summary = sched._send_one('now')
        sched.sudo().last_run = fields.Datetime.now()
        if summary['email_off']:
            msg = _("Email is not switched on for this company, so nothing "
                    "was sent. The schedule is saved.")
        elif summary['skipped']:
            msg = _("Sent to %(sent)s of %(total)s people. The others were "
                    "skipped — the history says why.", sent=summary['sent'],
                    total=summary['sent'] + summary['skipped'])
        elif summary['sent'] == 1:
            msg = _("Sent to 1 person.")
        else:
            msg = _("Sent to %s people.", summary['sent'])
        return {'ok': True, 'msg': msg, 'summary': summary,
                'schedule': sched._pbx_payload()}
