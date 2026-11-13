# -*- coding: utf-8 -*-
"""ORG CHART P3 — the plan's projection, the plan RPCs, the time machine and
"Suggest a chart" (ORGCHART_P3.md §1.1.3–4, §1.2, §1.3).

THE PROJECTION. A plan is a list of changes over the live chart. `_project`
replays them over an in-memory copy of the manager / dotted-line columns
(`_proj_base`), judging each one exactly as P2 judges a live write — same
sentences, same loop rule (`_loop_in`), but against the PROJECTION, so a
change that only loops because of an earlier planned move is refused. Every
read here is a read: nothing in this file writes an employee or a job.

THE TIME MACHINE. The past comes from field tracking (`mail.tracking.value`
rows for `parent_id` / `pb_dotted_manager_id` on `hr.employee`): for each
person, the OLDEST row written after the day shown carries the value they had
on that day. People who joined after the day are hidden and a hidden manager
is skipped up the chain. People archived since are not brought back (their
rows are gone from the chart's search); the note says so. The future is
today's chart plus approved-not-yet-live plans up to that day, minus people
whose departure date has passed, plus accepted offers as "Starts …" cards.
"""
import logging
import uuid
from collections import Counter
from datetime import datetime, time as dtime, timedelta
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_date

from .pb_orgchart import _initials
from .pb_orgchart_plan import state_label
from .pb_orgchart_write import _Refused

_logger = logging.getLogger(__name__)

#: The person at the top of a company, by title (P3 §1.3 rule d).
TOP_TITLE = re.compile(r"chief executive|\bceo\b|managing director|general director|giám đốc", re.I)
WIDE_SPAN = 10
OFFER_ACCEPTED = ('accepted', 'signed')


class PbOrgChartProject(models.AbstractModel):
    _inherit = 'pb.orgchart'

    # ================================================================ state
    @api.model
    def _proj_base(self, company_id):
        """The live columns the projection starts from: every employee's
        manager, dotted line, active flag and company (the whole table — a
        loop must see archived and other-company people too)."""
        Emp = self.env['hr.employee']
        Emp.flush_model(['parent_id', 'pb_dotted_manager_id', 'active', 'company_id'])
        self.env.cr.execute(
            "SELECT id, parent_id, pb_dotted_manager_id, active, company_id FROM hr_employee")
        mgr, dot, info = {}, {}, {}
        for i, p, d, a, c in self.env.cr.fetchall():
            mgr[i] = p or False
            dot[i] = d or False
            info[i] = (bool(a), c)
        return {'company': company_id, 'mgr': mgr, 'dot': dot, 'info': info,
                'live_mgr': dict(mgr), 'live_dot': dict(dot),
                'title': {}, 'roles': {}, 'virtual': [], 'touched': set(),
                'stale': {}, 'names': {}}

    @api.model
    def _nm(self, st, i):
        if not i:
            return _("nobody")
        if i not in st['names']:
            st['names'][i] = self.env['hr.employee'].sudo().with_context(
                active_test=False).browse(i).name or ''
        return st['names'][i]

    @api.model
    def _vperson(self, st, eid, role=None):
        try:
            eid = int(eid)
        except (TypeError, ValueError):
            raise _Refused(_("That person is no longer on the chart. Refresh and try again."))
        inf = st['info'].get(eid)
        if not inf:
            raise _Refused(_("That person is no longer on the chart. Refresh and try again."))
        active, comp = inf
        if comp != st['company']:
            if comp in self._company_ids():
                c = self.env['res.company'].sudo().browse(comp)
                pc = self.env['res.company'].sudo().browse(st['company'])
                raise _Refused(_("%(p)s works for %(c)s — this plan is for %(pc)s.",
                                 p=self._nm(st, eid), c=c.name, pc=pc.name))
            raise _Refused(_("That person is no longer on the chart. Refresh and try again."))
        if not active:
            if role == 'manager':
                raise _Refused(_("%(m)s has left, so nobody can report to them.", m=self._nm(st, eid)))
            raise _Refused(_("%(p)s has left and is no longer on the chart.", p=self._nm(st, eid)))
        return eid

    @api.model
    def _vmanager(self, st, e, mid):
        m = self._vperson(st, mid, role='manager')
        if m == e:
            raise _Refused(_("Someone can't report to themselves."))
        return m

    @api.model
    def _vkids(self, st, e):
        return [k for k, m in st['mgr'].items() if m == e and st['info'].get(k, (False,))[0]]

    @api.model
    def _vrole(self, st, job_ref):
        """An open role in the projection: (job id, {count, mgr, title})."""
        if isinstance(job_ref, str) and job_ref.startswith('plan-'):
            raise _Refused(_("That role is new in this plan. Take it out of the list of changes "
                             "instead, or fill it once the plan is live."))
        try:
            jid = int(str(job_ref).replace('job-', ''))
        except (TypeError, ValueError):
            raise _Refused(_("That open role is no longer on the chart. Refresh and try again."))
        if jid not in st['roles']:
            job = self.env['hr.job'].sudo().browse(jid).exists()
            if not job or (job.company_id and job.company_id.id != st['company']):
                raise _Refused(_("That open role is no longer on the chart. Refresh and try again."))
            m = self._role_manager(job)
            st['roles'][jid] = {'count': int(job.no_of_recruitment or 0), 'mgr': m.id or False,
                                'title': job.name or '', 'dept_id': job.department_id.id or False,
                                'live_count': int(job.no_of_recruitment or 0), 'live_mgr': m.id or False}
        return jid, st['roles'][jid]

    # ============================================================ one change
    @api.model
    def _vapply(self, st, ch):
        """Judge one change against the projection and apply it to `st`.

        Returns ``{'label', 'note', 'from'}`` or raises _Refused with the
        same sentence the live write would give. Nothing is mutated before
        every check has passed."""
        k = ch.get('kind')
        nm = lambda i: self._nm(st, i)   # noqa: E731
        if k == 'move':
            e = self._vperson(st, ch.get('employee_id'))
            m = self._vmanager(st, e, ch.get('to_manager_id'))
            old = st['mgr'].get(e) or False
            if old == m:
                raise _Refused(_("%(p)s already reports to %(m)s.", p=nm(e), m=nm(m)))
            whole = ch.get('whole_team', True) is not False
            kids = self._vkids(st, e)
            changes = {e: m}
            if not whole:
                for kk in kids:
                    changes[kk] = old
            if self._loop_in(changes, parents=st['mgr']):
                raise _Refused(_("Can't do that — %(m)s is inside %(p)s's own team.", m=nm(m), p=nm(e)))
            st['mgr'].update(changes)
            st['touched'] |= set(changes)
            if whole or not kids:
                label = _("%(p)s now reports to %(m)s", p=nm(e), m=nm(m))
            elif old:
                label = _("%(p)s now reports to %(m)s; their %(n)s reports stay with %(o)s",
                          p=nm(e), m=nm(m), n=len(kids), o=nm(old))
            else:
                label = _("%(p)s now reports to %(m)s; their %(n)s reports have no manager now",
                          p=nm(e), m=nm(m), n=len(kids))
            note = _("From %(o)s", o=nm(old)) if old else _("Had no manager")
            return {'label': label, 'note': note, 'from': old}
        if k == 'unassign':
            e = self._vperson(st, ch.get('employee_id'))
            old = st['mgr'].get(e) or False
            if not old:
                raise _Refused(_("%(p)s has no manager to remove.", p=nm(e)))
            st['mgr'][e] = False
            st['touched'].add(e)
            return {'label': _("%(p)s removed from %(m)s's team", p=nm(e), m=nm(old)),
                    'note': _("Now in the “no manager yet” lane"), 'from': old}
        if k == 'swap':
            e = self._vperson(st, ch.get('employee_id'))
            m = st['mgr'].get(e) or False
            if not m:
                raise _Refused(_("%(p)s has no manager to swap places with.", p=nm(e)))
            grand = st['mgr'].get(m) or False
            if not grand:
                raise _Refused(_("The top of the chart has nobody to swap with."))
            inf = st['info'].get(m, (False, None))
            if not inf[0] or inf[1] != st['company']:
                raise _Refused(_("%(m)s can't swap places with %(p)s here.", m=nm(m), p=nm(e)))
            mine = self._vkids(st, e)
            theirs = [x for x in self._vkids(st, m) if x != e]
            changes = {e: grand, m: e}
            for x in theirs:
                changes[x] = e
            for x in mine:
                changes[x] = m
            if self._loop_in(changes, parents=st['mgr']):
                raise _Refused(_("Can't do that — %(m)s is inside %(p)s's own team.", m=nm(grand), p=nm(e)))
            st['mgr'].update(changes)
            st['touched'] |= set(changes)
            return {'label': _("%(p)s and %(m)s swap places", p=nm(e), m=nm(m)),
                    'note': _("%(p)s now leads; %(m)s reports to them", p=nm(e), m=nm(m)),
                    'from': m, 'to': m}
        if k == 'dotted':
            e = self._vperson(st, ch.get('employee_id'))
            old = st['dot'].get(e) or False
            to = ch.get('to_manager_id')
            if to:
                m = self._vmanager(st, e, to)
                if m == st['mgr'].get(e):
                    raise _Refused(_("%(p)s already reports to %(m)s directly.", p=nm(e), m=nm(m)))
                if m == old:
                    raise _Refused(_("%(p)s already has a dotted line to %(m)s.", p=nm(e), m=nm(m)))
                st['dot'][e] = m
                label = _("%(p)s also reports to %(m)s (dotted line)", p=nm(e), m=nm(m))
            else:
                if not old:
                    raise _Refused(_("%(p)s has no dotted line to remove.", p=nm(e)))
                st['dot'][e] = False
                label = _("%(p)s no longer has a dotted line to %(m)s", p=nm(e), m=nm(old))
            st['touched'].add(e)
            return {'label': label, 'note': _("Their main manager stays the same"), 'from': old}
        if k == 'new_role':
            m = self._vperson(st, ch.get('to_manager_id'), role='manager')
            title = (ch.get('title') or '').strip()
            if not title:
                raise _Refused(_("Give the role a title."))
            reason = ch.get('reason') or False
            if reason and reason not in ('growth', 'backfill', 'cover'):
                raise _Refused(_("Pick why the role is open from the list."))
            dept = self.env['hr.employee'].sudo().browse(m).department_id.id or False
            st['virtual'].append({'id': 'plan-%s' % (ch.get('cid') or 'new'), 'cid': ch.get('cid'),
                                  'title': title, 'mgr': m, 'reason': reason, 'dept_id': dept})
            return {'label': _("New open role: %(t)s under %(m)s", t=title, m=nm(m)),
                    'note': _("Hiring sees it as a job to fill once the plan is live"), 'from': False}
        if k == 'move_role':
            jid, r = self._vrole(st, ch.get('job_id'))
            if r['count'] <= 0:
                raise _Refused(_("The %(t)s role is no longer open.", t=r['title']))
            m = self._vperson(st, ch.get('to_manager_id'), role='manager')
            if r['mgr'] == m:
                raise _Refused(_("The %(t)s role already sits under %(m)s.", t=r['title'], m=nm(m)))
            old = r['mgr']
            r['mgr'] = m
            return {'label': _("The open %(t)s role now sits under %(m)s", t=r['title'], m=nm(m)),
                    'note': _("From %(o)s", o=nm(old)) if old else _("Had no manager"), 'from': old}
        if k == 'fill_role':
            jid, r = self._vrole(st, ch.get('job_id'))
            if r['count'] <= 0:
                raise _Refused(_("The %(t)s role is no longer open.", t=r['title']))
            e = self._vperson(st, ch.get('employee_id'))
            rm = r['mgr']
            if rm == e:
                raise _Refused(_("%(p)s can't fill a role that reports to them.", p=nm(e)))
            if rm and self._loop_in({e: rm}, parents=st['mgr']):
                raise _Refused(_("Can't do that — %(m)s is inside %(p)s's own team.", m=nm(rm), p=nm(e)))
            old = st['mgr'].get(e) or False
            if rm:
                st['mgr'][e] = rm
            st['title'][e] = r['title']
            r['count'] -= 1
            st['touched'].add(e)
            return {'label': _("%(p)s fills the %(t)s role", p=nm(e), t=r['title']),
                    'note': _("Their title becomes %(t)s; one fewer to hire", t=r['title']), 'from': old}
        if k == 'close_role':
            jid, r = self._vrole(st, ch.get('job_id'))
            if r['count'] <= 0:
                raise _Refused(_("The %(t)s role is no longer open.", t=r['title']))
            r['count'] = 0
            return {'label': _("The open %(t)s role is closed", t=r['title']),
                    'note': _("Nobody more to hire for it"), 'from': False}
        raise _Refused(_("That kind of change is not known."))

    @api.model
    def _project(self, plan, st=None):
        """Replay a plan's (not yet applied) changes over `st`. A change that
        is no longer possible is skipped and named in `st['stale']`."""
        plan = plan.sudo()
        if st is None:
            st = self._proj_base(plan.company_id.id)
        else:
            st['company'] = plan.company_id.id
        for ch in plan.change_ids.sorted('sequence'):
            if ch.applied:
                continue
            try:
                self._vapply(st, ch._as_dict())
            except _Refused as e:
                st['stale'][ch.id] = str(e.args[0])
        return st

    @api.model
    def _proj_view(self, st):
        """A projection as a `_graph` / `_rows` / `_open_roles` view."""
        changed = set()
        for e in st['touched']:
            if (st['mgr'].get(e) != st['live_mgr'].get(e)
                    or st['dot'].get(e) != st['live_dot'].get(e) or e in st['title']):
                changed.add(e)
        ghost = [{'from_manager_id': st['live_mgr'][e], 'emp_id': e}
                 for e in sorted(changed)
                 if st['live_mgr'].get(e) and st['mgr'].get(e) != st['live_mgr'].get(e)]
        return {'parents': st['mgr'], 'dotted': st['dot'], 'titles': st['title'],
                'roles': st['roles'], 'virtual': st['virtual'],
                'changed': changed, 'ghost': ghost}

    # ============================================================== views
    @api.model
    def _view_for(self, plan_id=None, as_of=None):
        """(view, extra payload) for `get_chart` / `get_branch`."""
        if plan_id:
            try:
                plan = self._plan_get(plan_id)
            except _Refused as e:
                return None, {'error': str(e.args[0])}
            st = self._project(plan)
            view = self._proj_view(st)
            return view, {
                'plan': self._plan_payload(plan, st),
                'changed_ids': sorted(view['changed']),
                'ghost_edges': view['ghost'],
            }
        if as_of:
            try:
                day = fields.Date.to_date(as_of)
            except (TypeError, ValueError):
                day = None
            today = fields.Date.context_today(self)
            if not day or day == today:
                return None, {}
            if day < today:
                return self._past_view(day)
            return self._future_view(day)
        return None, {}

    @api.model
    def _join_dates(self, ids):
        """Best-known join date per person (P1's rule: first contract date,
        else the earliest contract start, else the day the record was made).
        SQL over ids the caller already read, for hiding only."""
        if not ids:
            return {}
        has_contract = 'hr.contract' in self.env
        self.env['hr.employee'].flush_model()
        self.env.cr.execute("""
            SELECT e.id, e.first_contract_date, %s, e.create_date::date
              FROM hr_employee e WHERE e.id = ANY(%%s)""" % (
            "(SELECT min(c.date_start) FROM hr_contract c WHERE c.employee_id = e.id)"
            if has_contract else "NULL::date"), [list(ids)])
        return {i: (a or b or c) for i, a, b, c in self.env.cr.fetchall()}

    @api.model
    def _past_view(self, day):
        """Who reported to whom at the end of `day`, from field tracking."""
        ids = self.env['hr.employee'].search([('company_id', 'in', self._company_ids())]).ids
        F = self.env['ir.model.fields'].sudo().search(
            [('model', '=', 'hr.employee'), ('name', 'in', ('parent_id', 'pb_dotted_manager_id'))])
        fname = {f.id: f.name for f in F}
        parents, dotted_over = {}, {}
        if fname and ids:
            self.env['mail.tracking.value'].flush_model()
            self.env['mail.message'].flush_model()
            end = datetime.combine(day + timedelta(days=1), dtime.min)
            self.env.cr.execute("""
                SELECT m.res_id, v.field_id, v.old_value_integer
                  FROM mail_tracking_value v JOIN mail_message m ON m.id = v.mail_message_id
                 WHERE m.model = 'hr.employee' AND v.field_id = ANY(%s)
                   AND m.res_id = ANY(%s) AND m.date >= %s
                 ORDER BY m.date ASC, v.id ASC""", [list(fname), ids, end])
            seen = set()
            for res_id, fid, old in self.env.cr.fetchall():
                key = (res_id, fid)
                if key in seen:
                    continue
                seen.add(key)
                if fname[fid] == 'parent_id':
                    parents[res_id] = old or False
                else:
                    dotted_over[res_id] = old or False
        dotted = None
        if dotted_over:
            self.env.cr.execute("SELECT id, pb_dotted_manager_id FROM hr_employee WHERE id = ANY(%s)", [ids])
            dotted = {i: d for i, d in self.env.cr.fetchall() if d}
            dotted.update(dotted_over)
        joined = self._join_dates(ids)
        hide = {i for i, d in joined.items() if d and d > day}
        view = {'parents': parents, 'dotted': dotted, 'hide': hide, 'no_roles': True, 'ref_day': day}
        return view, {
            'as_of': fields.Date.to_string(day),
            'as_of_note': _("Showing who reported to whom on %(d)s · people who have since left are not shown",
                            d=format_date(self.env, day, date_format='d MMM y')),
        }

    @api.model
    def _future_view(self, day):
        """Today plus everything known to happen by `day`."""
        ids = self.env['hr.employee'].search([('company_id', 'in', self._company_ids())]).ids
        Plan = self.env['pb.orgchart.plan'].sudo()
        plans = Plan.search([('state', '=', 'approved'), ('effective_date', '<=', day),
                             ('company_id', 'in', self._company_ids())],
                            order='effective_date, id')
        st = None
        for plan in plans:
            st = self._project(plan, st if st is not None else self._proj_base(plan.company_id.id))
        view = self._proj_view(st) if st is not None else {}
        # leavers: a departure date on or before the day shown
        hide = set()
        if ids:
            self.env['hr.employee'].flush_model(['current_version_id'])
            self.env['hr.version'].flush_model(['departure_date'])
            self.env.cr.execute("""
                SELECT e.id FROM hr_employee e JOIN hr_version v ON v.id = e.current_version_id
                 WHERE e.id = ANY(%s) AND v.departure_date IS NOT NULL AND v.departure_date <= %s""",
                                [ids, day])
            hide = {r[0] for r in self.env.cr.fetchall()}
        view = dict(view, hide=hide, ref_day=day)
        n_plans = len(plans)
        dlabel = format_date(self.env, day, date_format='d MMM y')
        return view, {
            'as_of': fields.Date.to_string(day),
            'as_of_note': _("Showing the chart on %(d)s · announced leavers and accepted offers up to that day",
                            d=dlabel) if not n_plans else (_("Showing the chart on %(d)s · %(n)s approved plans, announced leavers and "
                             "accepted offers up to that day", d=format_date(self.env, day, date_format='d MMM y'),
                             n=n_plans) if n_plans != 1 else
                           _("Showing the chart on %(d)s · 1 approved plan, announced leavers and "
                             "accepted offers up to that day", d=format_date(self.env, day, date_format='d MMM y'))),
            'changed_ids': sorted(view.get('changed') or ()),
            'ghost_edges': [],
            'starters': self._starters(day),
        }

    @api.model
    def _starters(self, day):
        """Accepted offers starting by `day`, as "Starts …" cards. pb_hiring
        is a soft dependency."""
        if 'pb.hiring.offer' not in self.env:
            return []
        today = fields.Date.context_today(self)
        try:
            offers = self.env['pb.hiring.offer'].sudo().search([
                ('state', 'in', OFFER_ACCEPTED), ('start_date', '>', today), ('start_date', '<=', day),
                ('company_id', 'in', self._company_ids())], order='start_date, id')
        except Exception as e:  # noqa: BLE001 — no offers is a fine answer
            _logger.debug("pb_orgchart: offers unreadable: %s", e)
            return []
        out = []
        for o in offers:
            try:
                if o.employee_id and o.employee_id.active:
                    continue    # already on the chart as themselves
                req = o.requisition_id
                mgr = o.reporting_manager_id or req.reporting_manager_id \
                    or req.department_id.manager_id
                name = o.candidate_name or _("New starter")
                out.append({
                    'id': 'start-%s' % o.id, 'name': name, 'ini': _initials(name),
                    'title': o.job_title or '', 'dept_id': req.department_id.id or False,
                    'dept': req.department_id.name or '', 'loc': o.location or '',
                    'manager_id': mgr.id if mgr and mgr.active else False,
                    'start': fields.Date.to_string(o.start_date),
                    'start_label': _("Starts %(d)s", d=format_date(self.env, o.start_date, date_format='d MMM')),
                })
            except Exception as e:  # noqa: BLE001 — one bad offer never blocks the chart
                _logger.debug("pb_orgchart: offer %s skipped: %s", o.id, e)
        return out

    # ============================================================ plans
    @api.model
    def _plan_get(self, plan_id, edit=False):
        try:
            plan = self.env['pb.orgchart.plan'].browse(int(plan_id)).exists()
        except (TypeError, ValueError):
            plan = None
        if not plan:
            raise _Refused(_("That plan is no longer there. Refresh and try again."))
        try:
            plan.check_access('read')
        except AccessError:
            raise _Refused(_("That plan is not yours to see."))
        if edit:
            if plan.state != 'draft':
                raise _Refused(_("This plan has already been sent, so it can't be changed."))
            if plan.user_id != self.env.user:
                raise _Refused(_("Only the person who started a plan can change it."))
        return plan

    @api.model
    def _plan_run(self, fn):
        """Rights, then `fn()` in one savepoint; refusals become sentences."""
        if not self._may_write():
            return {'error': _("Only an HR user can plan changes to the chart.")}
        try:
            with self.env.cr.savepoint():
                return fn()
        except _Refused as e:
            return {'error': str(e.args[0])}
        except AccessError:
            return {'error': _("You don't have the rights to change this plan. Ask an HR manager.")}
        except (UserError, ValidationError) as e:
            msg = str(getattr(e, 'args', [''])[0] or '')
            return {'error': msg or _("That could not be saved.")}

    @api.model
    def _my_draft_summary(self):
        plan = self.env['pb.orgchart.plan'].search([
            ('user_id', '=', self.env.uid), ('company_id', '=', self.env.company.id),
            ('state', '=', 'draft')], limit=1)
        return {'id': plan.id, 'n': len(plan.change_ids), 'name': plan.name} if plan else False

    @api.model
    def _plan_approvers(self, plan):
        """Who the plan will go to, in words: the route's steps and the
        people each one asks today. Never raises."""
        out = {'ok': False, 'steps': [], 'line': _("the HR team")}
        try:
            plan = plan.sudo()
            if not plan._engine_managed():
                return out
            engine = self.env['biz.approval.engine'].sudo()
            process = plan._approval_process()
            ctx = plan._approval_context()
            binding, version, _trace, error = engine._resolve_binding(
                plan.company_id, process, ctx.get('scope_keys'), ctx.get('kind_key'))
            if error or not version:
                return out
            from odoo.addons.biz_approval_workflow.models import definition as D
            d = D.normalise(version.definition)
            steps = []
            for step in d.get('steps') or []:
                if step.get('kind') == 'fast':
                    steps.append({'title': _("No approval needed"), 'names': []})
                    continue
                if step.get('kind') == 'notify':
                    continue
                people, _issue = engine._resolve_step_people(
                    step, ctx, plan.company_id, plan.effective_date or fields.Date.context_today(self),
                    record=plan)
                # P4 (G33): the same swap the engine makes when the request is
                # built — a seat holder who is the sender is replaced by the
                # seat's backup — so the dialog names who will really be asked
                if hasattr(engine, '_conflict_swap'):
                    people, _notes = engine._conflict_swap(people, ctx, d.get('safeguards') or {})
                steps.append({'title': step.get('title') or '', 'names': [p['name'] for p in people]})
            if steps:
                out['steps'] = steps
                out['ok'] = True
                first = steps[0]
                out['line'] = ("%s (%s)" % (first['title'], ", ".join(first['names']))
                               if first['names'] else first['title'])
                none_needed = _("No approval needed")
                out['fast'] = all(s['title'] == none_needed for s in steps)
        except Exception as e:  # noqa: BLE001 — the dialog falls back to words
            _logger.debug("pb_orgchart: approvers of plan %s unknown: %s", plan.id, e)
        return out

    @api.model
    def _plan_payload(self, plan, st=None):
        plan = plan.sudo()
        if st is None:
            st = self._project(plan)
        comp = plan.company_id.id
        changed = self._proj_view(st)['changed']

        def spans(mgrmap):
            c = Counter(m for e, m in mgrmap.items()
                        if m and st['info'].get(e, (False, None)) == (True, comp))
            return sum(1 for n in c.values() if n >= WIDE_SPAN)

        chs = plan.change_ids.sorted('sequence')
        moved_dept = False
        for e in changed:
            m = st['mgr'].get(e)
            if m and m != st['live_mgr'].get(e):
                Emp = self.env['hr.employee'].sudo()
                if Emp.browse(e).department_id != Emp.browse(m).department_id:
                    moved_dept = True
                    break
        mine = plan.user_id.id == self.env.uid
        return {
            'plan_id': plan.id, 'name': plan.name, 'state': plan.state,
            'state_label': state_label(self.env, plan.state),
            'effective_date': fields.Date.to_string(plan.effective_date),
            'effective_label': format_date(self.env, plan.effective_date, date_format='d MMM y')
            if plan.effective_date else '',
            'note': plan.note or '', 'n': len(chs), 'mine': mine,
            'user': plan.user_id.name or '',
            'editable': plan.state == 'draft' and mine,
            'apply_error': plan.apply_error or '',
            'changes': [{
                'id': c.id, 'kind': c.kind, 'label': c.label or '', 'note': c.note or '',
                'employee_id': c.employee_id.id or False, 'to_manager_id': c.to_manager_id.id or False,
                'job_id': c.job_id.id or False, 'batch': c.batch or '',
                'applied': c.applied, 'error': c.error or '', 'stale': st['stale'].get(c.id) or '',
            } for c in chs],
            'effect': {
                'people': len(changed),
                'new_roles': len(chs.filtered(lambda c: c.kind == 'new_role')),
                'closed_roles': len(chs.filtered(lambda c: c.kind == 'close_role')),
                'wide_before': spans(st['live_mgr']),
                'wide_after': spans(st['mgr']),
                'crosses_teams': moved_dept,
            },
            'approver': self._plan_approvers(plan),
        }

    @api.model
    def _create_changes(self, plan, st, changes):
        """Judge `changes` in order against the projection and store them as
        one batch (all or nothing)."""
        Change = self.env['pb.orgchart.plan.change']
        seq = max(plan.change_ids.mapped('sequence') or [0])
        batch = uuid.uuid4().hex[:12]
        made = Change
        for ch in changes:
            if not isinstance(ch, dict):
                raise _Refused(_("That change could not be read. Refresh and try again."))
            seq += 10
            ch = dict(ch)
            kind = ch.get('kind')
            if kind == 'new_role':
                rec = Change.create({'plan_id': plan.id, 'sequence': seq, 'batch': batch,
                                     'kind': kind, 'label': '/'})
                ch['cid'] = rec.id
                res = self._vapply(st, ch)
            else:
                res = self._vapply(st, ch)
                rec = Change.create({'plan_id': plan.id, 'sequence': seq, 'batch': batch,
                                     'kind': kind, 'label': '/'})
            job = ch.get('job_id')
            vals = {
                'employee_id': int(ch['employee_id']) if ch.get('employee_id') else False,
                'to_manager_id': int(ch['to_manager_id']) if ch.get('to_manager_id') else False,
                'from_manager_id': res.get('from') or False,
                'whole_team': ch.get('whole_team', True) is not False,
                'job_id': int(str(job).replace('job-', '')) if job and not str(job).startswith('plan-') else False,
                'title': (ch.get('title') or '').strip() or False,
                'reason': ch.get('reason') or False,
                'label': res['label'], 'note': res.get('note') or False,
            }
            if kind == 'swap':
                vals['to_manager_id'] = res.get('to') or False
            rec.write(vals)
            made |= rec
        return made

    # ------------------------------------------------------------ RPCs
    @api.model
    def plan_open(self):
        """The caller's open draft for the current company (one each),
        made when there is none."""
        def go():
            Plan = self.env['pb.orgchart.plan']
            plan = Plan.search([('user_id', '=', self.env.uid), ('state', '=', 'draft'),
                                ('company_id', '=', self.env.company.id)], limit=1)
            if not plan:
                plan = Plan.create({'company_id': self.env.company.id, 'user_id': self.env.uid})
            return self._plan_payload(plan)
        return self._plan_run(go)

    @api.model
    def plan_add_change(self, plan_id, change):
        return self.plan_add_changes(plan_id, [change])

    @api.model
    def plan_add_changes(self, plan_id, changes):
        """Add one change, or several in one go (they undo together). Each is
        judged against the projection so far; one refusal refuses all."""
        def go():
            plan = self._plan_get(plan_id, edit=True)
            if not changes:
                raise _Refused(_("Nothing to add."))
            st = self._project(plan)
            made = self._create_changes(plan, st, changes)
            out = self._plan_payload(plan)
            out['ok'] = True
            out['label'] = made[-1:].label if len(made) == 1 else \
                _("%(n)s changes added to your plan", n=len(made))
            return out
        return self._plan_run(go)

    @api.model
    def plan_remove_change(self, plan_id, change_id):
        def go():
            plan = self._plan_get(plan_id, edit=True)
            ch = plan.change_ids.filtered(lambda c: c.id == int(change_id))
            if not ch:
                raise _Refused(_("That change is no longer in the plan."))
            ch.unlink()
            return dict(self._plan_payload(plan), ok=True)
        return self._plan_run(go)

    @api.model
    def plan_undo(self, plan_id):
        """Take the last change (or the last batch) out; answer with what was
        removed, so the screen can offer Redo."""
        def go():
            plan = self._plan_get(plan_id, edit=True)
            chs = plan.change_ids.sorted('sequence')
            if not chs:
                raise _Refused(_("Nothing to undo."))
            last = chs[-1]
            gone = chs.filtered(lambda c: c.batch and c.batch == last.batch) if last.batch else last
            redo = []
            for c in gone.sorted('sequence'):
                d = c._as_dict()
                d.pop('cid', None)
                d.pop('from_manager_id', None)
                if c.kind == 'swap':
                    d.pop('to_manager_id', None)
                redo.append(d)
            label = last.label if len(gone) == 1 else _("%(n)s changes", n=len(gone))
            gone.unlink()
            return dict(self._plan_payload(plan), ok=True, redo=redo, label=label)
        return self._plan_run(go)

    @api.model
    def plan_set(self, plan_id, vals):
        """Name, effective date and message of a draft plan."""
        def go():
            plan = self._plan_get(plan_id, edit=True)
            w = {}
            vals_ = vals or {}
            if 'name' in vals_:
                name = (vals_.get('name') or '').strip()
                if not name:
                    raise _Refused(_("Give the plan a name."))
                w['name'] = name[:120]
            if 'effective_date' in vals_:
                try:
                    day = fields.Date.to_date(vals_.get('effective_date'))
                except (TypeError, ValueError):
                    day = None
                if not day:
                    raise _Refused(_("Pick the day the changes should be made."))
                if day < fields.Date.context_today(self):
                    raise _Refused(_("Pick today or a later day."))
                w['effective_date'] = day
            if 'note' in vals_:
                w['note'] = (vals_.get('note') or '').strip() or False
            if w:
                plan.write(w)
            return dict(self._plan_payload(plan), ok=True)
        return self._plan_run(go)

    @api.model
    def plan_submit(self, plan_id, vals=None):
        """Send the plan for approval (optionally saving name, date and
        message first)."""
        if vals:
            res = self.plan_set(plan_id, vals)
            if res.get('error'):
                return res

        def go():
            plan = self._plan_get(plan_id, edit=True)
            st = self._project(plan)
            if st['stale']:
                raise _Refused(_("Some changes are no longer possible — they are marked in the list. "
                                 "Take them out, then send the plan."))
            plan.action_submit()
            plan.invalidate_recordset()
            if plan.state == 'pending':
                label = _("Sent to the HR team for approval. You'll be told when it is live.")
            elif plan.state == 'applied':
                label = _("No approval was needed, so the changes are live now.")
            else:
                label = _("Approved straight away. The changes are made on %(d)s.",
                          d=format_date(self.env, plan.effective_date))
            return dict(self._plan_payload(plan), ok=True, label=label)
        return self._plan_run(go)

    @api.model
    def plan_discard(self, plan_id):
        def go():
            plan = self._plan_get(plan_id, edit=True)
            plan.action_discard()
            return {'ok': True, 'label': _("Plan discarded — the chart is back to how it was.")}
        return self._plan_run(go)

    @api.model
    def plans_list(self):
        """My plans that are still going (and the last month's outcomes),
        plus the company's plans waiting for approval."""
        if not self._may_write():
            return []
        Plan = self.env['pb.orgchart.plan']
        since = fields.Datetime.now() - timedelta(days=30)
        mine = Plan.search([('user_id', '=', self.env.uid), ('company_id', 'in', self._company_ids()),
                            '|', ('state', 'in', ('draft', 'pending', 'approved')),
                            '&', ('state', 'in', ('refused', 'applied')), ('write_date', '>=', since)],
                           limit=30)
        others = Plan.search([('user_id', '!=', self.env.uid), ('company_id', 'in', self._company_ids()),
                              ('state', 'in', ('pending', 'approved'))], limit=30)
        order = {'draft': 0, 'pending': 1, 'approved': 2, 'applied': 3, 'refused': 4}
        out = []
        for p in sorted(mine | others, key=lambda r: (order.get(r.state, 9), -r.id)):
            out.append({
                'id': p.id, 'name': p.name, 'state': p.state,
                'state_label': state_label(self.env, p.state), 'n': len(p.change_ids),
                'effective_label': format_date(self.env, p.effective_date, date_format='d MMM y')
                if p.effective_date else '',
                'mine': p.user_id.id == self.env.uid, 'user': p.user_id.name or '',
                'errors': len(p.change_ids.filtered(lambda c: c.error and not c.applied)),
            })
        return out

    # ===================================================== suggest a chart
    @api.model
    def suggest_chart(self):
        """A starting point for a company where few managers are set: who
        each person with no manager could report to, worked out from the
        team records (P3 §1.3). A read: nothing is saved."""
        company = self.env.company
        Emp = self.env['hr.employee']
        ids = Emp.search([('company_id', '=', company.id)]).ids
        idset = set(ids)
        st = self._proj_base(company.id)
        parent = st['mgr']
        no_mgr = [i for i in ids if not (parent.get(i) and parent.get(i) in idset)]
        # team and title from the current versions, in one read
        Emp.flush_model(['current_version_id', 'job_title', 'name'])
        self.env['hr.version'].flush_model(['department_id', 'job_id', 'job_title'])
        info = {}
        if ids:
            self.env.cr.execute("""
                SELECT e.id, e.name, v.department_id, coalesce(v.job_title, ''), coalesce(j.name->>'en_US', '')
                  FROM hr_employee e LEFT JOIN hr_version v ON v.id = e.current_version_id
                  LEFT JOIN hr_job j ON j.id = v.job_id
                 WHERE e.id = ANY(%s)""", [ids])
            for i, name, dept, jt, jn in self.env.cr.fetchall():
                info[i] = {'name': name or '', 'dept': dept, 'title': jt or jn or ''}
        depts = {}
        for d in self.env['hr.department'].sudo().with_context(active_test=False).search(
                [('company_id', 'in', [company.id, False])]):
            m = d.manager_id
            depts[d.id] = {'name': d.name or '', 'parent': d.parent_id.id or False,
                           'mgr': m.id if (m and m.id in idset) else False}
        tops = [i for i in no_mgr if TOP_TITLE.search(info.get(i, {}).get('title') or '')]
        top = tops[0] if len(tops) == 1 else False
        changes, left_out = [], []
        vp = dict(parent)
        rules = Counter()
        for e in sorted(no_mgr, key=lambda x: info.get(x, {}).get('name', '')):
            if e == top:
                continue
            d = info.get(e, {}).get('dept')
            if not d or d not in depts:
                left_out.append({'employee_id': e, 'why': _("Not in any team, so nobody can be suggested.")})
                continue
            dep = depts[d]
            cand, why, rule = False, '', ''
            leads = dep['mgr'] == e
            if dep['mgr'] and not leads:
                cand, rule = dep['mgr'], 'team'
                why = _("Manages the %(t)s team", t=dep['name'])
            else:
                seen, p = {d}, dep['parent']
                while p and p in depts and p not in seen:
                    seen.add(p)
                    if depts[p]['mgr'] and depts[p]['mgr'] != e:
                        cand, rule = depts[p]['mgr'], 'parent'
                        why = _("Manages %(p)s, the team above %(t)s", p=depts[p]['name'], t=dep['name'])
                        break
                    p = depts[p]['parent']
            if not cand and leads:
                if top and top != e:
                    cand, rule = top, 'top'
                    why = _("Leads the %(t)s team; %(c)s is at the top of the company",
                            t=dep['name'], c=info.get(top, {}).get('name', ''))
                else:
                    left_out.append({'employee_id': e, 'why': _(
                        "Leads a team, but no one top person could be worked out")})
                    continue
            if not cand:
                left_out.append({'employee_id': e, 'why': _(
                    "Their team has no manager set, and no team above it has one")})
                continue
            if self._loop_in({e: cand}, parents=vp):
                left_out.append({'employee_id': e, 'why': _("That would put them inside their own team")})
                continue
            vp[e] = cand
            rules[rule] += 1
            changes.append({'employee_id': e, 'name': info.get(e, {}).get('name', ''),
                            'to_manager_id': cand, 'to_name': info.get(cand, {}).get('name', ''),
                            'why': why, 'rule': rule})
        for lo in left_out:
            lo['name'] = info.get(lo['employee_id'], {}).get('name', '')
        reasons = Counter(lo['why'] for lo in left_out)
        if top:
            top_line = _("%(p)s is at the top of the company (from their title).",
                         p=info.get(top, {}).get('name', ''))
        elif tops:
            top_line = _("No one top person could be worked out — %(n)s people have a top title.", n=len(tops))
        else:
            top_line = _("No one top person could be worked out — nobody has a title like Chief Executive "
                         "or General Director.")
        return {
            'changes': changes,
            'left_out': left_out,
            'summary': {
                'no_manager': len(no_mgr), 'placed': len(changes), 'left_out': len(left_out),
                'by_team': rules['team'], 'by_parent': rules['parent'], 'to_top': rules['top'],
                'top_id': top or False, 'top_line': top_line,
                'reasons': [{'why': w, 'n': n} for w, n in reasons.most_common()],
            },
        }

    @api.model
    def plan_use_suggestion(self):
        """"Use it": the suggestion goes into the caller's draft plan as one
        batch (nothing is live until the plan is published). A suggestion the
        plan no longer allows is skipped and counted."""
        def go():
            opened = self.plan_open()
            if opened.get('error'):
                raise _Refused(opened['error'])
            plan = self._plan_get(opened['plan_id'], edit=True)
            sug = self.suggest_chart()
            st = self._project(plan)
            added = skipped = 0
            batch = uuid.uuid4().hex[:12]
            seq = max(plan.change_ids.mapped('sequence') or [0])
            Change = self.env['pb.orgchart.plan.change']
            for s in sug['changes']:
                ch = {'kind': 'move', 'employee_id': s['employee_id'],
                      'to_manager_id': s['to_manager_id'], 'whole_team': True}
                try:
                    res = self._vapply(st, ch)
                except _Refused:
                    skipped += 1
                    continue
                seq += 10
                Change.create({'plan_id': plan.id, 'sequence': seq, 'batch': batch, 'kind': 'move',
                               'employee_id': s['employee_id'], 'to_manager_id': s['to_manager_id'],
                               'from_manager_id': res.get('from') or False, 'whole_team': True,
                               'label': res['label'], 'note': s['why']})
                added += 1
            if not added:
                raise _Refused(_("There was nothing to add — everyone the suggestion places is already "
                                 "placed in your plan."))
            out = self._plan_payload(plan)
            out.update(ok=True, added=added, skipped=skipped,
                       label=_("1 suggested change added to your plan") if added == 1 else
                       _("%(n)s suggested changes added to your plan", n=added))
            return out
        return self._plan_run(go)
