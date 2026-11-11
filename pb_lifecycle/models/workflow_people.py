"""WF2 P4a — everyone can take part, and late work is chased the approvals way.

Who a person step goes to (`_resolve_people`), in four ways:

  * staff     — a staff login; one to-do on the run, as before. When that
                person is away and has named someone to cover in Approvals
                (`biz.approval.delegation.covering`), the step goes to the
                person covering and says so (D2: one cover feature).
  * team      — a team from Approvals › Who approves (`is_pool` role,
                `biz.approval.responsibility.pool_user_ids`): anyone on it can
                take it, first one wins (`take`, row lock).
  * home      — an employee-home login (portal) linked to an active employee in
                the run's company: no to-do (they have no to-do list); the task
                shows on their employee home and is done there (R5).
  * link      — nobody has a login but the system knows their work email: a
                private link by email (R5, D16), one random 32-byte key per
                sending, a resend voids the old one.

Late work (D2, D13) is chased by the approval engine's own hourly job
(`biz.approval.engine._escalate_extra`) and its outbox: one reminder a day
after the due date, one note to the manager a day later — the same numbers
the engine uses for approvals, read from its defaults. Passing up TELLS; it
never moves the task (reassigning is an approval-route feature).

No local is called `user` or `uid` in a method that calls `_()` (ledger G12).
"""
import base64
import logging
import re
import secrets
from datetime import datetime, time, timedelta

import pytz
from markupsafe import Markup, escape
from psycopg2 import errors as pg_errors

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from odoo.addons.biz_approval_workflow.models import definition as approval_definition

from . import workflow_definition as D
from .workflow_models import internal, system

_logger = logging.getLogger(__name__)

#: A link works this long after the due date, and at least this long after
#: it was sent; a step with no due date gets the longer default.
LINK_AFTER_DUE_DAYS = 14
LINK_DEFAULT_DAYS = 30
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
#: Field types a person outside the app cannot answer on a page: a file needs
#: the app's upload, a record lookup would show records to a stranger.
LINK_UNSUPPORTED = ('file', 'lookup')
HOME_UNSUPPORTED = ('lookup',)


def mask_email(email):
    """m***@example.com — enough to recognise, never the whole address."""
    email = str(email or '')
    if '@' not in email:
        return ''
    name, domain = email.split('@', 1)
    return '%s***@%s' % (name[:1], domain)


def late_numbers():
    """The approval engine's own reminder / pass-up days (read, never copied)."""
    late = approval_definition.default_safeguards().get('late') or {}
    return int(late.get('remind_days') or 1), int(late.get('escalate_days') or 2)


class WorkflowStepPeople(models.Model):
    _inherit = 'pb.workflow.step'

    #: The deadline the to-do already had, now also kept on the step.
    due_at = fields.Datetime(index=True)
    reminded_at = fields.Datetime()
    passed_up_at = fields.Datetime()
    #: A team task: everyone who may take it; `assignee_id` empty until taken.
    team_user_ids = fields.Many2many('res.users', 'pb_workflow_step_team_rel', 'step_id', 'user_id')
    #: Whose task this is when someone is covering for them.
    covered_user_id = fields.Many2one('res.users')
    #: The employee a home or link task is for (pass-up and company checks).
    person_employee_id = fields.Many2one('hr.employee', ondelete='set null')
    #: The private link (never shown, never in progress data).
    access_token = fields.Char(copy=False, groups='base.group_system')
    link_email = fields.Char(copy=False, groups='base.group_system')
    link_name = fields.Char(copy=False)
    link_expires_at = fields.Datetime(copy=False)
    link_opened_at = fields.Datetime(copy=False)
    link_done_ip = fields.Char(copy=False, groups='base.group_system')
    _unique_access_token = models.Constraint('unique(access_token)', 'This link key is already in use.')

    def _link_words(self):
        """“the link sent to m***@example.com” (masked)."""
        return _('the link sent to %s', mask_email(self.sudo().link_email))


class WorkflowNotice(models.Model):
    """A notice for someone who reads it on their employee home (R5): the
    in-app inbox is for staff logins only."""
    _name = 'pb.workflow.notice'
    _description = 'Workflow notice'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True)
    run_id = fields.Many2one('pb.workflow.run', ondelete='cascade', index=True)
    subject = fields.Char()
    body = fields.Text()
    read_at = fields.Datetime()


class WorkflowOutboxKinds(models.Model):
    _inherit = 'biz.approval.outbox'

    kind = fields.Selection(selection_add=[
        ('task_reminder', 'A workflow task is waiting'),
        ('task_passed_up', 'A workflow task is late'),
        ('stage_late', 'Past its target time'),
    ], ondelete={'task_reminder': 'cascade', 'task_passed_up': 'cascade', 'stage_late': 'cascade'})


class WorkflowLateJob(models.AbstractModel):
    _inherit = 'biz.approval.engine'

    @api.model
    def _escalate_extra(self, now):
        super()._escalate_extra(now)
        self.env['pb.workflow.studio'].sudo()._chase_late(now)


class WorkflowPeople(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    # ================================================================ who
    def _home_login(self, login, company):
        """An employee-home login linked to an active employee here, or None."""
        login = login[:1] if login else login
        if not login or not login.active or not login.share:
            return None
        employee = self.env['hr.employee'].sudo().search([
            ('user_id', '=', login.id), ('company_id', '=', company.id)], limit=1)
        return (login, employee) if employee else None

    def _team_members(self, role, company, run=None):
        """Staff logins on a team for this company (and the record's area
        first, as the approval engine resolves it)."""
        source = run._source() if run is not None and run.source_model else None
        scopes = source._approval_context().get('scope_keys', ['']) \
            if source is not None and hasattr(source, '_approval_context') else ['']
        row, _via = self.env['biz.approval.responsibility'].sudo().resolve(company, role, scopes)
        rows = row if row else self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', company.id), ('role_id', '=', role.id), ('active', '=', True)])
        members = rows.mapped('pool_user_ids') | rows.mapped('user_id')
        return members.filtered(lambda m: m.active and not m.share and company in m.company_ids)

    def _owner_person(self, run, owner):
        """(login, employee) the owner rule names, either may be empty, for
        the rules that can name someone without a staff login."""
        kind = owner.get('kind')
        Users, Employee = self.env['res.users'].sudo(), self.env['hr.employee'].sudo()
        if kind == 'initiator':
            return run.initiator_id, Employee
        source = run._source() if run.source_model else None
        if kind == 'field':
            uid = self._resolve_owner_on(source, run.company_id, owner, run.initiator_id)
            return Users.browse(uid).exists(), Employee
        if kind == 'subject':
            if source is None or not hasattr(source, '_workflow_subject'):
                raise UserError(_('This kind of record does not say who it is about. Choose someone else.'))
            subject = self._subject(source)
            return (subject.get('user') or Users)[:1], (subject.get('employee') or Employee)[:1]
        if kind == 'manager':
            try:
                uid = self._resolve_owner_on(source, run.company_id, owner, run.initiator_id)
                return Users.browse(uid).exists(), Employee
            except UserError:
                # Nobody with a login: the line manager may still be reached
                # by link, when the record names the employee.
                subject = self._subject(source) if source is not None else {}
                employee = (subject.get('employee') or Employee)[:1]
                if not employee and source is not None:
                    employee = source if source._name == 'hr.employee' else (
                        source.employee_id if 'employee_id' in source._fields else Employee)
                boss = employee.sudo().parent_id if employee else Employee
                if boss and not boss.user_id:
                    return Users, boss
                raise
        return Users, Employee

    def _resolve_people(self, run, owner):
        """Who a person step goes to: a dict with `mode` staff / team / home
        / link (see the module docstring). Raises a plain UserError when
        nobody can do it."""
        owner = owner or {}
        kind = owner.get('kind')
        company = run.company_id
        if kind == 'team':
            role = self.env['biz.approval.role'].sudo().browse(int(owner.get('id') or 0)).exists()
            if not role or not role.is_pool:
                raise UserError(_('Choose a team from Approvals › Who approves.'))
            members = self._team_members(role, company, run)
            if not members:
                raise UserError(_('Nobody is on the team “%s” here yet. Add people to it in Approvals › Who approves.', role.name))
            return {'mode': 'team', 'users': members, 'role': role}
        if kind not in ('initiator', 'field', 'subject', 'manager'):
            return {'mode': 'staff', 'uid': self._resolve_owner(run, owner)}
        login, employee = self._owner_person(run, owner)
        if login and login.active and not login.share:
            return {'mode': 'staff', 'uid': login.id}
        home = self._home_login(login, company)
        if home:
            return {'mode': 'home', 'uid': home[0].id, 'employee': home[1]}
        name = employee.name or login.name or _('The person this is about')
        if login:
            raise UserError(_('%s cannot sign in at the moment, so this cannot be given to them.', name))
        email = (employee.work_email or '').strip() if employee else ''
        if employee and employee.active and (not employee.company_id or employee.company_id == company) \
                and EMAIL.match(email):
            return {'mode': 'link', 'email': email, 'name': employee.name or '', 'employee': employee}
        if kind == 'subject':
            raise UserError(_('%s has no staff login yet, so this task cannot be given to them.', name))
        raise UserError(_('%s has no login and no work email, so this cannot reach them.', name))

    def _covering(self, person, company):
        """Who covers for a staff person today (Approvals' own hand-over)."""
        delegate = self.env['biz.approval.delegation'].sudo().covering(person, company)
        if delegate and delegate.active and not delegate.share and company in delegate.company_ids \
                and delegate != person:
            return delegate
        return None

    # =========================================================== deadlines
    def _task_deadline(self, run, node):
        """The to-do's date: `due` days, working days on the company calendar."""
        days = node.get('due', 2)
        deadline = fields.Date.today() + timedelta(days=days)
        if node.get('due_kind', 'working') == 'working':
            calendar = run.company_id.resource_calendar_id
            if not calendar:
                raise UserError(_('Set the company working calendar before assigning this task.'))
            planned = calendar.plan_days(days + 1, pytz.utc.localize(fields.Datetime.now()), compute_leaves=True)
            if not planned:
                raise UserError(_('The company calendar has no available working days.'))
            deadline = planned.astimezone(pytz.timezone(calendar.tz or 'UTC')).date()
        return deadline

    @staticmethod
    def _due_at(deadline):
        """Late from the morning after the deadline day."""
        return datetime.combine(deadline + timedelta(days=1), time.min)

    def _activity_for(self, run, step, node, person_id, deadline):
        return internal(self.env['mail.activity']).create({
            'res_model_id': self.env['ir.model']._get_id('pb.workflow.run'),
            'res_id': run.id,
            'activity_type_id': node.get('activity_type_id') or self.env.ref('mail.mail_activity_data_todo').id,
            'user_id': person_id, 'summary': node['title'],
            'note': _('Open Workflow Studio → My tasks to complete this step.'),
            'date_deadline': deadline, 'workflow_step_id': step.id})

    # ============================================================ assigning
    def _assign_person_step(self, run, step, node):
        """The people branch of `WorkflowStep._execute` (task, form, confirm)."""
        Users = self.env['res.users'].sudo()
        who = self._resolve_people(run, node.get('owner', {}))
        deadline = self._task_deadline(run, node)
        vals = {'state': 'waiting', 'due_at': self._due_at(deadline), 'reminded_at': False,
                'passed_up_at': False, 'team_user_ids': [(5, 0, 0)], 'covered_user_id': False,
                'person_employee_id': False}
        mode = who['mode']
        if mode == 'staff':
            person = Users.browse(who['uid']).exists()
            if not person or not person.active or person.share or run.company_id not in person.company_ids:
                raise UserError(_('Choose an active person who belongs to this company.'))
            cover = self._covering(person, run.company_id)
            doer = cover or person
            if run.source_model:
                self.with_user(doer)._source(run.source_model, run.source_id)
            activity = step.activity_id or self._activity_for(run, step, node, doer.id, deadline)
            vals.update(assignee_id=doer.id, activity_id=activity.id,
                        covered_user_id=person.id if cover else False)
            internal(step).write(vals)
            if cover:
                run._log(_('Waiting for %(who)s, covering for %(whose)s while they are away.',
                           who=doer.name, whose=person.name), step)
            else:
                run._log(_('Waiting for %s.', person.name), step)
        elif mode == 'team':
            members = who['users']
            if run.source_model:
                readable = self.env['res.users']
                for member in members:
                    try:
                        self.with_user(member)._source(run.source_model, run.source_id)
                        readable |= member
                    except (AccessError, UserError):
                        continue
                members = readable
            if not members:
                raise UserError(_('Nobody on the team “%s” can open this record.', who['role'].name))
            step._cancel_activity()
            vals.update(assignee_id=False, activity_id=False, team_user_ids=[(6, 0, members.ids)])
            internal(step).write(vals)
            run._log(_('Waiting for someone on the team %s.', who['role'].name), step)
            stamp = fields.Datetime.to_string(step.started_at or fields.Datetime.now())
            for member in members:
                self.env['biz.approval.outbox'].sudo()._queue(
                    'task_reminder', member, payload=self._task_payload(run, step, 'new_team'),
                    dedupe='wf-team-new-%s-%s-%s' % (step.id, stamp, member.id))
        elif mode == 'home':
            step._cancel_activity()
            vals.update(assignee_id=who['uid'], activity_id=False, person_employee_id=who['employee'].id)
            internal(step).write(vals)
            run._log(_('Waiting for %s, on their employee home.', Users.browse(who['uid']).name), step)
        else:
            step._cancel_activity()
            vals.update(assignee_id=False, activity_id=False, person_employee_id=who['employee'].id)
            internal(step).write(vals)
            self._send_link(run, step, who['email'], who['name'])

    # ======================================================== the inbox data
    def _task_domain(self):
        return [('state', '=', 'waiting'), ('kind', 'in', list(D.PEOPLE)),
                ('run_id.state', 'not in', ['held', 'cancelled', 'rejected', 'done'])]

    def _my_task_steps(self, companies=None):
        """Steps waiting on me: mine, or my team's and nobody has taken them."""
        companies = companies or self.env.user.company_ids
        Step = self.env['pb.workflow.step'].sudo()
        return Step.search(self._task_domain() + [
            ('company_id', 'in', companies.ids),
            '|', ('assignee_id', '=', self.env.uid),
            '&', ('assignee_id', '=', False), ('team_user_ids', 'in', [self.env.uid])], limit=300)

    def _readable_task(self, step):
        """I may open this task's record (a team task included)."""
        run = step.sudo().run_id
        if run.company_id not in self.env.user.company_ids:
            return False
        if not run.source_model:
            return True
        try:
            self.with_company(run.company_id)._source(run.source_model, run.source_id)
            return True
        except (AccessError, UserError):
            return False

    def _record_name(self, run):
        if not run.source_model:
            return ''
        record = self.env[run.source_model].sudo().browse(run.source_id).exists() \
            if run.source_model in self.env else None
        return record.display_name if record else ''

    def _team_role(self, step):
        owner = (step.sudo().config or {}).get('owner') or {}
        if owner.get('kind') != 'team':
            return self.env['biz.approval.role']
        return self.env['biz.approval.role'].sudo().browse(int(owner.get('id') or 0)).exists()

    def _task_card(self, step, mine=True):
        """One card in the Approvals inbox (and a row in My tasks)."""
        s = step.sudo()
        run = s.run_id
        now = fields.Datetime.now()
        late = bool(s.due_at and s.due_at < now)
        back = (s.answers or {}).get('_sent_back') or None
        role = self._team_role(s)
        untaken = bool(s.team_user_ids) and not s.assignee_id
        if back:
            label = _('Sent back to you') if mine else _('Sent back')
        elif late:
            label = _('Late')
        else:
            label = _('To do')
        if untaken:
            waiting = _('Team: %s · nobody has taken it', role.name or _('a team'))
        elif s.assignee_id:
            waiting = s.assignee_id.name
        elif s.sudo().link_email:
            waiting = _('%(who)s, by %(link)s', who=s.link_name or _('Someone without a login'), link=s._link_words())
        else:
            waiting = ''
        record = self._record_name(run)
        verb = {'input': _('Fill in'), 'confirm': _('Read and confirm')}.get(s.kind, _('To do'))
        card = {
            'id': s.id, 'source': 'workflow', 'kind': 'task', 'task_kind': s.kind, 'verb': verb,
            'open': {'type': 'workflow_task', 'id': s.id} if mine else {'type': 'workflow_progress', 'id': run.id},
            'process': run.name, 'process_key': '', 'area': 'other', 'icon': 'workflow',
            'title': s.name, 'sub': ' · '.join(x for x in (run.name, record) if x),
            'record': record, 'amount': 0.0, 'currency': '', 'count': '', 'workflow': run.name,
            'submitted_by': '' if run.initiator_id.id == SUPERUSER_ID else run.initiator_id.name or '',
            'submitted_at': fields.Datetime.to_string(s.started_at) or '',
            'due_at': fields.Datetime.to_string(s.due_at - timedelta(seconds=1)) if s.due_at else '',
            # The deadline is a day (the to-do's date), not a time.
            'due_day': fields.Date.to_string((s.due_at - timedelta(days=1)).date()) if s.due_at else '',
            'late': late, 'state': 'waiting', 'state_label': label, 'mine': mine,
            'blocked': False, 'block_reason': '', 'return_note': (back or {}).get('note') or '',
            'sent_back': back, 'waiting_for': waiting, 'badges': [], 'route': [],
            'team': {'name': role.name, 'taken': bool(s.assignee_id),
                     'taken_by': s.assignee_id.name or ''} if role else None,
            'can_take': mine and untaken,
            'can_release': mine and bool(s.team_user_ids) and s.assignee_id.id == self.env.uid,
            'covering_for': s.covered_user_id.name or '',
        }
        return card

    def _search_ok(self, card, search):
        if not search:
            return True
        text = ' '.join(str(card.get(k) or '') for k in ('title', 'workflow', 'record', 'waiting_for')).lower()
        return str(search).strip().lower() in text

    def _inbox_tasks(self, scope='me', search=None, team_user_ids=None, wide=False):
        """Cards for the inbox: mine (scope me), or a read of my people's /
        everyone's waiting tasks for those who may view workflow progress."""
        if not self.env.user.has_group('base.group_user'):
            return []
        if scope == 'me':
            steps = self._my_task_steps()
            cards = [self._task_card(s, True) for s in steps if self._readable_task(s)]
        else:
            if not self._can_view_progress():
                return []
            domain = self._task_domain() + [('company_id', 'in', self.env.user.company_ids.ids)]
            if not wide:
                people = list(team_user_ids or [])
                if not people:
                    return []
                domain += ['|', ('assignee_id', 'in', people), ('covered_user_id', 'in', people)]
            steps = self.env['pb.workflow.step'].sudo().search(domain, limit=200)
            mine = set(self._my_task_steps().ids)
            cards = [self._task_card(s, s.id in mine) for s in steps if self._readable_task(s)]
        cards = [c for c in cards if self._search_ok(c, search)]
        cards.sort(key=lambda c: (not c['late'], c['due_at'] or '9999', c['id']))
        return cards

    # ============================================================== teams
    def _team_task(self, task_id):
        """A team task I am on, read for me (membership checked first)."""
        self._staff()
        task = self.env['pb.workflow.step'].sudo().browse(int(task_id or 0)).exists()
        if not task or not task.team_user_ids:
            raise UserError(_('This task no longer exists.'))
        if self.env.user not in task.team_user_ids or task.company_id not in self.env.user.company_ids:
            raise AccessError(_('Only someone on this team can take this task.'))
        if not self.with_company(task.company_id)._readable_task(task):
            raise AccessError(_('You no longer have access to this workflow record.'))
        return task

    @api.model
    def take(self, task_id):
        """Take a team task. The first one wins; the step row is locked."""
        task = self._team_task(task_id)
        try:
            with self.env.cr.savepoint(flush=False):
                self.env.cr.execute('SELECT id FROM pb_workflow_step WHERE id=%s FOR UPDATE NOWAIT', [task.id])
        except pg_errors.LockNotAvailable:
            raise UserError(_('Someone on the team is taking this right now. Look again in a moment.'))
        task.invalidate_recordset()
        if task.state != 'waiting' or task.run_id.state in ('held', 'done', 'cancelled', 'rejected'):
            raise UserError(_('This task is not waiting any more.'))
        if task.assignee_id:
            if task.assignee_id.id == self.env.uid:
                return self.task_detail(task.id)
            raise UserError(_('%s has just taken this.', task.assignee_id.name))
        run = task.run_id
        deadline = (task.due_at - timedelta(days=1)).date() if task.due_at else fields.Date.today()
        activity = self._activity_for(run, task, task.config, self.env.uid, deadline)
        internal(task).write({'assignee_id': self.env.uid, 'activity_id': activity.id})
        run._log(_('%s took this for the team.', self.env.user.name), task)
        return self.task_detail(task.id)

    @api.model
    def release(self, task_id):
        """Put a team task I took back for the team."""
        task = self._team_task(task_id)
        if task.assignee_id.id != self.env.uid or task.state != 'waiting':
            raise UserError(_('Only the person who took this can put it back.'))
        task._cancel_activity()
        internal(task).write({'assignee_id': False, 'activity_id': False})
        task.run_id._log(_('%s put this back for the team.', self.env.user.name), task)
        return {'ok': True}

    def _task(self, task_id):
        # A team task nobody has taken yet may be opened by anyone on the team.
        task = self.env['pb.workflow.step'].sudo().browse(int(task_id or 0)).exists()
        if task and task.team_user_ids and not task.assignee_id and self.env.user in task.team_user_ids:
            task = self._team_task(task.id)
            self._run_state_open(task)
            return task
        return super()._task(task_id)

    def _run_state_open(self, task):
        if task.run_id.state in ('held', 'done', 'cancelled', 'rejected') or task.state != 'waiting':
            raise UserError(_('This task is not waiting for an answer.'))

    @api.model
    def answer(self, task_id, values=None, complete=True):
        task = self.env['pb.workflow.step'].sudo().browse(int(task_id or 0)).exists()
        if task and task.team_user_ids and not task.assignee_id:
            # Answering (or saving) takes it: the same lock and "first wins"
            # as Take it.
            self.take(task.id)
        return super().answer(task_id, values, complete)

    @api.model
    def task_detail(self, task_id):
        result = super().task_detail(task_id)
        task = self.env['pb.workflow.step'].sudo().browse(int(task_id))
        role = self._team_role(task)
        result.update(
            team={'name': role.name, 'taken': bool(task.assignee_id),
                  'mine': task.assignee_id.id == self.env.uid} if role else None,
            covering_for=task.covered_user_id.name or '',
            due=fields.Datetime.to_string(task.due_at - timedelta(seconds=1)) if task.due_at else '',
            late=bool(task.due_at and task.due_at < fields.Datetime.now()))
        return result

    @api.model
    def tasks(self, run_id=None):
        rows = super().tasks(run_id=run_id)
        company = self._company()
        known = {r['id'] for r in rows}
        extra = self.env['pb.workflow.step'].sudo().search(self._task_domain() + [
            ('company_id', '=', company.id), ('assignee_id', '=', False),
            ('team_user_ids', 'in', [self.env.uid])] + ([('run_id', '=', int(run_id))] if run_id else []), limit=200)
        rows += [{'id': s.id, 'name': s.name, 'workflow': s.run_id.name, 'run_id': s.run_id.id,
                  'kind': s.kind, 'due': ''} for s in extra if s.id not in known and self._readable_task(s)]
        by_id = {s.id: s for s in self.env['pb.workflow.step'].sudo().browse([r['id'] for r in rows])}
        for row in rows:
            card = self._task_card(by_id[row['id']], True)
            row.update({k: card[k] for k in ('team', 'can_take', 'can_release', 'covering_for', 'late',
                                             'state_label', 'record', 'sent_back')})
            if card['due_at']:
                row['due'] = card['due_at'][:10]
        return rows

    # ======================================================= employee home
    def _home_tasks(self, person):
        """Waiting tasks of an employee-home login (the controller passes
        the session user explicitly)."""
        Step = self.env['pb.workflow.step'].sudo()
        return Step.search(self._task_domain() + [('assignee_id', '=', person.id),
                                                  ('team_user_ids', '=', False)], order='due_at, id', limit=100)

    def _home_task(self, person, step_id):
        """The step, when it is this person's and still waiting; else None.
        The ownership check comes before any other read."""
        step = self.env['pb.workflow.step'].sudo().browse(int(step_id or 0)).exists()
        if not step or not person or step.assignee_id.id != person.id or step.team_user_ids:
            return None
        if step.kind not in D.PEOPLE:
            return None
        return step

    def _page_fields(self, step, unsupported):
        """The form fields for a QWeb page, with what cannot be done there."""
        form = (step.config or {}).get('form') or {}
        rows = []
        for f in form.get('fields', []) if step.kind == 'input' else []:
            rows.append(dict(f, unsupported=f.get('type') in unsupported))
        return rows

    def _page_values(self, step):
        answers = {k: v for k, v in (step.answers or {}).items() if not str(k).startswith('_')}
        try:
            answers.update(self._prefills(step))
        except (AccessError, UserError):
            pass
        return answers

    def _page_data(self, step, unsupported):
        """Everything a QWeb task page shows: the step's own words, its form
        fields, the record's display name. Nothing else about the record."""
        run = step.run_id
        back = (step.answers or {}).get('_sent_back') or None
        due = (step.due_at - timedelta(days=1)).date() if step.due_at else None
        return {
            'id': step.id, 'name': step.name, 'kind': step.kind, 'workflow': run.name,
            'record': self._record_name(run), 'instructions': (step.config or {}).get('notes', ''),
            'text': (step.config or {}).get('text', '') if step.kind == 'confirm' else '',
            'buttons': D.buttons(step.config) if step.kind in ('task', 'confirm') else [],
            'fields': self._page_fields(step, unsupported), 'values': self._page_values(step),
            'readonly': list(self._prefills_safe(step)), 'sent_back': back,
            'due': format_date(self.env, due) if due else '',
            'late': bool(step.due_at and step.due_at < fields.Datetime.now()),
            'company': run.company_id.name or '', 'company_id': run.company_id.id,
        }

    def _prefills_safe(self, step):
        try:
            return self._prefills(step)
        except (AccessError, UserError):
            return {}

    def _complete_outside(self, step, values, actor_words=None, person=None, ip=None):
        """Finish a task answered on the employee home or by link.

        The same checks the staff path uses (`D.validate_answers` /
        `D.validate_outcome`), run as the system on a locked run. `person`
        is the employee-home login (files must be theirs), None for a link.
        Returns {'ok': bool, 'errors': {...}, 'state': ...}."""
        run = step.run_id
        run._lock()
        step.invalidate_recordset()
        if step.state != 'waiting' or run.state in ('held', 'done', 'cancelled', 'rejected'):
            return {'ok': False, 'state': 'done', 'errors': {}}
        values = values if isinstance(values, dict) else {}
        if step.kind == 'input':
            form = step.config.get('form', {'fields': []})
            prefills = self._prefills_safe(step)
            cleaned, errors = D.validate_answers(form, values, prefills)
            for f in form.get('fields', []):
                if f['type'] == 'lookup' and cleaned.get(f['id']):
                    errors[f['id']] = _('Choose this in the app.')
                if f['type'] == 'file' and cleaned.get(f['id']):
                    for ident in cleaned[f['id']]:
                        att = self.env['ir.attachment'].sudo().browse(ident).exists()
                        if not person or not att or att.res_model != 'pb.workflow.step' or \
                                att.res_id != step.id or att.create_uid.id != person.id:
                            errors[f['id']] = _('Attach the file again.')
        else:
            cleaned, errors = D.validate_outcome(step.config, values)
        if errors:
            return {'ok': False, 'state': 'waiting', 'errors': errors}
        internal(step).write({'answers': cleaned})
        if ip is not None:
            # The key stays on the done step, so the link answers "already
            # done" (single use is the step's state, checked under lock).
            internal(step).write({'link_done_ip': str(ip)[:64]})
        step._finish(cleaned)
        if ip is not None:
            # Recorded as the link, never as the public visitor (R8).
            link = mask_email(step.sudo().link_email)
            run._log({'confirm': _('Confirmed by link sent to %(email)s: “%(what)s”.', email=link,
                                   what=cleaned.get('outcome_label', '')),
                      'input': _('Filled in by link sent to %s.', link)}.get(step.kind) or (
                     _('Answered by link sent to %(email)s: “%(what)s”.', email=link, what=cleaned.get('outcome_label', ''))
                     if len(D.buttons(step.config)) > 1 else _('Done by link sent to %s.', link)), step)
        elif step.kind == 'confirm':
            run._log(_('%(who)s confirmed: “%(what)s”.', who=actor_words, what=cleaned.get('outcome_label', '')), step)
        elif len(D.buttons(step.config)) > 1:
            run._log(_('%(who)s chose “%(what)s”.', who=actor_words, what=cleaned.get('outcome_label', '')), step)
        elif step.kind == 'input':
            run._log(_('%s sent the details.', actor_words), step)
        else:
            run._log(_('%s marked it done.', actor_words), step)
        run._advance()
        return {'ok': True, 'state': 'done', 'errors': {}}

    def _home_upload(self, person, step, field_id, upload):
        """One file from the employee-home page, kept on the step only."""
        field = next((f for f in self._page_fields(step, HOME_UNSUPPORTED) if f['id'] == field_id
                      and f['type'] == 'file'), None)
        if not field:
            raise UserError(_('This file does not belong to this task.'))
        raw = upload.read()
        if not raw or len(raw) > 10 * 1024 * 1024:
            raise UserError(_('Choose a file up to 10 MB.'))
        if self.env.uid != person.id:
            raise AccessError(_('Only the person this task is for can attach a file to it.'))
        # Under sudo, but as that person: the file is recorded as theirs, so
        # the answer check (`create_uid`) accepts it and nobody else's does.
        att = self.env['ir.attachment'].sudo().create({
            'name': (upload.filename or 'file')[:180], 'datas': base64.b64encode(raw),
            'mimetype': (upload.mimetype or 'application/octet-stream')[:100],
            'res_model': 'pb.workflow.step', 'res_id': step.id,
            'company_id': step.company_id.id, 'public': False})
        return att.id

    # ============================================================== notices
    def _notice_for_home(self, run, step, person, text):
        """A notice for an employee-home login: kept for their home page."""
        self.env['pb.workflow.notice'].sudo().create({
            'user_id': person.id, 'company_id': run.company_id.id, 'run_id': run.id,
            'subject': run.name, 'body': text[:4000]})
        internal(step).write({'assignee_id': person.id})
        run._log(_('Told %s on their employee home.', person.name), step)
        step._finish()

    def _notify_step(self, run, step, source, node):
        owner = node.get('owner') or {}
        person = None
        try:
            if owner.get('kind') == 'subject':
                subject = self._subject(source) if source is not None else {}
                person = (subject.get('user') or self.env['res.users'])[:1]
            elif owner.get('kind') in ('initiator', 'field', 'manager'):
                person = self.env['res.users'].sudo().browse(self._resolve_owner(run, owner)).exists()
        except UserError:
            person = None
        home = self._home_login(person, run.company_id) if person else None
        if home:
            return self._notice_for_home(run, step, home[0], self._fill(node.get('text'), run, source))
        return super()._notify_step(run, step, source, node)

    def _home_notices(self, person, unread_only=False):
        domain = [('user_id', '=', person.id)]
        if unread_only:
            domain.append(('read_at', '=', False))
        return self.env['pb.workflow.notice'].sudo().search(domain, limit=30)

    # ================================================================ links
    def _send_link(self, run, step, email, name):
        """Mint a fresh key (the old one stops working) and send the email."""
        token = secrets.token_urlsafe(32)
        now = fields.Datetime.now()
        expires = now + timedelta(days=LINK_DEFAULT_DAYS)
        if step.due_at:
            expires = max(step.due_at + timedelta(days=LINK_AFTER_DUE_DAYS), now + timedelta(days=LINK_AFTER_DUE_DAYS))
        internal(step).write({'access_token': token, 'link_email': email, 'link_name': name,
                              'link_expires_at': expires, 'link_opened_at': False})
        url = '%s/workflow/t/%s' % (step.get_base_url().rstrip('/'), token)
        template = self.env.ref('pb_lifecycle.mail_template_workflow_link')
        company = run.company_id
        sender = company.email_formatted or self.env['ir.mail_server'].sudo()._get_default_from_address() or ''
        due = (step.due_at - timedelta(days=1)).date() if step.due_at else None
        template.sudo().with_context(
            link_url=url, link_company=company.name or '', link_name=name or '',
            link_due=fields.Date.to_string(due) if due else '',
            link_until=fields.Date.to_string(expires.date()),
        ).send_mail(step.id, force_send=False, email_values={
            'email_to': email, 'email_from': sender, 'recipient_ids': [],
            'author_id': company.partner_id.id, 'auto_delete': True,
            'model': False, 'res_id': False})
        run._log(_('Waiting for %(who)s: a link was sent to %(email)s.',
                   who=name or _('them'), email=mask_email(email)), step)

    @api.model
    def resend_link(self, step_id):
        """“Send the link again”: a new key, the old link stops working."""
        self._progress_permission()
        step = self.env['pb.workflow.step'].sudo().browse(int(step_id or 0)).exists()
        if not step:
            raise UserError(_('This step no longer exists.'))
        self._run(step.run_id.id)
        if step.state != 'waiting' or not step.link_email:
            raise UserError(_('This step is not waiting for a link.'))
        run = step.run_id
        run._lock()
        sys_service = run._service()
        sys_service._send_link(run, sys_service.env['pb.workflow.step'].browse(step.id),
                               step.link_email, step.link_name)
        return {'ok': True, 'sent_to': mask_email(step.link_email)}

    def _step_for_token(self, token):
        """(step, status) for a link. The ONLY way in from the public route.

        status: ok / done / expired / missing. Unknown and expired links are
        shown the same page, so the link space cannot be probed."""
        Step = self.env['pb.workflow.step'].sudo()
        if not token or not isinstance(token, str) or len(token) < 32 or len(token) > 80:
            return Step, 'missing'
        step = Step.search([('access_token', '=', token)], limit=1)
        if not step:
            return Step, 'missing'
        if step.state == 'done':
            return step, 'done'
        if step.state != 'waiting' or step.run_id.state in ('held', 'done', 'cancelled', 'rejected') \
                or not step.link_expires_at or step.link_expires_at < fields.Datetime.now():
            return step, 'expired'
        return step, 'ok'

    # ===================================================== reminders, pass-up
    def _task_payload(self, run, step, why):
        """The words of a reminder / pass-up note (posted on the run)."""
        when = (step.due_at - timedelta(days=1)).date() if step.due_at else None
        record = self._record_name(run)
        what = '%s · %s' % (step.name, record) if record else step.name
        if why == 'new_team':
            summary = _('New for your team: %s', step.name)
            body = _('“%(step)s” in %(workflow)s is waiting for someone on your team. Open it in Approvals and press Take it.',
                     step=step.name, workflow=run.name)
        elif why == 'reminder':
            summary = _('Still waiting for you: %s', step.name)
            body = _('“%(what)s” was due on %(when)s. Open it in Approvals to finish it.', what=what, when=when or '')
        elif why == 'passed_up':
            who = step.assignee_id.name or step.link_name or _('nobody on the team yet')
            summary = _('Late: %s', step.name)
            body = _('“%(what)s” was due on %(when)s and is still with %(who)s. Nothing has been moved; '
                     'you are told so you can help.', what=what, when=when or '', who=who)
        else:
            summary, body = step.name, ''
        return {'res_model': 'pb.workflow.run', 'res_id': run.id, 'summary': summary, 'body': body,
                'step_title': step.name}

    def _manager_of(self, person, employee, company):
        """The line manager's staff login for a person, inside the company."""
        Employee = self.env['hr.employee'].sudo()
        if not employee and person:
            employee = Employee.search([('user_id', '=', person.id), ('company_id', '=', company.id)], limit=1)
        boss = employee.parent_id.user_id if employee else self.env['res.users']
        if boss and boss.active and not boss.share and company in boss.company_ids:
            return boss
        return None

    def _workflow_owner(self, run):
        """Who looks after a workflow: whoever published the version it runs."""
        owner = run.version_id.published_by
        if owner and owner.active and not owner.share and run.company_id in owner.company_ids \
                and owner.id != SUPERUSER_ID:
            return owner
        return None

    def _chase_late(self, now):
        """Hourly, from the approval engine's job: remind, then pass up."""
        remind_days, escalate_days = late_numbers()
        Outbox = self.env['biz.approval.outbox'].sudo()
        steps = self.env['pb.workflow.step'].sudo().search(self._task_domain() + [
            ('due_at', '!=', False), ('due_at', '<', now)], limit=500)
        for step in steps:
            try:
                with self.env.cr.savepoint():
                    run = step.run_id
                    stamp = fields.Datetime.to_string(step.started_at or step.create_date)
                    # `due_at` is the moment it became late (the morning after
                    # the due day), as an approval step's `due_at` is.
                    if not step.reminded_at and now >= step.due_at + timedelta(days=remind_days):
                        people = (step.assignee_id or step.team_user_ids).filtered(
                            lambda p: p.active and not p.share)
                        for person in people:
                            Outbox._queue('task_reminder', person, payload=self._task_payload(run, step, 'reminder'),
                                          dedupe='wf-task-reminder-%s-%s-%s' % (step.id, stamp, person.id))
                        internal(step).write({'reminded_at': now})
                        if people:
                            run._log(_('A reminder went out for %s.', step.name), step)
                    if not step.passed_up_at and now >= step.due_at + timedelta(days=escalate_days):
                        boss = None if (step.team_user_ids and not step.assignee_id) else \
                            self._manager_of(step.assignee_id, step.person_employee_id, run.company_id)
                        boss = boss or self._workflow_owner(run)
                        if boss and boss == step.assignee_id:
                            boss = None
                        if boss:
                            Outbox._queue('task_passed_up', boss, payload=self._task_payload(run, step, 'passed_up'),
                                          dedupe='wf-task-passed-up-%s-%s-%s' % (step.id, stamp, boss.id))
                            run._log(_('%(step)s is late; %(who)s was told.', step=step.name, who=boss.name), step)
                        else:
                            run._log(_('%s is late and there is nobody to tell.', step.name), step)
                        internal(step).write({'passed_up_at': now})
            except Exception:  # noqa: BLE001 — one step never stops the rest
                _logger.exception('Workflow step %s: late handling failed', step.id)
        self._chase_late_stages(now)

    def _chase_late_stages(self, now):
        """D13: a record in a user-made stage longer than its target time."""
        Pos = self.env['pb.workflow.record.stage'].sudo()
        Outbox = self.env['biz.approval.outbox'].sudo()
        rows = Pos.search([('stage_id.target_hours', '>', 0), ('late_told_at', '=', False),
                           ('stage_id.active', '=', True)], limit=500)
        for row in rows:
            if row.entered_at + timedelta(hours=row.stage_id.target_hours) > now:
                continue
            try:
                with self.env.cr.savepoint():
                    service = system(self.env, row.company_id)['pb.workflow.studio']
                    if not service._record_position(row.res_model, row.res_id, row.company_id):
                        continue
                    person, run = service._stage_waiting_for(row)
                    if person:
                        payload = {'summary': _('Past its target time: %s', row.stage_id.name),
                                   'body': _('This has been in “%(stage)s” longer than its target of %(hours)s hours.',
                                             stage=row.stage_id.name, hours=row.stage_id.target_hours),
                                   'res_model': 'pb.workflow.run' if run else row.res_model,
                                   'res_id': run.id if run else row.res_id}
                        Outbox._queue('stage_late', person, payload=payload,
                                      dedupe='wf-stage-late-%s-%s' % (row.id, fields.Datetime.to_string(row.entered_at)))
                        if run:
                            service._stage_log(run, _('Past its target time in %(stage)s; %(who)s was told.',
                                                      stage=row.stage_id.name, who=person.name))
                    internal(row).write({'late_told_at': now})
            except Exception:  # noqa: BLE001
                _logger.exception('Workflow stage position %s: late handling failed', row.id)

    def _stage_waiting_for(self, row):
        """(who the record waits for, the run) for a late stage position."""
        Run = self.env['pb.workflow.run'].sudo()
        if row.res_model == 'pb.workflow.run':
            runs = Run.browse(row.res_id).exists()
        else:
            runs = Run.search([('company_id', '=', row.company_id.id), ('source_model', '=', row.res_model),
                               ('source_id', '=', row.res_id), ('state', 'in', ['running', 'waiting', 'failed'])])
        runs = runs or row.run_id
        for run in runs:
            waiting = run.step_ids.filtered(lambda s: s.state == 'waiting' and s.kind in D.PEOPLE and s.assignee_id)
            if waiting:
                return waiting[0].assignee_id, run
        stage = row.stage_id
        if stage.enter == 'person' and stage.enter_owner:
            try:
                source = self.env[row.res_model].sudo().browse(row.res_id).exists() if row.res_model in self.env else None
                if source:
                    initiator = runs[:1].initiator_id if runs else None
                    person = self.env['res.users'].sudo().browse(
                        self._resolve_owner_on(source, row.company_id, stage.enter_owner, initiator)).exists()
                    if person and person.active and not person.share:
                        return person, runs[:1] or None
            except (AccessError, UserError):
                pass
        for run in runs:
            owner = self._workflow_owner(run)
            if owner:
                return owner, run
        return None, runs[:1] or None


class WorkflowRecordStageLate(models.Model):
    _inherit = 'pb.workflow.record.stage'

    #: Told once per entry that it ran past the stage's target time (D13).
    late_told_at = fields.Datetime()
