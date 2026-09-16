# -*- coding: utf-8 -*-
"""`pb.goal.set` — one person's goals for one year, and the thing that travels.

THE SHEET IS WHAT GETS APPROVED, NOT THE GOAL. A manager does not agree to
"grow the north region" on its own; they agree to a set of four goals whose
weights add up to a hundred, which is a different and much better question —
it is the only one that forces somebody to say what matters MOST. So the route
carries the sheet, the goals ride on it, and a goal changed after the manager
agreed reopens the whole thing (the revision stamp, AM32).

WHO TYPES WHAT. The employee writes the goals and the key results. The MANAGER
writes the weights — which is the whole point of the manager's rung, and the
reason the employee sees the weight column read-only on their own page. The HR
lead locks it, and locking is what makes the goals read-only for everybody:
after that only a key result's PROGRESS moves, because progress is not a
change of plan.

WHAT HAPPENS WHEN NOBODY HAS PUBLISHED A ROUTE. `_approval_transitions` below
is the small ladder the record keeps for itself. Under a published route the
shim takes every press and the route decides the order (AM84); with nothing
published this keeps the record usable, which is what makes the module
installable on a database where goal approvals were never switched on.
"""

import logging

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .goals_common import (
    GROUP_MANAGER, MAX_GOALS, P_HR_SENDER, P_MANAGER_MAIL, SET_EDITABLE,
    SET_OPEN, SET_RANK, SET_STATES, SET_STATE_LABEL, WEIGHT_TOTAL, counted,
    due_words, flag, leg, text, weight_sentence,
)

_logger = logging.getLogger(__name__)


class PbGoalSet(models.Model):
    _name = 'pb.goal.set'
    _description = 'Goal sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'deadline asc, id desc'

    #: The ladder the record keeps for itself when no route is published.
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('returned', 'submitted'): None,
        ('submitted', 'manager_ok'): None,
        ('manager_ok', 'locked'): GROUP_MANAGER,
        ('submitted', 'returned'): None,
        ('manager_ok', 'returned'): None,
        ('submitted', 'refused'): None,
        ('manager_ok', 'refused'): GROUP_MANAGER,
    }

    #: ONE SHEET PER PERSON PER YEAR. `_sql_constraints` as a LIST is silently
    #: ignored on Odoo 19 — the rule simply is not enforced and nothing says
    #: so — and a `models.Constraint` class attribute is the form that works.
    _one_per_cycle = models.Constraint(
        'unique(employee_id, cycle_id)',
        'That person already has a goal sheet for this year.')

    # ------------------------------------------------------------ what it is
    name = fields.Char(string='Reference', compute='_compute_name',
                       store=True, readonly=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Whose goals', required=True, index=True,
        ondelete='cascade', tracking=True)
    cycle_id = fields.Many2one(
        'pb.goal.cycle', string='Goal year', required=True, index=True,
        ondelete='restrict', tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    #: WHY IT IS STORED. The board filters on it, the record rule for "my
    #: team's sheets" reads the employee's own parent (so a re-pointed manager
    #: takes effect at once, which is right), and this column is what the
    #: approval route and the reminder email address. Kept in step by
    #: `_compute_manager`, which depends on the hop it is made of (R138).
    manager_user_id = fields.Many2one(
        'res.users', string='Their manager', compute='_compute_manager',
        store=True, readonly=True, index=True)
    manager_employee_id = fields.Many2one(
        'hr.employee', string='Manager', compute='_compute_manager',
        store=True, readonly=True)
    department_id = fields.Many2one(
        'hr.department', string='Part of the business',
        related='employee_id.department_id', store=True, readonly=True)

    deadline = fields.Date(
        string='Goals due by', index=True, tracking=True,
        help='The day their goals are expected to be written and sent in. '
             'Set when the sheet is opened, from the goal year.')
    joined_on = fields.Date(
        string='Joined on', readonly=True,
        help='Kept on the sheet so a person who joined half-way through the '
             'year can be treated fairly later on. Nothing reads it yet.')

    state = fields.Selection(
        SET_STATES, string='Status', default='draft', required=True,
        index=True, tracking=True, copy=False)
    locked_at = fields.Datetime(string='Locked on', readonly=True, copy=False)
    locked_by_id = fields.Many2one(
        'res.users', string='Locked by', readonly=True, copy=False)
    return_note = fields.Text(
        string='What they were asked to change', readonly=True, copy=False,
        help='What the manager or the HR lead wrote when they sent it back. '
             'The employee reads this on their own goals page.')

    goal_ids = fields.One2many('pb.goal', 'set_id', string='Goals')
    goal_count = fields.Integer(string='Goals', compute='_compute_totals',
                                store=True)
    kr_count = fields.Integer(string='Key results',
                              compute='_compute_totals', store=True)
    weight_total = fields.Float(
        string='Weights add up to', compute='_compute_totals', store=True,
        help='The weights on every goal added together. A manager cannot '
             'agree a sheet until this is 100.')
    #: `aggregator`, NOT `group_operator`. Odoo 19 renamed the attribute
    #: (`odoo/orm/fields_numeric.py:23`) and the old spelling is quietly
    #: nothing — a list grouped by department would then SUM four people's
    #: percentages and print 312%.
    progress = fields.Float(
        string='How far along', compute='_compute_progress', store=True,
        aggregator='avg',
        help='The weighted average of how far the goals have got.')

    #: The reminders already sent, as keys. One row rather than one column per
    #: reminder: a job that has to be edited to add a new nudge is a job that
    #: never gets a new nudge.
    reminder_log = fields.Char(string='Reminders already sent', copy=False,
                               readonly=True, default='')

    # ------------------------------------------------------------- computed
    @api.depends('employee_id', 'cycle_id')
    def _compute_name(self):
        for record in self:
            who = record.employee_id.sudo().name or _('Somebody')
            year = record.cycle_id.sudo().name or _('this year')
            record.name = '%s · %s' % (who, year)

    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name or _('Goal sheet')

    @api.depends('employee_id', 'employee_id.parent_id',
                 'employee_id.parent_id.user_id')
    def _compute_manager(self):
        """NAME EVERY HOP THE ANSWER IS MADE OF (R138).

        A compute that depends on the RECORD and not on the fields it reads is
        correct once and then frozen for the life of the environment — a sheet
        still addressed to the manager somebody had in March.
        """
        for record in self:
            manager = record.employee_id.sudo().parent_id
            record.manager_employee_id = manager.id or False
            record.manager_user_id = manager.user_id.id or False

    @api.depends('goal_ids', 'goal_ids.weight', 'goal_ids.kr_ids')
    def _compute_totals(self):
        for record in self:
            goals = record.goal_ids
            record.goal_count = len(goals)
            record.kr_count = sum(len(goal.kr_ids) for goal in goals)
            record.weight_total = sum(goals.mapped('weight'))

    @api.depends('goal_ids.progress', 'goal_ids.weight')
    def _compute_progress(self):
        """Weighted where the weights are set, plain average where they are not.

        A SHEET WHOSE WEIGHTS ARE NOT IN YET STILL HAS A HONEST ANSWER, and it
        is the plain average rather than zero — a screen of zeros over a person
        who has done half their work is how a working feature gets reported as
        broken.
        """
        for record in self:
            goals = record.goal_ids
            if not goals:
                record.progress = 0.0
                continue
            total = sum(goals.mapped('weight'))
            if total > 0:
                record.progress = round(sum(
                    (goal.weight or 0.0) * (goal.progress or 0.0)
                    for goal in goals) / total, 1)
            else:
                record.progress = round(
                    sum(goals.mapped('progress')) / len(goals), 1)

    # -------------------------------------------------------------- guards
    @api.constrains('goal_ids')
    def _check_goal_count(self):
        for record in self:
            if len(record.goal_ids) > MAX_GOALS:
                raise ValidationError(_(
                    "%(n)s goals is more than anybody can hold in their head. "
                    "Keep it to %(max)s.", n=len(record.goal_ids),
                    max=MAX_GOALS))

    @api.constrains('employee_id', 'cycle_id', 'company_id')
    def _check_company(self):
        for record in self:
            cycle = record.cycle_id.sudo()
            if cycle and record.company_id and \
                    cycle.company_id != record.company_id:
                raise ValidationError(_(
                    "%(who)s works for %(their)s and %(cycle)s belongs to "
                    "%(other)s.", who=record.employee_id.sudo().name or '',
                    their=record.company_id.name or '',
                    cycle=cycle.name or '', other=cycle.company_id.name or ''))

    # --------------------------------------------------------------- create
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('company_id') and vals.get('employee_id'):
                employee = self.env['hr.employee'].sudo().browse(
                    vals['employee_id'])
                vals['company_id'] = employee.company_id.id or self.env.company.id
            if not vals.get('joined_on') and vals.get('employee_id'):
                vals['joined_on'] = self._join_date(vals['employee_id'])
            if not vals.get('deadline') and vals.get('cycle_id'):
                cycle = self.env['pb.goal.cycle'].sudo().browse(
                    vals['cycle_id'])
                vals['deadline'] = fields.Date.today() + timedelta(
                    days=max(cycle.submission_days or 14, 1))
        return super().create(vals_list)

    @api.model
    def _join_date(self, employee_id):
        """The join-date ladder, as the rest of the product reads it (R77).

        `first_contract_date` is a real column that is NOT writable on this
        build, so the ladder is: that column, then the earliest contract start,
        then the day the record was made. Read as the system — one field of an
        `hr.employee` prefetches forty and forty of those sit behind payroll
        groups (R56).
        """
        employee = self.env['hr.employee'].sudo().browse(
            int(employee_id or 0)).exists()
        if not employee:
            return False
        try:
            if employee.first_contract_date:
                return employee.first_contract_date
        except Exception:               # noqa: BLE001 — optional column
            pass
        try:
            contract = self.env['hr.contract'].sudo().search(
                [('employee_id', '=', employee.id)],
                order='date_start asc', limit=1)
            if contract and contract.date_start:
                return contract.date_start
        except Exception:               # noqa: BLE001 — not every build has it
            pass
        return employee.create_date.date() if employee.create_date else False

    # ---------------------------------------------------------- the presses
    def _may_edit(self):
        self.ensure_one()
        return self.state in SET_EDITABLE

    def _check_ready_to_submit(self):
        """Everything that has to be true before a sheet can be sent in.

        Said ONCE, here, so the portal button, the backend button and the test
        suite all refuse for the same reason in the same words.
        """
        self.ensure_one()
        record = self.sudo()
        if not record.goal_ids:
            raise UserError(_(
                "There are no goals on this sheet yet. Write at least one, "
                "then send it in."))
        naked = record.goal_ids.filtered(lambda g: not g.kr_ids)
        if naked:
            raise UserError(_(
                "Every goal needs at least one key result — something with a "
                "number on it that says whether the goal was met. %(what)s "
                "%(has)s none yet.",
                what=', '.join('"%s"' % (g.title or '') for g in naked[:4]),
                has=counted(len(naked), _('has'), _('have'))))
        unrated = record.goal_ids.filtered(lambda g: not g.self_rating)
        if unrated:
            raise UserError(_(
                "Say how you think each goal will go before you send it in. "
                "%s is not rated yet.",
                ', '.join('"%s"' % (g.title or '') for g in unrated[:4])))
        undated = record.goal_ids.filtered(lambda g: not g.date_end)
        if undated:
            raise UserError(_(
                "Every goal needs a date it is meant to be done by. %s has "
                "none.", ', '.join('"%s"' % (g.title or '')
                                   for g in undated[:4])))
        return True

    def action_goals_submit(self):
        """Send it in for the manager to read."""
        for record in self:
            if record.state not in SET_EDITABLE:
                raise UserError(_(
                    "This has already been sent in — it is %s.",
                    SET_STATE_LABEL.get(record.state, record.state).lower()))
            record._check_ready_to_submit()
            record.sudo().write({'return_note': False})
            record._advance_state('submitted')
        return True

    def action_goals_send_back(self, note=False):
        """Send it back with a note the employee actually reads.

        THE NOTE IS WRITTEN HERE AND NOT ONLY IN THE ADAPTER. Under a
        published route the press becomes a decision and the engine hands the
        reason to `_approval_return`; with nothing published it goes straight
        down the record's own ladder and the adapter is never called at all.
        Written in both places the note survives either door — and a sheet
        that comes back with no reason is the same as nothing happening.
        """
        for record in self:
            if record.state not in ('submitted', 'manager_ok'):
                raise UserError(_(
                    "There is nothing waiting to be sent back on this one."))
            reason = (note or '').strip() or _(
                "Please have another look at these.")
            record.sudo().write({'return_note': reason})
            if record._chain_open_request():
                record._advance_state('returned', reason)
                continue
            # NOTHING LIVE TO DECIDE, AND THE SHEET IS STILL STRANDED.
            #
            # There is one ordinary way to get here and it is not an edge
            # case: somebody reworded a goal while the sheet was waiting on
            # the HR lead. The engine then correctly refuses to carry out an
            # approval that was given to a different sheet — "This changed
            # after it was sent in… Send it back and ask for it again" — and
            # closes the request. Which leaves the record at "Waiting on the
            # HR lead" with no live request behind it, and the shim answering
            # the very button that message tells you to press with *"This has
            # not been sent in for approval, so there is nothing to decide
            # yet."*
            #
            # So when the route has gone, the record's own ladder takes it
            # back. Found live; the advice the engine gives has to work.
            frm = record.state
            record._chain_engine_write('returned')
            record._chain_log(frm, 'returned', reason)
            record._after_approval_transition('returned')
        return True

    def action_goals_manager_ok(self):
        """The manager agrees. Refused while the weights do not add up."""
        for record in self:
            record._require_weights()
            record._advance_state('manager_ok')
        return True

    def action_goals_lock(self):
        """The HR lead locks it."""
        for record in self:
            record._advance_state('locked')
        return True

    def _require_weights(self):
        """THE ONE RULE THE MANAGER'S RUNG EXISTS FOR.

        Said here rather than in the adapter so that the backend button, the
        engine's pre-decision hook and the test suite all refuse in the same
        words with the same arithmetic in them.
        """
        self.ensure_one()
        total = round(self.sudo().weight_total or 0.0, 2)
        if abs(total - WEIGHT_TOTAL) > 0.01:
            raise UserError(weight_sentence(total))
        return True

    # ==================================================================
    #  EVERY CONSEQUENCE HANGS OFF THE STATE, AND NEVER OFF THE DOOR
    # ==================================================================
    def _after_approval_transition(self, to_state):
        """What happens when a sheet reaches a status, whichever door it came
        through.

        THIS IS NOT A TIDINESS CHOICE. A goal sheet has two ways to move: a
        published approval route, where the engine drives it, and the record's
        own small ladder, used on a database where goal approvals were never
        switched on. The adapter's hooks (`_approval_apply`, `_approval_return`)
        are the ROUTE'S half and are never called on the other path — so a
        consequence written there alone means a sheet that reaches "locked"
        without a route is never actually frozen, and a sheet sent back never
        tells the person. Both are silent, and both look perfectly normal.

        The mixin calls this hook on BOTH paths (`biz_approval_mixin.py:77`
        for the plain ladder; `chain_shim.py:426/451/467/495` for the engine),
        so the consequence hangs off the STATUS and each door only has to say
        which status it reached.

        Every leg is paperwork and is guarded (R104/R131): a lock that
        happened must never be reported as a failure because an email did not.
        """
        result = super()._after_approval_transition(to_state)
        if to_state == 'locked':
            leg(self.env, 'locking goal sheet %s' % self.id,
                lambda: self._do_lock(by_user=self.env.user))
        elif to_state == 'returned':
            leg(self.env, 'the sent-back email for %s' % self.id,
                lambda: self._notify_returned())
        elif to_state == 'submitted' and flag(self.env, P_MANAGER_MAIL):
            leg(self.env, 'the manager email for %s' % self.id,
                lambda: self._notify_manager())
        return result

    # ------------------------------------------------------- what locking IS
    def _do_lock(self, by_user=None):
        """Write the lock and tell the person. Never raises over paperwork."""
        self.ensure_one()
        record = self.sudo()
        if record.locked_at:
            return True
        record.write({
            'locked_at': fields.Datetime.now(),
            'locked_by_id': (by_user or self.env.user).id,
        })
        record.goal_ids.write({'locked': True})
        leg(self.env, 'the locked email', lambda: record._notify_locked())
        record.message_post(body=_(
            "Agreed and locked by %(who)s. The goals cannot be changed now; "
            "progress on the key results still moves.",
            who=(by_user or self.env.user).name or ''))
        return True

    # ------------------------------------------------------------- the mail
    def _sender(self):
        """The address goal emails come from.

        An HR address if somebody has typed one, then the company's own, then
        the address this build sends everything else from. NEVER A PERSON'S —
        a reminder from "the HR team" is a reminder people reply to, and a
        reminder from whoever happened to press the button is a reminder people
        reply to the wrong person.

        THE LAST RUNG IS NOT DECORATION. On this database company 5 carries no
        email address at all, so without it every goal email fell through to
        the template's own `{{ ... or user.email_formatted }}` — and the first
        live run sent "Your goals have come back" FROM the manager's personal
        address. Found by reading the queue rather than the screen.
        """
        self.ensure_one()
        typed = text(self.env, P_HR_SENDER, '')
        if typed:
            return typed
        company = self.sudo().company_id or self.env.company
        if company.email:
            return company.email
        if company.partner_id.email:
            return company.partner_id.email
        return self.env['ir.config_parameter'].sudo().get_param(
            'mail.default.from') or ''

    def _employee_email(self):
        """Read AS THE SYSTEM (R104).

        `private_email` carries `groups="hr.group_hr_user"`, and the person
        doing the sending is very often the employee's own manager, who holds
        no HR group by definition. A mail helper that reads it as the caller
        turns a successful approval into a reported failure.
        """
        self.ensure_one()
        employee = self.employee_id.sudo()
        return (employee.work_email or employee.private_email
                or employee.user_id.email or '')

    def _send(self, template_xmlid, to=None, extra=None):
        """One email, with the recipient passed EXPLICITLY (R6).

        A `mail.template`'s own rendered `email_to` can reach `mail.mail`
        EMPTY — the message is created, queued and addressed to nobody, with
        no error anywhere. Proven side by side. The template keeps its field
        as documentation and this is what actually addresses it.
        """
        self.ensure_one()
        address = to or self._employee_email()
        if not address:
            _logger.info('pb_goals: %s has no email address, so %s was not '
                         'sent', self.employee_id.id, template_xmlid)
            return False
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            return False
        values = {'email_to': address}
        sender = self._sender()
        if sender:
            values['email_from'] = sender
        if extra:
            values.update(extra)
        template.sudo().send_mail(self.id, force_send=False,
                                  email_values=values)
        return True

    def _notify_kickoff(self):
        today = fields.Date.today()
        for record in self:
            leg(record.env, 'the kick-off email for %s' % record.id,
                lambda rec=record: rec._send('pb_goals.mail_goals_kickoff'))
            leg(record.env, 'the kick-off to-do for %s' % record.id,
                lambda rec=record: rec._schedule_activity(
                    rec.deadline or today,
                    _("Write your goals for %s", rec.cycle_id.sudo().name
                      or '')))
        return True

    def _notify_locked(self):
        self.ensure_one()
        return self._send('pb_goals.mail_goals_locked')

    def _notify_returned(self):
        self.ensure_one()
        return self._send('pb_goals.mail_goals_returned')

    def _notify_manager(self):
        """The optional courtesy email to the manager.

        The route already puts the request in their inbox, so this is a second
        message and it is behind its own switch. A manager who lives in their
        inbox gets both; a company that finds it noise turns it off.
        """
        self.ensure_one()
        manager = self.sudo().manager_user_id
        address = manager.email or manager.partner_id.email or ''
        if not address:
            return False
        return self._send('pb_goals.mail_goals_manager_review', to=address)

    def _schedule_activity(self, due, summary):
        """A to-do on somebody's list, WITHOUT a second email (R183).

        `mail.activity.create` notifies every new activity whose assignee is
        not the acting user unless `mail_activity_quick_update` is in the
        context — so a courtesy to-do beside our own email sends a second,
        generically worded message in the same second.
        """
        self.ensure_one()
        user = self.sudo().employee_id.user_id
        if not user:
            return False
        existing = self.env['mail.activity'].sudo().search_count([
            ('res_model', '=', self._name), ('res_id', '=', self.id),
            ('user_id', '=', user.id), ('summary', '=', summary)])
        if existing:
            return False
        self.sudo().with_context(
            mail_activity_quick_update=True).activity_schedule(
                'mail.mail_activity_data_todo', date_deadline=due,
                summary=summary, user_id=user.id)
        return True

    # ------------------------------------------------------------ the words
    def _state_word(self):
        self.ensure_one()
        return SET_STATE_LABEL.get(self.state, self.state or '')

    def _rank(self):
        self.ensure_one()
        return SET_RANK.get(self.state, 9)

    def _due_words(self):
        self.ensure_one()
        if self.state in ('locked', 'refused'):
            return ''
        return due_words(self.deadline, fields.Date.today())

    def _is_open(self):
        self.ensure_one()
        return self.state in SET_OPEN

    # ------------------------------------------------------------- the door
    def action_view_goals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Goals · %s', self.employee_id.sudo().name or ''),
            'res_model': 'pb.goal',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('set_id', '=', self.id)],
            'context': {'default_set_id': self.id},
        }
