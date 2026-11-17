# -*- coding: utf-8 -*-
"""`pb.conduct.case` — one conduct (disciplinary) case, concern to letter.

    concern  ->  hearing  ->  decision  ->  letter  ->  closed

PRIVACY IS THE DESIGN (owner ruling P3):

  * Only people HR names (this module's two groups) hold ANY access right on
    the case, its notes, its history, its letters or its set-up tables. No
    lifecycle, HR, payroll or administrator group is let in.
  * Nobody named reads a case about THEMSELVES (global rule).
  * No chatter: nothing is posted to `hr.employee` or to any thread other
    people follow, and no email or to-do is ever sent. The case keeps its own
    history (`pb.conduct.event`), readable only by the named people.
  * Hearing minutes and notes are NEVER filed in the documents vault; only a
    FINISHED letter is, under this module's own category, which a global rule
    hides from everybody not named (except the person it is addressed to).
  * Files added to a case are attachments OF THE CASE, so the attachment
    access check follows the case's own rules.
  * The employee sees only their own finished letters, on My Payobook, through
    this module's controller (never through a record rule).
"""

import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, format_datetime

from .conduct_common import (
    DEFAULT_VALID_MONTHS, NOTE_KINDS, OPEN_STATES, OUTCOMES, SIGNOFF_OUTCOMES,
    SIGNOFF_STATES, STATES, WARNING_OUTCOMES, named_users,
)

_logger = logging.getLogger(__name__)


class PbConductCase(models.Model):
    _name = 'pb.conduct.case'
    _description = 'Conduct case'
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False,
                       default=lambda self: _('New'))
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='restrict')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    department_id = fields.Many2one(
        'hr.department', string='Department', index=True,
        help='The department when the case was opened.')
    state = fields.Selection(STATES, string='Step', default='concern',
                             required=True, index=True)
    reason_id = fields.Many2one('pb.conduct.reason', string='Reason',
                                required=True)
    incident_date = fields.Date(string='When it happened')
    summary = fields.Text(string='What happened', required=True)
    raised_by = fields.Char(
        string='Raised by',
        help='Who brought the concern to HR. Free text, not a login: the '
             'person who raised it does not get to see the case.')
    opened_on = fields.Date(string='Opened', default=fields.Date.context_today)

    # ------------------------------------------------------------ hearing
    hearing_date = fields.Datetime(string='Hearing on')
    hearing_place = fields.Char(string='Where')
    hearing_attendees = fields.Char(
        string='Who attends', help='For example: the employee, a companion or '
                                   'employee representative, the HR lead.')
    hearing_held_on = fields.Date(string='Hearing held on')

    # ----------------------------------------------------------- decision
    outcome = fields.Selection(OUTCOMES, string='Decision')
    decision_summary = fields.Text(string='Decision, in a few sentences')
    decided_on = fields.Date(string='Decided on')
    decided_by = fields.Many2one('res.users', string='Decided by')
    valid_until = fields.Date(
        string='Warning valid until',
        help='After this date the warning no longer counts. The usual period '
             'differs by country; check it with your adviser.')
    # ---------------------------------------- second sign-off (ruling CD1)
    # Set when the decision is recorded. A case decided before this existed
    # keeps False and goes on exactly as before ("cases already decided stay
    # as they are") — no migration, no backfill.
    signoff_required = fields.Boolean(string='Needs a second sign-off',
                                      readonly=True, copy=False)
    signoff_state = fields.Selection(SIGNOFF_STATES, string='Second sign-off',
                                     readonly=True, copy=False)
    signoff_asked_by = fields.Many2one('res.users', string='Sign-off asked by',
                                       readonly=True, copy=False)
    signoff_asked_on = fields.Datetime(string='Sign-off asked on', readonly=True,
                                       copy=False)
    signoff_by = fields.Many2one('res.users', string='Second sign-off by',
                                 readonly=True, copy=False)
    signoff_on = fields.Datetime(string='Second sign-off on', readonly=True,
                                 copy=False)
    signoff_note = fields.Char(string='Why it was sent back', readonly=True,
                               copy=False)
    closed_on = fields.Date(string='Closed on')
    close_reason = fields.Char(string='Why it was closed')
    exit_case_id = fields.Integer(string='Leaving checklist', copy=False)

    note_ids = fields.One2many('pb.conduct.note', 'case_id', string='Notes')
    event_ids = fields.One2many('pb.conduct.event', 'case_id', string='History')
    letter_ids = fields.One2many('pb.conduct.letter', 'case_id', string='Letters')

    # ================================================================ create
    @api.model_create_multi
    def create(self, vals_list):
        Emp = self.env['hr.employee'].sudo()
        for vals in vals_list:
            emp = Emp.browse(vals.get('employee_id') or 0).exists()
            if emp:
                vals.setdefault('company_id', emp.company_id.id)
                vals.setdefault('department_id', emp.department_id.id or False)
            if not vals.get('name') or vals.get('name') == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'pb.conduct.case') or _('Case')
        cases = super().create(vals_list)
        for case in cases:
            case._log(_('Case opened: %s.', case.reason_id.name or ''))
        return cases

    # ============================================================== helpers
    def _log(self, text):
        Event = self.env['pb.conduct.event'].sudo()
        for case in self:
            Event.create({'case_id': case.id, 'text': text,
                          'user_id': self.env.uid})

    def _state_label(self):
        return dict(self._fields['state']._description_selection(self.env)).get(
            self.state, '')

    def _outcome_label(self):
        return dict(self._fields['outcome']._description_selection(
            self.env)).get(self.outcome, '') if self.outcome else ''

    def _require_state(self, *states):
        for case in self:
            if case.state not in states:
                raise UserError(_(
                    'This case is at the "%s" step, so that cannot be done now.',
                    case._state_label()))

    # ================================================================ moves
    def action_plan_hearing(self, hearing_date, place=None, attendees=None):
        """Concern -> Hearing (or move an already planned hearing)."""
        self.ensure_one()
        self._require_state('concern', 'hearing')
        if not hearing_date:
            raise UserError(_('Choose the date and time of the hearing.'))
        moved = self.state == 'hearing' and self.hearing_date
        self.write({'state': 'hearing', 'hearing_date': hearing_date,
                    'hearing_place': place or False,
                    'hearing_attendees': attendees or False})
        when = format_datetime(self.env, self.hearing_date, dt_format='d MMM y, HH:mm')
        self._log(_('Hearing moved to %s.', when) if moved
                  else _('Hearing planned for %s.', when))
        return True

    def action_hearing_held(self, held_on=None, minutes=None):
        """Hearing -> Decision. The minutes are a note on the case, never a file."""
        self.ensure_one()
        self._require_state('hearing')
        held_on = held_on or fields.Date.context_today(self)
        self.write({'state': 'decision', 'hearing_held_on': held_on})
        if minutes and minutes.strip():
            self.env['pb.conduct.note'].create({
                'case_id': self.id, 'kind': 'minutes', 'body': minutes.strip(),
                'date': held_on})
        self._log(_('Hearing held on %s.', format_date(self.env, held_on)))
        return True

    def action_skip_hearing(self, why):
        """Concern -> Decision without a hearing (for example: no action)."""
        self.ensure_one()
        self._require_state('concern')
        if not (why or '').strip():
            raise UserError(_('Say in a few words why there is no hearing.'))
        self.write({'state': 'decision'})
        self._log(_('Went to a decision without a hearing: %s', why.strip()))
        return True

    def action_decide(self, outcome, summary, valid_until=None, decided_on=None):
        """Decision -> Letter. Prepares the decision letter as a draft."""
        self.ensure_one()
        self._require_state('decision')
        if outcome not in dict(OUTCOMES):
            raise UserError(_('Choose what was decided.'))
        if not (summary or '').strip():
            raise UserError(_('Write the decision in a few sentences. It goes in the letter.'))
        decided_on = fields.Date.to_date(decided_on) if decided_on else \
            fields.Date.context_today(self)
        if outcome in WARNING_OUTCOMES:
            if valid_until:
                valid_until = fields.Date.to_date(valid_until)
            else:
                valid_until = decided_on + relativedelta(
                    months=DEFAULT_VALID_MONTHS.get(outcome, 12))
            if valid_until <= decided_on:
                raise UserError(_('The warning must stay valid after the day it was decided.'))
        else:
            valid_until = False
        self.write({'state': 'letter', 'outcome': outcome,
                    'decision_summary': summary.strip(), 'decided_on': decided_on,
                    'decided_by': self.env.uid, 'valid_until': valid_until,
                    'signoff_required': outcome in SIGNOFF_OUTCOMES,
                    **self._signoff_blank()})
        self._log(_('Decided: %s.', self._outcome_label()))
        self.env['pb.conduct.letter'].prepare(self, outcome)
        return True

    @staticmethod
    def _signoff_blank():
        return {'signoff_state': False, 'signoff_asked_by': False,
                'signoff_asked_on': False, 'signoff_by': False,
                'signoff_on': False, 'signoff_note': False}

    def _signoff_pending(self):
        """A recorded decision that still waits for its second sign-off."""
        self.ensure_one()
        return bool(self.outcome and self.signoff_required
                    and self.signoff_state != 'confirmed')

    def _draft_decision_letters(self):
        return self.letter_ids.filtered(lambda l: l.kind != 'invite' and l.state == 'draft')

    def action_close(self, why=None):
        """Any open step -> Closed. A case with a decision closes when its
        decision letter is issued; before a decision it needs a reason.

        A decision still waiting for its second sign-off never counts: closing
        such a case (with a reason) drops the unconfirmed decision and its
        draft letter, so no warning is ever on record without two people."""
        self.ensure_one()
        self._require_state(*OPEN_STATES)
        if self.state == 'signoff':
            raise UserError(_('This decision is waiting for a second sign-off. Take it back '
                              'first if the case should close without it.'))
        why = (why or '').strip()
        if self.state in ('concern', 'hearing', 'decision') and not why:
            raise UserError(_('Say in a few words why the case is closed.'))
        unconfirmed = self.state == 'letter' and self._signoff_pending()
        if unconfirmed and not why:
            raise UserError(_('This decision has no second sign-off yet, so its letter cannot '
                              'be issued. To close the case without it, say why.'))
        if self.state == 'letter' and not why and self._draft_decision_letters():
            raise UserError(_('Issue the decision letter first, or say why the case closes without it.'))
        if unconfirmed:
            label = self._outcome_label()
            self._draft_decision_letters().unlink()
            self.write({'outcome': False, 'valid_until': False, 'decided_on': False,
                        'decided_by': False, 'signoff_required': False,
                        **self._signoff_blank()})
            self._log(_('The decision (%s) had no second sign-off and does not count.', label))
        self.write({'state': 'closed', 'closed_on': fields.Date.context_today(self),
                    'close_reason': why or False})
        self._log(_('Case closed: %s', why) if why else _('Case closed.'))
        return True

    # ======================================== second sign-off (ruling CD1)
    def _signers(self):
        """Who may give this decision its second sign-off: a person NAMED for
        conduct cases in the case's company — never the person who recorded
        the decision, never the person who asked for the sign-off, never the
        employee the case is about (named or not)."""
        self.ensure_one()
        out = named_users(self.env, self.company_id)
        banned = (self.decided_by | self.signoff_asked_by
                  | self.employee_id.sudo().user_id)
        return out - banned

    def _can_sign(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(user and user.id in self._signers().ids)

    def _signoff_blocker(self):
        """Why nobody can give the second sign-off now, in screen words; ''
        when somebody can."""
        self.ensure_one()
        if self._signers():
            return ''
        if len(named_users(self.env, self.company_id)) <= 1:
            return _('A second person named for conduct cases is needed to confirm this '
                     'decision. Only one person is named for this company now: name a second '
                     'one on the Access screen.')
        return _('Nobody else named for conduct cases can confirm this decision: the person '
                 'who recorded it, the person who asked and the employee themselves cannot. '
                 'Name another person on the Access screen.')

    def _require_signer(self):
        if not self._can_sign():
            raise UserError(self._signoff_blocker() or _(
                'Only a second person named for conduct cases can do this: not the person '
                'who recorded the decision or asked for the sign-off, and never the '
                'employee themselves.'))

    def action_ask_signoff(self):
        """Letter (decision recorded) -> Second sign-off."""
        self.ensure_one()
        self._require_state('letter')
        if not self._signoff_pending():
            raise UserError(_('This decision does not need a second sign-off.'))
        if not self._draft_decision_letters():
            raise UserError(_('There is no decision letter to confirm. Record the decision again.'))
        self.write({'state': 'signoff', **self._signoff_blank(),
                    'signoff_state': 'waiting', 'signoff_asked_by': self.env.uid,
                    'signoff_asked_on': fields.Datetime.now()})
        self._log(_('Sent for a second sign-off.'))
        return True

    def action_confirm_signoff(self):
        """Second sign-off -> the letter is issued (the employee can read it
        now) and the case closes, exactly as issuing it did before."""
        self.ensure_one()
        self._require_state('signoff')
        self._require_signer()
        letters = self._draft_decision_letters()
        if not letters:
            raise UserError(_('There is no decision letter to confirm. Record the decision again.'))
        self.write({'state': 'letter', 'signoff_state': 'confirmed',
                    'signoff_by': self.env.uid, 'signoff_on': fields.Datetime.now(),
                    'signoff_note': False})
        self._log(_('Decision confirmed by a second named person.'))
        for letter in letters:
            letter.action_issue()
        return True

    def action_send_back(self, why):
        """Second sign-off -> back to the person who recorded the decision."""
        self.ensure_one()
        self._require_state('signoff')
        self._require_signer()
        why = (why or '').strip()
        if not why:
            raise UserError(_('Say in a few words why it goes back.'))
        self.write({'state': 'letter', 'signoff_state': 'sent_back',
                    'signoff_by': self.env.uid, 'signoff_on': fields.Datetime.now(),
                    'signoff_note': why[:500]})
        self._log(_('Sent back by the second sign-off: %s', why[:500]))
        return True

    def action_withdraw_signoff(self):
        """Second sign-off -> back to Letter, by the people waiting on it."""
        self.ensure_one()
        self._require_state('signoff')
        self.write({'state': 'letter', **self._signoff_blank()})
        self._log(_('Taken back before the second sign-off.'))
        return True

    def action_change_decision(self):
        """Letter -> Decision again, while no decision letter is issued.
        The draft letter goes; the decision text stays to start from."""
        self.ensure_one()
        self._require_state('letter')
        if self.letter_ids.filtered(lambda l: l.kind != 'invite' and l.state == 'issued'):
            raise UserError(_('The decision letter has been issued, so the decision cannot change.'))
        label = self._outcome_label()
        self._draft_decision_letters().unlink()
        self.write({'state': 'decision', 'outcome': False, 'valid_until': False,
                    'decided_on': False, 'decided_by': False, 'signoff_required': False,
                    **self._signoff_blank()})
        self._log(_('Decision (%s) taken back to change it.', label))
        return True

    def action_reopen(self):
        self.ensure_one()
        self._require_state('closed')
        back = 'letter' if self.outcome else 'concern'
        self.write({'state': back, 'closed_on': False, 'close_reason': False})
        self._log(_('Case opened again.'))
        return True

    def action_start_exit(self):
        """Dismissal -> the leaving checklist (pb_offboarding), by probe.

        Nothing about the case goes onto the checklist: the lifecycle team can
        read it, so the note it carries is neutral.
        """
        self.ensure_one()
        if self.outcome != 'dismissal':
            raise UserError(_('The leaving checklist is opened only after a dismissal.'))
        if self._signoff_pending():
            raise UserError(_('The leaving checklist opens once the dismissal has its second '
                              'sign-off.'))
        if 'pb.journey.case' not in self.env or 'pb.journey.template' not in self.env:
            raise UserError(_('The leaving checklist is not part of this system.'))
        emp = self.employee_id.sudo()
        Case = self.env['pb.journey.case'].sudo()
        case = Case.search([('employee_id', '=', emp.id),
                            ('case_type', '=', 'offboarding'),
                            ('state', 'in', ('draft', 'active', 'on_hold'))], limit=1)
        if not case:
            template = self.env['pb.journey.template'].sudo().pick_for(
                'offboarding', country_id=Case._employee_country(emp),
                company_id=self.company_id.id)
            case = Case.create({
                'employee_id': emp.id, 'case_type': 'offboarding',
                'template_id': template.id if template else False,
                'anchor_date': fields.Date.context_today(self),
                'source': 'manual', 'company_id': self.company_id.id,
            })
            case.action_open()
        elif hasattr(case, 'setup_offboarding'):
            case.setup_offboarding()
        self.sudo().exit_case_id = case.id
        self._log(_('Leaving checklist opened.'))
        return case.id

    # ================================================================ reads
    def _history_rows(self):
        """The person's OTHER cases, newest first (named readers only)."""
        self.ensure_one()
        others = self.search([('employee_id', '=', self.employee_id.id),
                              ('id', '!=', self.id)], order='id desc', limit=20)
        today = fields.Date.context_today(self)
        return [{
            'id': c.id, 'name': c.name or '',
            'reason': c.reason_id.name or '',
            'opened_on': fields.Date.to_string(c.opened_on) if c.opened_on else '',
            'outcome': c._outcome_label() or c._state_label(),
            'valid_until': fields.Date.to_string(c.valid_until) if c.valid_until else '',
            'live': bool(c.valid_until and c.valid_until >= today and c.state == 'closed'),
        } for c in others]


class PbConductNote(models.Model):
    _name = 'pb.conduct.note'
    _description = 'Conduct case note'
    _order = 'date desc, id desc'

    case_id = fields.Many2one('pb.conduct.case', required=True, index=True,
                              ondelete='cascade')
    company_id = fields.Many2one(related='case_id.company_id', store=True, index=True)
    kind = fields.Selection(NOTE_KINDS, string='Kind', required=True,
                            default='investigation')
    date = fields.Date(string='Date', default=fields.Date.context_today)
    body = fields.Text(string='Note', required=True)
    author_id = fields.Many2one('res.users', string='Written by',
                                default=lambda self: self.env.uid, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        notes = super().create(vals_list)
        for note in notes:
            label = dict(note._fields['kind']._description_selection(note.env)).get(note.kind, '')
            note.case_id._log(_('%s added.', label))
        return notes


class PbConductEvent(models.Model):
    """The case's own history. Written by the case (sudo), never edited."""
    _name = 'pb.conduct.event'
    _description = 'Conduct case history'
    _order = 'id desc'

    case_id = fields.Many2one('pb.conduct.case', required=True, index=True,
                              ondelete='cascade')
    company_id = fields.Many2one(related='case_id.company_id', store=True, index=True)
    user_id = fields.Many2one('res.users', string='By')
    text = fields.Char(string='What happened', required=True)
