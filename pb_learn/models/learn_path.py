# -*- coding: utf-8 -*-
"""LEARN v3 — role paths, the month-end card, milestone notes, team readiness.

Four small answers the Learn home, the helper and the Team lens need. None of
them stores content: the role paths are a table in this file, the month-end
date is read from the pay calendar when that module is installed, milestones
are counts over records the company already has, and readiness is the
progress rows `learn.progress` already writes.

ROLE PATHS
----------
Thirty-nine stations is the whole product. An approver needs seven of them. The
role a learner picks decides which stations are REQUIRED for them — the map
dims the rest and `next_best` suggests only from the path — and nothing else:
every station stays open to everybody. A learner who never picks gets a role
guessed from their groups, and the guess is labelled as a guess.

PRIVACY
-------
The Team lens shows progress only — which stations a person has finished and
when they last opened Learn. Never the questions anybody asked (those are
`learn.question`, own-rows, and not read here). The readiness method runs
with elevated rights on purpose, because `learn.progress` is own-rows; it
re-asks the manager gate itself before reading anything.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# Which stations are REQUIRED for each role. Reading order is the map's own
# (line_order), so these are sets, not sequences.
#
# LEARN REFRESH step 5 — rebuilt over the final station set (39 stations).
# Each path is what that person does in a normal month, not everything they
# may open. Notes on the choices:
#   officer  — the whole month (run → deliver → adjust / settle) plus the
#              setup screens an officer is the first to be asked about.
#   approver — what they read before saying yes: the run, a payslip, the
#              report, and the two other things they are asked to sign.
#   hr       — people from hiring to leaving, their records and time. NOT
#              `access`: handing out access is an administrator's job
#              (biz_access grants need the access-manager group), and an HR
#              manager does not hold it by default.
#   manager  — the team's week in Workforce plus the people decisions a
#              line manager is part of. Guessed from the attendance groups
#              the Workforce tabs are gated on (pb_mission.js).
#   owner    — the numbers, the plan, the filings and who signs what.
ROLE_PATHS = {
    'officer': ('dashboard', 'approvals', 'runpayroll', 'payruns', 'payslips',
                'import', 'afterrun', 'adjust', 'fullfinal', 'records',
                'schemes', 'treatment', 'statutory', 'formula', 'blueprint',
                'mapping'),
    'approver': ('dashboard', 'approvals', 'payruns', 'payslips', 'insights',
                 'reports', 'payreview'),
    'hr': ('dashboard', 'employees', 'records', 'hiring', 'joiners',
           'probation', 'exits', 'contractends', 'wftime', 'paybands'),
    'manager': ('approvals', 'wftoday', 'wftime', 'wfclose', 'hiring',
                'probation', 'growth'),
    'owner': ('dashboard', 'approvals', 'insights', 'explorer', 'reports',
              'decisionroom', 'paybands', 'govreports', 'matrix', 'access'),
}
ROLES = tuple(ROLE_PATHS)

# The groups a role is guessed from, tried in this order. The first role
# with a group the user holds wins; nothing held means "officer", the role
# the lessons were written for. `manager` comes after hr so an HR user who
# also holds attendance rights stays hr.
ROLE_GUESS = (
    ('officer', ('pb_hr_payroll_base.group_payroll_base_officer',
                 'pb_hr_payroll_base.group_payroll_base_manager',
                 'pb_hr_payroll_base.group_payroll_super_admin')),
    ('approver', ('pb_hr_payroll_base.group_payroll_final_approver',)),
    ('hr', ('hr.group_hr_manager', 'hr.group_hr_user')),
    ('manager', ('hr_attendance.group_hr_attendance_manager',
                 'hr_attendance.group_hr_attendance_officer')),
    ('owner', ('base.group_system',)),
)

# Who may read the Team lens: payroll managers and administrators.
TEAM_GROUPS = ('pb_hr_payroll_base.group_payroll_base_manager',
               'pb_hr_payroll_base.group_payroll_super_admin',
               'base.group_system')

# Who is counted as "the team": anyone whose role guess comes from a group,
# plus anyone who picked a role themselves.
TEAM_MEMBER_GROUPS = tuple(g for role, gs in ROLE_GUESS if role != 'owner' for g in gs)

# Milestones, in the order a company reaches them. Each is (key, station the
# note points at). Counts are company-wide: "your company's first pay run".
MILESTONES = (
    ('m_employee', 'employees'),
    ('m_run', 'payslips'),
    ('m_submitted', 'approvals'),
    ('m_done', 'govreports'),
)

# How many days ahead the month-end card starts to show.
CALENDAR_WINDOW_DAYS = 7


class ResUsers(models.Model):
    _inherit = 'res.users'

    learn_role = fields.Selection(
        [('officer', 'Payroll officer'), ('approver', 'Approver'),
         ('hr', 'HR admin'), ('manager', 'People manager'), ('owner', 'Owner')],
        string='Learning path', copy=False,
        help="The learning path this person picked in Learn. Empty means "
             "the path is guessed from their access groups.")


class LearnPath(models.AbstractModel):
    _name = 'learn.path'
    _description = 'Payobook Learn — role paths, month-end, milestones, team'

    # ------------------------------------------------------------- roles
    @api.model
    def _has_any(self, user, xmlids):
        for xmlid in xmlids:
            if self.env.ref(xmlid, raise_if_not_found=False) \
                    and user.has_group(xmlid):
                return True
        return False

    @api.model
    def guess_role(self, user=None):
        user = user or self.env.user
        for role, groups in ROLE_GUESS:
            if self._has_any(user, groups):
                return role
        return 'officer'

    @api.model
    def role_of(self, user=None):
        """(role, chosen) — the picked role, or the guess with chosen False."""
        user = user or self.env.user
        if user.sudo().learn_role in ROLES:
            return user.sudo().learn_role, True
        return self.guess_role(user), False

    @api.model
    def set_role(self, role):
        """The learner's own pick. Writes only the calling user's row."""
        if role not in ROLES:
            raise AccessError(self.env._("That is not a learning path."))
        self.env.user.sudo().write({'learn_role': role})
        return self.bootstrap_extra()

    @api.model
    def required_for(self, role):
        return set(ROLE_PATHS.get(role) or ())

    # --------------------------------------------------------- month-end
    @api.model
    def month_end(self):
        """The next "changes close" date from the pay calendar, or {}.

        Only when the pay calendar module is installed and has an upcoming
        month for this company closing within the window. Nothing is guessed:
        a company with no pay calendar gets no card.
        """
        if 'pb.payroll.calendar' not in self.env:
            return {}
        today = fields.Date.context_today(self)
        try:
            row = self.env['pb.payroll.calendar'].sudo().search([
                ('company_id', 'in', [self.env.company.id, False]),
                ('state', '=', 'upcoming'),
                ('cutoff_date', '>=', today),
                ('cutoff_date', '<=', today + timedelta(days=CALENDAR_WINDOW_DAYS)),
            ], order='cutoff_date asc', limit=1)
        except Exception:                                          # noqa: BLE001
            _logger.info("pb_learn: cannot read the pay calendar", exc_info=True)
            return {}
        if not row:
            return {}
        return {
            'cutoff': row.cutoff_date.isoformat(),
            'days': (row.cutoff_date - today).days,
            'month': row.month.isoformat() if row.month else '',
        }

    # --------------------------------------------------------- the bundle
    @api.model
    def bootstrap_extra(self):
        """What the map and the helper need beyond learn.runtime.bootstrap."""
        role, chosen = self.role_of()
        return {
            'role': role,
            'role_chosen': chosen,
            'roles': {k: list(v) for k, v in ROLE_PATHS.items()},
            'month_end': self.month_end(),
        }

    # -------------------------------------------------------- milestones
    @api.model
    def _milestone_reached(self):
        """{key: bool} — company-wide, counted with elevated rights.

        Only asked for people who work on payroll (see `milestones`), so the
        counts never tell anyone something their role hides from them.
        """
        company = self.env.company
        out = {}
        Emp = self.env['hr.employee'].sudo()
        out['m_employee'] = bool(Emp.search_count(
            [('company_id', '=', company.id)], limit=1))
        if 'hr.payslip.run' in self.env:
            Run = self.env['hr.payslip.run'].sudo()
            dom = [('company_id', '=', company.id)] \
                if 'company_id' in Run._fields else []
            out['m_run'] = bool(Run.search_count(dom, limit=1))
            out['m_submitted'] = bool(Run.search_count(
                dom + [('state', 'not in', ('draft', 'cancel'))], limit=1))
            out['m_done'] = bool(Run.search_count(
                dom + [('state', 'in', ('done', 'paid', 'close'))], limit=1))
        return out

    @api.model
    def _seen_milestones(self):
        Event = self.env['learn.event'].sudo()
        rows = Event.search([('user_id', '=', self.env.uid),
                             ('company_id', '=', self.env.company.id),
                             ('kind', 'in', ('milestone_seen', 'milestone_base'))])
        return rows

    @api.model
    def milestones(self):
        """Milestones reached that this person has not been told about.

        THE FIRST CALL IS A BASELINE, not a burst: everything already reached
        when somebody first meets this feature is marked seen silently, so a
        company with two years of pay runs is never told "you ran your first
        pay run". From then on each first is told once, to each person, and
        never again.
        """
        if not self._has_any(self.env.user, TEAM_MEMBER_GROUPS[:3]):
            return []
        if self.env['learn.live'].world_is_demo():
            return []
        reached = self._milestone_reached()
        seen_rows = self._seen_milestones()
        Event = self.env['learn.event']
        if not seen_rows.filtered(lambda r: r.kind == 'milestone_base'):
            Event.log('milestone_base', detail=','.join(
                k for k, v in reached.items() if v) or '-')
            for key, ok in reached.items():
                if ok:
                    Event.log('milestone_seen', detail=key)
            return []
        seen = set(seen_rows.mapped('detail'))
        return [{'key': key, 'station': station}
                for key, station in MILESTONES
                if reached.get(key) and key not in seen]

    @api.model
    def ack_milestone(self, key):
        if key in dict(MILESTONES):
            self.env['learn.event'].log('milestone_seen', detail=key)
        return True

    # -------------------------------------------------------------- team
    @api.model
    def can_see_team(self):
        return self._has_any(self.env.user, TEAM_GROUPS)

    @api.model
    def _check_team(self):
        if not self.can_see_team():
            raise AccessError(self.env._(
                "Only a payroll manager or an administrator can see the team."))

    @api.model
    def readiness(self):
        """One row per team member: role, required stations done, last seen.

        Progress only. The questions people asked are never read here.
        """
        self._check_team()
        company = self.env.company
        Users = self.env['res.users'].sudo()
        users = Users.search([
            ('share', '=', False), ('active', '=', True),
            ('company_ids', 'in', company.id),
        ])
        members = users.filtered(
            lambda u: u.learn_role or self._has_any(u, TEAM_MEMBER_GROUPS))
        Progress = self.env['learn.progress'].sudo()
        Event = self.env['learn.event'].sudo()
        stations = {s['key']: s for s in self.env['learn.content'].stations()}
        rows = []
        for user in members.sorted('name'):
            role, chosen = self.role_of(user)
            required = [k for k in ROLE_PATHS[role] if k in stations]
            done = set(Progress.search([
                ('user_id', '=', user.id), ('company_id', '=', company.id),
                ('state', '=', 'done'), ('key', 'in', required),
            ]).mapped('key'))
            last = Event.search([('user_id', '=', user.id),
                                 ('company_id', '=', company.id)],
                                order='occurred_at desc', limit=1)
            todo = [k for k in required if k not in done]
            rows.append({
                'id': user.id,
                'name': user.name,
                'role': role,
                'role_chosen': chosen,
                'required': len(required),
                'done': len(done),
                'todo': [{'key': k, 'name': stations[k]['name']} for k in todo[:3]],
                'minutes_left': sum(int(stations[k].get('duration_min') or 0)
                                    for k in todo),
                'last_seen': last.occurred_at.isoformat() if last else '',
                'status': ('ready' if not todo
                           else 'started' if done or last else 'not_started'),
            })
        return rows

    @api.model
    def remind(self, user_id):
        """Send one person a note pointing at their next required lesson."""
        self._check_team()
        user = self.env['res.users'].sudo().browse(int(user_id)).exists()
        if not user or user.share or self.env.company not in user.company_ids:
            raise AccessError(self.env._("That person is not on this team."))
        role, _chosen = self.role_of(user)
        stations = {s['key']: s for s in self.env['learn.content'].stations()}
        done = set(self.env['learn.progress'].sudo().search([
            ('user_id', '=', user.id), ('state', '=', 'done')]).mapped('key'))
        nxt = next((k for k in ROLE_PATHS[role]
                    if k in stations and k not in done), None)
        lang = (user.lang or 'en_US').startswith('vi') and 'vi' or 'en'
        name = stations[nxt]['name'].get(lang) if nxt else ''
        sender = self.env.user.name
        if lang == 'vi':
            body = (f"{sender} gợi ý bạn học tiếp bài «{name}» trong mục Học tập."
                    if name else f"{sender} gợi ý bạn xem lại mục Học tập.")
            subject = "Gợi ý học tập"
        else:
            body = (f"{sender} suggests you take the lesson “{name}” "
                    f"next, in Learn." if name
                    else f"{sender} suggests you take a look at Learn.")
            subject = "A lesson suggestion"
        if 'mail.thread' not in self.env:
            return False
        self.env['mail.thread'].sudo().message_notify(
            partner_ids=user.partner_id.ids, subject=subject, body=body)
        self.env['learn.event'].log('team_remind', detail=str(user.id))
        return True
