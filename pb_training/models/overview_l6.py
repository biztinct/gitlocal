# -*- coding: utf-8 -*-
"""LEARNING L6 — the Overview finished, the Learning settings, the report
pack, Home › TEAM's training chips and the learning record's sessions.

OVERVIEW (handover §3.2). Every block is live: compliance (the Required
matrix's summary), paths, sessions (this week, seats free, to close),
course requests waiting on a decision, follow-ups waiting on managers,
certificates, the month and the departments. The headline is COMPOSED from
the blocks: the situation sentence, then one sentence per concern that is
not zero — at most three, in a fixed order (late → missing required →
expiring → sessions to close → requests → follow-ups). Nothing waiting is the
calm hero: "All clear. 214 people are in date." `queue` keeps every chip
(quiet board: grey at zero); `waiting` is the rows with a count, in the
same order — what the hero draws in colour.

SETTINGS (§3.3). One facade, `settings_get()` / `settings_set(values)`, over
the `ir.config_parameter` switches that had no screen. Training managers and
the head of training read them; only the HEAD of training (or a system
administrator) writes. Every switch comes back with the sentence that says
what it does, worked out here so the screen and the morning job read the
same numbers.

REPORT PACK (§3.4). The body gains hours, cost against the allowance,
compliance and ratings; the attachment is the full spreadsheet; "Send me a
test" goes to the person who pressed it and to nobody else, and never uses up
the period; the preview is the body as it would go.
"""

import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .numbers_l6 import CACHE_KEY, FULL_KEY
from .training_common import (
    GROUP_ADMIN, GROUP_MANAGER, P_CERT_MANAGER_DAYS, P_CERT_REMINDERS,
    P_DAY1_AUTO, P_ENFORCE_CAP, P_FEEDBACK_ON, P_FOLLOWUP_DAYS, P_FOLLOWUP_ON,
    P_HR_DAYS, P_MANAGER_DAYS, P_PACK, P_PACK_EMAIL, P_PACK_PERIOD,
    P_REMINDERS, P_RENEW_BEFORE, flag, number, text, tr,
)

_logger = logging.getLogger(__name__)

#: One address, plainly: something@somewhere.tld, no spaces.
EMAIL_RE = re.compile(r'^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$')

#: The switches the Learning settings screen reads and writes:
#: key → (kind, parameter, low, high). Everything else is not writable here.
SETTINGS = {
    'report_pack': ('bool', P_PACK, None, None),
    'report_pack_period': ('period', P_PACK_PERIOD, None, None),
    'report_pack_email': ('emails', P_PACK_EMAIL, None, None),
    'reminders': ('bool', P_REMINDERS, None, None),
    'manager_days': ('int', P_MANAGER_DAYS, 0, 60),
    'hr_days': ('int', P_HR_DAYS, 0, 90),
    'cert_reminders': ('bool', P_CERT_REMINDERS, None, None),
    'renew_before': ('int', P_RENEW_BEFORE, 0, 365),
    'enforce_cap': ('int', P_ENFORCE_CAP, 0, 10000),
    'feedback_on': ('bool', P_FEEDBACK_ON, None, None),
    'followup_on': ('bool', P_FOLLOWUP_ON, None, None),
    'followup_days': ('int', P_FOLLOWUP_DAYS, 1, 365),
    'day1': ('bool', P_DAY1_AUTO, None, None),
}
#: The order the Overview draws what waits in — the headline's order.
WAITING_ORDER = ['late', 'paths', 'required', 'certs', 'sessions',
                 'course_requests', 'claims', 'requests', 'followups']
INT_DEFAULTS = {'manager_days': 2, 'hr_days': 5, 'renew_before': 60,
                'enforce_cap': 500, 'followup_days': 30}


def split_emails(raw):
    """Addresses typed with commas, semicolons, spaces or new lines."""
    parts = re.split(r'[,;\s]+', raw or '')
    seen, out = set(), []
    for part in parts:
        part = part.strip()
        if part and part.lower() not in seen:
            seen.add(part.lower())
            out.append(part)
    return out


class PbTrainingOverviewL6(models.AbstractModel):
    _inherit = 'pb.training'

    # =====================================================================
    #  the Overview
    # =====================================================================
    @api.model
    def overview(self):
        data = super().overview()
        if not data.get('allowed'):
            return data
        companies = self.env.companies.ids
        queue = {row['key']: row for row in data.get('queue') or []}
        req = data.get('required') or {}
        data['compliance'] = req if req.get('has_rules') else None
        data['requests'] = {
            'waiting': (queue.get('course_requests') or {}).get('count', 0),
            'claims': (queue.get('claims') or {}).get('count', 0),
            'more_time': (queue.get('requests') or {}).get('count', 0),
        }
        data['followups'] = {
            'waiting': (queue.get('followups') or {}).get('count', 0)}
        data.setdefault('paths', {'has_paths': False})
        data.setdefault('sessions', {'has_sessions': False})
        concerns = self._overview_concerns(data, queue)
        data['concerns'] = [c['key'] for c in concerns]
        # What waits, worst first (the headline's own order).
        data['waiting'] = sorted(
            [row for row in data.get('queue') or [] if row.get('count')],
            key=lambda row: WAITING_ORDER.index(row['key'])
            if row['key'] in WAITING_ORDER else len(WAITING_ORDER))
        data['calm'] = not concerns and not data['waiting']
        data['headline'] = self._overview_compose(data, concerns)
        data['in_date_people'] = self._in_date_people(data)
        return data

    @api.model
    def _overview_concerns(self, data, queue):
        """Every concern that is not zero, in the fixed order."""
        def count(key):
            return (queue.get(key) or {}).get('count', 0)

        late = count('late')
        path_late = (data.get('paths') or {}).get('late', 0)
        missing = (data.get('required') or {}).get('people_missing', 0) \
            if (data.get('required') or {}).get('has_rules') else 0
        expiring = (data.get('certificates') or {}).get('expiring_30', 0)
        to_close = (data.get('sessions') or {}).get('to_close', 0) \
            if (data.get('sessions') or {}).get('has_sessions') else 0
        asks = count('course_requests') + count('claims') + count('requests')
        followups = count('followups')
        out = []
        if late:
            out.append({'key': 'late', 'text': _("1 is past their date.")
                        if late == 1 else _("%(late)s are past their date.",
                                            late=late)})
        if path_late:
            out.append({'key': 'paths',
                        'text': _("1 person is late on a path.")
                        if path_late == 1 else
                        _("%s people are late on a path.", path_late)})
        if missing:
            out.append({'key': 'required',
                        'text': self._required_fragment(req_of(data))})
        if expiring:
            out.append({'key': 'certs',
                        'text': self._cert_fragment(expiring)})
        if to_close:
            out.append({'key': 'sessions',
                        'text': _("1 session is waiting to be closed.")
                        if to_close == 1 else
                        _("%s sessions are waiting to be closed.", to_close)})
        if asks:
            out.append({'key': 'asks',
                        'text': _("1 request is waiting for a decision.")
                        if asks == 1 else
                        _("%s requests are waiting for a decision.", asks)})
        if followups:
            out.append({'key': 'followups',
                        'text': _("1 follow-up is waiting on a manager.")
                        if followups == 1 else
                        _("%s follow-ups are waiting on managers.",
                          followups)})
        return out

    @api.model
    def _in_date_people(self, data):
        """With rules: the people the matrix covers, less those missing
        something. Without: everybody who has been put on a course and is
        not past a date on one."""
        req = data.get('required') or {}
        if req.get('has_rules'):
            return max(req.get('people', 0) - req.get('people_missing', 0), 0)
        rows = self.env['pb.training.assignment'].sudo().search_read(
            [('company_id', 'in', self.env.companies.ids)],
            ['employee_id', 'state'])
        everyone = {r['employee_id'][0] for r in rows if r['employee_id']}
        late = {r['employee_id'][0] for r in rows
                if r['employee_id'] and r['state'] == 'overdue'}
        return len(everyone - late)

    @api.model
    def _overview_compose(self, data, concerns):
        """The situation sentence, then at most three concerns; or the calm
        hero."""
        people = data.get('people', 0)
        courses = data.get('courses', 0)
        finished = (data.get('month') or {}).get('finished', 0)
        if not concerns and not data.get('waiting'):
            n = self._in_date_people(data)
            if not n:
                return self._overview_headline(0, 0, 0, finished)
            return _("All clear. 1 person is in date.") if n == 1 else \
                _("All clear. %s people are in date.", n)
        first = self._overview_headline(people, courses, 0, 0)
        return ' '.join([first] + [c['text'] for c in concerns[:3]])

    # =====================================================================
    #  the Learning settings (Settings › HR › Learning)
    # =====================================================================
    @api.model
    def _can_set(self):
        user = self.env.user
        return user.has_group(GROUP_ADMIN) or user._is_admin()

    @api.model
    def _settings_values(self):
        env = self.env
        values = {}
        for key, (kind, param, _lo, _hi) in SETTINGS.items():
            if kind == 'bool':
                values[key] = bool(flag(env, param))
            elif kind == 'int':
                values[key] = number(env, param, INT_DEFAULTS.get(key, 0))
            elif kind == 'period':
                values[key] = 'weekly' if text(env, param, 'monthly') \
                    .lower().startswith('week') else 'monthly'
            else:
                values[key] = ', '.join(split_emails(text(env, param, '')))
        return values

    @api.model
    def _settings_words(self, v):
        """The sentence under each switch — what it does, with its numbers."""
        env = self.env
        people = split_emails(v['report_pack_email'])
        period = _("weekly") if v['report_pack_period'] == 'weekly' \
            else _("monthly")
        if not v['report_pack']:
            pack = _("The pack is off. Nothing is sent.")
        elif not people:
            pack = _("The pack is on, but nobody is set to receive it yet.")
        elif v['report_pack_period'] == 'weekly':
            pack = _("The %(period)s pack goes to %(who)s the morning after "
                     "each week ends.", period=period, who=', '.join(people))
        else:
            pack = _("The %(period)s pack goes to %(who)s the morning after "
                     "each month ends.", period=period, who=', '.join(people))
        if v['reminders']:
            reminders = _(
                "Reminders go to the person 3, 1 and 0 days before the date, "
                "then every 3 days; the manager after %(m)s days late; the HR "
                "lead after %(h)s.", m=v['manager_days'], h=v['hr_days'])
        else:
            reminders = _("Nobody is reminded. The morning job still brings "
                          "courses up to date and says what it would have "
                          "sent.")
        certs = _(
            "Certificate reminders go 60, 30 and 7 days before and on the "
            "day; the manager hears %s days before.",
            number(env, P_CERT_MANAGER_DAYS, 14)) if v['cert_reminders'] \
            else _("No certificate reminders are sent.")
        feedback = _("Finishing a course asks the person two ratings and one "
                     "line, once.") if v['feedback_on'] else \
            _("Nobody is asked how a course was.")
        followup = _("%s days after somebody finishes a course, their manager "
                     "is asked whether their work has changed.",
                     v['followup_days']) if v['followup_on'] else \
            _("Managers are not asked whether a course made a difference.")
        day1 = _("A new joiner's checklist puts the day-one courses and "
                 "paths on them by itself.") if v['day1'] else \
            _("Day-one courses are not put on by themselves; the joining "
              "checklist says what it would have put on.")
        return {
            'report_pack': pack,
            'reminders': reminders,
            'cert_reminders': certs,
            'renew_before': _("A refresher course is put on the person %s "
                              "days before their certificate runs out.",
                              v['renew_before']),
            'enforce_cap': _("The morning job puts at most %s required "
                             "courses on people in one run.",
                             v['enforce_cap']),
            'feedback_on': feedback,
            'followup_on': followup,
            'day1': day1,
        }

    @api.model
    def settings_get(self):
        """Everything the Learning settings screen draws, in one read."""
        user = self.env.user
        if not (self._can_manage() or self._can_set()):
            return {'allowed': False}
        from .pack import MAIL_CAP
        values = self._settings_values()
        return {
            'allowed': True,
            'can_write': self._can_set(),
            'values': values,
            'words': self._settings_words(values),
            'pack': self.env['pb.training.pack'].status(),
            'mail_cap': MAIL_CAP,
            'my_email': user.email or '',
            'company': self.env.company.name or '',
        }

    @api.model
    def settings_set(self, values=None):
        """Write the switches. The head of training (or a system
        administrator) only; every value is checked before any is written,
        so a bad address leaves everything as it was."""
        if not self._can_set():
            raise AccessError(_(
                "Only the head of training can change the Learning "
                "settings."))
        from .pack import MAIL_CAP
        values = values or {}
        writes = {}
        for key, raw in values.items():
            if key not in SETTINGS:
                continue
            kind, param, low, high = SETTINGS[key]
            if kind == 'bool':
                writes[param] = '1' if raw else '0'
            elif kind == 'int':
                try:
                    n = int(raw)
                except (TypeError, ValueError):
                    raise UserError(_("%s is not a whole number.", raw))
                if n < low or n > high:
                    raise UserError(_(
                        "That number has to be between %(low)s and %(high)s.",
                        low=low, high=high))
                writes[param] = str(n)
            elif kind == 'period':
                writes[param] = 'weekly' if str(raw or '').lower() \
                    .startswith('week') else 'monthly'
            else:
                emails = split_emails(raw)
                bad = [e for e in emails if not EMAIL_RE.match(e)]
                if bad:
                    raise UserError(_("%s is not an email address.", bad[0]))
                if len(emails) > MAIL_CAP:
                    raise UserError(_(
                        "The pack goes to at most %(cap)s addresses; there "
                        "are %(n)s.", cap=MAIL_CAP, n=len(emails)))
                writes[param] = ', '.join(emails)
        icp = self.env['ir.config_parameter'].sudo()
        for param, value in writes.items():
            icp.set_param(param, value)
        data = self.settings_get()
        data['message'] = _("Saved.")
        return data


def req_of(data):
    return data.get('required') or {}


# =========================================================================
#  the report pack
# =========================================================================
class PbTrainingPackL6(models.AbstractModel):
    _inherit = 'pb.training.pack'

    @api.model
    def _can_preview(self):
        user = self.env.user
        return user.has_group(GROUP_MANAGER) or user._is_admin()

    @api.model
    def _numbers_link(self):
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '') or ''
        return '%s/web#action=pb_learning_hub.action_pb_learning_hub' % \
            base.rstrip('/')

    @api.model
    def _pack_lines(self, board):
        """The new lines of the email, as plain English sentences (LD10:
        training mail is English)."""
        lines = []
        hours = board.get('hours') or {}
        if hours.get('total'):
            lines.append(hours.get('headline') or '')
        cost = board.get('cost') or {}
        if cost and not cost.get('empty'):
            lines.append(cost.get('headline') or '')
            budget = cost.get('budget')
            if budget:
                lines.append(_("%(line)s: %(spent)s spent of %(budget)s, "
                               "%(left)s left.", line=budget['line'],
                               spent=budget['spent_words'],
                               budget=budget['budget_words'],
                               left=budget['left_words']))
        comp = board.get('compliance')
        if comp:
            lines.append(comp.get('headline') or '')
        effect = board.get('effect') or {}
        if effect.get('ratings_count'):
            bit = _("Courses were rated %(avg)s out of 5 from %(n)s "
                    "ratings.", avg=effect['ratings_avg'],
                    n=effect['ratings_count'])
            if effect.get('followup_effect_avg') is not None:
                bit = '%s %s' % (bit, _(
                    "Managers say work changed %s out of 5.",
                    effect['followup_effect_avg']))
            lines.append(bit)
        return [line for line in lines if line]

    @api.model
    def _body(self, board, label):
        try:
            return self.env['ir.qweb']._render('pb_training.mail_pack', {
                'board': board, 'label': label,
                'lines': self._pack_lines(board),
                'top': ((board.get('hours') or {}).get('by_person')
                        or [])[:5],
                'link': self._numbers_link(),
            })
        except Exception:                   # noqa: BLE001 — never lose a send
            _logger.warning('pb_training: the pack body could not be rendered',
                            exc_info=True)
            return '<p>%s</p>' % (board.get('headline') or label)

    @api.model
    def _sheet(self, board, label):
        """The full spreadsheet (every sheet), built from the board already
        read — never a second whole-page read."""
        Analytics = self.env['pb.training.analytics']
        key = Analytics._cache_key(board.get('from'), board.get('to'), None)
        me = self.with_context(**{CACHE_KEY: {'key': key, 'payload': board}})
        return super(PbTrainingPackL6, me)._sheet(board, label)

    @api.model
    def _deliver(self, start, end, stamp, label, people):
        # LD10 / LN47: the pack is English end to end.
        return super(PbTrainingPackL6, self.with_context(
            lang='en_US', **{FULL_KEY: True}))._deliver(
            start, end, stamp, label, people)

    @api.model
    def _built(self):
        """(board, label, body) for the period that has just ended."""
        me = self.with_context(lang='en_US', **{FULL_KEY: True})
        start, end, _stamp, label = me._window()
        board = me.env['pb.training.analytics'].get_numbers(
            fields.Date.to_string(start), fields.Date.to_string(end))
        return me, board, label, me._body(board, label)

    @api.model
    def preview(self):
        """The email as it would go, for the preview modal."""
        if not self._can_preview():
            raise AccessError(_("Only a training manager can preview the "
                                "pack."))
        me, board, label, body = self._built()
        return {
            'label': label,
            'subject': _("Training — %s", label),
            'html': body,
            'to': self._recipients(),
            'attachment': _("Training %s.xlsx", label),
        }

    @api.model
    def send_test(self):
        """One copy to the person who pressed it — nobody else, ever — and
        the period is not used up (a test is not the pack)."""
        if not self._can_preview():
            raise AccessError(_("Only a training manager can send a test "
                                "pack."))
        email = (self.env.user.email or '').strip()
        if not email:
            raise UserError(_("Your login has no email address, so a test "
                              "cannot be sent to you. Add one to your "
                              "profile first."))
        me, board, label, body = self._built()
        attachment = me._sheet(board, label)
        values = {
            'subject': _("Training — %s (test)", label),
            'email_to': email,
            'body_html': body,
            'auto_delete': False,
        }
        if attachment:
            values['attachment_ids'] = [(4, attachment.id)]
        self.env['mail.mail'].sudo().create(values)
        return {'ok': True, 'to': email,
                'message': _("A test copy of the %(label)s pack is on its way "
                             "to %(to)s.", label=label, to=email)}


# =========================================================================
#  Home › TEAM: certificates expiring and requests waiting on me
# =========================================================================
class PbMyTrainingTeamL6(models.AbstractModel):
    _inherit = 'pb.my.training'

    #: The records a manager decides in Learning's name.
    DECIDED_HERE = ('pb.training.request', 'pb.training.delay')

    @api.model
    def team(self):
        data = super().team()
        data['expiring_certs'] = {'count': 0, 'names': []}
        data['waiting_on_me'] = {'count': 0}
        try:
            data['waiting_on_me'] = {'count': self._waiting_on_me()}
            if data.get('manages'):
                data['expiring_certs'] = self._team_expiring()
        except Exception:                   # noqa: BLE001 — chips are extra
            _logger.warning('pb_training: the team chips could not be read',
                            exc_info=True)
        return data

    @api.model
    def _team_expiring(self):
        emp = self._my_employee()
        reports = self.env['hr.employee'].sudo().search(
            [('parent_id', '=', emp.id), ('active', '=', True)])
        if not reports or 'pb.employee.document' not in self.env:
            return {'count': 0, 'names': []}
        today = fields.Date.today()
        docs = self.env['pb.employee.document'].sudo().search([
            ('employee_id', 'in', reports.ids),
            ('training_source', '!=', False),
            ('renewed_by_id', '=', False),
            ('expiry_date', '>=', today),
            ('expiry_date', '<=', today + timedelta(days=30)),
        ], order='expiry_date, id')
        names = []
        for doc in docs:
            name = doc.employee_id.name or ''
            if name not in names:
                names.append(name)
        return {'count': len(docs), 'names': names[:5]}

    @api.model
    def _waiting_on_me(self):
        """Course requests and more-time requests whose live step has an
        open seat for me — the approval engine's own answer."""
        Seat = self.env.get('biz.approval.request.seat')
        if Seat is None:
            return 0
        return Seat.sudo().search_count([
            ('status', '=', 'open'),
            ('acting_user_id', '=', self.env.uid),
            ('step_id.status', '=', 'active'),
            ('request_id.state', 'in', ('pending', 'blocked')),
            ('request_id.res_model', 'in', self.DECIDED_HERE),
        ])


# =========================================================================
#  the learning record: sessions, and hours counted once
# =========================================================================
class ReportLearningRecordL6(models.AbstractModel):
    _inherit = 'report.pb_training.report_learning_record'

    @api.model
    def _record(self, emp):
        from .learning_record import _hours_words
        from .session import SESSION_KIND_LABEL
        rec = super()._record(emp)
        atts = self.env['pb.training.attendance'].sudo().search(
            [('employee_id', '=', emp.id),
             ('state', 'in', ('attended', 'no_show'))],
            order='session_start desc, id desc')
        date_words = self.env['pb.employee.document']._pb_date_words
        sessions = []
        attended_hours = 0.0
        for att in atts:
            session = att.session_id
            local = session._local(session.start) if session.start else None
            if att.state == 'attended':
                attended_hours += att.hours or 0.0
            sessions.append({
                'course': session.channel_id.sudo().name or '',
                'kind': tr(self.env, SESSION_KIND_LABEL.get(session.kind, '')),
                'when': date_words(local.date()) if local else '',
                'hours': _hours_words(att.hours)
                if att.state == 'attended' else '',
                'state': att._state_word(),
            })
        rec['sessions'] = sessions
        # Hours counted once: a course finished by attending counts through
        # the attendance; a blended course adds only its lessons' part.
        done = self.env['pb.training.assignment'].sudo().search(
            [('employee_id', '=', emp.id), ('state', '=', 'done')])
        course_hours = 0.0
        for row in done:
            linked = sum(a.hours or 0.0 for a in row.attendance_ids.sudo()
                         if a.state == 'attended')
            course_hours += max((row.hours or 0.0) - linked, 0.0)
        rec['hours_total'] = _hours_words(course_hours + attended_hours)
        n = len([s for s in atts if s.state == 'attended'])
        if n:
            rec['summary'] = '%s · %s' % (
                rec['summary'],
                tr(self.env, '1 session attended') if n == 1
                else tr(self.env, '%s sessions attended', n))
        return rec
