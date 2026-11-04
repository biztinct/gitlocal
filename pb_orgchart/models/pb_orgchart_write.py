# -*- coding: utf-8 -*-
"""ORG CHART P2 — changing the chart, live (ORGCHART_P2.md §1.2).

Every write is an explicit RPC with a plain-English answer (ledger D5):

    {'ok': True, 'label': 'Bình now reports to Giang',
     'undo': {'method': 'restore', 'args': [snapshot]},
     'refresh': {'people': [...], 'open_roles': [...], 'gone_roles': [...],
                 'counts': {...}}}

or ``{'error': 'one plain sentence'}`` — never a raise to the screen.

Rules kept here:
* The server is the judge. Rights (`_may_write`), self, loops, archived and
  other-company managers are refused here whatever the screen allowed.
* The undo snapshot is taken BEFORE anything is written; it holds exactly
  the values this call changes, and `restore()` puts them back. One generic
  undo means every write undoes the same way, and the undo itself is judged
  (a manager archived in between refuses the undo with a sentence).
* All writes of one call happen inside one savepoint: a refusal raised by a
  constraint half-way leaves nothing behind.
* The answer carries the server's own rows for everyone the write touched
  (and their managers up to the top, whose team sizes changed), so the
  screen patches its tree from facts rather than guessing (P2 §3.1, §4).
* No chatter posts beyond what field tracking writes (D6). No emails.
  `coach_id` is never written.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Datetime

_logger = logging.getLogger(__name__)

TRACKED = ('parent_id', 'pb_dotted_manager_id')


class _Refused(Exception):
    """A plain sentence for the person; raised inside a write, answered as
    ``{'error': sentence}``."""


class PbOrgChartWrite(models.AbstractModel):
    _inherit = 'pb.orgchart'

    # ============================================================ helpers
    def _no_rights(self):
        return {'error': _("Only an HR user can change who reports to whom.")}

    @api.model
    def _person(self, emp_id, role=None):
        """An active employee of the allowed companies, or a _Refused."""
        try:
            emp_id = int(emp_id)
        except (TypeError, ValueError):
            raise _Refused(_("That person is no longer on the chart. Refresh and try again."))
        emp = self.env['hr.employee'].with_context(active_test=False).browse(emp_id).exists()
        # The checks read as superuser: a person of a company that is not
        # switched on would otherwise answer "no rights" instead of the truth.
        chk = emp.sudo()
        if not emp or chk.company_id.id not in self._company_ids():
            raise _Refused(_("That person is no longer on the chart. Refresh and try again."))
        if not chk.active:
            if role == 'manager':
                raise _Refused(_("%(m)s has left, so nobody can report to them.", m=chk.name))
            raise _Refused(_("%(p)s has left and is no longer on the chart.", p=chk.name))
        return emp

    @api.model
    def _manager_for(self, emp, mgr_id):
        """The manager `emp` may report to, or a _Refused (self, archived,
        other company)."""
        mgr = self._person(mgr_id, role='manager')
        if mgr == emp:
            raise _Refused(_("Someone can't report to themselves."))
        if emp.company_id != mgr.company_id:
            raise _Refused(_("%(m)s works for %(c)s — a manager must be in the same company.",
                             m=mgr.name, c=mgr.company_id.name))
        return mgr

    @api.model
    def _job(self, job_id, must_be_open=True):
        try:
            job_id = int(str(job_id).replace('job-', ''))
        except (TypeError, ValueError):
            raise _Refused(_("That open role is no longer on the chart. Refresh and try again."))
        job = self.env['hr.job'].browse(job_id).exists()
        if job and job.sudo().company_id.id not in self._company_ids() + [False]:
            job = self.env['hr.job']
        if not job:
            raise _Refused(_("That open role is no longer on the chart. Refresh and try again."))
        if must_be_open and job.no_of_recruitment <= 0:
            raise _Refused(_("The %(t)s role is no longer open.", t=job.name))
        # Jobs are written as superuser AFTER `_may_write()`: with recruitment
        # installed an HR officer may only READ hr.job (hr_recruitment
        # re-declares `hr.access_hr_job_user` read-only; the job form's
        # interviewers are recruitment-only). sudo() keeps the user as the
        # author of the tracking message.
        return job.sudo()

    @api.model
    def _role_manager(self, job):
        """Who the open role reports to (ledger D3): its own manager, else its
        department's manager — only if active in the allowed companies."""
        comp = self._company_ids()
        for m in (job.pb_manager_id, job.department_id.manager_id):
            if m and m.active and m.company_id.id in comp:
                return m
        return self.env['hr.employee']

    @api.model
    def _parents(self):
        """Every employee's manager column, straight from the table: the loop
        check must see the whole tree, archived and other companies too."""
        Emp = self.env['hr.employee']
        Emp.flush_model(['parent_id'])
        self.env.cr.execute("SELECT id, parent_id FROM hr_employee")
        return dict(self.env.cr.fetchall())

    @api.model
    def _loop_in(self, changes, parents=None):
        """The first person in `changes` ({emp: new manager}) who would end up
        inside their own team once every change is applied, else None."""
        p = dict(parents if parents is not None else self._parents())
        p.update(changes)
        for e in changes:
            seen = set()
            c = p.get(e)
            while c and c not in seen:
                if c == e:
                    return e
                seen.add(c)
                c = p.get(c)
        return None

    @api.model
    def _loop_sentence(self, emp_id, mgr_id):
        Emp = self.env['hr.employee'].with_context(active_test=False)
        return _("Can't do that — %(m)s is inside %(p)s's own team.",
                 m=Emp.browse(mgr_id).name or _("that manager"), p=Emp.browse(emp_id).name)

    #: Fields the stock employee record recomputes when the manager changes:
    #: the coach (`hr`), the time-off approver (`hr_holidays`) and the expense
    #: approver (`hr_expense`) follow the new manager's login when they were
    #: empty or the old manager's. The chart changes the MANAGER ONLY: these
    #: are written back with their current value in the same write, which
    #: protects them from that recompute (G16 — on payobook a swap failed
    #: because the follow-up made a portal login a time-off approver).
    FOLLOWERS = ('coach_id', 'leave_manager_id', 'expense_manager_id')

    @api.model
    def _followers(self, ids):
        """{emp: {field: id or False}} for the FOLLOWERS present here."""
        Emp = self.env['hr.employee']
        flds = [f for f in self.FOLLOWERS if f in Emp._fields]
        out = {}
        for e in Emp.sudo().browse(list(ids)).exists():
            out[str(e.id)] = {f: e[f].id or False for f in flds}
        return out

    @api.model
    def _snap(self, changes):
        """The undo snapshot of a manager change, taken BEFORE it is written:
        each person's manager and the approvers the system moves with it."""
        Emp = self.env['hr.employee']
        return {'managers': {str(e): (Emp.browse(e).parent_id.id or False) for e in changes},
                'followers': self._followers(changes)}

    @api.model
    def _set_managers(self, changes):
        """Write {emp: manager or False}, the manager and nothing else.

        The coach and the approvers keep their value (the coach is a binding
        non-goal; the approvers because following would hand approval rights
        to whatever login the new manager has). They are written in the SAME
        write as the manager, which stops the stock recompute. People with
        the same new manager and the same current values share one write."""
        Emp = self.env['hr.employee']
        fol = self._followers(changes)
        groups = {}
        for e, m in changes.items():
            keep = fol.get(str(e), {})
            key = (m or False,) + tuple(sorted(keep.items()))
            groups.setdefault(key, []).append(e)
        for key, ids in groups.items():
            vals = {'parent_id': key[0]}
            vals.update(dict(key[1:]))
            Emp.browse(ids).write(vals)

    @api.model
    def _run(self, fn):
        """Run a write: rights first, then `fn()` inside one savepoint.
        `fn` returns the answer dict; a _Refused / constraint becomes
        ``{'error': sentence}`` and nothing is kept."""
        if not self._may_write():
            return self._no_rights()
        try:
            with self.env.cr.savepoint():
                return fn()
        except _Refused as e:
            return {'error': str(e.args[0])}
        except AccessError:
            return {'error': _("You don't have the rights to change this record. Ask an HR manager.")}
        except (UserError, ValidationError) as e:
            msg = str(getattr(e, 'args', [''])[0] or '')
            return {'error': _("That change could not be saved. The system said: %(m)s", m=msg)
                    if msg else _("That change could not be saved.")}

    @api.model
    def _answer(self, label, undo, emps=(), jobs=()):
        return {'ok': True, 'label': label,
                'undo': {'method': 'restore', 'args': [undo]} if undo else False,
                'refresh': self._refresh(emps, jobs)}

    @api.model
    def _refresh(self, emp_ids=(), job_ids=()):
        """The server's rows for everyone touched, plus their managers up to
        the top (whose team sizes changed), the touched open roles and the
        numbers that depend on the tree's shape."""
        graph = self._graph()
        active = set(graph['ids'])
        want = set()
        for i in emp_ids:
            c = i
            while c and c in active and c not in want:
                want.add(c)
                c = graph['mgr'].get(c)
        depts = self._departments()
        rows = self._rows(sorted(want), graph, depts)
        all_roles = self._open_roles(depts, active)
        job_ids = {int(j) for j in job_ids if j}
        roles = [o for o in all_roles if o['job_id'] in job_ids]
        open_now = {o['job_id'] for o in roles}
        return {
            'people': rows,
            'open_roles': roles,
            'gone_roles': ['job-%s' % j for j in job_ids if j not in open_now],
            'counts': self._shape_counts(graph, len(all_roles)),
        }

    @staticmethod
    def _k(d):
        """JSON keys are strings: {"12": 7} → {12: 7}."""
        return {int(k): v for k, v in (d or {}).items()}

    # ============================================================== moves
    @api.model
    def move(self, emp_id, manager_id, whole_team=True):
        """`emp` reports to `manager`. Whole team (default): their reports
        come along. Only them: their direct reports first move up to `emp`'s
        old manager (or to nobody when there was none)."""
        def go():
            emp = self._person(emp_id)
            mgr = self._manager_for(emp, manager_id)
            old = emp.parent_id
            if old == mgr:
                raise _Refused(_("%(p)s already reports to %(m)s.", p=emp.name, m=mgr.name))
            kids = self.env['hr.employee'].search([('parent_id', '=', emp.id)])
            changes = {emp.id: mgr.id}
            if not whole_team:
                for k in kids:
                    changes[k.id] = old.id or False
            if self._loop_in(changes):
                raise _Refused(self._loop_sentence(emp.id, mgr.id))
            undo = self._snap(changes)
            self._set_managers(changes)
            if whole_team or not kids:
                label = _("%(p)s now reports to %(m)s", p=emp.name, m=mgr.name)
            elif old:
                label = _("%(p)s now reports to %(m)s; their %(n)s reports stay with %(o)s",
                          p=emp.name, m=mgr.name, n=len(kids), o=old.name)
            else:
                label = _("%(p)s now reports to %(m)s; their %(n)s reports have no manager now",
                          p=emp.name, m=mgr.name, n=len(kids))
            return self._answer(label, undo, list(changes) + [mgr.id] + ([old.id] if old else []))
        return self._run(go)

    @api.model
    def move_many(self, emp_ids, manager_id):
        """Several people under one manager, all or nothing — what a company
        with nobody's manager set needs most (rize: 234 of 241)."""
        def go():
            ids = []
            for i in emp_ids or []:
                try:
                    i = int(i)
                except (TypeError, ValueError):
                    continue
                if i not in ids:
                    ids.append(i)
            if not ids:
                raise _Refused(_("Pick at least one person."))
            mgr = self._person(manager_id, role='manager')
            if mgr.id in ids:
                raise _Refused(_("%(m)s can't report to themselves — take them out of the selection.",
                                 m=mgr.name))
            people = [self._person(i) for i in ids]
            for p in people:
                self._manager_for(p, mgr.id)
            changes = {p.id: mgr.id for p in people if p.parent_id != mgr}
            if not changes:
                raise _Refused(_("Everyone you picked already reports to %(m)s.", m=mgr.name))
            bad = self._loop_in(changes)
            if bad:
                raise _Refused(self._loop_sentence(bad, mgr.id))
            Emp = self.env['hr.employee']
            undo = self._snap(changes)
            olds = {Emp.browse(e).parent_id.id for e in changes} - {False}
            self._set_managers(changes)
            n = len(changes)
            label = (_("%(p)s now reports to %(m)s", p=Emp.browse(next(iter(changes))).name, m=mgr.name)
                     if n == 1 else _("%(n)s people now report to %(m)s", n=n, m=mgr.name))
            return self._answer(label, undo, list(changes) + [mgr.id] + list(olds))
        return self._run(go)

    @api.model
    def unassign(self, emp_id):
        """Remove from their manager's team: no manager (their own team stays
        with them)."""
        def go():
            emp = self._person(emp_id)
            old = emp.parent_id
            if not old:
                raise _Refused(_("%(p)s has no manager to remove.", p=emp.name))
            undo = self._snap({emp.id: False})
            self._set_managers({emp.id: False})
            return self._answer(_("%(p)s removed from %(m)s's team", p=emp.name, m=old.name),
                                undo, [emp.id, old.id])
        return self._run(go)

    @api.model
    def swap(self, emp_id):
        """Swap places with the manager (POC semantics): `emp` takes the
        manager's manager and the manager's other reports; the manager
        reports to `emp` and takes `emp`'s former reports."""
        def go():
            emp = self._person(emp_id)
            mgr = emp.parent_id
            if not mgr:
                raise _Refused(_("%(p)s has no manager to swap places with.", p=emp.name))
            if not mgr.parent_id:
                raise _Refused(_("The top of the chart has nobody to swap with."))
            if not mgr.active or mgr.company_id != emp.company_id:
                raise _Refused(_("%(m)s can't swap places with %(p)s here.", m=mgr.name, p=emp.name))
            Emp = self.env['hr.employee']
            grand = mgr.parent_id
            mine = Emp.search([('parent_id', '=', emp.id)])
            theirs = Emp.search([('parent_id', '=', mgr.id), ('id', '!=', emp.id)])
            changes = {emp.id: grand.id, mgr.id: emp.id}
            for k in theirs:
                changes[k.id] = emp.id
            for k in mine:
                changes[k.id] = mgr.id
            if self._loop_in(changes):
                raise _Refused(self._loop_sentence(emp.id, grand.id))
            undo = self._snap(changes)
            self._set_managers(changes)
            return self._answer(_("%(p)s and %(m)s swap places", p=emp.name, m=mgr.name),
                                undo, list(changes) + [grand.id])
        return self._run(go)

    @api.model
    def set_dotted(self, emp_id, manager_id=False):
        """Add, change or clear the dotted-line manager (ledger D2)."""
        def go():
            emp = self._person(emp_id)
            old = emp.pb_dotted_manager_id
            if manager_id:
                mgr = self._manager_for(emp, manager_id)
                if mgr == emp.parent_id:
                    raise _Refused(_("%(p)s already reports to %(m)s directly.", p=emp.name, m=mgr.name))
                if mgr == old:
                    raise _Refused(_("%(p)s already has a dotted line to %(m)s.", p=emp.name, m=mgr.name))
                label = _("%(p)s also reports to %(m)s (dotted line)", p=emp.name, m=mgr.name)
            else:
                mgr = self.env['hr.employee']
                if not old:
                    raise _Refused(_("%(p)s has no dotted line to remove.", p=emp.name))
                label = _("%(p)s no longer has a dotted line to %(m)s", p=emp.name, m=old.name)
            undo = {'dotted': {str(emp.id): old.id or False}}
            emp.write({'pb_dotted_manager_id': mgr.id or False})
            return self._answer(label, undo, [emp.id])
        return self._run(go)

    # ============================================================== roles
    @api.model
    def add_open_role(self, manager_id, title, reason=False):
        """A new open role under `manager`: a job in their team, one to fill.
        The same title in the same team already exists → one more to fill."""
        def go():
            mgr = self._person(manager_id, role='manager')
            name = (title or '').strip()
            if not name:
                raise _Refused(_("Give the role a title."))
            if reason and reason not in ('growth', 'backfill', 'cover'):
                raise _Refused(_("Pick why the role is open from the list."))
            Job = self.env['hr.job'].sudo()  # see _job(): officers may only read jobs
            dept = mgr.department_id
            job = Job.search([('name', '=ilike', name), ('department_id', '=', dept.id or False),
                              ('company_id', '=', mgr.company_id.id)], limit=1)
            if job:
                undo = {'jobs': {str(job.id): {
                    'no_of_recruitment': job.no_of_recruitment,
                    'pb_manager_id': job.pb_manager_id.id or False,
                    'pb_reason': job.pb_reason or False}}}
                vals = {'no_of_recruitment': job.no_of_recruitment + 1, 'pb_manager_id': mgr.id}
                if reason:
                    vals['pb_reason'] = reason
                job.write(vals)
                label = _("One more %(t)s to hire under %(m)s", t=job.name, m=mgr.name)
            else:
                job = Job.create({
                    'name': name, 'department_id': dept.id or False,
                    'company_id': mgr.company_id.id, 'no_of_recruitment': 1,
                    'pb_manager_id': mgr.id, 'pb_reason': reason or False,
                })
                undo = {'created_jobs': [job.id]}
                label = _("New open role: %(t)s under %(m)s", t=job.name, m=mgr.name)
            return self._answer(label, undo, [mgr.id], [job.id])
        return self._run(go)

    @api.model
    def move_role(self, job_id, manager_id):
        """Hang an open role under another manager (`pb_manager_id`)."""
        def go():
            job = self._job(job_id)
            mgr = self._person(manager_id, role='manager')
            if job.company_id and mgr.company_id != job.company_id:
                raise _Refused(_("%(m)s works for %(c)s — the role is in %(r)s.",
                                 m=mgr.name, c=mgr.company_id.name, r=job.company_id.name))
            if self._role_manager(job) == mgr:
                raise _Refused(_("The %(t)s role already sits under %(m)s.", t=job.name, m=mgr.name))
            old = self._role_manager(job)
            undo = {'jobs': {str(job.id): {'pb_manager_id': job.pb_manager_id.id or False}}}
            job.write({'pb_manager_id': mgr.id})
            return self._answer(_("The open %(t)s role now sits under %(m)s", t=job.name, m=mgr.name),
                                undo, [mgr.id] + ([old.id] if old else []), [job.id])
        return self._run(go)

    @api.model
    def fill_role(self, job_id, emp_id):
        """Someone already here takes the open role: their job, title and
        manager become the role's; one fewer to hire (never below 0)."""
        def go():
            job = self._job(job_id)
            emp = self._person(emp_id)
            if job.company_id and emp.company_id != job.company_id:
                raise _Refused(_("%(p)s works for %(c)s — the role is in %(r)s.",
                                 p=emp.name, c=emp.company_id.name, r=job.company_id.name))
            mgr = self._role_manager(job)
            if mgr == emp:
                raise _Refused(_("%(p)s can't fill a role that reports to them.", p=emp.name))
            old_mgr = emp.parent_id
            if mgr and self._loop_in({emp.id: mgr.id}):
                raise _Refused(self._loop_sentence(emp.id, mgr.id))
            undo = {
                'emp_jobs': {str(emp.id): {'job_id': emp.job_id.id or False,
                                           'job_title': emp.job_title or False}},
                'jobs': {str(job.id): {'no_of_recruitment': job.no_of_recruitment}},
            }
            if mgr:
                undo.update(self._snap({emp.id: mgr.id}))
            emp.write({'job_id': job.id, 'job_title': job.name})
            if mgr and emp.parent_id != mgr:
                self._set_managers({emp.id: mgr.id})
            job.write({'no_of_recruitment': max(0, job.no_of_recruitment - 1)})
            touched = [emp.id] + ([mgr.id] if mgr else []) + ([old_mgr.id] if old_mgr else [])
            return self._answer(_("%(p)s fills the %(t)s role", p=emp.name, t=job.name),
                                undo, touched, [job.id])
        return self._run(go)

    @api.model
    def close_role(self, job_id):
        """Nobody more to hire for this role: the target goes to 0. The job
        itself (and anyone already in it) stays."""
        def go():
            job = self._job(job_id)
            undo = {'jobs': {str(job.id): {'no_of_recruitment': job.no_of_recruitment}}}
            mgr = self._role_manager(job)
            job.write({'no_of_recruitment': 0})
            return self._answer(_("The open %(t)s role is closed", t=job.name), undo,
                                [mgr.id] if mgr else [], [job.id])
        return self._run(go)

    # =============================================================== undo
    @api.model
    def restore(self, snapshot):
        """Put back exactly what one write changed (the `undo` of every
        answer). Judged like any write: a manager who left since, or a loop
        made by a change in between, refuses the undo with a sentence."""
        def go():
            snap = snapshot or {}
            Emp = self.env['hr.employee']
            managers = self._k(snap.get('managers'))
            dotted = self._k(snap.get('dotted'))
            emp_jobs = self._k(snap.get('emp_jobs'))
            jobs = self._k(snap.get('jobs'))
            created = [int(j) for j in snap.get('created_jobs') or []]
            # judge everything first
            for e, m in list(managers.items()) + list(dotted.items()):
                emp = self._person(e)
                if m:
                    self._manager_for(emp, m)
            for e in emp_jobs:
                self._person(e)
            if managers:
                bad = self._loop_in(managers)
                if bad:
                    raise _Refused(_("That can't be undone any more — the chart changed since."))
            job_recs = {}
            for j in list(jobs) + created:
                job = self._job(j, must_be_open=False)
                job_recs[job.id] = job
            # then write
            touched = set(managers) | set(dotted) | set(emp_jobs)
            for e in managers:
                old = Emp.browse(e).parent_id
                if old:
                    touched.add(old.id)
            touched |= {m for m in managers.values() if m}
            for e, vals in emp_jobs.items():
                Emp.browse(e).write({'job_id': vals.get('job_id') or False,
                                     'job_title': vals.get('job_title') or False})
            if managers:
                self._set_managers(managers)
            # the approvers (and coach) exactly as they were before the change
            Fl = [f for f in self.FOLLOWERS if f in Emp._fields]
            for e, vals in self._k(snap.get('followers')).items():
                w = {f: vals.get(f) or False for f in Fl if f in vals}
                rec = Emp.sudo().browse(e).exists()
                if rec and any((rec[f].id or False) != w[f] for f in w):
                    rec.write(w)
            for e, m in dotted.items():
                Emp.browse(e).write({'pb_dotted_manager_id': m or False})
            for j, vals in jobs.items():
                w = {k: v for k, v in vals.items()
                     if k in ('no_of_recruitment', 'pb_manager_id', 'pb_reason')}
                if w:
                    job_recs[j].write(w)
            for j in created:
                job = job_recs[j]
                mgr = self._role_manager(job)
                if mgr:
                    touched.add(mgr.id)
                # a job made a moment ago: remove it when nothing else uses it,
                # else only stop hiring for it
                if job.employee_ids or ('application_count' in job._fields and job.application_count):
                    job.write({'no_of_recruitment': 0})
                else:
                    try:
                        with self.env.cr.savepoint():
                            job.unlink()
                    except (UserError, ValidationError, AccessError) as e:
                        _logger.debug("pb_orgchart: job %s kept on undo: %s", j, e)
                        job.write({'no_of_recruitment': 0})
            return self._answer(_("Put back as it was"), False, touched,
                                list(jobs) + created)
        return self._run(go)

    # ============================================================ history
    @api.model
    def get_history(self, emp_id):
        """Manager and dotted-line changes for one person, newest first, from
        field tracking (ledger D6). A read: it never writes."""
        try:
            emp = self.env['hr.employee'].with_context(active_test=False).browse(int(emp_id)).exists()
            if not emp:
                return []
            emp.check_access('read')
        except (TypeError, ValueError, AccessError):
            return []
        # Tracking rows are readable by administrators only; the person's own
        # record was read as the user above, and only these two fields are
        # returned.
        F = self.env['ir.model.fields'].sudo()
        fld = {f.id: f.name for f in F.search([('model', '=', 'hr.employee'), ('name', 'in', TRACKED)])}
        if not fld:
            return []
        vals = self.env['mail.tracking.value'].sudo().search([
            ('field_id', 'in', list(fld)),
            ('mail_message_id.model', '=', 'hr.employee'),
            ('mail_message_id.res_id', '=', emp.id)], limit=200)
        People = self.env['hr.employee'].sudo().with_context(active_test=False)
        ids = {v.old_value_integer for v in vals} | {v.new_value_integer for v in vals}
        names = {p.id: p.name for p in People.browse([i for i in ids if i]).exists()}

        def nm(i):
            return names.get(i) or _("someone no longer here")

        out = []
        for v in vals:
            msg = v.mail_message_id
            o, n = v.old_value_integer, v.new_value_integer
            if fld[v.field_id.id] == 'parent_id':
                if o and n:
                    what = _("Moved from %(a)s to %(b)s", a=nm(o), b=nm(n))
                elif n:
                    what = _("Manager set to %(b)s", b=nm(n))
                elif o:
                    what = _("Removed from %(a)s's team", a=nm(o))
                else:
                    continue
            else:
                if o and n:
                    what = _("Dotted line moved from %(a)s to %(b)s", a=nm(o), b=nm(n))
                elif n:
                    what = _("Dotted line to %(b)s added", b=nm(n))
                elif o:
                    what = _("Dotted line to %(a)s removed", a=nm(o))
                else:
                    continue
            when = Datetime.context_timestamp(self, msg.date) if msg.date else None
            out.append({
                'when': when.date().isoformat() if when else '',
                'at': msg.date.isoformat() if msg.date else '',
                'what': what,
                'who': msg.author_id.name or '',
                'kind': 'dotted' if fld[v.field_id.id] != 'parent_id' else 'move',
                '_k': (msg.date or Datetime.now(), v.id),
            })
        out.sort(key=lambda r: r['_k'], reverse=True)
        for r in out:
            r.pop('_k')
        return out
