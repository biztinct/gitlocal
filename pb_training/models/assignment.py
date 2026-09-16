# -*- coding: utf-8 -*-
"""`pb.training.assignment` — a course somebody HAS to do, by a day.

E1 built a course somebody is ON. This is the other half: a course somebody
OWES. The difference is three facts and everything that follows from them —
WHY they were put on it, WHEN it has to be finished, and WHO is told when it
is not.

WHY THE STATE IS STORED AND NOT COMPUTED. Every number on every screen here is
a question about a date: overdue today, due this week, three days late. A
non-stored compute cannot be searched, grouped or used in a filter domain
(R10), and a stored compute over `slide.slide.partner` would recompute the
whole table every time anybody finished a lesson. So `state` is a plain column
written by ONE method — `_refresh()` — which the completion path, the daily job
and the board's own read all call. There is exactly one place in this module
that decides how far an assignment has got.

AND IT CARRIES NO DEFAULT. A stored value that arrives on every create cannot
tell "nobody has said" from "somebody said this" (R143), and `state` is filled
in by `create` itself from the facts, which is the honest version.

WHAT "FINISHED" MEANS is the same sentence the employee's own page uses: every
lesson done, and — if the course has a test at the end — the test passed. It is
read through `_pb_lessons()` / `_pb_lessons_left()` and `_test_state()`, which
are E1's single answers to those questions, so the tile on somebody's phone and
the row on the training board can never disagree.

ONE OPEN ASSIGNMENT PER PERSON PER COURSE. A second one while the first is
still running is refused by name, because two due dates for one course is two
answers to "when do I have to have done this by". A FINISHED one may be
assigned again, which is exactly what a yearly compliance course is.
"""

import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .training_common import (
    ASSIGN_OPEN, ASSIGN_REASON_LABEL, ASSIGN_REASONS, ASSIGN_STATES,
    P_DEFAULT_DUE, TEST_NONE, TEST_PASSED, as_id, days_over, due_words, leg,
    number,
)

_logger = logging.getLogger(__name__)


class PbTrainingAssignment(models.Model):
    _name = 'pb.training.assignment'
    _description = 'Training assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    #: PROBLEM FIRST (R113). A board about who still has to do something opens
    #: on the thing that is late, then the thing that is due, then the rest.
    #: `due_date` ascending puts the oldest overdue row at the top, which is
    #: the one somebody has to act on.
    _order = 'due_date asc, id desc'

    # ------------------------------------------------------------ what it is
    channel_id = fields.Many2one(
        'slide.channel', string='Course', required=True, index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Who has to do it', required=True, index=True,
        ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Their contact', index=True,
        compute='_compute_partner', store=True, readonly=True,
        help='The content engine keys a course membership on a contact, not '
             'on an employee record. This is the contact of their login — '
             'somebody with no login has nowhere for a course to appear.')
    reason = fields.Selection(
        ASSIGN_REASONS, string='Why', required=True, default='adhoc',
        index=True, tracking=True)
    due_date = fields.Date(string='To be finished by', index=True,
                           tracking=True)
    assigned_by_id = fields.Many2one(
        'res.users', string='Put on it by', readonly=True,
        default=lambda self: self.env.user)
    assigned_on = fields.Date(string='Put on it', readonly=True,
                              default=fields.Date.context_today)
    schedule_id = fields.Many2one(
        'pb.training.schedule', string='From the schedule', index=True,
        ondelete='set null', readonly=True)
    rule_id = fields.Many2one(
        'pb.training.rule', string='From the day-one rule', index=True,
        ondelete='set null', readonly=True)

    state = fields.Selection(
        ASSIGN_STATES, string='How far it has got', index=True, readonly=True,
        copy=False, tracking=True)
    completed_on = fields.Date(string='Finished on', readonly=True, copy=False)
    score = fields.Float(string='Test score', digits=(5, 1), readonly=True,
                         copy=False)
    excused_until = fields.Date(
        string='More time agreed until', readonly=True, copy=False,
        help='Set when a request for more time is agreed. Nothing chases an '
             'assignment before this date.')

    counts_for_probation = fields.Boolean(
        string='Their trial period waits for it', tracking=True,
        help='Tick it and the trial period cannot be passed until this course '
             'is finished. It is ticked for you when the reason is the trial '
             'period.')
    status_id = fields.Many2one(
        'pb.training.status', string='Trial-period row', readonly=True,
        copy=False, ondelete='set null')

    delay_ids = fields.One2many('pb.training.delay', 'assignment_id',
                                string='Requests for more time')
    reminder_log = fields.Text(
        string='What has been sent', readonly=True, copy=False, default='{}',
        help='One key per nudge that has gone out, so a second run of the '
             'day sends nothing twice.')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    # ------------------------------------------------------- read-only words
    # THE SENTENCE, WHOLE, AND NOT A FRAME WITH A NUMBER IN IT (R117). The
    # reminder emails read these rather than assembling "%s days left" in the
    # template, where a translator would be handed a frame and a number
    # separately and could not fix a plural they were never given. They are
    # non-stored computes because they are true only of the day they are read.
    course_name = fields.Char(string='Course name', related='channel_id.name',
                              store=False, readonly=True)
    due_words = fields.Char(string='In words', compute='_compute_words')
    progress_words = fields.Char(string='How far in words',
                                 compute='_compute_words')
    reason_words = fields.Char(string='Why in words',
                               compute='_compute_words')

    # =====================================================================
    #  names and computes
    # =====================================================================
    @api.depends('employee_id')
    def _compute_partner(self):
        """AS THE SYSTEM, and narrowly (R56).

        Reading one field of an `hr.employee` reads forty, and about forty of
        them sit behind payroll groups — so a trainer who holds no payroll
        group would get an AccessError naming thirty fields nobody asked for,
        in the middle of putting somebody on a course.
        """
        for rec in self:
            emp = rec.employee_id.sudo()
            rec.partner_id = emp.user_id.partner_id.id if emp.user_id \
                else False

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (
                rec.employee_id.sudo().name or _('Somebody'),
                rec.channel_id.sudo().name or _('a course'))

    @api.depends('due_date', 'reason', 'state')
    def _compute_words(self):
        """The three sentences the emails are made of.

        `_progress` is read per record and that is deliberate: these are only
        ever rendered one record at a time, in an email somebody is about to
        receive, and a number that is right is worth more than a number that
        is fast.
        """
        today = fields.Date.today()
        for rec in self:
            rec.due_words = due_words(rec.due_date, today)
            rec.reason_words = ASSIGN_REASON_LABEL.get(rec.reason, '')
            try:
                facts = rec._progress()
            except Exception:           # noqa: BLE001 — a sentence is not fatal
                rec.progress_words = ''
                continue
            if not facts['total']:
                rec.progress_words = ''
            elif facts['done'] >= facts['total']:
                rec.progress_words = _("Every lesson is done — only the test "
                                       "is left.")
            elif not facts['done']:
                # Neutral wording on purpose: the same sentence is rendered
                # into the person's own email, their manager's and the HR
                # lead's, and "you have not opened it" is wrong in two of the
                # three.
                rec.progress_words = _("Not a single lesson opened yet.")
            elif facts['total'] - facts['done'] == 1:
                rec.progress_words = _("One lesson to go.")
            else:
                rec.progress_words = _(
                    "%s lessons to go.", facts['total'] - facts['done'])

    # =====================================================================
    #  how far it has got — ONE answer, used everywhere
    # =====================================================================
    def _progress(self):
        """(done, total, finished, score) for one assignment.

        The same three questions E1's own tile asks, asked through E1's own
        helpers so there is one answer to each of them in the product.
        """
        self.ensure_one()
        blank = {'done': 0, 'total': 0, 'finished': False, 'score': None,
                 'test': TEST_NONE, 'percent': 0}
        channel = self.channel_id.sudo()
        partner = self.partner_id
        if not channel or not partner:
            return blank
        lessons = channel._pb_lessons()
        done_ids = channel._pb_done_ids(partner)
        done = len([s for s in lessons if s.id in done_ids])
        total = len(lessons)
        row = channel._pb_membership(partner)
        test_slide = channel._pb_test_slide()
        state, score = self.env['pb.my.training']._test_state(
            channel, row, test_slide, total - done)
        return {
            'done': done,
            'total': total,
            # The SAME sentence `pb.my.training._tile` uses: every lesson
            # done, and the test passed when there is one.
            'finished': bool(total) and done >= total
            and state in (TEST_PASSED, TEST_NONE),
            'score': score,
            'test': state,
            'percent': int(round(100.0 * done / total)) if total else 0,
        }

    def _refresh(self):
        """Write `state` (and its companions) from the facts. Idempotent.

        Called by `create`, by the learner's own completion path, by the daily
        job and by every board read, so no screen can ever show a state that
        stopped being true three lessons ago.
        """
        today = fields.Date.today()
        for rec in self:
            try:
                rec._refresh_one(today)
            except Exception:           # noqa: BLE001 — one row, one grave
                _logger.warning('pb_training: assignment %s could not be '
                                'brought up to date', rec.id, exc_info=True)
        return True

    def _refresh_one(self, today=None):
        self.ensure_one()
        today = today or fields.Date.today()
        facts = self._progress()
        vals = {}
        if facts['finished']:
            state = 'done'
            if not self.completed_on:
                vals['completed_on'] = today
            if facts['score'] is not None:
                vals['score'] = float(facts['score'])
        elif self.excused_until and self.excused_until >= today:
            state = 'excused'
        elif self.due_date and self.due_date < today:
            state = 'overdue'
        elif facts['done']:
            state = 'in_progress'
        else:
            state = 'assigned'
        if state != self.state:
            vals['state'] = state
        if vals:
            self.sudo().with_context(
                tracking_disable=True, mail_notrack=True).write(vals)
        # The trial-period row follows the assignment, both ways: finishing
        # the course ticks it, and re-opening the course un-ticks it. A gate
        # that can only ever close is a gate somebody works around.
        if self.status_id:
            leg(self.env, 'training status follow',
                lambda: self._sync_status(state, facts))
        return state

    def _sync_status(self, state, facts):
        """Keep `pb.training.status` saying what the assignment says."""
        self.ensure_one()
        status = self.status_id.sudo()
        if not status:
            return False
        if state == 'done' and status.state != 'done':
            status.action_done(facts.get('score'))
        elif state != 'done' and status.state == 'done':
            status.action_reopen()
        return True

    # =====================================================================
    #  making one
    # =====================================================================
    @api.model
    def _default_due(self, today=None):
        """A fortnight from today, or whatever the company has set.

        THE SERVER'S CLOCK AND NEVER `context_today` (R36/R154): a date that
        decides whether something is late must not change with who is looking
        at it, and the live box's day is not always the agent's.
        """
        days = number(self.env, P_DEFAULT_DUE, 14)
        return (today or fields.Date.today()) + timedelta(days=max(days, 0))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reason') == 'probation' \
                    and 'counts_for_probation' not in vals:
                vals['counts_for_probation'] = True
            if not vals.get('due_date'):
                vals['due_date'] = self._default_due()
            if not vals.get('company_id') and vals.get('employee_id'):
                emp = self.env['hr.employee'].sudo().browse(
                    vals['employee_id'])
                vals['company_id'] = (emp.company_id or self.env.company).id
        records = super().create(vals_list)
        for rec in records:
            rec._guard_one_open()
        for rec in records:
            # Each piece of paperwork inside its OWN savepoint (R131): a
            # try/except is not enough when the thing that failed reached the
            # database, and a failed email must never be able to undo the
            # assignment it was about.
            leg(self.env, 'enrol on the course', rec._enrol)
            leg(self.env, 'trial-period row', rec._ensure_status)
            rec._refresh_one()
            leg(self.env, 'tell the employee and their manager', rec._announce)
        return records

    def _guard_one_open(self):
        """Two due dates for one course is two answers to one question."""
        self.ensure_one()
        clash = self.sudo().search([
            ('id', '!=', self.id),
            ('channel_id', '=', self.channel_id.id),
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ASSIGN_OPEN),
        ], limit=1)
        if clash:
            raise UserError(_(
                "%(who)s is already doing %(course)s — it is due on "
                "%(when)s. Change that date rather than adding a second one, "
                "or wait until they have finished it.",
                who=self.employee_id.sudo().name or '',
                course=self.channel_id.sudo().name or '',
                when=clash.due_date or _('no date')))
        return True

    def _enrol(self):
        """Put them on the course. Idempotent — the engine dedups itself."""
        self.ensure_one()
        if not self.partner_id:
            _logger.info('pb_training: %s has no login, so assignment %s has '
                         'nowhere to appear', self.employee_id.id, self.id)
            return False
        self.channel_id.sudo()._action_add_members(self.partner_id.sudo())
        return True

    def _ensure_status(self):
        """The trial-period row, when the trial period waits for this course.

        DATA, NOT CODE (the handover's rule): `pb_probation` is not touched.
        A track with NO jobs on it is never spread to anybody by
        `ensure_for_employee` (`pb_probation/models/training.py:88-92`), which
        is exactly what makes it safe to hang assignment-made items off one —
        nobody inherits them by having the wrong job title.
        """
        self.ensure_one()
        if not self.counts_for_probation or self.status_id:
            return False
        if 'pb.training.status' not in self.env:
            return False
        track = self._assigned_track()
        if not track:
            return False
        Item = self.env['pb.training.item'].sudo()
        name = self.channel_id.sudo().name or _('Course')
        item = Item.search([('track_id', '=', track.id),
                            ('name', '=', name)], limit=1)
        if not item:
            item = Item.create({'track_id': track.id, 'name': name,
                                'required': True})
        Status = self.env['pb.training.status'].sudo()
        status = Status.search([('employee_id', '=', self.employee_id.id),
                                ('item_id', '=', item.id)], limit=1)
        if not status:
            status = Status.create({
                'employee_id': self.employee_id.id,
                'item_id': item.id,
                'state': 'todo',
                'company_id': self.company_id.id,
            })
        status.write({'assignment_id': self.id})
        self.sudo().write({'status_id': status.id})
        return True

    def _assigned_track(self):
        """The one course-tracker row every assigned course hangs off.

        One per company, named in the words the trial-period screen already
        uses, and with `job_ids` EMPTY so `ensure_for_employee` never spreads
        it to anybody by accident.
        """
        self.ensure_one()
        Track = self.env['pb.training.track'].sudo()
        name = _('Assigned training')
        track = Track.search([('name', '=', name),
                              ('company_id', '=', self.company_id.id)],
                             limit=1)
        if not track:
            track = Track.create({
                'name': name,
                'company_id': self.company_id.id,
                'description': _(
                    'Courses the training team put somebody on. A course in '
                    'here is only asked of the person it was assigned to.'),
            })
        return track

    # =====================================================================
    #  telling people
    # =====================================================================
    def _mail(self, xmlid, email_to):
        """Queue one email. Never raises, never queues a dead letter.

        A message with an empty `email_to` is created, queued and addressed to
        nobody with no error anywhere (R6), so the count would claim somebody
        was told when nobody was. And the address is passed EXPLICITLY — a
        template's own rendered address can reach `mail.mail` empty.
        """
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_training: %s is missing', xmlid)
            return False
        if not email_to:
            return False
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': email_to, 'auto_delete': False})
            return True
        except Exception:               # noqa: BLE001 — a nudge is not fatal
            _logger.warning('pb_training: %s could not be queued for '
                            'assignment %s', xmlid, self.id, exc_info=True)
            return False

    def _their_email(self):
        """Their own address, read as the system (R56/R104)."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        return (emp.work_email or '').strip() or \
            (emp.user_id.email or '').strip()

    def _manager(self):
        self.ensure_one()
        return self.employee_id.sudo().parent_id

    def _manager_email(self):
        self.ensure_one()
        manager = self._manager()
        if not manager:
            return ''
        return (manager.work_email or '').strip() or \
            (manager.user_id.email or '').strip()

    def _announce(self):
        """One email to them, one to their manager, one to-do on their desk."""
        self.ensure_one()
        self._mail('pb_training.mail_template_assignment_start',
                   self._their_email())
        self._mail('pb_training.mail_template_assignment_start_manager',
                   self._manager_email())
        user = self.employee_id.sudo().user_id
        if user and self.due_date:
            try:
                self.activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_todo',
                    summary=_("Training: %s", self.channel_id.sudo().name
                              or ''),
                    note=_("%(course)s has to be finished by %(when)s.",
                           course=self.channel_id.sudo().name or '',
                           when=self.due_date),
                    user_id=user.id, date_deadline=self.due_date)
            except Exception:           # noqa: BLE001 — a to-do is a courtesy
                _logger.warning('pb_training: no to-do could be raised for '
                                'assignment %s', self.id, exc_info=True)
        return True

    # =====================================================================
    #  the reminder ledger
    # =====================================================================
    def _sent(self):
        self.ensure_one()
        try:
            data = json.loads(self.reminder_log or '{}')
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}

    def _mark_sent(self, key, today=None):
        self.ensure_one()
        data = self._sent()
        data[key] = fields.Date.to_string(today or fields.Date.today())
        self.sudo().with_context(tracking_disable=True, mail_notrack=True) \
            .write({'reminder_log': json.dumps(data, sort_keys=True)})
        return True

    def _clear_reminders(self):
        """A new due date starts a new chase, so the old keys go.

        Without this, agreeing five more days would be agreed in silence and
        then chased on the old schedule, because every key the old date earned
        would still be in the ledger.
        """
        self.sudo().with_context(tracking_disable=True, mail_notrack=True) \
            .write({'reminder_log': '{}'})
        return True

    # =====================================================================
    #  what a screen reads
    # =====================================================================
    def _payload(self, today=None):
        """One assignment, as a row on a board or a tile on a phone."""
        self.ensure_one()
        today = today or fields.Date.today()
        facts = self._progress()
        return {
            'id': self.id,
            'channel_id': self.channel_id.id,
            'course': self.channel_id.sudo().name or '',
            'employee_id': self.employee_id.id,
            'who': self.employee_id.sudo().name or '',
            'department': self.employee_id.sudo().department_id.name or '',
            'reason': self.reason,
            'reason_word': ASSIGN_REASON_LABEL.get(self.reason, ''),
            'due': fields.Date.to_string(self.due_date) or '',
            'due_words': due_words(self.due_date, today),
            'days_over': days_over(self.due_date, today),
            'state': self.state or 'assigned',
            'percent': facts['percent'],
            'done': facts['done'],
            'total': facts['total'],
            'test': facts['test'],
            'score': int(round(self.score)) if self.score else None,
            'probation': bool(self.counts_for_probation),
            'completed_on': fields.Date.to_string(self.completed_on) or '',
            'delay': self._open_delay_payload(),
        }

    def _open_delay_payload(self):
        self.ensure_one()
        delay = self.delay_ids.sudo().filtered(
            lambda d: d.state in ('submitted', 'approved'))[:1]
        if not delay:
            return None
        return {'id': delay.id, 'state': delay.state,
                'days': delay.days_asked,
                'kind': delay.reason_kind}

    # =====================================================================
    #  the doors a board opens
    # =====================================================================
    def action_open_record(self):
        """R125 does not apply to an act_window RECORD, but it does to this:
        a dict handed to `doAction` must carry `views`."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Training assignment"),
            'res_model': 'pb.training.assignment',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    # ----------------------------------------------------------------- bulk
    @api.model
    def assign_many(self, channel_id, employee_ids, reason='adhoc',
                    due_date=None, counts_for_probation=None):
        """Put a group of people on one course, and say what really happened.

        FOUR OUTCOMES AND THEY ARE ALL REPORTED: put on, already doing it,
        no login to put it on, and could not be done. A bulk action that
        answers "12 people added" over eight is how a training record ends up
        being wrong in a way nobody notices.
        """
        channel = self.env['slide.channel'].sudo().browse(
            as_id(channel_id)).exists()
        if not channel:
            raise UserError(_("That course is not here any more."))
        ids = [as_id(e) for e in (employee_ids or []) if as_id(e)]
        if not ids:
            raise UserError(_("Pick at least one person."))
        rows = self.env['hr.employee'].sudo().search([
            ('id', 'in', ids),
            ('company_id', 'in', self.env.companies.ids),
        ])
        made, already, no_login, failed = [], [], [], []
        for emp in rows:
            if not emp.user_id or not emp.user_id.partner_id:
                no_login.append(emp.name or '')
                continue
            open_row = self.sudo().search([
                ('channel_id', '=', channel.id),
                ('employee_id', '=', emp.id),
                ('state', 'in', ASSIGN_OPEN)], limit=1)
            if open_row:
                already.append(emp.name or '')
                continue
            vals = {
                'channel_id': channel.id,
                'employee_id': emp.id,
                'reason': reason or 'adhoc',
                'company_id': (emp.company_id or self.env.company).id,
            }
            if due_date:
                vals['due_date'] = due_date
            if counts_for_probation is not None:
                vals['counts_for_probation'] = bool(counts_for_probation)
            try:
                with self.env.cr.savepoint():
                    made.append(self.create(vals).id)
            except Exception:           # noqa: BLE001 — one person, one grave
                _logger.warning('pb_training: %s could not be put on course '
                                '%s', emp.id, channel.id, exc_info=True)
                failed.append(emp.name or '')
        return {
            'made': made,
            'already': already,
            'no_login': no_login,
            'failed': failed,
            'message': self._assign_sentence(channel, made, already, no_login,
                                             failed),
        }

    @api.model
    def _assign_sentence(self, channel, made, already, no_login, failed):
        """The whole sentence, branched — never a frame with a hole (R117)."""
        bits = []
        if len(made) == 1:
            bits.append(_("1 person is now doing %s.", channel.name or ''))
        elif made:
            bits.append(_("%(n)s people are now doing %(course)s.",
                          n=len(made), course=channel.name or ''))
        else:
            bits.append(_("Nobody new was added."))
        if already:
            bits.append(_("%s was already doing it.", ', '.join(already[:5]))
                        if len(already) == 1
                        else _("%s were already doing it.",
                               ', '.join(already[:5])))
        if no_login:
            bits.append(_("%s has no Payobook login yet, so there is nowhere "
                          "for the course to appear.", ', '.join(no_login[:5]))
                        if len(no_login) == 1
                        else _("%s have no Payobook login yet, so there is "
                               "nowhere for the course to appear.",
                               ', '.join(no_login[:5])))
        if failed:
            bits.append(_("%s could not be added — tell the training team.",
                          ', '.join(failed[:5])))
        return ' '.join(bits)
