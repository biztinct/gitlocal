# -*- coding: utf-8 -*-
"""LEARNING L5 — course versions: "Publish a new version".

There was no precedent anywhere (ledger F6). A training manager changes a
course — a new safety rule, a corrected procedure — and presses "Publish a
new version" with one line saying what changed. From that moment:

  * the course's version goes up by one and the line is logged on it;
  * everybody who FINISHED the previous version (a finished assignment for
    the course, or the content engine's own "completed" membership) and is
    not on it right now gets their lesson progress on that course reset and
    a short re-read assignment (reason "Changed course", not counted for the
    trial period, due in `pb_reread_days` days), plus one email saying what
    changed;
  * nothing is deleted — not a lesson, not a certificate (handover §5.3). A
    test already passed stays passed, so the re-read is the lessons only.

The people to reset are worked out ONCE, when the button is pressed, and
stored on the course (`pb_version_queue`). One press handles up to
`pb_training.reread_cap` people (500); the morning job carries on with the
rest (`_rereads`). Working the list out once is what makes the remainder
honest: somebody who finishes the NEW version tomorrow is never mistaken for
somebody who finished the old one.
"""

import json
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .training_common import (
    GROUP_ADMIN, GROUP_MANAGER, P_REREAD_CAP, leg, number,
)

_logger = logging.getLogger(__name__)

NO_ANNOUNCE = 'pb_training_no_announce'


class SlideChannelVersion(models.Model):
    _inherit = 'slide.channel'

    pb_version = fields.Integer(string='Version', default=1, copy=False)
    pb_version_note = fields.Text(string='What changed', copy=False)
    pb_version_published_on = fields.Date(string='This version since',
                                          copy=False)
    pb_reread_days = fields.Integer(
        string='Days to read the changes', default=14,
        help='When a new version is published, the people who finished the '
             'last one have this many days to read it again.')
    pb_version_log = fields.Html(string='Version history', copy=False,
                                 sanitize=True)
    pb_version_pending = fields.Boolean(
        string='Still putting people on the re-read', copy=False)
    pb_version_queue = fields.Text(copy=False)

    # =====================================================================
    #  who finished the last version
    # =====================================================================
    def _pb_finishers(self):
        """Employees who finished this course before the current version,
        and are not on it right now. Read as the system."""
        self.ensure_one()
        Assignment = self.env['pb.training.assignment'].sudo()
        version = self.pb_version or 1
        done = Assignment.search([('channel_id', '=', self.id),
                                  ('state', '=', 'done')])
        emp_ids = set(done.filtered(
            lambda a: (a.course_version or 0) < version).mapped(
                'employee_id').ids)
        # Somebody whose latest finish is already on this version is not a
        # finisher of the old one.
        emp_ids -= set(done.filtered(
            lambda a: (a.course_version or 0) >= version).mapped(
                'employee_id').ids)
        members = self.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', self.id),
            ('member_status', '=', 'completed')])
        if members:
            emps = self.env['hr.employee'].sudo().search([
                ('user_id.partner_id', 'in', members.mapped('partner_id').ids)])
            emp_ids |= set(emps.ids)
        if not emp_ids:
            return self.env['hr.employee'].sudo().browse()
        busy = set(Assignment.search([
            ('channel_id', '=', self.id),
            ('employee_id', 'in', list(emp_ids)),
            ('state', 'in', ('assigned', 'in_progress', 'overdue',
                             'excused'))]).mapped('employee_id').ids)
        emps = self.env['hr.employee'].sudo().browse(
            sorted(emp_ids - busy)).exists()
        return emps.filtered(lambda e: e.user_id and e.active)

    def _pb_queue(self):
        self.ensure_one()
        try:
            data = json.loads(self.pb_version_queue or '[]')
            return [int(x) for x in data if x]
        except (TypeError, ValueError):
            return []

    # =====================================================================
    #  the press
    # =====================================================================
    def _pb_publish_version(self, note, reread_days=None):
        """Bump, stamp, log, work out who finished the old one, and handle
        the first batch. Returns the counts."""
        self.ensure_one()
        note = (note or '').strip()[:2000]
        if not note:
            raise UserError(_(
                "Say in a line what changed. It goes in the email the people "
                "who finished the course get."))
        channel = self.sudo()
        finishers = channel._pb_finishers()
        new = (channel.pb_version or 1) + 1
        today = fields.Date.today()
        entry = Markup('<p><b>%s</b> · %s · %s<br/>%s</p>') % (
            _("Version %s", new), fields.Date.to_string(today),
            self.env.user.name or '', note)
        vals = {
            'pb_version': new,
            'pb_version_note': note,
            'pb_version_published_on': today,
            'pb_version_log': entry + (channel.pb_version_log or Markup('')),
            'pb_version_queue': json.dumps(finishers.ids),
            'pb_version_pending': bool(finishers),
        }
        if reread_days is not None:
            try:
                vals['pb_reread_days'] = max(int(reread_days), 1)
            except (TypeError, ValueError):
                pass
        channel.write(vals)
        channel.message_post(body=_(
            "Version %(n)s published: %(note)s — %(people)s finished the "
            "last version and are asked to read it again.",
            n=new, note=note, people=len(finishers)))
        done = channel._pb_reread_batch()
        return {'version': new, 'people': len(finishers), 'done': done,
                'left': len(channel._pb_queue())}

    def _pb_reread_batch(self, cap=None):
        """Reset progress and put a re-read on the next people in the queue.
        Idempotent per person and version."""
        self.ensure_one()
        channel = self.sudo()
        queue = channel._pb_queue()
        if not queue:
            channel.write({'pb_version_pending': False})
            return 0
        cap = cap if cap is not None else number(self.env, P_REREAD_CAP, 500)
        take, rest = queue[:max(cap, 0)], queue[max(cap, 0):]
        done = 0
        for emp in self.env['hr.employee'].sudo().browse(take).exists():
            if leg(self.env, 'put a re-read on %s' % emp.id,
                   lambda emp=emp: channel._pb_reread_one(emp)):
                done += 1
        channel.write({'pb_version_queue': json.dumps(rest),
                       'pb_version_pending': bool(rest)})
        _logger.info('pb_training: course %s version %s — %s re-read(s) put '
                     'on, %s left for the morning job', channel.id,
                     channel.pb_version, done, len(rest))
        return done

    def _pb_reread_one(self, emp):
        """One person: lesson progress reset, a re-read assignment, one
        email. Nothing is deleted."""
        self.ensure_one()
        version = self.pb_version or 1
        Assignment = self.env['pb.training.assignment'].sudo()
        if Assignment.search_count([
                ('channel_id', '=', self.id), ('employee_id', '=', emp.id),
                ('reason', '=', 'reread'), ('course_version', '=', version)]):
            return False
        if Assignment.search_count([
                ('channel_id', '=', self.id), ('employee_id', '=', emp.id),
                ('state', 'in', ('assigned', 'in_progress', 'overdue',
                                 'excused'))]):
            return False
        partner = emp.user_id.partner_id
        if not partner:
            return False
        self._pb_reset_progress(partner)
        days = max(self.pb_reread_days or 14, 1)
        row = Assignment.with_context(**{NO_ANNOUNCE: True}).create({
            'channel_id': self.id,
            'employee_id': emp.id,
            'reason': 'reread',
            'counts_for_probation': False,
            'due_date': fields.Date.today() + timedelta(days=days),
            'course_version': version,
            'company_id': (emp.company_id or self.env.company).id,
        })
        leg(self.env, 'tell them the course changed',
            lambda: row._pb_mail_changed())
        return True

    def _pb_reset_progress(self, partner):
        """Lesson progress back to zero on this course for one person.

        THE MEMBERSHIP FIRST: the content engine never recomputes a
        membership that says "completed" (`slide.channel.partner.
        _recompute_completion`), so it is set back to "joined" before the
        lessons are marked not done — then the engine's own recompute writes
        the completion. The lesson rows are kept (votes, quiz attempts);
        only `completed` goes back.
        """
        self.ensure_one()
        member = self.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', self.id), ('partner_id', '=', partner.id)],
            limit=1)
        if member and member.member_status == 'completed':
            member.write({'member_status': 'joined'})
        if not member:
            self._action_add_members(partner)
        lessons = self.env['slide.slide.partner'].sudo().search([
            ('channel_id', '=', self.id), ('partner_id', '=', partner.id),
            ('completed', '=', True),
            ('slide_id.slide_category', '!=', 'certification')])
        if lessons:
            lessons.write({'completed': False})
        member = self.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', self.id), ('partner_id', '=', partner.id)],
            limit=1)
        if member:
            member._recompute_completion()
        return True


class PbTrainingAssignmentVersion(models.Model):
    _inherit = 'pb.training.assignment'

    course_version = fields.Integer(
        string='Course version', readonly=True, copy=False,
        help='The version of the course this was finished on (or, for a '
             're-read, the version it asks them to read).')

    def _refresh_one(self, today=None):
        was = self.state
        state = super()._refresh_one(today)
        if state == 'done' and was != 'done' and not self.course_version:
            self.sudo().with_context(tracking_disable=True).write(
                {'course_version': self.channel_id.sudo().pb_version or 1})
        return state

    def _pb_mail_changed(self):
        self.ensure_one()
        template = self.env.ref('pb_training.mail_template_course_changed',
                                raise_if_not_found=False)
        to = self._their_email()
        if not template or not to:
            return False
        template.sudo().with_context(lang='en_US').send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        return True

    def _payload(self, today=None):
        data = super()._payload(today)
        data['course_version'] = self.course_version or 0
        data['version_word'] = ('v%s' % self.course_version) \
            if self.reason == 'reread' and self.course_version else ''
        return data


class PbTrainingAutomationRereads(models.AbstractModel):
    _inherit = 'pb.training.automation'

    @api.model
    def _cron_daily(self):
        counts = super()._cron_daily() or {}
        counts['rereads'] = self._leg(
            'carry on with re-reads after a new course version',
            self._rereads)
        return counts

    @api.model
    def _rereads(self):
        done = 0
        for channel in self.env['slide.channel'].sudo().search(
                [('pb_version_pending', '=', True)]):
            done += channel._pb_reread_batch() or 0
        return done


def require_manager(env):
    user = env.user
    if not (user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN)):
        raise AccessError(_(
            "Only a training manager can publish a new version of a "
            "course."))
