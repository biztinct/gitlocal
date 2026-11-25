# -*- coding: utf-8 -*-
"""NEWHIRE P3b — the welcome message, its link, the reminders (handover §2.2,
§2.3, §2.5) and the facade of the New joiners buttons (§2.6).

THE LINK (ledger D8) is the product's standard sign-up invitation:
`res.partner.signup_prepare(signup_type='signup')` then
`_get_signup_url_for_action(url='/my/welcome')` — the very calls the
connected-system bridge's `pb_portal_signup_url` compute makes, plus the
landing page. It lands on the real My Payobook pages, where every existing
form, approval, mask, file check and audit applies; the person chooses a
password once. Signed by the stock code over (partner, users, last login
date, signup type): it dies at the first sign-in and after
`auth_signup.signup.validity.hours` (144 h unless a database sets it).

It is built ON DEMAND and handed back once: never written to a field, the
chatter, a log line, a payload or a stored result. The one place it exists
at rest is the outgoing mail itself while it waits in the queue — sent with
no document attached (so it is not on anybody's chatter) and deleted once
sent (`auto_delete`).

Email is sent only where the site sends email: an active outgoing mail
server (the precedent of `pb_explorer._pbx_mail_on` / `pb_voice`). Three of
the five live sites have none on purpose; there HR copies the link.
"""
import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.pb_people_advanced.models.newhire_approval import require_hr

from .welcome_legs import LegFailed

_logger = logging.getLogger(__name__)

TEMPLATE = 'pb_new_hire.mail_template_welcome'
LANDING = '/my/welcome'

#: The reminders' own switch (the base `pb_lifecycle.reminders_enabled` too).
PARAM_REMINDERS = 'pb_new_hire.ask_reminders'
REMIND_EVERY_DAYS = 2
REMIND_UNTIL_DAYS_AFTER = 14
NUDGE_DAYS_BEFORE = 3
#: "Send again" and "Copy the welcome link": once a minute per person.
RATE_SECONDS = 60
#: A ceiling on one run of the job (the lifecycle job's own habit).
RUN_CAP = 300

MANAGE_GROUPS = ('hr.group_hr_manager', 'biz_access.group_access_manager')

_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class HrEmployeeNewHireInvite(models.Model):
    """What the reminders remember about one new person (D10: only where the
    studio is installed)."""
    _inherit = 'hr.employee'

    nh_remind = fields.Boolean(
        string='Remind about joining details', copy=False, groups='hr.group_hr_user',
        help='Set from the Add employee studio: the person is reminded every 2 days '
             'until what they were asked for is done.')
    nh_reminded_on = fields.Date(string='Joining details: last reminder', copy=False,
                                 readonly=True, groups='hr.group_hr_user')
    nh_hr_nudged = fields.Boolean(string='Joining details: HR told', copy=False,
                                  readonly=True, groups='hr.group_hr_user')
    nh_sent_at = fields.Datetime(string='Joining details: last message', copy=False,
                                 readonly=True, groups='hr.group_hr_user')
    nh_copied_at = fields.Datetime(string='Joining details: link last copied', copy=False,
                                   readonly=True, groups='hr.group_hr_user')
    nh_details_ticked = fields.Boolean(string='Joining details: checklist ticked', copy=False,
                                       readonly=True, groups='hr.group_hr_user')


class PbNewHireInvite(models.AbstractModel):
    _name = 'pb.new.hire.invite'
    _description = 'New hire studio: the welcome message and its link'

    # ================================================================ facts
    @api.model
    def _mail_on(self):
        """Does this site send email? An active outgoing mail server."""
        return bool(self.env['ir.mail_server'].sudo().search_count([('active', '=', True)]))

    @api.model
    def _can_manage(self):
        user = self.env.user
        return user._is_superuser() or user.has_group('base.group_system') \
            or any(user.has_group(g) for g in MANAGE_GROUPS)

    @api.model
    def _require_manage(self):
        if not self._can_manage():
            raise AccessError(_("Only an HR manager or someone who manages access can send or "
                                "copy the welcome link."))

    @api.model
    def _employee(self, employee_id):
        """An employee of the user's companies (sudo after the gate)."""
        emp = self.env['hr.employee'].sudo().browse(_int(employee_id)).exists()
        if not emp or (emp.company_id and emp.company_id not in self.env.user.company_ids):
            return self.env['hr.employee'].sudo()
        return emp

    @api.model
    def _first(self, employee):
        return (employee.name or '').split(' ')[0] or employee.name or ''

    @api.model
    def _user(self, employee):
        """The person's own sign-in (employee tier): the employee's login,
        else the joiner field the bridge fills."""
        emp = employee.sudo()
        for user in (emp.user_id, emp.pb_portal_user_id if 'pb_portal_user_id' in emp._fields else None):
            if user and user.share:
                return user.sudo()
        return self.env['res.users'].sudo()

    @api.model
    def _email_login(self, user):
        return bool(user and user.share and '@' in (user.login or ''))

    @api.model
    def _signed_in(self, user):
        """Read the way the stock sign-up code reads it (`_get_login_date`)."""
        return bool(user and user.sudo().login_date)

    @api.model
    def _address(self, employee):
        """Where the message goes: the personal email, else the work email."""
        emp = employee.sudo()
        for value in (emp.private_email, emp.work_email):
            value = (value or '').strip()
            if value and _EMAIL.match(value):
                return value
        return ''

    @api.model
    def _first_day(self, employee):
        emp = employee.sudo()
        day = emp.date_of_joining if 'date_of_joining' in emp._fields else False
        if not day and 'contract_ids' in emp._fields:
            starts = [c.date_start for c in emp.contract_ids if c.date_start]
            day = min(starts) if starts else False
        return day or False

    @api.model
    def _lang_of(self, user=None, employee=None):
        """The language a person reads (P5a): their sign-in's, else the
        employee record's, else this environment's — always an active one."""
        installed = {code for code, _name in self.env['res.lang'].sudo().get_installed()}
        for lang in ((user.sudo().lang if user else None),
                     (employee.sudo().lang if employee is not None and 'lang' in employee._fields else None),
                     self.env.lang):
            if lang and lang in installed:
                return lang
        return 'en_US'

    @api.model
    def _validity_hours(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'auth_signup.signup.validity.hours', 144)
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 144

    @api.model
    def expires_hint(self, employee):
        """The truth about the link's life, from the real validity setting."""
        first = self._first(employee)
        user = self._user(employee)
        if self._signed_in(user):
            return _("It opens the welcome page. %s signs in as usual.", first)
        hours = self._validity_hours()
        if hours % 24 == 0:
            days = hours // 24
            return _("It works for 1 day, or until %s signs in.", first) if days == 1 else \
                _("It works for %(n)s days, or until %(first)s signs in.", n=days, first=first)
        return _("It works for %(n)s hours, or until %(first)s signs in.", n=hours, first=first)

    # ================================================================ the link
    @api.model
    def _link(self, employee):
        """The welcome link, built now and returned once (never stored).

        Never signed in: the standard sign-up invitation landing on
        `/my/welcome` (the person chooses a password once). Signed in before:
        the plain page (they sign in as usual). '' when there is no email
        sign-in to invite."""
        user = self._user(employee)
        if not user:
            return ''
        partner = user.partner_id.sudo()
        if self._signed_in(user):
            return partner.get_base_url().rstrip('/') + LANDING
        if not self._email_login(user):
            return ''
        partner.signup_prepare(signup_type='signup')
        return partner._get_signup_url_for_action(url=LANDING).get(partner.id) or ''

    # ================================================================ sending
    @api.model
    def send(self, employee, kind='welcome'):
        """Queue the welcome message (`kind='welcome'`, everything not done
        yet) or a reminder (only what is still open). Never raises.
        → `{ok, sent, to, message}`."""
        emp = employee.sudo()
        first = self._first(emp)
        out = {'ok': False, 'sent': False, 'to': '', 'message': ''}
        # P5a: the message is written in the person's language — the items'
        # words too (the answers on this screen stay in the sender's)
        lang = self._lang_of(self._user(emp), emp)
        Ask = self.env['pb.new.hire.ask'].sudo().with_context(lang=lang)
        summary = Ask.summary(emp)
        wanted = ('open',) if kind == 'reminder' else ('open', 'waiting')
        items = [i for i in summary['items'] if i['state'] in wanted]
        if not items:
            out.update(ok=True, message=_("Nothing is waiting for %s, so no message was sent.", first))
            return out
        if not self._mail_on():
            out['message'] = _("This site does not send email. Copy the welcome link and send it "
                               "to %s yourself.", first)
            return out
        address = self._address(emp)
        if not address:
            out['message'] = _("There is no email address for %s. Add one on the employee record, "
                               "or copy the welcome link and send it yourself.", first)
            return out
        user = self._user(emp)
        if not user:
            out['message'] = _("%s has no sign-in yet. Make one in Access first.", first)
            return out
        template = self.env.ref(TEMPLATE, raise_if_not_found=False)
        if not template:
            out['message'] = _("The welcome message is missing. Ask an administrator to update "
                               "the Add employee studio.")
            return out
        link = self._link(emp)
        if not link:
            out['message'] = _("%s signs in with the employee number, so there is no welcome link "
                               "to send.", first)
            return out
        needs = dict(Ask._fields['need']._description_selection(Ask.env))
        day = self._first_day(emp)
        hours = self._validity_hours()
        ctx = {
            'pb_nh_kind': kind,
            'pb_nh_first': first,
            'pb_nh_day': fields.Date.to_string(day) if day else '',
            'pb_nh_items': [{'label': i['label'],
                             'need': needs.get(i['need'], '') if i['need'] == 'first_pay' else ''}
                            for i in items],
            'pb_nh_days': hours // 24 if hours % 24 == 0 else 0,
            'pb_nh_hours': hours,
            'pb_nh_signed_in': self._signed_in(user),
            'pb_nh_login': user.login or '',
            'pb_nh_link': link,
            'pb_nh_lang': lang,
        }
        try:
            # no document attached: the message (and the link inside it) is
            # on nobody's chatter, and it is deleted once it has gone
            template.sudo().with_context(**ctx).send_mail(
                emp.id, force_send=False,
                email_values={'email_to': address, 'model': False, 'res_id': False,
                              'auto_delete': True})
        except Exception:                       # noqa: BLE001 — a message, never a crash
            _logger.warning('new hire: the welcome message for employee %s could not be '
                            'queued', emp.id, exc_info=True)
            out['message'] = _("The message could not be prepared. Try again in a moment.")
            return out
        finally:
            link = ctx = None                   # noqa: F841 — not kept a moment longer
        emp.write({'nh_sent_at': fields.Datetime.now()})
        note = _("Reminder about the joining details sent to %s.", address) if kind == 'reminder' \
            else _("Welcome message sent to %s.", address)
        emp.message_post(body=note)
        out.update(ok=True, sent=True, to=address, message=note)
        return out

    # ================================================================ buttons
    @api.model
    def _too_soon(self, when):
        return bool(when and fields.Datetime.now() - when < timedelta(seconds=RATE_SECONDS))

    @api.model
    def copy_link(self, employee_id):
        """"Copy the welcome link" (HR managers, access managers). The note
        on the employee names who copied it; the link itself goes nowhere
        but back to the caller."""
        self._require_manage()
        emp = self._employee(employee_id)
        if not emp:
            return {'ok': False, 'message': _("That person is no longer here.")}
        first = self._first(emp)
        if self._too_soon(emp.nh_copied_at):
            return {'ok': False, 'message': _(
                "The welcome link of %s was copied less than a minute ago. Wait a minute, then "
                "copy it again.", first)}
        if not self._user(emp):
            return {'ok': False, 'message': _("%s has no sign-in yet. Make one in Access first.", first)}
        link = self._link(emp)
        if not link:
            return {'ok': False, 'message': _(
                "%s signs in with the employee number, so there is no welcome link. Give them the "
                "employee number and the first password from Access.", first)}
        emp.write({'nh_copied_at': fields.Datetime.now()})
        emp.message_post(body=_("%s copied the welcome link.", self.env.user.name or ''))
        return {'ok': True, 'link': link, 'expires_hint': self.expires_hint(emp),
                'message': _("Link copied. %s", self.expires_hint(emp))}

    @api.model
    def send_again(self, employee_id):
        """"Send again": a reminder now, with what is still open."""
        self._require_manage()
        emp = self._employee(employee_id)
        if not emp:
            return {'ok': False, 'message': _("That person is no longer here.")}
        if self._too_soon(emp.nh_sent_at):
            return {'ok': False, 'message': _(
                "A message went to %s less than a minute ago. Wait a minute, then send it again.",
                self._first(emp))}
        return self.send(emp, 'reminder')

    @api.model
    def _board(self, employee_ids):
        """`{employee id: asked}` for the New joiners board — one batched
        read of every person on the page. `asked` is False for a person who
        was asked nothing."""
        emps = self.env['hr.employee'].sudo().browse([i for i in employee_ids if i]).exists()
        if not emps:
            return {}
        summaries = self.env['pb.new.hire.ask'].sudo().summaries(emps)
        manage = self._can_manage()
        mail_on = self._mail_on()
        today = fields.Date.context_today(self)
        out = {}
        for emp in emps:
            s = summaries.get(emp.id)
            if not s or not s['total']:
                out[emp.id] = False
                continue
            user = self._user(emp)
            day = self._first_day(emp)
            link_ok = bool(user) and (self._signed_in(user) or self._email_login(user))
            act = bool(day and (day - today).days <= 7 and any(
                i['need'] == 'first_pay' and i['state'] == 'open' for i in s['items']))
            out[emp.id] = dict(
                s, items=[{k: i[k] for k in ('key', 'label', 'state', 'need')} for i in s['items']],
                first=self._first(emp), has_login=link_ok,
                can_copy=manage and link_ok,
                can_send=manage and link_ok and mail_on and bool(self._address(emp)) and bool(s['open']),
                mail_on=mail_on, act=act,
                chip=_("%(done)s of %(total)s details", done=s['done'], total=s['total']))
        return out

    @api.model
    def card(self, employee_id):
        """The studio's done card for an added person: what they were asked,
        and whether the link can be copied here."""
        require_hr(self.env)
        emp = self._employee(employee_id)
        if not emp:
            return {'asked': False}
        return {'asked': self._board([emp.id]).get(emp.id) or False,
                'expires_hint': self.expires_hint(emp)}

    # ================================================================ reminders
    @api.model
    def _reminders_on(self):
        Param = self.env['ir.config_parameter'].sudo()
        mine = str(Param.get_param(PARAM_REMINDERS, '1')).strip() not in ('0', 'false', 'False', '')
        return mine and self.env['pb.journey.case']._reminders_enabled()

    @api.model
    def _hr_contact(self, employee, rows):
        """Who is told: the person who proposed the hire, else the joining
        checklist's HR owner."""
        maker = rows.mapped('proposal_id.user_id')[:1]
        if maker and maker.active:
            return maker
        case = self.env['pb.journey.case'].sudo().search(
            [('employee_id', '=', employee.id), ('case_type', '=', 'onboarding'),
             ('state', 'not in', ('cancelled',))], limit=1)
        if case:
            try:
                user = case._resolve_assignee('hr', employee)
            except Exception:                   # noqa: BLE001 — a name, never a crash
                user = None
            if user:
                return user[:1]
        return self.env['res.users']

    @api.model
    def _nh_remind_asks(self, today=None):
        """The reminders piece of the lifecycle job (handover §2.5)."""
        if not self._reminders_on():
            return {'off': True}
        today = today or fields.Date.today()
        Ask = self.env['pb.new.hire.ask'].sudo()
        rows = Ask.search([('state', 'in', ('open', 'waiting')),
                           ('employee_id.active', '=', True)], limit=RUN_CAP * 10)
        employees = rows.mapped('employee_id').filtered('nh_remind')[:RUN_CAP]
        if not employees:
            return {'reminded': 0, 'nudged': 0}
        summaries = Ask.summaries(employees)
        mail_on = self._mail_on()
        reminded = nudged = 0
        for emp in employees:
            s = summaries.get(emp.id) or {}
            day = self._first_day(emp)
            if not day or (today - day).days >= REMIND_UNTIL_DAYS_AFTER:
                continue
            try:
                with self.env.cr.savepoint():
                    last = emp.nh_reminded_on
                    if mail_on and s.get('open') and (not last or (today - last).days >= REMIND_EVERY_DAYS):
                        if self.send(emp, 'reminder').get('sent'):
                            emp.write({'nh_reminded_on': today})
                            reminded += 1
                    missing = [i for i in s.get('items') or []
                               if i['need'] == 'first_pay' and i['state'] != 'done']
                    if missing and not emp.nh_hr_nudged and today >= day - timedelta(days=NUDGE_DAYS_BEFORE):
                        if self._nudge(emp, day, len(missing),
                                       rows.filtered(lambda r: r.employee_id == emp)):
                            nudged += 1
            except Exception:                   # noqa: BLE001 — one person, one grave
                _logger.exception('new hire: the reminder for employee %s failed', emp.id)
        _logger.info('pb_new_hire: %s joining-details reminder(s), %s note(s) to HR',
                     reminded, nudged)
        return {'reminded': reminded, 'nudged': nudged}

    @api.model
    def _nudge(self, employee, day, n, rows):
        user = self._hr_contact(employee, rows)
        if not user:
            return False
        # P5a: the note is written in the language of the HR person it is for
        return self.with_context(lang=self._lang_of(user))._nudge_write(employee, day, n, user)

    @api.model
    def _nudge_write(self, employee, day, n, user):
        from odoo.tools.misc import format_date
        when = format_date(self.env, day, date_format='EEE d MMM')
        sentence = _("%(name)s starts on %(day)s and 1 thing needed for the first pay is still "
                     "missing.", name=employee.name or '', day=when) if n == 1 \
            else _("%(name)s starts on %(day)s and %(n)s things needed for the first pay are still "
                   "missing.", name=employee.name or '', day=when, n=n)
        employee.activity_schedule(
            'mail.mail_activity_data_todo',
            date_deadline=max(fields.Date.today(), day - timedelta(days=NUDGE_DAYS_BEFORE)),
            summary=_("Joining details missing"), note=sentence, user_id=user.id)
        employee.write({'nh_hr_nudged': True})
        return True


class PbNewHireLegsInvite(models.AbstractModel):
    """The last welcome leg: the welcome message (it needs the sign-in and
    the asks; it does not need the checklist)."""
    _inherit = 'pb.new.hire.legs'

    @api.model
    def _failed(self, employee, key, reason):
        if key != 'invite':
            return super()._failed(employee, key, reason)
        # the reason is already the whole sentence (what, why, what next)
        try:
            employee.message_post(body=reason)
        except Exception:                       # noqa: BLE001 — the note is a courtesy
            _logger.warning('new hire: could not note the welcome leg on %s', employee.id,
                            exc_info=True)
        return {'key': key, 'ok': False, 'message': reason}

    @api.model
    def _leg_invite(self, employee, values, state):
        if 'nh_remind' in values and 'nh_remind' in employee._fields:
            employee.write({'nh_remind': bool(values.get('nh_remind'))})
        if values.get('pb_nh_asks') is None:
            return False                        # not a P3 payload
        first = self._first(employee)
        if not self.env['pb.new.hire.ask'].sudo().search_count([('employee_id', '=', employee.id)]):
            return _("nothing to ask %s for, so no welcome message", first)
        Invite = self.env['pb.new.hire.invite']
        mode = values.get('login_mode') or 'none'
        if mode == 'code':
            raise LegFailed(_("No welcome link: %s has no email sign-in. They can still finish these "
                              "after signing in with the employee number.", first))
        if mode != 'email' or not Invite._user(employee):
            raise LegFailed(_("No welcome link: %s has no sign-in yet. Once one is made in Access, "
                              "these are waiting for them on My Payobook.", first))
        answer = Invite.send(employee, 'welcome')
        if not answer.get('sent'):
            raise LegFailed(_("No welcome message: %s", answer.get('message') or ''))
        employee.write({'nh_reminded_on': fields.Date.today()})
        return _("welcome message to %s", answer['to'])


class PbJourneyCaseNewHireReminders(models.Model):
    """The reminders ride on the ONE lifecycle job (no new scheduled job:
    the template-job list would need it)."""
    _inherit = 'pb.journey.case'

    @api.model
    def _cron_lifecycle_reminders(self):
        counts = super()._cron_lifecycle_reminders()
        if not isinstance(counts, dict):
            counts = {'base': counts}
        try:
            counts['new_hire_asks'] = self.env['pb.new.hire.invite']._nh_remind_asks()
        except Exception:                       # noqa: BLE001 — one piece, one grave
            _logger.exception('pb_new_hire: the joining-details reminders failed')
        return counts
