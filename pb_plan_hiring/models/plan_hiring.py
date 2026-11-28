# -*- coding: utf-8 -*-
"""An approved Decision Room plan → DRAFT hiring requests (S8-C).

THE LINES come from the approved plan's frozen levers, `state.moves =
[{team, role, n, month}]` (`decision_engine.js`): team `t<department id>`
(the room rolls teams up to their root department) or `other_teams`; role
`r<job id>`, `r0` / `other_<n>` ("other roles") or empty (the whole team);
`n` people (negative = leavers); `month` 1–12 = January–December.

Moves with the same team, role and month are one line (their people added),
keyed `team|role|month`. THE KEY is what makes a second press harmless:
`pb.hiring.requisition.(pb_plan_id, pb_plan_line_key)` is unique, and a line
that has a request (in any state, closed included) is never made again.

A request is made exactly the way the Hiring board's "New request" makes one
(`pb.hiring.act('create')`: the request is created AS THE PERSON, so
`_require_raise` applies, then put in "writing"); it is never sent in.
"""
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class HiringRequisitionPlan(models.Model):
    _inherit = 'pb.hiring.requisition'

    pb_plan_id = fields.Many2one(
        'pb.decision.plan', string='From the plan', index=True,
        ondelete='set null', copy=False, readonly=True,
        help='The approved Decision Room plan this request was made from.')
    pb_plan_line_key = fields.Char(string='Plan line', copy=False,
                                   readonly=True)

    _pb_plan_line_unique = models.Constraint(
        'UNIQUE(pb_plan_id, pb_plan_line_key)',
        'This line of the plan already has a hiring request.')


class HiringBoardPlan(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _row(self, req):
        row = super()._row(req)
        plan = req.sudo().pb_plan_id
        row['pb_plan'] = {'id': plan.id, 'name': plan.name or ''} if plan else None
        return row


class DecisionPlanHiring(models.Model):
    _inherit = 'pb.decision.plan'

    pb_requisition_ids = fields.One2many(
        'pb.hiring.requisition', 'pb_plan_id', string='Hiring requests')

    # -------------------------------------------------------------- lines
    def _pb_plan_year_start(self):
        """The first month the plan's month 1 can be: January of the year the
        plan was approved; a month already past then is next year's."""
        self.ensure_one()
        state = self.state or {}
        year = _as_int(state.get('year')) if isinstance(state, dict) else 0
        decided = fields.Datetime.to_datetime(self.decided_at) if self.decided_at \
            else fields.Datetime.now()
        return year or decided.year, decided.date().replace(day=1)

    def _pb_wanted_by(self, month):
        year, floor = self._pb_plan_year_start()
        month = min(12, max(1, _as_int(month, 1)))
        wanted = date(year, month, 1)
        if not _as_int((self.state or {}).get('year')) and wanted < floor:
            wanted = date(year + 1, month, 1)
        return wanted

    def _pb_raw_lines(self):
        self.ensure_one()
        moves = (self.state or {}).get('moves') if isinstance(self.state, dict) else []
        lines = {}
        for move in moves or []:
            if not isinstance(move, dict):
                continue
            n = _as_int(round(float(move.get('n') or 0)))
            if not n:
                continue
            team = str(move.get('team') or '')
            role = str(move.get('role') or '')
            month = min(12, max(1, _as_int(move.get('month'), 1)))
            key = '%s|%s|%s' % (team, role, month)
            hit = lines.setdefault(key, {'key': key, 'team': team, 'role': role,
                                         'month': month, 'n': 0})
            hit['n'] += n
        return list(lines.values())

    def _pb_line_rows(self):
        """Every line of the plan, said in plain words, with what can be done."""
        self.ensure_one()
        plan = self.sudo()
        Dept = self.env['hr.department'].sudo()
        Job = self.env['hr.job'].sudo()
        companies = plan.company_ids | plan.company_id
        made = {r.pb_plan_line_key: r for r in plan.with_context(
            active_test=False).pb_requisition_ids}
        probe_pause = 'pb_hiring_paused' in Dept._fields
        rows = []
        for raw in sorted(self._pb_raw_lines(),
                          key=lambda r: (r['month'], r['team'], r['role'])):
            wanted_by = self._pb_wanted_by(raw['month'])
            row = dict(raw, team_name='', role_name='', title='', needs_title=False,
                       can_make=False, why='', request=None, department_id=0,
                       job_id=0, wanted_by=str(wanted_by),
                       month_name=format_date(self.env, wanted_by,
                                              date_format='MMMM y'))
            dept = Dept.browse(_as_int(raw['team'][1:])) if raw['team'].startswith('t') \
                else Dept.browse()
            dept = dept.exists()
            if dept and dept.company_id in companies:
                row['team_name'] = dept.display_name
                row['department_id'] = dept.id
            role = raw['role']
            job = Job.browse(_as_int(role[1:])).exists() \
                if role.startswith('r') and _as_int(role[1:]) else Job.browse()
            if job:
                row['role_name'] = row['title'] = job.name or ''
                row['job_id'] = job.id
                # the job's own team when it sits under the plan's team
                if job.department_id and dept and job.department_id.id in Dept.search(
                        [('id', 'child_of', dept.id)]).ids:
                    row['department_id'] = job.department_id.id
                    row['team_name'] = job.department_id.display_name
            elif role:
                row['role_name'] = _("Other roles")
                row['needs_title'] = True
            else:
                row['role_name'] = _("Anyone in the team")
                row['needs_title'] = True
            req = made.get(raw['key'])
            if req:
                row['request'] = {
                    'id': req.id, 'name': req.display_name,
                    'state': dict(req._fields['request_state'].selection).get(
                        req.request_state, '') if 'request_state' in req._fields else '',
                }
                row['why'] = _("Has a hiring request")
            elif raw['n'] < 0:
                row['why'] = _("People leaving are not handled here")
            elif raw['team'] == 'other_teams' or not row['department_id']:
                row['why'] = _("This line covers several small teams. Make the request on the Hiring board and choose the team there.")
            elif probe_pause and Dept.browse(row['department_id']).pb_hiring_paused:
                src = Dept.browse(row['department_id'])._pb_pause_source()
                reason = src.pb_hiring_pause_reason if src else ''
                row['why'] = _("Hiring is paused for this team: %s", reason) if reason \
                    else _("Hiring is paused for this team.")
            else:
                row['can_make'] = True
            rows.append(row)
        return rows

    def _pb_hiring_summary(self):
        self.ensure_one()
        rows = self._pb_line_rows()
        hires = [r for r in rows if r['n'] > 0]
        return {'lines': len(hires),
                'made': sum(1 for r in hires if r['request'])}

    # ------------------------------------------------------------- screens
    @api.model
    def _pb_plan_for(self, plan_id):
        self.env['pb.decision.room']._require_read()
        plan = self.browse(_as_int(plan_id)).exists()
        if not plan:
            raise UserError(_("That plan is no longer there."))
        plan.check_access('read')
        return plan

    @api.model
    def pb_get_hiring_lines(self, plan_id):
        plan = self._pb_plan_for(plan_id)
        Req = self.env['pb.hiring.requisition']
        can_raise = Req._can_raise() if hasattr(Req, '_can_raise') else True
        return {
            'plan': {'id': plan.id, 'name': plan.name, 'approved': plan.status == 'approved'},
            'lines': plan._pb_line_rows() if plan.status == 'approved' else [],
            'can_raise': bool(can_raise),
            'cannot_raise': '' if can_raise else _(
                "Hiring requests are made by whoever runs that part of the "
                "business, or by the hiring team. Ask one of them to press this."),
        }

    @api.model
    def pb_make_hiring_requests(self, plan_id, picks):
        """`picks` = [{key, title?}] → one DRAFT hiring request per line.

        A line already holding a request is skipped (never doubled), and so is
        any line the plan cannot make (see `_pb_line_rows`)."""
        plan = self._pb_plan_for(plan_id)
        if plan.status != 'approved':
            raise UserError(_(
                "Only an approved plan makes hiring requests. Approve it first."))
        Req = self.env['pb.hiring.requisition']
        if hasattr(Req, '_require_raise'):
            Req._require_raise()
        wanted = {}
        for pick in picks or []:
            if isinstance(pick, dict) and pick.get('key'):
                wanted[str(pick['key'])] = (pick.get('title') or '').strip()
        rows = {r['key']: r for r in plan._pb_line_rows()}
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        made, skipped = [], []
        for key, title in wanted.items():
            row = rows.get(key)
            if not row or not row['can_make'] or row['request']:
                skipped.append(key)
                continue
            title = title or row['title']
            if not title:
                raise UserError(_(
                    "Give a job title for %(team)s, %(month)s.",
                    team=row['team_name'], month=row['month_name']))
            dept = self.env['hr.department'].sudo().browse(row['department_id'])
            vals = {
                'title': title[:200],
                'role_type': 'new_role',
                'department_id': dept.id,
                'company_id': dept.company_id.id,
                'currency_id': dept.company_id.currency_id.id,
                'headcount': max(1, row['n']),
                'requested_by_id': employee.id or False,
                'target_start_date': row['wanted_by'],
                'remarks': _("From the approved plan \"%s\".", plan.name),
                'pb_plan_id': plan.id,
                'pb_plan_line_key': key,
            }
            if row['job_id']:
                vals['job_id'] = row['job_id']
            # As the person (the request's own gate), inside a savepoint so a
            # refused line leaves nothing behind.
            with self.env.cr.savepoint():
                req = Req.create(vals)
                req._request_write('writing')
            made.append(req.id)
        result = self.pb_get_hiring_lines(plan.id)
        result['made'] = len(made)
        result['skipped'] = len(skipped)
        return result

    @api.model
    def pb_open_request(self, requisition_id):
        """The Hiring board, opened on that request's role."""
        req = self.env['pb.hiring.requisition'].browse(_as_int(requisition_id)).exists()
        if not req:
            raise UserError(_("That hiring request is no longer there."))
        try:
            req.check_access('read')
        except AccessError:
            raise AccessError(_("That hiring request is not open to you."))
        action = self.env['ir.actions.actions']._for_xml_id(
            'pb_hiring.action_pb_hiring_board')
        action['context'] = {'pb_role_id': req.id}
        return action


class DecisionRoomPlanHiring(models.AbstractModel):
    _inherit = 'pb.decision.room'

    @api.model
    def _plan_dict(self, plan):
        out = super()._plan_dict(plan)
        if plan.status == 'approved':
            try:
                out['pb_hiring'] = plan._pb_hiring_summary()
            except Exception:  # noqa: BLE001 - a summary never breaks the dock
                out['pb_hiring'] = None
        return out
