# -*- coding: utf-8 -*-
"""ORG CHART P3 — planning mode (ORGCHART_P3.md §1.1, ledger D7).

A plan is a record, not a client trick: a stack of changes (`change_ids`)
that is drawn as a projection over the live chart, sent for approval through
the approval engine (process key ``orgplan``), and applied on its effective
date once — and only once — it is approved.

Rules kept here:
* **Nothing is written to an employee until the plan is approved.** `_apply`
  refuses any plan that is not in the ``approved`` state, whoever calls it.
* **Applying uses P2's own write helpers** (`_do_move`, `_do_swap`, ...), so
  `parent_id` is only ever written through `_set_managers` (coach and the two
  approvers keep their value, ledger G16) and loops are judged by `_loop_in`.
* **Idempotent per change**: each change carries `applied`; the daily job
  only retries what has not been applied, and never raises out (a failing
  change records a sentence in `error` and the plan stays ``approved``).
* The changes are written AS THE PERSON WHO PLANNED THEM (`with_user` +
  `sudo`), so the History tab names them; the approver is on the trail.
"""
import json
import logging

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_date

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

from .pb_orgchart_write import _Refused

_logger = logging.getLogger(__name__)

PROCESS_KEY = 'orgplan'
#: The responsibility the default route asks. The approval catalogue has no
#: "people" responsibility; the HR lifecycle team ("joining, contracts,
#: extensions and leaving") is the one that already decides contract
#: extensions, so a reorganisation goes to the same people (ledger D7).
ROLE_KEY = 'lifecycle'

register_chain(
    'pb.orgchart.plan', PROCESS_KEY,
    submit_state='pending',
    driven=('approved',),
    date_field='effective_date',
)

STATES = [
    ('draft', 'Being planned'),
    ('pending', 'Waiting for approval'),
    ('approved', 'Approved'),
    ('refused', 'Turned down'),
    ('applied', 'Live'),
    ('discarded', 'Discarded'),
]

KINDS = [
    ('move', 'Move'),
    ('dotted', 'Dotted line'),
    ('unassign', 'Remove from team'),
    ('swap', 'Swap places'),
    ('new_role', 'New open role'),
    ('move_role', 'Move an open role'),
    ('fill_role', 'Fill an open role'),
    ('close_role', 'Close an open role'),
]


def state_label(env, state):
    """The plan's status in plain words, translated."""
    return {
        'draft': env._("Being planned"),
        'pending': env._("Waiting for approval"),
        'approved': env._("Approved"),
        'refused': env._("Turned down"),
        'applied': env._("Live"),
        'discarded': env._("Discarded"),
    }.get(state, state or '')


class PbOrgChartPlan(models.Model):
    _name = 'pb.orgchart.plan'
    _description = 'Org chart plan'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'biz.approval.chain.mixin']
    _order = 'id desc'

    _approval_process_key = PROCESS_KEY
    _approval_transitions = {
        ('draft', 'pending'): None,
        ('pending', 'approved'): None,
        ('pending', 'refused'): None,
        ('draft', 'discarded'): None,
    }
    _approval_dead_states = ('refused', 'discarded')

    name = fields.Char(
        string="Plan", required=True, tracking=True,
        default=lambda self: _("Org chart changes"),
        help="A short name for the plan, for example \"Q1 restructure of the "
             "Southern field team\".")
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, index=True,
        default=lambda self: self.env.company)
    user_id = fields.Many2one(
        'res.users', string="Planned by", required=True, index=True,
        default=lambda self: self.env.user, ondelete='restrict')
    state = fields.Selection(
        STATES, string="Status", default='draft', required=True, index=True,
        tracking=True, copy=False)
    effective_date = fields.Date(
        string="Goes live on", required=True, tracking=True,
        default=fields.Date.context_today,
        help="The day the changes are made on the employee records, once the "
             "plan is approved.")
    note = fields.Text(string="Message to the approver")
    change_ids = fields.One2many('pb.orgchart.plan.change', 'plan_id', string="Changes")
    change_count = fields.Integer(string="Changes", compute='_compute_change_count')
    applied_at = fields.Datetime(string="Made live at", readonly=True, copy=False)
    applied_by = fields.Many2one('res.users', string="Made live by", readonly=True, copy=False)
    apply_error = fields.Text(string="Changes that could not be made", readonly=True, copy=False)

    @api.depends('change_ids')
    def _compute_change_count(self):
        for rec in self:
            rec.change_count = len(rec.change_ids)

    # ================================================================ rights
    def _approval_can(self, from_state, to_state):
        """Sending in and discarding: the person who planned it (or an HR
        manager / administrator), and only with HR rights. Approving and
        turning down go through the engine's own screens; without a published
        route nobody but the system may do either."""
        self.ensure_one()
        if (from_state, to_state) in (('draft', 'pending'), ('draft', 'discarded')):
            if self.env.su:
                return True
            user = self.env.user
            if not self.env['pb.orgchart']._may_write():
                return False
            return bool(self.user_id == user or user._is_admin()
                        or user.has_group('hr.group_hr_manager'))
        if to_state in ('approved', 'refused') and not self._engine_managed():
            return bool(self.env.su)
        return super()._approval_can(from_state, to_state)

    def _chain_engine_write(self, state):
        """The route's own status moves (sent in, approved, turned down) are
        written as superuser: the approver may hold no HR group and only
        read rights on the plan (a seat is a read, ledger AM60). The engine
        has already decided the move may happen; `sudo()` keeps the user as
        the author of the tracking line."""
        return super(PbOrgChartPlan, self.sudo())._chain_engine_write(state)

    # ============================================================ the chain
    def _chain_title(self):
        self.ensure_one()
        n = len(self.change_ids)
        return (_("Org chart change: %(name)s (1 change)", name=self.name)
                if n == 1 else
                _("Org chart change: %(name)s (%(n)s changes)", name=self.name, n=n))

    def _plan_facts(self):
        self.ensure_one()
        people = set()
        crosses = False
        for ch in self.sudo().change_ids:
            if ch.employee_id:
                people.add(ch.employee_id.id)
            if ch.kind == 'move' and ch.employee_id and ch.to_manager_id \
                    and ch.employee_id.department_id != ch.to_manager_id.department_id:
                crosses = True
        return {
            'changes': len(self.change_ids),
            'people': len(people),
            'new_roles': len(self.change_ids.filtered(lambda c: c.kind == 'new_role')),
            'crosses_teams': crosses,
        }

    def _chain_facts(self):
        self.ensure_one()
        f = self._plan_facts()
        return {
            'changes': {'value': f['changes'], 'unit': _('changes')},
            'people': {'value': f['people'], 'unit': _('people')},
            'new_roles': {'value': f['new_roles'], 'unit': _('roles')},
            'crosses_teams': {'value': f['crosses_teams'], 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'changes': {'type': 'int', 'label': _('How many changes')},
            'people': {'type': 'int', 'label': _('How many people move or change')},
            'new_roles': {'type': 'int', 'label': _('New open roles')},
            'crosses_teams': {'type': 'bool', 'label': _('Someone moves to a manager in another team')},
        }

    def _chain_revision_values(self):
        """What the approver signs for: every change and the day it goes
        live. A change added after it was sent in is a different plan."""
        self.ensure_one()
        return {
            'company': self.company_id.id,
            'date': str(self.effective_date or ''),
            'changes': [[c.kind, c.employee_id.id, c.to_manager_id.id, c.job_id.id,
                         c.title or '', bool(c.whole_team), c.reason or '']
                        for c in self.sudo().change_ids.sorted('sequence')],
        }

    def _approval_card_count(self, request):
        self.ensure_one()
        n = len(self.change_ids)
        return _("1 change") if n == 1 else _("%(n)s changes", n=n)

    def _approval_detail(self, request):
        """One row per change, in plain words, for the request drawer."""
        self.ensure_one()
        plan = self.sudo()
        rows = [{'head': c.label or '', 'sub': c.note or '', 'cells': [], 'tone': ''}
                for c in plan.change_ids.sorted('sequence')]
        chips = [
            {'label': _('Goes live on'),
             'value': format_date(self.env, plan.effective_date) if plan.effective_date else ''},
            {'label': _('Planned by'), 'value': plan.user_id.name or ''},
        ]
        return {'title': _('The changes'), 'columns': [], 'rows': rows,
                'chips': chips, 'note': (plan.note or '')[:240]}

    # ------------------------------------------------------------- the seed
    @api.model
    def _seed_independent(self, company):
        """Follow the company's own choice about the independence rule.

        The rule ("whoever sent it in never decides it") is on for a new
        route — except where the business has switched it off on its other
        people routes (rize did, for its one-person account: every request
        landed on a seat only the sender held). The contract-extension route
        is the nearest relative of this one, so its published setting is
        copied; with none, the rule stays on."""
        try:
            process = self.env['biz.approval.process']._by_key('extension')
            if not process:
                return True
            wf = self.env['biz.approval.workflow'].sudo().search(
                [('company_id', '=', company.id), ('process_id', '=', process.id)], limit=1)
            ver = wf.version_ids.filtered(lambda v: v.status == 'published')[:1]
            if not ver:
                return True
            d = ver.definition or {}
            if isinstance(d, str):
                d = json.loads(d)
            return bool(((d or {}).get('safeguards') or {}).get('independent', True))
        except Exception:   # noqa: BLE001 — a seed never fails on a guess
            _logger.debug("pb_orgchart: independence of %s unknown", company.name, exc_info=True)
            return True

    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, ROLE_KEY, 'hr.group_hr_manager')
        return Seed.lay(
            company, PROCESS_KEY, 'Org chart changes',
            route(role_step(_('HR team'), ROLE_KEY),
                  independent=self._seed_independent(company)),
            binding_note='The route every org chart plan follows unless a part '
                         'of the business is given its own.',
            model_name='pb.orgchart.plan',
            role_keys=(ROLE_KEY,),
            reason='Set up when org chart planning was switched on')

    # ============================================================== actions
    def action_submit(self, note=None):
        """Send the plan to the HR team: the engine opens the request and the
        people asked get a to-do."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("This plan has already been sent."))
        if not self.change_ids:
            raise UserError(_("Add at least one change before sending the plan."))
        if not self._engine_managed():
            try:
                with self.env.cr.savepoint():
                    self.sudo()._approval_seed_default(self.company_id)
            except Exception:   # noqa: BLE001
                _logger.exception("pb_orgchart: the plan route could not be laid for %s",
                                  self.company_id.name)
            if not self._engine_managed():
                raise UserError(_(
                    "Approvals for org chart changes are not set up for %(c)s yet. "
                    "Ask whoever looks after approvals to set them up.", c=self.company_id.name))
        self._advance_state('pending', note=note)
        self.invalidate_recordset(['state', 'approval_request_id', 'approval_state'])
        if self.state == 'pending':
            self.sudo().message_post(body=_("Sent to the HR team for approval."))
            self._ask_approvers()
        return True

    def _ask_approvers(self):
        """A to-do for each person the live step asks (the precedent's way)."""
        self.ensure_one()
        try:
            request = self.approval_request_id
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1] if request else None
            users = step.sudo().seat_ids.mapped('acting_user_id') if step else self.env['res.users']
            for user in users.filtered(lambda u: u.active and not u.share):
                self.sudo().activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_todo',
                    summary=_("Approve the org chart plan: %(n)s", n=self.name),
                    note=_("%(who)s planned %(n)s. It goes live on %(d)s once approved.",
                           who=self.user_id.name, n=self._chain_title(),
                           d=format_date(self.env, self.effective_date)),
                    user_id=user.id, date_deadline=self.effective_date)
        except Exception:   # noqa: BLE001 — a missing to-do never blocks sending
            _logger.exception("pb_orgchart: could not raise the to-do for plan %s", self.id)

    def action_discard(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only a plan that has not been sent can be discarded."))
        self._advance_state('discarded')
        return True

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state in ('approved', 'refused'):
            try:
                self.sudo().activity_unlink(['mail.mail_activity_data_todo'])
            except Exception:   # noqa: BLE001
                _logger.debug("pb_orgchart: to-dos of plan %s kept", self.id, exc_info=True)
        if to_state == 'approved':
            today = fields.Date.context_today(self)
            if self.effective_date and self.effective_date <= today:
                self._apply()
            else:
                self.sudo().message_post(body=_(
                    "Approved. The changes are made on %(d)s.",
                    d=format_date(self.env, self.effective_date)))
        elif to_state == 'refused':
            self.sudo().message_post(body=_("Turned down. Nothing on the chart changed."))
        return res

    # ================================================================ apply
    def _apply(self):
        """Make an APPROVED plan's changes on the employee records.

        Never raises: each change runs in its own savepoint and records
        either `applied` or a plain sentence in `error`. The plan goes
        ``applied`` when every change is in; otherwise it stays ``approved``
        with `apply_error` and a chatter line, and the daily job tries the
        rest again."""
        done = self.env['pb.orgchart.plan']
        for plan in self:
            if plan.state != 'approved':
                continue    # never without an approval, for anyone
            sup = plan.sudo()
            planner = sup.user_id
            W = self.env['pb.orgchart'].with_user(planner).sudo().with_context(
                allowed_company_ids=[sup.company_id.id])
            notes = []
            for ch in sup.change_ids.sorted('sequence'):
                if ch.applied:
                    continue
                try:
                    with self.env.cr.savepoint():
                        undo, note = ch.with_env(W.env)._apply_one(W)
                    ch.write({'applied': True, 'error': False,
                              'undo_snapshot': json.dumps(undo) if undo else False})
                    if note:
                        notes.append(note)
                except _Refused as e:
                    ch.write({'error': str(e.args[0])})
                except (UserError, ValidationError, AccessError) as e:
                    msg = str(getattr(e, 'args', [''])[0] or '')
                    ch.write({'error': _("The system said: %(m)s", m=msg) if msg
                              else _("This change could not be made.")})
                except Exception:   # noqa: BLE001 — never raise out of an apply
                    _logger.exception("pb_orgchart: plan %s change %s failed", plan.id, ch.id)
                    ch.write({'error': _("This change could not be made. It will be tried again tomorrow.")})
            left = sup.change_ids.filtered(lambda c: not c.applied)
            n = len(sup.change_ids)
            if not left:
                sup._chain_state_write('applied')
                sup.write({'applied_at': fields.Datetime.now(), 'applied_by': self.env.user.id,
                           'apply_error': False})
                body = escape(_("The plan is live: %(n)s changes made.", n=n) if n != 1
                              else _("The plan is live: 1 change made."))
                done |= plan
            else:
                lines = ["%s — %s" % (c.label, c.error or '') for c in left]
                sup.write({'apply_error': "\n".join(lines)})
                body = escape(_("%(d)s of %(n)s changes were made. These could not be, and are "
                                "tried again every day:", d=n - len(left), n=n))
                body += Markup("<ul>%s</ul>") % Markup("").join(
                    Markup("<li>%s</li>") % ln for ln in lines)
            if notes:
                body += Markup("<ul>%s</ul>") % Markup("").join(
                    Markup("<li>%s</li>") % nt for nt in notes)
            sup.message_post(body=body)
        return done

    @api.model
    def _cron_apply_due(self, today=None):
        """Daily: every approved plan whose day has come. Never raises."""
        today = today or fields.Date.context_today(self)
        plans = self.sudo().search([('state', '=', 'approved'), ('effective_date', '<=', today)],
                                   order='effective_date, id')
        for plan in plans:
            try:
                with self.env.cr.savepoint():
                    plan._apply()
            except Exception:   # noqa: BLE001
                _logger.exception("pb_orgchart: plan %s could not be applied", plan.id)
        return len(plans)


class PbOrgChartPlanChange(models.Model):
    _name = 'pb.orgchart.plan.change'
    _description = 'Org chart plan change'
    _order = 'plan_id, sequence, id'

    plan_id = fields.Many2one('pb.orgchart.plan', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    batch = fields.Char(help="Changes added in one go (several people moved at once, a suggested "
                             "chart) share this, so one Undo takes them all back.")
    kind = fields.Selection(KINDS, required=True)
    employee_id = fields.Many2one('hr.employee', string="Person", ondelete='cascade')
    from_manager_id = fields.Many2one('hr.employee', string="From", ondelete='set null')
    to_manager_id = fields.Many2one('hr.employee', string="To", ondelete='set null')
    whole_team = fields.Boolean(default=True, help="When moving a manager: their team comes along.")
    job_id = fields.Many2one('hr.job', string="Open role", ondelete='cascade')
    title = fields.Char(string="Job title")
    reason = fields.Selection(
        [('growth', "Growth — new position"),
         ('backfill', "Backfill — someone is leaving"),
         ('cover', "Cover for leave")], string="Why the role is open")
    label = fields.Char(string="What changes")
    note = fields.Char(string="Detail")
    applied = fields.Boolean(readonly=True, copy=False)
    error = fields.Char(string="Could not be made", readonly=True, copy=False)
    undo_snapshot = fields.Text(readonly=True, copy=False,
                                help="What the change replaced on the records, to put it back.")

    def _as_dict(self):
        self.ensure_one()
        return {
            'cid': self.id, 'kind': self.kind,
            'employee_id': self.employee_id.id or False,
            'to_manager_id': self.to_manager_id.id or False,
            'from_manager_id': self.from_manager_id.id or False,
            'whole_team': self.whole_team,
            'job_id': self.job_id.id or False,
            'title': self.title or '', 'reason': self.reason or False,
        }

    def _apply_one(self, W):
        """Make this change through P2's helpers. Returns (undo, note) where
        `note` is a sentence for the chatter when reality had moved on."""
        self.ensure_one()
        k = self.kind
        emp = self.employee_id.sudo()
        note = None
        if k == 'move':
            live = emp.parent_id
            if live == self.to_manager_id:
                return None, _("%(p)s already reported to %(m)s.", p=emp.name, m=live.name)
            if self.from_manager_id and live != self.from_manager_id:
                note = _("%(p)s had moved to %(x)s in the meantime.", p=emp.name,
                         x=live.name or _("no manager"))
            _l, undo, _t = W._do_move(emp.id, self.to_manager_id.id, self.whole_team)
            return undo, note
        if k == 'unassign':
            if not emp.parent_id:
                return None, _("%(p)s had no manager any more.", p=emp.name)
            _l, undo, _t = W._do_unassign(emp.id)
            return undo, note
        if k == 'swap':
            _l, undo, _t = W._do_swap(emp.id, expect_manager_id=self.to_manager_id.id or None)
            return undo, note
        if k == 'dotted':
            if (emp.pb_dotted_manager_id.id or False) == (self.to_manager_id.id or False):
                return None, None
            _l, undo, _t = W._do_set_dotted(emp.id, self.to_manager_id.id or False)
            return undo, note
        if k == 'new_role':
            out = W._do_add_open_role(self.to_manager_id.id, self.title, self.reason)
            undo = out[1]
            jobs = out[3] if len(out) > 3 else []
            if jobs:
                self.write({'job_id': jobs[0]})
            return undo, note
        if k == 'move_role':
            job = self.job_id.sudo()
            if W._role_manager(job) == self.to_manager_id:
                return None, None
            out = W._do_move_role(job.id, self.to_manager_id.id)
            return out[1], note
        if k == 'fill_role':
            out = W._do_fill_role(self.job_id.id, emp.id)
            return out[1], note
        if k == 'close_role':
            if self.job_id.sudo().no_of_recruitment <= 0:
                return None, None
            out = W._do_close_role(self.job_id.id)
            return out[1], note
        raise _Refused(_("That kind of change is not known."))


def seed_all(env):
    """Lay the default ``orgplan`` route on every company. Idempotent and
    never fatal (install hook, migration and a later company all call it)."""
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with env.cr.savepoint():
                if env['pb.orgchart.plan']._approval_seed_default(company):
                    done += 1
        except Exception:   # noqa: BLE001 — an upgrade must not die here
            _logger.exception("pb_orgchart: %s has no org chart plan route", company.name)
    return done
