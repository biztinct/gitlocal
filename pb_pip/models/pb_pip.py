# -*- coding: utf-8 -*-
"""`pb.pip` — the PIP lens's only server surface.

The shape every cockpit in this product keeps: an `AbstractModel` facade,
`@api.model` reads, every independent probe inside its own `_safe()` so one
failing metric answers zero instead of taking the screen down,
`self.env.companies` scoping on every search, a row cap, and no sudo in a READ.

WHAT IS DIFFERENT HERE, and it is the point of the phase: the gate is this
module's OWN two groups and NOT the lifecycle tiers. `_can_read()` refuses
anybody else — including a lifecycle administrator, including somebody with
`base.group_system` who has not been given the group by name — and it refuses by
answering an EXPLAINED empty payload rather than by raising, so a user who
reaches this by typing a URL gets a sentence rather than a traceback and no data
whatsoever leaves the server.

THE QUESTION THIS BOARD ANSWERS: which plans are running, which are drifting,
and which one is waiting on somebody. So a row is a PLAN, the number beside it
is how much of it is left, and the three things after it are the three things
that say whether it is working — the objectives at risk, the check-ins actually
held, and whether the person has even seen it.
"""

import logging
from datetime import date

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError

from .pip_common import (
    CHECKIN_FREQ_LABEL, GROUP_HEAD, GROUP_USER, OBJECTIVE_STATE_LABEL,
    P_EMPLOYEE_VIEW, P_MANAGER_SEES_OWN, PIP_OPEN, PIP_STATE_LABEL,
    VERDICT_LABEL, flag, initials,
)

_logger = logging.getLogger(__name__)

BOARD_LIMIT = 300

#: A plan is "nearly done" inside this many days of its end date.
SOON_DAYS = 7

#: The refusal payload. One shape, used by every read, so a client that gets it
#: never has to guess which keys are missing.
def _refusal():
    return {
        'allowed': False,
        'can_write': False,
        'is_head': False,
        'kpis': {},
        'rows': [],
        'total': 0,
        'capped': False,
        'states': [],
        'owners': [],
        'companies': [],
        'templates': [],
        'employee_view': False,
        'manager_sees_own': False,
        'why': _("Improvement plans are looked after by a small group in HR. "
                 "This screen is not part of the general HR permissions, and "
                 "it is not part of being an administrator either — somebody "
                 "has to add you to it by name. Ask your HR lead if you "
                 "believe you should have it."),
    }


class PbPip(models.AbstractModel):
    _name = 'pb.pip'
    _description = 'Payobook Improvement Plan cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug('PIP metric failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        """THE gate. No lifecycle tier, no `_is_admin()` fallback.

        `_is_admin()` is deliberately absent. Every other facade in this
        product includes it, because on those screens an administrator seeing
        everything is convenient and harmless. Here it is neither: "I am a
        system administrator" is not a reason to know who is on an improvement
        plan, and the administrator who genuinely needs it is one row in a
        group away. `env.su` still passes, because that is code acting as the
        system rather than a person reading a screen.
        """
        user = self.env.user
        return bool(self.env.su
                    or user.has_group(GROUP_USER)
                    or user.has_group(GROUP_HEAD))

    @api.model
    def _can_write(self):
        return self._can_read()

    @api.model
    def _is_head(self):
        return bool(self.env.su or self.env.user.has_group(GROUP_HEAD))

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(_refusal()['why'])
        return True

    @api.model
    def _require_head(self):
        if not self._is_head():
            raise AccessError(_(
                "Changing who can see improvement plans is for the head of "
                "HR."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self, closed=False):
        """Every plan this reader may see. A REFUSAL PAYLOAD, never a raise.

        An access dialog on a screen somebody navigated to honestly is a dead
        end; a sentence that says who to ask is not. Nothing but the sentence
        crosses the wire when the answer is no.
        """
        if not self._can_read():
            return _refusal()
        Case = self.env['pb.pip.case']
        co_ids = self.env.companies.ids or [self.env.company.id]
        today = date.today()
        domain = [('company_id', 'in', co_ids)]
        domain += ([('state', 'not in', list(PIP_OPEN))] if closed
                   else [('state', 'in', list(PIP_OPEN))])
        cases = self._safe(
            lambda: Case.search(domain, order='end_date, id desc',
                                limit=BOARD_LIMIT),
            default=Case.browse())

        rows = []
        for case in cases:
            try:
                rows.append(self._row(case, today))
            except Exception:
                _logger.exception('PIP row for plan %s', case.id)

        kpis = {
            'open': len([r for r in rows if r['state'] in PIP_OPEN]),
            'coaching': len([r for r in rows
                             if r['state'] in ('requested', 'coaching')]),
            'running': len([r for r in rows if r['state'] == 'active']),
            'deciding': len([r for r in rows if r['state'] == 'evaluation']),
            'at_risk': len([r for r in rows if r['at_risk'] or r['drifting']]),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'is_head': self._is_head(),
            'closed_view': bool(closed),
            'kpis': kpis,
            'rows': rows,
            'total': len(rows),
            'capped': len(rows) >= BOARD_LIMIT,
            'states': _facet(rows, 'state_label'),
            'owners': _facet(rows, 'owner'),
            'companies': _facet(rows, 'company'),
            'templates': self._templates(),
            'employee_view': flag(self.env, P_EMPLOYEE_VIEW),
            'manager_sees_own': flag(self.env, P_MANAGER_SEES_OWN),
            'why': '',
        }

    @api.model
    def _templates(self):
        # `sudo()` on a CONFIGURATION table, read by the manager request dialog
        # as well as by the board. A template is "Delivery quality — 6 weeks":
        # it names no person and reveals nothing about anybody, and a manager
        # who cannot read the list cannot be shown what they are asking for.
        # The company filter is still applied by hand, because sudo skips the
        # rule that would have applied it.
        Template = self.env['pb.pip.template'].sudo()
        rows = self._safe(
            lambda: Template.search(
                ['|', ('company_id', '=', False),
                 ('company_id', 'in', self.env.companies.ids
                  or [self.env.company.id])], order='sequence, name'),
            default=Template.browse())
        return [{
            'id': t.id,
            'name': t.name or '',
            'weeks': t.default_weeks or 6,
            'freq': t.checkin_freq or 'weekly',
            'freq_label': CHECKIN_FREQ_LABEL.get(t.checkin_freq or 'weekly',
                                                 ''),
            'lines': [{'name': ln.name or '',
                       'description': ln.description or ''}
                      for ln in t.focus_line_ids],
        } for t in rows]

    @api.model
    def _emp(self, case):
        """The person on a plan, read as the system.

        NOT A HOLE IN THE GATE — the gate is the search above, and by the time
        anything reaches here the reader has already been proved entitled to
        this case. This is about a different mechanism entirely: reading ONE
        field of an `hr.employee` prefetches EVERY stored field of it, and this
        build's employee record carries about forty fields behind `groups=`
        (payroll country, insurance code, union fee, tham_gia_bhxh…). A reader
        who holds the improvement-plan group but not the payroll ones therefore
        gets an AccessError naming forty fields nobody asked for, on a screen
        that only ever wanted the person's name.

        The alternative — telling every HR lead who runs improvement plans that
        they must also hold the payroll groups — would hand out far more than
        it withholds.
        """
        return case.employee_id.sudo()

    @api.model
    def _row(self, case, today=None):
        today = today or date.today()
        emp = self._emp(case)
        end = case.end_date
        start = case.start_date
        left = (end - today).days if end else None
        span = ((end - start).days if (end and start) else 0) or 0
        gone = ((today - start).days if start else 0) or 0
        # A percentage nobody can misread: how much of the plan's time has
        # been used, clamped, and only when there is a plan to measure.
        elapsed = 0
        if span > 0:
            elapsed = max(0, min(100, int(round(gone * 100.0 / span))))
        planned = case.checkins_planned or 0
        held = case.checkins_done or 0
        # Adherence is measured against what should have happened BY NOW, not
        # against the whole plan — a plan in week one has held one of six and
        # is not 17% adherent, it is on track.
        due_by_now = self._safe(
            lambda: len(case.checkin_ids.filtered(
                lambda c: c.state != 'cancelled' and c.scheduled_date
                and c.scheduled_date <= today)), default=0)
        adherence = int(round(held * 100.0 / due_by_now)) if due_by_now else None
        return {
            'id': case.id,
            'employee_id': emp.id,
            'employee': emp.name or '—',
            'initials': initials(emp.name),
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '')
            or '',
            'dept': (emp.department_id.name if emp.department_id else '')
            or _('No team'),
            'company': (case.company_id.name if case.company_id else '')
            or _('Not set'),
            'manager': emp.parent_id.name if emp.parent_id else '',
            'requested_by': (case.requested_by_user_id.name
                             if case.requested_by_user_id else ''),
            'owner': (case.hr_owner_user_id.name
                      if case.hr_owner_user_id else _('Nobody yet')),
            'state': case.state,
            'state_label': PIP_STATE_LABEL.get(case.state, ''),
            'template': case.template_id.name if case.template_id else '',
            'reason': case.reason_text or '',
            'start_date': str(start) if start else '',
            'end_date': str(end) if end else '',
            'weeks': case.weeks or 0,
            'freq': case.checkin_freq or 'weekly',
            'freq_label': CHECKIN_FREQ_LABEL.get(case.checkin_freq or 'weekly',
                                                 ''),
            'days_left': left,
            'when': _when(left, case.state),
            'elapsed': elapsed,
            'objectives': case.objective_count or 0,
            'at_risk': case.at_risk_count or 0,
            'on_track': case.on_track_count or 0,
            'checkins_planned': planned,
            'checkins_done': held,
            'checkins_due': due_by_now,
            'adherence': adherence,
            'ack': bool(case.employee_ack),
            'ack_at': str(case.ack_at or ''),
            'eval_sent': bool(case.eval_request_id),
            'eval_in': bool(case.eval_request_id
                            and case.eval_request_id.state == 'submitted'),
            'verdict': case.verdict or '',
            'verdict_label': VERDICT_LABEL.get(case.verdict, '')
            if case.verdict else '',
            'letter_id': case.letter_id.id if case.letter_id else 0,
            'exit_case_id': case.exit_case_id.id if case.exit_case_id else 0,
            'soon': bool(left is not None and 0 <= left <= SOON_DAYS),
            'overdue': bool(left is not None and left < 0
                            and case.state == 'active'),
            # "Drifting" is the one derived word on this board, and it is the
            # one an HR lead actually acts on: a running plan where more than
            # a third of the conversations that should have happened have not.
            'drifting': bool(case.state == 'active' and due_by_now >= 2
                             and adherence is not None and adherence < 67),
        }

    # ------------------------------------------------------------ one plan
    @api.model
    def get_case(self, case_id):
        """One plan, whole — the drawer behind a row."""
        self._require_read()
        case = self.env['pb.pip.case'].browse(int(case_id)).exists()
        if not case:
            raise UserError(_("That plan could not be found."))
        checkins = self._safe(
            lambda: case.checkin_ids.sorted(
                key=lambda c: (c.scheduled_date or date.max, c.id)),
            default=self.env['pb.employee.checkin'].browse())
        return {
            'row': self._row(case),
            'coaching': str(case.coaching_html or ''),
            'coaching_start': str(case.coaching_start or ''),
            'outcome_note': case.outcome_note or '',
            'final_rating': case.final_rating or 0,
            'objectives': [{
                'id': o.id,
                'name': o.name or '',
                'metric': o.metric or '',
                'target': o.target or '',
                'weight': o.weight or 1,
                'status': o.status,
                'status_label': OBJECTIVE_STATE_LABEL.get(o.status, ''),
                'notes': o.notes or '',
            } for o in case.objective_ids],
            'checkins': [{
                'id': c.id,
                'name': c.name or '',
                'date': str(c.scheduled_date) if c.scheduled_date else '',
                'state': c.state,
                'notes': c.notes or '',
                'red': c.red_flag,
                'red_note': c.red_flag_note or '',
                'owner': c.owner_user_id.name if c.owner_user_id else '',
            } for c in checkins],
            'evaluation': self._safe(lambda: case.evaluation_answers(),
                                     default={'answered': False, 'when': '',
                                              'objectives': [], 'notes': []}),
            'eval_link': self._safe(
                lambda: (case.eval_request_id._token_url()
                         if case.eval_request_id
                         and case.eval_request_id.state != 'submitted'
                         else ''), default=''),
            'blockers': self._safe(lambda: case._start_blockers(), default=[]),
        }

    # =====================================================================
    #  WRITES. Every one goes through the model that owns the fact.
    # =====================================================================
    @api.model
    def take_up(self, case_id, note=None):
        self._require_read()
        return self._case(case_id).action_take_up(note=note)

    @api.model
    def save_coaching(self, case_id, html):
        self._require_read()
        return self._case(case_id).action_save_coaching(html)

    @api.model
    def close_at_coaching(self, case_id, note=None):
        self._require_read()
        return self._case(case_id).action_close_at_coaching(note=note)

    @api.model
    def save_plan_setup(self, case_id, weeks=None, freq=None, owner_id=None):
        """The three things about a plan that can be set before it starts."""
        self._require_read()
        case = self._case(case_id)
        case._require_hr()
        if case.state not in ('requested', 'coaching'):
            raise UserError(_(
                "The dates are fixed once a plan is running — everybody has "
                "already been told them."))
        vals = {}
        if weeks not in (None, '', False):
            try:
                vals['weeks'] = max(1, min(26, int(weeks)))
            except (TypeError, ValueError):
                pass
        if freq in ('weekly', 'biweekly'):
            vals['checkin_freq'] = freq
        if owner_id not in (None, '', False):
            try:
                vals['hr_owner_user_id'] = int(owner_id)
            except (TypeError, ValueError):
                pass
        if vals:
            case.sudo().write(vals)
        return True

    @api.model
    def add_objective(self, case_id, name, metric=None, target=None,
                      weight=1):
        self._require_read()
        case = self._case(case_id)
        case._require_hr()
        if not (name or '').strip():
            raise UserError(_("Give the objective a name first."))
        objective = self.env['pb.pip.objective'].sudo().create({
            'case_id': case.id,
            'name': name.strip()[:200],
            'metric': (metric or '').strip()[:400] or False,
            'target': (target or '').strip()[:120] or False,
            'weight': max(1, int(weight or 1)),
            'sequence': 10 * (len(case.objective_ids) + 1),
        })
        case.message_post(body=_("Objective added: %s.", objective.name))
        return {'id': objective.id}

    @api.model
    def remove_objective(self, objective_id):
        self._require_read()
        row = self.env['pb.pip.objective'].browse(int(objective_id)).exists()
        if not row:
            raise UserError(_("That objective could not be found."))
        row.case_id._require_hr()
        if row.case_id.state not in ('requested', 'coaching'):
            raise UserError(_(
                "An objective cannot be taken off a plan that is already "
                "running — the person has been told what it says. Mark it "
                "\"met\" or \"not met\" instead."))
        name = row.name
        row.case_id.message_post(body=_("Objective removed: %s.", name))
        row.sudo().unlink()
        return True

    @api.model
    def set_objective_status(self, objective_id, status):
        self._require_read()
        row = self.env['pb.pip.objective'].browse(int(objective_id)).exists()
        if not row:
            raise UserError(_("That objective could not be found."))
        row.case_id._require_hr()
        return row.action_set_status(status)

    @api.model
    def start_preview(self, case_id):
        self._require_read()
        return self._case(case_id).start_preview()

    @api.model
    def start_plan(self, case_id):
        self._require_read()
        return self._case(case_id).action_start_plan()

    @api.model
    def evaluate(self, case_id):
        self._require_read()
        return self._case(case_id).action_evaluate()

    @api.model
    def verdict_preview(self, case_id, verdict):
        self._require_read()
        return self._case(case_id).verdict_preview(verdict)

    @api.model
    def save_verdict(self, case_id, verdict, rating=None, note=None,
                     objective_states=None):
        self._require_read()
        return self._case(case_id).action_verdict(
            verdict, rating=rating, note=note,
            objective_states=objective_states)

    @api.model
    def start_exit(self, case_id):
        self._require_read()
        return self._case(case_id).action_start_exit()

    @api.model
    def settle_checkin(self, checkin_id, notes=None, red_flag=None,
                       red_note=None):
        self._require_read()
        row = self.env['pb.employee.checkin'].sudo().browse(
            int(checkin_id)).exists()
        if not row or not row.pip_case_id:
            raise UserError(_("That check-in could not be found."))
        row.pip_case_id._require_hr()
        return row.action_done(notes=notes, red_flag=red_flag,
                               red_flag_note=red_note)

    @api.model
    def run_automation(self):
        self._require_read()
        return self.env['pb.journey.case'].run_pip_automation()

    # ------------------------------------------------------- the two switches
    @api.model
    def set_switch(self, name, value):
        """The head of HR turns the two visibility switches on and off.

        Only these two, by name, and only from this method: a facade that will
        write any config parameter it is handed is a facade that will write
        `web.base.url` when somebody types it.
        """
        self._require_head()
        allowed = {'employee_view': P_EMPLOYEE_VIEW,
                   'manager_sees_own': P_MANAGER_SEES_OWN}
        key = allowed.get(name)
        if not key:
            raise UserError(_("That is not one of the two settings."))
        raw = '1' if value else '0'
        self.env['ir.config_parameter'].sudo().set_param(key, raw)
        _logger.info('pb_pip: %s set to %s by %s', key, raw, self.env.user.id)
        return {'name': name, 'value': bool(value)}

    # ------------------------------------------------- the manager's one door
    @api.model
    def request_options(self):
        """What the "ask HR" dialog needs, and whether this person may use it.

        A FRIENDLY PAYLOAD FOR SOMEBODY WHO MANAGES NOBODY, never an error.
        The ⌘K row that opens this dialog is offered to every internal user,
        because "manages at least one person" is not a group and a palette gate
        is a group list — so the sentence that explains it lives here, where it
        can be true.
        """
        Emp = self.env['hr.employee']
        me = Emp.sudo().search([('user_id', '=', self.env.uid)], limit=1)
        team = Emp.sudo().search(
            [('parent_id', '=', me.id), ('active', '=', True)],
            order='name') if me else Emp.browse()
        return {
            'allowed': bool(team),
            'why': '' if team else _(
                "This is for a manager who wants HR to look at how somebody "
                "in their team is doing. Nobody reports to you on the "
                "records, so there is nothing to ask about here. If that is "
                "wrong, ask HR to put your team under you."),
            'team': [{
                'id': e.id,
                'name': e.name or '',
                'job': e.job_title or (e.job_id.name if e.job_id else '') or '',
                'avatar': '/web/image/hr.employee/%s/avatar_128' % e.id,
            } for e in team],
            'templates': [{'id': t['id'], 'name': t['name'],
                           'weeks': t['weeks'], 'lines': t['lines']}
                          for t in self._safe(lambda: self._templates(),
                                              default=[])],
        }

    @api.model
    def raise_request(self, employee_id, reason, template_id=None):
        """A manager asks HR to look at somebody. The ONLY write they can make.

        Re-derived rather than trusted: the employee has to be somebody who
        actually reports to the caller, checked here and not in the browser,
        because a crafted id would otherwise put a request on a colleague's
        record.
        """
        Emp = self.env['hr.employee']
        me = Emp.sudo().search([('user_id', '=', self.env.uid)], limit=1)
        target = Emp.sudo().browse(int(employee_id)).exists()
        mine = bool(me and target and target.parent_id
                    and target.parent_id.id == me.id)
        if not (mine or self._can_read()):
            raise AccessError(_(
                "You can ask HR to look at somebody who reports to you. This "
                "person does not."))
        if not (reason or '').strip():
            raise UserError(_(
                "Write a few lines about what you have seen. HR reads this "
                "before anything else happens, and \"performance\" on its own "
                "tells them nothing."))
        # Asked BEFORE, because `request_for` is idempotent and hands back the
        # plan that was already there — and "we already have this in hand" is a
        # completely different thing to say to a manager than "thank you, HR
        # will pick it up".
        already = self.env['pb.pip.case'].sudo().search_count([
            ('employee_id', '=', target.id), ('state', 'in', list(PIP_OPEN))])
        case = self.env['pb.pip.case'].request_for(
            target, reason=reason, template=template_id)
        return {'id': case.id,
                'state': case.state,
                'existing': bool(already),
                'label': PIP_STATE_LABEL.get(case.state, '')}

    @api.model
    def my_requests(self):
        """The requests this caller raised, and only those.

        Read through the ORM WITHOUT sudo on purpose: the record rule is what
        decides, so if `pb_pip.manager_sees_own` is off this answers an empty
        list through the same mechanism a direct read would — one rule, one
        answer, no second copy of the logic to keep in step.
        """
        Case = self.env['pb.pip.case']
        try:
            cases = Case.search(
                [('requested_by_user_id', '=', self.env.uid)],
                order='id desc', limit=20)
        except AccessError:
            cases = Case.browse()
        return [{
            'id': c.id,
            # `.sudo()` for the NAME only — see `_emp` for why one field read on
            # hr.employee is never one field read.
            'employee': c.employee_id.sudo().name or '',
            'state': c.state,
            'state_label': PIP_STATE_LABEL.get(c.state, ''),
            'when': str(c.create_date.date()) if c.create_date else '',
        } for c in cases]

    # ------------------------------------------------------------ the doors
    @api.model
    def open_case_action(self, case_id):
        self._require_read()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.pip.case',
            'res_id': int(case_id),
            'view_mode': 'form',
        }

    @api.model
    def open_letter_action(self, letter_id):
        self._require_read()
        letter = self.env['pb.hr.letter'].browse(int(letter_id)).exists()
        if not letter:
            raise UserError(_("That letter could not be found."))
        return letter.action_open_pdf()

    @api.model
    def open_employee_action(self, employee_id):
        self._require_read()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'res_id': int(employee_id),
            'view_mode': 'form',
        }

    # -------------------------------------------------------------- plumbing
    @api.model
    def _case(self, case_id):
        case = self.env['pb.pip.case'].browse(int(case_id)).exists()
        if not case:
            raise UserError(_("That plan could not be found."))
        return case


def _when(days, state):
    """"3 weeks left" / "ends today" — never a bare number."""
    if state in ('passed', 'failed', 'terminated'):
        return _('closed')
    if state in ('requested', 'coaching'):
        return _('not started yet')
    if days is None:
        return _('no dates yet')
    if days == 0:
        return _('ends today')
    if days == 1:
        return _('ends tomorrow')
    if days > 14:
        return _('%s weeks left', int(round(days / 7.0)))
    if days > 1:
        return _('%s days left', days)
    if days == -1:
        return _('ended yesterday')
    return _('ended %s days ago', -days)


def _facet(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key) or ''
        if value:
            counts[value] = counts.get(value, 0) + 1
    return [{'id': k, 'label': k, 'count': v}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
