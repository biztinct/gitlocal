# -*- coding: utf-8 -*-
"""One contract, decided two months before it runs out.

THE PROBLEM THIS SOLVES IS A DATE NOBODY LOOKED AT. A fixed-term contract ends
on a day somebody typed into a form a year ago. Nothing happens on that day —
no email, no screen, no refusal — the person simply becomes an employee with no
agreement, or stops being paid, or both, and the first anybody hears of it is
the person themselves. `pb.contract.review` is the record that makes that date
somebody's job two months early.

SIX PLACES, AND A REVIEW IS ONLY EVER AT ONE OF THEM:

    upcoming    the end date is known and is still far away
    decide      it is inside the lead time and somebody has to choose
    extension   an extension has been asked for and a manager has to approve it
    conversion  the person is being evaluated for a permanent contract (P5)
    done        somebody chose, and what follows from choosing has happened
    lapsed      nobody chose and the date went past

THE THREE CHOICES, AND WHAT EACH ONE ACTUALLY DOES:

    Let it end      opens the leaving checklist P4 built, anchored at the
                    contract's own end date. The contract is not touched — it
                    ends on its date, which is what "let it end" means.
    Extend it       captures the reason, asks the manager, and on approval
                    creates a NEW contract carrying the old one's terms with
                    new dates on it.
    Make permanent  runs P5's review machine with `kind='conversion'`, and on a
                    pass creates a NEW contract with NO end date.

RULING D1 IS THE WHOLE DESIGN. Neither an extension nor a conversion ever
stretches an existing contract's `date_end` or rewrites its wage. The old
contract is left to end on its own date — the platform's own nightly job closes
it — and the new one starts the day after. Two records, two agreements, one
history somebody can read. `pb_contract_lifecycle` makes exactly one kind of
write to an existing contract and it is `pb_renewed_from_id` on the NEW one.
"""

import json
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .contract_common import (
    DECISION_LABEL, DECISIONS, GROUP_MANAGER, P_EXTENSION_MONTHS, P_LEAD_DAYS,
    P_MAIL, REVIEW_OPEN, REVIEW_STATE_LABEL, REVIEW_STATES, add_months,
    counted, first_name, flag, number,
)

_logger = logging.getLogger(__name__)

#: The fields a new contract copies from the old one BEYOND the four the People
#: wizard already carries (wage, structure, structure type, working schedule).
#: Named explicitly and probed before writing, because a blind `copy()` would
#: also carry the old contract's state, its kanban state and every stamp on it.
CARRIED_FIELDS = (
    'type_id', 'schedule_pay', 'job_id', 'department_id', 'hra',
    'travel_allowance', 'da', 'meal_allowance', 'medical_allowance',
    'other_allowance', 'dependents', 'location', 'tupart', 'shuipart',
    'costcenter', 'company_id',
)


class PbContractReview(models.Model):
    _name = 'pb.contract.review'
    _description = 'Contract Decision'
    # `mail.activity.mixin` as well as `mail.thread`, and it is load-bearing:
    # `activity_schedule()` lives on the ACTIVITY mixin, not on the thread one
    # (R3), and the HR nudges raise their to-dos through it.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'end_date, id'

    name = fields.Char(compute='_compute_name', store=True, string='Decision')
    contract_id = fields.Many2one(
        'hr.contract', string='Contract', required=True, index=True,
        ondelete='cascade', tracking=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', related='contract_id.employee_id',
        store=True, index=True, readonly=True)
    end_date = fields.Date(
        string='Contract ends', index=True, tracking=True,
        help='A snapshot, taken when the decision was raised. Moving the date '
             'on the contract afterwards does not re-plan a decision somebody '
             'has already started working to.')
    lead_days = fields.Integer(
        string='Raised this many days early', default=60,
        help='How far before the end date this decision was put in front of '
             'somebody.')
    trigger_date = fields.Date(
        compute='_compute_trigger_date', store=True,
        string='Decision due from')
    days_left = fields.Integer(
        compute='_compute_days_left', string='Days left')
    state = fields.Selection(
        REVIEW_STATES, string='Status', default='upcoming', required=True,
        index=True, tracking=True)
    decision = fields.Selection(
        DECISIONS, string='Decision', tracking=True)
    decided_by = fields.Many2one('res.users', string='Decided by',
                                 readonly=True)
    decided_at = fields.Datetime(string='Decided on', readonly=True)
    decision_note = fields.Text(string='Why')

    manager_user_id = fields.Many2one(
        'res.users', string='Manager', index=True, ondelete='set null')
    new_contract_id = fields.Many2one(
        'hr.contract', string='The new contract', readonly=True,
        ondelete='set null', copy=False)
    review_id = fields.Many2one(
        'pb.probation.review', string='Evaluation', readonly=True,
        ondelete='set null', copy=False,
        help='The conversion evaluation this decision is waiting on. It is a '
             'probation review with its kind set to conversion — the same '
             'machine, asked a different question.')
    extension_ids = fields.One2many(
        'pb.contract.extension', 'review_id', string='Extension requests')
    exit_case_id = fields.Many2one(
        'pb.journey.case', string='Leaving checklist', readonly=True,
        ondelete='set null', copy=False)
    letter_id = fields.Many2one('pb.hr.letter', string='Letter',
                                readonly=True, ondelete='set null')

    # ---- the stamps that make every job idempotent (R30) ----
    notified = fields.Boolean(string='Raised with HR', readonly=True,
                              copy=False)
    escalated = fields.Boolean(string='Escalated', readonly=True, copy=False)
    nagged_on = fields.Date(string='Last daily nudge', readonly=True,
                            copy=False)
    lapse_alerted = fields.Boolean(string='Lapse reported', readonly=True,
                                   copy=False)

    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    # NOTE ON UNIQUENESS. There is deliberately NO database constraint saying
    # "one open decision per contract". A contract legitimately has several
    # decisions over its life (one that ended in an extension, then the next
    # one), and a partial unique index over the open states would need an
    # explicit flush every time one closes and the next opens in the same
    # breath (R22). `open_for()` is the single door and it searches first,
    # which is the guarantee that actually holds.

    # ------------------------------------------------------------- computes
    @api.depends('employee_id', 'end_date')
    def _compute_name(self):
        for rec in self:
            rec.name = _(
                '%(who)s — contract ends %(when)s',
                who=rec.employee_id.name or _('Employee'),
                when=rec.end_date or _('on a date nobody has set'))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Contract decision')

    @api.depends('end_date', 'lead_days')
    def _compute_trigger_date(self):
        for rec in self:
            rec.trigger_date = (
                rec.end_date - timedelta(days=max(0, rec.lead_days or 0))
                if rec.end_date else False)

    def _compute_days_left(self):
        today = fields.Date.today()
        for rec in self:
            rec.days_left = ((rec.end_date - today).days
                             if rec.end_date else 0)

    # =====================================================================
    #  THE ENTRY POINT.  Idempotent, because it is reached from three places.
    # =====================================================================
    @api.model
    def open_for(self, contract, lead_days=None):
        """The decision for this contract — one at a time, reused, never doubled.

        Reached by the nightly job, by the board's "raise it now" button and by
        anybody opening a contract's own form. All three must find the same
        record (R30).

        `contract` may be a record or an id — over JSON-RPC a recordset
        argument arrives as a plain integer and walks straight past every
        `getattr` (R43), so it is coerced at the door.
        """
        contract = self._as_contract(contract)
        if not contract:
            raise UserError(_("Pick the contract this decision is about first."))
        if not contract.date_end:
            raise UserError(_(
                "%s has no end date, so there is nothing to decide. A contract "
                "with no end date is already permanent.",
                contract.employee_id.name or _('That contract')))
        existing = self.sudo().search([
            ('contract_id', '=', contract.id),
            ('state', 'in', REVIEW_OPEN),
        ], order='id desc', limit=1)
        if existing:
            return existing

        lead = int(lead_days if lead_days is not None
                   else number(self.env, P_LEAD_DAYS, 60))
        emp = contract.employee_id
        manager = emp.parent_id if emp else False
        review = self.sudo().create({
            'contract_id': contract.id,
            'end_date': contract.date_end,
            'lead_days': max(0, lead),
            'manager_user_id': manager.user_id.id
            if (manager and manager.user_id) else False,
            'company_id': (contract.company_id
                           or (emp.company_id if emp else False)
                           or self.env.company).id,
            'state': 'upcoming',
        })
        review.message_post(body=_(
            "Raised because this contract ends on %(when)s. Somebody has to "
            "choose from %(due)s — that is %(lead)s beforehand.",
            when=contract.date_end, due=review.trigger_date or '',
            lead=counted(max(0, lead), _('day'), _('days'))))
        return review

    @api.model
    def _as_contract(self, value):
        """A contract from a record or an id. R43, at the door."""
        Contract = self.env['hr.contract']
        if isinstance(value, models.BaseModel):
            return value[:1].exists()
        if isinstance(value, (int, float)) and value:
            return Contract.sudo().browse(int(value)).exists()
        return Contract.browse()

    # ---------------------------------------------------------------- gates
    def _require_manager(self):
        """Who may decide.

        The HR team, the person's own manager, and an administrator. Not
        "anybody with a login": these three buttons end somebody's employment,
        agree a new one, or start an evaluation with their colleagues in it.
        """
        self.ensure_one()
        user = self.env.user
        if user.has_group(GROUP_MANAGER) or user._is_admin():
            return True
        if self.manager_user_id and self.manager_user_id.id == user.id:
            return True
        raise AccessError(_(
            "Only the HR team or this person's own manager can decide what "
            "happens to their contract."))

    # =====================================================================
    #  WHAT EACH BUTTON WILL DO, IN WORDS, BEFORE IT IS PRESSED
    # =====================================================================
    def decision_preview(self, decision, months=None):
        """The consequence copy the drawer shows above the three buttons.

        Built on the SERVER, because a second opinion written in JavaScript
        would only ever disagree with the one that counts — and because these
        three sentences are the only thing standing between a hurried Friday
        and somebody's job.
        """
        self.ensure_one()
        emp = self.employee_id
        who = first_name(emp.name) or emp.name or _('this person')
        end = self.end_date or self.contract_id.date_end
        lines, blocked = [], []
        if decision == 'terminate':
            lines = [
                _('%(who)s\'s contract runs to %(when)s and then stops. '
                  'Nothing about it is changed.', who=who, when=end),
                _('Their leaving checklist opens, dated %s — the clearances, '
                  'the handover and the exit questionnaire.', end),
                _('No email goes to them from here. Their manager and the HR '
                  'team are told, and somebody speaks to them.'),
            ]
        elif decision == 'extend':
            span = int(months or number(self.env, P_EXTENSION_MONTHS, 12))
            new_start = (end + timedelta(days=1)) if end else False
            new_end = add_months(new_start, span) if new_start else False
            lines = [
                _('You write down why, and %(who)s\'s manager is asked to '
                  'agree it.', who=who),
                _('When they agree, a NEW contract is prepared: %(start)s to '
                  '%(end)s, on exactly the terms of the one running now.',
                  start=new_start, end=new_end),
                _('The contract running now is not touched. It ends on '
                  '%s, as it always would have.', end),
                _('The new contract is prepared as a draft, so somebody reads '
                  'it before it starts.'),
            ]
        elif decision == 'convert':
            lines = [
                _('%(who)s is evaluated the same way a trial period is: their '
                  'manager names three to five colleagues, each gets a private '
                  'link, and the answers come back together.', who=who),
                _('If the evaluation is passed, a NEW contract with NO end '
                  'date is prepared and they are recorded as permanent.'),
                _('If it is not, this comes back here and you choose again. '
                  'Nothing is created and nobody is told they failed.'),
                _('The contract running now is not touched either way.'),
            ]
            if self.review_id and self.review_id.state != 'closed':
                blocked = [_('An evaluation is already running for %s.', who)]
        return {
            'decision': decision,
            'label': DECISION_LABEL.get(decision, ''),
            'lines': lines,
            'blocked': blocked,
        }

    # =====================================================================
    #  1. LET IT END
    # =====================================================================
    def action_terminate(self, note=None):
        """Open the leaving checklist — reusing P4's own way in.

        NOT a second implementation. `pb.journey.case.setup_offboarding()` is
        what P4 built for exactly this: it creates the clearances and the exit
        questionnaire, and it is idempotent, so reaching the same case from a
        resignation, from a failed trial period and from here leaves ONE set of
        rows behind (R30). P5's `action_start_exit` takes the same road and this
        is deliberately the same code, anchored at the contract's end date
        rather than at a trial end.
        """
        self.ensure_one()
        self._require_manager()
        if self.state in ('done',):
            raise UserError(_(
                "This contract was already decided on %(when)s.",
                when=self.decided_at or _('an earlier date')))
        emp = self.employee_id
        if not emp:
            raise UserError(_("This contract has nobody on it."))
        anchor = self.end_date or self.contract_id.date_end \
            or fields.Date.today()
        Case = self.env['pb.journey.case'].sudo()
        case = Case.search([
            ('employee_id', '=', emp.id),
            ('case_type', '=', 'offboarding'),
            ('state', 'in', ('draft', 'active', 'on_hold')),
        ], limit=1)
        if not case:
            template = self.env['pb.journey.template'].sudo().pick_for(
                'offboarding',
                country_id=Case._employee_country(emp),
                company_id=(self.company_id or self.env.company).id)
            case = Case.create({
                'employee_id': emp.id,
                'case_type': 'offboarding',
                'template_id': template.id if template else False,
                'anchor_date': anchor,
                'source': 'manual',
                'company_id': (self.company_id or self.env.company).id,
            })
            case.action_open()
        else:
            case.setup_offboarding()
        self._close('terminate', note=note, exit_case=case)
        case.message_post(body=_(
            "Opened because %(who)s's contract is ending on %(when)s and was "
            "not extended.", who=emp.name or '', when=anchor))
        self.message_post(body=_(
            "The leaving checklist is open — %s.",
            counted(len(case.task_ids), _('step'), _('steps'))))
        self._mail('pb_contract_lifecycle.mail_template_decision_made',
                   self._hr_addresses() + self._manager_addresses())
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.journey.case',
            'res_id': case.id,
            'view_mode': 'form',
        }

    # =====================================================================
    #  2. EXTEND IT
    # =====================================================================
    def action_request_extension(self, reason=None, months=None):
        """Capture the reason and put it in front of the manager.

        THE REASON IS REQUIRED AND THAT IS THE POINT. An extension with no
        reason on it is a decision nobody can review in a year's time, and the
        second extension of the same contract is exactly the thing somebody
        should be able to read the first one's reason before agreeing.
        """
        self.ensure_one()
        self._require_manager()
        if self.state == 'done':
            raise UserError(_("This contract has already been decided."))
        reason = (reason or '').strip()
        if not reason:
            raise UserError(_(
                "Write down why the contract is being extended. In a year "
                "somebody will read this before agreeing the next one."))
        live = self.extension_ids.filtered(
            lambda e: e.state in ('draft', 'pending'))
        if live:
            raise UserError(_(
                "There is already an extension waiting for %s to agree it.",
                live[0].approver_user_id.name or _('a manager')))
        span = max(1, int(months or number(self.env, P_EXTENSION_MONTHS, 12)))
        request = self.env['pb.contract.extension'].sudo().create({
            'review_id': self.id,
            'reason': reason,
            'months': span,
            'company_id': (self.company_id or self.env.company).id,
        })
        request.action_submit()
        self.sudo().write({'state': 'extension'})
        self.message_post(body=_(
            "An extension of %(span)s has been asked for. %(who)s has until "
            "%(when)s to agree it.",
            span=counted(span, _('month'), _('months')),
            who=(request.approver_user_id.name if request.approver_user_id
                 else _('The manager')),
            when=request.approve_by))
        return {'extension_id': request.id,
                'approve_by': str(request.approve_by or '')}

    def _on_extension_approved(self, request):
        """The manager agreed — build the new contract. Called by the request."""
        self.ensure_one()
        end = self.end_date or self.contract_id.date_end
        start = (end + timedelta(days=1)) if end else fields.Date.today()
        new_end = add_months(start, max(1, request.months or 1))
        contract = self._build_new_contract(start, new_end)
        if not contract:
            return False
        self._close('extend', note=request.reason, new_contract=contract)
        self._prepare_letter('pb_contract_lifecycle.letter_template_extension',
                             {'new_start': str(start), 'new_end': str(new_end),
                              'extra': request.reason or ''})
        self._mail('pb_contract_lifecycle.mail_template_extension_done',
                   self._employee_addresses() + self._manager_addresses()
                   + self._hr_addresses())
        return contract

    # =====================================================================
    #  3. MAKE IT PERMANENT
    # =====================================================================
    def action_request_conversion(self):
        """Hand the question to P5's review machine.

        NOT A SECOND EVALUATION ENGINE. `pb.probation.review` already asks a
        manager for three to five colleagues, sends each of them a private
        link, puts the answers together with the check-in notes beside them,
        books the conversation and records a decision. P5 shipped `kind` for
        exactly this and wrote every method against the field rather than
        against the word "probation", so this phase passes one argument instead
        of forking a model.
        """
        self.ensure_one()
        self._require_manager()
        if self.state == 'done':
            raise UserError(_("This contract has already been decided."))
        emp = self.employee_id
        if not emp:
            raise UserError(_("This contract has nobody on it."))
        review = self.env['pb.probation.review'].sudo().open_for(
            emp, kind='conversion', trial_end=self.end_date)
        self.sudo().write({'review_id': review.id, 'state': 'conversion'})
        try:
            review.action_start_nomination()
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not ask for '
                              'colleagues on evaluation %s', review.id)
        review.message_post(body=_(
            "Opened to decide whether %(who)s's fixed-term contract becomes "
            "permanent. It ends on %(when)s.",
            who=emp.name or '', when=self.end_date or ''))
        self.message_post(body=_(
            "An evaluation has been opened. Their manager has been asked to "
            "name three to five colleagues."))
        return {'review_id': review.id}

    def _on_conversion_verdict(self, verdict):
        """What a conversion evaluation's decision means for THIS contract.

        Called from `pb.probation.review._on_verdict` — the hook P5 shipped
        empty and last, so this sees a finished world: the state is on the
        employee record, the letter exists, any next round is scheduled.

        NEVER RAISES. A failure here would undo a verdict somebody has already
        been told about, and the honest fallback is a decision that is still
        open with a note in its chatter saying why.
        """
        self.ensure_one()
        try:
            if verdict == 'pass':
                return self._convert_now()
            # Not a pass. The contract question comes BACK to a person — a
            # module that let it end because a panel said "not yet" would be
            # ending somebody's employment on the strength of a rating.
            self.sudo().write({'state': 'decide'})
            self.message_post(body=_(
                "The evaluation finished without a pass, so nothing has been "
                "created. The choice is back here: let the contract end, "
                "extend it, or evaluate again."))
            self._mail('pb_contract_lifecycle.mail_template_decision_needed',
                       self._hr_addresses() + self._manager_addresses())
            return False
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not act on the '
                              'conversion verdict for decision %s', self.id)
            return False

    def _convert_now(self):
        """A permanent contract, with no end date on it."""
        self.ensure_one()
        end = self.end_date or self.contract_id.date_end
        start = (end + timedelta(days=1)) if end else fields.Date.today()
        contract = self._build_new_contract(start, False)
        if not contract:
            return False
        emp = self.employee_id
        emp.pb_set_employment_type('employee', reason=_(
            "Made permanent on %s, after a conversion evaluation.",
            fields.Date.today()))
        self._close('convert', new_contract=contract)
        self._prepare_letter(
            'pb_contract_lifecycle.letter_template_permanent',
            {'new_start': str(start), 'extra': ''})
        self._mail('pb_contract_lifecycle.mail_template_converted',
                   self._employee_addresses() + self._manager_addresses()
                   + self._hr_addresses())
        return contract

    # =====================================================================
    #  THE ONE PLACE A NEW CONTRACT IS MADE (ruling D1)
    # =====================================================================
    def _build_new_contract(self, date_start, date_end):
        """A NEW contract carrying the old one's terms, with new dates on it.

        THROUGH THE PEOPLE WIZARD'S OWN CREATE PATH, deliberately. The renewal
        prefill (`pb.people.contract.wizard.get_defaults(renew_from=...)`) is
        what the Contracts cockpit's Renew button already uses, and a second
        way of copying a wage would be a second answer to "what did this person
        agree to". The wizard carries the wage, the salary structure, the
        structure type and the working schedule; everything else that has to
        follow the person is copied by the explicit pass below.

        NOTHING IS WRITTEN TO THE OLD CONTRACT. Not its end date, not its
        wage, not its state. It ends on its own date and the platform's own
        nightly job closes it. The only link is `pb_renewed_from_id` on the
        NEW record, pointing back.

        Draft, not running. Two open contracts on one person is a payroll
        question nobody wants answered by accident, and the platform opens a
        draft by itself once somebody has marked it ready.
        """
        self.ensure_one()
        old = self.contract_id
        emp = self.employee_id
        if not (old and emp):
            return self.env['hr.contract'].browse()
        Wizard = self.env['pb.people.contract.wizard'].sudo()
        try:
            defaults = Wizard.get_defaults(employee_id=emp.id,
                                           renew_from=old.id)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not read the '
                              'renewal prefill for contract %s', old.id)
            defaults = {}
        prefill = (defaults or {}).get('prefill') or {}
        label = _('%(who)s — from %(when)s',
                  who=emp.name or '', when=date_start)
        vals = {
            'employee_id': emp.id,
            'name': label,
            'wage': prefill.get('wage', old.wage),
            'date_start': str(date_start),
            'struct_id': prefill.get('struct_id'),
            'structure_type_id': prefill.get('structure_type_id'),
            'resource_calendar_id': prefill.get('resource_calendar_id'),
            'activate': False,
        }
        if date_end:
            vals['date_end'] = str(date_end)
        res = Wizard.create_contract(vals)
        if res.get('error') or not res.get('contract_id'):
            self.message_post(body=_(
                "The new contract could not be prepared: %s. Nothing has been "
                "changed on the contract that is running.",
                res.get('error') or _('unknown reason')))
            _logger.warning('pb_contract_lifecycle: new contract for %s '
                            'refused: %s', emp.id, res.get('error'))
            return self.env['hr.contract'].browse()

        contract = self.env['hr.contract'].sudo().browse(res['contract_id'])
        carried = {}
        for name in CARRIED_FIELDS:
            if name not in contract._fields or name not in old._fields:
                continue
            field = old._fields[name]
            value = old[name]
            if field.type == 'many2one':
                value = value.id if value else False
            if value or value == 0:
                carried[name] = value
        carried['pb_renewed_from_id'] = old.id
        try:
            contract.write(carried)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not carry the '
                              'remaining terms onto contract %s', contract.id)
        contract.message_post(body=_(
            "Prepared from %(old)s, which ends on %(when)s. The terms are the "
            "same; only the dates are new.",
            old=old.name or _('the contract before it'),
            when=old.date_end or ''))
        return contract

    # ------------------------------------------------------------- closing
    def _close(self, decision, note=None, new_contract=None, exit_case=None):
        """Write the decision down. The one place `state` becomes `done`."""
        self.ensure_one()
        vals = {
            'state': 'done',
            'decision': decision,
            'decided_by': self.env.uid,
            'decided_at': fields.Datetime.now(),
        }
        if note:
            vals['decision_note'] = note
        if new_contract:
            vals['new_contract_id'] = new_contract.id
        if exit_case:
            vals['exit_case_id'] = exit_case.id
        self.sudo().write(vals)
        self.message_post(body=_(
            "Decision: %s.", DECISION_LABEL.get(decision, decision)))
        return True

    # ------------------------------------------------------------ the nudges
    def notify_decision_needed(self):
        """"This is now yours" — to HR and to the manager, once.

        BOTH, not one. The manager knows whether the work continues; HR knows
        what the contract has to say. A message to only one of them is a
        message that gets forwarded.
        """
        self.ensure_one()
        if self.state == 'upcoming':
            self.sudo().state = 'decide'
        if self.notified:
            return False
        sent = self._mail('pb_contract_lifecycle.mail_template_decision_needed',
                          self._hr_addresses() + self._manager_addresses())
        self.sudo().notified = True
        self.message_post(body=_(
            "The decision is due. %(who)s and the HR team have been asked to "
            "choose: let it end, extend it, or make it permanent.",
            who=(self.manager_user_id.name if self.manager_user_id
                 else _('The manager'))))
        return sent

    def state_label(self):
        self.ensure_one()
        return REVIEW_STATE_LABEL.get(self.state, self.state or '')

    # ------------------------------------------------------------- letters
    def _prepare_letter(self, xmlid, extra=None):
        """Prepare, file and email a letter. Never raises.

        A letter that could not be produced is a letter somebody writes by
        hand, and it must not undo a contract that has already been created and
        a person who has already been told.
        """
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_contract_lifecycle: %s is missing — no letter '
                            'for decision %s', xmlid, self.id)
            return self.env['pb.hr.letter'].browse()
        try:
            letter = self.env['pb.hr.letter'].sudo().create({
                'employee_id': self.employee_id.id,
                'template_id': template.id,
                'context_json': json.dumps(extra or {}),
                'company_id': (self.company_id or self.env.company).id,
            })
            letter.action_generate()
            if flag(self.env, P_MAIL):
                letter.action_send()
            self.sudo().letter_id = letter.id
            return letter
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not prepare the '
                              'letter for decision %s', self.id)
            return self.env['pb.hr.letter'].browse()

    # ------------------------------------------------------------- the mail
    def _mail(self, xmlid, addresses):
        """Queue one message. Never raises; never counts a dead letter.

        `email_to` is passed EXPLICITLY (R6): a template's own rendered address
        can reach `mail.mail` empty and the message is then created, queued and
        addressed to nobody with no error anywhere.
        """
        self.ensure_one()
        if not flag(self.env, P_MAIL):
            _logger.info('pb_contract_lifecycle: contract emails are switched '
                         'off')
            return False
        clean, seen = [], set()
        for address in (addresses or []):
            address = (address or '').strip()
            if address and address.lower() not in seen:
                seen.add(address.lower())
                clean.append(address)
        if not clean:
            _logger.info('pb_contract_lifecycle: decision %s — nobody to '
                         'write to', self.id)
            return False
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_contract_lifecycle: %s is missing', xmlid)
            return False
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': ','.join(clean),
                              'auto_delete': False})
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not queue %s for '
                              'decision %s', xmlid, self.id)
            return False

    def _manager_addresses(self):
        self.ensure_one()
        out = []
        if self.manager_user_id and self.manager_user_id.email:
            out.append(self.manager_user_id.email)
        manager = self.employee_id.parent_id if self.employee_id else False
        if manager and manager.work_email:
            out.append(manager.work_email)
        return out

    def _hr_addresses(self):
        self.ensure_one()
        out = []
        try:
            people = self.env['pb.journey.case']._users_in_group(
                GROUP_MANAGER, self.company_id or self.env.company, limit=0)
            out.extend(u.email for u in people if u.email)
        except Exception:               # noqa: BLE001
            _logger.debug('pb_contract_lifecycle: no HR addresses for '
                          'decision %s', self.id)
        return out

    def _employee_addresses(self):
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return []
        return [a for a in (emp.work_email, emp.private_email) if a][:1]
