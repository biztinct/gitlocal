# -*- coding: utf-8 -*-
"""`pb.goal.change` — asking to change goals that have already been agreed.

A LOCK THAT CANNOT BE OPENED IS A LOCK PEOPLE WORK AROUND. Businesses change in
June: a product is cancelled, a region is merged, somebody's job changes. A goal
year with no way to say so is a goal year that everybody agrees to ignore by
August, and a year everybody ignores is worse than no year at all — because the
company still thinks it has one.

So there is exactly one way to change a locked sheet and it is a REQUEST that
somebody decides. Not an HR override, not an "unlock" button: the same two
people who agreed the goals in the first place agree the change, through the
same sign-off system as everything else on this database.

WHAT IS KEPT. Every carried-out change writes a `pb.goal.audit` row holding the
goal BEFORE and AFTER, who asked, who agreed and why — and the goal itself then
says "Changed on 12 June" on every screen it appears on. A change nobody can
see afterwards is the same as no lock at all; the audit row is what makes the
lock mean something even when it is opened.

THE WEIGHTS STILL HAVE TO ADD UP. A reweight that totals ninety is refused at
SUBMIT — before anybody is asked to decide it — because the alternative is a
manager and an HR lead both agreeing to a year that does not add up, and then
somebody having to explain which of them was wrong.

THE CONSEQUENCE HANGS OFF THE STATUS (R204). `_after_approval_transition` is
called on both the published route and the record's own ladder; the adapter's
`_approval_apply` is the route's half only. A change carried out in one place
and not the other is a change that silently does not happen on a database where
the route was never switched on.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .goals_common import (
    CHANGE_KINDS, CHANGE_KIND_LABEL, CHANGE_OPEN, CHANGE_RANK, CHANGE_STATES,
    CHANGE_STATE_LABEL, GROUP_MANAGER, MAX_GOALS, WEIGHT_TOTAL, as_id, leg,
    weight_sentence,
)

_logger = logging.getLogger(__name__)


class PbGoalChange(models.Model):
    _name = 'pb.goal.change'
    _description = 'Goal change request'
    _inherit = ['mail.thread', 'biz.approval.chain.mixin']
    _order = 'id desc'

    #: The ladder the record keeps for itself when no route is published.
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'manager_ok'): None,
        ('manager_ok', 'approved'): GROUP_MANAGER,
        ('submitted', 'draft'): None,
        ('manager_ok', 'draft'): None,
        ('submitted', 'refused'): None,
        ('manager_ok', 'refused'): GROUP_MANAGER,
    }

    name = fields.Char(string='Reference', compute='_compute_name',
                       store=True, readonly=True)
    set_id = fields.Many2one(
        'pb.goal.set', string='Goal sheet', required=True, index=True,
        ondelete='cascade', tracking=True)
    goal_id = fields.Many2one(
        'pb.goal', string='Which goal', index=True, ondelete='set null',
        tracking=True,
        help='Empty when the request is about the sheet as a whole — a new '
             'goal, or the weights.')
    employee_id = fields.Many2one(
        'hr.employee', string='Whose', related='set_id.employee_id',
        store=True, index=True, readonly=True)
    manager_user_id = fields.Many2one(
        'res.users', string='Their manager', related='set_id.manager_user_id',
        store=True, index=True, readonly=True)
    cycle_id = fields.Many2one(
        'pb.goal.cycle', string='Goal year', related='set_id.cycle_id',
        store=True, index=True, readonly=True)
    department_id = fields.Many2one(
        'hr.department', string='Part of the business',
        related='set_id.department_id', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='set_id.company_id',
        store=True, index=True, readonly=True)

    kind = fields.Selection(CHANGE_KINDS, string='What kind of change',
                            required=True, default='edit', index=True,
                            tracking=True)
    #: THE PROPOSAL, NOT THE CHANGE. Nothing is written to a goal until the
    #: last rung agrees; until then this is what is being asked for, and it is
    #: JSON because its shape is different for each of the four kinds and a
    #: column per kind would be sixteen columns that are empty fifteen
    #: sixteenths of the time.
    payload_json = fields.Text(string='What is being asked for',
                               readonly=True, copy=False)
    summary = fields.Char(string='In one line', compute='_compute_summary',
                          store=True, readonly=True)
    reason = fields.Text(
        string='Why', required=True, tracking=True,
        help='What changed in the business. This is the whole of what the '
             'manager and the HR lead have to go on.')
    requested_by_id = fields.Many2one(
        'res.users', string='Asked by', readonly=True, copy=False,
        default=lambda self: self.env.user)
    state = fields.Selection(CHANGE_STATES, string='Status', default='draft',
                             required=True, index=True, tracking=True,
                             copy=False)
    decided_at = fields.Datetime(string='Decided on', readonly=True,
                                 copy=False)
    applied_at = fields.Datetime(string='Carried out on', readonly=True,
                                 copy=False)
    refuse_note = fields.Text(string='Why it was turned down', readonly=True,
                              copy=False)
    audit_ids = fields.One2many('pb.goal.audit', 'change_id',
                                string='What it changed')

    # ------------------------------------------------------------- computed
    @api.depends('set_id', 'kind')
    def _compute_name(self):
        for record in self:
            record.name = _("Change %(n)s · %(who)s", n=record.id or '',
                            who=record.set_id.sudo().employee_id.name or '')

    def _compute_display_name(self):
        for record in self:
            record.display_name = record.summary or record.name or _('Change')

    @api.depends('kind', 'goal_id', 'payload_json')
    def _compute_summary(self):
        """ONE LINE THAT SAYS WHAT IS BEING ASKED FOR.

        The approver's inbox shows this and nothing else at first glance, so
        it has to carry the actual proposal rather than the word "Change".
        """
        for record in self:
            record.summary = record._summary_sentence()

    def _summary_sentence(self):
        self.ensure_one()
        payload = self.payload()
        title = (self.goal_id.sudo().title or payload.get('title') or '')
        if self.kind == 'drop':
            return _("Drop \"%s\"", title)
        if self.kind == 'add':
            return _("Add a goal: \"%s\"", payload.get('title') or '')
        if self.kind == 'reweight':
            return _("Change the weights on %s",
                     self.set_id.sudo().cycle_id.name or _('this year'))
        new_title = payload.get('title')
        if new_title and title and new_title != title:
            return _("Reword \"%(old)s\" to \"%(new)s\"", old=title,
                     new=new_title)
        return _("Change \"%s\"", title or _('a goal'))

    def _kind_word(self):
        self.ensure_one()
        return CHANGE_KIND_LABEL.get(self.kind, self.kind or '')

    def _state_word(self):
        self.ensure_one()
        return CHANGE_STATE_LABEL.get(self.state, self.state or '')

    def _rank(self):
        self.ensure_one()
        return CHANGE_RANK.get(self.state, 9)

    def payload(self):
        self.ensure_one()
        try:
            return json.loads(self.payload_json or '{}') or {}
        except (TypeError, ValueError):
            return {}

    # ==================================================================
    #  Raising one
    # ==================================================================
    @api.model
    def raise_change(self, set_id, kind, values, reason, goal_id=None):
        """The one door. Used by the employee's page and by the board.

        IT VALIDATES BEFORE IT CREATES, so a request that could never be
        carried out is never raised — a refusal at the moment somebody types
        is a sentence they can act on; a refusal three days later, after two
        people have agreed it, is a waste of everybody's afternoon.
        """
        sheet = self.env['pb.goal.set'].browse(as_id(set_id)).exists()
        if not sheet:
            raise UserError(_("That goal sheet is not there any more."))
        sheet.check_access('read')
        if sheet.state != 'locked':
            raise UserError(_(
                "Goals are only changed by asking once they have been agreed "
                "and locked. These are %s — change them on the sheet "
                "itself.", (sheet._state_word() or '').lower()))
        written = (reason or '').strip()
        if not written:
            raise UserError(_(
                "Say why. A request to change agreed goals with no reason on "
                "it is a request nobody can decide."))
        if kind not in dict(CHANGE_KINDS):
            raise UserError(_("That is not a kind of change this asks for."))
        goal = self.env['pb.goal'].sudo().browse(as_id(goal_id)).exists() \
            if goal_id else self.env['pb.goal'].sudo().browse()
        if goal and goal.set_id.id != sheet.id:
            raise UserError(_("That goal is not on this sheet."))
        if kind in ('edit', 'drop') and not goal:
            raise UserError(_("Say which goal this is about."))
        payload = self._clean_payload(sheet, kind, values, goal)
        record = self.sudo().create({
            'set_id': sheet.id,
            'goal_id': goal.id or False,
            'kind': kind,
            'payload_json': json.dumps(payload),
            'reason': written,
            'requested_by_id': self.env.uid,
        })
        record.message_post(body=_(
            "%(who)s asked for this change. %(why)s",
            who=self.env.user.name or '', why=written))
        return record

    @api.model
    def _clean_payload(self, sheet, kind, values, goal):
        """Everything a proposal needs, checked in the words on the screen."""
        values = dict(values or {})
        if kind == 'drop':
            return {'goal_id': goal.id, 'title': goal.title or ''}
        if kind == 'reweight':
            weights = {int(key): round(float(value or 0), 2)
                       for key, value in dict(
                           values.get('weights') or {}).items()}
            live = {g.id: g for g in sheet.sudo()._all_goals()}
            unknown = [key for key in weights if key not in live]
            if unknown:
                raise UserError(_(
                    "One of those goals is not on this sheet any more. Open "
                    "the page again and have another go."))
            missing = [g for g in live.values() if g.id not in weights]
            if missing:
                raise UserError(_(
                    "Say what every goal is worth, not just the ones that "
                    "change — otherwise the total is a guess. %s has no new "
                    "weight.", ', '.join('"%s"' % (g.title or '')
                                         for g in missing[:4])))
            total = round(sum(weights.values()), 2)
            if abs(total - WEIGHT_TOTAL) > 0.01:
                raise UserError(weight_sentence(total))
            return {'weights': {str(key): value
                                for key, value in weights.items()}}
        # edit and add both carry the same shape as a goal
        out = {}
        title = (values.get('title') or '').strip()
        if kind == 'add' and not title:
            raise UserError(_(
                "Give the new goal a name — one line saying what is going to "
                "be done."))
        if title:
            out['title'] = title[:200]
        description = (values.get('description') or '').strip()
        if kind == 'add' and not description:
            raise UserError(_(
                "Say why the new goal matters and what good looks like."))
        if description:
            out['description'] = description
        for key in ('date_start', 'date_end'):
            if values.get(key):
                out[key] = str(values[key])
        if kind == 'add':
            if not out.get('date_end'):
                raise UserError(_("Say when the new goal should be done by."))
            if len(sheet.sudo()._all_goals()) >= MAX_GOALS:
                raise UserError(_(
                    "%s goals is as many as one sheet holds. Ask to drop one "
                    "first.", MAX_GOALS))
            # A NEW GOAL ARRIVES AT NOUGHT and the weights are a separate
            # request. Two changes in one request is two decisions in one
            # press, and the second one is the one nobody reads.
            out['weight'] = 0.0
            krs = [str(line).strip()
                   for line in (values.get('kr_titles') or [])
                   if str(line).strip()]
            if not krs:
                raise UserError(_(
                    "A goal needs at least one key result — something with a "
                    "number on it that says whether it was met."))
            out['kr_titles'] = krs[:8]
        if kind == 'edit' and not out:
            raise UserError(_("Nothing has been changed on that goal."))
        return out

    # ==================================================================
    #  The presses
    # ==================================================================
    def action_change_submit(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_(
                    "This has already been sent in — it is %s.",
                    (record._state_word() or '').lower()))
            record._check_still_possible()
            record._advance_state('submitted')
        return True

    def action_change_manager_ok(self):
        for record in self:
            record._advance_state('manager_ok')
        return True

    def action_change_approve(self):
        for record in self:
            record._advance_state('approved')
        return True

    def action_change_refuse(self, note=False):
        for record in self:
            if record.state not in CHANGE_OPEN:
                raise UserError(_(
                    "There is nothing waiting to be decided on this one."))
            record.sudo().write({'refuse_note': (note or '').strip() or False})
            record._advance_state('refused', note or '')
        return True

    def _check_still_possible(self):
        """The world may have moved since somebody typed this.

        A request to drop a goal that was already dropped, or to reweight a
        sheet that has since had a goal added, cannot be carried out — and the
        honest moment to say so is when it is sent in, not when somebody
        agrees it.
        """
        self.ensure_one()
        record = self.sudo()
        if record.set_id.state == 'closed':
            raise UserError(_(
                "That goal year has been closed, so its goals cannot change "
                "now."))
        if record.kind in ('edit', 'drop') and not record.goal_id.exists():
            raise UserError(_("That goal is not on the sheet any more."))
        if record.kind == 'reweight':
            payload = record.payload()
            weights = payload.get('weights') or {}
            live = {str(goal.id) for goal in record.set_id._all_goals()}
            if set(weights) != live:
                raise UserError(_(
                    "The goals on this sheet have changed since this was "
                    "written. Open the page again and set the weights once "
                    "more."))
        return True

    # ==================================================================
    #  EVERY CONSEQUENCE HANGS OFF THE STATUS (R204)
    # ==================================================================
    def _after_approval_transition(self, to_state):
        result = super()._after_approval_transition(to_state)
        if to_state == 'approved':
            leg(self.env, 'carrying out change %s' % self.id,
                lambda: self._apply())
        elif to_state == 'refused':
            leg(self.env, 'the turned-down email for change %s' % self.id,
                lambda: self._notify('pb_goals.mail_goals_change_refused'))
        return result

    def _apply(self):
        """Carry the change out, and write down what it did.

        THE AUDIT ROW IS WRITTEN FROM THE BEFORE AND THE AFTER, read either
        side of the write — not predicted from the payload. A payload says
        what somebody asked for; the row has to say what actually happened,
        and the two differ the moment a constraint clips a value (R121's
        lesson from the delegation side: measured, never predicted).
        """
        self.ensure_one()
        record = self.sudo()
        if record.applied_at:
            return False
        sheet = record.set_id
        Goal = self.env['pb.goal'].sudo()
        payload = record.payload()
        before = {}
        after = {}
        if record.kind == 'drop':
            goal = record.goal_id
            before = record._goal_snapshot(goal)
            # ARCHIVED AND NEVER DELETED. A goal somebody worked on for five
            # months is history, and history that is deleted cannot be
            # produced when somebody asks what the year was about.
            goal.write({'active': False})
            after = {'dropped': True}
        elif record.kind == 'add':
            krs = payload.get('kr_titles') or []
            goal = Goal.create({
                'set_id': sheet.id,
                'title': payload.get('title') or '',
                'description': payload.get('description') or '',
                'date_start': payload.get('date_start') or False,
                'date_end': payload.get('date_end') or False,
                'weight': 0.0,
                'locked': True,
                'sequence': (max(sheet._all_goals().mapped('sequence')
                                 or [0]) + 10),
                'kr_ids': [(0, 0, {'title': line,
                                   'sequence': (index + 1) * 10})
                           for index, line in enumerate(krs)],
            })
            record.write({'goal_id': goal.id})
            after = record._goal_snapshot(goal)
        elif record.kind == 'reweight':
            goal = self.env['pb.goal'].sudo().browse()
            weights = payload.get('weights') or {}
            before = {'weights': {
                str(g.id): round(g.weight or 0.0, 2)
                for g in sheet._all_goals()}}
            for key, value in weights.items():
                target = Goal.browse(int(key)).exists()
                if target:
                    target.write({'weight': float(value)})
            sheet.invalidate_recordset(['weight_total'])
            after = {'weights': {
                str(g.id): round(g.weight or 0.0, 2)
                for g in sheet._all_goals()}}
        else:                                       # edit
            goal = record.goal_id
            before = record._goal_snapshot(goal)
            vals = {key: payload[key] for key in
                    ('title', 'description', 'date_start', 'date_end')
                    if key in payload}
            if vals:
                goal.write(vals)
            after = record._goal_snapshot(goal)

        audit = self.env['pb.goal.audit'].sudo().create({
            'change_id': record.id,
            'set_id': sheet.id,
            'goal_id': goal.id or False,
            'kind': record.kind,
            'by_user_id': self.env.uid,
            'before_json': json.dumps(before),
            'after_json': json.dumps(after),
            'what': record.summary or '',
            'reason': record.reason or '',
        })
        record.write({'applied_at': fields.Datetime.now(),
                      'decided_at': fields.Datetime.now()})
        leg(self.env, 'the chatter line for change %s' % record.id,
            lambda: sheet.message_post(body=_(
                "Change agreed and carried out: %(what)s. %(why)s",
                what=record.summary or '', why=record.reason or '')))
        leg(self.env, 'the agreed email for change %s' % record.id,
            lambda: record._notify('pb_goals.mail_goals_change_agreed'))
        return audit

    def _goal_snapshot(self, goal):
        if not goal:
            return {}
        return {
            'title': goal.title or '',
            'description': goal.description or '',
            'weight': round(goal.weight or 0.0, 2),
            'date_start': str(goal.date_start or ''),
            'date_end': str(goal.date_end or ''),
            'krs': [kr.title or '' for kr in goal.kr_ids],
        }

    def _notify(self, template_xmlid):
        """One email to the person whose goals they are (R6: explicit `to`)."""
        self.ensure_one()
        record = self.sudo()
        address = record.set_id._employee_email()
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template or not address:
            return False
        values = {'email_to': address}
        sender = record.set_id._sender()
        if sender:
            values['email_from'] = sender
        template.sudo().send_mail(self.id, force_send=False,
                                  email_values=values)
        return True

    # ------------------------------------------------------------- the door
    def action_view_set(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Goal sheet'),
            'res_model': 'pb.goal.set',
            'res_id': self.set_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }


class PbGoalAudit(models.Model):
    """What a change actually did, kept for as long as the goal is.

    READ-ONLY BY CONSTRUCTION. There is no door that edits one of these and no
    permission that writes one except the system's own: an audit row somebody
    can tidy up is not an audit row.
    """

    _name = 'pb.goal.audit'
    _description = 'Goal change trail'
    _order = 'at desc, id desc'

    change_id = fields.Many2one('pb.goal.change', string='Request',
                                index=True, ondelete='set null')
    set_id = fields.Many2one('pb.goal.set', string='Goal sheet', required=True,
                             index=True, ondelete='cascade')
    goal_id = fields.Many2one('pb.goal', string='Goal', index=True,
                              ondelete='set null')
    company_id = fields.Many2one('res.company', string='Company',
                                 related='set_id.company_id', store=True,
                                 index=True, readonly=True)
    kind = fields.Selection(CHANGE_KINDS, string='What kind of change')
    at = fields.Datetime(string='When', required=True,
                         default=fields.Datetime.now)
    by_user_id = fields.Many2one('res.users', string='Carried out by',
                                 default=lambda self: self.env.user)
    before_json = fields.Text(string='Before')
    after_json = fields.Text(string='After')
    what = fields.Char(string='What changed')
    reason = fields.Text(string='Why')

    def _compute_display_name(self):
        for row in self:
            row.display_name = row.what or _('Change')

    def before(self):
        self.ensure_one()
        try:
            return json.loads(self.before_json or '{}') or {}
        except (TypeError, ValueError):
            return {}

    def after(self):
        self.ensure_one()
        try:
            return json.loads(self.after_json or '{}') or {}
        except (TypeError, ValueError):
            return {}


class PbGoalChanged(models.Model):
    """"Changed on <date>" on the goal it happened to."""

    _inherit = 'pb.goal'

    audit_ids = fields.One2many('pb.goal.audit', 'goal_id',
                                string='Changes to this goal')
    changed_on = fields.Date(string='Last changed on',
                             compute='_compute_changed', store=True,
                             readonly=True)
    change_count = fields.Integer(string='Changes',
                                  compute='_compute_changed', store=True,
                                  readonly=True)

    @api.depends('audit_ids', 'audit_ids.at')
    def _compute_changed(self):
        for goal in self:
            rows = goal.audit_ids
            goal.change_count = len(rows)
            goal.changed_on = max(rows.mapped('at')).date() if rows else False

    def _changed_words(self):
        """"Changed on 12 June 2026, after it was agreed" — or nothing."""
        self.ensure_one()
        if not self.changed_on:
            return ''
        return _("Changed on %s, after it was agreed",
                 self.changed_on.strftime('%d %B %Y'))


class PbGoalSetChanges(models.Model):
    _inherit = 'pb.goal.set'

    change_ids = fields.One2many('pb.goal.change', 'set_id',
                                 string='Change requests')
    audit_ids = fields.One2many('pb.goal.audit', 'set_id',
                                string='What has been changed')
    open_change_count = fields.Integer(
        string='Changes waiting', compute='_compute_open_changes',
        store=True, readonly=True)

    @api.depends('change_ids', 'change_ids.state')
    def _compute_open_changes(self):
        for record in self:
            record.open_change_count = len(record.change_ids.filtered(
                lambda c: c.state in CHANGE_OPEN))
